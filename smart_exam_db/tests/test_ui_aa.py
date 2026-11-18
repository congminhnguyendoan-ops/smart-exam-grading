import re
import shutil
import subprocess

import pytest

from conftest import ROOT

FRONTEND = ROOT / "frontend"


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để chạy test JS")
def test_duyet_dinh_danh_node():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "duyet_dinh_danh.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"pass 6\b", r.stdout) and re.search(r"fail 0\b", r.stdout), r.stdout


def test_man_duyet_noi_logic_moi_khong_doi_id_cu():
    h = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert h.index('src="duyet_dinh_danh.js"') < h.index('src="app.js"')
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    for s in ("DuyetDinhDanh.kiemSbd(", "DuyetDinhDanh.kiemMaDe(", "DuyetDinhDanh.canXacNhan(", "DuyetDinhDanh.chanLuu(", "DuyetDinhDanh.phim(",
              "DuyetDinhDanh.keTiep(", "DuyetDinhDanh.cotCanNhin", 'id="in-sbd"', 'id="in-ma"', 'id="luu-dd"', "data-fill=", '"ke-tiep"', '"ke-tiep-sau-luu"',
              'id="bao-sbd"', 'id="bao-ma"', "<kbd>Enter</kbd>"):
        assert s in js, s
    assert re.search(r"if \(hoi\.length && !confirm\(", js)
    assert js.count("put(`/sheets/${id}/identity`") == 1


def test_m_co_huong_dan_chup_thang_thu_gon_duoc():
    html = (FRONTEND / "m.html").read_text(encoding="utf-8")
    khoi = re.search(r'<details id="hd-chup"[^>]*>.*?</details>', html, re.S).group(0)
    assert html.index('id="v-cap"') < html.index('id="hd-chup"') < html.index('id="ds-to"')
    assert "open" not in khoi.split(">")[0]
    for y in ("song song với tờ giấy", "4 ô vuông đen", "Đủ sáng, không bóng đổ", "Viết chữ số rõ trong ô"):
        assert y in khoi, y
    assert "hd-chup" not in (FRONTEND / "m.js").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để kiểm cú pháp JS")
@pytest.mark.parametrize("ten", ["duyet_dinh_danh.js", "chon_tep.js"])
def test_duyet_dinh_danh_cu_phap(ten):
    r = subprocess.run(["node", "--check", str(FRONTEND / ten)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để chạy test JS")
def test_chon_tep_node():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "chon_tep.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"pass 2\b", r.stdout) and re.search(r"fail 0\b", r.stdout), r.stdout


def test_o_chon_tep_tieng_viet_giu_keo_tha_va_chon_nhieu():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    o = re.search(r'<label class="chon-tep[^"]*">(<input[^>]*>)📁 Chọn ảnh</label>', js)
    assert o and 'type="file"' in o.group(1) and 'id="files"' in o.group(1) and "multiple" in o.group(1)
    assert js.count("moTaTepChon(") >= 2 and 'drop.addEventListener("drop"' in js and 'addEventListener("change", (e) => dat(e.target.files))' in js
    h = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert h.index('src="ten_tep.js"') < h.index('src="chon_tep.js"') < h.index('src="app.js"')
    css = (FRONTEND / "style.css").read_text(encoding="utf-8")
    an = css[css.index(".chon-tep input{"):css.index("}", css.index(".chon-tep input{"))]
    assert "opacity:0" in an and "display:none" not in an
