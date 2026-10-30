"""
don_anh.py - Dọn ẢNH TẠM của phiếu đã chốt (docs/thiet_ke_chup_dien_thoai.md mục 7). Điểm, đáp án, lý do, SHA-256 ảnh GIỮ NGUYÊN.

Được xoá: phiếu `graded` (có điểm chính thức) hoặc `rejected`, chưa xoá, lần thay đổi cuối (phiếu / kết quả) cách đây ≥ ANH_GIU_GIO giờ.
KHÔNG xoá phiếu `needs_review` (giáo viên còn cần ảnh để duyệt); mặc định không xoá kỳ thi có "[DEMO" trong tên (ANH_GIU_DEMO=1).
Tệp xoá: ảnh gốc + ảnh nắn + ảnh ô viết tay (ocr_digits). Chỉ tệp nằm TRONG storage_dir; thiếu tệp không lỗi. Xoá tệp TRƯỚC rồi ghi
image_deleted_at (đứt giữa chừng thì lần sau làm lại – không bao giờ đánh dấu "đã xoá" khi tệp còn).

  python -m backend.don_anh              # XEM TRƯỚC (chỉ đọc): phiếu nào sẽ bị xoá ảnh
  python -m backend.don_anh --ap-dung    # xoá thật (cần migration 003)
Máy chủ: luồng nền chạy lúc khởi động + mỗi giờ khi ANH_XOA_TU_DONG=1 (tools/chay_server_lan.py bật sẵn).
"""
import argparse
import logging
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import CauHinh

log = logging.getLogger("smart_exam.don_anh")
CHU_KY_GIAY = 3600


def da_co_cot(conn) -> bool:
    """Migration 003 đã áp chưa (có cột answer_sheets.image_deleted_at)."""
    return conn.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'answer_sheets' AND column_name = 'image_deleted_at'"
                        ).fetchone() is not None


def phieu_can_xoa(conn, cfg: CauHinh, bay_gio: datetime | None = None, gioi_han: int = 500, ky_thi: list[int] | None = None) -> list[dict]:
    """[{sheet_id, exam_id, status, moc, tep: [đường dẫn tương đối]}] – CHỈ ĐỌC. `bay_gio`: đồng hồ giả (test); `ky_thi`: chỉ các kỳ thi này."""
    moc = (bay_gio or datetime.now(timezone.utc)) - timedelta(hours=cfg.anh_giu_gio)
    rows = conn.execute(
        "SELECT a.sheet_id, a.exam_id, a.status::text AS status, a.image_path, a.aligned_image_path, "
        "GREATEST(a.updated_at, COALESCE(r.updated_at, a.updated_at)) AS moc, "
        "ARRAY(SELECT o.crop_image_path FROM ocr_digits o WHERE o.sheet_id = a.sheet_id AND o.crop_image_path IS NOT NULL) AS cat "
        "FROM answer_sheets a JOIN exams e USING (exam_id) "
        "LEFT JOIN results r ON r.sheet_id = a.sheet_id AND r.status <> 'void' "
        "WHERE a.image_deleted_at IS NULL AND (a.status = 'rejected' OR (a.status = 'graded' AND r.result_id IS NOT NULL)) "
        "AND GREATEST(a.updated_at, COALESCE(r.updated_at, a.updated_at)) <= %(moc)s "
        "AND (NOT %(giu_demo)s OR e.exam_title NOT LIKE '%%[DEMO%%') "
        "AND (%(kt)s::bigint[] IS NULL OR a.exam_id = ANY(%(kt)s::bigint[])) "
        "ORDER BY a.sheet_id LIMIT %(n)s", {"moc": moc, "giu_demo": cfg.anh_giu_demo, "n": gioi_han, "kt": ky_thi}).fetchall()
    return [{"sheet_id": r["sheet_id"], "exam_id": r["exam_id"], "status": r["status"], "moc": r["moc"],
             "tep": [p for p in (r["image_path"], r["aligned_image_path"], *r["cat"]) if p]} for r in rows]


def xoa_tep(storage_dir: Path, tep: list[str]) -> tuple[int, list[str]]:
    """Xoá các tệp (đường dẫn tương đối) NẰM TRONG storage_dir. Trả (số tệp đã xoá, các đường dẫn bị TỪ CHỐI vì ra ngoài storage_dir).
    Tệp không còn -> bỏ qua (không lỗi). Không xoá thư mục."""
    goc = storage_dir.resolve()
    da_xoa, tu_choi = 0, []
    for rel in tep:
        p = (goc / rel).resolve()
        if goc not in p.parents:
            tu_choi.append(rel)
            continue
        try:
            p.unlink()
            da_xoa += 1
        except FileNotFoundError:
            pass
    return da_xoa, tu_choi


def don(conn, cfg: CauHinh, bay_gio: datetime | None = None, ap_dung: bool = True, ky_thi: list[int] | None = None) -> dict:
    """Một lượt dọn. ap_dung=False: chỉ liệt kê. KHÔNG commit (người gọi quyết). Phiếu có tệp bị từ chối KHÔNG được đánh dấu đã xoá."""
    ds = phieu_can_xoa(conn, cfg, bay_gio, ky_thi=ky_thi)
    tong = {"phieu": len(ds), "tep_xoa": 0, "tu_choi": [], "phieu_danh_dau": 0}
    if not ap_dung:
        return tong | {"ds": ds}
    for p in ds:
        n, tc = xoa_tep(cfg.storage_dir, p["tep"])
        tong["tep_xoa"] += n
        if tc:
            tong["tu_choi"] += tc
            log.warning("Phiếu %s: bỏ qua %d đường dẫn nằm ngoài thư mục lưu trữ: %s", p["sheet_id"], len(tc), tc)
            continue
        conn.execute("UPDATE answer_sheets SET image_deleted_at = now() WHERE sheet_id = %s AND image_deleted_at IS NULL", (p["sheet_id"],))
        tong["phieu_danh_dau"] += 1
    return tong


def chay_mot_luot(cfg: CauHinh) -> dict | None:
    from .db import ket_noi
    with ket_noi() as conn:
        if not da_co_cot(conn):
            log.warning("Dọn ảnh tạm: CSDL chưa áp migration 003 (thiếu answer_sheets.image_deleted_at) – bỏ qua. Chạy: python -m backend.migrate")
            return None
        kq = don(conn, cfg)
        conn.commit()
    log.info("Dọn ảnh tạm: %d phiếu, xoá %d tệp (giữ %g giờ sau khi chốt)", kq["phieu_danh_dau"], kq["tep_xoa"], cfg.anh_giu_gio)
    return kq


class LuongDon:
    """Luồng nền nhẹ: một lượt ngay khi khởi động rồi mỗi CHU_KY_GIAY. Lỗi một lượt chỉ ghi log, không làm sập máy chủ."""

    def __init__(self, cfg: CauHinh, chu_ky: float = CHU_KY_GIAY):
        self.cfg, self.chu_ky, self.dung = cfg, chu_ky, threading.Event()
        self.t = threading.Thread(target=self._chay, name="don_anh_tam", daemon=True)

    def _chay(self) -> None:
        while not self.dung.is_set():
            try:
                chay_mot_luot(self.cfg)
            except Exception:  # noqa: BLE001
                log.exception("Dọn ảnh tạm lỗi (bỏ qua lượt này)")
            self.dung.wait(self.chu_ky)

    def bat(self) -> "LuongDon":
        self.t.start()
        return self

    def tat(self) -> None:
        self.dung.set()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap-dung", action="store_true", help="xoá thật (mặc định chỉ xem trước)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from .config import lay_cau_hinh
    from .db import ket_noi
    cfg = lay_cau_hinh()
    with ket_noi() as conn:
        if not da_co_cot(conn):
            print("CSDL chưa áp migration 003 – chạy python -m backend.migrate trước.")
            return 1
        if not a.ap_dung:
            conn.execute("SET TRANSACTION READ ONLY")
        kq = don(conn, cfg, ap_dung=a.ap_dung)
        conn.commit() if a.ap_dung else conn.rollback()
    print(f"Giữ ảnh {cfg.anh_giu_gio:g} giờ sau khi chốt; giữ kỳ thi [DEMO…]: {'có' if cfg.anh_giu_demo else 'không'}; thư mục {cfg.storage_dir}")
    if a.ap_dung:
        print(f"ĐÃ XOÁ: {kq['tep_xoa']} tệp của {kq['phieu_danh_dau']} phiếu" + (f"; từ chối {len(kq['tu_choi'])} đường dẫn ngoài thư mục" if kq["tu_choi"] else ""))
    else:
        for p in kq["ds"]:
            print(f"  phiếu {p['sheet_id']} (kỳ thi {p['exam_id']}, {p['status']}, chốt {p['moc']:%d/%m %H:%M}): {len(p['tep'])} tệp")
        print(f"XEM TRƯỚC: {kq['phieu']} phiếu. Thêm --ap-dung để xoá.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
