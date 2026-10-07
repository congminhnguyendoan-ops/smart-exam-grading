"""Kiểm thử công cụ đánh giá độc lập tools/eval_omr.py (Tuần 5, Phần A mốc A4)."""
import ast
import sys

import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import eval_omr as E  # noqa: E402

CAM = {"dinh_vi", "dinh_vi_khoi", "dac_trung_o", "du_doan", "ap_luat_cau", "ap_luat_cot", "TEN_DAC_TRUNG", "thang_anh",
       "LOP_CAU", "LOP_BUBBLE", "KHOI_DIEM_MIN", "HANG_DIEM_MIN", "LAN_CAN_MM"}


def test_eval_chi_dung_api_cong_khai_cua_omr():
    """Độc lập: eval_omr.py chỉ được dùng omr.doc_phieu / omr.nap_mo_hinh; không import công cụ huấn luyện."""
    cay = ast.parse((ROOT / "tools" / "eval_omr.py").read_text(encoding="utf-8"))
    thuoc_tinh = {n.attr for n in ast.walk(cay) if isinstance(n, ast.Attribute)
                  and isinstance(n.value, ast.Name) and n.value.id == "omr"}
    assert thuoc_tinh <= {"doc_phieu", "nap_mo_hinh"}, thuoc_tinh
    ten = {a.name for n in ast.walk(cay) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    mod = {n.module for n in ast.walk(cay) if isinstance(n, ast.ImportFrom)}
    assert not (ten & CAM) and not ({"omr_du_lieu", "huan_luyen_omr"} & (ten | mod))


def test_giai_ma_nhan():
    assert E.giai_ma("-") == {} and E.giai_ma("B") == {"B": "filled"} and E.giai_ma("c") == {"C": "faint"}
    assert E.giai_ma("AC") == {"A": "filled", "C": "filled"}
    assert [E.trang_thai_that(E.giai_ma(c)) for c in ("-", "B", "c", "AC")] == ["trong", "ro", "mo", "nhieu"]


def _c(that, that_o, doc, doc_o, can_xem):
    return {"that": that, "that_o": that_o, "doc": doc, "doc_o": doc_o, "can_xem": str(can_xem)}


@pytest.mark.parametrize("r,mong", [
    (_c("ro", "A", "ro", "A", 0), "dung_chac_chan"),
    (_c("ro", "A", "ro", "B", 0), "loi_nang"),                     # sai đáp án, không cần xem
    (_c("mo", "C", "trong", "", 0), "loi_nang"),                   # vết mờ đọc thành trống (★Q1)
    (_c("trong", "", "ro", "D", 0), "loi_nang"),                   # trống đọc thành có tô
    (_c("mo", "C", "ro", "C", 0), "loi_nhe"),
    (_c("ro", "A", "mo", "A", 1), "can_xem_thua"),
    (_c("trong", "", "trong", "", 1), "can_xem_thua"),
    (_c("mo", "C", "mo", "C", 1), "can_xem_can_thiet"),
    (_c("nhieu", "AC", "nhieu", "CA", 1), "can_xem_can_thiet"),
    (_c("ro", "A", "nhieu", "AB", 1), "can_xem_thua_doc_sai"),
    (_c("trong", "", "trong", "", 0), "dung_chac_chan"),
])
def test_xep_loai_cau(r, mong):
    assert E.loai_cau(r) == mong


@pytest.mark.parametrize("that,doc,can_xem,mong", [("3", "3", 0, "dung_chac_chan"), ("3", "8", 0, "loi_nang"),
                                                   ("-", "?", 1, "can_xem_can_thiet"), ("-", "5", 0, "loi_nang"),
                                                   ("3", "3", 1, "can_xem_thua"), ("3", "?", 1, "can_xem_thua_doc_sai")])
def test_xep_loai_cot(that, doc, can_xem, mong):
    assert E.loai_cot({"that": that, "doc": doc, "can_xem": str(can_xem)}) == mong


def test_clopper_pearson():
    assert E.cp_tren(0, 2744) == pytest.approx(1 - 0.025 ** (1 / 2744), rel=1e-3)
    assert 0.3 < E.cp_tren(1, 5) < 0.75


def test_chan_val_test():
    with pytest.raises(SystemExit):
        E.ds_anh("test", True)
    with pytest.raises(SystemExit):
        E.ds_anh("val", False)


def test_nhan_doi_chieu_cell_labels():
    """Bộ đọc nhãn riêng của eval khớp cell_labels.csv trên toàn train (lệch thì doc_nhan dừng)."""
    can_file(ROOT / "data" / "ground_truth.csv", ROOT / "data" / "cell_labels.csv")
    n = E.doc_nhan(set(range(1, 29)))
    assert len(n) == 28 and n["0001"]["sbd"] == "06238-"
