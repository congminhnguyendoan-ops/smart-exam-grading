"""Lệnh AA phần B: bảng màu chung (frontend/mau.css) – tương phản đạt WCAG, mọi màu chỉ ở một chỗ, trạng thái luôn kèm chữ. Không cần CSDL."""
import re
import sys

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import kiem_tuong_phan as K  # noqa: E402

FRONTEND = ROOT / "frontend"
bo_cmt = lambda s: re.sub(r"/\*.*?\*/", "", s, flags=re.S)  # noqa: E731


def test_cong_thuc_tuong_phan_dung_moc_wcag():
    assert round(K.ty_le("#000000", "#FFFFFF"), 2) == 21.0
    assert round(K.ty_le("#FFFFFF", "#FFFFFF"), 2) == 1.0
    assert round(K.ty_le("#767676", "#FFFFFF"), 2) == 4.54                 # mốc quen thuộc: xám nhạt nhất đạt 4,5:1 trên trắng


def test_moi_cap_mau_chinh_dat_nguong():
    ds = K.bang()
    hong = [f"{d['chu']}/{d['nen']} {d['ty_le']}:1 < {d['nguong']}:1" for d in ds if not d["dat"]]
    assert not hong, hong
    assert len(ds) == len(K.CAP) >= 30


def test_mau_chi_dinh_nghia_o_mau_css_va_bien_nao_cung_co():
    bien = set(re.findall(r"(--[\w-]+)\s*:", (FRONTEND / "mau.css").read_text(encoding="utf-8")))
    for ten in ("style.css", "m.css"):
        css = bo_cmt((FRONTEND / ten).read_text(encoding="utf-8"))
        assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", css), f"{ten} còn mã màu viết cứng"
        assert not re.search(r"\brgba?\(", css), f"{ten} còn rgb()/rgba() viết cứng"
        assert ":root" not in css, f"{ten} tự định nghĩa biến – phải ở mau.css"
        dung = set(re.findall(r"var\((--[\w-]+)\)", css))
        assert dung <= bien, f"{ten} dùng biến không có trong mau.css: {dung - bien}"
    for ten in ("app.js", "quan_tri.js", "m.js"):
        assert not re.search(r"#[0-9A-Fa-f]{6}\b", bo_cmt((FRONTEND / ten).read_text(encoding="utf-8"))), ten


def test_vien_o_nhap_dat_3_1_va_vien_the_van_nhe():
    """Lệnh AB: input / select / textarea dùng --vien-o (≥ 3:1 với thẻ, nền trang, thanh bên); .card vẫn viền --line nhẹ."""
    ds = {(d["chu"], d["nen"]): d for d in K.bang()}
    for nen in ("--card", "--bg", "--side"):
        assert ds[("--vien-o", nen)]["dat"] and ds[("--vien-o", nen)]["ty_le"] >= 3.0, nen
    css = bo_cmt((FRONTEND / "style.css").read_text(encoding="utf-8"))
    for sel in ("input[type=text]{", ".login input,.formcol input{", "select,textarea{", ".exam-pick select{"):
        quy_tac = css[css.index(sel):css.index("}", css.index(sel))]
        assert "var(--vien-o)" in quy_tac and "var(--line)" not in quy_tac, sel
    the = css[css.index(".card{"):css.index("}", css.index(".card{"))]
    assert "border:1px solid var(--line)" in the
    m = bo_cmt((FRONTEND / "m.css").read_text(encoding="utf-8"))
    assert "var(--vien-o)" in m[m.index("input:not([type=file]){"):m.index("}", m.index("input:not([type=file]){"))]


def test_mau_css_nap_truoc_va_khong_che_do_toi():
    for html, mau, rieng in (("index.html", 'href="mau.css"', 'href="style.css"'), ("m.html", 'href="/app/mau.css"', 'href="/app/m.css"')):
        h = (FRONTEND / html).read_text(encoding="utf-8")
        assert h.index(mau) < h.index(rieng), html
    for ten in ("mau.css", "style.css", "m.css"):
        assert "prefers-color-scheme" not in (FRONTEND / ten).read_text(encoding="utf-8")
    m = (FRONTEND / "m.html").read_text(encoding="utf-8")
    assert re.search(r'name="theme-color" content="([^"]+)"', m).group(1).upper() == K.doc_bien()["--pri"]


def test_trang_thai_luon_kem_chu():
    """Chính thức / Cần xem / Bị từ chối: nhãn có chữ, không chỉ dựa vào màu (app.js NHAN_TRANG_THAI, NHAN_BD)."""
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    for chu, lop in (("Chính thức", "ok"), ("Cần xem", "warn"), ("Bị từ chối", "bad")):
        assert f'["{chu}", "{lop}"]' in js, chu
