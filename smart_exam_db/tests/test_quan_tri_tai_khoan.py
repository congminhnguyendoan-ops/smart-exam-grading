"""Lệnh H – Việc 2: admin quản lý tài khoản giáo viên (/admin/users). CSDL thật trong giao dịch ROLLBACK, AUTH_MODE=on.
Kiểm: chỉ admin; tạo tài khoản (scrypt, không lộ mật khẩu ở phản hồi / lỗi 422 / log); đặt lại mật khẩu (phiên cũ hết hiệu lực); vô hiệu hoá
(không đăng nhập được, phiên đang có bị từ chối ở lần gọi kế); giới hạn 5 lần sai / 15 phút; gán / bỏ gán kỳ thi; tài khoản không phải giáo viên -> 404."""
import logging
import uuid

import pytest

from backend import auth, demo
from test_dang_nhap import MK, bang_moi, client_on, dn, tao_user  # noqa: F401 – fixture dùng lại

MK_MOI = "Mk-Ban-Dau-" + uuid.uuid4().hex[:8]          # chuỗi đủ đặc trưng để dò trong phản hồi / log


@pytest.fixture
def tk(client_on, bang_moi):
    c, conn = client_on, bang_moi
    ad, id_ad = tao_user(conn, "admin")
    gv, id_gv = tao_user(conn)
    sv, _ = tao_user(conn, "student")
    return c, conn, {"ad": dn(c, ad), "gv": dn(c, gv), "sv": dn(c, sv)}, id_ad, id_gv


def tao_gv(c, h, **them):
    u = "gv" + uuid.uuid4().hex[:8]
    return c.post("/admin/users", headers=h, json={"username": u, "full_name": "Giáo viên thử", "password": MK_MOI, **them}), u


def khong_lo(text: str, *mk: str) -> bool:
    return all(m not in text for m in mk) and "scrypt$" not in text and "password_hash" not in text


def test_chi_admin(tk):
    c, conn, h, _, id_gv = tk
    n = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
    goi = [("get", "/admin/users", None), ("post", "/admin/users", {"username": "khongduoc", "full_name": "X", "password": MK_MOI}),
           ("post", f"/admin/users/{id_gv}/password", {"new_password": MK_MOI}), ("post", f"/admin/users/{id_gv}/active", {"is_active": False}),
           ("get", f"/admin/users/{id_gv}/exams", None), ("put", f"/admin/users/{id_gv}/exams/1", None), ("delete", f"/admin/users/{id_gv}/exams/1", None)]
    for vai in ("gv", "sv"):
        for m, url, body in goi:
            r = getattr(c, m)(url, headers=h[vai], **({"json": body} if body is not None else {}))
            assert r.status_code == 403, (vai, url, r.text)
    for m, url, body in goi:
        assert getattr(c, m)(url, **({"json": body} if body is not None else {})).status_code == 401
    assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == n                  # giáo viên không tự tạo được tài khoản
    assert c.get("/me", headers=h["gv"]).status_code == 200                                     # tài khoản giáo viên không bị khoá


def test_tao_tai_khoan_scrypt_khong_lo_mat_khau(tk, caplog):
    c, conn, h, _, _ = tk
    caplog.set_level(logging.DEBUG)
    r, u = tao_gv(c, h["ad"], email=None)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["username"] == u and d["role"] == "teacher" and d["is_active"] and d["email"] == f"{u}@smartexam.local" and d["so_ky_thi"] == 0
    assert khong_lo(r.text, MK_MOI)
    bam = conn.execute("SELECT password_hash FROM users WHERE user_id = %s", (d["user_id"],)).fetchone()["password_hash"]
    assert bam.startswith("scrypt$") and MK_MOI not in bam and auth.kiem_mat_khau(MK_MOI, bam)
    assert khong_lo(c.get("/admin/users", headers=h["ad"]).text, MK_MOI)
    assert c.post("/auth/login", json={"username": u, "password": MK_MOI}).status_code == 200    # giáo viên đăng nhập được
    assert MK_MOI not in caplog.text and "scrypt$" not in caplog.text


def test_tao_tai_khoan_loi_va_trung(tk):
    c, _, h, _, _ = tk
    r, u = tao_gv(c, h["ad"])
    assert r.status_code == 201
    r2 = c.post("/admin/users", headers=h["ad"], json={"username": u.upper(), "full_name": "Trùng", "password": MK_MOI})
    assert r2.status_code == 409 and "Tên đăng nhập" in r2.json()["detail"]                    # không phân biệt hoa thường
    r3, _ = tao_gv(c, h["ad"], email=r.json()["email"])
    assert r3.status_code == 409 and "Email" in r3.json()["detail"]
    for them, mau in (({"username": "a b"}, "Tên đăng nhập"), ({"username": "ab"}, "Tên đăng nhập"), ({"full_name": "  "}, "Họ tên"),
                      ({"email": "khong-phai-email"}, "Email")):
        r4, _ = tao_gv(c, h["ad"], **them)
        assert r4.status_code == 422 and mau in r4.json()["detail"] and khong_lo(r4.text, MK_MOI), them


def test_loi_422_khong_chep_lai_mat_khau(tk):
    c, _, h, _, id_gv = tk
    ngan = "ngan" + uuid.uuid4().hex[:3]                                                      # 7 ký tự: dịch vụ từ chối
    r = c.post("/admin/users", headers=h["ad"], json={"username": "gv" + uuid.uuid4().hex[:8], "full_name": "X", "password": ngan})
    assert r.status_code == 422 and "ít nhất 8" in r.json()["detail"] and ngan not in r.text
    r = c.post("/admin/users", headers=h["ad"], json={"password": MK_MOI})                      # thiếu trường: pydantic 422, KHÔNG chép body
    assert r.status_code == 422 and khong_lo(r.text, MK_MOI)
    r = c.post(f"/admin/users/{id_gv}/password", headers=h["ad"], json={"new_password": ngan})
    assert r.status_code == 422 and ngan not in r.text
    r = c.post(f"/admin/users/{id_gv}/password", headers=h["ad"], json={"new_password": 12345678, "x": MK_MOI})
    assert r.status_code == 422 and khong_lo(r.text, MK_MOI, "12345678")
    r = c.post("/auth/login", json={"password": MK_MOI})                                        # cũng áp cho đăng nhập
    assert r.status_code == 422 and MK_MOI not in r.text
    assert "input" in c.post("/admin/exams", headers=h["ad"], json={"exam_title": "x"}).json()["detail"][0]   # đường dẫn khác: định dạng 422 mặc định


def test_dat_lai_mat_khau_phien_cu_het_hieu_luc(tk, caplog):
    c, conn, h, _, id_gv = tk
    caplog.set_level(logging.DEBUG)
    u = conn.execute("SELECT username FROM users WHERE user_id = %s", (id_gv,)).fetchone()["username"]
    assert c.get("/me", headers=h["gv"]).status_code == 200
    r = c.post(f"/admin/users/{id_gv}/password", headers=h["ad"], json={"new_password": MK_MOI})
    assert r.status_code == 204 and r.content == b""
    assert c.get("/me", headers=h["gv"]).status_code == 401                                   # phiên cũ bị từ chối ở lần gọi kế
    assert c.post("/auth/login", json={"username": u, "password": MK}).status_code == 401      # mật khẩu cũ hết dùng
    assert c.post("/auth/login", json={"username": u, "password": MK_MOI}).status_code == 200
    assert MK_MOI not in caplog.text


def test_vo_hieu_hoa_va_kich_hoat_lai(tk):
    c, conn, h, _, id_gv = tk
    u = conn.execute("SELECT username FROM users WHERE user_id = %s", (id_gv,)).fetchone()["username"]
    r = c.post(f"/admin/users/{id_gv}/active", headers=h["ad"], json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    me = c.get("/me", headers=h["gv"])
    assert me.status_code == 401                                                                # phiên đang có bị từ chối NGAY lần gọi kế tiếp
    assert c.get("/exams", headers=h["gv"]).status_code == 401
    r = c.post("/auth/login", json={"username": u, "password": MK})
    assert r.status_code == 401 and r.json()["detail"] == auth.THONG_BAO_SAI                     # cùng thông báo như sai mật khẩu
    assert c.post(f"/admin/users/{id_gv}/active", headers=h["ad"], json={"is_active": True}).json()["is_active"] is True
    assert c.post("/auth/login", json={"username": u, "password": MK}).status_code == 200


def test_gioi_han_5_lan_sai_van_giu(tk):
    c, _, h, _, _ = tk
    r, u = tao_gv(c, h["ad"])
    assert r.status_code == 201
    for _ in range(auth.SO_LAN_SAI_TOI_DA):
        assert c.post("/auth/login", json={"username": u, "password": "sai-mat-khau-1"}).status_code == 401
    assert c.post("/auth/login", json={"username": u, "password": MK_MOI}).status_code == 429   # đúng mật khẩu vẫn bị chặn trong 15 phút


def test_chi_quan_ly_tai_khoan_giao_vien(tk):
    c, conn, h, id_ad, _ = tk
    _, id_ad2 = tao_user(conn, "admin")
    _, id_sv = tao_user(conn, "student")
    for uid in (id_ad, id_ad2, id_sv, 10 ** 12):
        for m, url, body in (("post", f"/admin/users/{uid}/password", {"new_password": MK_MOI}), ("post", f"/admin/users/{uid}/active", {"is_active": False}),
                             ("get", f"/admin/users/{uid}/exams", None)):
            r = getattr(c, m)(url, headers=h["ad"], **({"json": body} if body is not None else {}))
            assert r.status_code == 404 and r.json()["detail"] == f"Không có tài khoản giáo viên {uid}.", (uid, url)
    assert c.get("/me", headers=h["ad"]).status_code == 200                                     # admin không tự khoá mình


def test_gan_bo_gan_ky_thi(tk):
    c, conn, h, id_ad, id_gv = tk
    gB, id_B = tao_user(conn)
    hB = dn(c, gB)
    e = c.post("/admin/exams", headers=h["ad"], json={"exam_title": "Kỳ thi gán (pytest)", "subject_code": "GN" + uuid.uuid4().hex[:6].upper(),
                                                      "num_questions": 10, "teacher_user_id": id_gv,
                                                      "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}]}).json()["exam_id"]
    assert [x["nguon"] for x in c.get(f"/admin/users/{id_gv}/exams", headers=h["ad"]).json() if x["exam_id"] == e] == ["phu_trach"]
    assert c.get(f"/exams/{e}", headers=hB).status_code == 404
    r = c.put(f"/admin/users/{id_B}/exams/{e}", headers=h["ad"])                                  # gán cho B: B thành người phụ trách, A thôi
    assert r.status_code == 200 and e in {x["exam_id"] for x in r.json()}
    assert c.get(f"/exams/{e}", headers=hB).status_code == 200
    assert c.get(f"/exams/{e}", headers=h["gv"]).status_code == 404                               # A không dạy lớp nào của kỳ thi -> mất quyền
    assert c.delete(f"/admin/users/{id_gv}/exams/{e}", headers=h["ad"]).status_code == 404         # A không còn phụ trách: không bỏ gán được
    r = c.delete(f"/admin/users/{id_B}/exams/{e}", headers=h["ad"])
    assert r.status_code == 200 and e not in {x["exam_id"] for x in r.json()}
    assert c.get(f"/exams/{e}", headers=hB).status_code == 404
    assert conn.execute("SELECT created_by FROM exams WHERE exam_id = %s", (e,)).fetchone()["created_by"] == id_ad   # về admin đang thao tác
    assert c.put(f"/admin/users/{id_B}/exams/999999999999", headers=h["ad"]).status_code == 404
    c.post(f"/admin/users/{id_B}/active", headers=h["ad"], json={"is_active": False})
    r = c.put(f"/admin/users/{id_B}/exams/{e}", headers=h["ad"])
    assert r.status_code == 422 and "vô hiệu hoá" in r.json()["detail"]


def test_quan_tri_js_co_chuc_nang_tai_khoan():
    from conftest import ROOT
    js = (ROOT / "frontend" / "quan_tri.js").read_text(encoding="utf-8")
    for url in ("/admin/users", "/password", "/active", "/exams/${"):
        assert url in js, url
    assert "localStorage" not in js and "sessionStorage" not in js                              # không lưu mật khẩu ở trình duyệt
