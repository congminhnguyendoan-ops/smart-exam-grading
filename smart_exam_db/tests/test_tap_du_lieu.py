"""Ranh giới dev/test (cv_engine/tap_du_lieu.py – nguồn duy nhất) và chốt chặn tập test. Không mở ảnh nào."""
import pytest

from cv_engine.tap_du_lieu import (PHIEU_DEV, PHIEU_TEST, PHIEU_TRAIN, PHIEU_VAL, ChamTapTest, chan_test, la_test,
                                   ma_phieu, tap_cua)


@pytest.mark.parametrize("ten, ma", [("0035_C1", 35), ("0035_C1.jpg", 35), ("0035", 35), ("data/raw/0001_C4.jpg", 1),
                                     ("D003", None), ("IMG_4357", None), ("0035_C5", None)])
def test_ma_phieu(ten, ma):
    assert ma_phieu(ten) == ma


def test_ranh_gioi():
    assert list(PHIEU_DEV) == list(range(1, 35)) and list(PHIEU_TEST) == list(range(35, 41))
    assert set(PHIEU_TRAIN) | set(PHIEU_VAL) == set(PHIEU_DEV) and not set(PHIEU_TRAIN) & set(PHIEU_VAL)
    assert [tap_cua(t) for t in ("0034_C4", "0035_C1", "0040", "D010", "abc")] == ["dev", "test", "test", "dev", "khac"]
    assert la_test("0040_C2") and not la_test("D001")


def test_chan_test():
    chan_test(["0001_C1", "0034_C4", "D010"])                       # dev: không chặn
    with pytest.raises(ChamTapTest, match="0035_C1"):
        chan_test(["0001_C1", "0035_C1"], viec="thử")
    chan_test(["0035_C1"], xac_nhan=True)                            # có cờ: cho qua


def test_eval_dung_chung_ranh_gioi():
    """eval_preprocessing.SPLITS phải chính là ranh giới của tap_du_lieu; danh sách dev = 78 ảnh, không có test.
    (list_images chỉ liệt kê TÊN file, không mở ảnh.)"""
    import sys
    from conftest import DATA, ROOT, can_file
    can_file(DATA / "raw")
    sys.path.insert(0, str(ROOT / "tools"))
    import eval_preprocessing as ep
    assert ep.SPLITS == {"dev": PHIEU_DEV, "test": PHIEU_TEST}
    dev = ep.list_images("dev")
    assert len(dev) == 78 and not any(la_test(x.ten) for x in dev)
