"""Lệnh G3: câu lý do của phiếu cần xem CHƯA ghép được thí sinh ở Bảng điểm. Chỉ đổi câu chữ – không đổi trạng thái / chấm. CSDL thật, giao dịch ROLLBACK."""
import json
import uuid

import pytest

from backend import bang_diem
from backend.bang_diem import ly_do_chua_ghep


@pytest.fixture
def ky_thi(conn_thu):
    """Kỳ thi CÓ danh sách dự thi: sv_trong (220001-giống) có trong danh sách, sv_ngoai có trong hệ thống nhưng KHÔNG dự kỳ thi này."""
    c = conn_thu
    uid = c.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()["user_id"]
    mon = c.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, 'Môn G3') RETURNING subject_id", ("G" + uuid.uuid4().hex[:8].upper(),)).fetchone()["subject_id"]
    mau = c.execute("SELECT template_id FROM sheet_templates ORDER BY template_id LIMIT 1").fetchone()["template_id"]
    eid = c.execute("INSERT INTO exams (subject_id, template_id, exam_title, num_questions, max_score, created_by) VALUES (%s, %s, 'Kỳ thi G3', 10, 10, %s) RETURNING exam_id",
                    (mon, mau, uid)).fetchone()["exam_id"]
    ma = lambda: str(uuid.uuid4().int)[:6]                                                    # noqa: E731
    trong, ngoai = ma(), ma()
    sv = lambda code: c.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV G3') RETURNING student_id", (code,)).fetchone()["student_id"]   # noqa: E731
    c.execute("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s)", (eid, sv(trong)))
    sv(ngoai)
    return {"conn": c, "eid": eid, "trong": trong, "ngoai": ngoai}


def phieu(k, sbd, can_xem, status="needs_review"):
    return k["conn"].execute(
        "INSERT INTO answer_sheets (exam_id, image_path, status, detected_sbd, original_filename, omr_detail) VALUES (%s, 'x.jpg', %s::sheet_status, %s, 'att.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.jpeg', %s) RETURNING sheet_id",
        (k["eid"], status, sbd, json.dumps({"sbd": {"can_xem": can_xem}, "ma_de": {"can_xem": False}}))).fetchone()["sheet_id"]


def test_cau_chu_hai_truong_hop(ky_thi):
    c, e = ky_thi["conn"], ky_thi["eid"]
    # (b) SBD CÓ trong danh sách nhưng máy đọc chưa chắc -> câu mới (KHÔNG nói "chưa khớp danh sách")
    assert ly_do_chua_ghep(c, e, ky_thi["trong"], True) == f"SBD đọc được {ky_thi['trong']} nhưng chưa chắc, cần giáo viên chốt"
    # (a) SBD đọc chắc nhưng KHÔNG có trong danh sách dự thi -> giữ câu cũ
    assert ly_do_chua_ghep(c, e, ky_thi["ngoai"], False) == f"SBD đọc: {ky_thi['ngoai']} – chưa khớp danh sách"
    assert ly_do_chua_ghep(c, e, "999999", False) == "SBD đọc: 999999 – chưa khớp danh sách"
    # thiếu chữ số ('?') -> chưa đọc đủ
    assert ly_do_chua_ghep(c, e, "06238?", True) == "SBD chưa đọc đủ (06238?), cần giáo viên chốt"
    assert ly_do_chua_ghep(c, e, "06238?", False) == "SBD chưa đọc đủ (06238?), cần giáo viên chốt"
    assert ly_do_chua_ghep(c, e, None, True) == "SBD chưa đọc đủ (–), cần giáo viên chốt"


def test_bang_diem_tra_dung_cau_va_khong_doi_trang_thai(ky_thi):
    c, e = ky_thi["conn"], ky_thi["eid"]
    b_chua_chac = phieu(ky_thi, ky_thi["trong"], True)            # kiểu #5505 / #4275: SBD có trong danh sách, máy chưa chắc
    a_ngoai_ds = phieu(ky_thi, ky_thi["ngoai"], False)
    bi_tu_choi = c.execute("INSERT INTO answer_sheets (exam_id, image_path, status, error_message, reject_code) VALUES (%s, 'x.jpg', 'rejected', 'Ảnh mờ', 'anh_mo') RETURNING sheet_id", (e,)).fetchone()["sheet_id"]
    truoc = {r["sheet_id"]: r["status"] for r in c.execute("SELECT sheet_id, status::text AS status FROM answer_sheets WHERE exam_id = %s", (e,)).fetchall()}
    kq = {p["sheet_id"]: p for p in bang_diem.bang_diem(c, e)["unmatched"]}
    assert kq[b_chua_chac]["reject_message"] == f"SBD đọc được {ky_thi['trong']} nhưng chưa chắc, cần giáo viên chốt"
    assert kq[a_ngoai_ds]["reject_message"] == f"SBD đọc: {ky_thi['ngoai']} – chưa khớp danh sách"
    assert kq[bi_tu_choi]["reject_message"] == "Ảnh mờ"                                  # phiếu bị từ chối: giữ nguyên thông báo
    assert "sbd_can_xem" not in kq[b_chua_chac] and "exam_id" not in kq[b_chua_chac]
    sau = {r["sheet_id"]: r["status"] for r in c.execute("SELECT sheet_id, status::text AS status FROM answer_sheets WHERE exam_id = %s", (e,)).fetchall()}
    assert sau == truoc                                                                  # không đổi trạng thái phiếu
    assert c.execute("SELECT count(*) AS n FROM results WHERE exam_id = %s", (e,)).fetchone()["n"] == 0


def test_api_va_giao_dien_dung_cau_moi(client, ky_thi):
    from conftest import ROOT
    phieu(ky_thi, ky_thi["trong"], True)
    u = client.get(f"/exams/{ky_thi['eid']}/results").json()["unmatched"]
    assert u and "chưa chắc, cần giáo viên chốt" in u[0]["reject_message"]
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "chưa khớp danh sách" not in js                                               # câu cứng sai đã bỏ khỏi giao diện; câu do máy chủ quyết định
