import argparse
import sys
from pathlib import Path

from .db import ket_noi

THU_MUC = Path(__file__).resolve().parent / "migrations"
TUY_CHON = {"003_xoa_anh_tam.sql"}


def ds_file() -> list[Path]:
    return sorted(THU_MUC.glob("*.sql"))


def chua_ap(conn, ca_tuy_chon: bool = False) -> list[str]:
    co = conn.execute("SELECT to_regclass('schema_migrations') AS t").fetchone()["t"]
    xong = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations").fetchall()} if co else set()
    return [f.name for f in ds_file() if f.name not in xong and (ca_tuy_chon or f.name not in TUY_CHON)]


def da_ap(conn) -> set[str]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                 "(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
    return {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}


def ap_dung(conn=None) -> list[str]:
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
