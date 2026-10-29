"""
quan_tri.py - Dịch vụ QUẢN TRỊ (chỉ admin; quyền kiểm ở main.chi_admin): kỳ thi (tạo / sửa tên + ngày / đóng – mở / xoá khi chưa có phiếu)
và tài khoản giáo viên. KHÔNG đổi cấu trúc CSDL (không migration mới):
  - "giáo viên phụ trách" kỳ thi = exams.created_by (cột có sẵn, phan_quyen.py đã cho người tạo thấy kỳ thi) -> gán / bỏ gán = đổi created_by;
  - đóng / mở = exams.status ('closed' / 'draft' – ENUM exam_status có sẵn). Kỳ thi đóng KHÔNG nhận ảnh mới; duyệt, bảng điểm, Excel vẫn dùng được.
Tạo kỳ thi dùng lại service.tao_ky_thi (cùng quy tắc kiểm đáp án). Mọi SQL có tham số. Không tự commit. Không log mật khẩu.
"""
import logging

from .auth import NguoiDung
from .service import DuLieuSai, KhongTimThay, XungDot, tao_ky_thi

log = logging.getLogger("smart_exam.quan_tri")

TRANG_THAI_DONG, TRANG_THAI_MO = "closed", "draft"
THONG_BAO_DA_DONG = "Kỳ thi đã đóng – không nhận thêm ảnh. Nhờ quản trị viên mở lại nếu cần."


# ------------------------------------------------------------------------------------------------ kỳ thi
_DS_KY_THI = ("SELECT e.exam_id, e.exam_title, e.exam_date, e.status::text AS status, e.num_questions, e.created_at, "
              "sj.subject_code, sj.subject_name, e.class_id, c.class_code, c.class_name, "
              "u.user_id AS teacher_user_id, u.username AS teacher_username, u.full_name AS teacher_name, u.role::text AS teacher_role, "
              "(SELECT count(*) FROM answer_sheets a WHERE a.exam_id = e.exam_id) AS so_phieu, "
              "(SELECT string_agg(ec.code, ', ' ORDER BY ec.code) FROM exam_codes ec WHERE ec.exam_id = e.exam_id) AS ma_de "
              "FROM exams e JOIN subjects sj ON sj.subject_id = e.subject_id LEFT JOIN classes c ON c.class_id = e.class_id "
              "JOIN users u ON u.user_id = e.created_by")


def ds_ky_thi(conn) -> list[dict]:
    return conn.execute(f"{_DS_KY_THI} ORDER BY e.exam_id DESC").fetchall()


def mot_ky_thi(conn, exam_id: int) -> dict:
    r = conn.execute(f"{_DS_KY_THI} WHERE e.exam_id = %s", (exam_id,)).fetchone()
    if not r:
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    return r


def giao_vien_hop_le(conn, user_id: int) -> dict:
    """Giáo viên phụ trách phải là tài khoản teacher đang hoạt động (không gán cho admin / sinh viên / tài khoản bị vô hiệu hoá)."""
    u = conn.execute("SELECT user_id, username, full_name, role::text AS role, is_active FROM users WHERE user_id = %s", (user_id,)).fetchone()
    if not u or u["role"] != "teacher" or not u["is_active"]:
        raise DuLieuSai("Giáo viên phụ trách không tồn tại, không phải tài khoản giáo viên hoặc đã bị vô hiệu hoá.")
    return u


def tao_ky_thi_qt(conn, nd: NguoiDung, d: dict, teacher_user_id: int | None) -> int:
    """d đã qua phan_quyen.giai_lop_cho_ky_thi (class_id). Người phụ trách = giáo viên được chọn, không chọn thì chính admin."""
    chu = giao_vien_hop_le(conn, teacher_user_id)["user_id"] if teacher_user_id is not None else nd.user_id
    exam_id = tao_ky_thi(conn, d, chu)
    log.info("Quản trị %s tạo kỳ thi %s (phụ trách user_id %s)", nd.username, exam_id, chu)
    return exam_id


def sua_ky_thi(conn, exam_id: int, thay: dict) -> dict:
    """thay: chỉ các khoá người dùng gửi – exam_title (3–200 ký tự) và / hoặc exam_date (None = xoá ngày)."""
    mot_ky_thi(conn, exam_id)
    if not thay:
        raise DuLieuSai("Cần exam_title và / hoặc exam_date.")
    if "exam_title" in thay:
        ten = (thay["exam_title"] or "").strip()
        if not 3 <= len(ten) <= 200:
            raise DuLieuSai("Tên kỳ thi phải dài 3–200 ký tự.")
        conn.execute("UPDATE exams SET exam_title = %s, updated_at = now() WHERE exam_id = %s", (ten, exam_id))
    if "exam_date" in thay:
        conn.execute("UPDATE exams SET exam_date = %s, updated_at = now() WHERE exam_id = %s", (thay["exam_date"], exam_id))
    return mot_ky_thi(conn, exam_id)


def dat_dong_mo(conn, exam_id: int, dong: bool) -> dict:
    """Đóng: status = 'closed'. Mở lại: 'draft' (giá trị mặc định khi tạo; hệ thống chưa dùng 'published' / 'grading')."""
    mot_ky_thi(conn, exam_id)
    conn.execute("UPDATE exams SET status = %s::exam_status, updated_at = now() WHERE exam_id = %s",
                 (TRANG_THAI_DONG if dong else TRANG_THAI_MO, exam_id))
    return mot_ky_thi(conn, exam_id)


def xoa_ky_thi(conn, exam_id: int) -> None:
    """Chỉ xoá kỳ thi CHƯA có phiếu / lô tải / kết quả (CSDL xoá dây chuyền phiếu theo kỳ thi – nên phải chặn ở đây). Đã có phiếu: chỉ đóng."""
    mot_ky_thi(conn, exam_id)
    n = conn.execute("SELECT (SELECT count(*) FROM answer_sheets WHERE exam_id = %(e)s) + (SELECT count(*) FROM scan_batches WHERE exam_id = %(e)s) "
                     "+ (SELECT count(*) FROM results WHERE exam_id = %(e)s) AS n", {"e": exam_id}).fetchone()["n"]
    if n:
        raise XungDot("Kỳ thi đã có phiếu – không xoá được (để giữ điểm và lịch sử). Hãy ĐÓNG kỳ thi thay vì xoá.")
    conn.execute("DELETE FROM exams WHERE exam_id = %s", (exam_id,))


# ------------------------------------------------------------------------------------------------ tài khoản
_DS_TAI_KHOAN = ("SELECT u.user_id, u.username, u.full_name, u.email, u.role::text AS role, u.is_active, u.last_login_at, u.created_at, "
                 "(SELECT count(*) FROM exams e WHERE e.created_by = u.user_id) AS so_ky_thi, "
                 "(SELECT string_agg(c.class_code, ', ' ORDER BY c.class_code) FROM teacher_classes tc JOIN classes c ON c.class_id = tc.class_id "
                 " WHERE tc.user_id = u.user_id) AS lop FROM users u")


def ds_tai_khoan(conn) -> list[dict]:
    """Tài khoản admin + giáo viên (sinh viên không quản lý ở đây). KHÔNG có password_hash."""
    return conn.execute(f"{_DS_TAI_KHOAN} WHERE u.role IN ('admin', 'teacher') ORDER BY u.role, lower(u.username)").fetchall()


def kiem_dang_mo(conn, exam_id: int) -> None:
    """Tải ảnh: kỳ thi đã đóng -> 409. Gọi SAU phan_quyen.kiem_ky_thi (ngoài quyền vẫn là 404, không lộ trạng thái)."""
    r = conn.execute("SELECT status::text AS s FROM exams WHERE exam_id = %s", (exam_id,)).fetchone()
    if r and r["s"] == TRANG_THAI_DONG:
        raise XungDot(THONG_BAO_DA_DONG)
