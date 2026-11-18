import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để chạy test JS")
def test_duyet_nhanh_node():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "duyet_nhanh.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"(#|ℹ) pass 8\b", r.stdout), r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để kiểm cú pháp JS")
def test_cu_phap_js():
    for ten in ("duyet_nhanh.js", "app.js", "quan_tri.js"):
        r = subprocess.run(["node", "--check", str(FRONTEND / ten)], capture_output=True, text=True)
        assert r.returncode == 0, f"{ten}: {r.stderr}"


def test_index_nap_duyet_nhanh_truoc_app():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert html.index('src="duyet_nhanh.js"') < html.index('src="app.js"')


def test_hop_xac_nhan_khong_bam_san_va_khong_dung_sbd():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    i = js.index("function moXacNhanHangLoat")
    j = js.index("/* AF1: phím tắt", i)
    f = js[i:j]
    assert 'id="hl-ok" disabled' in f and 'id="hl-da-xem"' in f and '$("#hl-huy", dlg).focus()' in f
    assert "Không hoàn tác được" in f and "SBD / mã đề không bị thay đổi" in f
    assert "/questions/confirm-remaining" in f and "/identity" not in f and "sbd:" not in f and "exam_code:" not in f
    assert "hl.duoc.map((c) => c.question_no)" in f


def test_nhan_hanh_dong_nhat_ky():
    assert "xac_nhan_hang_loat:" in (FRONTEND / "quan_tri.js").read_text(encoding="utf-8")
