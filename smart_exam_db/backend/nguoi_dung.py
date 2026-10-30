"""
nguoi_dung.py - Dịch vụ tài khoản: đăng nhập, hồ sơ, đổi mật khẩu, lớp của giáo viên, danh sách sinh viên của lớp.
Mọi truy vấn SQL dùng tham số. KHÔNG tự commit (API / test quyết định). Không log mật khẩu / token.
"""
import re
import time

from . import auth
from .config import CauHinh
from .service import DuLieuSai, KhongTimThay, LoiDichVu

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ChuaDangNhap(LoiDichVu):
    ma_http = 401


class KhongCoQuyen(LoiDichVu):
    ma_http = 403


class QuaNhieuLan(LoiDichVu):
    ma_http = 429


# ------------------------------------------------------------------------------------------------ đăng nhập / phiên
def dang_nhap(conn, cfg: CauHinh, username: str, mat_khau: str, ip: str) -> tuple[str, auth.NguoiDung]:
    """Đúng -> (token, người dùng). Mọi lỗi (sai tên, sai mật khẩu, tài khoản bị khoá) cùng MỘT thông báo + 401; quá 5 lần sai / 15 phút -> 429."""
    khoa = (username.strip().lower(), ip)
    if auth.gioi_han.bi_chan(khoa):
        raise QuaNhieuLan("Thử đăng nhập sai quá nhiều lần. Hãy thử lại sau ít phút.")
    u = conn.execute("SELECT user_id, username, full_name, email, role::text AS role, is_active, password_hash FROM users "
                     "WHERE lower(username) = lower(%s)", (username.strip(),)).fetchone()
    if u is None:
        auth.kiem_gia()
        dung = False
    else:
        dung = auth.kiem_mat_khau(mat_khau, u["password_hash"]) and u["is_active"]
    if not dung:
        auth.gioi_han.ghi_sai(khoa)
        raise ChuaDangNhap(auth.THONG_BAO_SAI)
    auth.gioi_han.xoa(khoa)
    conn.execute("UPDATE users SET last_login_at = now() WHERE user_id = %s", (u["user_id"],))
    token = auth.tao_token(cfg.auth_secret, u["user_id"], u["password_hash"], cfg.session_hours)
    return token, auth.NguoiDung(u["user_id"], u["username"], u["full_name"], u["email"], u["role"])


def xac_thuc(conn, cfg: CauHinh, token: str | None, x_user: str | None) -> auth.NguoiDung:
    """Người dùng hiện tại. AUTH_MODE=demo: DEMO_USER / X-User (hành vi cũ, không kiểm quyền). on: token ký hợp lệ (cookie hoặc Bearer)."""
    if cfg.auth_mode == "demo":
        ten = x_user or cfg.nguoi_dung_demo
        u = conn.execute("SELECT user_id, username, full_name, email, role::text AS role FROM users WHERE lower(username) = lower(%s) AND is_active",
                         (ten,)).fetchone()
        if not u:
            raise KhongTimThay(f"Không có người dùng '{ten}' (đặt DEMO_USER trong .env).")
        return auth.NguoiDung(u["user_id"], u["username"], u["full_name"], u["email"], u["role"], demo=True)
    if not token:
        raise ChuaDangNhap("Cần đăng nhập.")
    d = auth.doc_token(cfg.auth_secret, token)
    u = conn.execute("SELECT user_id, username, full_name, email, role::text AS role, is_active, password_hash FROM users WHERE user_id = %s",
                     (d["u"],)).fetchone() if d else None
    if not d or not u or not u["is_active"] or auth._vet_mat_khau(u["password_hash"]) != d["f"]:
        raise ChuaDangNhap("Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")
    return auth.NguoiDung(u["user_id"], u["username"], u["full_name"], u["email"], u["role"])


# ------------------------------------------------------------------------------------------------ hồ sơ
def ho_so(conn, nd: auth.NguoiDung) -> dict:
    return conn.execute("SELECT user_id, username, full_name, email, role::text AS role, last_login_at, created_at FROM users WHERE user_id = %s",
                        (nd.user_id,)).fetchone()


def sua_ho_so(conn, nd: auth.NguoiDung, full_name: str | None, email: str | None) -> dict:
    if full_name is None and email is None:
        raise DuLieuSai("Cần full_name và / hoặc email.")
    if full_name is not None and not full_name.strip():
        raise DuLieuSai("Họ tên không được để trống.")
    if email is not None and not EMAIL_RE.match(email.strip()):
        raise DuLieuSai("Email không hợp lệ.")
    conn.execute("UPDATE users SET full_name = COALESCE(%s, full_name), email = COALESCE(%s, email) WHERE user_id = %s",
                 (full_name.strip() if full_name is not None else None, email.strip() if email is not None else None, nd.user_id))
    return ho_so(conn, nd)


def doi_mat_khau(conn, nd: auth.NguoiDung, cu: str, moi: str) -> None:
    khoa = (nd.username.lower(), "doi-mat-khau")
    if auth.gioi_han.bi_chan(khoa):
        raise QuaNhieuLan("Nhập sai mật khẩu cũ quá nhiều lần. Hãy thử lại sau ít phút.")
    u = conn.execute("SELECT password_hash FROM users WHERE user_id = %s", (nd.user_id,)).fetchone()
    if not auth.kiem_mat_khau(cu, u["password_hash"]):
        auth.gioi_han.ghi_sai(khoa)
        raise DuLieuSai("Mật khẩu cũ không đúng.")
    loi = auth.mat_khau_hop_le(moi)
    if loi:
        raise DuLieuSai(loi)
    if moi == cu:
        raise DuLieuSai("Mật khẩu mới phải khác mật khẩu cũ.")
    auth.gioi_han.xoa(khoa)
    conn.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (auth.bam_mat_khau(moi), nd.user_id))


# ------------------------------------------------------------------------------------------------ lớp + sinh viên
def lop_cua_toi(conn, nd: auth.NguoiDung) -> list[dict]:
    """Lớp mình phụ trách (kèm môn dạy + số sinh viên). Admin: mọi lớp (không gắn môn)."""
    if nd.la_admin or nd.demo:
        return conn.execute(
            "SELECT c.class_id, c.class_code, c.class_name, c.academic_year, NULL::bigint AS subject_id, NULL::text AS subject_code, "
            "NULL::text AS subject_name, (SELECT count(*) FROM students s WHERE s.class_id = c.class_id) AS so_sinh_vien "
            "FROM classes c ORDER BY c.class_code").fetchall()
    return conn.execute(
        "SELECT c.class_id, c.class_code, c.class_name, c.academic_year, tc.subject_id, sj.subject_code, sj.subject_name, "
        "(SELECT count(*) FROM students s WHERE s.class_id = c.class_id) AS so_sinh_vien "
        "FROM teacher_classes tc JOIN classes c ON c.class_id = tc.class_id LEFT JOIN subjects sj ON sj.subject_id = tc.subject_id "
        "WHERE tc.user_id = %s ORDER BY c.class_code", (nd.user_id,)).fetchall()


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def sinh_vien_lop(conn, class_id: int, q: str | None, trang: int, co_trang: int) -> dict:
    """Quyền đã kiểm ở phan_quyen.kiem_lop. Tìm theo mã hoặc tên (không phân biệt hoa thường), phân trang."""
    lop = conn.execute("SELECT class_id, class_code, class_name, academic_year FROM classes WHERE class_id = %s", (class_id,)).fetchone()
    if not lop:
        raise KhongTimThay(f"Không có lớp {class_id}.")
    mau = f"%{_escape_like(q.strip())}%" if q and q.strip() else None
    dk = "s.class_id = %s AND (%s::text IS NULL OR s.student_code ILIKE %s OR s.full_name ILIKE %s)"
    tham = (class_id, mau, mau, mau)
    tong = conn.execute(f"SELECT count(*) AS n FROM students s WHERE {dk}", tham).fetchone()["n"]
    ds = conn.execute(f"SELECT s.student_id, s.student_code, s.full_name, s.date_of_birth, s.gender, s.email FROM students s WHERE {dk} "
                      "ORDER BY s.student_code LIMIT %s OFFSET %s", (*tham, co_trang, (trang - 1) * co_trang)).fetchall()
    return {"class": lop, "tong": tong, "trang": trang, "co_trang": co_trang, "sinh_vien": ds}
