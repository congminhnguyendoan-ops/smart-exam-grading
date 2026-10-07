"""
nap_demo.py - Nạp dữ liệu mẫu cho demo backend: kỳ thi "[DEMO] ..." + 4 mã đề + đáp án giả lập + 28 thí sinh DEMO (SBD viết tay của
phiếu 0001–0028 trong data/ground_truth.csv). CHẠY LẠI ĐƯỢC (không nhân đôi, không ghi đè); không xoá gì. Xem backend/demo.py.

  python tools/nap_demo.py            # từ smart_exam_db/ ; cần .env (DATABASE_URL) và đã chạy: python -m backend.migrate
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import demo, service  # noqa: E402
from backend.config import lay_cau_hinh  # noqa: E402
from backend.db import giao_dich  # noqa: E402


def main() -> None:
    cfg = lay_cau_hinh()
    with giao_dich() as conn:
        kq = demo.nap_demo(conn, service.lay_nguoi_dung(conn, cfg.nguoi_dung_demo))
    print(("Đã tạo" if kq["ky_thi_moi"] else "Đã có sẵn") + f" kỳ thi DEMO exam_id = {kq['exam_id']}; "
          f"thí sinh DEMO mới {kq['thi_sinh_moi']}/{kq['thi_sinh']}.")
    print(f"Tải ảnh thử:  curl -F file=@data/raw/0002_C2.jpg http://127.0.0.1:8000/exams/{kq['exam_id']}/sheets")


if __name__ == "__main__":
    main()
