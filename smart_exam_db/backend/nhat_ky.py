import json
import re

HANH_DONG = {
    "tao_ky_thi": "exam", "sua_ky_thi": "exam", "dong_ky_thi": "exam", "mo_ky_thi": "exam", "xoa_ky_thi": "exam",
    "tao_tai_khoan": "user", "dat_lai_mat_khau": "user", "vo_hieu_hoa_tai_khoan": "user", "kich_hoat_tai_khoan": "user",
    "gan_ky_thi": "user", "bo_gan_ky_thi": "user", "dat_lop_giao_vien": "user",
    "tao_lop": "class", "sua_lop": "class", "vo_hieu_hoa_lop": "class", "kich_hoat_lop": "class", "xoa_lop": "class",
    "them_giao_vien_vao_lop": "class", "bo_giao_vien_khoi_lop": "class",
}
HANH_DONG_DUYET = {"xac_nhan_hang_loat": "exam", "giu_nhu_may_cham": "exam"}
_NHAY_CAM = re.compile(r"pass|mat_khau|matkhau|hash|token|secret|cookie|session", re.IGNORECASE)


def _loc(v):
    if isinstance(v, dict):
        return {k: _loc(x) for k, x in v.items() if not _NHAY_CAM.search(str(k))}
    if isinstance(v, (list, tuple)):
        return [_loc(x) for x in v]
    return v


def ghi(conn, nd, hanh_dong: str, doi_tuong_id: int | None, chi_tiet: dict | None = None) -> None:
    loai = {**HANH_DONG, **HANH_DONG_DUYET}[hanh_dong]
    conn.execute("INSERT INTO admin_audit_log (actor_user_id, action, object_type, object_id, details) VALUES (%s, %s, %s, %s, %s::jsonb)",
                 (nd.user_id, hanh_dong, loai, doi_tuong_id, json.dumps(_loc(chi_tiet or {}), ensure_ascii=False, default=str)))


def thay_doi(cu: dict, moi: dict, khoa) -> dict:
    return {k: {"cu": cu.get(k), "moi": moi.get(k)} for k in khoa if cu.get(k) != moi.get(k)}


def ds(conn, trang: int = 1, co_trang: int = 100) -> dict:
    tong = conn.execute("SELECT count(*) AS n FROM admin_audit_log").fetchone()["n"]
    dong = conn.execute(
        "SELECT l.log_id, l.created_at, l.actor_user_id, u.username AS actor_username, l.action, l.object_type, l.object_id, l.details "
        "FROM admin_audit_log l LEFT JOIN users u ON u.user_id = l.actor_user_id ORDER BY l.created_at DESC, l.log_id DESC LIMIT %s OFFSET %s",
        (co_trang, (trang - 1) * co_trang)).fetchall()
    return {"tong": tong, "trang": trang, "co_trang": co_trang, "dong": dong}
