import re

from conftest import ROOT
from test_backend_api import anh_trang, tai, tao_de


def test_f3_so_phieu_o_chon_ky_thi_khop_so_phieu_sau_khi_tai(client):
    eid = tao_de(client, n=10, ma_de=("101",))
    ds = lambda: next(e for e in client.get("/exams").json() if e["exam_id"] == eid)       # noqa: E731
    assert ds()["so_phieu"] == 0 and client.get(f"/exams/{eid}").json()["sheets"]["tong"] == 0
    assert tai(client, eid, "trang", du_lieu=anh_trang()).status_code == 201
    assert ds()["so_phieu"] == 1 and client.get(f"/exams/{eid}").json()["sheets"]["tong"] == 1


def test_f3_giao_dien_lam_moi_nhan_ky_thi_moi_lan_nap_chi_tiet():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "function lamMoiNhanKyThi" in js and "const nhanKyThi" in js
    nap = js[js.index("async function napChiTietKyThi"):]
    nap = nap[:nap.index("\n}\n")]
    assert "lamMoiNhanKyThi(e)" in nap
    assert js.count("await napChiTietKyThi()") >= 4


def test_f4_m_js_luu_sieu_du_lieu_o_session_storage_khong_token_khong_anh():
    bo_cmt = lambda p: re.sub(r"/\*.*?\*/|^\s*//.*$", "", (ROOT / "frontend" / p).read_text(encoding="utf-8"), flags=re.S | re.M)   # noqa: E731
    js = bo_cmt("m.js")
    assert 'KHOA_PHIEN = "m_hang_doi"' in js and "sessionStorage.setItem(KHOA_PHIEN" in js and "khoiPhucPhien" in js
    luu = js[js.index("function luuPhien"):js.index("async function traCuuPhieu")]
    assert "xuatSieuDuLieu()" in luu and "token" not in luu.lower() and ".file" not in luu
    assert "localStorage" not in js
    assert "removeItem(KHOA_PHIEN)" in js
    assert "/sheets/${id}" in js


def test_g2_ten_tep_node_va_gan_dung_cho():
    import shutil
    import subprocess
    import pytest
    if shutil.which("node") is None:
        pytest.skip("không có node")
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "ten_tep.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and re.search(r"pass 5\b", r.stdout), r.stdout + r.stderr
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    m = (ROOT / "frontend" / "m.js").read_text(encoding="utf-8")
    assert "esc(p.original_filename)" not in app and "esc(f.name)" not in app
    assert app.count("tenTepHtml(") >= 6 and m.count("tenTepHtml(") >= 2
    for html, ref in (("index.html", 'src="ten_tep.js"'), ("m.html", 'src="/app/ten_tep.js"')):
        h = (ROOT / "frontend" / html).read_text(encoding="utf-8")
        assert ref in h and h.index("ten_tep.js") < h.index("app.js" if html == "index.html" else "m.js")
