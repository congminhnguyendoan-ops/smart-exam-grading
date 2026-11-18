import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("AUTH_MODE", "demo")
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
