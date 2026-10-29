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
    if d.get("class_id") is not None:
        lop_dang_hoat_dong(conn, d["class_id"])               # lệnh I: kỳ thi mới chỉ gắn lớp đang hoạt động
    exam_id = tao_ky_thi(conn, d, chu)
    log.info("Quản trị %s tạo kỳ thi %s (phụ trách user_id %s)", nd.username, exam_id, chu)
    return exam_id


def sua_ky_thi(conn, exam_id: int, thay: dict) -> dict:
    """thay: chỉ các khoá người dùng gửi – exam_title (3–200 ký tự), exam_date (None = xoá ngày), class_id (None = bỏ lớp; lớp MỚI phải
    đang hoạt động). Đổi lớp đổi luôn giáo viên thấy kỳ thi QUA LỚP (người phụ trách giữ nguyên) – hiệu lực ở lần gọi kế tiếp."""
    e = mot_ky_thi(conn, exam_id)
    if not thay:
        raise DuLieuSai("Cần exam_title, exam_date và / hoặc class_id.")
    if "class_id" in thay:
        moi = thay["class_id"]
        if moi is not None and moi != e["class_id"]:
            lop_dang_hoat_dong(conn, moi)
        conn.execute("UPDATE exams SET class_id = %s, updated_at = now() WHERE exam_id = %s", (moi, exam_id))
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
    """Chỉ xoá kỳ thi CHƯA có phiếu / lô tải / kết quả (CSDL xoá dây chuyền phiếu theo kỳ thi – nên phải chặn ở đây). Đã có phiếu: chỉ đóng.
    An toàn thêm: không xoá kỳ thi đã có danh sách dự thi (exam_students cũng bị xoá dây chuyền) hoặc kỳ thi [DEMO…] (bộ demo bảo vệ)."""
    e = mot_ky_thi(conn, exam_id)
    if "[DEMO" in e["exam_title"].upper():
        raise XungDot("Kỳ thi [DEMO…] dùng cho demo / bảo vệ – không xoá qua web (chỉ đóng).")
    if conn.execute("SELECT 1 FROM exam_students WHERE exam_id = %s LIMIT 1", (exam_id,)).fetchone():
        raise XungDot("Kỳ thi đã có danh sách dự thi – xoá sẽ mất danh sách. Hãy ĐÓNG kỳ thi thay vì xoá.")
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


def tao_giao_vien(conn, nd: NguoiDung, username: str, full_name: str, email: str | None, mat_khau: str,
                  class_ids: list[int] | None = None) -> dict:
    """Tài khoản vai trò teacher (không tạo admin / sinh viên qua web). Mật khẩu băm scrypt (auth.bam_mat_khau); không trả / không log mật khẩu.
    class_ids (lệnh I): gán luôn các lớp (đang hoạt động) lúc tạo – lỗi lớp thì cả yêu cầu ROLLBACK (không còn tài khoản dở dang)."""
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
    if class_ids:                                           # kiểm lớp TRƯỚC khi ghi tài khoản (không để tài khoản dở dang)
        hop_le = {r["class_id"] for r in conn.execute("SELECT class_id FROM classes WHERE class_id = ANY(%s) AND is_active",
                                                      (list(set(class_ids)),)).fetchall()}
        if set(class_ids) - hop_le:
            raise DuLieuSai(f"Lớp không tồn tại hoặc đã bị vô hiệu hoá: {', '.join(map(str, sorted(set(class_ids) - hop_le)))}.")
    uid = conn.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, 'teacher') RETURNING user_id",
                       (username, email, auth.bam_mat_khau(mat_khau), full_name)).fetchone()["user_id"]
    log.info("Quản trị %s tạo tài khoản giáo viên %s (user_id %s)", nd.username, username, uid)
    if class_ids:
        dat_lop_cho_giao_vien(conn, nd, uid, class_ids)
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


# ------------------------------------------------------------------------------------------------ lớp học (lệnh I)
# Chỉ lớp + giáo viên của lớp. KHÔNG quản lý sinh viên (số sinh viên chỉ để xem). Trạng thái lớp: classes.is_active (migration 004).
# Lớp vô hiệu hoá: không chọn được cho kỳ thi mới / gán giáo viên mới; giáo viên ĐÃ gán vẫn xem kỳ thi cũ của lớp (giữ điểm, lịch sử).
MA_LOP_RE = re.compile(r"^[A-Za-z0-9._-]{2,30}$")
_DS_LOP = ("SELECT c.class_id, c.class_code, c.class_name, c.academic_year, c.is_active, c.created_at, "
           "(SELECT count(*) FROM teacher_classes tc WHERE tc.class_id = c.class_id) AS so_giao_vien, "
           "(SELECT count(*) FROM students s WHERE s.class_id = c.class_id) AS so_sinh_vien, "
           "(SELECT count(*) FROM exams e WHERE e.class_id = c.class_id) AS so_ky_thi, "
           "(SELECT string_agg(u.username, ', ' ORDER BY u.username) FROM teacher_classes tc JOIN users u ON u.user_id = tc.user_id "
           " WHERE tc.class_id = c.class_id) AS giao_vien FROM classes c")


def ds_lop(conn) -> list[dict]:
    return conn.execute(f"{_DS_LOP} ORDER BY c.is_active DESC, c.class_code").fetchall()


def mot_lop(conn, class_id: int) -> dict:
    r = conn.execute(f"{_DS_LOP} WHERE c.class_id = %s", (class_id,)).fetchone()
    if not r:
        raise KhongTimThay(f"Không có lớp {class_id}.")
    return r


def _ten_nam_hoc(class_name: str | None, academic_year: str | None) -> tuple[str | None, str | None]:
    ten = class_name.strip() if class_name is not None else None
    if ten is not None and not 1 <= len(ten) <= 150:
        raise DuLieuSai("Tên lớp không được để trống (tối đa 150 ký tự).")
    nam = (academic_year or "").strip() or None
    if nam is not None and len(nam) > 20:
        raise DuLieuSai("Năm học tối đa 20 ký tự (vd 2026-2027).")
    return ten, nam


def tao_lop(conn, nd: NguoiDung, class_code: str, class_name: str, academic_year: str | None) -> dict:
    ma = class_code.strip()
    if not MA_LOP_RE.match(ma):
        raise DuLieuSai("Mã lớp 2–30 ký tự, chỉ gồm chữ không dấu, số, dấu chấm, gạch dưới, gạch ngang (vd CNTT-K22A).")
    ten, nam = _ten_nam_hoc(class_name, academic_year)
    if conn.execute("SELECT 1 FROM classes WHERE lower(class_code) = lower(%s)", (ma,)).fetchone():
        raise XungDot(f"Mã lớp '{ma}' đã có (không phân biệt hoa thường).")
    cid = conn.execute("INSERT INTO classes (class_code, class_name, academic_year) VALUES (%s, %s, %s) RETURNING class_id",
                       (ma, ten, nam)).fetchone()["class_id"]
    log.info("Quản trị %s tạo lớp %s (class_id %s)", nd.username, ma, cid)
    return mot_lop(conn, cid)


def sua_lop(conn, class_id: int, thay: dict) -> dict:
    """Sửa tên và / hoặc năm học (mã lớp không đổi: kỳ thi, giao diện, trang bìa đã dùng nó)."""
    mot_lop(conn, class_id)
    if not thay:
        raise DuLieuSai("Cần class_name và / hoặc academic_year.")
    if "class_name" in thay:
        ten, _ = _ten_nam_hoc(thay["class_name"] or "", None)
        conn.execute("UPDATE classes SET class_name = %s WHERE class_id = %s", (ten, class_id))
    if "academic_year" in thay:
        _, nam = _ten_nam_hoc(None, thay["academic_year"])
        conn.execute("UPDATE classes SET academic_year = %s WHERE class_id = %s", (nam, class_id))
    return mot_lop(conn, class_id)


def dat_hoat_dong_lop(conn, nd: NguoiDung, class_id: int, hoat_dong: bool) -> dict:
    l = mot_lop(conn, class_id)
    conn.execute("UPDATE classes SET is_active = %s WHERE class_id = %s", (hoat_dong, class_id))
    log.info("Quản trị %s %s lớp %s", nd.username, "kích hoạt lại" if hoat_dong else "vô hiệu hoá", l["class_code"])
    return mot_lop(conn, class_id)


def xoa_lop(conn, nd: NguoiDung, class_id: int) -> None:
    """Chỉ xoá lớp CHƯA gắn kỳ thi và CHƯA có sinh viên (giáo viên của lớp bị bỏ gán theo). Còn lại: vô hiệu hoá."""
    l = mot_lop(conn, class_id)
    if l["so_ky_thi"] or l["so_sinh_vien"]:
        raise XungDot(f"Lớp đã gắn {l['so_ky_thi']} kỳ thi và có {l['so_sinh_vien']} sinh viên – không xoá được. Hãy VÔ HIỆU HOÁ lớp thay vì xoá.")
    conn.execute("DELETE FROM classes WHERE class_id = %s", (class_id,))
    log.info("Quản trị %s xoá lớp %s (chưa có kỳ thi / sinh viên)", nd.username, l["class_code"])


def lop_dang_hoat_dong(conn, class_id: int) -> dict:
    """Lớp chọn cho kỳ thi mới / gán giáo viên mới phải tồn tại và đang hoạt động."""
    l = mot_lop(conn, class_id)
    if not l["is_active"]:
        raise DuLieuSai(f"Lớp {l['class_code']} đã bị vô hiệu hoá – kích hoạt lại trước khi dùng.")
    return l


# ------------------------------------------------------------------------------------------------ giáo viên – lớp (nhiều – nhiều, teacher_classes)
# Quyền theo lớp tính lại MỖI yêu cầu từ teacher_classes (phan_quyen.py) -> thêm / bỏ gán có hiệu lực ở lần gọi kế tiếp.
# subject_id ("Môn tôi dạy") KHÔNG nhập được từ web: dòng giữ nguyên khi đặt lại danh sách lớp; dòng mới để NULL.
def giao_vien_cua_lop(conn, class_id: int) -> list[dict]:
    mot_lop(conn, class_id)
    return conn.execute("SELECT u.user_id, u.username, u.full_name, u.is_active, sj.subject_code, tc.assigned_at "
                        "FROM teacher_classes tc JOIN users u ON u.user_id = tc.user_id LEFT JOIN subjects sj ON sj.subject_id = tc.subject_id "
                        "WHERE tc.class_id = %s ORDER BY lower(u.username)", (class_id,)).fetchall()


def them_giao_vien_vao_lop(conn, nd: NguoiDung, class_id: int, user_id: int) -> list[dict]:
    l = lop_dang_hoat_dong(conn, class_id)
    u = giao_vien_hop_le(conn, user_id)
    conn.execute("INSERT INTO teacher_classes (user_id, class_id) VALUES (%s, %s) ON CONFLICT (user_id, class_id) DO NOTHING", (user_id, class_id))
    log.info("Quản trị %s gán %s vào lớp %s", nd.username, u["username"], l["class_code"])
    return giao_vien_cua_lop(conn, class_id)


def bo_giao_vien_khoi_lop(conn, nd: NguoiDung, class_id: int, user_id: int) -> list[dict]:
    l = mot_lop(conn, class_id)
    n = conn.execute("DELETE FROM teacher_classes WHERE class_id = %s AND user_id = %s", (class_id, user_id)).rowcount
    if not n:
        raise KhongTimThay(f"Giáo viên {user_id} không thuộc lớp {l['class_code']}.")
    log.info("Quản trị %s bỏ user_id %s khỏi lớp %s", nd.username, user_id, l["class_code"])
    return giao_vien_cua_lop(conn, class_id)


def lop_cua_giao_vien(conn, user_id: int) -> list[dict]:
    _giao_vien(conn, user_id)
    return conn.execute("SELECT c.class_id, c.class_code, c.class_name, c.academic_year, c.is_active, sj.subject_code "
                        "FROM teacher_classes tc JOIN classes c ON c.class_id = tc.class_id LEFT JOIN subjects sj ON sj.subject_id = tc.subject_id "
                        "WHERE tc.user_id = %s ORDER BY c.class_code", (user_id,)).fetchall()


def dat_lop_cho_giao_vien(conn, nd: NguoiDung, user_id: int, class_ids: list[int]) -> list[dict]:
    """Đặt ĐÚNG danh sách lớp của giáo viên (tick nhiều lớp). Lớp THÊM mới phải đang hoạt động và giáo viên phải đang hoạt động;
    lớp giữ lại không đổi (giữ môn); lớp bỏ đi bị xoá khỏi teacher_classes. Id lớp không tồn tại -> 422, không đổi gì."""
    u = _giao_vien(conn, user_id)
    muon = set(class_ids)
    co = {r["class_id"]: r for r in conn.execute("SELECT class_id, class_code, is_active FROM classes WHERE class_id = ANY(%s)", (list(muon),)).fetchall()}
    thieu = sorted(muon - set(co))
    if thieu:
        raise DuLieuSai(f"Không có lớp: {', '.join(map(str, thieu))}.")
    dang = {r["class_id"] for r in conn.execute("SELECT class_id FROM teacher_classes WHERE user_id = %s", (user_id,)).fetchall()}
    them, bo = muon - dang, dang - muon
    if them and not u["is_active"]:
        raise DuLieuSai("Tài khoản đang bị vô hiệu hoá – kích hoạt lại trước khi gán lớp.")
    tat = sorted(co[c]["class_code"] for c in them if not co[c]["is_active"])
    if tat:
        raise DuLieuSai(f"Lớp đã bị vô hiệu hoá, không gán thêm được: {', '.join(tat)}.")
    if bo:
        conn.execute("DELETE FROM teacher_classes WHERE user_id = %s AND class_id = ANY(%s)", (user_id, list(bo)))
    for c in sorted(them):
        conn.execute("INSERT INTO teacher_classes (user_id, class_id) VALUES (%s, %s)", (user_id, c))
    if them or bo:
        log.info("Quản trị %s đặt lớp cho %s: thêm %s, bỏ %s", nd.username, u["username"], sorted(them), sorted(bo))
    return lop_cua_giao_vien(conn, user_id)


def kiem_dang_mo(conn, exam_id: int) -> None:
    """Tải ảnh: kỳ thi đã đóng -> 409. Gọi SAU phan_quyen.kiem_ky_thi (ngoài quyền vẫn là 404, không lộ trạng thái)."""
    r = conn.execute("SELECT status::text AS s FROM exams WHERE exam_id = %s", (exam_id,)).fetchone()
    if r and r["s"] == TRANG_THAI_DONG:
        raise XungDot(THONG_BAO_DA_DONG)
