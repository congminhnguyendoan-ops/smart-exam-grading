"""
migrate.py - Chạy các file backend/migrations/*.sql theo thứ tự tên; ghi vào bảng schema_migrations. Chạy lại an toàn:
mọi file đều idempotent (IF NOT EXISTS), nên áp lại cũng không hỏng gì. KHÔNG xoá / reset CSDL.

  python -m backend.migrate            # áp các migration chưa áp
  python -m backend.migrate --kiem     # chỉ liệt kê đã áp / chưa áp
"""
import argparse
import sys
from pathlib import Path

from .db import ket_noi

THU_MUC = Path(__file__).resolve().parent / "migrations"


def ds_file() -> list[Path]:
    return sorted(THU_MUC.glob("*.sql"))


def da_ap(conn) -> set[str]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                 "(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
    return {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}


def ap_dung(conn=None) -> list[str]:
    """Áp các migration chưa áp, mỗi file một giao dịch. Trả danh sách file vừa áp."""
    own = conn is None
    conn = conn or ket_noi()
    try:
        xong = da_ap(conn)
        conn.commit()
        moi = []
        for f in ds_file():
            if f.name in xong:
                continue
            conn.execute(f.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (f.name,))
            conn.commit()
            moi.append(f.name)
        return moi
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Áp migration bổ sung cho backend")
    ap.add_argument("--kiem", action="store_true")
    a = ap.parse_args()
    with ket_noi() as conn:
        xong = da_ap(conn)
        conn.commit()
        if a.kiem:
            for f in ds_file():
                print(("ĐÃ ÁP   " if f.name in xong else "CHƯA ÁP ") + f.name)
            return
        moi = ap_dung(conn)
        print("Đã áp: " + ", ".join(moi) if moi else "Không có migration mới (đã áp hết).")


if __name__ == "__main__":
    sys.exit(main())
