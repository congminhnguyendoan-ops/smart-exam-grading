"""Ma trận các trường hợp tô ô (mức xám 0–255) chạy qua cả chuỗi doc_phieu trên phiếu trắng vẽ giả.

Khác test_omr_luat.py (đưa xác suất giả vào luật), file này vẽ ô bằng điểm ảnh thật với mức xám cho trước,
nên bắt được lỗi ở khâu đặc trưng / ngưỡng. Mức xám tính trên giấy trắng 255 (0 = đen hẳn).

Ngưỡng quan sát được (omr_m1.json, ô vẽ đặc 0,85r, các câu còn lại của tờ tô đen 30 như phiếu thường):
    <= 80  tô RÕ, chắc      100  vùng đệm rõ/mờ (giấy tối)      120–205  tô MỜ, cần xem      220  vùng đệm mờ/trống      >= 235  TRỐNG, chắc
LƯU Ý: mô hình đo độ tối của ô theo thang của CHÍNH TỜ PHIẾU (S_anh trong omr.py), nên ranh giới rõ/mờ dịch theo độ đậm bút
chung của tờ: tờ tô toàn bút chì nhạt (xám 150) thì xám 170–190 vẫn là "rõ". Thiên lệch này an toàn (nghiêng về hỏi giáo viên khi
tờ đậm) nhưng có nghĩa là một vệt nhạt lạc trên tờ toàn nét nhạt không bị gắn cờ.
"""
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
    """cases: tối đa 40 dict {ô: mức xám}; câu i+1 tô theo cases[i]. Các câu còn lại tô đậm ô C như một phiếu thường
    (thang S_anh của omr.py ước lượng từ chính tờ phiếu, nên một tờ có quá ít vết tô sẽ cho kết quả khác);
    chỉ trả về len(cases) câu đầu."""
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


GIAY = [255, 170]          # giấy sáng và giấy tối (thiếu sáng)


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
    """A đậm + B ở mọi mức: B tô được (đậm hay mờ) -> nhiều ô cần xem; B gần như trống -> A rõ, không cần xem."""
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
    """2 / 3 / 4 ô cùng mức (đậm cùng đậm, nhạt cùng nhạt): luôn nhiều ô + cần xem; cùng trống thì là câu trống."""
    chon = "ABCD"[:so_o]
    muc = DAM + MO + TRONG
    kq = doc(mo_hinh, [{o: g for o in chon} for g in muc], giay)
    for g, k in zip(muc, kq):
        if g in TRONG:
            assert (k.trang_thai, k.can_xem) == ("trong", False), g
        else:
            assert (k.trang_thai, k.dap_an, k.can_xem) == ("nhieu", chon, True), g


def test_hai_o_mot_dam_mot_mo_o_cac_vi_tri_khac_nhau(mo_hinh):
    """Mọi cặp ô (6 cặp) × (đậm, mờ): luôn nhiều ô + cần xem, đáp án trả về đúng hai ô."""
    cap = [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]
    cases = [{a: 20, b: 200} for a, b in cap] + [{a: 200, b: 20} for a, b in cap]
    for (a, b), k in zip(cap + cap, doc(mo_hinh, cases)):
        assert k.trang_thai == "nhieu" and k.dap_an == a + b and k.can_xem


def test_du_40_cau_moi_cau_mot_dap_an_khac_nhau(mo_hinh):
    """Đủ 40 câu: câu q tô ô 'ABCD'[q % 4] đậm -> cả 40 câu đọc đúng, không câu nào cần xem."""
    cases = [{"ABCD"[q % 4]: 30} for q in range(1, 41)]
    kq = doc(mo_hinh, cases)
    assert len(kq) == 40
    for q, k in enumerate(kq, 1):
        assert (k.cau, k.dap_an, k.trang_thai, k.can_xem) == (q, "ABCD"[q % 4], "ro", False)


def test_du_40_cau_xen_ke_ro_mo_trong_nhieu(mo_hinh):
    """40 câu xen kẽ 4 loại, mỗi loại 10 câu: rõ / mờ / trống / nhiều ô -> trạng thái và cờ cần xem đúng từng câu."""
    mau = [({"B": 30}, "ro", False), ({"C": 200}, "mo", True), ({}, "trong", False), ({"A": 30, "D": 30}, "nhieu", True)]
    cases = [mau[(q - 1) % 4][0] for q in range(1, 41)]
    for q, k in enumerate(doc(mo_hinh, cases), 1):
        _, tt, xem = mau[(q - 1) % 4]
        assert (k.trang_thai, k.can_xem) == (tt, xem), q


@pytest.mark.parametrize("kich", [0.7, 1.0, 1.2])
def test_vung_to_du_to_la_ro(mo_hinh, kich):
    """Vết tô phủ từ 0,7r tới tràn ra ngoài viền (1,2r) vẫn là tô rõ."""
    anh = omr.nap_mau().copy()
    for q in range(1, 41):
        cx, cy = ANS["centers"][str(q)]["B"]
        cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(kich * R)), 30, -1)
    kq = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh), L, mo_hinh).cau
    assert all((k.trang_thai, k.dap_an, k.can_xem) == ("ro", "B", False) for k in kq)


@pytest.mark.xfail(strict=True, reason="LỖ HỔNG ĐÃ BIẾT (27/10/2026): chấm nhỏ đậm (bán kính 0,3r ≈ 11% diện tích lõi) "
                   "bị đọc là TRỐNG và không gắn cần xem. Cần luật 'vết nhỏ' – xem docs/ke_hoach_cai_tien_27-10.md mục 6.3; "
                   "khi sửa xong, bỏ xfail này.")
def test_cham_nho_dam_phai_can_xem(mo_hinh):
    anh = omr.nap_mau().copy()
    for q in range(1, 41):
        cx, cy = ANS["centers"][str(q)]["B"]
        cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(0.3 * R)), 30, -1)
    kq = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh), L, mo_hinh).cau
    assert all(k.can_xem or k.dap_an == "B" for k in kq)
