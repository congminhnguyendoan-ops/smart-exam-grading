"""
preprocessing.py - Nắn phẳng ảnh phiếu chụp bằng điện thoại (Tuần 4, docs/ke_hoach_tuan4.md).

Mục tiêu: trả ảnh xám đã nắn đúng toạ độ layout.json (300 DPI), và KHÔNG BAO GIỜ trả ảnh nắn sai mà
báo OK – ảnh không nắn được phải bị từ chối có lý do (KetQuaTienXuLy.ok = False, ly_do = mã lỗi).

Tiến độ:
    Bước 2  load_image()                         – xong
    Bước 3b tim_ung_vien_marker()                – lọc + xếp hạng ứng viên marker
    Bước 3c find_markers()  (chọn 4 marker theo hình học) – xong
    Bước 4  warp(), verify(), preprocess() (chiều phiếu bằng nội dung, từ chối có lý do) – xong
    Bước 5  normalize()     (khử bóng / cân bằng sáng: chia nền, cửa sổ ≈ 15 mm) – xong
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

    ly_do (mã lỗi khi ok = False): 'khong_doc_duoc', 'thieu_marker', 'marker_khong_dat', 'nhieu_phieu',
    'marker_mo_ho', 'marker_cham_mep', 'anh_mo', 'khong_khop_bo_cuc', 'khong_ro_chieu'. Xoay sai không phải lỗi:
    chiều 0°/180° quyết bằng nội dung rồi tự xoay lại (huong_xoay).
    """
    ok: bool = False
    ly_do: str = ""
    anh_nan: np.ndarray | None = None           # xám, đã nắn, chưa chuẩn hoá (Bước 3–4)
    anh_chuan_hoa: np.ndarray | None = None     # Bước 5: normalize(anh_nan) – uint8 cùng cỡ, chỉ điền khi ok
    marker: np.ndarray | None = None            # 4×2 float32: tâm TL, TR, BR, BL trên ảnh gốc, dưới pixel (Bước 3)
    huong_xoay: int | None = None               # 0 / 90 / 180 / 270 (Bước 4)
    blur_score: float | None = None
    # Hướng xoay ĐÃ ÁP khi đọc (1–8, truy vết ca như 0006). JPG: thẻ EXIF Orientation của file.
    # HEIC: giá trị GỐC lấy từ info["original_orientation"], vì pillow-heif tự xoay rồi đặt thẻ về 1.
    exif_orientation: int = 1
    chi_tiet: dict = field(default_factory=dict)    # số đo để truy vết (S0/S180, biên chiều, ứng viên, …)


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


# ============================================================================ Bước 4: nắn + số đo cho verify()
# Dừng B: các hàm ĐO (điểm bố cục S, blur_score, lõi marker) – ngưỡng chọn bằng `tools/kiem_verify.py khao-sat`.
# Chỉ dùng toạ độ layout.json; KHÔNG render PDF / so bản đồ cạnh (phép 2 eval), KHÔNG dùng nhãn (phép 3 eval).
DO_DICH_MM = 2.0            # dò lệch từng phần tử ±2 mm (ảnh C3 dev còn lệch thật tới 1,30 mm giữa trang)
VIEN_NET_PX = 3.0           # nửa bề rộng dải viền in sẵn (px @300 DPI) khi đo tương phản
VANH_NGOAI_PX = (6.0, 12.0) # dải giấy so sánh: cách viền 6–12 px (khe giữa 2 ô tròn liền nhau ≥ 16 px)
MO_DPI = 150                # blur_score đo ở 150 DPI (giảm nhiễu hạt của ảnh C2 tối)
MO_VUNG_PX = 15             # vùng đo blur: phần tử nới 15 px (@300 DPI) – chịu được lệch ~1,3 mm


def warp(gray: np.ndarray, marker: np.ndarray, layout: dict) -> np.ndarray:
    """4 tâm marker (TL, TR, BR, BL trên ảnh gốc) -> trang layout (px @ dpi). Giống hệt cách nắn của v3_hinh_hoc."""
    m = layout["markers"]["centers"]
    M = cv2.getPerspectiveTransform(np.float32(marker), np.float32([m[g] for g in GOC]))
    return cv2.warpPerspective(gray, M, tuple(layout["page_px"]))


def loai_trang(layout: dict) -> str:
    return "phieu" if "answers" in layout else "chu_so"


def phan_tu_bo_cuc(layout: dict) -> list[tuple[str, np.ndarray]]:
    """[(khoá nhân, tâm N×2)] các phần tử in sẵn dùng đo bố cục. Phiếu: ô tròn đáp án (r 29,5) + bubble SBD/mã đề
    (r 26) – có trên cả phiếu thu dữ liệu lẫn phiếu thi thật. Trang D: 400 ô viết (cùng cỡ)."""
    if loai_trang(layout) == "phieu":
        a = layout["answers"]
        dap_an = np.array([a["centers"][q][o] for q in a["centers"] for o in a["options"]], np.float64)
        bub = np.array([p for f in ("sbd", "exam_code") for col in layout[f]["bubbles"] for p in col], np.float64)
        return [(f"tron_{a['bubble_radius']}", dap_an), (f"tron_{layout['sbd']['bubble_radius']}", bub)]
    R = np.array([b["rect"] for b in layout["boxes"]], np.float64)
    w, h = R[0, 2], R[0, 3]
    return [(f"chu_nhat_{w}_{h}", R[:, :2] + R[:, 2:] / 2)]


def nhan_tuong_phan(khoa: str, phan: str = "ca") -> np.ndarray:
    """Nhân đối xứng tâm: +1/n trên dải viền, −1/n trên dải giấy ngoài (tròn) hoặc trong+ngoài (chữ nhật).
    Tương quan với ảnh độ tối d = 1 − xám/nền ⇒ phản hồi = độ tối viền − độ tối giấy quanh viền.
    phan (chỉ chữ nhật): 'ca' = 4 cạnh cùng một độ dịch, 'doc' / 'ngang' = chỉ cạnh dọc / cạnh ngang."""
    a, b = VANH_NGOAI_PX
    if khoa.startswith("tron_"):
        r = float(khoa.split("_")[1])
        n = int(np.ceil(r + b)) + 1
        yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
        rho = np.hypot(xx, yy)
        vien, giay = np.abs(rho - r) <= VIEN_NET_PX, (rho >= r + a) & (rho <= r + b)
    else:
        w, h = (float(v) / 2 for v in khoa.split("_")[2:])
        n = int(np.ceil(max(w, h) + b)) + 1
        yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
        dx, dy = np.abs(xx) - w, np.abs(yy) - h           # khoảng cách có dấu tới cạnh dọc / cạnh ngang
        canh_doc = (np.abs(dx) <= VIEN_NET_PX) & (np.abs(yy) <= h - VIEN_NET_PX)
        canh_ngang = (np.abs(dy) <= VIEN_NET_PX) & (np.abs(xx) <= w - VIEN_NET_PX)
        giay_doc = (np.abs(dx) >= a) & (np.abs(dx) <= b) & (np.abs(yy) <= h - VIEN_NET_PX)
        giay_ngang = (np.abs(dy) >= a) & (np.abs(dy) <= b) & (np.abs(xx) <= w - VIEN_NET_PX)
        vien = {"ca": canh_doc | canh_ngang, "doc": canh_doc, "ngang": canh_ngang}[phan]
        giay = {"ca": giay_doc | giay_ngang, "doc": giay_doc, "ngang": giay_ngang}[phan]
    k = vien / vien.sum() - giay / giay.sum()
    return k.astype(np.float32)


def anh_do_toi(anh_nan: np.ndarray) -> np.ndarray:
    """d = 1 − xám / nền giấy cục bộ (float32): khử khác biệt chiếu sáng C1–C4 (C2 tối, C4 đèn vàng)."""
    return 1.0 - anh_nan.astype(np.float32) / np.maximum(uoc_luong_nen(anh_nan), 1.0)


def phan_hoi_phan_tu(d: np.ndarray, layout: dict, phan: str = "ca") -> list[tuple[np.ndarray, np.ndarray]]:
    """[(bản đồ phản hồi đã lấy max trong cửa sổ ±DO_DICH_MM, tâm phần tử)] cho từng loại phần tử."""
    k_dich = 2 * round(DO_DICH_MM * layout["dpi"] / 25.4) + 1
    out = []
    for khoa, tam in phan_tu_bo_cuc(layout):
        R = cv2.filter2D(d, cv2.CV_32F, nhan_tuong_phan(khoa, phan), borderType=cv2.BORDER_REPLICATE)
        out.append((cv2.dilate(R, cv2.getStructuringElement(cv2.MORPH_RECT, (k_dich, k_dich))), tam))
    return out


def lay_mau(Rmax: np.ndarray, tam: np.ndarray, xoay180: bool) -> np.ndarray:
    """Giá trị Rmax tại tâm phần tử; xoay180: tại vị trí phần tử khi trang bị lật 180° (W−1−x, H−1−y).
    Nhân đối xứng tâm ⇒ phản hồi của ảnh xoay 180° = phản hồi ảnh gốc lấy ở điểm đối xứng (không cần xoay ảnh)."""
    H, W = Rmax.shape
    p = (np.array([W - 1, H - 1]) - tam) if xoay180 else tam
    x = np.clip(np.round(p[:, 0]).astype(int), 0, W - 1)
    y = np.clip(np.round(p[:, 1]).astype(int), 0, H - 1)
    return Rmax[y, x]


def diem_bo_cuc(anh_nan: np.ndarray, layout: dict, phan: str = "ca", d: np.ndarray | None = None) -> dict:
    """S0 / S180 = trung vị tương phản viền trên mọi phần tử, khi trang đúng chiều / lật 180°. Kèm mảng từng phần tử."""
    d = anh_do_toi(anh_nan) if d is None else d
    ph = phan_hoi_phan_tu(d, layout, phan)
    v0 = np.concatenate([lay_mau(R, t, False) for R, t in ph])
    v180 = np.concatenate([lay_mau(R, t, True) for R, t in ph])
    return {"S0": float(np.median(v0)), "S180": float(np.median(v180)), "v0": v0, "v180": v180}


def mat_na_mo(layout: dict, xoay180: bool = False) -> np.ndarray:
    """Vùng đo blur @MO_DPI: phần tử in sẵn nới MO_VUNG_PX (tròn: đĩa r + nới; chữ nhật: hộp nới)."""
    W, H = layout["page_px"]
    s = MO_DPI / layout["dpi"]
    m = np.zeros((round(H * s), round(W * s)), np.uint8)
    for khoa, tam in phan_tu_bo_cuc(layout):
        p = (np.array([W - 1, H - 1]) - tam) if xoay180 else tam
        if khoa.startswith("tron_"):
            r = (float(khoa.split("_")[1]) + MO_VUNG_PX) * s
            for x, y in p * s:
                cv2.circle(m, (round(x), round(y)), round(r), 1, -1)
        else:
            w, h = (float(v) / 2 for v in khoa.split("_")[2:])
            for x, y in p:
                cv2.rectangle(m, (round((x - w - MO_VUNG_PX) * s), round((y - h - MO_VUNG_PX) * s)),
                              (round((x + w + MO_VUNG_PX) * s), round((y + h + MO_VUNG_PX) * s)), 1, -1)
    return m


def blur_score(anh_nan: np.ndarray, layout: dict, cach: str = "phan_tu", xoay180: bool = False) -> float:
    """Phương sai Laplacian ở MO_DPI. 'phan_tu_huong': như phan_tu nhưng min(var ∂²/∂x², var ∂²/∂y²) – bắt mờ một hướng.
    'phan_tu' (chính): trên ảnh xám/nền (khử chiếu sáng), trong vùng phần tử in sẵn.
    'toan_trang' (đối chứng): trên ảnh xám thô /255, toàn vùng trong 4 marker (bỏ ô 20 mm quanh marker).
    KHÔNG chia cho tương phản mực: mờ làm nét mảnh nhạt đi, chia cho tương phản sẽ triệt tiêu chính tín hiệu mờ."""
    s = MO_DPI / layout["dpi"]
    nho = cv2.resize(anh_nan, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if cach in ("phan_tu", "phan_tu_huong"):
        x = nho.astype(np.float32) / np.maximum(uoc_luong_nen(nho), 1.0)
        m = mat_na_mo(layout, xoay180)[:x.shape[0], :x.shape[1]]
    else:
        x = nho.astype(np.float32) / 255.0
        m = np.zeros(x.shape, np.uint8)
        mm = MO_DPI / 25.4
        m[round(20 * mm):round(277 * mm), round(20 * mm):round(190 * mm)] = 1
        for c in layout["markers"]["centers"].values():
            cx, cy = c[0] * s, c[1] * s
            m[max(0, round(cy - 10 * mm)):round(cy + 10 * mm), max(0, round(cx - 10 * mm)):round(cx + 10 * mm)] = 0
    if cach == "phan_tu_huong":     # mờ chuyển động chỉ làm nhoè MỘT hướng: lấy hướng nhoè nhất
        dxx = cv2.Sobel(x, cv2.CV_32F, 2, 0, ksize=3)
        dyy = cv2.Sobel(x, cv2.CV_32F, 0, 2, ksize=3)
        return float(min(dxx[m > 0].var(), dyy[m > 0].var()))
    L = cv2.Laplacian(x, cv2.CV_32F, ksize=3)
    return float(L[m > 0].var())


def den_loi_marker(anh_nan: np.ndarray, layout: dict) -> list[float]:
    """Mỗi marker (TL, TR, BR, BL): trung bình xám lõi 6×6 mm / trung vị xám vành giấy 6–10 mm quanh tâm.
    Marker thật ≈ 0,1–0,3 (đen trên giấy); vết khác / giấy ≈ 1. (Gần giống phép 1 của eval – phép phụ.)"""
    mm = layout["dpi"] / 25.4
    out = []
    for g in GOC:
        cx, cy = layout["markers"]["centers"][g]
        x0, y0 = round(cx - 10 * mm), round(cy - 10 * mm)
        o = anh_nan[max(0, y0):round(cy + 10 * mm), max(0, x0):round(cx + 10 * mm)].astype(np.float32)
        yy, xx = np.mgrid[:o.shape[0], :o.shape[1]]
        ax, ay = np.abs(xx + max(0, x0) - cx), np.abs(yy + max(0, y0) - cy)
        loi = (ax <= 3 * mm) & (ay <= 3 * mm)
        vanh = (np.maximum(ax, ay) >= 6 * mm) & (np.maximum(ax, ay) <= 10 * mm)
        out.append(float(o[loi].mean() / max(np.median(o[vanh]), 1.0)))
    return out


# Ngưỡng verify() – chốt ở dừng B (06/10/2026), căn cứ: `python tools/kiem_verify.py khao-sat`
# (data/_eval/v4_verify/khao_sat_dev.csv: 78 ảnh dev thật; khao_sat_mo.csv: hậu quả mờ). "Dev xấu nhất" = ảnh đúng.
BIEN_CHIEU_MIN = 0.20       # khong_ro_chieu: (S_tốt − S_kia) / S_tốt; dev xấu nhất phiếu 0,805 (0018_C2) ×4,0,
                            # trang D 0,429 (D006) ×2,1
S_MIN = {"phieu": 0.23,     # khong_khop_bo_cuc: S_tốt; phiếu dev xấu nhất 0,365 (0010_C2), trang D chấm theo layout
         "chu_so": 0.18}    # phiếu tốt nhất 0,144 (D006) – biên ×1,6 / ×1,6. Trang D: 0,451 (D001) vs phiếu chấm theo
                            # layout D 0,072 (0026_C2) – ×2,5 / ×2,5. Hai phép đo khác nhau -> hai ngưỡng
MO_MIN = 0.012              # anh_mo: blur_score 'phan_tu_huong'. NGƯỠNG TẠM, THẬN TRỌNG. Dev xấu nhất 0,221 (0034_C3),
                            # trang D 0,416 (D002). OMR (độ tối trung bình ô Ø5 mm, dò lại ±4 mm) còn tách filled/faint
                            # khỏi blank tới Gauss σ ≈ 32 px / chuyển động 80 px (px ẢNH GỐC 4032×3024) – mức gãy đầu
                            # tiên có blur_score ≤ 0,00063. Ngưỡng đặt ở trung bình nhân 0,221 và 0,00063 (×18,7 mỗi
                            # phía), CHẶT HƠN NHIỀU so với OMR cần, vì CNN chữ số viết tay (Tuần 6) chưa đo theo mức mờ.
                            # Tuần 6: đo CNN trên ảnh giả data/_eval/_gia_v4 rồi chỉnh lại theo hậu quả.
LOI_MARKER_MAX = 0.60       # marker_khong_dat: lõi 6×6 mm / vành giấy; dev xấu nhất 0,357 (0034_C3, marker loá), D 0,246


def verify(anh_nan: np.ndarray, layout: dict) -> tuple[bool, str, bool, dict]:
    """Bước 4: kiểm tra ảnh đã nắn (theo cách gán marker r ∈ {0, 1} của find_markers) + quyết chiều 0°/180° bằng
    NỘI DUNG -> (ok, ly_do, lat_180, chi_tiet). lat_180 = trang đang lộn ngược (đầu trang ở dưới).
    Thứ tự kết luận: anh_mo -> khong_khop_bo_cuc -> khong_ro_chieu -> marker_khong_dat (lõi marker).
    Mọi số đo chỉ dựa layout.json; không dùng phép 2/3 của eval (không render PDF, không nhãn)."""
    S = diem_bo_cuc(anh_nan, layout)
    lat = S["S180"] > S["S0"]
    s_tot, s_kia = (S["S180"], S["S0"]) if lat else (S["S0"], S["S180"])
    ct = {"S0": S["S0"], "S180": S["S180"], "bien_chieu": (s_tot - s_kia) / s_tot if s_tot > 0 else 0.0,
          "blur_score": blur_score(anh_nan, layout, "phan_tu_huong", lat),
          "loi_marker": max(den_loi_marker(anh_nan, layout))}
    if ct["blur_score"] < MO_MIN:
        return False, "anh_mo", lat, ct
    if s_tot < S_MIN[loai_trang(layout)]:
        return False, "khong_khop_bo_cuc", lat, ct
    if ct["bien_chieu"] < BIEN_CHIEU_MIN:
        return False, "khong_ro_chieu", lat, ct
    if ct["loi_marker"] > LOI_MARKER_MAX:
        return False, "marker_khong_dat", lat, ct
    return True, "", lat, ct


def huong_xoay(marker: np.ndarray) -> int:
    """Góc phiếu bị xoay trong ảnh gốc (chiều kim đồng hồ, bội 90°) từ vectơ TL -> TR: 0 = đầu trang ở trên."""
    dx, dy = np.asarray(marker[1], float) - np.asarray(marker[0], float)
    return int(round(np.degrees(np.arctan2(dy, dx)) / 90.0)) % 4 * 90


GIAY_DICH = 240             # chia nền: giấy -> 240 (chừa chỗ cho điểm sáng hơn nền ước lượng, không cắt cụt ở 255)
LOI_MARKER_MM_CH = 3.0      # nửa cạnh lõi marker (mm) – điểm đen của chia_nen_keo (cùng lõi 6×6 mm với den_loi_marker)
# Các cách chuẩn hoá được so ở Bước 5 dừng B (tools/kiem_chuan_hoa.py khao-sat). Giữ cả cách thua để số khảo sát tái tạo
# được. Mọi cách chỉ dùng anh_nan + layout (M2: vị trí marker) – không nhãn, không PDF render, không phép 2/3 của eval.
CACH_CHUAN_HOA = {
    "khong": ("khong", {}),
    "chia_nen_8": ("chia_nen", {"cua_so": 8}),          # cửa sổ nền ≈ 37 mm trên anh_nan
    "chia_nen_12": ("chia_nen", {"cua_so": 12}),        # ≈ 25 mm (= cửa sổ của find_markers trên ảnh gốc)
    "chia_nen_20": ("chia_nen", {"cua_so": 20}),        # ≈ 15 mm (vẫn > marker 8 mm)
    "chia_nen_keo_tv": ("chia_nen_keo", {"cua_so": 12, "diem_den": "trung_vi"}),
    "chia_nen_keo_min": ("chia_nen_keo", {"cua_so": 12, "diem_den": "min"}),
    **{f"clahe_{c}_{g}": ("clahe", {"clip": c, "luoi": g}) for c in (1.5, 2, 3) for g in (8, 16)},
}


def ti_le_nen(anh_nan: np.ndarray, cua_so: int) -> np.ndarray:
    """anh_nan / nền giấy cục bộ (float32; giấy ≈ 1, mực < 1) – uoc_luong_nen của Bước 3b."""
    return anh_nan.astype(np.float32) / np.maximum(uoc_luong_nen(anh_nan, cua_so), 1.0)


# Chốt ở Bước 5 dừng B (07/10/2026, người dùng chọn sau khi xem ảnh trước/sau), căn cứ `python tools/kiem_chuan_hoa.py
# so-sanh` (data/_eval/v5_chuan_hoa/so_sanh.md): cấu hình duy nhất qua cả 3 cổng; maximin AUC faint/blank đặc trưng tuyệt
# đối 0,9938 -> 0,9992, CI ghép cặp của Δ [+0,002; +0,012]; bóng trung vị C1 0,241->0,044, C2 0,573->0,100, C3 0,143->0,061,
# C4 0,280->0,049, D 0,184->0,073. p1(faint) − p99(blank) tuyệt đối âm -> dương mọi điều kiện, nhưng ở C4 CI của Δ chạm 0
# ([−0,006; +0,108]). Giá: nhiễu hạt C2 ×1,11, ~66 ms/ảnh.
# GIỚI HẠN ĐÃ BIẾT: (1) mép bóng sắc (0032_C4 câu 21–30) còn dải mảnh; hiệu theo hàng (local_darkness, tương đối) giảm tới
# −0,044 (faint) / −0,037 (filled), không hàng nào lật – anh_nan vẫn giữ, Tuần 5 chọn anh_nan / anh_chuan_hoa bằng thí nghiệm
# F1 lớp faint. (2) cửa sổ 20 (≈ 15 mm) ở BIÊN lưới đã thử (8/12/20); không thử nhỏ hơn vì gần cỡ ô Ø5 mm – nguy cơ ước lượng
# nền "ăn" vào ô tô, xoá mất faint. (3) Trang D: tương phản nét không đổi, nét/nhiễu 50,1 -> 48,1, chênh mức nét giữa trang
# 29,7 -> 32,9 – Tuần 6 thử CNN trên cả anh_nan và anh_chuan_hoa.
CACH_MAC_DINH = "chia_nen_20"


def normalize(anh_nan: np.ndarray, layout: dict, cach: str = CACH_MAC_DINH) -> np.ndarray:
    """Bước 5: khử bóng / cân bằng sáng -> anh_chuan_hoa (uint8, cùng cỡ anh_nan). Không đổi anh_nan.
    'chia_nen' (M1, mặc định chia_nen_20): anh / nền ước lượng × GIAY_DICH. 'chia_nen_keo' (M2): M1 rồi kéo điểm đen = lõi
    6×6 mm của 4 marker (đen thật, vị trí biết từ layout) về 0. 'clahe' (M3): CLAHE trên anh_nan. Chỉ dùng anh_nan + layout
    (không nhãn, không PDF render). Căn cứ + giới hạn: xem CACH_MAC_DINH."""
    kieu, ts = CACH_CHUAN_HOA[cach]
    if kieu == "khong":
        return anh_nan.copy()
    if kieu == "clahe":
        return cv2.createCLAHE(clipLimit=ts["clip"], tileGridSize=(ts["luoi"], ts["luoi"])).apply(anh_nan)
    r = ti_le_nen(anh_nan, ts["cua_so"])
    if kieu == "chia_nen_keo":
        k = LOI_MARKER_MM_CH * layout["dpi"] / 25.4
        loi = [float(r[round(cy - k):round(cy + k), round(cx - k):round(cx + k)].mean())
               for cx, cy in layout["markers"]["centers"].values()]
        den = float(np.median(loi)) if ts["diem_den"] == "trung_vi" else min(loi)
        r = (r - den) / max(1.0 - den, 1e-3)
    return np.clip(r * GIAY_DICH, 0, 255).round().astype(np.uint8)


def preprocess(path, layout: dict) -> KetQuaTienXuLy:
    """Đọc ảnh -> tìm 4 marker -> nắn -> verify (chiều bằng nội dung, từ chối có lý do) -> normalize (chỉ khi ok).
    layout = layout của loại trang mong đợi (phiếu / trang chữ số).
    Lỗi đọc file -> ok=False, 'khong_doc_duoc'; lỗi lập trình khác vẫn ném ra (Bước 6 quyết có bọc hay không).
    marker_cham_mep (chốt 06/10/2026: TỪ CHỐI, không ước lượng tâm): (1) một marker của bộ được chọn chạm mép ảnh;
    (2) không chọn được bộ 4 mà có ứng viên chạm mép -> báo marker_cham_mep (lời nhắc 'đưa cả tờ vào khung')."""
    kq = KetQuaTienXuLy()
    try:
        gray, kq.exif_orientation = doc_anh(path)
    except LoiDocAnh:
        kq.ly_do = "khong_doc_duoc"
        return kq
    tam, ly_do, ct = find_markers(gray, layout)
    kq.chi_tiet = {"ung_vien": [(u.x, u.y) for u in ct["ung_vien"]], "so_bo_dat": len(ct["bo_dat"])}
    if tam is None:
        if ly_do in ("thieu_marker", "marker_khong_dat") and any(u.cham_mep for u in ct["ung_vien"]):
            ly_do = "marker_cham_mep"
        kq.ly_do = ly_do
        return kq
    bo = ct["bo_dat"][0]
    if any(ct["ung_vien"][bo["bo"][j]].cham_mep for j in bo["gan"]["idx"]):
        kq.ly_do, kq.marker = "marker_cham_mep", tam
        return kq
    anh_nan = warp(gray, tam, layout)
    ok, ly_do, lat, ct_v = verify(anh_nan, layout)
    kq.chi_tiet.update(ct_v)
    kq.blur_score = ct_v["blur_score"]
    if lat:                                     # trang lộn ngược: gán lại góc (r + 2) và nắn lại – chính xác hơn rot90
        tam = np.roll(tam, -2, axis=0)
        anh_nan = warp(gray, tam, layout)
    kq.marker, kq.huong_xoay = tam, huong_xoay(tam)
    kq.ok, kq.ly_do = ok, ly_do
    kq.anh_nan = anh_nan                        # giữ cả khi bị từ chối (để xem lại); dùng được chỉ khi ok
    if ok:                                      # Bước 5: sau verify – không đổi anh_nan / ok / ly_do
        kq.anh_chuan_hoa = normalize(anh_nan, layout)
    return kq
