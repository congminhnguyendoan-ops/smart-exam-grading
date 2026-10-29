"""Lệnh I – Việc 3: lớp của kỳ thi + quy tắc quyền KẾT HỢP (HỢP, không phải giao):
giáo viên thấy kỳ thi  ⇔  là người phụ trách (exams.created_by)  HOẶC  thuộc lớp của kỳ thi (teacher_classes). Không thuộc cả hai -> 404.
Trang bìa và danh sách /exams (nguồn của /m?kythi) theo cùng quy tắc. CSDL thật trong giao dịch ROLLBACK, AUTH_MODE=on."""
import uuid

import pytest

from backend import demo
from test_dang_nhap import bang_moi, client_on, dn, tao_user  # noqa: F401 – fixture dùng lại
from test_quan_tri_lop import lp, ma_lop  # noqa: F401 – fixture dùng lại


def tao_ky_thi(c, h, **them) -> int:
    r = c.post("/admin/exams", headers=h, json={"exam_title": "Kỳ thi quy tắc quyền", "subject_code": "QQ" + uuid.uuid4().hex[:6].upper(),
                                                "num_questions": 10, "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}], **them})
    assert r.status_code == 201, r.text
    return r.json()["exam_id"]


@pytest.fixture
def bon(lp):
    """4 giáo viên với một kỳ thi E (lớp L, phụ trách P): P phụ trách nhưng KHÔNG thuộc L; T thuộc L nhưng không phụ trách;
    PT vừa phụ trách vừa thuộc L (dùng cho kỳ thi thứ hai); N không thuộc cả hai."""
    c, conn, h, _, _, l = lp
    L = l["class_id"]
    ten = {}
    for k in ("P", "T", "N"):
        u, uid = tao_user(conn)
        ten[k] = (dn(c, u), uid)
    c.put(f"/admin/classes/{L}/teachers/{ten['T'][1]}", headers=h["ad"])
    E = tao_ky_thi(c, h["ad"], class_id=L, teacher_user_id=ten["P"][1])
    return c, conn, h, L, E, ten


def thay(c, hd, eid) -> bool:
    r = c.get(f"/exams/{eid}", headers=hd)
    assert r.status_code in (200, 404), r.text
    return r.status_code == 200


def test_quy_tac_hop_phu_trach_hoac_lop(bon):
    c, _, _, _, E, t = bon
    assert thay(c, t["P"][0], E)                     # chỉ phụ trách
    assert thay(c, t["T"][0], E)                     # chỉ thuộc lớp
    r = c.get(f"/exams/{E}", headers=t["N"][0])      # không thuộc cả hai
    assert r.status_code == 404 and r.json()["detail"] == f"Không có kỳ thi {E}."
    for k, mong in (("P", True), ("T", True), ("N", False)):
        assert (E in {x["exam_id"] for x in c.get("/exams", headers=t[k][0]).json()}) is mong, k     # /exams = danh sách /m?kythi dùng
        assert (c.get(f"/exams/{E}/cover.pdf", headers=t[k][0]).status_code == 200) is mong, k       # trang bìa cùng quy tắc


def test_doi_lop_cua_ky_thi(bon, lp):
    c, _, h, L, E, t = bon
    L2 = c.post("/admin/classes", headers=h["ad"], json={"class_code": ma_lop(), "class_name": "Lớp mới của kỳ thi"}).json()["class_id"]
    c.put(f"/admin/classes/{L2}/teachers/{t['N'][1]}", headers=h["ad"])
    r = c.patch(f"/admin/exams/{E}", headers=h["ad"], json={"class_id": L2})
    assert r.status_code == 200 and r.json()["class_id"] == L2
    assert thay(c, t["N"][0], E) and not thay(c, t["T"][0], E) and thay(c, t["P"][0], E)       # lớp mới thấy, lớp cũ thôi, phụ trách giữ
    r = c.patch(f"/admin/exams/{E}", headers=h["ad"], json={"class_id": None})
    assert r.json()["class_id"] is None
    assert not thay(c, t["N"][0], E) and thay(c, t["P"][0], E)                                    # bỏ lớp: chỉ còn người phụ trách


def test_bo_phu_trach_van_thay_qua_lop(bon):
    c, _, h, L, E, t = bon
    c.put(f"/admin/classes/{L}/teachers/{t['P'][1]}", headers=h["ad"])                             # P thuộc lớp nữa
    assert c.delete(f"/admin/users/{t['P'][1]}/exams/{E}", headers=h["ad"]).status_code == 200      # bỏ phụ trách
    assert thay(c, t["P"][0], E)                                                                   # vẫn thấy QUA LỚP (hợp)
    c.delete(f"/admin/classes/{L}/teachers/{t['P'][1]}", headers=h["ad"])
    assert not thay(c, t["P"][0], E)                                                               # không còn đường nào -> 404


def test_lop_vo_hieu_va_lop_khong_co(bon):
    c, _, h, L, E, t = bon
    c.post(f"/admin/classes/{L}/status", headers=h["ad"], json={"is_active": False})
    r = c.post("/admin/exams", headers=h["ad"], json={"exam_title": "Kỳ thi lớp vô hiệu", "subject_code": "QV" + uuid.uuid4().hex[:6].upper(),
                                                      "num_questions": 10, "class_id": L, "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}]})
    assert r.status_code == 422 and "vô hiệu hoá" in r.json()["detail"]
    assert thay(c, t["T"][0], E)                                                                   # giáo viên đã gán vẫn xem kỳ thi cũ của lớp
    assert c.patch(f"/admin/exams/{E}", headers=h["ad"], json={"exam_title": "Đổi tên giữ lớp", "class_id": L}).status_code == 200   # giữ lớp hiện tại: được
    E2 = tao_ky_thi(c, h["ad"])
    assert c.patch(f"/admin/exams/{E2}", headers=h["ad"], json={"class_id": L}).status_code == 422                     # gắn MỚI vào lớp vô hiệu: không
    assert c.patch(f"/admin/exams/{E2}", headers=h["ad"], json={"class_id": 999999999999}).status_code == 404


def test_form_ky_thi_dung_danh_sach_chon_lop():
    from conftest import ROOT
    js = (ROOT / "frontend" / "quan_tri.js").read_text(encoding="utf-8")
    assert '<select id="qt-lop">' in js and '<select id="qs-lop">' in js and "chonLopHtml" in js and "class_code: lop" not in js
