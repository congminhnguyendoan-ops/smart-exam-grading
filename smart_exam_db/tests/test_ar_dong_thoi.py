import psycopg
import pytest

from backend import dong_thoi


def _gia_dua(conn, so_lan_hong: int, ten_rb: str = "bang_ar_tam_pkey"):
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS bang_ar_tam (x int PRIMARY KEY)")
    goi = []

    def nhan(c, cfg, mh, exam_id, du_lieu, ten, user_id, batch_id):
        goi.append(1)
        if len(goi) <= so_lan_hong:
            c.execute("INSERT INTO bang_ar_tam VALUES (1)")
            c.execute("INSERT INTO bang_ar_tam VALUES (1)")
        return 7, False
    return nhan, goi


@pytest.fixture
def rb_dua(monkeypatch):
    monkeypatch.setattr(dong_thoi, "RANG_BUOC_DUA", {"bang_ar_tam_pkey"})


def test_r1_thu_lai_sau_unique_violation_do_dua(conn_thu, rb_dua):
    nhan, goi = _gia_dua(conn_thu, 1)
    kq = dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan)
    assert kq == (7, False) and len(goi) == 2, "lần 1 thua cuộc đua -> lần 2 phải thấy phiếu thắng và thành công"
    assert conn_thu.execute("SELECT count(*) AS n FROM bang_ar_tam").fetchone()["n"] == 0, "phần ghi dở của lần thua phải bị hoàn tác (savepoint)"
    assert conn_thu.info.transaction_status.name == "INTRANS", "giao dịch ngoài vẫn sống (không rollback cả yêu cầu)"


def test_r1_khoa_muc_ky_thi_lay_khi_thu_lai_va_giu_den_het_giao_dich(conn_thu, rb_dua):
    from backend.db import ket_noi
    nhan, _ = _gia_dua(conn_thu, 1)
    dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 424242, b"x", "a.jpg", 1, nhan=nhan)
    with ket_noi() as c2:
        c2.execute("SET TRANSACTION READ ONLY")
        giu = c2.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS ok", ("ar:thu-lai:424242",)).fetchone()["ok"]
        c2.rollback()
    assert giu is False, "khoá mức kỳ thi 'thu-lai' phải đang được giữ bởi giao dịch này"


def test_r1_rang_buoc_khac_khong_bi_nuot(conn_thu):
    nhan, goi = _gia_dua(conn_thu, 5)
    with pytest.raises(psycopg.errors.UniqueViolation):
        dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan)
    assert len(goi) == 1


def test_r1_het_so_lan_thu_thi_nem_loi_that(conn_thu, rb_dua):
    nhan, goi = _gia_dua(conn_thu, 99)
    with pytest.raises(psycopg.errors.UniqueViolation):
        dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan)
    assert len(goi) == dong_thoi.SO_LAN_THU


def test_r1_khong_dua_thi_goi_dung_mot_lan(conn_thu):
    nhan, goi = _gia_dua(conn_thu, 0)
    assert dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan) == (7, False) and len(goi) == 1


def test_r1_main_dung_tang_dieu_phoi_va_khong_goi_thang_service_nhan_anh():
    import inspect

    from backend import main
    nguon = inspect.getsource(main)
    assert "service.nhan_anh(" not in nguon and nguon.count("dong_thoi.nhan_anh_an_toan(") == 2


def test_r1_tep_dong_bang_khong_bi_cham():
    import hashlib

    from conftest import ROOT
    mong = {"backend/service.py": "2537b4f51a00a167c1c2d9d45e9ff29fcd9e149d8a3e6260b4ce6dd875847f8e", "backend/schemas.py": "05310795f5646007320a3dd1795ffb971eea5e45cd4bf882115e7dcb84cd231d",
            "models/ocr_cnn.json": "a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8", "models/omr_m1.json": "507ecc7b4f885e148c1a896884f8a285ea4e308de4477e47f870bebf7c059797",
            "cv_engine/ocr.py": "e9b3e00fc0917341756441d5aecc39abc14a85861b35844e6506cae33a26b4be", "cv_engine/omr.py": "e0111fc1909af598f7df882b40bda9bb8d509e2c25c2423ea0e15963786c1912",
            "cv_engine/preprocessing.py": "0d35c26ae716778d11ec69382da5c1dff70e5a88b455ae8946091393d618f237",
            "cv_engine/tap_du_lieu.py": "3f030b71ece0b3117db0465c2ebbe3cf1948911140deb002f20a333d37fd9f01"}
    for tep, sha in mong.items():
        du_lieu = (ROOT / tep).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(du_lieu).hexdigest() == sha, f"{tep} đã bị đổi – tệp đóng băng (docs/tieu_chi_sua_ah.md mục 0)"


def _khoa_dang_giu(ten: str) -> bool:
    from backend.db import ket_noi
    with ket_noi() as c2:
        c2.execute("SET TRANSACTION READ ONLY")
        ok = c2.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS ok", (ten,)).fetchone()["ok"]
        c2.rollback()
    return not ok


def test_r2_khoa_theo_ky_thi_va_bam_anh(conn_thu):
    import hashlib
    nhan, _ = _gia_dua(conn_thu, 0)
    anh = b"noi dung anh r2"
    dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 31337, anh, "a.jpg", 1, nhan=nhan)
    sha = hashlib.sha256(anh).hexdigest()
    assert _khoa_dang_giu(f"ar:anh:31337:{sha}"), "yêu cầu thứ hai CÙNG ảnh, CÙNG kỳ thi phải bị chặn tới khi giao dịch này kết thúc"
    assert not _khoa_dang_giu(f"ar:anh:31338:{sha}"), "kỳ thi khác: không chặn"
    assert not _khoa_dang_giu(f"ar:anh:31337:{hashlib.sha256(b'anh khac').hexdigest()}"), "ảnh khác: không chặn"


def test_r2_lo_khong_khoa_theo_anh(conn_thu):
    import hashlib
    nhan, _ = _gia_dua(conn_thu, 0)
    anh = b"anh trong lo r2"
    dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 31339, anh, "a.jpg", 1, nhan=nhan, khoa_theo_anh=False)
    assert not _khoa_dang_giu(f"ar:anh:31339:{hashlib.sha256(anh).hexdigest()}")


def test_r2_main_lo_tai_nhieu_anh_tat_khoa_theo_anh():
    import inspect

    from backend import main
    nguon = inspect.getsource(main.tai_nhieu_anh)
    assert "khoa_theo_anh=False" in nguon and "khoa_theo_anh" not in inspect.getsource(main.tai_mot_anh)


def test_r3_lo_lay_khoa_muc_ky_thi_dau_lo(client, conn_thu):
    from test_backend_api import anh_trang, tao_de
    eid = tao_de(client)
    r = client.post(f"/exams/{eid}/sheets/batch", files=[("files", ("t.jpg", anh_trang(), "image/jpeg"))])
    assert r.status_code == 201 and r.json()["tong"] == 1
    assert _khoa_dang_giu(f"ar:lo:{eid}"), "lô phải giữ khoá mức kỳ thi tới hết giao dịch"
    assert not _khoa_dang_giu(f"ar:lo:{eid + 1}")


def test_r3_khoa_lo_lay_truoc_khi_xu_ly_anh_dau_tien():
    import inspect

    from backend import main
    nguon = inspect.getsource(main.tai_nhieu_anh)
    assert nguon.index('khoa_ky_thi(conn, exam_id, "lo")') < nguon.index("INSERT INTO scan_batches") < nguon.index("nhan_anh_an_toan(")


from test_dang_nhap import MK, bang_moi, client_on, tao_user  # noqa: E402,F401  (fixture dùng lại)

DUONG_CO_XAC_THUC = [("GET", "/me", None), ("GET", "/me/classes", None), ("GET", "/exams", None), ("GET", "/exams/1/sheets", None), ("GET", "/exams/1/results", None),
                     ("GET", "/sheets/1", None), ("GET", "/meta/ket-noi", None), ("PATCH", "/me", {"full_name": "Tên mới"}), ("POST", "/me/password", {})]


def _goi(client_on, token, cach):
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        h = {"Authorization": f"Bearer {token}"} if cach == "bearer" and token else {}
        if cach == "cookie" and token:
            c.cookies.set("se_session", token)
        return [c.request(m, d, json=js, headers=h).status_code for m, d, js in DUONG_CO_XAC_THUC]


def _dang_xuat(token, cach="bearer"):
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        if cach == "cookie" and token:
            c.cookies.set("se_session", token)
        return c.post("/auth/logout", headers={"Authorization": f"Bearer {token}"} if cach == "bearer" and token else {}).status_code


def _dang_nhap_lay_token(client_on, ten):
    r = client_on.post("/auth/login", json={"username": ten, "password": MK})
    assert r.status_code == 200
    return r.cookies.get("se_session") or client_on.cookies.get("se_session")


def test_r4_moi_lan_dang_nhap_mot_token_khac_nhau(client_on, bang_moi):
    ten, _ = tao_user(bang_moi)
    t1, t2 = _dang_nhap_lay_token(client_on, ten), _dang_nhap_lay_token(client_on, ten)
    assert t1 != t2, "hai lần đăng nhập (kể cả cùng một giây) phải ra hai token khác nhau"


def test_r4_dang_xuat_thu_hoi_dung_mot_phien(client_on, bang_moi):
    ten, _ = tao_user(bang_moi)
    t1, t2 = _dang_nhap_lay_token(client_on, ten), _dang_nhap_lay_token(client_on, ten)
    assert all(x != 401 for x in _goi(client_on, t1, "cookie") + _goi(client_on, t1, "bearer"))
    assert _dang_xuat(t1, "bearer") == 204
    assert _goi(client_on, t1, "cookie") == [401] * len(DUONG_CO_XAC_THUC), "T1 (cookie) phải 401 trên MỌI đường dẫn có xác thực"
    assert _goi(client_on, t1, "bearer") == [401] * len(DUONG_CO_XAC_THUC), "T1 (Bearer) phải 401 trên mọi đường dẫn"
    assert all(x != 401 for x in _goi(client_on, t2, "cookie") + _goi(client_on, t2, "bearer")), "phiên khác của CÙNG tài khoản không bị ảnh hưởng"
    n = bang_moi.execute("SELECT count(*) AS n, bool_and(token_sha256 <> %s) AS khong_luu_token_tho FROM revoked_tokens WHERE user_id = (SELECT user_id FROM users WHERE username = %s)",
                         (t1, ten)).fetchone()
    assert n["n"] == 1 and n["khong_luu_token_tho"], "chỉ 1 dòng (băm), không lưu token thô"


def test_r4_token_gia_van_401_va_khong_ghi_bang(client_on, bang_moi):
    ten, _ = tao_user(bang_moi)
    t = _dang_nhap_lay_token(client_on, ten)
    truoc = bang_moi.execute("SELECT count(*) AS n FROM revoked_tokens").fetchone()["n"]
    for gia in ("v1.abc.def", "rac", t[:-3] + ("AAA" if not t.endswith("AAA") else "BBB"), t.replace("v1.", "v2.", 1)):
        assert _goi(client_on, gia, "bearer") == [401] * len(DUONG_CO_XAC_THUC)
        assert _dang_xuat(gia, "bearer") == 204 and _dang_xuat(gia, "cookie") == 204
    assert _dang_xuat(None) == 204
    assert bang_moi.execute("SELECT count(*) AS n FROM revoked_tokens").fetchone()["n"] == truoc, "token giả / không token KHÔNG được ghi vào bảng"


def test_r4_dang_xuat_lap_lai_an_toan(client_on, bang_moi):
    ten, _ = tao_user(bang_moi)
    t = _dang_nhap_lay_token(client_on, ten)
    for _ in range(3):
        assert _dang_xuat(t, "bearer") == 204
    assert bang_moi.execute("SELECT count(*) AS n FROM revoked_tokens WHERE user_id = (SELECT user_id FROM users WHERE username = %s)", (ten,)).fetchone()["n"] == 1


def test_r4_thu_hoi_hieu_luc_ngay_ca_khi_chua_commit(client_on, bang_moi, monkeypatch):
    from backend import nguoi_dung
    ten, _ = tao_user(bang_moi)
    t = _dang_nhap_lay_token(client_on, ten)
    assert _dang_xuat(t, "bearer") == 204
    bang_moi.execute("DELETE FROM revoked_tokens WHERE user_id = (SELECT user_id FROM users WHERE username = %s)", (ten,))
    assert _goi(client_on, t, "bearer") == [401] * len(DUONG_CO_XAC_THUC) and nguoi_dung.bam_token(t) in nguoi_dung._THU_HOI_TRONG_BO_NHO


def test_r4_demo_mode_dang_xuat_khong_dung_bang(client):
    truoc = client.app.state.cfg.auth_mode
    assert client.post("/auth/logout").status_code == 204 and truoc in ("on", "demo")


def test_r4_khoi_dong_thieu_bang_thu_hoi_thi_tu_choi():
    import inspect

    from backend import main
    nguon = inspect.getsource(main.lifespan)
    assert "revoked_tokens" in nguon and "LoiCauHinh" in nguon


def test_r5_cong_cham_gioi_han_va_503_khi_qua_han():
    import threading
    import time

    cong = dong_thoi.CongCham(2, 0.3)
    dang, dinh, ket = [0], [0], []
    khoa = threading.Lock()

    def viec():
        try:
            with cong.vao():
                with khoa:
                    dang[0] += 1
                    dinh[0] = max(dinh[0], dang[0])
                time.sleep(0.5)
                with khoa:
                    dang[0] -= 1
            ket.append("ok")
        except dong_thoi.QuaTai as e:
            ket.append(("503", e.retry_after))
    ts = [threading.Thread(target=viec) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert dinh[0] <= 2, "không bao giờ quá giới hạn đồng thời"
    assert ket.count("ok") == 2 and sum(1 for x in ket if isinstance(x, tuple)) == 4, ket
    assert all(x[1] >= 1 and isinstance(x[1], int) for x in ket if isinstance(x, tuple))
    with cong.vao():
        pass


def test_r5_nha_cho_ca_khi_viec_ném_loi():
    cong = dong_thoi.CongCham(1, 0.2)
    with pytest.raises(RuntimeError):
        with cong.vao():
            raise RuntimeError("x")
    with cong.vao():
        pass


def test_r5_20_yeu_cau_cung_luc_moi_yeu_cau_thanh_cong_hoac_503_va_khong_vuot_gioi_han():
    import threading
    import time

    cong = dong_thoi.CongCham(3, 2.0)
    dang, dinh, ket, khoa = [0], [0], [], threading.Lock()

    def viec(i):
        try:
            with cong.vao():
                with khoa:
                    dang[0] += 1
                    dinh[0] = max(dinh[0], dang[0])
                time.sleep(0.15)
                with khoa:
                    dang[0] -= 1
            ket.append(200)
        except dong_thoi.QuaTai:
            ket.append(503)
    ts = [threading.Thread(target=viec, args=(i,)) for i in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert set(ket) <= {200, 503} and len(ket) == 20 and dinh[0] <= 3 and ket.count(200) >= 3


def test_r5_mac_dinh_toi_thieu_2_hai_luot_cua_giao_dien_khong_bao_gio_cho():
    import threading
    import time

    from backend.config import CauHinh
    assert CauHinh.__dataclass_fields__["cham_dong_thoi"].default >= 2 and CauHinh.__dataclass_fields__["cham_cho_giay"].default > 0
    cong = dong_thoi.CongCham(CauHinh.__dataclass_fields__["cham_dong_thoi"].default, 0.05)
    ok = []

    def luot():
        with cong.vao():
            time.sleep(0.2)
        ok.append(1)
    ts = [threading.Thread(target=luot) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(ok) == 2


def test_r5_cau_hinh_bien_moi_truong(monkeypatch):
    from backend.config import LoiCauHinh, lay_cau_hinh
    monkeypatch.delenv("CHAM_DONG_THOI", raising=False)
    monkeypatch.delenv("CHAM_CHO_GIAY", raising=False)
    c = lay_cau_hinh()
    assert (c.cham_dong_thoi, c.cham_cho_giay) == (4, 30.0)
    monkeypatch.setenv("CHAM_DONG_THOI", "3")
    monkeypatch.setenv("CHAM_CHO_GIAY", "8")
    c = lay_cau_hinh()
    assert (c.cham_dong_thoi, c.cham_cho_giay) == (3, 8.0)
    for ten, xau in (("CHAM_DONG_THOI", "0"), ("CHAM_DONG_THOI", "abc"), ("CHAM_DONG_THOI", "-2"), ("CHAM_CHO_GIAY", "0"), ("CHAM_CHO_GIAY", "x"), ("CHAM_CHO_GIAY", "99999")):
        monkeypatch.setenv(ten, xau)
        with pytest.raises(LoiCauHinh):
            lay_cau_hinh()
        monkeypatch.setenv(ten, "3" if ten == "CHAM_DONG_THOI" else "8")


def test_r5_endpoint_tra_503_kem_retry_after_khi_cong_day(client, conn_thu):
    from test_backend_api import anh_trang, tao_de
    eid = tao_de(client)
    app_state = client.app.state
    cu = getattr(app_state, "cong_cham", None)
    app_state.cong_cham = cong = dong_thoi.CongCham(1, 0.2)
    try:
        with cong.vao():
            r = client.post(f"/exams/{eid}/sheets", files={"file": ("a.jpg", anh_trang(), "image/jpeg")})
            rl = client.post(f"/exams/{eid}/sheets/batch", files=[("files", ("a.jpg", anh_trang(), "image/jpeg"))])
        assert r.status_code == 503 and r.headers["retry-after"].isdigit() and int(r.headers["retry-after"]) >= 1 and "bận" in r.json()["detail"]
        assert rl.status_code == 503 and rl.headers["retry-after"].isdigit()
        assert client.post(f"/exams/{eid}/sheets", files={"file": ("a.jpg", anh_trang(), "image/jpeg")}).status_code == 201
    finally:
        if cu is None:
            del app_state.cong_cham
        else:
            app_state.cong_cham = cu


def test_r5_cong_cham_lay_truoc_khoa_csdl():
    import inspect

    from backend import main
    don, lo = inspect.getsource(main.tai_mot_anh), inspect.getsource(main.tai_nhieu_anh)
    assert don.index("cong.vao()") < don.index("nhan_anh_an_toan(")
    assert lo.index("cong.vao()") < lo.index('khoa_ky_thi(conn, exam_id, "lo")')
