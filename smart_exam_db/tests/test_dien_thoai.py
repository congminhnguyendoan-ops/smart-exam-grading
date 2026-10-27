"""Chụp bằng điện thoại -> chấm ngay (docs/thiet_ke_chup_dien_thoai.md): trang /m, chọn IP LAN, QR, GET /meta/ket-noi, tải ảnh, ảnh tạm.

Phần không cần CSDL chạy mọi nơi. Phần cần CSDL: giao dịch ROLLBACK + thư mục ảnh tạm (conftest). Phần cần cột image_deleted_at
(migration 003) dùng fixture csdl_003 – SKIP rõ cho tới khi migration được áp (test KHÔNG tự áp)."""
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend import don_anh, mang
from conftest import ROOT, can_file
from test_backend_api import anh_trang, giai_quyet_het, tao_de
from test_dang_nhap import bang_moi, client_on, dn, gan, tao_lop, tao_user  # noqa: F401  (fixture dùng lại)

FRONTEND = ROOT / "frontend"
ANH_GIA = ROOT / "data" / "_eval" / "demo_bv" / "gia"       # python tools/thu_bo_demo.py tao-anh


# ------------------------------------------------------------------------------------------------ trang /m (tĩnh)
def test_trang_m_co_cac_phan_tu_chinh():
    html = (FRONTEND / "m.html").read_text(encoding="utf-8")
    o = re.search(r'<input[^>]*id="cam"[^>]*>', html).group(0)
    assert 'type="file"' in o and 'accept="image/*"' in o and 'capture="environment"' in o      # camera gốc, không cần HTTPS
    for id_ in ("v-login", "f-login", "v-exams", "exam-list", "v-cap", "ket-qua", "dang-cham", "counter", "recent", "logout"):
        assert f'id="{id_}"' in html, id_
    for ref in re.findall(r'(?:src|href)="/app/([a-z.]+)"', html):
        assert (FRONTEND / ref).exists(), ref
    assert 'name="viewport"' in html


def test_m_js_khong_luu_token_khong_nen_anh_goi_dung_api():
    js = re.sub(r"/\*.*?\*/|^\s*//.*$", "", (FRONTEND / "m.js").read_text(encoding="utf-8"), flags=re.S | re.M)   # bỏ comment
    assert "localStorage" not in js and "document.cookie" not in js and "Authorization" not in js
    assert "toBlob" not in js and "canvas" not in js.lower()                 # gửi ẢNH GỐC, không nén / đổi kích thước
    assert "FormData" in js and "timeout" in js
    from backend.main import app
    paths = app.openapi()["paths"]
    goi = set(re.findall(r'[`"](/(?:exams|sheets|meta|auth|me)[^`"?]*)[`"]', js))
    assert goi
    for m in goi:
        chuan = re.sub(r"\$\{[^}]+\}", "x", m)
        assert any(re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", p), chuan) for p in paths), f"m.js gọi {m} nhưng API không có"


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để kiểm cú pháp JS")
@pytest.mark.parametrize("ten", ["m.js", "app.js"])
def test_js_dung_cu_phap(ten):
    r = subprocess.run(["node", "--check", str(FRONTEND / ten)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_app_js_co_nut_ket_noi_va_tham_do_khi_tab_hien():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    assert "/meta/ket-noi" in js and "visibilitychange" in js and "document.hidden" in js and "setInterval(thamDo" in js
    assert 'id="ket-noi-dt"' in (FRONTEND / "index.html").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ chọn IP LAN, QR, tường lửa
def test_chon_ip_lan_bo_dia_chi_ao_va_khong_dung_duoc():
    cap = [("Software Loopback Interface 1", "127.0.0.1"), ("Realtek PCIe GbE", "169.254.127.159"), ("Intel Wi-Fi 6 AX201", "192.168.1.142"),
           ("vEthernet (WSL)", "172.29.160.1"), ("Docker Desktop", "10.0.75.1"), ("Microsoft Wi-Fi Direct Virtual Adapter #2", "192.168.137.1"),
           ("Ethernet", "10.10.5.20"), ("Wi-Fi", "fe80::1"), ("Công cộng?", "8.8.8.8"), ("Intel Wi-Fi 6 AX201", "192.168.1.142"),
           ("Bluetooth Device (Personal Area Network)", "169.254.79.160"), ("NordLynx VPN", "10.5.0.2")]
    uv = mang.chon_ung_vien(cap, ip_mac_dinh="10.10.5.20")
    ips = [u.ip for u in uv]
    assert "127.0.0.1" not in ips and not any(i.startswith("169.254.") for i in ips) and "8.8.8.8" not in ips and "fe80::1" not in ips
    assert len(ips) == len(set(ips))
    assert ips[0] == "10.10.5.20"                                            # tuyến mặc định đứng đầu
    that = [u.ip for u in uv if not u.ao]
    assert set(that) == {"10.10.5.20", "192.168.1.142", "192.168.137.1"}      # Wi-Fi Direct (điểm phát sóng Windows) KHÔNG bị coi là ảo
    assert {u.ip for u in uv if u.ao} == {"172.29.160.1", "10.0.75.1", "10.5.0.2"}
    assert ips[-3:] and all(u.ao for u in uv[len(that):])                    # card ảo xếp cuối
    assert next(u for u in uv if u.ip == "192.168.137.1").hotspot


def test_chon_ip_khong_co_mang():
    assert mang.chon_ung_vien([("Loopback", "127.0.0.1"), ("x", "169.254.1.1")]) == []
    assert mang.la_ip_lan("172.16.0.1") and mang.la_ip_lan("172.31.255.1") and not mang.la_ip_lan("172.32.0.1") and not mang.la_ip_lan("abc")


def test_qr_va_lenh_tuong_lua():
    url = mang.url_dien_thoai("192.168.1.142", 8000)
    assert url == "http://192.168.1.142:8000/m"
    svg = mang.qr_svg(url)
    assert svg.lstrip().startswith("<svg") and "<path" in svg
    import segno
    assert segno.make(url, error="m").designator                             # mã hoá được
    assert "█" in mang.qr_terminal(url) or "▀" in mang.qr_terminal(url)
    lt = mang.lenh_tuong_lua(8000)
    assert "-LocalPort 8000" in lt["mo"] and "-Profile Private" in lt["mo"] and "Public" not in lt["mo"] and "Any" not in lt["mo"]
    assert lt["go"].startswith("Remove-NetFirewallRule")
    assert mang.lenh_doi_ho_so('Wi"Fi') == 'Set-NetConnectionProfile -InterfaceAlias "WiFi" -NetworkCategory Private'


def test_mac_dinh_khong_mo_lan_khong_don_anh(monkeypatch):
    monkeypatch.delenv("SMART_EXAM_HOST", raising=False)
    assert mang.dang_mo_lan() is False
    monkeypatch.setenv("SMART_EXAM_HOST", "0.0.0.0")
    assert mang.dang_mo_lan() is True
    from backend.config import lay_cau_hinh
    assert lay_cau_hinh().anh_xoa_tu_dong is False                          # conftest ép tắt: kiểm thử không bao giờ dọn ảnh thật


def test_chay_server_lan_chi_in_khong_chay(capsys):
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import chay_server_lan as C
    C.ho_so_mang = lambda: [("Wi-Fi", "Public")]                              # không gọi PowerShell trong test
    C.in_huong_dan(8000, True)
    out = capsys.readouterr().out
    assert "New-NetFirewallRule" in out and "-Profile Private" in out and "Set-NetConnectionProfile" in out and "Public" in out


# ------------------------------------------------------------------------------------------------ dọn ảnh tạm: phần tệp (thư mục tạm, không CSDL)
def test_xoa_tep_chi_trong_thu_muc_luu_tru(tmp_path):
    kho, ngoai = tmp_path / "kho", tmp_path / "ngoai"
    (kho / "uploads" / "1").mkdir(parents=True)
    ngoai.mkdir()
    a, b = kho / "uploads" / "1" / "a.jpg", ngoai / "b.jpg"
    a.write_bytes(b"x"); b.write_bytes(b"y")
    n, tu_choi = don_anh.xoa_tep(kho, ["uploads/1/a.jpg", "uploads/1/khong_co.jpg", "../ngoai/b.jpg", str(b)])
    assert n == 1 and not a.exists()
    assert b.exists() and set(tu_choi) == {"../ngoai/b.jpg", str(b)}         # KHÔNG BAO GIỜ xoá ngoài storage_dir
    assert (kho / "uploads" / "1").is_dir()                                  # không xoá thư mục


# ------------------------------------------------------------------------------------------------ API (CSDL, ROLLBACK)
def test_trang_m_cong_khai_api_van_can_dang_nhap(client_on):
    r = client_on.get("/m")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and 'capture="environment"' in r.text
    assert client_on.get("/app/m.js").status_code == 200 and client_on.get("/app/m.css").status_code == 200
    assert client_on.get("/meta/ket-noi").status_code == 401                 # thông tin mạng: chỉ người đã đăng nhập
    assert client_on.post("/exams/1/sheets", files={"file": ("a.jpg", anh_trang(), "image/jpeg")}).status_code == 401


def test_meta_ket_noi_khi_dang_nhap(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    k = client_on.get("/meta/ket-noi", headers=dn(client_on, u)).json()
    assert set(k) >= {"lan_bat", "cong", "url", "qr_svg", "ung_vien", "gioi_han_anh_mb"} and k["gioi_han_anh_mb"] == client_on.cfg.gioi_han_anh_mb
    assert all(mang.la_ip_lan(x["ip"]) for x in k["ung_vien"])
    sv, _ = tao_user(bang_moi, vai_tro="student")
    assert client_on.get("/meta/ket-noi", headers=dn(client_on, sv)).status_code == 403


@pytest.fixture
def gv_ky_thi(client_on, bang_moi):
    u, uid = tao_user(bang_moi)
    lop = tao_lop(bang_moi)
    gan(bang_moi, uid, lop["id"])
    h = dn(client_on, u)
    r = client_on.post("/exams", headers=h, json={"exam_title": "Đề thử điện thoại", "subject_code": "TDT1", "subject_name": "Môn thử", "num_questions": 40,
                                                  "class_id": lop["id"], "codes": [{"code": m, "answers": "ABCD" * 10} for m in ("101", "102", "103", "104")]})
    assert r.status_code == 201, r.text
    return h, r.json()["exam_id"]


def test_tai_anh_hong_va_anh_trang_bi_tu_choi(client_on, gv_ky_thi):
    h, eid = gv_ky_thi
    for du_lieu, ma in ((b"khong phai anh", "khong_doc_duoc"), (anh_trang(), None)):
        r = client_on.post(f"/exams/{eid}/sheets", headers=h, files={"file": ("a.jpg", du_lieu, "image/jpeg")})
        assert r.status_code == 201 and r.json()["status"] == "rejected" and r.json()["reject_message"]
        if ma:
            assert r.json()["reject_code"] == ma
    lk = client_on.get("/meta/reject-reasons").json()
    assert lk["khong_doc_duoc"]["advice"]                                    # m.js lấy lời khuyên chụp lại từ đây


def test_tai_anh_qua_lon_bi_chan(client_on, gv_ky_thi):
    from backend.main import app, get_cau_hinh
    h, eid = gv_ky_thi
    app.dependency_overrides[get_cau_hinh] = lambda: replace(client_on.cfg, gioi_han_anh_mb=1)
    r = client_on.post(f"/exams/{eid}/sheets", headers=h, files={"file": ("lon.jpg", b"\xff" * (1024 * 1024 + 1), "image/jpeg")})
    assert r.status_code == 422 and "lớn hơn 1 MB" in r.json()["detail"]


def test_tai_anh_hop_le_tra_du_truong_cho_dien_thoai(client_on, gv_ky_thi):
    can_file(ANH_GIA / "BV01.jpg")
    h, eid = gv_ky_thi
    du_lieu = (ANH_GIA / "BV01.jpg").read_bytes()
    r = client_on.post(f"/exams/{eid}/sheets", headers=h, files={"file": ("BV01.jpg", du_lieu, "image/jpeg")})
    assert r.status_code == 201
    t = r.json()
    assert t["status"] in ("needs_review", "graded") and t["da_ton_tai"] is False
    v = client_on.get(f"/sheets/{t['sheet_id']}", headers=h).json()          # đúng các trường m.js đọc
    assert v["sbd"]["detected"] == "220001" and "can_xem" in v["sbd"] and "reasons" in v["sbd"]
    assert v["exam_code"]["matched_code"] == "101" and v["score"]["provisional"] is not None and "pending_questions" in v["score"]
    assert v["image_deleted_at"] is None and all("reasons" in q for q in v["questions"])
    lai = client_on.post(f"/exams/{eid}/sheets", headers=h, files={"file": ("BV01.jpg", du_lieu, "image/jpeg")}).json()
    assert lai["da_ton_tai"] is True and lai["sheet_id"] == t["sheet_id"]     # ảnh trùng: trả phiếu cũ, không chấm lại


def test_anh_da_xoa_doc_duoc_khi_chua_co_cot(conn_thu):
    """Trước migration 003 (hoặc sau), hàm đọc 'đã xoá' không lỗi: phiếu không tồn tại -> None."""
    from backend import service
    assert service.anh_da_xoa_luc(conn_thu, -1) is None


# ------------------------------------------------------------------------------------------------ dọn ảnh tạm: cần cột (migration 003)
def test_don_anh_dong_ho_gia(client, conn_thu, cau_hinh_thu, csdl_003):
    """Đồng hồ giả + thư mục ảnh tạm (cau_hinh_thu) + ROLLBACK: phiếu đã chốt / bị từ chối bị xoá ảnh sau 24 giờ; phiếu chờ duyệt và
    kỳ thi [DEMO…] được giữ; API ảnh trả 410; điểm và SHA giữ nguyên (tải lại ảnh cũ vẫn nhận ra)."""
    can_file(ANH_GIA / "BV01.jpg", ANH_GIA / "BV02.jpg")
    eid = tao_de(client)
    a1, a2 = (ANH_GIA / "BV01.jpg").read_bytes(), (ANH_GIA / "BV02.jpg").read_bytes()
    gui = lambda e, ten, b: client.post(f"/exams/{e}/sheets", files={"file": (ten, b, "image/jpeg")}).json()   # noqa: E731
    chot = gui(eid, "BV01.jpg", a1)["sheet_id"]
    giai_quyet_het(client, chot)
    v = client.get(f"/sheets/{chot}").json()
    if v["status"] != "graded":                                                # SBD / mã đề chưa chốt -> giáo viên nhập
        v = client.put(f"/sheets/{chot}/identity", json={"sbd": "220001", "exam_code": "101"}).json()
    assert v["status"] == "graded", v["status"]
    diem = v["score"]["official"]
    cho = gui(eid, "BV02.jpg", a2)["sheet_id"]                                # để nguyên: needs_review
    tu_choi = gui(eid, "trang.jpg", anh_trang())["sheet_id"]
    demo = client.post("/exams", json={"exam_title": "Đề thử [DEMO] giữ ảnh", "subject_code": "TDM1", "num_questions": 40,
                                       "codes": [{"code": "101", "answers": "ABCD" * 10}]}).json()["exam_id"]
    tu_choi_demo = gui(demo, "trang.jpg", anh_trang())["sheet_id"]
    kt = [eid, demo]

    bay_gio = datetime.now(timezone.utc)
    assert don_anh.phieu_can_xoa(conn_thu, cau_hinh_thu, bay_gio, ky_thi=kt) == []                       # chưa đủ 24 giờ
    sau = bay_gio + timedelta(hours=25)
    ds = {p["sheet_id"]: p for p in don_anh.phieu_can_xoa(conn_thu, cau_hinh_thu, sau, ky_thi=kt)}
    assert set(ds) == {chot, tu_choi}                                          # KHÔNG: phiếu chờ duyệt, kỳ thi [DEMO…]
    assert len(ds[chot]["tep"]) == 2 + 9 and len(ds[tu_choi]["tep"]) == 1      # gốc + nắn + 9 ô viết tay / chỉ ảnh gốc
    assert all((cau_hinh_thu.storage_dir / p).exists() for p in ds[chot]["tep"])
    assert set(p["sheet_id"] for p in don_anh.phieu_can_xoa(conn_thu, replace(cau_hinh_thu, anh_giu_demo=False), sau, ky_thi=kt)) == {chot, tu_choi, tu_choi_demo}

    kq = don_anh.don(conn_thu, cau_hinh_thu, sau, ky_thi=kt)
    assert kq["phieu_danh_dau"] == 2 and kq["tep_xoa"] == 12 and not kq["tu_choi"]
    assert not any((cau_hinh_thu.storage_dir / p).exists() for p in ds[chot]["tep"] + ds[tu_choi]["tep"])
    assert don_anh.phieu_can_xoa(conn_thu, cau_hinh_thu, sau, ky_thi=kt) == []                           # chạy lại: không còn gì

    for url in (f"/sheets/{chot}/image?kind=original", f"/sheets/{chot}/image?kind=aligned", f"/sheets/{chot}/questions/1/image",
                f"/sheets/{chot}/digits/sbd/0/image", f"/sheets/{tu_choi}/image?kind=original"):
        r = client.get(url)
        assert r.status_code == 410 and "đã được xoá" in r.json()["detail"], url
    v = client.get(f"/sheets/{chot}").json()
    assert v["image_deleted_at"] is not None and v["status"] == "graded" and v["score"]["official"] == diem     # điểm giữ nguyên
    assert client.get(f"/sheets/{cho}/image?kind=aligned").status_code == 200                               # phiếu chờ duyệt còn ảnh
    lai = gui(eid, "BV01.jpg", a1)
    assert lai["da_ton_tai"] is True and lai["sheet_id"] == chot                                             # SHA giữ: vẫn nhận ảnh trùng
