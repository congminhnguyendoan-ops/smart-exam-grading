"""
sao_luu_demo.py - Lệnh U (30/10/2026): sao lưu TOÀN BỘ CSDL trước buổi demo bằng pg_dump -Fc (chỉ ĐỌC CSDL, ghi một tệp .dump).

  python tools/sao_luu_demo.py            # -> data/_backup/smart_exam_<YYYYmmdd_HHMMSS>_demo.dump, rồi kiểm bằng pg_restore -l
  python tools/sao_luu_demo.py --chi-in   # chỉ in lệnh sẽ chạy (không chạy)

Thông tin kết nối lấy từ DATABASE_URL (.env). Mật khẩu chỉ truyền cho pg_dump qua biến môi trường PGPASSWORD của TIẾN TRÌNH CON – không nằm trên
dòng lệnh, không in ra màn hình. Lệnh khôi phục: docs/kich_ban_demo.md (mục "Sao lưu / khôi phục").
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

THU_MUC = ROOT / "data" / "_backup"


def tim_cong_cu(ten: str) -> str | None:
    """pg_dump / pg_restore: trong PATH, không thì bản PostgreSQL mới nhất ở C:\\Program Files\\PostgreSQL\\<bản>\\bin."""
    p = shutil.which(ten)
    if p:
        return p
    ds = sorted(glob.glob(rf"C:\Program Files\PostgreSQL\*\bin\{ten}.exe"), key=lambda x: int(Path(x).parts[-3]) if Path(x).parts[-3].isdigit() else 0)
    return ds[-1] if ds else None


def tach_url(url: str) -> dict:
    """postgresql://user:mk@host:port/db -> {host, port, user, db, mat_khau}."""
    u = urlsplit(url)
    if u.scheme not in ("postgresql", "postgres") or not u.path.strip("/"):
        raise SystemExit("DỪNG: DATABASE_URL không đúng dạng postgresql://user:mật-khẩu@host:cổng/tên-csdl (không in giá trị).")
    return {"host": u.hostname or "localhost", "port": str(u.port or 5432), "user": unquote(u.username or ""), "db": u.path.strip("/"),
            "mat_khau": unquote(u.password) if u.password else None}


def lenh_dump(pg_dump: str, k: dict, ra: Path) -> list[str]:
    return [pg_dump, "-Fc", "-h", k["host"], "-p", k["port"], "-U", k["user"], "-d", k["db"], "-f", str(ra)]


def lenh_khoi_phuc(k: dict, tep: str = "<tệp .dump>") -> str:
    pr = tim_cong_cu("pg_restore") or "pg_restore"
    return f'& "{pr}" -h {k["host"]} -p {k["port"]} -U {k["user"]} -d {k["db"]} --clean --if-exists --no-owner "{tep}"'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chi-in", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from backend.config import lay_database_url
    k = tach_url(lay_database_url())
    pg_dump = tim_cong_cu("pg_dump")
    if not pg_dump:
        print("DỪNG: không thấy pg_dump (PATH hoặc C:\\Program Files\\PostgreSQL\\<bản>\\bin).")
        return 2
    ra = THU_MUC / f"smart_exam_{datetime.now():%Y%m%d_%H%M%S}_demo.dump"
    lenh = lenh_dump(pg_dump, k, ra)
    print("Lệnh (mật khẩu truyền qua PGPASSWORD, không in):", " ".join(f'"{x}"' if " " in x else x for x in lenh))
    if a.chi_in:
        print("Khôi phục (GHI ĐÈ CSDL – chỉ chạy khi đã quyết):", lenh_khoi_phuc(k))
        return 0
    THU_MUC.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if k["mat_khau"] is not None:
        env["PGPASSWORD"] = k["mat_khau"]
    r = subprocess.run(lenh, env=env, capture_output=True, text=True)
    if r.returncode != 0 or not ra.is_file():
        print("LỖI pg_dump:", (r.stderr or "").replace(k["mat_khau"] or "\0", "***")[:500])
        return 3
    pr = tim_cong_cu("pg_restore")
    muc = None
    if pr:
        rl = subprocess.run([pr, "-l", str(ra)], capture_output=True, text=True)
        muc = sum(1 for d in rl.stdout.splitlines() if d.strip() and not d.startswith(";")) if rl.returncode == 0 else None
    print(f"ĐÃ SAO LƯU: {ra} ({ra.stat().st_size / 1024 ** 2:.1f} MB)" + (f"; pg_restore -l đọc được {muc} mục" if muc else "; CHƯA kiểm được bằng pg_restore -l"))
    print("Khôi phục (GHI ĐÈ CSDL – chỉ chạy khi đã quyết; nhập mật khẩu khi được hỏi):")
    print("  " + lenh_khoi_phuc(k, str(ra)))
    return 0 if muc else 4


if __name__ == "__main__":
    sys.exit(main())
