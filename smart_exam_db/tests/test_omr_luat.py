import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from conftest import ROOT, can_file
from cv_engine import omr
from cv_engine.preprocessing import nap_layout

LUAT_CAU = {"trong_min": 0.9, "to_min": 0.5, "ro_min": 0.6}
LUAT_BUB = {"trong_min": 0.9, "to_min": 0.7}
TRONG, MO, RO = (0.99, 0.01, 0.0), (0.02, 0.95, 0.03), (0.0, 0.02, 0.98)


def cau(*o):
    return omr.ap_luat_cau(1, np.array(o), LUAT_CAU)


def test_mot_o_ro_chac_chan():
    k = cau(RO, TRONG, TRONG, TRONG)
    assert (k.trang_thai, k.dap_an, k.can_xem, k.ly_do) == ("ro", "A", False, ())


def test_mot_o_mo_can_xem():
    k = cau(TRONG, TRONG, MO, TRONG)
    assert (k.trang_thai, k.dap_an, k.can_xem, k.ly_do) == ("mo", "C", True, ("o_mo",))


@pytest.mark.parametrize("o,dap_an", [((RO, TRONG, RO, TRONG), "AC"), ((RO, RO, RO, TRONG), "ABC"),
                                      ((RO, RO, RO, RO), "ABCD"), ((RO, MO, TRONG, TRONG), "AB"),
                                      ((MO, TRONG, TRONG, MO), "AD")])
def test_nhieu_o_ke_ca_3_4_o_va_ro_cong_mo(o, dap_an):
    k = cau(*o)
    assert (k.trang_thai, k.dap_an, k.can_xem) == ("nhieu", dap_an, True) and "nhieu_o" in k.ly_do


def test_trong_chac_chan_khong_can_xem():
    k = cau(TRONG, TRONG, TRONG, TRONG)
    assert (k.trang_thai, k.dap_an, k.can_xem) == ("trong", "", False)


@pytest.mark.parametrize("lung", [(0.70, 0.29, 0.01), (0.55, 0.44, 0.01), (0.89, 0.10, 0.01)])
def test_trong_co_o_sat_nguong_can_xem(lung):
    k = cau(TRONG, lung, TRONG, TRONG)
    assert k.trang_thai == "trong" and k.dap_an == "" and k.can_xem and k.ly_do == ("tin_cay_thap",)


def test_o_to_lung_chung_ben_canh_o_ro():
    k = cau(RO, (0.6, 0.4, 0.0), TRONG, TRONG)
    assert k.dap_an == "A" and k.can_xem and "tin_cay_thap" in k.ly_do


def test_ro_min_quyet_ro_hay_mo():
    assert cau((0.0, 0.45, 0.55), TRONG, TRONG, TRONG).trang_thai == "mo"
    assert cau((0.0, 0.35, 0.65), TRONG, TRONG, TRONG).trang_thai == "ro"


def test_vi_tri_xau_luon_can_xem():
    k = omr.ap_luat_cau(1, np.array([RO, TRONG, TRONG, TRONG]), LUAT_CAU, vi_tri_xau=True)
    assert k.dap_an == "A" and k.can_xem and k.ly_do == ("vi_tri",)


def test_do_tin_cay_va_xac_suat():
    k = cau(RO, (0.7, 0.3, 0.0), TRONG, TRONG)
    assert k.do_tin_cay == pytest.approx(0.7)
    assert set(k.xac_suat) == {"A", "B", "C", "D"} and set(k.xac_suat["A"]) == {"blank", "faint", "filled"}


def cot(*p_to):
    return omr.ap_luat_cot("sbd", 1, np.column_stack([1 - np.array(p_to), np.array(p_to)]), LUAT_BUB)


def test_cot_mot_o():
    k = cot(*([0.001] * 3 + [0.99] + [0.001] * 6))
    assert (k.chu_so, k.can_xem) == ("3", False)


def test_cot_khong_to():
    k = cot(*([0.001] * 10))
    assert (k.chu_so, k.can_xem, k.ly_do) == ("?", True, ("khong_o_nao",))


def test_cot_nhieu_o():
    k = cot(*([0.99, 0.99] + [0.001] * 8))
    assert (k.chu_so, k.can_xem, k.ly_do) == ("?", True, ("nhieu_o",))


@pytest.mark.parametrize("p", [0.3, 0.45, 0.6])
def test_cot_mo_lung_chung_can_xem(p):
    k = cot(*([0.001] * 5 + [p] + [0.001] * 4))
    assert k.can_xem and "tin_cay_thap" in k.ly_do
    assert k.chu_so == ("5" if p >= 0.5 else "?")


def test_cot_bubble_mo_theo_ld_anh():
    P = np.column_stack([np.full(10, 0.999), np.full(10, 0.001)])
    P[4] = (0.2, 0.8)
    ld = np.zeros(10)
    luat = {**LUAT_BUB, "ro_min_ld_anh": 0.7}
    ld[4] = 0.4
    k = omr.ap_luat_cot("ma_de", 1, P, luat, ld_anh=ld)
    assert (k.chu_so, k.can_xem, k.ly_do) == ("4", True, ("o_mo",))
    ld[4] = 0.95
    assert not omr.ap_luat_cot("ma_de", 1, P, luat, ld_anh=ld).can_xem


def test_trang_thai_sang_db():
    assert [omr.sang_bubble_state(t) for t in ("trong", "ro", "mo", "nhieu")] == ["blank", "filled", "faint", "multiple"]


def test_du_doan_logistic_va_nguong():
    rng = np.random.default_rng(0)
    m3 = {"loai": "logistic", "cau": {"trung_binh": [0.0] * 9, "do_lech": [1.0] * 9, "he_so": rng.normal(size=(3, 9)).tolist(),
                                       "chan": [0.0, 0.1, -0.1], "lop": list(omr.LOP_CAU)}}
    P = omr.du_doan(m3, "cau", rng.normal(size=(5, 9)))
    assert P.shape == (5, 3) and np.allclose(P.sum(1), 1)
    m0 = {"loai": "nguong", "nguong": {"mark_min": 0.25, "filled_min": 0.8}}
    X = np.zeros((3, 9))
    X[:, omr.TEN_DAC_TRUNG.index("ld_anh")] = [0.1, 0.5, 0.9]
    assert omr.du_doan(m0, "cau", X).argmax(1).tolist() == [0, 1, 2]


@pytest.mark.parametrize("ten", ["omr_m1.json", "omr_m0.json"])
def test_mo_hinh_json_trong_git(ten):
    m = omr.nap_mo_hinh(omr.MODELS_DIR / ten)
    sd = m["sieu_du_lieu"]
    for k in ("ngay", "git_head", "sha256_dac_trung", "sha256_cell_labels", "sha256_split", "fold_huan_luyen", "nguon_anh"):
        assert k in sd
    assert m["nguon_anh"] in ("anh_nan", "anh_chuan_hoa")
    assert m["luat"]["cau"]["trong_min"] > 0.5 and m["luat"]["bubble"]["to_min"] >= 0.5


def test_doc_phieu_tu_choi_anh_khong_ok():
    with pytest.raises(ValueError):
        omr.doc_phieu(SimpleNamespace(ok=False, ly_do="anh_mo"), nap_layout("phieu"))


def _ve_o(anh, cx, cy, r, muc):
    cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(0.85 * r)), int(muc), -1)


def test_doc_phieu_tren_phieu_trang_ve_gia():
    L = nap_layout("phieu")
    anh = omr.nap_mau().copy()
    ans, r = L["answers"], L["answers"]["bubble_radius"]
    for o in "ABC":
        _ve_o(anh, *ans["centers"]["1"][o], r, 30)
    _ve_o(anh, *ans["centers"]["2"]["A"], r, 30)
    _ve_o(anh, *ans["centers"]["2"]["D"], r, 175)
    _ve_o(anh, *ans["centers"]["3"]["B"], r, 30)
    sbd, ma = L["sbd"], L["exam_code"]
    _ve_o(anh, *sbd["bubbles"][1][4], sbd["bubble_radius"], 200)
    for i, d in enumerate([4, 5, 6, 7]):
        _ve_o(anh, *sbd["bubbles"][i + 2][d], sbd["bubble_radius"], 30)
    for i, d in enumerate([1, 0, 1]):
        _ve_o(anh, *ma["bubbles"][i][d], ma["bubble_radius"], 30)
    kq = SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh)
    res = omr.doc_phieu(kq, L, omr.nap_mo_hinh())
    c = {k.cau: k for k in res.cau}
    assert (c[1].trang_thai, c[1].dap_an, c[1].can_xem) == ("nhieu", "ABC", True)
    assert c[2].trang_thai == "nhieu" and c[2].dap_an == "AD" and c[2].can_xem
    assert (c[3].trang_thai, c[3].dap_an, c[3].can_xem) == ("ro", "B", False)
    assert all(c[q].trang_thai == "trong" and not c[q].can_xem for q in range(4, 41))
    assert res.sbd_cot[0].chu_so == "?" and "khong_o_nao" in res.sbd_cot[0].ly_do
    assert res.sbd_cot[1].can_xem
    assert res.sbd[2:] == "4567" and not any(k.can_xem for k in res.sbd_cot[2:])
    assert res.ma_de == "101" and not res.ma_de_can_xem
    assert res.can_xem and res.sbd_can_xem and len(res.cau) == 40


def test_doc_phieu_anh_that_0001_C1():
    can_file(ROOT / "data" / "raw" / "0001_C1.jpg")
    from cv_engine.preprocessing import preprocess
    L = nap_layout("phieu")
    res = omr.doc_phieu(preprocess(ROOT / "data" / "raw" / "0001_C1.jpg", L), L)
    assert res.sbd == "06238?" and res.sbd_cot[5].ly_do == ("khong_o_nao",)
    assert res.ma_de == "101" and not res.ma_de_can_xem
    assert res.nguon_anh == "anh_nan" and res.phien_ban_mo_hinh == "omr_m1"
    assert json.dumps(res.dich_chuyen_mm)
