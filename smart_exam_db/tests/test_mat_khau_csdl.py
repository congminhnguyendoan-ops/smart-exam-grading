"""Lệnh W1 – mật khẩu CSDL KHÔNG còn viết cứng trong script tạo CSDL (00_create_database.sql, run_all.bat, run_all.sh).
Script đọc SMART_EXAM_DB_PASSWORD (biến môi trường, hoặc dòng SMART_EXAM_DB_PASSWORD= trong smart_exam_db/.env); thiếu thì DỪNG trước mọi lệnh psql.

AN TOÀN: KHÔNG BAO GIỜ chạy run_all thật (nó DROP DATABASE). run_all.bat / .sh được CHÉP NGUYÊN BYTE sang thư mục tạm và `psql` được thay bằng
một stub chỉ ghi tham số. Chốt trong 00_create_database.sql chạy bằng psql thật với --single-transaction trên chính CSDL smart_exam: PostgreSQL từ chối
DROP DATABASE trong khối giao dịch (và không xoá được CSDL đang nối), nên kể cả khi chốt hỏng cũng không xoá được gì; test chỉ kiểm rằng chốt dừng TRƯỚC đó."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from conftest import ROOT

DB = ROOT / "database"
MAT_KHAU_CU = "smartexam" + "123"                       # tách chuỗi để chính tệp test không chứa mật khẩu cũ


def test_khong_con_mat_khau_cu_trong_ma():
    """Không tệp mã nào (database/, backend/, tools/, answer_sheet/, tests/, frontend/) còn mật khẩu cũ."""
    thay = []
    for thu_muc in ("database", "backend", "tools", "answer_sheet", "tests", "frontend"):
        for p in (ROOT / thu_muc).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".sql", ".bat", ".sh", ".js", ".html", ".ps1"} and ".venv" not in p.parts:
                if MAT_KHAU_CU in p.read_text(encoding="utf-8", errors="ignore"):
                    thay.append(str(p.relative_to(ROOT)))
    assert not thay, thay
    assert "SMART_EXAM_DB_PASSWORD" in (ROOT / ".env.example").read_text(encoding="utf-8")


def _stub(thu_muc: Path, ghi: Path) -> dict:
    """Thư mục tạm: database/ (bản chép run_all.*) + stub psql ghi tham số vào `ghi`."""
    (thu_muc / "database").mkdir(parents=True)
    shutil.copyfile(DB / "run_all.sh", thu_muc / "database" / "run_all.sh")                  # chép nguyên byte
    # run_all.bat: chép nguyên, CHỈ đổi "psql " đầu dòng -> "call psql ": stub là psql.bat, mà cmd gọi một .bat khác KHÔNG có `call` thì không
    # quay lại (psql thật là psql.exe nên tệp gốc không cần `call`). Kết thúc dòng giữ như trong repo.
    goc = (DB / "run_all.bat").read_bytes()
    (thu_muc / "database" / "run_all.bat").write_bytes(goc.replace(b"\npsql ", b"\ncall psql "))
    bin_ = thu_muc / "bin"
    bin_.mkdir()
    (bin_ / "psql.bat").write_text(f'@echo off\r\necho psql %*>>"{ghi}"\r\nexit /b 0\r\n', encoding="utf-8")
    (bin_ / "psql").write_text(f'#!/usr/bin/env bash\necho "psql $*" >> "{ghi.as_posix()}"\n', encoding="utf-8")
    os.chmod(bin_ / "psql", 0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("SMART_EXAM_DB_PASSWORD", "PGPASSWORD")}
    env["PATH"] = str(bin_) + os.pathsep + env["PATH"]
    return env


@pytest.mark.skipif(sys.platform != "win32", reason="run_all.bat chỉ chạy trên Windows")
@pytest.mark.parametrize("ca", ["thieu", "env_file", "bien_moi_truong"])
def test_run_all_bat(tmp_path, ca):
    ghi = tmp_path / "goi_psql.txt"
    env = _stub(tmp_path, ghi)
    if ca == "env_file":
        (tmp_path / ".env").write_text("# ghi chú\nDATABASE_URL=postgresql://x:y@h/d\nSMART_EXAM_DB_PASSWORD=Tu-Env-File-1\n", encoding="utf-8")
    if ca == "bien_moi_truong":
        (tmp_path / ".env").write_text("SMART_EXAM_DB_PASSWORD=khong-dung\n", encoding="utf-8")
        env["SMART_EXAM_DB_PASSWORD"] = "Bien-Moi-Truong-2"
    r = subprocess.run(["cmd", "/c", str(tmp_path / "database" / "run_all.bat")], cwd=tmp_path / "database", env=env,
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    out = r.stdout.decode("utf-8", "replace")
    if ca == "thieu":
        assert r.returncode == 1 and "LOI: chua co mat khau CSDL" in out and "SMART_EXAM_DB_PASSWORD" in out
        assert not ghi.exists(), "thiếu mật khẩu mà vẫn gọi psql"
        return
    mk = "Tu-Env-File-1" if ca == "env_file" else "Bien-Moi-Truong-2"
    goi = ghi.read_text(encoding="utf-8", errors="replace").splitlines()
    assert r.returncode == 0 and len(goi) == 6, out
    assert f'app_password="{mk}"' in goi[0] or f"app_password={mk}" in goi[0]
    assert MAT_KHAU_CU not in "".join(goi)


def _bash():
    """Git Bash trên Windows (bash.exe của WindowsApps là WSL, có thể không có bản phân phối); Linux / macOS: bash trên PATH."""
    if sys.platform == "win32":
        for p in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe", Path(r"C:\Program Files\Git\bin\bash.exe")):
            if p.exists():
                return str(p)
        return None
    return shutil.which("bash")


@pytest.mark.skipif(_bash() is None, reason="không có bash (Git Bash)")
@pytest.mark.parametrize("ca", ["thieu", "env_file"])
def test_run_all_sh(tmp_path, ca):
    ghi = tmp_path / "goi_psql.txt"
    env = _stub(tmp_path, ghi)
    if ca == "env_file":
        (tmp_path / ".env").write_bytes(b"DATABASE_URL=x\r\nSMART_EXAM_DB_PASSWORD=Sh-Env-3\r\n")       # .env kiểu Windows (CRLF)
    sh = (tmp_path / "database" / "run_all.sh").as_posix()
    bin_ = (tmp_path / "bin").as_posix()
    r = subprocess.run([_bash(), "-c", f'export PATH="{bin_}:$PATH"; unset SMART_EXAM_DB_PASSWORD; bash "{sh}"'], env=env,
                       capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    err = r.stderr.decode("utf-8", "replace")
    if ca == "thieu":
        assert r.returncode == 1 and "LỖI: chưa có mật khẩu CSDL" in err and not ghi.exists()
        return
    goi = ghi.read_text(encoding="utf-8").splitlines()
    assert r.returncode == 0 and len(goi) == 6, err
    assert "app_password=Sh-Env-3" in goi[0] and "\r" not in goi[0]


def _psql():
    p = shutil.which("psql") or r"C:\Program Files\PostgreSQL\17\bin\psql.exe"
    return p if Path(p).exists() else None


@pytest.mark.skipif(_psql() is None, reason="không có psql")
@pytest.mark.parametrize("bien, mau", [([], "thiếu mật khẩu"), (["-v", "app_password="], "division by zero")])
def test_chot_sql_dung_truoc_drop(bien, mau):
    """Chốt trong 00_create_database.sql: thiếu / rỗng mật khẩu -> lỗi NGAY, không tới DROP DATABASE (an toàn: --single-transaction, xem docstring)."""
    try:
        from backend.config import lay_database_url
        u = urlsplit(lay_database_url())
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"không đọc được DATABASE_URL: {e}")
    env = {**os.environ, "PGPASSWORD": unquote(u.password or ""), "PGCLIENTENCODING": "UTF8", "LC_MESSAGES": "C"}
    r = subprocess.run([_psql(), "-X", "-h", u.hostname or "localhost", "-p", str(u.port or 5432), "-U", unquote(u.username or ""),
                        "-d", u.path.lstrip("/"), "--single-transaction", "-v", "ON_ERROR_STOP=1", *bien, "-f", str(DB / "00_create_database.sql")],
                       env=env, capture_output=True, timeout=60)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert r.returncode != 0 and mau in out, out
    assert "DROP DATABASE" not in out and "transaction block" not in out, "chốt không dừng trước DROP DATABASE"
