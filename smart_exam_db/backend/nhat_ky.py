"""
nhat_ky.py - NHẬT KÝ THAO TÁC QUẢN TRỊ (lệnh V4, bảng admin_audit_log – migration 005).

Gọi ghi(...) ở main.py NGAY SAU khi hàm quan_tri.* chạy xong, trong CÙNG giao dịch của yêu cầu:
  - thao tác lỗi (ngoại lệ) không tới được dòng ghi -> chỉ ghi thao tác THÀNH CÔNG;
  - giao dịch rollback thì dòng nhật ký mất theo -> không có nhật ký "ma".
details KHÔNG BAO GIỜ chứa mật khẩu / mã băm / token: nơi gọi chỉ đưa tên, mã, giá trị cũ → mới; _loc() bỏ thêm mọi khoá có tên nhạy cảm (phòng khi sót).
Không tự commit. Mọi SQL có tham số.
"""
import json
import re

HANH_DONG = {
    # kỳ thi
    "tao_ky_thi": "exam", "sua_ky_thi": "exam", "dong_ky_thi": "exam", "mo_ky_thi": "exam", "xoa_ky_thi": "exam",
    # tài khoản giáo viên
    "tao_tai_khoan": "user", "dat_lai_mat_khau": "user", "vo_hieu_hoa_tai_khoan": "user", "kich_hoat_tai_khoan": "user",
    "gan_ky_thi": "user", "bo_gan_ky_thi": "user", "dat_lop_giao_vien": "user",
    # lớp
    "tao_lop": "class", "sua_lop": "class", "vo_hieu_hoa_lop": "class", "kich_hoat_lop": "class", "xoa_lop": "class",
    "them_giao_vien_vao_lop": "class", "bo_giao_vien_khoi_lop": "class",
    # duyệt phiếu (lệnh AF): giáo viên xác nhận hàng loạt câu của MỘT phiếu – đối tượng là kỳ thi (CHECK của migration 005), sheet_id trong details
    "xac_nhan_hang_loat": "exam",
}
_NHAY_CAM = re.compile(r"pass|mat_khau|matkhau|hash|token|secret|cookie|session", re.IGNORECASE)


def _loc(v):
    """Bỏ mọi khoá có tên nhạy cảm (mọi tầng)."""
    if isinstance(v, dict):
        return {k: _loc(x) for k, x in v.items() if not _NHAY_CAM.search(str(k))}
    if isinstance(v, (list, tuple)):
        return [_loc(x) for x in v]
    return v


def ghi(conn, nd, hanh_dong: str, doi_tuong_id: int | None, chi_tiet: dict | None = None) -> None:
    """Một dòng nhật ký. hanh_dong phải thuộc HANH_DONG (loại đối tượng suy ra từ đó)."""
    loai = HANH_DONG[hanh_dong]                                                # KeyError = lỗi lập trình, không nuốt
    conn.execute("INSERT INTO admin_audit_log (actor_user_id, action, object_type, object_id, details) VALUES (%s, %s, %s, %s, %s::jsonb)",
                 (nd.user_id, hanh_dong, loai, doi_tuong_id, json.dumps(_loc(chi_tiet or {}), ensure_ascii=False, default=str)))


def thay_doi(cu: dict, moi: dict, khoa) -> dict:
    """{khoá: {"cu": ..., "moi": ...}} cho các khoá có đổi giá trị."""
    return {k: {"cu": cu.get(k), "moi": moi.get(k)} for k in khoa if cu.get(k) != moi.get(k)}


def ds(conn, trang: int = 1, co_trang: int = 100) -> dict:
    """Mới nhất trước. Trả tong, trang, co_trang, dong (kèm tên đăng nhập người thao tác – None nếu tài khoản đã bị xoá)."""
    tong = conn.execute("SELECT count(*) AS n FROM admin_audit_log").fetchone()["n"]
    dong = conn.execute(
        "SELECT l.log_id, l.created_at, l.actor_user_id, u.username AS actor_username, l.action, l.object_type, l.object_id, l.details "
        "FROM admin_audit_log l LEFT JOIN users u ON u.user_id = l.actor_user_id ORDER BY l.created_at DESC, l.log_id DESC LIMIT %s OFFSET %s",
        (co_trang, (trang - 1) * co_trang)).fetchall()
    return {"tong": tong, "trang": trang, "co_trang": co_trang, "dong": dong}
