"""Ảnh giả lỗi cố ý (data/_eval/_gia_v4, tạo từ ảnh dev bằng tools/kiem_verify.py tao-gia): bị từ chối đúng mã.
Mong đợi lấy từ danh_sach.csv – chốt TRƯỚC khi chạy verify() ở Bước 4 – không viết lại ở đây."""
import csv

import pytest
from conftest import GIA, can_file

from cv_engine.preprocessing import MA_LY_DO, nap_layout, preprocess

NHOM = {"khong_du_marker": {"thieu_marker", "marker_khong_dat"}}
# Mỗi mã từ chối một ca (+ một ca xoay phải ok): che marker, marker chạm mép, hai tờ, tờ khác lọt khung, mờ,
# nhầm loại trang, không có phiếu, quá nghiêng.
CA = ["che_toi_tl_0001_C1", "cat_muc_2px_br_0001_C1", "hai_to_1_0001_C1+0008_C4", "lot_khung_19mm_0001_C1",
      "mo_gauss8_0001_C1", "nham_loai_D003", "khong_phieu_giay_0005_C2", "qua_nghieng_45_0008_C4", "xoay180_0006_C2"]


@pytest.fixture(scope="module")
def danh_sach() -> dict:
    can_file(GIA / "danh_sach.csv")
    return {r["ten"]: r for r in csv.DictReader((GIA / "danh_sach.csv").open(encoding="utf-8-sig"))}


@pytest.mark.parametrize("ten", CA)
def test_anh_gia(ten, danh_sach):
    d = danh_sach[ten]
    can_file(GIA / f"{ten}.jpg")
    kq = preprocess(GIA / f"{ten}.jpg", nap_layout(d["layout"]))
    if d["mong_doi"] == "ok":
        assert kq.ok and kq.huong_xoay == int(d["huong_mong_doi"]) and kq.anh_chuan_hoa is not None
        return
    chap_nhan = set()
    for m in filter(None, d["ly_do_mong_doi"].split("|")):
        chap_nhan |= NHOM.get(m, {m})
    assert not kq.ok
    assert kq.ly_do in chap_nhan, f"{ten}: trả '{kq.ly_do}', mong {sorted(chap_nhan)}"
    assert kq.ly_do in MA_LY_DO
    assert kq.anh_chuan_hoa is None
