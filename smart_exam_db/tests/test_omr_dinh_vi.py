import hashlib
import json
import sys

import numpy as np
import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402

PX_MM = 25.4 / 300


@pytest.fixture(scope="module")
def layout():
    return nap_layout("phieu")


def test_mau_png_khop_sha(layout):
    mau = omr.nap_mau(kiem_sha=False)
    meta = json.loads(omr.MAU_PNG.with_suffix(".json").read_text(encoding="utf-8"))
    assert mau.shape == (layout["page_px"][1], layout["page_px"][0])
    assert hashlib.sha256(mau.tobytes()).hexdigest() == meta["sha256_diem_anh"]


def test_lech_lan_can_theo_duong_thang():
    deu = [(0.0, 5.0 * i) for i in range(10)]
    assert max(omr._lech_lan_can(deu, i, 3) for i in range(10)) < 1e-6
    nhay = list(deu)
    nhay[4] = (0.0, nhay[4][1] + 12.0)
    assert omr._lech_lan_can(nhay, 4, 3) > omr.mm_px(nap_layout("phieu"), omr.LAN_CAN_MM)


def _anh(ten, layout):
    can_file(ROOT / "data" / "raw" / f"{ten}.jpg", ROOT / "data" / "split.csv")
    from omr_du_lieu import anh_da_nan
    return anh_da_nan(ten, layout)[0]


def test_giay_cong_0014_C2(layout):
    kq = omr.dinh_vi(_anh("0014_C2", layout), layout)
    assert not any(kq.co.values()), {k: v for k, v in kq.co.items() if v}
    dx, dy = np.array(kq.dich["q10"]) * PX_MM
    assert abs(dx + 2.62) < 0.3 and abs(dy - 3.39) < 0.3


@pytest.mark.parametrize("dx,dy", [(7, 0), (-7, 0), (0, 11), (0, 5.8), (0, -5.8)])
def test_dich_dung_mot_khoang_cach_o(layout, dx, dy):
    from kiem_dinh_vi import dich_anh
    anh = _anh("0001_C1", layout)
    goc = omr.dinh_vi(anh, layout)
    kq = omr.dinh_vi(dich_anh(anh, dx, dy), layout)
    for key in kq.dich:
        mong = np.array(goc.dich[key]) + np.array([dx, dy]) / PX_MM
        dung = np.abs(np.array(kq.dich[key]) - mong).max() * PX_MM <= 0.5
        assert dung or kq.co[key], f"{key}: khớp nhầm không cờ khi dịch ({dx}, {dy}) mm"


def test_dich_nho_dung_khong_co(layout):
    from kiem_dinh_vi import dich_anh
    anh = _anh("0001_C1", layout)
    goc = omr.dinh_vi(anh, layout)
    kq = omr.dinh_vi(dich_anh(anh, 2, -2), layout)
    for key in kq.dich:
        assert not kq.co[key]
        assert np.abs(np.array(kq.dich[key]) - np.array(goc.dich[key]) - np.array([2, -2]) / PX_MM).max() * PX_MM <= 0.5


def test_anh_sai_co_bi_tu_choi(layout):
    with pytest.raises(ValueError):
        omr.dinh_vi(np.zeros((100, 100), np.uint8), layout)


def test_split_rang_buoc():
    can_file(ROOT / "data" / "raw", ROOT / "data" / "ground_truth.csv", ROOT / "data" / "split.csv")
    import tao_split
    nd = tao_split.tao_noi_dung(ROOT / "data" / "raw", ROOT / "data" / "ground_truth.csv")
    assert tao_split.kiem_rang_buoc(nd) == []
    assert (ROOT / "data" / "split.csv").read_text(encoding="utf-8") == nd


def test_phan_a_chan_val_va_test():
    can_file(ROOT / "data" / "split.csv")
    import omr_du_lieu
    from cv_engine.tap_du_lieu import ChamTapTest
    with pytest.raises(omr_du_lieu.ChamTapVal):
        omr_du_lieu.ds_anh("val")
    with pytest.raises(ValueError):
        omr_du_lieu.ds_anh("test")
    with pytest.raises(ChamTapTest):
        omr_du_lieu.anh_da_nan("0035_C1", {})
    assert {int(r["phieu"]) for r in omr_du_lieu.ds_anh("train")} == set(range(1, 29))
