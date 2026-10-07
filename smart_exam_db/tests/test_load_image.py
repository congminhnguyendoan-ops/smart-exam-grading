"""load_image(): EXIF Orientation, đường dẫn Unicode, file lỗi. Không cần data/ (ảnh thử tự tạo trong tmp_path)."""
import numpy as np
import pytest
from PIL import Image

from cv_engine.preprocessing import LoiDocAnh, load_image, nap_layout, preprocess

# Ảnh "hiển thị đúng" D (cao 60 × rộng 40, không đối xứng); ảnh lưu = D biến đổi ngược, kèm thẻ EXIF.
# EXIF 3: xoay 180° khi hiển thị; 6: xoay 90° theo chiều kim đồng hồ; 8: xoay 90° ngược chiều kim đồng hồ.
LUU = {1: lambda d: d, 3: lambda d: np.rot90(d, 2), 6: lambda d: np.rot90(d, 1), 8: lambda d: np.rot90(d, -1)}


def anh_mau() -> np.ndarray:
    d = np.full((60, 40), 220, np.uint8)
    d[:20, :15] = 20                    # khối đen góc trên trái
    d[45:, 30:] = 120                   # khối xám góc dưới phải
    return d


def ghi_jpg_exif(path, a: np.ndarray, orientation: int) -> None:
    exif = Image.Exif()
    exif[274] = orientation
    Image.fromarray(np.ascontiguousarray(a)).save(path, quality=98, exif=exif)


@pytest.mark.parametrize("orientation", [1, 3, 6, 8])
def test_exif_ra_dung_chieu(tmp_path, orientation):
    d = anh_mau()
    p = tmp_path / f"exif_{orientation}.jpg"
    ghi_jpg_exif(p, LUU[orientation](d), orientation)
    g = load_image(p)
    assert g.dtype == np.uint8 and g.shape == d.shape
    mad = float(np.mean(np.abs(g.astype(int) - d.astype(int))))
    sai = [float(np.mean(np.abs(g.astype(int) - np.rot90(d, 2).astype(int))))]     # chiều sai cùng cỡ: xoay 180°
    assert mad < 5, f"EXIF {orientation}: lệch {mad:.2f} mức xám so với chiều đúng"
    assert min(sai) > 30


def test_duong_dan_unicode(tmp_path):
    p = tmp_path / "ảnh thử có dấu" / "phiếu_đề_101.jpg"
    p.parent.mkdir()
    ghi_jpg_exif(p, anh_mau(), 1)
    assert load_image(p).shape == (60, 40)


def test_file_khong_ton_tai_va_hong(tmp_path):
    with pytest.raises(LoiDocAnh):
        load_image(tmp_path / "khong_co.jpg")
    hong = tmp_path / "hong.jpg"
    hong.write_bytes(b"day khong phai anh JPEG")
    with pytest.raises(LoiDocAnh):
        load_image(hong)


def test_preprocess_file_loi_tra_ma_khong_doc_duoc(tmp_path):
    kq = preprocess(tmp_path / "khong_co.jpg", nap_layout("phieu"))
    assert (kq.ok, kq.ly_do, kq.anh_nan, kq.anh_chuan_hoa) == (False, "khong_doc_duoc", None, None)
