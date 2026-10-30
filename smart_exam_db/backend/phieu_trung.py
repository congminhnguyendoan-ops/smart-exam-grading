"""
phieu_trung.py - Phiếu TRÙNG SBD trong cùng kỳ thi (lệnh F2, 28/10/2026). Không đổi logic chấm (service.danh_gia_phieu giữ nguyên):
phiếu thứ hai của một thí sinh đã có điểm chính thức bị giữ ở `needs_review` với lý do `duplicate_sbd`. Module này thêm:

  * dem_cho(): số phiếu trùng đang chờ duyệt theo thí sinh (cho Bảng điểm / Excel cảnh báo).
  * bo_phieu_chup_lai(): "Bỏ phiếu chụp lại (giữ phiếu cũ)" – phiếu mới bị loại, phiếu cũ không đổi.
  * thay_phieu_cu(): "Dùng phiếu này thay phiếu cũ" – MỘT giao dịch: rút điểm chính thức của phiếu cũ (results -> 'void', trigger ghi
    score_audit_logs: ai / lúc nào / lý do "phiếu A bị thay bằng phiếu B"), phiếu cũ không còn tính, phiếu mới được đánh giá lại bằng
    ĐÚNG đường quyết định cũ (service.danh_gia_phieu) để duyệt tiếp / chốt.

Bất biến: không bao giờ có hai điểm chính thức cho một thí sinh (chỉ mục duy nhất uq_results_exam_student giữ nguyên; thua cuộc đua -> 409).
"""
from . import service
from .service import DuLieuSai, KhongTimThay, XungDot

MA_BI_THAY = "bi_thay_the"          # answer_sheets.reject_code của phiếu cũ bị thay
MA_BI_BO = "chup_lai_bi_bo"         # answer_sheets.reject_code của phiếu chụp lại bị bỏ


def dem_cho(conn, exam_id: int) -> dict[int, list[int]]:
    """{student_id: [sheet_id phiếu trùng đang chờ duyệt]} của một kỳ thi (phiếu needs_review có mục hàng đợi còn mở với lý do duplicate_sbd)."""
    rows = conn.execute(
        "SELECT a.matched_student_id AS sid, a.sheet_id FROM answer_sheets a JOIN review_queue rq ON rq.sheet_id = a.sheet_id "
        "WHERE a.exam_id = %s AND a.status = 'needs_review' AND a.matched_student_id IS NOT NULL "
        "AND rq.status IN ('pending', 'in_progress') AND 'duplicate_sbd' = ANY (rq.reasons::text[]) ORDER BY a.sheet_id", (exam_id,)).fetchall()
    ra: dict[int, list[int]] = {}
    for r in rows:
        ra.setdefault(r["sid"], []).append(r["sheet_id"])
    return ra


def _phieu_trung_dang_giu(conn, sheet_id: int) -> dict:
    """Khoá và trả phiếu mới nếu nó THỰC SỰ đang bị giữ vì duplicate_sbd; không thì XungDot (409) / KhongTimThay (404)."""
    sh = conn.execute("SELECT sheet_id, exam_id, status::text AS status, matched_student_id FROM answer_sheets WHERE sheet_id = %s FOR UPDATE",
                      (sheet_id,)).fetchone()
    if not sh:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    rv = conn.execute("SELECT review_id, reasons::text[] AS reasons FROM review_queue WHERE sheet_id = %s AND status IN ('pending', 'in_progress') "
                      "ORDER BY review_id DESC LIMIT 1", (sheet_id,)).fetchone()
    if sh["status"] != "needs_review" or not rv or "duplicate_sbd" not in rv["reasons"] or sh["matched_student_id"] is None:
        raise XungDot(f"Phiếu {sheet_id} không bị giữ vì trùng SBD (trạng thái '{sh['status']}').")
    return {**sh, "review_id": rv["review_id"]}


def bo_phieu_chup_lai(conn, sheet_id: int, user_id: int, ten_nguoi: str) -> dict:
    """Bỏ phiếu mới (ảnh chụp lại), GIỮ phiếu cũ. Phiếu mới -> 'rejected' (mã chup_lai_bi_bo); mục hàng đợi -> 'rejected'. Điểm không đổi."""
    sh = _phieu_trung_dang_giu(conn, sheet_id)
    cu = conn.execute("SELECT sheet_id FROM results WHERE exam_id = %s AND student_id = %s AND status <> 'void' AND sheet_id <> %s",
                      (sh["exam_id"], sh["matched_student_id"], sheet_id)).fetchone()
    ghi = f"Bỏ phiếu chụp lại #{sheet_id}, giữ phiếu cũ #{cu['sheet_id'] if cu else '?'} (trùng SBD) – bởi {ten_nguoi}"
    conn.execute("UPDATE review_queue SET status = 'rejected', resolved_by = %s, resolution_note = %s, resolved_at = now() WHERE review_id = %s",
                 (user_id, ghi, sh["review_id"]))
    conn.execute("UPDATE answer_sheets SET status = 'rejected', reject_code = %s, error_message = %s WHERE sheet_id = %s",
                 (MA_BI_BO, f"Đã bỏ: ảnh chụp lại trùng SBD với phiếu #{cu['sheet_id'] if cu else '?'} (giữ phiếu cũ).", sheet_id))
    return {"hanh_dong": "bo_phieu_moi", "sheet_id": sheet_id, "giu_phieu": cu["sheet_id"] if cu else None}


def thay_phieu_cu(conn, sheet_id: int, old_sheet_id: int, user_id: int, ten_nguoi: str) -> dict:
    """Dùng phiếu `sheet_id` thay phiếu cũ `old_sheet_id` – MỘT giao dịch (của yêu cầu). old_sheet_id là phiếu cũ mà người dùng ĐÃ THẤY khi xác nhận:
    nếu trong lúc đó đã đổi (người khác thay / chốt) -> 409, không làm gì. Thứ tự khoá: results của phiếu cũ -> phiếu mới (tránh deadlock)."""
    if old_sheet_id == sheet_id:
        raise DuLieuSai("Phiếu cũ và phiếu mới phải khác nhau.")
    pre = conn.execute("SELECT exam_id, matched_student_id FROM answer_sheets WHERE sheet_id = %s", (sheet_id,)).fetchone()
    if not pre:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")
    res = conn.execute("SELECT result_id, sheet_id, score, status::text AS status FROM results WHERE exam_id = %s AND student_id = %s "
                       "AND status <> 'void' FOR UPDATE", (pre["exam_id"], pre["matched_student_id"])).fetchone() if pre["matched_student_id"] else None
    if not res or res["sheet_id"] != old_sheet_id:
        raise XungDot("Phiếu cũ của thí sinh này đã thay đổi (có người vừa thay / chốt phiếu khác) – tải lại trang rồi chọn lại.")
    sh = _phieu_trung_dang_giu(conn, sheet_id)
    if sh["matched_student_id"] != pre["matched_student_id"]:
        raise XungDot("Phiếu này vừa được ghép lại thí sinh khác – tải lại trang.")
    sbd = conn.execute("SELECT student_code FROM students WHERE student_id = %s", (sh["matched_student_id"],)).fetchone()["student_code"]
    ly_do = f"Thay phiếu #{old_sheet_id} bằng phiếu #{sheet_id} (trùng SBD {sbd}) – xác nhận bởi {ten_nguoi}"
    conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(user_id),))
    conn.execute("SELECT set_config('app.change_reason', %s, true)", (ly_do,))
    conn.execute("UPDATE results SET status = 'void' WHERE result_id = %s", (res["result_id"],))       # trigger ghi score_audit_logs
    conn.execute("UPDATE answer_sheets SET status = 'rejected', reject_code = %s, error_message = %s WHERE sheet_id = %s",
                 (MA_BI_THAY, f"Đã bị thay bằng phiếu #{sheet_id} (trùng SBD {sbd}), điểm cũ đã rút.", old_sheet_id))
    kq = service.danh_gia_phieu(conn, sheet_id, user_id, f"Thay phiếu #{old_sheet_id} (trùng SBD) – giáo viên đã xác nhận")
    return {"hanh_dong": "thay_phieu_cu", "sheet_id": sheet_id, "phieu_cu": old_sheet_id, "diem_cu": float(res["score"]), "ket_qua": kq}
