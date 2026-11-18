import io
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from backend import auth, demo
from backend.phan_quyen import MA_LOP_KHONG_DUNG
from test_backend_api import anh_trang

MK = "MatKhau-Thu-123"
BAM_GIA_SEED = "$2b$12$KIXQJ6vY0nZ0r8bB1rj3NuQm5YfV1N3x7n0gM1W6xFvX4v2Q9m3yS"


@pytest.fixture
def bang_moi(conn_thu):
    r = conn_thu.execute("SELECT to_regclass('teacher_classes') AS t, (SELECT count(*) FROM information_schema.columns "
                         "WHERE table_name = 'exams' AND column_name = 'class_id') AS c").fetchone()
    if r["t"] is None or r["c"] == 0:
        pytest.skip("SKIP: migration 002 chưa áp (python -m backend.migrate) – test phân quyền theo lớp KHÔNG được tính là đạt")
    return conn_thu


@pytest.fixture
def client_on(bang_moi, cau_hinh_thu, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app, get_cau_hinh, get_conn
    cfg = replace(cau_hinh_thu, auth_mode="on", auth_secret="t" * 48)
    monkeypatch.setattr(auth, "gioi_han", auth.GioiHanDangNhap())

    def _conn():
        yield bang_moi
    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_cau_hinh] = lambda: cfg
    with TestClient(app) as c:
        c.cfg = cfg
        yield c
    app.dependency_overrides.clear()


def tao_user(conn, vai_tro="teacher", mk=MK, active=True, bam=None) -> tuple[str, int]:
    u = "t" + uuid.uuid4().hex[:10]
    conn.execute("INSERT INTO users (username, email, password_hash, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s::user_role, %s)",
                 (u, f"{u}@test.local", bam or auth.bam_mat_khau(mk), f"Người dùng {u}", vai_tro, active))
    return u, conn.execute("SELECT user_id FROM users WHERE username = %s", (u,)).fetchone()["user_id"]


def tao_lop(conn, so_sv=0, ten_sv="Sinh viên") -> dict:
    ma = "L" + uuid.uuid4().hex[:8].upper()
    cid = conn.execute("INSERT INTO classes (class_code, class_name, academic_year) VALUES (%s, %s, '2026-2027') RETURNING class_id",
                       (ma, f"Lớp thử {ma}")).fetchone()["class_id"]
    for i in range(so_sv):
        conn.execute("INSERT INTO students (student_code, full_name, class_id, email, gender) VALUES (%s, %s, %s, %s, 'Nam')",
                     (str(uuid.uuid4().int)[:12], f"{ten_sv} {ma} số {i + 1}", cid, f"sv{i}{ma.lower()}@test.local"))
    return {"id": cid, "ma": ma}


def gan(conn, uid, cid, sid=None):
    conn.execute("INSERT INTO teacher_classes (user_id, class_id, subject_id) VALUES (%s, %s, %s)", (uid, cid, sid))


def dn(client, username, mk=MK) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": mk})
    assert r.status_code == 200, r.text
    token = r.cookies.get(auth.COOKIE)
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def ky_thi(client, h, **them) -> int:
    r = client.post("/admin/exams" if "teacher_user_id" in them else "/exams", headers=h, json={"exam_title": "Đề thử phân quyền", "subject_code": "T" + uuid.uuid4().hex[:8].upper(),
                                               "subject_name": "Môn thử", "num_questions": 10,
                                               "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}], **them})
    assert r.status_code == 201, r.text
    return r.json()["exam_id"]


def tai_trang(client, h, eid, ten="x"):
    return client.post(f"/exams/{eid}/sheets", headers=h, files={"file": (f"{ten}.jpg", anh_trang(), "image/jpeg")})


@pytest.fixture
def the_gioi(client_on, bang_moi):
    c, conn = client_on, bang_moi
    mon = conn.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, 'Môn gán lớp') RETURNING subject_id",
                       ("M" + uuid.uuid4().hex[:8].upper(),)).fetchone()["subject_id"]
    lopA, lopB = tao_lop(conn, 3), tao_lop(conn, 2)
    uA, idA = tao_user(conn)
    uB, idB = tao_user(conn)
    uAd, idAd = tao_user(conn, "admin")
    uSv, idSv = tao_user(conn, "student")
    gan(conn, idA, lopA["id"], mon)
    gan(conn, idB, lopB["id"])
    hA, hB, hAd, hSv = dn(c, uA), dn(c, uB), dn(c, uAd), dn(c, uSv)
    EA = ky_thi(c, hAd, class_code=lopA["ma"], teacher_user_id=idA)
    EB = ky_thi(c, hAd, class_id=lopB["id"], teacher_user_id=idB)
    E_cu = ky_thi(c, hAd, teacher_user_id=idA)
    SA = tai_trang(c, hA, EA).json()["sheet_id"]
    return SimpleNamespace(c=c, conn=conn, lopA=lopA, lopB=lopB, uA=uA, idA=idA, uB=uB, idB=idB, hA=hA, hB=hB, hAd=hAd, hSv=hSv, EA=EA, EB=EB, E_cu=E_cu,
                           SA=SA, mon=mon)


def khong_ton_tai(r) -> bool:
    return r.status_code == 404 and r.json()["detail"].startswith("Không có ")


def test_dang_nhap_dung_cookie_httponly(client_on, bang_moi):
    u, uid = tao_user(bang_moi)
    r = client_on.post("/auth/login", json={"username": u.upper(), "password": MK})
    assert r.status_code == 200 and r.json()["username"] == u and r.json()["role"] == "teacher" and "password" not in r.text
    ck = r.headers["set-cookie"].lower()
    assert "se_session=" in ck and "httponly" in ck and "samesite=lax" in ck and "path=/" in ck and "secure" not in ck
    me = client_on.get("/me").json()
    assert me["user_id"] == uid and me["last_login_at"] is not None and "password_hash" not in me


def test_cookie_secure_khi_bat_bien_moi_truong(client_on, bang_moi):
    from backend.main import app, get_cau_hinh
    app.dependency_overrides[get_cau_hinh] = lambda: replace(client_on.cfg, cookie_secure=True)
    u, _ = tao_user(bang_moi)
    r = client_on.post("/auth/login", json={"username": u, "password": MK})
    assert "secure" in r.headers["set-cookie"].lower()


def test_loi_dang_nhap_cung_mot_thong_bao(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    khoa, _ = tao_user(bang_moi, active=False)
    gia, _ = tao_user(bang_moi, bam=BAM_GIA_SEED)
    kq = [client_on.post("/auth/login", json=b) for b in (
        {"username": u, "password": "sai-mat-khau"}, {"username": "khong-co-" + u, "password": MK},
        {"username": khoa, "password": MK}, {"username": gia, "password": MK})]
    assert {r.status_code for r in kq} == {401}
    assert {r.json()["detail"] for r in kq} == {auth.THONG_BAO_SAI}
    assert client_on.get("/me").status_code == 401


def test_gioi_han_thu_sai_429(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    khac, _ = tao_user(bang_moi)
    for _ in range(5):
        assert client_on.post("/auth/login", json={"username": u, "password": "sai"}).status_code == 401
    r = client_on.post("/auth/login", json={"username": u, "password": MK})
    assert r.status_code == 429 and "quá nhiều" in r.json()["detail"]
    assert client_on.post("/auth/login", json={"username": khac, "password": MK}).status_code == 200
    xa, _ = tao_user(bang_moi)
    for _ in range(5):
        client_on.post("/auth/login", json={"username": "khong-co-" + xa, "password": "x"})
    assert client_on.post("/auth/login", json={"username": "khong-co-" + xa, "password": "x"}).status_code == 429


def test_dang_xuat_xoa_cookie(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    client_on.post("/auth/login", json={"username": u, "password": MK})
    r = client_on.post("/auth/logout")
    assert r.status_code == 204 and "se_session=" in r.headers["set-cookie"] and "max-age=0" in r.headers["set-cookie"].lower()
    assert client_on.get("/me").status_code == 401


ENDPOINT_MAU = [("GET", "/exams"), ("GET", "/exams/1"), ("GET", "/exams/1/sheets"), ("GET", "/exams/1/results"), ("GET", "/exams/1/export.xlsx"),
                ("GET", "/exams/1/review-questions"), ("GET", "/sheets/1"), ("GET", "/sheets/1/image"), ("GET", "/sheets/1/review-questions"),
                ("GET", "/sheets/1/questions/1/image"), ("GET", "/sheets/1/digits/sbd/0/image"), ("GET", "/me"), ("GET", "/me/classes"),
                ("GET", "/classes/1/students"), ("PATCH", "/me"), ("POST", "/me/password"), ("POST", "/exams"),
                ("POST", "/sheets/1/questions/1/review"), ("PUT", "/sheets/1/identity"), ("POST", "/exams/1/sheets"), ("POST", "/exams/1/sheets/batch")]


@pytest.mark.parametrize("phuong_thuc,duong_dan", ENDPOINT_MAU)
def test_khong_dang_nhap_401_va_x_user_bi_bo_qua(client_on, bang_moi, phuong_thuc, duong_dan):
    u, _ = tao_user(bang_moi, "admin")
    for h in ({}, {"X-User": u}, {"Authorization": "Bearer khong-phai-token"}):
        r = client_on.request(phuong_thuc, duong_dan, headers=h, json={} if phuong_thuc in ("POST", "PUT", "PATCH") else None)
        assert r.status_code == 401, (phuong_thuc, duong_dan, h, r.status_code, r.text[:120])


def test_token_het_han_gia_va_tai_khoan_bi_khoa(client_on, bang_moi):
    u, uid = tao_user(bang_moi)
    h = dn(client_on, u)
    assert client_on.get("/me", headers=h).status_code == 200
    bam = bang_moi.execute("SELECT password_hash FROM users WHERE user_id = %s", (uid,)).fetchone()["password_hash"]
    het_han = auth.tao_token(client_on.cfg.auth_secret, uid, bam, -1)
    gia = auth.tao_token("khoa-khac-" + "z" * 40, uid, bam, 8)
    sua = h["Authorization"][:-3] + ("AAA" if not h["Authorization"].endswith("AAA") else "BBB")
    for t in (f"Bearer {het_han}", f"Bearer {gia}", sua):
        assert client_on.get("/me", headers={"Authorization": t}).status_code == 401
    bang_moi.execute("UPDATE users SET is_active = FALSE WHERE user_id = %s", (uid,))
    assert client_on.get("/me", headers=h).status_code == 401


def test_cookie_va_bearer_deu_duoc_chap_nhan(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    h = dn(client_on, u)
    assert client_on.get("/me", headers=h).status_code == 200
    client_on.post("/auth/login", json={"username": u, "password": MK})
    assert client_on.get("/me").status_code == 200


def test_xem_va_sua_ho_so(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    h = dn(client_on, u)
    me = client_on.get("/me", headers=h).json()
    assert set(me) >= {"user_id", "username", "full_name", "email", "role", "last_login_at"} and me["email"] == f"{u}@test.local"
    r = client_on.patch("/me", headers=h, json={"full_name": "  Tên Mới  ", "email": f"{u}.moi@test.local"})
    assert r.status_code == 200 and r.json()["full_name"] == "Tên Mới" and r.json()["email"] == f"{u}.moi@test.local"
    assert client_on.patch("/me", headers=h, json={"email": "khong-phai-email"}).status_code == 422
    assert client_on.patch("/me", headers=h, json={"full_name": "   "}).status_code == 422
    assert client_on.patch("/me", headers=h, json={}).status_code == 422
    assert client_on.get("/me", headers=h).json()["full_name"] == "Tên Mới"
    assert client_on.patch("/me", headers=h, json={"role": "admin", "full_name": "Vẫn Là GV"}).json()["role"] == "teacher"


def test_doi_mat_khau(client_on, bang_moi):
    u, _ = tao_user(bang_moi)
    h = dn(client_on, u)
    assert client_on.post("/me/password", headers=h, json={"old_password": "sai-het", "new_password": "MatKhauMoi-456"}).status_code == 422
    assert client_on.post("/me/password", headers=h, json={"old_password": MK, "new_password": "ngan"}).status_code == 422
    assert client_on.post("/me/password", headers=h, json={"old_password": MK, "new_password": MK}).status_code == 422
    assert client_on.post("/me/password", headers=h, json={"old_password": MK, "new_password": "MatKhauMoi-456"}).status_code == 204
    assert client_on.get("/me", headers=h).status_code == 401
    assert client_on.post("/auth/login", json={"username": u, "password": MK}).status_code == 401
    assert client_on.post("/auth/login", json={"username": u, "password": "MatKhauMoi-456"}).status_code == 200


def test_tai_khoan_mau_dat_tai_khoan(bang_moi):
    from backend import tai_khoan
    u = "tk" + uuid.uuid4().hex[:8]
    assert tai_khoan.dat_tai_khoan(bang_moi, u, f"{u}@test.local", "Tên", "teacher", "Mk-ngau-nhien-1") == "tao"
    h = bang_moi.execute("SELECT password_hash FROM users WHERE username = %s", (u,)).fetchone()["password_hash"]
    assert auth.kiem_mat_khau("Mk-ngau-nhien-1", h) and "Mk-ngau" not in h
    assert tai_khoan.dat_tai_khoan(bang_moi, u, f"{u}@test.local", "Tên 2", "teacher", "Mk-moi-2") == "cap_nhat"
    h2 = bang_moi.execute("SELECT password_hash, full_name FROM users WHERE username = %s", (u,)).fetchone()
    assert auth.kiem_mat_khau("Mk-moi-2", h2["password_hash"]) and h2["full_name"] == "Tên 2"


def test_sinh_vien_khong_dung_duoc_api_cham(the_gioi):
    g = the_gioi
    for pt, dd in (("GET", "/exams"), ("GET", f"/exams/{g.EA}"), ("POST", "/exams"), ("GET", "/me/classes"), ("GET", f"/classes/{g.lopA['id']}/students"),
                   ("GET", f"/sheets/{g.SA}"), ("GET", f"/exams/{g.EA}/results"), ("GET", f"/exams/{g.EA}/export.xlsx")):
        r = g.c.request(pt, dd, headers=g.hSv, json={} if pt == "POST" else None)
        assert r.status_code == 403, (pt, dd, r.status_code)
    assert g.c.get("/me", headers=g.hSv).status_code == 200


def test_ds_ky_thi_theo_quyen_co_mon_lop(the_gioi):
    g = the_gioi
    ds = lambda h: {e["exam_id"]: e for e in g.c.get("/exams", headers=h).json()}                   # noqa: E731
    a, b, ad = ds(g.hA), ds(g.hB), ds(g.hAd)
    assert {g.EA, g.E_cu} <= set(a) and g.EB not in a
    assert g.EB in b and g.EA not in b and g.E_cu not in b
    assert {g.EA, g.EB, g.E_cu} <= set(ad)
    e = a[g.EA]
    assert e["class_code"] == g.lopA["ma"] and e["class_id"] == g.lopA["id"] and e["subject_code"] and e["subject_name"] == "Môn thử" and e["class_name"]
    assert a[g.E_cu]["class_id"] is None and a[g.E_cu]["class_code"] is None
    d = g.c.get(f"/exams/{g.EA}", headers=g.hA).json()
    assert d["class_code"] == g.lopA["ma"] and d["subject_name"] == "Môn thử"


def test_hai_giao_vien_cung_lop_thay_ky_thi_cua_lop(the_gioi):
    g = the_gioi
    u2, id2 = tao_user(g.conn)
    gan(g.conn, id2, g.lopA["id"])
    h2 = dn(g.c, u2)
    ids = {e["exam_id"] for e in g.c.get("/exams", headers=h2).json()}
    assert g.EA in ids and g.E_cu not in ids
    assert g.c.get(f"/sheets/{g.SA}", headers=h2).status_code == 200


def test_tao_ky_thi_voi_lop(the_gioi):
    g = the_gioi
    so_lop = g.conn.execute("SELECT count(*) AS n FROM classes").fetchone()["n"]
    body = {"exam_title": "Đề lớp", "subject_code": "TL" + uuid.uuid4().hex[:6].upper(), "num_questions": 10,
            "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}]}
    for them in ({"class_id": g.lopA["id"]}, {"class_id": g.lopB["id"]}, {"class_code": "KHONG-CO-LOP-NAY"}, {}):
        assert g.c.post("/exams", headers=g.hA, json={**body, **them}).status_code == 403, them
    ok = g.c.post("/exams", headers=g.hAd, json={**body, "class_id": g.lopA["id"], "class_code": g.lopA["ma"].lower()})
    assert ok.status_code == 201
    r = g.c.post("/exams", headers=g.hAd, json={**body, "class_code": "KHONG-CO-LOP-NAY"})
    assert r.status_code == 422 and r.json()["detail"] == MA_LOP_KHONG_DUNG
    assert g.c.post("/exams", headers=g.hAd, json={**body, "class_id": g.lopA["id"], "class_code": g.lopB["ma"]}).status_code == 422
    assert g.c.post("/exams", headers=g.hAd, json={**body, "class_id": g.lopB["id"]}).status_code == 201
    assert g.conn.execute("SELECT count(*) AS n FROM classes").fetchone()["n"] == so_lop


def test_idor_ky_thi_404_nhu_khong_ton_tai(the_gioi):
    g = the_gioi
    anh = ("x.jpg", anh_trang(), "image/jpeg")
    yeu_cau = [("GET", "/exams/{e}", {}), ("GET", "/exams/{e}/sheets", {}), ("GET", "/exams/{e}/review-questions", {}), ("GET", "/exams/{e}/results", {}),
               ("GET", "/exams/{e}/export.xlsx", {}), ("POST", "/exams/{e}/sheets", {"files": {"file": anh}}),
               ("POST", "/exams/{e}/sheets/batch", {"files": [("files", anh)]})]
    for pt, mau, kw in yeu_cau:
        ngoai = g.c.request(pt, mau.format(e=g.EA), headers=g.hB, **kw)
        khong_co = g.c.request(pt, mau.format(e=999999999), headers=g.hB, **kw)
        assert ngoai.status_code == 404 and khong_co.status_code == 404, (pt, mau, ngoai.status_code)
        assert ngoai.json()["detail"].replace(str(g.EA), "N") == khong_co.json()["detail"].replace("999999999", "N"), (pt, mau)
        chu = g.c.request(pt, mau.format(e=g.EA), headers=g.hA, **kw)
        assert chu.status_code in (200, 201), (pt, mau, chu.status_code, chu.text[:100])
        admin = g.c.request(pt, mau.format(e=g.EA), headers=g.hAd, **kw)
        assert admin.status_code in (200, 201), (pt, mau, admin.status_code)
    for pt, mau, kw in yeu_cau[:5]:
        assert g.c.request(pt, mau.format(e=g.EB), headers=g.hA, **kw).status_code == 404


def test_idor_phieu_404_nhu_khong_ton_tai(the_gioi):
    g = the_gioi
    s, kv = g.SA, 987654321
    yeu_cau = [("GET", "/sheets/{s}", {}), ("GET", "/sheets/{s}/image?kind=original", {}), ("GET", "/sheets/{s}/image", {}), ("GET", "/sheets/{s}/review-questions", {}),
               ("GET", "/sheets/{s}/questions/1/image", {}), ("GET", "/sheets/{s}/digits/sbd/0/image", {}),
               ("POST", "/sheets/{s}/questions/1/review", {"json": {"action": "confirm"}}), ("PUT", "/sheets/{s}/identity", {"json": {"sbd": "123456"}})]
    for pt, mau, kw in yeu_cau:
        ngoai = g.c.request(pt, mau.format(s=s), headers=g.hB, **kw)
        khong_co = g.c.request(pt, mau.format(s=kv), headers=g.hB, **kw)
        assert ngoai.status_code == 404 == khong_co.status_code, (pt, mau, ngoai.status_code)
        assert ngoai.json()["detail"].replace(str(s), "N") == khong_co.json()["detail"].replace(str(kv), "N") == "Không có phiếu N.", (pt, mau)
        for h in (g.hA, g.hAd):
            r = g.c.request(pt, mau.format(s=s), headers=h, **kw)
            assert not (r.status_code == 404 and r.json()["detail"] == f"Không có phiếu {s}."), (pt, mau, r.text[:100])


def test_idor_khong_sua_duoc_phieu_cua_nguoi_khac(the_gioi):
    g = the_gioi
    truoc = g.c.get(f"/sheets/{g.SA}", headers=g.hA).json()
    for pt, dd, js in (("POST", f"/sheets/{g.SA}/questions/1/review", {"action": "set", "selected_options": "A"}),
                       ("PUT", f"/sheets/{g.SA}/identity", {"sbd": "999999", "exam_code": "101"})):
        assert g.c.request(pt, dd, headers=g.hB, json=js).status_code == 404
    assert g.c.get(f"/sheets/{g.SA}", headers=g.hA).json() == truoc


def test_lop_cua_toi_va_sinh_vien_chi_lop_minh(the_gioi):
    g = the_gioi
    a = g.c.get("/me/classes", headers=g.hA).json()
    assert [c["class_code"] for c in a] == [g.lopA["ma"]] and a[0]["so_sinh_vien"] == 3 and a[0]["subject_name"] == "Môn gán lớp" and a[0]["subject_id"] == g.mon
    b = g.c.get("/me/classes", headers=g.hB).json()
    assert [c["class_code"] for c in b] == [g.lopB["ma"]] and b[0]["subject_id"] is None and b[0]["so_sinh_vien"] == 2
    ad = {c["class_code"] for c in g.c.get("/me/classes", headers=g.hAd).json()}
    assert {g.lopA["ma"], g.lopB["ma"]} <= ad
    r = g.c.get(f"/classes/{g.lopA['id']}/students", headers=g.hA).json()
    assert r["tong"] == 3 and r["lop"]["class_code"] == g.lopA["ma"] and len(r["sinh_vien"]) == 3
    assert set(r["sinh_vien"][0]) == {"student_id", "student_code", "full_name", "date_of_birth", "gender", "email"}
    ngoai = g.c.get(f"/classes/{g.lopA['id']}/students", headers=g.hB)
    khong_co = g.c.get("/classes/999999999/students", headers=g.hB)
    assert ngoai.status_code == khong_co.status_code == 404
    assert ngoai.json()["detail"].replace(str(g.lopA["id"]), "N") == khong_co.json()["detail"].replace("999999999", "N")
    assert g.c.get(f"/classes/{g.lopA['id']}/students", headers=g.hAd).json()["tong"] == 3
    assert g.c.get(f"/classes/{g.lopB['id']}/students", headers=g.hAd).json()["tong"] == 2


def test_tim_kiem_va_phan_trang_sinh_vien(the_gioi):
    g = the_gioi
    url = f"/classes/{g.lopA['id']}/students"
    tat_ca = g.c.get(url, headers=g.hA).json()["sinh_vien"]
    ma = tat_ca[1]["student_code"]
    assert [s["student_code"] for s in g.c.get(url, headers=g.hA, params={"q": ma}).json()["sinh_vien"]] == [ma]
    assert g.c.get(url, headers=g.hA, params={"q": "SỐ 2"}).json()["tong"] == 1 or g.c.get(url, headers=g.hA, params={"q": "số 2"}).json()["tong"] == 1
    assert g.c.get(url, headers=g.hA, params={"q": "%"}).json()["tong"] == 0
    assert g.c.get(url, headers=g.hA, params={"q": "_"}).json()["tong"] == 0
    p1 = g.c.get(url, headers=g.hA, params={"page": 1, "page_size": 2}).json()
    p2 = g.c.get(url, headers=g.hA, params={"page": 2, "page_size": 2}).json()
    assert len(p1["sinh_vien"]) == 2 and len(p2["sinh_vien"]) == 1 and p1["tong"] == p2["tong"] == 3
    assert {s["student_id"] for s in p1["sinh_vien"]}.isdisjoint({s["student_id"] for s in p2["sinh_vien"]})
    assert g.c.get(url, headers=g.hA, params={"page": 0}).status_code == 422


def test_bang_diem_va_excel_co_mon_lop(the_gioi):
    g = the_gioi
    b = g.c.get(f"/exams/{g.EA}/results", headers=g.hA).json()
    assert b["class_code"] == g.lopA["ma"] and b["subject_name"] == "Môn thử" and b["subject_code"] and b["class_name"]
    ws = load_workbook(io.BytesIO(g.c.get(f"/exams/{g.EA}/export.xlsx", headers=g.hA).content))["Bảng điểm"]
    assert "Môn thử" in ws["A4"].value and ws["A4"].value.startswith("Môn: ") and g.lopA["ma"] in ws["F4"].value and ws["F4"].value.startswith("Lớp: ")
    assert ws["A1"].value.startswith("BẢNG ĐIỂM") and ws["A5"].value == "STT" and ws["B5"].value == "SBD"
    ws2 = load_workbook(io.BytesIO(g.c.get(f"/exams/{g.E_cu}/export.xlsx", headers=g.hA).content))["Bảng điểm"]
    assert "không gắn lớp" in ws2["F4"].value
    assert g.c.get(f"/exams/{g.E_cu}/results", headers=g.hA).json()["class_code"] is None


def test_che_do_demo_giu_hanh_vi_cu(client):
    assert client.get("/exams").status_code == 200
    me = client.get("/me").json()
    assert me["username"]
    assert client.get("/exams", headers={"X-User": "khong-co-nguoi-nay"}).status_code == 404
    assert client.post("/auth/login", json={"username": "a", "password": "b"}).status_code == 422


def test_migration_002_chay_lai_an_toan(bang_moi):
    from backend import migrate
    sql = (migrate.THU_MUC / "002_lop_giao_vien.sql").read_text(encoding="utf-8")
    bang_moi.execute(sql)
    bang_moi.execute(sql)
    assert bang_moi.execute("SELECT to_regclass('teacher_classes') AS t").fetchone()["t"] is not None


def test_nap_giao_vien_demo_xem_truoc_khong_ghi(capsys, monkeypatch):
    import sys
    sys.path.insert(0, str(__import__("conftest").ROOT / "tools"))
    import nap_giao_vien_demo as N
    monkeypatch.setattr(sys, "argv", ["nap_giao_vien_demo.py"])
    assert N.main() == 0
    out = capsys.readouterr().out
    assert "XEM TRƯỚC" in out and "Chưa ghi gì" in out and "gv_an -> CNTT-K22A" in out and "gv_binh -> CNTT-K22B" in out
