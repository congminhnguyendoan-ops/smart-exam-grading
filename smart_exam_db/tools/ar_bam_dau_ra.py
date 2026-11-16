"""ar_bam_dau_ra.py - Lệnh AR: băm đầu ra chấm lại 56 ảnh dev (data/_eval/backend/phieu_dau_cuoi.csv do tools/kiem_backend_dau_cuoi.py ghi),
BỎ cột sheet_id (số tự tăng, khác mỗi lần chạy). Hai lần chạy cho điểm / SBD / mã đề / cờ giống hệt nhau thì băm giống nhau.
  python tools/ar_bam_dau_ra.py            # in SHA-256 + số dòng
"""
import csv
import hashlib
import sys
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "_eval" / "backend" / "phieu_dau_cuoi.csv"


def bam(duong_dan: Path = CSV) -> tuple[str, int]:
    with duong_dan.open(encoding="utf-8", newline="") as f:
        dong = list(csv.DictReader(f))
    h = hashlib.sha256()
    for r in dong:
        h.update("|".join(f"{k}={r[k]}" for k in r if k != "sheet_id").encode("utf-8") + b"\n")
    return h.hexdigest(), len(dong)


if __name__ == "__main__":
    sha, n = bam()
    print(f"{sha}  ({n} dòng, bỏ cột sheet_id)")
    sys.exit(0)
