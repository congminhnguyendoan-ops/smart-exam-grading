import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ai_so_sanh_thuat_toan as A  # noqa: E402


def test_knn_phieu_ti_le_lang_gieng():
    lg = np.array([[3, 3, 5, 7, 3], [1, 2, 2, 2, 9]])
    assert np.allclose(A.knn_phieu(lg, 1)[0], np.eye(10)[3])
    p = A.knn_phieu(lg, 5)
    assert p[0, 3] == pytest.approx(0.6) and p[1, 2] == pytest.approx(0.6) and np.allclose(p.sum(1), 1)


def test_mau_con_phan_tang_co_dinh():
    y = np.repeat(np.arange(10), [100, 200, 100, 100, 100, 100, 100, 100, 100, 100])
    i = A.mau_con(y, 330, 2026)
    assert len(i) == 330 and np.array_equal(i, A.mau_con(y, 330, 2026))
    assert np.bincount(y[i])[1] == 60
    assert len(A.mau_con(y, 5000, 1)) == len(y)


def _r(macro, nguoi, stt=1):
    return {"theo_nguoi": {str(k): v for k, v in zip(A.NGUOI, nguoi)}, "macro": macro, "micro": macro, "phieu": macro,
            "sai_tu_tin_trang": stt, "sai_tu_tin_phieu": 0, "sai_trang": 2, "T": 1.0, "confusion": np.zeros((10, 10), int).tolist()}


def test_gop_seed_va_r1():
    rs = [_r(0.9, [0.9] * 5), _r(0.92, [0.92] * 5)]
    g = A.gop_seed(rs)
    assert g["macro"] == pytest.approx(0.91) and g["sai_tu_tin_trang_cong"] == 2 and g["sd_nguoi"] == pytest.approx(0.0)
    assert g["sd_seed"] == pytest.approx(np.std([0.9, 0.92], ddof=1))
    e = {"cnn": {"macro": 0.950}, "svm": {"macro": 0.959}, "lr": {"macro": 0.90}}
    r = A.ket_luan_r1(e)
    assert r["tot_nhat"] == "svm" and r["hop_ly"] and r["chenh_diem"] == pytest.approx(0.9)
    e["svm"]["macro"] = 0.9605
    r = A.ket_luan_r1(e)
    assert not r["hop_ly"] and r["dung_hon_cnn"] == [("svm", pytest.approx(1.05))]
    assert A.ket_luan_r1({"cnn": {"macro": 0.97}, "lr": {"macro": 0.9}})["tot_nhat"] == "cnn"


def test_chi_so_e2_hieu_chinh_va_sai_tu_tin():
    y = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9] * 5)
    ng = np.repeat(A.NGUOI, 10)
    z = np.eye(10)[y] * 5.0
    z[0] = np.eye(10)[7] * 5.0
    r = A.chi_so_e2(z, z[:10], y, ng, y[:10], ng[:10])
    assert r["sai_trang"] == 1 and r["sai_tu_tin_trang"] == 1 and r["theo_nguoi"]["1"] == pytest.approx(0.9)
    assert r["macro"] == pytest.approx(0.98) and r["confusion"][0][7] == 1 and 0.5 <= r["T"] <= 6
