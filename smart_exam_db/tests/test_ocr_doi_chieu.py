"""Đối chiếu hai kênh bubble ↔ viết tay (cv_engine/ocr.py: doi_chieu_cot / doi_chieu_truong). Hàm thuần, không đọc ảnh."""
import pytest

from cv_engine.ocr import doi_chieu_cot as c
from cv_engine.ocr import doi_chieu_truong as t


def test_khop_la_chac():
    r = c("3", False, "3", 0.9, True, False)
    assert r.chac and r.chu_so == "3" and r.ly_do == ()


def test_khop_nhung_cnn_khong_chac_van_nhan_neu_p_du():
    assert c("3", False, "3", 0.55, False, False).chac           # τ_khop 0,5: hai kênh độc lập cùng ra 3
    r = c("3", False, "3", 0.3, False, False)
    assert not r.chac and r.ly_do == ("tin_cay_thap",)


def test_lech_la_can_xem_va_giu_bubble():
    r = c("3", False, "8", 0.99, True, False)
    assert not r.chac and r.ly_do == ("lech_bubble",) and r.chu_so == "3"   # không để CNN chắc ghi đè bubble


def test_thieu_bubble_khong_tu_nhan_chu_viet_tay():
    """Ca 0001: SBD viết 062384, bubble 06238- (cột 6 không tô) -> cần xem, gợi ý 4 từ chữ viết tay, KHÔNG chắc."""
    r = c("?", True, "4", 0.99, True, False)
    assert not r.chac and r.ly_do == ("thieu_bubble",) and r.chu_so == "4"


def test_bubble_cx_la_can_xem():
    r = c("5", True, "5", 0.99, True, False)
    assert not r.chac and r.ly_do == ("bubble_cx",)


def test_o_trong_chi_tin_bubble_khi_co_trong_danh_sach():
    cot = [c("0", False, "0", 0.9, True, False), c("6", False, "?", 0.0, False, True)]
    assert cot[1].chac and cot[1].chi_trong_bubble
    assert t(cot, True) == ("06", True, ())
    gt, chac, ly = t(cot, None)
    assert not chac and ly == ("o_trong_chua_biet_ds",) and gt == "06"
    gt, chac, ly = t(cot, False)
    assert not chac and ly == ("o_trong_ngoai_ds",)


def test_truong_chi_chac_khi_moi_cot_chac():
    cot = [c("0", False, "0", 0.9, True, False), c("6", False, "5", 0.9, True, False)]
    gt, chac, ly = t(cot, True)
    assert not chac and ly == ("lech_bubble",) and gt == "06"
    gt, chac, ly = t([c("1", False, "1", 0.9, True, False)] * 3, True)
    assert chac and gt == "111" and ly == ()


def test_o_trong_va_bubble_thieu_la_can_xem():
    r = c("?", False, "?", 0.0, False, True)
    assert not r.chac and r.ly_do == ("thieu_bubble",) and r.chu_so == "?"
