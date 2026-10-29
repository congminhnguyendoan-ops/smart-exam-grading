"""
quan_tri.py - Dịch vụ QUẢN TRỊ (chỉ admin; quyền kiểm ở main.chi_admin): kỳ thi (tạo / sửa tên + ngày / đóng – mở / xoá khi chưa có phiếu)
và tài khoản giáo viên. KHÔNG đổi cấu trúc CSDL (không migration mới):
  - "giáo viên phụ trách" kỳ thi = exams.created_by (cột có sẵn, phan_quyen.py đã cho người tạo thấy kỳ thi) -> gán / bỏ gán = đổi created_by;
  - đóng / mở = exams.status ('closed' / 'draft' – ENUM exam_status có sẵn). Kỳ thi đóng KHÔNG nhận ảnh mới; duyệt, bảng điểm, Excel vẫn dùng được.
Tạo kỳ thi dùng lại service.tao_ky_thi (cùng quy tắc kiểm đáp án). Mọi SQL có tham số. Không tự commit. Không log mật khẩu.
"""
import logging
import re

from . import auth
from .auth import NguoiDung
from .nguoi_dung import EMAIL_RE
from .service import DuLieuSai, KhongTimThay, XungDot, tao_ky_thi

log = logging.getLogger("smart_exam.quan_tri")
TEN_DANG_NHAP_RE = re.compile(r"^[A-Za-z0-9._-]{3,50}$")

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


def _mot_tai_khoan(conn, user_id: int) -> dict:
    return conn.execute(f"{_DS_TAI_KHOAN} WHERE u.user_id = %s", (user_id,)).fetchone()


def _giao_vien(conn, user_id: int) -> dict:
    """Trang web CHỈ quản lý tài khoản GIÁO VIÊN: admin khác / sinh viên / id không có -> 404 cùng một thông báo
    (tài khoản admin quản lý bằng `python -m backend.tai_khoan`; không tự khoá chính mình)."""
    u = conn.execute("SELECT user_id, username, role::text AS role, is_active FROM users WHERE user_id = %s", (user_id,)).fetchone()
    if not u or u["role"] != "teacher":
        raise KhongTimThay(f"Không có tài khoản giáo viên {user_id}.")
    return u


def _mat_khau_hop_le(mat_khau: str) -> None:
    loi = auth.mat_khau_hop_le(mat_khau)
    if loi:
        raise DuLieuSai(loi)                                  # thông báo KHÔNG chứa mật khẩu


def tao_giao_vien(conn, nd: NguoiDung, username: str, full_name: str, email: str | None, mat_khau: str) -> dict:
    """Tài khoản vai trò teacher (không tạo admin / sinh viên qua web). Mật khẩu băm scrypt (auth.bam_mat_khau); không trả / không log mật khẩu."""
    username, full_name = username.strip(), full_name.strip()
    if not TEN_DANG_NHAP_RE.match(username):
        raise DuLieuSai("Tên đăng nhập 3–50 ký tự, chỉ gồm chữ không dấu, số, dấu chấm, gạch dưới, gạch ngang.")
    if not full_name or len(full_name) > 150:
        raise DuLieuSai("Họ tên không được để trống (tối đa 150 ký tự).")
    email = (email or "").strip() or f"{username.lower()}@smartexam.local"
    if not EMAIL_RE.match(email) or len(email) > 255:
        raise DuLieuSai("Email không hợp lệ.")
    _mat_khau_hop_le(mat_khau)
    if conn.execute("SELECT 1 FROM users WHERE lower(username) = lower(%s)", (username,)).fetchone():
        raise XungDot("Tên đăng nhập đã được dùng.")
    if conn.execute("SELECT 1 FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone():
        raise XungDot("Email đã được dùng cho tài khoản khác.")
    uid = conn.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, 'teacher') RETURNING user_id",
                       (username, email, auth.bam_mat_khau(mat_khau), full_name)).fetchone()["user_id"]
    log.info("Quản trị %s tạo tài khoản giáo viên %s (user_id %s)", nd.username, username, uid)
    return _mot_tai_khoan(conn, uid)


def dat_lai_mat_khau(conn, nd: NguoiDung, user_id: int, mat_khau: str) -> None:
    """Đổi hash -> mọi phiên cũ của giáo viên đó hết hiệu lực (token mang dấu vân tay hash). Không log mật khẩu."""
    u = _giao_vien(conn, user_id)
    _mat_khau_hop_le(mat_khau)
    conn.execute("UPDATE users SET password_hash = %s, updated_at = now() WHERE user_id = %s", (auth.bam_mat_khau(mat_khau), user_id))
    log.info("Quản trị %s đặt lại mật khẩu cho %s", nd.username, u["username"])


def dat_hoat_dong(conn, nd: NguoiDung, user_id: int, hoat_dong: bool) -> dict:
    """Vô hiệu hoá: is_active = FALSE -> không đăng nhập được, phiên đang có bị từ chối ở lần gọi kế tiếp (nguoi_dung.xac_thuc tra users mỗi yêu cầu)."""
    u = _giao_vien(conn, user_id)
    conn.execute("UPDATE users SET is_active = %s, updated_at = now() WHERE user_id = %s", (hoat_dong, user_id))
    log.info("Quản trị %s %s tài khoản %s", nd.username, "kích hoạt lại" if hoat_dong else "vô hiệu hoá", u["username"])
    return _mot_tai_khoan(conn, user_id)


def ky_thi_cua_giao_vien(conn, user_id: int) -> list[dict]:
    """Kỳ thi giáo viên thấy: `phu_trach` (exams.created_by – gán / bỏ gán được ở đây) và `lop` (qua teacher_classes – đổi bằng gán lớp)."""
    _giao_vien(conn, user_id)
    return conn.execute(
        "SELECT e.exam_id, e.exam_title, e.status::text AS status, c.class_code, "
        "CASE WHEN e.created_by = %(u)s THEN 'phu_trach' ELSE 'lop' END AS nguon "
        "FROM exams e LEFT JOIN classes c ON c.class_id = e.class_id "
        "WHERE e.created_by = %(u)s OR e.class_id IN (SELECT class_id FROM teacher_classes WHERE user_id = %(u)s) ORDER BY e.exam_id DESC",
        {"u": user_id}).fetchall()


def gan_ky_thi(conn, nd: NguoiDung, user_id: int, exam_id: int) -> list[dict]:
    """Giáo viên (đang hoạt động) thành người phụ trách kỳ thi. Mỗi kỳ thi MỘT người phụ trách: gán người mới thay người cũ."""
    u = _giao_vien(conn, user_id)
    if not u["is_active"]:
        raise DuLieuSai("Tài khoản đang bị vô hiệu hoá – kích hoạt lại trước khi gán kỳ thi.")
    mot_ky_thi(conn, exam_id)
    conn.execute("UPDATE exams SET created_by = %s, updated_at = now() WHERE exam_id = %s", (user_id, exam_id))
    log.info("Quản trị %s gán kỳ thi %s cho %s", nd.username, exam_id, u["username"])
    return ky_thi_cua_giao_vien(conn, user_id)


def bo_gan_ky_thi(conn, nd: NguoiDung, user_id: int, exam_id: int) -> list[dict]:
    """Bỏ gán: người phụ trách chuyển về chính admin đang thao tác (created_by NOT NULL). Giáo viên vẫn thấy kỳ thi nếu nó thuộc lớp mình dạy."""
    u = _giao_vien(conn, user_id)
    e = mot_ky_thi(conn, exam_id)
    if e["teacher_user_id"] != user_id:
        raise KhongTimThay(f"Kỳ thi {exam_id} không được gán cho tài khoản này.")
    conn.execute("UPDATE exams SET created_by = %s, updated_at = now() WHERE exam_id = %s", (nd.user_id, exam_id))
    log.info("Quản trị %s bỏ gán kỳ thi %s khỏi %s", nd.username, exam_id, u["username"])
    return ky_thi_cua_giao_vien(conn, user_id)


def kiem_dang_mo(conn, exam_id: int) -> None:
    """Tải ảnh: kỳ thi đã đóng -> 409. Gọi SAU phan_quyen.kiem_ky_thi (ngoài quyền vẫn là 404, không lộ trạng thái)."""
    r = conn.execute("SELECT status::text AS s FROM exams WHERE exam_id = %s", (exam_id,)).fetchone()
    if r and r["s"] == TRANG_THAI_DONG:
        raise XungDot(THONG_BAO_DA_DONG)
