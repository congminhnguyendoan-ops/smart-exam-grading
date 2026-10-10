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


# ---- Tuần 6: người viết; chứng minh các tập phiếu dev / test CŨ không đổi -------------------------------
def test_tap_cu_khong_doi():
    """Vân tay SHA-256 của toàn bộ ranh giới cũ (tap_cua / ma_phieu / la_test trên 0000–0044, 160 tên ảnh phiếu, D000–D012,
    tên lạ; cộng 8 mốc range) tính từ bản TRƯỚC khi thêm người viết (HEAD a97064d). Đổi bất kỳ hằng / hàm cũ nào sẽ làm vỡ test này."""
    import hashlib
    from cv_engine import tap_du_lieu as t
    names = ([f"{i:04d}" for i in range(0, 45)] + [f"{i:04d}_C{k}.jpg" for i in range(1, 41) for k in range(1, 5)]
             + [f"D{i:03d}" for i in range(0, 13)] + ["abc", "D1", "0035_x"])
    s = "|".join(f"{n}:{t.tap_cua(n)}:{t.ma_phieu(n)}:{t.la_test(n)}" for n in names)
    s += "|" + ",".join(map(str, [t.PHIEU_DEV.start, t.PHIEU_DEV.stop, t.PHIEU_TEST.start, t.PHIEU_TEST.stop,
                                  t.PHIEU_TRAIN.start, t.PHIEU_TRAIN.stop, t.PHIEU_VAL.start, t.PHIEU_VAL.stop]))
    assert hashlib.sha256(s.encode()).hexdigest() == "f3d507df4e2a3975b8b28f28815a72469cd764c39845a62f96bd936b308a5a98"


def test_nguoi_viet():
    from cv_engine.tap_du_lieu import fold_nguoi_viet, ma_trang, nguoi_viet, nguoi_viet_phieu, nguoi_viet_trang
    assert [nguoi_viet_trang(t) for t in range(1, 11)] == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert [nguoi_viet_phieu(p) for p in (1, 8, 9, 16, 17, 24, 25, 32, 33, 40)] == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert [nguoi_viet(x) for x in ("D001", "D010.jpg", "0001_C1", "0035_C3", "0040", "IMG_1", "D011", "0041")] == \
        [1, 5, 1, 5, 5, None, None, None]
    assert fold_nguoi_viet("D003") == 1 and fold_nguoi_viet("abc") is None and ma_trang("0001") is None
    for bad in (0, 11):
        with pytest.raises(ValueError):
            nguoi_viet_trang(bad)
    for bad in (0, 41):
        with pytest.raises(ValueError):
            nguoi_viet_phieu(bad)


def test_test_chi_nguoi_5():
    """Hạn chế đã ghi trong kế hoạch: tập test 0035–0040 toàn người 5 (cùng người viết D009–D010)."""
    from cv_engine.tap_du_lieu import PHIEU_TEST, nguoi_viet_phieu, nguoi_viet_trang
    assert {nguoi_viet_phieu(p) for p in PHIEU_TEST} == {5} == {nguoi_viet_trang(9), nguoi_viet_trang(10)}
