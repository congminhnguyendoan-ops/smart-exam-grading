"""
phan_quyen.py - Kiểm quyền theo đối tượng (chống IDOR). Quy tắc:
  admin            : mọi lớp / kỳ thi / phiếu.
  teacher          : lớp trong teacher_classes; kỳ thi do mình tạo (created_by) HOẶC thuộc lớp mình dạy; phiếu của các kỳ thi đó.
  student          : KHÔNG dùng API chấm (403 ở phụ thuộc `giao_vien` trong main.py).
  AUTH_MODE=demo   : bỏ qua kiểm quyền (hành vi cũ).
Đối tượng ngoài quyền -> KhongTimThay (404) với CÙNG thông báo như khi không tồn tại (không lộ tồn tại). Mọi SQL có tham số.
"""
from .auth import NguoiDung
from .service import DuLieuSai, KhongTimThay

# CÙNG một thông báo cho "lớp không tồn tại" và "không phụ trách lớp" -> không dò được mã lớp của người khác (hệ thống không tự tạo lớp)
MA_LOP_KHONG_DUNG = "Lớp không tồn tại hoặc bạn không phụ trách lớp này (hệ thống không tự tạo lớp – nhờ quản trị viên tạo / gán lớp)."
_LOP_CUA_TOI = "SELECT class_id FROM teacher_classes WHERE user_id = %s"


def duoc_xem_tat_ca(nd: NguoiDung) -> bool:
    return nd.demo or nd.la_admin


def kiem_ky_thi(conn, nd: NguoiDung, exam_id: int) -> None:
    if duoc_xem_tat_ca(nd):
        return                                    # kỳ thi không tồn tại -> service tự trả 404
    ok = conn.execute(f"SELECT 1 FROM exams e WHERE e.exam_id = %s AND (e.created_by = %s OR e.class_id IN ({_LOP_CUA_TOI}))",
                      (exam_id, nd.user_id, nd.user_id)).fetchone()
    if not ok:
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")


def kiem_phieu(conn, nd: NguoiDung, sheet_id: int) -> None:
    if duoc_xem_tat_ca(nd):
        return
    ok = conn.execute(f"SELECT 1 FROM answer_sheets a JOIN exams e USING (exam_id) WHERE a.sheet_id = %s "
                      f"AND (e.created_by = %s OR e.class_id IN ({_LOP_CUA_TOI}))", (sheet_id, nd.user_id, nd.user_id)).fetchone()
    if not ok:
        raise KhongTimThay(f"Không có phiếu {sheet_id}.")


def kiem_lop(conn, nd: NguoiDung, class_id: int) -> None:
    if duoc_xem_tat_ca(nd):
        return
    ok = conn.execute("SELECT 1 FROM teacher_classes WHERE user_id = %s AND class_id = %s", (nd.user_id, class_id)).fetchone()
    if not ok:
        raise KhongTimThay(f"Không có lớp {class_id}.")


def giai_lop_cho_ky_thi(conn, nd: NguoiDung, class_id: int | None, class_code: str | None) -> int | None:
    """class_id của kỳ thi mới (None nếu không chọn lớp). Lớp phải TỒN TẠI (không tự tạo) và thuộc lớp của người tạo (trừ admin / demo)."""
    if class_id is None and not class_code:
        return None
    if class_id is not None:
        r = conn.execute("SELECT class_id, class_code FROM classes WHERE class_id = %s", (class_id,)).fetchone()
    else:
        r = conn.execute("SELECT class_id, class_code FROM classes WHERE lower(class_code) = lower(%s)", (class_code.strip(),)).fetchone()
    if not r:
        raise DuLieuSai(MA_LOP_KHONG_DUNG)
    if not duoc_xem_tat_ca(nd):                       # kiểm quyền TRƯỚC khi nói gì về lớp (không lộ lớp người khác qua thông báo khác)
        ok = conn.execute("SELECT 1 FROM teacher_classes WHERE user_id = %s AND class_id = %s", (nd.user_id, r["class_id"])).fetchone()
        if not ok:
            raise DuLieuSai(MA_LOP_KHONG_DUNG)
    if class_id is not None and class_code and r["class_code"].lower() != class_code.strip().lower():
        raise DuLieuSai("class_id và class_code không cùng một lớp.")
    return r["class_id"]


def dieu_kien_ky_thi(nd: NguoiDung) -> tuple[str, tuple]:
    """Mệnh đề WHERE (alias e) + tham số để LỌC danh sách kỳ thi theo quyền."""
    if duoc_xem_tat_ca(nd):
        return "TRUE", ()
    return f"(e.created_by = %s OR e.class_id IN ({_LOP_CUA_TOI}))", (nd.user_id, nd.user_id)
