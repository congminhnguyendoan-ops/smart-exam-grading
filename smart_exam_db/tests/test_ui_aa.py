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


def test_man_duyet_noi_logic_moi_khong_doi_id_cu():
    """index.html nạp duyet_dinh_danh.js TRƯỚC app.js; app.js dùng đủ các hàm (lỗi tại ô, xác nhận, phím tắt, phiếu kế tiếp);
    các id cũ mà test / công cụ dựa vào vẫn còn (in-sbd, in-ma, luu-dd, data-fill)."""
    h = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert h.index('src="duyet_dinh_danh.js"') < h.index('src="app.js"')
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    for s in ("DuyetDinhDanh.kiemSbd(", "DuyetDinhDanh.kiemMaDe(", "DuyetDinhDanh.canXacNhan(", "DuyetDinhDanh.chanLuu(", "DuyetDinhDanh.phim(",
              "DuyetDinhDanh.keTiep(", "DuyetDinhDanh.cotCanNhin", 'id="in-sbd"', 'id="in-ma"', 'id="luu-dd"', "data-fill=", '"ke-tiep"', '"ke-tiep-sau-luu"',
              'id="bao-sbd"', 'id="bao-ma"', "<kbd>Enter</kbd>"):
        assert s in js, s
    # Máy không tự chọn: lưu CHỈ khi giáo viên bấm nút / Enter; cảnh báo phải qua confirm()
    assert re.search(r"if \(hoi\.length && !confirm\(", js)
    assert js.count("put(`/sheets/${id}/identity`") == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để kiểm cú pháp JS")
def test_duyet_dinh_danh_cu_phap():
    r = subprocess.run(["node", "--check", str(FRONTEND / "duyet_dinh_danh.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
