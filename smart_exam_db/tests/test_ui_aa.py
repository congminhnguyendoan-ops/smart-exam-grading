"""Lệnh AA (giao diện sau bảo vệ, nhánh ui-sau-bv): duyệt SBD / mã đề nhanh hơn (lỗi tại ô, phiếu kế tiếp, phím tắt), hướng dẫn chụp trên /m.
Chỉ kiểm tệp tĩnh + logic JS (node:test) – không cần CSDL."""
import re
import shutil
import subprocess

import pytest

from conftest import ROOT

FRONTEND = ROOT / "frontend"


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để chạy test JS")
def test_duyet_dinh_danh_node():
    """tests/js/duyet_dinh_danh.test.js: lỗi tại ô SBD / mã đề + gợi ý, xác nhận trước khi lưu, phiếu kế tiếp, phím tắt (6 test)."""
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "duyet_dinh_danh.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"pass 6\b", r.stdout) and re.search(r"fail 0\b", r.stdout), r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để kiểm cú pháp JS")
def test_duyet_dinh_danh_cu_phap():
    r = subprocess.run(["node", "--check", str(FRONTEND / "duyet_dinh_danh.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
