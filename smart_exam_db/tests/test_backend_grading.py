from decimal import Decimal

import pytest

from backend import grading

D = Decimal("0.25")


def hang(q, chon, state, cx=False):
    return {"question_no": q, "selected_options": chon, "state": state, "needs_review": cx}


KEY = {q: ("ABCD"[q % 4], None) for q in range(1, 41)}


def test_cau_chac_chan_dung_sai():
    rows = [hang(1, "B", "filled"), hang(2, "A", "filled"), hang(3, "", "blank"), hang(4, "AB", "multiple")]
    kq = grading.cham_diem(rows, {q: KEY[q] for q in range(1, 5)}, D)
    assert [c.is_correct for c in kq.cau] == [True, False, False, False]
    assert (kq.num_correct, kq.diem_tam, kq.diem_toi_da, kq.so_cau_can_xem) == (1, Decimal("0.250"), Decimal("0.250"), 0)


def test_cau_can_xem_khong_duoc_cham_nhu_chac_chan():
    rows = [hang(1, "B", "filled"), hang(2, "C", "faint", cx=True), hang(3, "DA", "multiple", cx=True)]
    kq = grading.cham_diem(rows, {q: KEY[q] for q in range(1, 4)}, D)
    assert [c.is_correct for c in kq.cau] == [True, None, None]
    assert (kq.num_correct, kq.diem_tam, kq.diem_toi_da, kq.so_cau_can_xem) == (1, Decimal("0.250"), Decimal("0.750"), 2)


def test_chi_state_filled_moi_tinh():
    kq = grading.cham_diem([hang(1, "B", "faint")], {1: KEY[1]}, D)
    assert kq.cau[0].is_correct is False and kq.diem_tam == 0


def test_diem_rieng_tung_cau_va_lam_tron():
    key = {1: ("A", Decimal("0.3335")), 2: ("B", None)}
    kq = grading.cham_diem([hang(1, "A", "filled"), hang(2, "B", "filled")], key, Decimal(10) / Decimal(3))
    assert kq.diem_tam == Decimal("3.667")


def test_thieu_hang_bai_lam_tinh_bo_trong():
    kq = grading.cham_diem([], {1: KEY[1]}, D)
    assert kq.cau[0].is_correct is False


@pytest.mark.parametrize("s,mong", [("", ""), ("b", "B"), ("ca", "AC"), ("AAB", "AB"), (" d ", "D")])
def test_chuan_hoa_lua_chon(s, mong):
    assert grading.chuan_hoa_lua_chon(s) == mong


@pytest.mark.parametrize("s", ["E", "1", "A-B"])
def test_lua_chon_sai(s):
    with pytest.raises(ValueError):
        grading.chuan_hoa_lua_chon(s)


def test_trang_thai_tu_lua_chon():
    assert [grading.trang_thai_tu_lua_chon(x) for x in ("", "A", "AC")] == ["blank", "filled", "multiple"]
