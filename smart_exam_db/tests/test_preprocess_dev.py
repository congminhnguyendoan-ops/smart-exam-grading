"""preprocess() trên 7 ảnh dev đại diện: ok, huong_xoay, anh_nan / anh_chuan_hoa giống tham chiếu (hồi quy theo vân tay
v4 / v5 – tools/tao_tham_chieu.py). Kèm: preprocess_anh(gray) cho kết quả y hệt preprocess(path)."""
import numpy as np
import pytest
from conftest import DATA, THAM_CHIEU, can_file, so_voi_tham_chieu

from cv_engine.preprocessing import (CACH_MAC_DINH, MA_LY_DO, doc_anh, nap_layout, normalize, preprocess,
                                     preprocess_anh)
from cv_engine.tap_du_lieu import tap_cua

ANH = ["0001_C1", "0005_C2", "0015_C3", "0032_C4", "0006_C2", "0014_C2", "D003"]


def duong_dan(ten: str):
    return DATA / ("raw_digits" if ten.startswith("D") else "raw") / f"{ten}.jpg"


@pytest.mark.parametrize("ten", ANH)
def test_anh_dev_dai_dien(ten, tham_chieu):
    assert tap_cua(ten) == "dev"
    ref = tham_chieu["anh"][ten]
    can_file(duong_dan(ten), THAM_CHIEU / f"{ten}_anh_nan.png")
    layout = nap_layout(ref["loai"])
    kq = preprocess(duong_dan(ten), layout)
    assert kq.ok and kq.ly_do == ""
    assert kq.huong_xoay == ref["huong_xoay"]
    assert kq.anh_nan.shape == tuple(layout["page_px"][::-1]) == kq.anh_chuan_hoa.shape
    assert kq.marker.shape == (4, 2) and kq.blur_score is not None
    so_voi_tham_chieu(kq.anh_nan, f"{ten}_anh_nan.png", ref["sha256_anh_nan"], tham_chieu["cung_phien_ban"])
    so_voi_tham_chieu(kq.anh_chuan_hoa, f"{ten}_anh_chuan_hoa.png", ref["sha256_anh_chuan_hoa"],
                      tham_chieu["cung_phien_ban"])


def test_preprocess_anh_giong_preprocess():
    p = duong_dan("0001_C1")
    can_file(p)
    layout = nap_layout("phieu")
    gray, exif = doc_anh(p)
    a, b = preprocess(p, layout), preprocess_anh(gray, layout, exif)
    assert a.ok and b.ok and (a.ly_do, a.huong_xoay, a.exif_orientation) == (b.ly_do, b.huong_xoay, b.exif_orientation)
    assert np.array_equal(a.anh_nan, b.anh_nan) and np.array_equal(a.anh_chuan_hoa, b.anh_chuan_hoa)
    assert np.array_equal(a.marker, b.marker)
    assert np.array_equal(a.anh_chuan_hoa, normalize(a.anh_nan, layout, CACH_MAC_DINH))


def test_api_co_dinh():
    assert set(MA_LY_DO) == {"khong_doc_duoc", "thieu_marker", "marker_khong_dat", "nhieu_phieu", "marker_mo_ho",
                             "marker_cham_mep", "anh_mo", "khong_khop_bo_cuc", "khong_ro_chieu"}
    assert all(MA_LY_DO.values())
    for loai in ("phieu", "chu_so"):
        assert nap_layout(loai)["page_px"] == [2480, 3508]
