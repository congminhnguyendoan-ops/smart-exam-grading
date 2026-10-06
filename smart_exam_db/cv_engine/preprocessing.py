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
import itertools
from dataclasses import dataclass, field
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
    contour: np.ndarray | None = field(default=None, repr=False)    # N×2 int, toạ độ ảnh
    dinh: np.ndarray | None = field(default=None, repr=False)       # 4×2 float: đỉnh dưới pixel (Bước 3c)
    tam: tuple | None = None    # tâm dưới pixel (Bước 3c, tam_phoi_canh) – tâm dùng để tính H


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
            cham_mep=bool(x == 0 or y == 0 or x + w == W or y + h == H),
            contour=c.reshape(-1, 2) + np.array([x, y])))
    for u in out:
        u.diem = u.tu_giac * (1.0 - u.muc_vien)
    return out


def qua_loc(u: UngVienMarker) -> bool:
    """Ngưỡng lọc hình dạng của Bước 3b (diện tích đã lọc trong do_vet_muc)."""
    return u.dac >= DAC_MIN and u.canh >= CANH_MIN and u.tu_giac >= TU_GIAC_MIN


def tim_ung_vien_marker(gray: np.ndarray) -> list[UngVienMarker]:
    """Bước 3b: ứng viên marker, xếp theo điểm giảm dần. Giữ CẢ marker của tờ khác lọt khung –
    phân biệt tờ chính là việc của bước chọn bộ 4 theo hình học (3c). Mỗi ứng viên có đỉnh + tâm dưới pixel."""
    out = sorted((u for u in do_vet_muc(gray) if qua_loc(u)), key=lambda u: -u.diem)
    for u in out:
        u.dinh = dinh_duoi_pixel(u.contour)
        u.tam = tam_phoi_canh(u.contour, u.dinh)
    return out


# ============================================================================ Bước 3c: chọn bộ 4 theo hình học
# Căn cứ ngưỡng: `python tools/marker_that.py khao-sat-bo-4` (bộ 4 thật của 78 ảnh dev vs mọi bộ 4 khác trong top-K).
K_UNG_VIEN = 10             # chỉ xét K ứng viên điểm cao nhất; hạng lớn nhất của marker thật ở 3b = 5 -> max(2×5, 5+4)
PHOI_CANH_MIN = 0.50        # K2 độ phối cảnh 4 tâm; bộ thật xấu nhất 0,597 (0015_C3), biên 0,097
CO_MIN, CO_MAX = 0.61, 1.40     # K3 diện tích marker / ô 8 mm dự đoán từ H⁻¹; bộ thật 0,767 (0014_C2) – 1,117
                                # (0033_C1), biên ×1,26 / ×1,25
DINH_MAX_MM = 2.0           # K4 đỉnh marker chiếu qua H lệch đỉnh ô 8 mm layout (mm); bộ thật xấu nhất 1,28 (0014_C2,
                            # giấy cong), biên 0,72; bộ khác tốt nhất (không xét K2/K3) 2,44 (0030_C3); cách gán
                            # dọc/ngang sai của bộ thật ≥ 2,43 (0031_C3) -> bị loại
CAT_DAU_CANH = 0.15         # bỏ 15% mỗi đầu cạnh (gần góc, bị bo tròn do mờ) khi khớp đường thẳng
GOC = ("tl", "tr", "br", "bl")


def theo_vong(pts: np.ndarray) -> np.ndarray:
    """Chỉ số 4 điểm sắp theo góc quanh trọng tâm, bắt đầu từ góc −π (điểm trên-trái của ảnh đứng thẳng)."""
    c = pts.mean(axis=0)
    return np.argsort(np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0]))


def _giao(l1, l2):
    """Giao hai đường thẳng dạng (vx, vy, x0, y0) của cv2.fitLine."""
    (a1, b1, x1, y1), (a2, b2, x2, y2) = l1, l2
    d = a1 * b2 - b1 * a2
    if abs(d) < 1e-9:
        return None
    t = ((x2 - x1) * b2 - (y2 - y1) * a2) / d
    return np.array([x1 + t * a1, y1 + t * b1])


def dinh_duoi_pixel(contour: np.ndarray) -> np.ndarray:
    """4 đỉnh dưới pixel của vết hình tứ giác: tứ giác thô (approxPolyN) -> gán điểm contour cho cạnh gần nhất, bỏ
    CAT_DAU_CANH mỗi đầu -> fitLine từng cạnh -> giao các cạnh kề. Cạnh thiếu điểm thì giữ đỉnh thô."""
    p = contour.astype(np.float32)
    q = cv2.approxPolyN(cv2.convexHull(p), 4, epsilon_percentage=-1, ensure_convex=True).reshape(-1, 2)
    a, b = q, np.roll(q, -1, axis=0)                       # cạnh i: q[i] -> q[i+1]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-9)
    t = ((p[:, None, :] - a[None]) * ab[None]).sum(2) / L2[None]          # N×4: vị trí chiếu trên từng cạnh
    hinh_chieu = a[None] + np.clip(t, 0, 1)[..., None] * ab[None]
    kc = np.linalg.norm(p[:, None, :] - hinh_chieu, axis=2)
    canh = kc.argmin(1)
    duong = []
    for i in range(4):
        m = (canh == i) & (t[:, i] > CAT_DAU_CANH) & (t[:, i] < 1 - CAT_DAU_CANH)
        duong.append(cv2.fitLine(p[m], cv2.DIST_HUBER, 0, 0.01, 0.01).ravel() if m.sum() >= 5 else None)
    dinh = q.astype(np.float64).copy()
    for i in range(4):                                     # đỉnh i = giao cạnh i−1 và cạnh i
        l1, l2 = duong[i - 1], duong[i]
        g = _giao(l1, l2) if l1 is not None and l2 is not None else None
        if g is not None and np.linalg.norm(g - q[i]) < 0.25 * np.sqrt(L2.max()):
            dinh[i] = g
    return dinh


def tam_cheo(dinh: np.ndarray) -> tuple:
    """Giao hai đường chéo = ảnh đúng của tâm ô vuông qua phép chiếu (centroid bị kéo về phía gần máy)."""
    g = _giao((*(dinh[2] - dinh[0]), *dinh[0]), (*(dinh[3] - dinh[1]), *dinh[1]))
    return tuple(map(float, g if g is not None else dinh.mean(axis=0)))


def tam_phoi_canh(contour: np.ndarray, dinh: np.ndarray) -> tuple:
    """Centroid trong hệ đã nắn phẳng cục bộ: H_loc đưa 4 đỉnh về ô vuông đơn vị, lấy trọng tâm các điểm ảnh của vết
    (trọng số = định thức Jacobi, tức diện tích thật trên mặt phiếu), rồi chiếu ngược. Đỉnh chỉ dùng để khử phối
    cảnh (sai số đỉnh ảnh hưởng bậc hai); vị trí do mọi điểm ảnh quyết định (dưới pixel như centroid)."""
    x, y, w, h = cv2.boundingRect(contour.astype(np.int32))
    m = np.zeros((h, w), np.uint8)
    cv2.drawContours(m, [(contour - [x, y]).astype(np.int32).reshape(-1, 1, 2)], -1, 1, -1)
    ys, xs = np.nonzero(m)
    P = np.stack([xs + x, ys + y], 1).astype(np.float64)
    Hl = cv2.getPerspectiveTransform(dinh.astype(np.float32), np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]))
    Q = cv2.perspectiveTransform(P[None], Hl)[0]
    wz = Hl[2, 0] * P[:, 0] + Hl[2, 1] * P[:, 1] + Hl[2, 2]
    J = np.abs(np.linalg.det(Hl) / wz ** 3)
    c = (Q * J[:, None]).sum(0) / J.sum()
    return tuple(map(float, cv2.perspectiveTransform(c[None, None], np.linalg.inv(Hl))[0, 0]))


def _o_layout(layout: dict) -> tuple[np.ndarray, np.ndarray]:
    """(tâm 4×2 theo GOC, đỉnh 4×4×2 của ô marker) trên trang layout (px @ dpi)."""
    tam = np.array([layout["markers"]["centers"][g] for g in GOC], np.float64)
    h = layout["markers"]["size"] / 2
    o = np.array([[-h, -h], [h, -h], [h, h], [-h, h]])
    return tam, tam[:, None, :] + o[None]


def do_bo_4(bo: list, layout: dict) -> dict:
    """Đo một bộ 4 ứng viên với CẢ 4 cách gán góc xoay vòng (theo thứ tự quanh trọng tâm).
    K1 lồi, K2 độ phối cảnh (không phụ thuộc cách gán); mỗi cách gán: H (4 tâm -> layout), K3 cỡ, K4 đỉnh (mm)."""
    tam = np.array([u.tam for u in bo], np.float64)
    o = theo_vong(tam)
    q = tam[o]
    d = lambda i, j: float(np.hypot(*(q[i] - q[j])))
    tl = [d(0, 1) / d(3, 2), d(0, 3) / d(1, 2)]
    ket = {"loi": bool(cv2.isContourConvex(q.reshape(-1, 1, 2).astype(np.float32))),
           "phoi_canh": min(min(r, 1 / r) for r in tl), "cach_gan": []}
    tam_L, o_L = _o_layout(layout)
    mm = 25.4 / layout["dpi"]
    for r in range(4):
        idx = [int(o[(k + r) % 4]) for k in range(4)]     # idx[k] = ứng viên gán cho góc GOC[k]
        H = cv2.getPerspectiveTransform(tam[idx].astype(np.float32), tam_L.astype(np.float32))
        Hi = np.linalg.inv(H)
        co, dinh = [], []
        for k, j in enumerate(idx):
            du_doan = cv2.perspectiveTransform(o_L[k][None].astype(np.float64), Hi)[0]
            co.append(bo[j].dien_tich / max(cv2.contourArea(du_doan.astype(np.float32)), 1.0))
            m = cv2.perspectiveTransform(bo[j].dinh[None].astype(np.float64), H)[0]
            kc = np.linalg.norm(m[:, None, :] - o_L[k][None], axis=2)
            dinh.append(kc.min(1).max() * mm)               # mỗi đỉnh đo được -> đỉnh layout gần nhất
        ket["cach_gan"].append({"xoay": r, "idx": idx, "H": H, "co_min": min(co), "co_max": max(co),
                                "dinh_mm": max(dinh)})
    return ket


def chon_cach_gan(ket: dict) -> tuple[dict, float]:
    """Cách gán có sai số K4 nhỏ nhất. Layout đối xứng qua 180° nên cách gán r và r+2 cho sai số gần như nhau:
    3c chỉ quyết DỌC/NGANG (cặp {0,2} hay {1,3}); trong cặp lấy r = 0 hoặc 1 (TL gần điểm trên-trái của ảnh).
    Phân biệt 0° với 180° là việc của Bước 4 (bằng nội dung). Trả (cách gán, sai số K4 của cặp vuông góc)."""
    cg = ket["cach_gan"]
    cap = [min(cg[p]["dinh_mm"], cg[p + 2]["dinh_mm"]) for p in (0, 1)]
    p = int(np.argmin(cap))
    return cg[p], cap[1 - p]


def qua_bo_4(ket: dict, g: dict) -> bool:
    return (ket["loi"] and ket["phoi_canh"] >= PHOI_CANH_MIN and g["co_min"] >= CO_MIN and g["co_max"] <= CO_MAX
            and g["dinh_mm"] <= DINH_MAX_MM)


def find_markers(gray: np.ndarray, layout: dict, uv: list | None = None):
    """Bước 3c: chọn 4 marker -> (tâm 4×2 float32 theo TL, TR, BR, BL | None, ly_do, chi_tiet).
    Đúng 1 bộ 4 đạt K1–K4 -> chọn. 0 bộ -> 'thieu_marker' (< 4 ứng viên) / 'marker_khong_dat'. ≥ 2 bộ -> từ chối,
    không chọn bừa: 'nhieu_phieu' nếu có 2 bộ đạt không chung ứng viên nào, ngược lại 'marker_mo_ho'.
    Chiều phiếu chỉ quyết dọc/ngang; 0° hay 180° để Bước 4."""
    uv = (tim_ung_vien_marker(gray) if uv is None else uv)[:K_UNG_VIEN]
    chi_tiet = {"ung_vien": uv, "bo_dat": []}
    if len(uv) < 4:
        return None, "thieu_marker", chi_tiet
    for bo in itertools.combinations(range(len(uv)), 4):
        ket = do_bo_4([uv[i] for i in bo], layout)
        g, vuong_goc = chon_cach_gan(ket)
        if qua_bo_4(ket, g):
            chi_tiet["bo_dat"].append({"bo": bo, "ket": ket, "gan": g, "dinh_mm_vuong_goc": vuong_goc})
    dat = chi_tiet["bo_dat"]
    if not dat:
        return None, "marker_khong_dat", chi_tiet
    if len(dat) >= 2:
        roi = any(not set(a["bo"]) & set(b["bo"]) for a, b in itertools.combinations(dat, 2))
        return None, ("nhieu_phieu" if roi else "marker_mo_ho"), chi_tiet
    bo, g = dat[0]["bo"], dat[0]["gan"]
    tam = np.array([uv[bo[j]].tam for j in g["idx"]], np.float32)
    return tam, "", chi_tiet


# ============================================================================ Bước 4–6 (chưa làm)


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
