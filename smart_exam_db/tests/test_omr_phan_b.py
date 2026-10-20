"""Tuần 5 Phần B: nested CV (B1a), kiểm phép đo vị trí độc lập (B1b), HTML cần xem cần thiết (B1c). Cần data/ dev (tự SKIP nếu thiếu)."""
import sys

import numpy as np
import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "answer_sheet"))


def test_dem_cau_nested_khop_dem_phan_a():
    can_file(ROOT / "data" / "_omr" / "dac_trung_nan.csv", ROOT / "data" / "_omr" / "oof_cau_m1_nan.npy")
    import huan_luyen_omr as H
    import omr_long as N
    sel = [r for r in H.doc_dac_trung("nan") if r["loai"] == "cau"]
    P = np.load(H.OMR_DIR / "oof_cau_m1_nan.npy")
    luat = __import__("json").loads((H.OMR_DIR / "luat.json").read_text(encoding="utf-8"))["cau"]
    t = N.tong(N.dem_cau(sel, P, luat))
    d = H.mo_phong_cau(sel, P, luat)                          # bộ đếm gốc của Phần A phải trùng bộ đếm theo điều kiện
    assert (t["cau"], t["nang"], t["nhe"], t["thua"], t["ro_that"]) == (d["cau"], d["nang"], d["nhe"], d["thua"], d["ro_that"])


def test_phep_do_vi_tri_doc_lap_dung_voi_anh_dich_gia():
    can_file(ROOT / "data" / "_omr" / "anh" / "0002_C2_nan.png", ROOT / "answer_sheet" / "output" / "phieu_trang.pdf")
    import eval_omr as E
    import kiem_vi_tri_eval as K
    from cv_engine.preprocessing import nap_layout
    from omr_du_lieu import anh_da_nan
    L = nap_layout("phieu")
    px = 25.4 / L["dpi"]
    mau = E._mau_pdf(L)
    nan, _ = anh_da_nan("0002_C2", L)
    goc = E.vi_tri_doc_lap(nan, L, mau)
    for dx, dy in ((2.0, 0.0), (0.0, -3.5), (-3.0, 3.0)):
        m = E.vi_tri_doc_lap(K.dich_anh(nan, dx, dy, px), L, mau)
        sai = max(max(abs((m[k][0] - goc[k][0]) - dx), abs((m[k][1] - goc[k][1]) - dy)) for k in goc)
        assert sai <= K.SAI_SO_MM, (dx, dy, sai)
    with pytest.raises(RuntimeError):                          # dịch đúng 1 chu kỳ dọc (11 mm): eval phải DỪNG, không đo sai im lặng
        E.vi_tri_doc_lap(K.dich_anh(nan, 0.0, 11.0, px), L, mau)


def test_eval_omr_val_dung_mo_hinh_day_du_va_chan_test():
    import eval_omr as E
    src = (ROOT / "tools" / "eval_omr.py").read_text(encoding="utf-8")
    assert 'ROOT / "models" / f"omr_{pp}.json"' in src and "chi_can_thiet" in src
    with pytest.raises(SystemExit):
        E.ds_anh("test", True)
    with pytest.raises(SystemExit):
        E.ds_anh("val", False)
