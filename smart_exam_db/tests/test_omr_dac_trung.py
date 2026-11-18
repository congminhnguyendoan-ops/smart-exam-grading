import sys

import numpy as np
import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402


@pytest.fixture(scope="module")
def layout():
    return nap_layout("phieu")


def test_phieu_trang_dung_san_thang(layout):
    mau = omr.nap_mau()
    dv = omr.dinh_vi(mau, layout, mau)
    assert not any(dv.co.values())
    cau, bub, S = omr.dac_trung_o(mau, layout, dv)
    assert cau.shape == (40, 4, len(omr.TEN_DAC_TRUNG)) and bub.shape == (9, 10, len(omr.TEN_DAC_TRUNG))
    assert S == omr.S_SAN
    i = omr.TEN_DAC_TRUNG.index("ld_anh")
    assert cau[..., i].max() < 0.25 and bub[..., i].max() < 0.25


def test_o_to_ro_toi_nhat(layout):
    can_file(ROOT / "data" / "raw" / "0001_C1.jpg", ROOT / "data" / "split.csv")
    from omr_du_lieu import anh_da_nan
    nan, _ = anh_da_nan("0001_C1", layout)
    cau, bub, S = omr.dac_trung_o(nan, layout, omr.dinh_vi(nan, layout))
    assert np.isfinite(cau).all() and np.isfinite(bub).all()
    ld = cau[1, :, omr.TEN_DAC_TRUNG.index("ld")]
    assert int(np.argmax(ld)) == 0 and cau[1, 0, omr.TEN_DAC_TRUNG.index("hang")] == 0
    assert 0.3 < S < 1.0
