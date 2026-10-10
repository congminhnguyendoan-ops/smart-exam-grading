"""
ocr.py - đọc chữ số viết tay (SBD, mã đề) – Tuần 6.

BƯỚC 2 (hiện có): CẮT ô viết tay + chuẩn hoá kiểu MNIST. Bước 8 sẽ thêm doc_chu_so(), suy luận NumPy + JSON, đối chiếu bubble.
Mọi toạ độ lấy từ layout.json / digit_sheet_layout.json (sheet_layout.py là nguồn duy nhất), pixel @300 DPI trên ảnh đã nắn.

Ô viết tay có VIỀN IN SẴN (ô 6×9 mm = 70,9 × 106,3 px). Viền phải bỏ trước khi đưa vào CNN, nếu không mô hình học viền.
Cách làm: dò lại vị trí 4 cạnh viền quanh vị trí danh nghĩa (±DO_LECH_VIEN px, từng cạnh), cắt vào trong NUT_VIEN px.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

DO_LECH_KHUNG = 40      # px: khung tìm được cách ô danh nghĩa tối đa 40 px (3,4 mm; nửa khoảng cách 2 ô trên trang chữ số = 47)
NUT_VIEN = 7            # px: cắt vào trong bbox NGOÀI của khung (nét viền ~4–5 px). Đo 4 trang (1 511 ô): 9 px cắt cụt chữ ở 35% ô,
                        # 7 px còn vệt viền (>50% một cạnh) ở 0,8% ô, 5 px ở 9% ô -> chọn 7; ô còn vệt viền gắn cờ qua vien_con
NGUONG_MUC = 0.30       # ink >= ngưỡng này mới tính là mực
DIEN_TICH_NHO = 10      # px: thành phần liên thông nhỏ hơn bị coi là hạt bẩn
DAI_VIEN = 5            # px: thành phần mực nằm GỌN trong dải 5 px sát một cạnh ô cắt = mảnh viền còn sót -> xoá
VIEN_RING = 3           # px: vành ngoài của ô cắt, để đo "chạm viền"
CO_MNIST = 28
CO_CHU_SO = 20


@dataclass
class OChuSo:
    """Một ô viết tay đã cắt. `anh28` = ảnh kiểu MNIST (nền 0, nét 255, 28×28) hoặc None nếu ô trống."""
    anh28: np.ndarray | None
    ink: np.ndarray                 # float32 0–1, ô cắt đã bỏ viền (để xem / thống kê)
    ink_px: int                     # số pixel mực (sau khi bỏ hạt bẩn)
    ti_le_muc: float                # ink_px / diện tích ô
    n_tp: int                       # số thành phần liên thông (sau khi bỏ hạt bẩn)
    cao: int                        # chiều cao / rộng bbox mực (px ô cắt); 0 nếu trống
    rong: int
    cham_vien: int                  # số pixel mực nằm trong vành ngoài VIEN_RING px của ô cắt
    vien_con: float                 # max (4 cạnh) tỉ lệ mực trong dải 2 px sát cạnh ô cắt TRƯỚC khi xoá; > 0,5 = có vệt viền (đã xoá dải 3 px của cạnh đó)
    lech_vien: tuple[int, int]      # (dx, dy) dò được so với vị trí danh nghĩa (px)
    ok_vien: bool                   # False nếu dò viền không đáng tin (dùng vị trí danh nghĩa + độ lệch trang)


def ban_do_toi(xam: np.ndarray) -> np.ndarray:
    """Độ tối so với nền giấy (float32 ≥ 0): nền = closing 15 px (xoá nét mảnh: viền ô, nét chữ). Dùng để dò viền."""
    nen = cv2.morphologyEx(xam, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    return np.clip(nen.astype(np.float32) - xam.astype(np.float32), 0, None)


def tim_khung(toi: np.ndarray, rects) -> list[tuple[int, int, int, int, bool]]:
    """Tìm khung (viền in sẵn) của từng ô trong `rects` = [(x, y, w, h)] danh nghĩa: thành phần liên thông của bản đồ tối có
    cỡ ≈ ô (w ± 8, h ± 9 px), gán cho ô danh nghĩa gần nhất (≤ DO_LECH_KHUNG px). Chữ số chạm viền dính vào khung nhưng
    không làm to bbox (nét chữ nằm trong ô). Trả [(x0, y0, x1, y1, ok)] = bbox NGOÀI của khung; ô không tìm thấy khung
    (ok=False) dùng dịch trung vị của các ô tìm được trong nhóm. Dò từng khung, không dò cả nhóm: ô liền kề trên phiếu chỉ cách ~12 px."""
    R = [tuple(int(round(v)) for v in r) for r in rects]
    m = DO_LECH_KHUNG + 12
    H, W = toi.shape
    xa, ya = max(min(r[0] for r in R) - m, 0), max(min(r[1] for r in R) - m, 0)
    xb, yb = min(max(r[0] + r[2] for r in R) + m, W), min(max(r[1] + r[3] for r in R) + m, H)
    cua = toi[ya:yb, xa:xb]
    nguong = 0.4 * float(np.percentile(cua, 99.5))
    n, _, st, _ = cv2.connectedComponentsWithStats((cua >= max(nguong, 20.0)).astype(np.uint8), connectivity=8)
    w0, h0 = R[0][2], R[0][3]
    ung = [(st[i, 0] + xa, st[i, 1] + ya, st[i, 2], st[i, 3]) for i in range(1, n)
           if abs(st[i, 2] - w0) <= 8 and abs(st[i, 3] - h0) <= 9]
    # khung ngoài ≈ ô danh nghĩa + nửa bề dày viền mỗi phía (viền danh nghĩa ở tâm nét)
    kq: list = [None] * len(R)
    for i, (x, y, w, h) in enumerate(R):
        best = min(ung, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2, default=None)
        if best is not None and abs(best[0] - x) <= DO_LECH_KHUNG and abs(best[1] - y) <= DO_LECH_KHUNG:
            kq[i] = (best[0], best[1], best[0] + best[2], best[1] + best[3], True)
    return kq


def _cuc_dai_gan(profile: np.ndarray, tam: int, bk: int) -> int:
    lo = max(tam - bk, 0)
    return lo + int(np.argmax(profile[lo:tam + bk + 1]))


def tinh_chinh_khung(toi: np.ndarray, rect, dx: int, dy: int, bk: int = 5) -> tuple[int, int, int, int]:
    """Ô không tìm được khung: đặt ở (danh nghĩa + dịch dx, dy của trang) rồi tinh chỉnh từng cạnh ±bk px theo hồ sơ độ tối
    (khung ngoài = tâm nét ± nửa bề dày ≈ 2 px)."""
    x, y, w, h = (int(round(v)) for v in rect)
    x, y = x + dx, y + dy
    r = bk + 4
    H, W = toi.shape
    xa, ya, xb, yb = max(x - r, 0), max(y - r, 0), min(x + w + r, W), min(y + h + r, H)
    cua = toi[ya:yb, xa:xb]
    c0, c1 = int(0.15 * w) + (x - xa), int(0.85 * w) + (x - xa)
    r0, r1 = int(0.15 * h) + (y - ya), int(0.85 * h) + (y - ya)
    hang, cot = cua[:, c0:c1].sum(axis=1), cua[r0:r1, :].sum(axis=0)
    t_ = _cuc_dai_gan(hang, y - ya, bk) + ya
    d_ = _cuc_dai_gan(hang, y + h - ya, bk) + ya
    l_ = _cuc_dai_gan(cot, x - xa, bk) + xa
    r_ = _cuc_dai_gan(cot, x + w - xa, bk) + xa
    return l_ - 2, t_ - 2, r_ + 2, d_ + 2


def ban_do_muc(o: np.ndarray) -> np.ndarray:
    """Ô xám (uint8, đã bỏ viền) -> bản đồ mực float32 0–1. Nền = trung vị ô (giấy); 0,5 độ tối tương đối = mực đầy."""
    g = o.astype(np.float32)
    nen = max(float(np.median(g)), 1.0)
    return np.clip((nen - g) / (0.5 * nen), 0.0, 1.0)


def _bo_hat_ban(ink: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Bỏ thành phần liên thông < DIEN_TICH_NHO; trả (ink đã lọc, số px mực, số thành phần)."""
    mask = (ink >= NGUONG_MUC).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    giu = np.zeros_like(mask)
    k = 0
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= DIEN_TICH_NHO:
            giu[lab == i] = 1
            k += 1
    if giu.any():
        giu = cv2.dilate(giu, np.ones((3, 3), np.uint8))          # giữ viền mềm của nét
    return ink * giu, int((mask & giu).sum()), k


def _bo_manh_vien(ink: np.ndarray) -> np.ndarray:
    """Xoá thành phần liên thông nằm gọn trong dải DAI_VIEN px sát một cạnh (mảnh viền còn sót ở góc / dọc cạnh). Nét chữ thật
    hiếm khi nằm trọn trong dải 5 px sát mép ô; nét dính viền vẫn giữ phần ở trong."""
    h, w = ink.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats((ink >= NGUONG_MUC).astype(np.uint8), connectivity=8)
    ra = ink.copy()
    for i in range(1, n):
        x0, y0, bw, bh = st[i, 0], st[i, 1], st[i, 2], st[i, 3]
        if x0 + bw <= DAI_VIEN or x0 >= w - DAI_VIEN or y0 + bh <= DAI_VIEN or y0 >= h - DAI_VIEN:
            ra[lab == i] = 0
    return ra


def ve_mnist(ink: np.ndarray) -> np.ndarray | None:
    """Ink (đã lọc) -> 28×28 uint8 kiểu MNIST: cắt bbox mực, co về khung 20×20 giữ tỉ lệ, đặt trọng tâm vào (14, 14)."""
    ys, xs = np.nonzero(ink >= NGUONG_MUC)
    if len(ys) == 0:
        return None
    c = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = c.shape
    s = CO_CHU_SO / max(h, w)
    nh, nw = max(int(round(h * s)), 1), max(int(round(w * s)), 1)
    c = cv2.resize(c, (nw, nh), interpolation=cv2.INTER_AREA)
    tong = float(c.sum()) + 1e-9
    cy = float((c.sum(axis=1) * np.arange(nh)).sum()) / tong
    cx = float((c.sum(axis=0) * np.arange(nw)).sum()) / tong
    oy, ox = int(round(CO_MNIST / 2 - cy)), int(round(CO_MNIST / 2 - cx))
    ra = np.zeros((CO_MNIST, CO_MNIST), np.float32)
    y0, x0 = max(oy, 0), max(ox, 0)
    y1, x1 = min(oy + nh, CO_MNIST), min(ox + nw, CO_MNIST)
    ra[y0:y1, x0:x1] = c[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    return np.clip(ra * 255.0 + 0.5, 0, 255).astype(np.uint8)


def cat_o(xam: np.ndarray, khung: tuple[int, int, int, int, bool], rect) -> OChuSo:
    """Cắt 1 ô viết tay: `khung` = (x0, y0, x1, y1, ok) từ tim_khung; `rect` = ô danh nghĩa (chỉ để báo độ lệch)."""
    x0, y0, x1, y1, ok = khung
    o = xam[y0 + NUT_VIEN:y1 - NUT_VIEN, x0 + NUT_VIEN:x1 - NUT_VIEN]
    ink, ink_px, n_tp = _bo_hat_ban(ban_do_muc(o))
    mk0 = ink >= NGUONG_MUC
    vc = float(max(mk0[:2].mean(), mk0[-2:].mean(), mk0[:, :2].mean(), mk0[:, -2:].mean()))
    if vc > 0.5:                     # còn vệt viền: xoá dải 3 px của cạnh có vệt (nét chữ thật hiếm khi phủ > 50% cạnh)
        ink = ink.copy()
        for sl, tl in ((np.s_[:3, :], mk0[:2].mean()), (np.s_[-3:, :], mk0[-2:].mean()),
                       (np.s_[:, :3], mk0[:, :2].mean()), (np.s_[:, -3:], mk0[:, -2:].mean())):
            if tl > 0.5:
                ink[sl] = 0
        ink, ink_px, n_tp = _bo_hat_ban(ink)
    ink, ink_px, n_tp = _bo_hat_ban(_bo_manh_vien(ink))
    ys, xs = np.nonzero(ink >= NGUONG_MUC)
    vanh = np.ones(ink.shape, bool)
    vanh[VIEN_RING:-VIEN_RING, VIEN_RING:-VIEN_RING] = False
    mk = ink >= NGUONG_MUC
    return OChuSo(anh28=ve_mnist(ink), ink=ink, ink_px=ink_px, ti_le_muc=ink_px / ink.size, n_tp=n_tp,
                  cao=int(ys.max() - ys.min() + 1) if len(ys) else 0, rong=int(xs.max() - xs.min() + 1) if len(xs) else 0,
                  cham_vien=int((mk & vanh).sum()), vien_con=vc,
                  lech_vien=(x0 - int(round(rect[0])), y0 - int(round(rect[1]))), ok_vien=ok)


def cat_anh(xam: np.ndarray, nhom_rects, toi: np.ndarray | None = None) -> list[list[OChuSo]]:
    """Cắt mọi ô của một ảnh. `nhom_rects` = [[rect, ...], ...], mỗi nhóm là các ô CÙNG HÀNG (SBD 6 ô, mã đề 3 ô, 1 hàng 20 ô
    của trang chữ số). Ô tìm được khung -> dùng khung; ô không tìm được (ok_vien=False: khung dính đường kẻ / chữ số trồi ra khỏi ô)
    -> dịch trung vị của CẢ ảnh + tinh chỉnh cạnh; đánh dấu ok_vien=False để công cụ liệt kê."""
    toi = ban_do_toi(xam) if toi is None else toi
    kh = [tim_khung(toi, rs) for rs in nhom_rects]
    tim = [(k[0] - round(r[0]), k[1] - round(r[1])) for ks, rs in zip(kh, nhom_rects) for k, r in zip(ks, rs) if k is not None]
    dx, dy = (int(np.median([d[0] for d in tim])), int(np.median([d[1] for d in tim]))) if tim else (0, 0)
    out = []
    for ks, rs in zip(kh, nhom_rects):
        hang = []
        for k, r in zip(ks, rs):
            if k is None:
                x0, y0, x1, y1 = tinh_chinh_khung(toi, r, dx, dy)
                k = (x0, y0, x1, y1, False)
            hang.append(cat_o(xam, k, r))
        out.append(hang)
    return out


# =============================================================================================
# Đối chiếu hai kênh (bubble OMR ↔ viết tay CNN) – docs/ke_hoach_tuan6.md mục 2 + ★Q3. Hàm THUẦN, không đọc ảnh.
# =============================================================================================
MA_LY_DO_OCR = {
    "lech_bubble": "Chữ số viết tay khác chữ số bubble.",
    "tin_cay_thap": "Chữ số viết tay khó đọc (độ tin cậy thấp), chưa đối chiếu được với bubble.",
    "thieu_bubble": "Cột bubble không đọc được (không tô / tô nhiều ô), chỉ có chữ viết tay.",
    "bubble_cx": "Cột bubble được OMR gắn 'cần xem'.",
    "o_trong_ngoai_ds": "Ô viết tay trống và SBD / mã đề không nằm trong danh sách của kỳ thi (chỉ có bubble).",
    "o_trong_chua_biet_ds": "Ô viết tay trống và chưa kiểm được danh sách của kỳ thi (chỉ có bubble).",
}


@dataclass(frozen=True)
class CotDoiChieu:
    chu_so: str                      # chữ số chốt ('?' nếu không chốt được)
    chac: bool                       # True = không cần giáo viên xem cột này
    ly_do: tuple[str, ...]           # mã trong MA_LY_DO_OCR; () khi chắc
    chi_trong_bubble: bool = False   # True = chắc CHỈ vì bubble (ô viết tay trống) – còn điều kiện danh sách thí sinh


def doi_chieu_cot(bubble: str, bubble_cx: bool, cnn: str, cnn_p: float, cnn_chac: bool, o_trong: bool,
                  tau_khop: float = 0.5) -> CotDoiChieu:
    """Một cột chữ số. bubble: '0'–'9' hoặc '?'; cnn: chữ số CNN dự đoán, cnn_p: xác suất đã hiệu chỉnh, cnn_chac: qua ngưỡng τ, δ
    (chỉ dùng khi KHÔNG có bubble để đối chiếu – nhưng khi đó vẫn là 'cần xem', xem bảng); o_trong: ô viết tay không có mực.
      bubble chắc + CNN cùng chữ số với p ≥ τ_khop            -> chắc
      bubble chắc + CNN khác chữ số / p < τ_khop              -> cần xem (lech_bubble / tin_cay_thap)
      bubble chắc + ô viết tay trống                          -> chắc theo bubble, ĐIỀU KIỆN danh sách (xem doi_chieu_truong, Q3)
      bubble '?' hoặc bị OMR gắn cần xem                      -> cần xem (không tự nhận một kênh duy nhất)"""
    if bubble == "?" or bubble_cx:
        ly = ["thieu_bubble" if bubble == "?" else "bubble_cx"]
        return CotDoiChieu(bubble if bubble != "?" else (cnn if not o_trong else "?"), False, tuple(ly))
    if o_trong:
        return CotDoiChieu(bubble, True, (), chi_trong_bubble=True)
    if cnn == bubble and cnn_p >= tau_khop:
        return CotDoiChieu(bubble, True, ())
    return CotDoiChieu(bubble, False, ("lech_bubble" if cnn != bubble else "tin_cay_thap",))


def doi_chieu_truong(cot: list[CotDoiChieu], trong_danh_sach: bool | None) -> tuple[str, bool, tuple[str, ...]]:
    """Cả trường (SBD / mã đề). Q3: cột 'chắc chỉ nhờ bubble' (ô viết tay trống) chỉ được nhận khi bubble chắc VÀ trường có trong danh sách
    (SBD: danh sách thí sinh; mã đề: các mã đề của kỳ thi). trong_danh_sach None = chưa kiểm được -> cần xem. Trả (giá trị, chắc, lý do)."""
    gia_tri = "".join(c.chu_so for c in cot)
    ly = [m for c in cot for m in c.ly_do]
    chac = all(c.chac for c in cot)
    if chac and any(c.chi_trong_bubble for c in cot) and trong_danh_sach is not True:
        chac = False
        ly.append("o_trong_chua_biet_ds" if trong_danh_sach is None else "o_trong_ngoai_ds")
    return gia_tri, chac, tuple(dict.fromkeys(ly))
