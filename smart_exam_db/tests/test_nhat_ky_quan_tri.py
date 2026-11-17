"""Lệnh V4 – nhật ký thao tác quản trị (bảng admin_audit_log, migration 005; GET /admin/audit).
CSDL thật trong giao dịch ROLLBACK (conftest.conn_thu kiểm cả admin_audit_log không bị để lại), AUTH_MODE=on.
Kiểm: chỉ admin xem (giáo viên / sinh viên 403, chưa đăng nhập 401); MỖI loại thao tác thành công để lại ĐÚNG MỘT dòng (đủ mọi hành động của
nhat_ky.HANH_DONG); thao tác bị từ chối không để lại dòng nào; mật khẩu / mã băm không xuất hiện trong nhật ký; phân trang mới nhất trước."""
import json
import uuid

import pytest

from backend import auth, nhat_ky
from test_dang_nhap import bang_moi, client_on, dn, tao_user  # noqa: F401 – fixture dùng lại
from test_quan_tri_ky_thi import than

MK_MOI = "BiMat-V4-taoMoi-73915"
MK_DAT_LAI = "BiMat-V4-datLai-28461"


@pytest.fixture
def nk(client_on, bang_moi):
    c, conn = client_on, bang_moi
    if conn.execute("SELECT to_regclass('admin_audit_log') AS t").fetchone()["t"] is None:
        pytest.skip("SKIP: migration 005 chưa áp (python -m backend.migrate) – test nhật ký KHÔNG được tính là đạt")
    ad, id_ad = tao_user(conn, "admin")
    g, id_g = tao_user(conn)
    sv, _ = tao_user(conn, "student")
    return c, conn, {"ad": dn(c, ad), "gv": dn(c, g), "sv": dn(c, sv)}, id_ad, id_g


def _moc(conn) -> int:
    return conn.execute("SELECT coalesce(max(log_id), 0) AS m FROM admin_audit_log").fetchone()["m"]


def _sau(conn, moc) -> list[dict]:
    return conn.execute("SELECT * FROM admin_audit_log WHERE log_id > %s ORDER BY log_id", (moc,)).fetchall()


def _mot(conn, moc, hanh_dong, loai, doi_tuong, id_ad) -> dict:
    d = _sau(conn, moc)
    assert len(d) == 1, [x["action"] for x in d]
    assert (d[0]["action"], d[0]["object_type"], d[0]["object_id"], d[0]["actor_user_id"]) == (hanh_dong, loai, doi_tuong, id_ad), d[0]
    return d[0]


def test_chi_admin_xem_nhat_ky(nk):
    c, _, h, _, _ = nk
    assert c.get("/admin/audit", headers=h["ad"]).status_code == 200
    for vai in ("gv", "sv"):
        assert c.get("/admin/audit", headers=h[vai]).status_code == 403
    assert c.get("/admin/audit").status_code == 401
    assert c.get("/admin/audit?page_size=201", headers=h["ad"]).status_code == 422


def test_moi_thao_tac_dung_mot_dong(nk):
    c, conn, h, id_ad, id_g = nk
    ad = h["ad"]
    da = set()

    def lam(hanh_dong, loai, doi_tuong, goi, ma=200):
        m = _moc(conn)
        r = goi()
        assert r.status_code == ma, (hanh_dong, r.text)
        dong = _mot(conn, m, hanh_dong, loai, doi_tuong() if callable(doi_tuong) else doi_tuong, id_ad)
        da.add(hanh_dong)
        return r, dong

    # kỳ thi
    m = _moc(conn)
    r = c.post("/admin/exams", headers=ad, json=than(teacher_user_id=id_g))
    assert r.status_code == 201
    eid = r.json()["exam_id"]
    d = _mot(conn, m, "tao_ky_thi", "exam", eid, id_ad)
    assert d["details"]["teacher_username"] and d["details"]["ma_de"] == "101, 102"
    da.add("tao_ky_thi")
    _, d = lam("sua_ky_thi", "exam", eid, lambda: c.patch(f"/admin/exams/{eid}", headers=ad, json={"exam_title": "Đổi tên V4"}))
    assert d["details"]["thay"] == {"exam_title": {"cu": "Kỳ thi quản trị (pytest)", "moi": "Đổi tên V4"}}
    _, d = lam("dong_ky_thi", "exam", eid, lambda: c.post(f"/admin/exams/{eid}/status", headers=ad, json={"closed": True}))
    assert d["details"]["status"] == {"cu": "draft", "moi": "closed"}
    lam("mo_ky_thi", "exam", eid, lambda: c.post(f"/admin/exams/{eid}/status", headers=ad, json={"closed": False}))
    # tài khoản
    ten = "v4" + uuid.uuid4().hex[:8]
    m = _moc(conn)
    r = c.post("/admin/users", headers=ad, json={"username": ten, "full_name": "GV nhật ký", "password": MK_MOI})
    assert r.status_code == 201, r.text
    uid = r.json()["user_id"]
    assert _mot(conn, m, "tao_tai_khoan", "user", uid, id_ad)["details"]["username"] == ten
    da.add("tao_tai_khoan")
    lam("dat_lai_mat_khau", "user", uid, lambda: c.post(f"/admin/users/{uid}/password", headers=ad, json={"new_password": MK_DAT_LAI}), 204)
    lam("vo_hieu_hoa_tai_khoan", "user", uid, lambda: c.post(f"/admin/users/{uid}/active", headers=ad, json={"is_active": False}))
    lam("kich_hoat_tai_khoan", "user", uid, lambda: c.post(f"/admin/users/{uid}/active", headers=ad, json={"is_active": True}))
    _, d = lam("gan_ky_thi", "user", uid, lambda: c.put(f"/admin/users/{uid}/exams/{eid}", headers=ad))
    assert d["details"]["exam_id"] == eid and d["details"]["phu_trach_truoc"] != ten
    _, d = lam("bo_gan_ky_thi", "user", uid, lambda: c.delete(f"/admin/users/{uid}/exams/{eid}", headers=ad))
    assert d["details"]["exam_id"] == eid
    # lớp
    ma = "V4-" + uuid.uuid4().hex[:8].upper()
    m = _moc(conn)
    r = c.post("/admin/classes", headers=ad, json={"class_code": ma, "class_name": "Lớp nhật ký"})
    assert r.status_code == 201
    cid = r.json()["class_id"]
    _mot(conn, m, "tao_lop", "class", cid, id_ad)
    da.add("tao_lop")
    _, d = lam("sua_lop", "class", cid, lambda: c.patch(f"/admin/classes/{cid}", headers=ad, json={"academic_year": "2027-2028"}))
    assert d["details"]["thay"] == {"academic_year": {"cu": None, "moi": "2027-2028"}}
    _, d = lam("them_giao_vien_vao_lop", "class", cid, lambda: c.put(f"/admin/classes/{cid}/teachers/{uid}", headers=ad))
    assert d["details"]["user_id"] == uid and d["details"]["class_code"] == ma
    lam("bo_giao_vien_khoi_lop", "class", cid, lambda: c.delete(f"/admin/classes/{cid}/teachers/{uid}", headers=ad))
    _, d = lam("dat_lop_giao_vien", "user", uid, lambda: c.put(f"/admin/users/{uid}/classes", headers=ad, json={"class_ids": [cid]}))
    assert d["details"]["them"] == [ma] and d["details"]["bo"] == []
    m = _moc(conn)                                                                             # lưu mà không đổi gì: không ghi
    assert c.put(f"/admin/users/{uid}/classes", headers=ad, json={"class_ids": [cid]}).status_code == 200 and _sau(conn, m) == []
    lam("vo_hieu_hoa_lop", "class", cid, lambda: c.post(f"/admin/classes/{cid}/status", headers=ad, json={"is_active": False}))
    lam("kich_hoat_lop", "class", cid, lambda: c.post(f"/admin/classes/{cid}/status", headers=ad, json={"is_active": True}))
    _, d = lam("xoa_lop", "class", cid, lambda: c.delete(f"/admin/classes/{cid}", headers=ad), 204)
    assert d["details"]["class_code"] == ma
    _, d = lam("xoa_ky_thi", "exam", eid, lambda: c.delete(f"/admin/exams/{eid}", headers=ad), 204)
    assert d["details"]["exam_title"] == "Đổi tên V4"
    assert da == set(nhat_ky.HANH_DONG), set(nhat_ky.HANH_DONG) - da                  # phủ ĐỦ mọi loại thao tác
    # đọc lại qua API: mới nhất trước, tên người thao tác
    j = c.get("/admin/audit?page_size=3", headers=ad).json()
    assert [x["action"] for x in j["dong"]] == ["xoa_ky_thi", "xoa_lop", "kich_hoat_lop"] and j["dong"][0]["actor_username"]
    assert j["tong"] >= len(da) and j["trang"] == 1 and j["co_trang"] == 3
    j2 = c.get("/admin/audit?page_size=3&page=2", headers=ad).json()
    assert not {x["log_id"] for x in j["dong"]} & {x["log_id"] for x in j2["dong"]}
    assert j2["dong"][0]["log_id"] < j["dong"][-1]["log_id"]


def test_thao_tac_bi_tu_choi_khong_ghi(nk):
    c, conn, h, id_ad, id_g = nk
    ad = h["ad"]
    r = c.post("/admin/exams", headers=ad, json=than(teacher_user_id=id_g))
    eid = r.json()["exam_id"]
    sv = conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV V4') RETURNING student_id", (str(uuid.uuid4().int)[:12],)).fetchone()["student_id"]
    conn.execute("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s)", (eid, sv))
    m = _moc(conn)
    tu_choi = [
        (lambda: c.delete(f"/admin/exams/{eid}", headers=ad), 409),                                       # có danh sách dự thi
        (lambda: c.patch(f"/admin/exams/{eid}", headers=ad, json={"exam_title": "ab"}), 422),
        (lambda: c.post("/admin/exams/999999999999/status", headers=ad, json={"closed": True}), 404),
        (lambda: c.post("/admin/classes", headers=ad, json={"class_code": "CNTT-K22A", "class_name": "Trùng"}), 409),
        (lambda: c.post(f"/admin/users/{id_g}/password", headers=ad, json={"new_password": "ngan"}), 422),
        (lambda: c.post(f"/admin/users/{id_ad}/active", headers=ad, json={"is_active": False}), 404),   # không khoá admin qua web
        (lambda: c.put(f"/admin/users/{id_g}/exams/999999999999", headers=ad), 404),
        (lambda: c.put(f"/admin/users/{id_g}/classes", headers=ad, json={"class_ids": [999999999999]}), 422),
        (lambda: c.post(f"/admin/exams/{eid}/status", headers=h["gv"], json={"closed": True}), 403),     # giáo viên
        (lambda: c.post("/admin/classes", json={"class_code": "V4-KDN", "class_name": "x"}), 401),        # chưa đăng nhập
    ]
    for goi, ma in tu_choi:
        r = goi()
        assert r.status_code == ma, r.text
    assert _sau(conn, m) == []


def test_mat_khau_khong_vao_nhat_ky(nk):
    c, conn, h, _, _ = nk
    m = _moc(conn)
    r = c.post("/admin/users", headers=h["ad"], json={"username": "v4" + uuid.uuid4().hex[:8], "full_name": "GV mật khẩu", "password": MK_MOI})
    uid = r.json()["user_id"]
    assert c.post(f"/admin/users/{uid}/password", headers=h["ad"], json={"new_password": MK_DAT_LAI}).status_code == 204
    bam = conn.execute("SELECT password_hash FROM users WHERE user_id = %s", (uid,)).fetchone()["password_hash"]
    van_ban = json.dumps([d["details"] for d in _sau(conn, m)], ensure_ascii=False) + c.get("/admin/audit", headers=h["ad"]).text
    assert len(_sau(conn, m)) == 2
    for bi_mat in (MK_MOI, MK_DAT_LAI, bam, bam.split("$")[-1]):
        assert bi_mat not in van_ban
    assert "password" not in van_ban.lower() and "mat_khau\":" not in van_ban


def test_loc_khoa_nhay_cam_moi_tang(nk):
    _, conn, _, id_ad, _ = nk
    nd = auth.NguoiDung(user_id=id_ad, username="x", full_name="x", email="x@test.local", role="admin")
    m = _moc(conn)
    nhat_ky.ghi(conn, nd, "tao_lop", 1, {"class_code": "A", "password": "x", "con": {"token": "y", "ok": 1, "ds": [{"mat_khau": "z", "giu": 2}]},
                                         "password_hash": "h"})
    assert _sau(conn, m)[0]["details"] == {"class_code": "A", "con": {"ok": 1, "ds": [{"giu": 2}]}}
    with pytest.raises(KeyError):
        nhat_ky.ghi(conn, nd, "hanh_dong_la", 1, {})
