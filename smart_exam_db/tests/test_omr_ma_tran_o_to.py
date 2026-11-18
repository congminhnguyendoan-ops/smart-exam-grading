from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from cv_engine import omr
from cv_engine.preprocessing import nap_layout

L = nap_layout("phieu")
ANS = L["answers"]
R = ANS["bubble_radius"]
DAM, MO, TRONG = (0, 40, 80), (120, 150, 190, 205), (235, 245)


@pytest.fixture(scope="module")
def mo_hinh():
    return omr.nap_mo_hinh()


def doc(mo_hinh, cases, giay=255):
    n = len(cases)
    cases = list(cases) + [{"C": 30}] * (40 - n)
    anh = omr.nap_mau().copy()
    for q, cs in enumerate(cases, 1):
        for o, g in cs.items():
            cx, cy = ANS["centers"][str(q)][o]
            cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(0.85 * R)), int(g), -1)
    if giay != 255:
        anh = (anh.astype(np.float32) * giay / 255).clip(0, 255).astype(np.uint8)
    kq = SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh)
    return omr.doc_phieu(kq, L, mo_hinh).cau[:n]


GIAY = [255, 170]


@pytest.mark.parametrize("giay", GIAY)
def test_mot_o_theo_muc_xam(mo_hinh, giay):
    muc = DAM + MO + TRONG
    kq = doc(mo_hinh, [{"A": g} for g in muc], giay)
    for g, k in zip(muc, kq):
        if g in DAM:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("ro", "A", False), g
        elif g in MO:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("mo", "A", True), g
        else:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("trong", "", False), g


@pytest.mark.parametrize("giay", GIAY)
def test_mot_dam_mot_nhat(mo_hinh, giay):
    muc = DAM + MO + TRONG
    kq = doc(mo_hinh, [{"A": 20, "B": g} for g in muc], giay)
    for g, k in zip(muc, kq):
        if g in TRONG:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("ro", "A", False), g
        else:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("nhieu", "AB", True), g


@pytest.mark.parametrize("giay", GIAY)
@pytest.mark.parametrize("so_o", [2, 3, 4])
def test_nhieu_o_cung_muc(mo_hinh, giay, so_o):
    chon = "ABCD"[:so_o]
    muc = DAM + MO + TRONG
    kq = doc(mo_hinh, [{o: g for o in chon} for g in muc], giay)
    for g, k in zip(muc, kq):
        if g in TRONG:
            assert (k.trang_thai, k.can_xem) == ("trong", False), g
        else:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("nhieu", chon, True), g


def test_hai_o_mot_dam_mot_mo_o_cac_vi_tri_khac_nhau(mo_hinh):
    cap = [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]
    cases = [{a: 20, b: 200} for a, b in cap] + [{a: 200, b: 20} for a, b in cap]
    for (a, b), k in zip(cap + cap, doc(mo_hinh, cases)):
        assert k.trang_thai == "nhieu" and k.dap_an == a + b and k.can_xem


def test_du_40_cau_moi_cau_mot_dap_an_khac_nhau(mo_hinh):
    cases = [{"ABCD"[q % 4]: 30} for q in range(1, 41)]
    kq = doc(mo_hinh, cases)
    assert len(kq) == 40
    for q, k in enumerate(kq, 1):
        assert (k.cau, k.dap_an, k.trang_thai, k.can_xem) == (q, "ABCD"[q % 4], "ro", False)


def test_du_40_cau_xen_ke_ro_mo_trong_nhieu(mo_hinh):
    mau = [({"B": 30}, "ro", False), ({"C": 200}, "mo", True), ({}, "trong", False), ({"A": 30, "D": 30}, "nhieu", True)]
    cases = [mau[(q - 1) % 4][0] for q in range(1, 41)]
    for q, k in enumerate(doc(mo_hinh, cases), 1):
        _, tt, xem = mau[(q - 1) % 4]
        assert (k.trang_thai, k.can_xem) == (tt, xem), q


@pytest.mark.parametrize("kich", [0.7, 1.0, 1.2])
def test_vung_to_du_to_la_ro(mo_hinh, kich):
    anh = omr.nap_mau().copy()
    for q in range(1, 41):
        cx, cy = ANS["centers"][str(q)]["B"]
        cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(kich * R)), 30, -1)
    kq = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh), L, mo_hinh).cau
    assert all((k.trang_thai, k.dap_an, k.can_xem) == ("ro", "B", False) for k in kq)


@pytest.mark.parametrize("kich", [0.2, 0.3])
@pytest.mark.parametrize("xam", [30, 90])
def test_cham_nho_dam_phai_can_xem(mo_hinh, kich, xam):
    anh = omr.nap_mau().copy()
    for q in range(1, 41):
        cx, cy = ANS["centers"][str(q)]["B"]
        cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(kich * R)), xam, -1)
    kq = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh), L, mo_hinh).cau
    assert all(k.can_xem and "vet_nho" in k.ly_do for k in kq)
    assert all((k.trang_thai, k.dap_an) == ("trong", "") for k in kq)


def test_cham_nho_canh_dap_an_ro_van_can_xem(mo_hinh):
    kq = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=_ve_cham_d(), anh_chuan_hoa=_ve_cham_d()), L, mo_hinh).cau
    assert all((k.trang_thai, k.dap_an, k.can_xem, k.ly_do) == ("ro", "A", True, ("vet_nho",)) for k in kq)


def _ve_cham_d():
    anh = omr.nap_mau().copy()
    for q in range(1, 41):
        for o, kich in (("A", 0.85), ("D", 0.3)):
            cx, cy = ANS["centers"][str(q)][o]
            cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(kich * R)), 30, -1)
    return anh


def test_phieu_trang_khong_gan_co_vet_nho(mo_hinh):
    anh = omr.nap_mau().copy()
    kq = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh), L, mo_hinh).cau
    assert not any("vet_nho" in k.ly_do for k in kq)


def _doc_to(mo_hinh, cases, nen=None):
    cases = list(cases) + [({"C": nen} if nen is not None else {})] * (40 - len(cases))
    anh = omr.nap_mau().copy()
    for q, cs in enumerate(cases, 1):
        for o, g in cs.items():
            cx, cy = ANS["centers"][str(q)][o]
            cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(0.85 * R)), int(g), -1)
    return omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh), L, mo_hinh)


@pytest.mark.parametrize("xam", [150, 190])
def test_to_nhat_ca_to_xam_nhat_moi_cau_da_chon_can_xem(mo_hinh, xam):
    res = _doc_to(mo_hinh, [{"ABCD"[q % 4]: xam} for q in range(40)])
    assert res.to_nhat and res.do_toi_to < omr.TO_NHAT_X
    assert all(k.can_xem and "to_nhat" in k.ly_do for k in res.cau)
    assert all((k.trang_thai, k.dap_an) == ("ro", "ABCD"[q % 4]) for q, k in enumerate(res.cau))


@pytest.mark.parametrize("xam", [30, 60, 80])
def test_to_nhat_to_dam_khong_co(mo_hinh, xam):
    res = _doc_to(mo_hinh, [{"ABCD"[q % 4]: xam} for q in range(40)])
    assert not res.to_nhat and not any("to_nhat" in k.ly_do or k.can_xem for k in res.cau)


@pytest.mark.parametrize("nen,vet", [(150, 170), (150, 190), (190, 190), (190, 210)])
def test_to_nhat_vet_lac_tren_to_nhat_co_co(mo_hinh, nen, vet):
    res = _doc_to(mo_hinh, [{"A": vet}], nen)
    assert res.to_nhat and res.cau[0].can_xem and "to_nhat" in res.cau[0].ly_do


def test_to_nhat_it_o_ro_chac_khong_danh_gia(mo_hinh):
    res = _doc_to(mo_hinh, [{"A": 150}] * 5)
    assert not res.to_nhat and omr.np.isnan(res.do_toi_to)
