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
