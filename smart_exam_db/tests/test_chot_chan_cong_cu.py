"""Chốt chặn tập test trong các công cụ (Tuần 4, Bước 6): không cờ --xac-nhan-test thì dừng / bỏ qua TRƯỚC khi đọc ảnh.
Mọi hàm đọc / nắn ảnh bị thay bằng hàm ném lỗi -> nếu công cụ chạm vào ảnh test, test fail."""
import sys

import pytest
from conftest import ANSWER_SHEET_DIR, ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ANSWER_SHEET_DIR))

import check_labels  # noqa: E402
import check_photos  # noqa: E402
import prepare_photos  # noqa: E402
from cv_engine.tap_du_lieu import ChamTapTest  # noqa: E402


def cam_doc(*_a, **_k):
    raise AssertionError("công cụ đã định đọc / nắn ảnh – chốt chặn tập test không hoạt động")


def test_audit_tat_ca_khong_co_co_bi_chan(monkeypatch):
    can_file(ANSWER_SHEET_DIR / "output" / "ground_truth.csv")
    monkeypatch.setattr(check_labels, "nan_anh", cam_doc)
    monkeypatch.setattr(check_labels, "render_pdf_page", cam_doc)
    with pytest.raises(ChamTapTest, match="0035"):
        check_labels.cmd_audit(["--split", "tat_ca", "--out", "khong_duoc_ghi"])


def test_audit_dev_khong_dung_phieu_test(monkeypatch, tmp_path):
    """Chế độ dev: danh sách phiếu đưa vào vòng quét chỉ có 0001–0034 (dừng ở ảnh đầu tiên để test chạy nhanh)."""
    can_file(ANSWER_SHEET_DIR / "output" / "ground_truth.csv")
    da_xem = []

    def ghi_va_dung(path, loai):
        da_xem.append(path.stem)
        raise KeyboardInterrupt
    monkeypatch.setattr(check_labels, "nan_anh", ghi_va_dung)
    monkeypatch.setattr(check_labels, "render_pdf_page", lambda *a, **k: None)
    with pytest.raises(KeyboardInterrupt):
        check_labels.cmd_audit(["--out", str(tmp_path)])
    assert da_xem and da_xem[0].startswith("0001_")


def test_check_labels_cau_le_bi_chan(monkeypatch):
    monkeypatch.setattr(check_labels, "nan_anh", cam_doc)
    monkeypatch.setattr(sys, "argv", ["check_labels.py", "0001:3", "0035:1"])
    with pytest.raises(SystemExit, match="TEST"):
        check_labels.main()


def test_preview_tat_ca_bi_chan(monkeypatch, tmp_path):
    (tmp_path / "mapping.csv").write_text("order,old_name,heic_name,capture_time,time_source,new_name,note\n"
                                          "1,IMG_1.jpg,IMG_1.HEIC,,,0001_C1.jpg,\n2,IMG_2.jpg,IMG_2.HEIC,,,0036_C4.jpg,\n",
                                          encoding="utf-8-sig")
    monkeypatch.setattr(prepare_photos, "preview_images", cam_doc)
    with pytest.raises(ChamTapTest, match="0036_C4"):
        prepare_photos.build_preview(tmp_path, "tat_ca", False)


def test_check_photos_bo_qua_anh_test(monkeypatch, tmp_path, capsys):
    src = tmp_path / "raw"
    src.mkdir()
    (src / "0035_C1.jpg").write_bytes(b"khong phai anh")
    monkeypatch.setattr(check_photos, "preprocess", cam_doc)
    monkeypatch.setattr(sys, "argv", ["check_photos.py", "--dir", str(src), "--out", str(tmp_path / "out")])
    check_photos.main()
    assert "BỎ QUA 1 ảnh tập TEST" in capsys.readouterr().out


def test_check_photos_khong_ghi_vao_thu_muc_goc(monkeypatch, tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    monkeypatch.setattr(sys, "argv", ["check_photos.py", "--dir", str(src), "--out", str(src / "_aligned")])
    with pytest.raises(SystemExit, match="Không ghi vào thư mục ảnh gốc"):
        check_photos.main()
