"""Lệnh I – admin quản lý lớp (/admin/classes) + gán giáo viên vào lớp (nhiều – nhiều) + lớp của kỳ thi.
CSDL thật trong giao dịch ROLLBACK (conftest.conn_thu kiểm cả classes / teacher_classes / users không bị để lại), AUTH_MODE=on. Cần migration 004."""
import uuid

import pytest

from backend import demo
from test_dang_nhap import bang_moi, client_on, dn, tai_trang, tao_user  # noqa: F401 – fixture dùng lại


def ma_lop() -> str:
    return "LT-" + uuid.uuid4().hex[:8].upper()


@pytest.fixture
def lp(client_on, bang_moi):
    c, conn = client_on, bang_moi
    if conn.execute("SELECT count(*) AS n FROM information_schema.columns WHERE table_name = 'classes' AND column_name = 'is_active'").fetchone()["n"] == 0:
        pytest.skip("SKIP: migration 004 chưa áp (python -m backend.migrate) – test lớp KHÔNG được tính là đạt")
    ad, id_ad = tao_user(conn, "admin")
    gA, idA = tao_user(conn)
    gB, idB = tao_user(conn)
    sv, _ = tao_user(conn, "student")
    h = {"ad": dn(c, ad), "A": dn(c, gA), "B": dn(c, gB), "sv": dn(c, sv)}
    r = c.post("/admin/classes", headers=h["ad"], json={"class_code": ma_lop(), "class_name": "Lớp thử lệnh I", "academic_year": "2026-2027"})
    assert r.status_code == 201, r.text
    return c, conn, h, idA, idB, r.json()


# ------------------------------------------------------------------------------------------------ Việc 1: lớp
def test_lop_chi_admin(lp):
    c, conn, h, idA, _, l = lp
    cid = l["class_id"]
    goi = [("get", "/admin/classes", None), ("post", "/admin/classes", {"class_code": ma_lop(), "class_name": "X"}),
           ("patch", f"/admin/classes/{cid}", {"class_name": "Y"}), ("post", f"/admin/classes/{cid}/status", {"is_active": False}),
           ("delete", f"/admin/classes/{cid}", None)]
    for vai in ("A", "B", "sv"):
        for m, url, body in goi:
            r = getattr(c, m)(url, headers=h[vai], **({"json": body} if body is not None else {}))
            assert r.status_code == 403, (vai, url, r.text)
    for m, url, body in goi:
        assert getattr(c, m)(url, **({"json": body} if body is not None else {})).status_code == 401
    assert c.get("/admin/classes", headers=h["ad"]).json() and conn.execute("SELECT is_active FROM classes WHERE class_id = %s", (cid,)).fetchone()["is_active"]


def test_tao_lop_va_trung_ma(lp):
    c, _, h, _, _, l = lp
    assert l["is_active"] and l["so_giao_vien"] == 0 and l["so_sinh_vien"] == 0 and l["so_ky_thi"] == 0 and l["academic_year"] == "2026-2027"
    r = c.post("/admin/classes", headers=h["ad"], json={"class_code": l["class_code"].lower(), "class_name": "Trùng"})
    assert r.status_code == 409 and "đã có" in r.json()["detail"]                              # không phân biệt hoa thường
    r = c.post("/admin/classes", headers=h["ad"], json={"class_code": "CNTT-K22A", "class_name": "Trùng lớp thật"})
    assert r.status_code == 409
    for body, mau in (({"class_code": "a b", "class_name": "X"}, "Mã lớp"), ({"class_code": "X", "class_name": "X"}, "Mã lớp"),
                      ({"class_code": ma_lop(), "class_name": "  "}, "Tên lớp"), ({"class_code": ma_lop(), "class_name": "X", "academic_year": "x" * 21}, "Năm học")):
        r = c.post("/admin/classes", headers=h["ad"], json=body)
        assert r.status_code == 422 and mau in r.json()["detail"], body


def test_sua_lop(lp):
    c, _, h, _, _, l = lp
    cid = l["class_id"]
    r = c.patch(f"/admin/classes/{cid}", headers=h["ad"], json={"class_name": " Lớp đổi tên "})
    assert r.status_code == 200 and r.json()["class_name"] == "Lớp đổi tên" and r.json()["academic_year"] == "2026-2027"
    assert c.patch(f"/admin/classes/{cid}", headers=h["ad"], json={"academic_year": None}).json()["academic_year"] is None
    assert c.patch(f"/admin/classes/{cid}", headers=h["ad"], json={"class_name": ""}).status_code == 422
    assert c.patch(f"/admin/classes/{cid}", headers=h["ad"], json={}).status_code == 422
    assert c.patch(f"/admin/classes/{cid}", headers=h["ad"], json={"class_code": "DOI-MA"}).status_code == 422       # mã lớp không sửa được (trường lạ bị bỏ qua)
    assert {x["class_id"]: x for x in c.get("/admin/classes", headers=h["ad"]).json()}[cid]["class_code"] == l["class_code"]
    assert c.patch("/admin/classes/999999999999", headers=h["ad"], json={"class_name": "X"}).status_code == 404


def test_vo_hieu_hoa_va_kich_hoat_lop(lp):
    c, _, h, _, _, l = lp
    cid = l["class_id"]
    assert c.post(f"/admin/classes/{cid}/status", headers=h["ad"], json={"is_active": False}).json()["is_active"] is False
    assert c.post(f"/admin/classes/{cid}/status", headers=h["ad"], json={"is_active": True}).json()["is_active"] is True


def test_xoa_lop(lp):
    c, conn, h, idA, _, l = lp
    co_sv = c.post("/admin/classes", headers=h["ad"], json={"class_code": ma_lop(), "class_name": "Có SV"}).json()["class_id"]
    conn.execute("INSERT INTO students (student_code, full_name, class_id) VALUES (%s, 'SV lớp', %s)", (str(uuid.uuid4().int)[:12], co_sv))
    r = c.delete(f"/admin/classes/{co_sv}", headers=h["ad"])
    assert r.status_code == 409 and "VÔ HIỆU HOÁ" in r.json()["detail"]
    co_kt = c.post("/admin/classes", headers=h["ad"], json={"class_code": ma_lop(), "class_name": "Có kỳ thi"}).json()["class_id"]
    e = c.post("/admin/exams", headers=h["ad"], json={"exam_title": "Kỳ thi gắn lớp", "subject_code": "XL" + uuid.uuid4().hex[:6].upper(), "num_questions": 10,
                                                      "class_id": co_kt, "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}]})
    assert e.status_code == 201
    assert c.delete(f"/admin/classes/{co_kt}", headers=h["ad"]).status_code == 409
    assert conn.execute("SELECT class_id FROM exams WHERE exam_id = %s", (e.json()["exam_id"],)).fetchone()["class_id"] == co_kt   # kỳ thi giữ lớp
    rong = l["class_id"]
    assert c.delete(f"/admin/classes/{rong}", headers=h["ad"]).status_code == 204
    assert c.delete(f"/admin/classes/{rong}", headers=h["ad"]).status_code == 404
