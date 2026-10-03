"""
preprocessing.py - Nắn phẳng ảnh phiếu chụp bằng điện thoại (Tuần 4, docs/ke_hoach_tuan4.md).

Mục tiêu: trả ảnh xám đã nắn đúng toạ độ layout.json (300 DPI), và KHÔNG BAO GIỜ trả ảnh nắn sai mà
báo OK – ảnh không nắn được phải bị từ chối có lý do (KetQuaTienXuLy.ok = False, ly_do = mã lỗi).

Tiến độ:
    Bước 2  load_image()                         – xong
    Bước 3  find_markers()  (chọn 4 marker theo hình học)
    Bước 4  warp(), verify() (chiều phiếu bằng nội dung, từ chối có lý do)
    Bước 5  normalize()     (khử bóng / cân bằng sáng)
    Bước 6  preprocess()    (API cho backend + thay align() trong các công cụ)

Quy tắc: file này KHÔNG import phép kiểm tra 2/3 của tools/eval_preprocessing.py (nếu dùng chung, lỗi của
phép đo trùng lỗi của hàm được đo và lỗi im lặng bị che mất). Toạ độ phiếu luôn đọc từ layout.json.
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()                  # cho phép Image.open() đọc HEIC/HEIF

TAG_ORIENTATION = 274                   # thẻ EXIF Orientation
DUOI_HEIF = {".heic", ".heif"}


class LoiDocAnh(Exception):
    """Không đọc / giải mã được file ảnh. preprocess() đổi thành ly_do = 'khong_doc_duoc'."""


@dataclass
class KetQuaTienXuLy:
    """Kết quả preprocess(path). Các trường được điền dần theo từng bước của kế hoạch Tuần 4.

    ly_do (mã lỗi khi ok = False): 'khong_doc_duoc', 'thieu_marker', 'marker_khong_dat', 'sai_huong',
    'khong_khop_bo_cuc', 'anh_mo', …
    """
    ok: bool = False
    ly_do: str = ""
    anh_nan: np.ndarray | None = None           # xám, đã nắn, chưa chuẩn hoá (Bước 3–4)
    anh_chuan_hoa: np.ndarray | None = None     # Bước 5
    marker: np.ndarray | None = None            # 4×2 float32: tâm TL, TR, BR, BL trên ảnh gốc, dưới pixel (Bước 3)
    huong_xoay: int | None = None               # 0 / 90 / 180 / 270 (Bước 4)
    blur_score: float | None = None
    # Hướng xoay ĐÃ ÁP khi đọc (1–8, truy vết ca như 0006). JPG: thẻ EXIF Orientation của file.
    # HEIC: giá trị GỐC lấy từ info["original_orientation"], vì pillow-heif tự xoay rồi đặt thẻ về 1.
    exif_orientation: int = 1


# ============================================================================ Bước 2: đọc ảnh
def ap_exif_orientation(a: np.ndarray, orientation: int) -> np.ndarray:
    """Xoay/lật điểm ảnh theo EXIF Orientation (1–8) để ảnh đúng chiều như khi xem.

    Quy ước EXIF: 6 = phải xoay 90° theo chiều kim đồng hồ để xem đúng, 8 = ngược chiều kim đồng hồ,
    3 = 180°; 2/4/5/7 là các ca có lật gương. np.rot90(a, k) xoay NGƯỢC chiều kim đồng hồ k lần.
    """
    if orientation == 2:
        a = a[:, ::-1]
    elif orientation == 3:
        a = a[::-1, ::-1]
    elif orientation == 4:
        a = a[::-1, :]
    elif orientation == 5:
        a = a.T
    elif orientation == 6:
        a = np.rot90(a, -1)
    elif orientation == 7:
        a = a[::-1, ::-1].T
    elif orientation == 8:
        a = np.rot90(a, 1)
    return np.ascontiguousarray(a)


def doc_anh(path) -> tuple[np.ndarray, int]:
    """(ảnh xám uint8 đúng chiều, giá trị EXIF Orientation đã áp). Ném LoiDocAnh nếu không đọc được.

    - Đọc byte bằng np.fromfile: cv2.imread không mở được đường dẫn có dấu tiếng Việt trên Windows.
    - JPG/PNG: giải mã bằng OpenCV, TẮT xoay EXIF tự động của OpenCV (IMREAD_IGNORE_ORIENTATION) rồi tự
      xoay bằng ap_exif_orientation() – để chỉ xoay đúng một lần và kiểm thử được. Không dùng Pillow để
      giải mã JPG: bộ giải mã và cách đổi sang xám khác OpenCV (lệch 1–2 mức xám).
    - HEIC/HEIF: Pillow + pillow-heif (tự xoay theo chiều gốc), rồi đổi xám bằng cv2.cvtColor (cùng công
      thức xám với OpenCV). Giá trị trả về là Orientation GỐC của file.
    """
    path = Path(path)
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as e:
        raise LoiDocAnh(f"không mở được file {path}: {e}") from e
    if data.size == 0:
        raise LoiDocAnh(f"file rỗng: {path}")

    if path.suffix.lower() in DUOI_HEIF:
        try:
            with Image.open(BytesIO(data.tobytes())) as im:
                # pillow-heif (libheif) ĐÃ xoay điểm ảnh và đặt EXIF Orientation về 1; giá trị gốc nằm ở
                # info["original_orientation"] (đo 03/10/2026: IMG_4214.HEIC gốc = 6, mở ra = 1).
                # exif_transpose vẫn gọi để an toàn với bản pillow-heif khác – với EXIF = 1 nó không làm gì.
                orientation = int(im.info.get("original_orientation") or im.getexif().get(TAG_ORIENTATION, 1))
                rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        except Exception as e:  # noqa: BLE001  (Pillow ném nhiều loại lỗi khác nhau)
            raise LoiDocAnh(f"không giải mã được HEIC {path}: {e}") from e
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), orientation

    gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
    if gray is None:
        raise LoiDocAnh(f"không giải mã được ảnh {path}")
    try:
        with Image.open(BytesIO(data.tobytes())) as im:      # chỉ đọc phần đầu file (EXIF), không giải mã
            orientation = int(im.getexif().get(TAG_ORIENTATION, 1))
    except Exception:  # noqa: BLE001  (định dạng Pillow không đọc được EXIF -> coi như không xoay)
        orientation = 1
    if orientation not in range(1, 9):
        orientation = 1
    return ap_exif_orientation(gray, orientation), orientation


def load_image(path) -> np.ndarray:
    """Ảnh xám uint8 đúng chiều theo EXIF (xem doc_anh()). Ném LoiDocAnh nếu không đọc được.

    Lưu ý: chiều *phiếu* không quyết định ở đây – EXIF có thể sai (ca 0006: iPhone ghi 3 thay vì 6).
    Chiều phiếu xác định bằng nội dung ở Bước 4.
    """
    return doc_anh(path)[0]


# ============================================================================ Bước 3–6 (chưa làm)
def find_markers(gray: np.ndarray, layout: dict):
    """Bước 3: lọc ứng viên, chọn 4 marker tạo tứ giác lồi tỉ lệ ~182:269 mm, cùng cỡ; tâm dưới pixel."""
    raise NotImplementedError("Bước 3")


def warp(gray: np.ndarray, marker: np.ndarray, layout: dict) -> np.ndarray:
    """Bước 4: perspective transform 4 tâm marker về toạ độ layout.json."""
    raise NotImplementedError("Bước 4")


def verify(anh_nan: np.ndarray, layout: dict) -> tuple[bool, str, int]:
    """Bước 4: kiểm tra ảnh nắn + xác định chiều phiếu bằng nội dung -> (ok, ly_do, huong_xoay)."""
    raise NotImplementedError("Bước 4")


def normalize(anh_nan: np.ndarray) -> np.ndarray:
    """Bước 5: khử bóng / cân bằng sáng."""
    raise NotImplementedError("Bước 5")


def preprocess(path, layout: dict) -> KetQuaTienXuLy:
    """Bước 6: đọc ảnh -> tìm marker -> nắn -> kiểm tra -> chuẩn hoá. Không bao giờ ném lỗi: lỗi -> ok=False."""
    raise NotImplementedError("Bước 6")
