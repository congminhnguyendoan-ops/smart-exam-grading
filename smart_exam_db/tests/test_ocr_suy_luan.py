"""Kiểm thử suy luận CNN chữ số bằng NumPy + JSON (Tuần 6 Phần C, Bước 3): khớp PyTorch, tốc độ, ô trống / nhiễu, ca 0001.

Cần models/ocr_cnn.json (có trong git). Test dùng ảnh / cache dev (data/ không có trong git) tự SKIP nếu thiếu; không đọc ảnh val / test."""
import json
import statistics
import sys
import time

import numpy as np
import pytest

from conftest import DATA, ROOT, can_file
from cv_engine import ocr, omr
from cv_engine.preprocessing import nap_layout, preprocess
from cv_engine.tap_du_lieu import PHIEU_TRAIN, ma_phieu

MO_HINH = ocr.DUONG_DAN_MO_HINH
ANH_0001 = DATA / "raw" / "0001_C1.jpg"
CAT = DATA / "_ocr" / "cat"


@pytest.fixture(scope="module")
def mh():
    can_file(MO_HINH)
    return ocr.nap_mo_hinh_ocr()


@pytest.fixture(scope="module")
def layout():
    return nap_layout("phieu")


@pytest.fixture(scope="module")
def kq0001(layout):
    can_file(ANH_0001)
    assert ma_phieu(ANH_0001.stem) in PHIEU_TRAIN
    kq = preprocess(str(ANH_0001), layout)
    assert kq.ok
    return kq


def test_sieu_du_lieu_mo_hinh(mh):
    sd = mh.sieu_du_lieu
    assert sd["git_sach"] is True and len(sd["git_head"]) == 40, "mô hình phải xuất từ commit sạch"
    td = sd["tuong_duong_numpy_torch"]
    assert td["cung_nhan"] == 1.0 and td["chenh_xac_suat_max"] < 1e-4
    assert sd["do_luong"]["IL"] == 0
    assert mh.tau_khop == 0.5
    assert {"ngay", "seeds", "cau_hinh", "sha256_du_lieu", "nhiet_do_T"} <= set(sd)


def test_numpy_khop_pytorch_tren_moi_chu_so_dev(mh):
    """Dựng lại CNN PyTorch từ CHÍNH trọng số JSON; NumPy phải cho cùng nhãn 100%, chênh xác suất < 1e-4 trên mọi chữ số dev."""
    torch = pytest.importorskip("torch")
    can_file(CAT / "anh_nan.npz", CAT / "anh_nan.csv")
    sys.path.insert(0, str(ROOT / "tools"))
    import huan_luyen_ocr as H
    t = H.tap_do("anh_nan")
    x = np.concatenate([t["trang"]["x"], t["phieu"]["x"]])
    assert len(x) > 4000
    d = json.loads(MO_HINH.read_text(encoding="utf-8"))
    ps = []
    for m_json in d["thanh_vien"]:
        m = H.tao_cnn()
        ten = {"c1.weight": "c1w", "c1.bias": "c1b", "c2.weight": "c2w", "c2.bias": "c2b",
               "d1.weight": "d1w", "d1.bias": "d1b", "d2.weight": "d2w", "d2.bias": "d2b"}
        m.load_state_dict({k: torch.tensor(np.array(m_json[v], np.float32)) for k, v in ten.items()})
        m.eval()
        z = H.logits(m, x).astype(np.float64) / m_json["T"]
        z -= z.max(1, keepdims=True)
        e = np.exp(z)
        ps.append(e / e.sum(1, keepdims=True))
    p_torch, p_np = np.mean(ps, axis=0), ocr.du_doan_xac_suat(mh, x)
    assert (p_np.argmax(1) == p_torch.argmax(1)).all()
    assert np.abs(p_np - p_torch).max() < 1e-4


def test_thoi_gian_cat_9_o_va_suy_luan(kq0001, layout, mh):
    ocr.doc_chu_so(kq0001, layout, mh)                          # khởi động
    ms = [ocr.doc_chu_so(kq0001, layout, mh).thoi_gian_ms for _ in range(7)]
    assert statistics.median(ms) <= 50.0, f"T5: {statistics.median(ms):.1f} ms > 50 ms"


def test_ban_do_toi_cuc_bo_giong_ca_trang(kq0001, layout):
    rects = [tuple(r) for f in ("sbd", "exam_code") for r in layout[f]["handwriting_boxes"]]
    cuc_bo = ocr._ban_do_toi_cuc_bo(kq0001.anh_nan, rects)
    ca_trang = ocr.ban_do_toi(kq0001.anh_nan)
    x0 = int(min(r[0] for r in rects)) - 90
    y0 = int(min(r[1] for r in rects)) - 90
    x1 = int(max(r[0] + r[2] for r in rects)) + 90
    y1 = int(max(r[1] + r[3] for r in rects)) + 90
    assert np.array_equal(cuc_bo[y0:y1, x0:x1], ca_trang[y0:y1, x0:x1])


def test_doc_chu_so_tu_choi_anh_khong_ok(layout, mh):
    from cv_engine.preprocessing import KetQuaTienXuLy
    with pytest.raises(ValueError):
        ocr.doc_chu_so(KetQuaTienXuLy(ly_do="anh_mo"), layout, mh)


def _sua_anh(kq, layout, ham):
    """Bản sao `kq` với anh_nan bị sửa ở vùng 9 ô viết tay: ham(vung_xam, rng) -> vùng mới."""
    from dataclasses import replace
    anh = kq.anh_nan.copy()
    rng = np.random.default_rng(0)
    for f in ("sbd", "exam_code"):
        for x, y, w, h in layout[f]["handwriting_boxes"]:
            x0, y0, x1, y1 = int(x) + 12, int(y) + 12, int(x + w) - 12, int(y + h) - 12      # chừa viền ô in sẵn
            anh[y0:y1, x0:x1] = ham(anh[y0:y1, x0:x1], rng)
    return replace(kq, anh_nan=anh)


def test_o_trong_khong_qua_cnn(kq0001, layout, mh):
    kq = _sua_anh(kq0001, layout, lambda v, r: np.full_like(v, int(np.median(v))))     # xoá hết chữ: chỉ còn giấy
    r = ocr.doc_chu_so(kq, layout, mh)
    for c in r.sbd + r.ma_de:
        assert c.o_trong and c.chu_so == "?" and c.top_k == [] and c.p == 0.0 and not c.cnn_chac, c


def test_o_nhieu_muc_khong_phai_chu_so(kq0001, layout, mh):
    kq = _sua_anh(kq0001, layout, lambda v, r: np.where(r.random(v.shape) < 0.6, 20, 230).astype(np.uint8))   # nhiễu đen dày
    r = ocr.doc_chu_so(kq, layout, mh)
    for c in r.sbd + r.ma_de:
        assert c.chu_so == "?" and not c.o_trong and c.loi_o in ("khong_phai_chu_so", "o_it_muc"), c
        assert c.top_k == [] and not c.cnn_chac


def test_loi_o_la_can_xem_ke_ca_khi_bubble_chac():
    c = ocr.doi_chieu_cot("3", False, "?", 0.0, False, False, 0.5, "khong_phai_chu_so")
    assert not c.chac and c.ly_do == ("khong_phai_chu_so",) and c.chu_so == "3"
    gt, chac, ly = ocr.doi_chieu_truong([c], True)
    assert not chac and "khong_phai_chu_so" in ly


def test_ca_0001_sbd_viet_062384_bubble_06238_thieu_cot_6(kq0001, layout, mh):
    """Ca thử của kế hoạch: SBD viết tay 062384, bubble 06238- (chữ số 6 không tô) -> cột cuối PHẢI cần xem, trường không chắc."""
    can_file(ROOT / "models" / "omr_m1.json")
    res = omr.doc_phieu(kq0001, layout, omr.nap_mo_hinh())
    hv = ocr.doc_chu_so(kq0001, layout, mh)
    dc = ocr.doi_chieu_dinh_danh(res, hv, True, True, mo_hinh=mh)
    assert res.sbd == "06238?"
    gia_tri, chac, ly = dc["sbd"]
    assert not chac and "thieu_bubble" in ly
    cot_cuoi = dc["cot"]["sbd"][5]
    assert not cot_cuoi.chac
    assert dc["can_xem"]


# --------------------------------------------------------------------------------------------- Lệnh AM: kiến trúc "sau_2x2"
def _mang_sau_ngau_nhien(torch, seed=20261116):
    sys.path.insert(0, str(ROOT / "tools"))
    import ak_so_sanh_mo_rong as K
    torch.manual_seed(seed)
    return K.tao_cnn_sau().eval()


def test_cnn_sau_numpy_khop_pytorch_trong_so_ngau_nhien(tmp_path):
    """Tiêu chí (c) của docs/tieu_chi_cnn_sau.md: ≥ 2000 ô MNIST test, cùng nhãn ≥ 99,9%, mọi logit lệch ≤ 1e-4.
    Đi qua ĐÚNG đường xuất JSON (xuat_ocr.tham_so + lam_tron 8 chữ số) rồi nap_mo_hinh_ocr, so với PyTorch dùng trọng số GỐC."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("sklearn")
    can_file(DATA / "_ocr" / "nguon" / "t10k-images-idx3-ubyte.gz")
    import huan_luyen_ocr as H
    import xuat_ocr as X
    net = _mang_sau_ngau_nhien(torch)
    assert sum(v.size for v in X.tham_so(net).values()) == 467818
    x = H.doc_mnist()[2][:2000]
    f = tmp_path / "sau.json"
    f.write_text(json.dumps({"phien_ban": "thu", "kien_truc": ocr.KIEN_TRUC_SAU, "tau": 0.9995, "delta": 0.99, "tau_khop": 0.5,
                             "thanh_vien": [{"seed": 1, "T": 1.0, **{k: X.lam_tron(v) for k, v in X.tham_so(net).items()}}]}), encoding="utf-8")
    mh_sau = ocr.nap_mo_hinh_ocr(f)
    assert mh_sau.kien_truc == ocr.KIEN_TRUC_SAU
    z_np = ocr.logit_mot_thanh_vien(mh_sau.thanh_vien[0], x)
    z_pt = H.logits(net, x)
    assert z_pt.std() > 0.01, "logit ngẫu nhiên không được suy biến"
    assert (z_np.argmax(1) == z_pt.argmax(1)).mean() >= 0.999
    assert np.abs(z_np - z_pt).max() <= 1e-4


def test_mo_hinh_cu_van_nap_nhu_truoc(mh):
    assert mh.kien_truc == "co_ban" and "c1w" in mh.thanh_vien[0] and "a1w" not in mh.thanh_vien[0]


def test_nap_mo_hinh_sau_thieu_khoa_bi_tu_choi(tmp_path):
    f = tmp_path / "hong.json"
    f.write_text(json.dumps({"kien_truc": ocr.KIEN_TRUC_SAU, "tau": 0.9, "delta": 0.9, "tau_khop": 0.5,
                             "thanh_vien": [{"seed": 1, "T": 1.0, "c1w": [0.0]}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        ocr.nap_mo_hinh_ocr(f)
