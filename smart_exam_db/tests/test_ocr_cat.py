import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import ocr  # noqa: E402


def _trang_gia(chu=True, dx=0, dy=0):
    im = np.full((500, 600), 200, np.uint8)
    rects = [(100 + dx, 100 + dy, 71, 106), (183 + dx, 100 + dy, 71, 106)]
    for x, y, w, h in rects:
        cv2.rectangle(im, (x, y), (x + w, y + h), 60, 4)
    if chu:
        x, y, w, h = rects[0]
        cv2.line(im, (x + 35, y + 25), (x + 35, y + 80), 50, 6)
    return im, rects


def test_cat_khung_va_chu():
    im, rects = _trang_gia()
    o = ocr.cat_anh(im, [rects])[0]
    assert o[0].ok_vien and o[1].ok_vien
    assert o[0].anh28 is not None and o[0].anh28.shape == (28, 28) and o[0].anh28.dtype == np.uint8
    assert o[0].n_tp == 1 and o[0].vien_con < 0.5 and o[0].cham_vien == 0
    assert o[1].anh28 is None and o[1].ink_px == 0
    assert abs(o[0].lech_vien[0]) <= 2 and abs(o[0].lech_vien[1]) <= 2


@pytest.mark.parametrize("dx,dy", [(-25, 18), (30, -22), (12, 35)])
def test_cat_theo_vien_khi_trang_lech(dx, dy):
    im, rects = _trang_gia(dx=dx, dy=dy)
    nom = [(100, 100, 71, 106), (183, 100, 71, 106)]
    o = ocr.cat_anh(im, [nom])[0]
    assert o[0].ok_vien and o[0].vien_con < 0.5
    assert o[0].anh28 is not None and o[1].anh28 is None
    assert o[0].cao >= 50


def test_khung_khong_tim_thay_duoc_danh_dau():
    im, rects = _trang_gia()
    cv2.rectangle(im, (95, 95), (260, 215), 200, -1)
    o = ocr.cat_anh(im, [rects])[0]
    assert not o[0].ok_vien and not o[1].ok_vien


def test_ve_mnist_tam_o_giua():
    ink = np.zeros((60, 40), np.float32)
    ink[5:55, 18:22] = 1.0
    a = ocr.ve_mnist(ink)
    ys, xs = np.nonzero(a)
    assert a.shape == (28, 28) and abs(ys.mean() - 13.5) <= 1.0 and abs(xs.mean() - 13.5) <= 1.0
    assert ys.max() - ys.min() + 1 <= 21 and ocr.ve_mnist(np.zeros((10, 10), np.float32)) is None


@pytest.mark.skipif(not (ROOT / "data/raw_digits/D003.jpg").exists(), reason="thiếu data/")
def test_trang_that_d003():
    from cv_engine.preprocessing import nap_layout, preprocess
    lay = nap_layout("chu_so")
    kq = preprocess(str(ROOT / "data/raw_digits/D003.jpg"), lay)
    assert kq.ok
    hang = {}
    for b in lay["boxes"]:
        hang.setdefault(b["row"], []).append(b["rect"])
    ok = n = 0
    for cac in ocr.cat_anh(kq.anh_nan, [hang[r] for r in sorted(hang)]):
        for o in cac:
            n += 1
            ok += o.ok_vien and o.anh28 is not None and o.vien_con < 0.5
    assert n == 400 and ok >= 380


def test_split_ocr_sinh_lai_giong_nhau():
    import ocr_du_lieu as d
    if not (ROOT / "data/raw").exists():
        pytest.skip("thiếu data/")
    s = d.tao_split()
    assert s == d.tao_split() and s.splitlines()[0] == "anh,loai,nguoi,fold,tap"
    dong = [x.split(",") for x in s.splitlines()[1:]]
    trang = [x for x in dong if x[1] == "trang"]
    assert [x[3] for x in trang] == ["0", "0", "1", "1", "2", "2", "3", "3", "4", "4"]
    assert all(x[3] == "" and x[4] == "test" for x in dong if x[1] == "phieu" and x[0][:4] in {f"{i:04d}" for i in range(35, 41)})


def test_cat_chan_tap_test(monkeypatch, tmp_path):
    import ocr_du_lieu as d
    if not (ROOT / "data/raw").exists():
        pytest.skip("thiếu data/")
    ds = d._liet_ke()
    from cv_engine.tap_du_lieu import ma_phieu
    assert len(ds) == 78 and all((ma_phieu(t) or 0) <= 34 for _, t, _ in ds)
