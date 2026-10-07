"""Đường ống I/O cho Bước 7 (đánh giá cuối trên tập test, đăng ký trước) – KHÔNG đọc ảnh test nào.
finalize --split test cấm --ke-thua; run test chỉ một lần; tên file dev giữ nguyên; HTML xem MÙ không lộ kết luận máy /
số đo; cận trên Clopper–Pearson; audit --split test cần cờ."""
import argparse
import sys

import numpy as np
import pytest
from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import check_labels  # noqa: E402
import eval_preprocessing as ep  # noqa: E402
from cv_engine.tap_du_lieu import ChamTapTest  # noqa: E402


def cam(*_a, **_k):
    raise AssertionError("đã định đọc dữ liệu – chốt chặn không hoạt động")


def test_finalize_test_cam_ke_thua(monkeypatch):
    monkeypatch.setattr(ep, "kiem_ke_thua", cam)
    with pytest.raises(SystemExit, match="không được --ke-thua"):
        ep.cmd_finalize(argparse.Namespace(phuong_phap="v6_api", split="test", ke_thua="v4_verify"))


def test_run_test_chi_mot_lan(monkeypatch, tmp_path):
    monkeypatch.setattr(ep, "EVAL_DIR", tmp_path)
    monkeypatch.setattr(ep, "list_images", cam)
    monkeypatch.setattr(ep, "nap_mau", cam)
    (tmp_path / "v6_api").mkdir()
    (tmp_path / "v6_api" / "diem_test.csv").write_text("anh\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="MỘT LẦN"):
        ep.cmd_run(argparse.Namespace(phuong_phap="v6_api", split="test", xac_nhan_test=True))
    with pytest.raises(SystemExit, match="--xac-nhan-test"):
        ep.cmd_run(argparse.Namespace(phuong_phap="v6_api", split="test", xac_nhan_test=False))


def test_ten_file_dev_giu_nguyen():
    assert ep.ten_xem("dev") == {"html": "xem_bang_mat.html", "csv": "xem_bang_mat.csv", "can": "can_xem.html"}
    assert ep.ten_xem("test") == {"html": "xem_bang_mat_test.html", "csv": "xem_bang_mat_test.csv",
                                  "can": "can_xem_test.html"}


def test_html_mu_khong_lo_ket_luan(tmp_path):
    r = {"anh": "0035_C1", "dieu_kien": "C1", "tra_anh": "co", "ket_luan_tu_dong": "sai", "ly_do_tu_dong": "trượt rõ: x",
         "khop_net": 0.123456, "lech_max_mm": 9.8765, "lech_trungvi_mm": 4.321, "giay": 0.777, "so_ung_vien": 5,
         "huong_xoay": 90, "huong_dung": "", "S0": 0.4242}
    p = tmp_path / "x.html"
    ep.viet_html([r, {**r, "anh": "0035_C2", "tra_anh": "khong", "ly_do": "thieu_marker"}], p, "v6_api", "test", mu=True)
    s = p.read_text(encoding="utf-8")
    for lo in ("0.123", "9.87", "4.32", "0.777", "0.42", "trượt", "ket_luan_tu_dong", "khop_net", "tự động", "thieu_marker",
               "90°"):
        assert lo not in s, f"HTML mù lộ '{lo}'"
    assert "0035_C1_chong_nho.jpg" in s and "KHÔNG trả ảnh nắn" in s


def test_anh_chong_mu_khong_ve_so_do():
    anh = np.full((60, 80), 200, np.uint8)
    mau = np.zeros_like(anh)
    mau[30, :] = 1
    tiles = [{"box": (0, 0, 40, 30), "dx": 3.0, "dy": 1.0, "tin_cay": True}]
    assert np.array_equal(ep.anh_chong(anh, mau, tiles, mu=True), ep.anh_chong(anh, mau, []))
    assert not np.array_equal(ep.anh_chong(anh, mau, tiles), ep.anh_chong(anh, mau, []))


@pytest.mark.parametrize("k, n, tren", [(0, 12, 0.2646), (0, 78, 0.0462), (1, 10, 0.4450), (12, 12, 1.0)])
def test_clopper_pearson(k, n, tren):
    assert ep.cp_tren(k, n) == pytest.approx(tren, abs=5e-4)


def test_audit_split_test_can_co(monkeypatch):
    monkeypatch.setattr(check_labels, "nan_anh", cam)
    monkeypatch.setattr(check_labels, "render_pdf_page", cam)
    with pytest.raises(ChamTapTest, match="0035"):
        check_labels.cmd_audit(["--split", "test", "--out", "khong_duoc_ghi"])
