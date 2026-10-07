"""Kiểm đầu-cuối backend trên một MẪU nhỏ ảnh dev (đủ C1–C4, gồm giấy cong 0014_C2, SBD thiếu cột 0001_C1) và vài ảnh giả.
Bản đầy đủ 56 ảnh + 74 ảnh giả: python tools/kiem_backend_dau_cuoi.py (báo cáo ở data/_eval/backend/)."""
import sys

import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import kiem_backend_dau_cuoi as K  # noqa: E402

MAU = ["0001_C1", "0002_C2", "0002_C3", "0014_C2", "0019_C4", "0027_C3", "0028_C4"]


def test_diem_doc_lap_tu_nhan():
    """Luật 'đúng thật' của công cụ kiểm: đúng MỘT ô và ô đó = đáp án (ô mờ cũng tính)."""
    assert K.dung_that("B", "B") and K.dung_that("b", "B") and not K.dung_that("A", "B")
    assert not K.dung_that("-", "B") and not K.dung_that("AB", "B") and not K.dung_that("BC", "B")
    assert K.chon_that("-") == "" and K.chon_that("c") == "C" and K.chon_that("AC") == "AC"


def test_dau_cuoi_mau(csdl_san_sang):
    can_file(*[ROOT / "data" / "raw" / f"{t}.jpg" for t in MAU], ROOT / "data" / "ground_truth.csv")
    kq = K.chay(MAU, voi_gia=True, tien_do=lambda *_: None, gia_toi_da=12)
    s = K.tom_tat(kq)
    assert s["anh"] == len(MAU) and s["anh_bi_tu_choi"] == 0
    assert s["cham_sai_khong_gan_can_xem"] == 0 and s["doc_sai_khong_gan_can_xem"] == 0       # SỐ CÂU CHẤM SAI MÀ KHÔNG GẮN CẦN XEM = 0
    assert s["sai_im_lang_sbd"] == 0 and s["sai_im_lang_ma_de"] == 0 and s["vi_pham_can"] == 0 and s["tu_chot_sai_diem"] == 0
    assert s["cuoi_dung_diem"] == len(MAU) and s["cuoi_graded"] == len(MAU)                   # điểm chính thức = điểm tính độc lập
    assert s["gia"].get("LOI_IM_LANG", 0) == 0 and s["gia"].get("tu_choi_nham", 0) == 0
    assert s["cau_can_xem"] > 0                                                               # mẫu có câu cần xem thật


def test_chi_nhan_anh_train(csdl_san_sang):
    with pytest.raises(AssertionError):
        K.chay(["0035_C1"], voi_gia=False, tien_do=lambda *_: None)                           # ngoài 0001–0028: không chạy
