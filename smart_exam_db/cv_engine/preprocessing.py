"""
preprocessing.py - Nắn phẳng ảnh phiếu chụp bằng điện thoại (Tuần 4, docs/ke_hoach_tuan4.md).

Mục tiêu: trả ảnh xám đã nắn đúng toạ độ layout.json (300 DPI), và KHÔNG BAO GIỜ trả ảnh nắn sai mà
báo OK – ảnh không nắn được phải bị từ chối có lý do (KetQuaTienXuLy.ok = False, ly_do = mã lỗi).

Tiến độ:
    Bước 2  load_image()                         – xong
    Bước 3b tim_ung_vien_marker()                – lọc + xếp hạng ứng viên marker
    Bước 3c find_markers()  (chọn 4 marker theo hình học)
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


# ============================================================================ Bước 3b: ứng viên marker
# Căn cứ mọi ngưỡng: `python tools/marker_that.py khao-sat` (312 marker thật / 78 ảnh dev,
# data/_eval/marker_that/dac_trung_moi_dev.csv). Giá trị "xấu nhất" ghi kèm là của marker thật.
NEN_THU_NHO = 4             # ước lượng nền trên ảnh thu nhỏ 1/4 (nền giấy thay đổi chậm) – nhanh hơn ~16 lần
NEN_CUA_SO = 12             # cạnh cửa sổ lấy max nền = max(H, W) / 12 (≈ 336 px ở 4032 px) – xem khao-sat
MUC_TI_LE = 0.5             # điểm ảnh tối hơn 50% nền giấy cục bộ = mực
DT_MIN, DT_MAX = 1e-4, 5e-3     # diện tích / diện tích ảnh – chỉ chặn vết vụn / vết khổng lồ
DAC_MIN = 0.80              # độ đặc = diện tích / bao lồi; xấu nhất 0,969 (0014_C2), biên 0,17
CANH_MIN = 0.30             # cạnh ngắn / cạnh dài của minAreaRect; xấu nhất 0,568 (0015_C3), biên 0,27 – biên lớn
                            # CỐ Ý, chừa cho marker bị khung hình cắt (dẹt hơn) lọt tới 3c quyết định
TU_GIAC_MIN = 0.83          # độ tứ giác; xấu nhất 0,938 (0014_C2), biên 0,108. Hình tròn/elip ≈ 0,68–0,78 (thử
                            # trên hình vẽ), hình vuông qua phối cảnh 0,45–1 vẫn 0,94–1,00
VIEN_HE_SO = 0.5            # vành quanh hộp bao rộng 0,5 × cạnh hộp (marker có ≥ 10 mm giấy trắng xung quanh)


@dataclass
class UngVienMarker:
    """Một vết mực có thể là marker. Toạ độ trên ảnh gốc (đã áp EXIF), pixel."""
    x: float                    # tâm (centroid điểm ảnh) – chỉ để so khớp; tâm dưới pixel tính ở 3c
    y: float
    dien_tich: int              # số điểm ảnh mực
    hop: tuple                  # (x, y, w, h) hộp bao
    dac: float                  # diện tích / diện tích bao lồi
    canh: float                 # cạnh ngắn / cạnh dài của minAreaRect
    tu_giac: float              # diện tích contour / diện tích tứ giác bao (approxPolyN 4 cạnh) – ≤ 1
    vuong: float                # diện tích / minAreaRect (chỉ báo cáo – bị phối cảnh làm giảm)
    muc_vien: float             # tỉ lệ điểm mực trong vành quanh hộp bao
    den_trong: float            # trung vị (xám / nền) ở lõi vết – càng nhỏ càng đen
    cham_mep: bool              # hộp bao chạm mép ảnh (marker có thể bị cắt, tâm lệch)
    diem: float = 0.0           # điểm xếp hạng = tu_giac × (1 − muc_vien)


def uoc_luong_nen(gray: np.ndarray, cua_so: int = NEN_CUA_SO) -> np.ndarray:
    """Độ sáng nền giấy cục bộ (float32, cùng cỡ ảnh): max trong cửa sổ max(H, W)/cua_so rồi làm mượt.
    Cửa sổ phải lớn hơn marker nhiều lần, nếu không tâm marker không 'thấy' giấy và marker chỉ còn vòng viền."""
    H, W = gray.shape
    nho = cv2.resize(gray, (W // NEN_THU_NHO, H // NEN_THU_NHO), interpolation=cv2.INTER_AREA)
    k = max(H, W) // cua_so // NEN_THU_NHO | 1
    nen = cv2.dilate(nho, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    nen = cv2.GaussianBlur(nen, (k, k), 0)
    return cv2.resize(nen, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)


def do_vet_muc(gray: np.ndarray, cua_so: int = NEN_CUA_SO) -> list[UngVienMarker]:
    """Mọi vết mực có diện tích trong [DT_MIN, DT_MAX] kèm đặc trưng – CHƯA lọc theo hình dạng.
    tim_ung_vien_marker() lọc + xếp hạng; khảo sát ngưỡng (tools/marker_that.py khao-sat) dùng thẳng hàm này."""
    H, W = gray.shape
    nen = np.maximum(uoc_luong_nen(gray, cua_so), 1.0)
    ti_le = gray.astype(np.float32) / nen
    muc = (ti_le < MUC_TI_LE).astype(np.uint8)
    n, lab, st, ct = cv2.connectedComponentsWithStats(muc, connectivity=8)
    tich_phan = cv2.integral(muc)                       # tổng điểm mực trong hình chữ nhật bất kỳ, O(1)

    def tong(x0, y0, x1, y1):
        return int(tich_phan[y1, x1] - tich_phan[y0, x1] - tich_phan[y1, x0] + tich_phan[y0, x0])

    out = []
    for i in np.flatnonzero((st[:, 4] >= DT_MIN * H * W) & (st[:, 4] <= DT_MAX * H * W)):
        if i == 0:
            continue
        x, y, w, h, a = (int(v) for v in st[i])
        vet = (lab[y:y + h, x:x + w] == i).astype(np.uint8)
        cnts, _ = cv2.findContours(vet, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cnts, key=cv2.contourArea)
        hull = cv2.convexHull(c).astype(np.float32)
        tg = cv2.approxPolyN(hull, 4, epsilon_percentage=-1, ensure_convex=True)
        a_c = cv2.contourArea(c)
        _, (rw, rh), _ = cv2.minAreaRect(c)
        # vành: hộp bao nới mỗi phía 0,5 × cạnh hộp (cắt theo mép ảnh), trừ hộp bao
        px, py = round(VIEN_HE_SO * w), round(VIEN_HE_SO * h)
        x0, y0, x1, y1 = max(0, x - px), max(0, y - py), min(W, x + w + px), min(H, y + h + py)
        dt_vien = (x1 - x0) * (y1 - y0) - w * h
        muc_vien = (tong(x0, y0, x1, y1) - tong(x, y, x + w, y + h)) / max(dt_vien, 1)
        # lõi: điểm cách biên vết > 25% cạnh ngắn (distanceTransform – nhanh hơn erode nhân lớn); rỗng thì lấy cả vết
        loi = cv2.distanceTransform(np.pad(vet, 1), cv2.DIST_L2, 3)[1:-1, 1:-1] > 0.25 * min(w, h)
        if not loi.any():
            loi = vet
        out.append(UngVienMarker(
            x=float(ct[i][0]), y=float(ct[i][1]), dien_tich=a, hop=(x, y, w, h),
            dac=a / max(cv2.contourArea(hull), 1.0), canh=min(rw, rh) / max(rw, rh, 1.0),
            tu_giac=a_c / max(cv2.contourArea(tg), 1.0), vuong=a / max(rw * rh, 1.0),
            muc_vien=muc_vien, den_trong=float(np.median(ti_le[y:y + h, x:x + w][loi > 0])),
            cham_mep=bool(x == 0 or y == 0 or x + w == W or y + h == H)))
    for u in out:
        u.diem = u.tu_giac * (1.0 - u.muc_vien)
    return out


def qua_loc(u: UngVienMarker) -> bool:
    """Ngưỡng lọc hình dạng của Bước 3b (diện tích đã lọc trong do_vet_muc)."""
    return u.dac >= DAC_MIN and u.canh >= CANH_MIN and u.tu_giac >= TU_GIAC_MIN


def tim_ung_vien_marker(gray: np.ndarray) -> list[UngVienMarker]:
    """Bước 3b: ứng viên marker, xếp theo điểm giảm dần. Giữ CẢ marker của tờ khác lọt khung –
    phân biệt tờ chính là việc của bước chọn bộ 4 theo hình học (3c)."""
    return sorted((u for u in do_vet_muc(gray) if qua_loc(u)), key=lambda u: -u.diem)


# ============================================================================ Bước 3c–6 (chưa làm)
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
