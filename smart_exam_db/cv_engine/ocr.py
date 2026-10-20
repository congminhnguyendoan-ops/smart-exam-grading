"""
ocr.py - đọc chữ số viết tay (SBD, mã đề) – Tuần 6.

Gồm: (1) CẮT ô viết tay + chuẩn hoá kiểu MNIST; (2) suy luận CNN bằng NumPy + JSON (models/ocr_cnn.json), `doc_chu_so()`;
(3) đối chiếu hai kênh bubble ↔ viết tay (`doi_chieu_cot`, `doi_chieu_truong`). Lúc chạy KHÔNG cần PyTorch.
Mọi toạ độ lấy từ layout.json / digit_sheet_layout.json (sheet_layout.py là nguồn duy nhất), pixel @300 DPI trên ảnh đã nắn.

Ô viết tay có VIỀN IN SẴN (ô 6×9 mm = 70,9 × 106,3 px). Viền phải bỏ trước khi đưa vào CNN, nếu không mô hình học viền.
Cách làm: dò lại vị trí 4 cạnh viền quanh vị trí danh nghĩa (±DO_LECH_VIEN px, từng cạnh), cắt vào trong NUT_VIEN px.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

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
    fr_toi: float = 0.0             # tỉ lệ pixel ô cắt tối hơn 50% mức giấy (phân vị 95): ô bị bôi đen > 30% không phải chữ số


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
                  lech_vien=(x0 - int(round(rect[0])), y0 - int(round(rect[1]))), ok_vien=ok,
                  fr_toi=float((o < 0.5 * float(np.percentile(o, 95))).mean()) if o.size else 0.0)


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
    "o_it_muc": "Ô viết tay có quá ít mực, không đọc được.",
    "khong_phai_chu_so": "Ô viết tay có quá nhiều mực / nhiều mảnh, không giống một chữ số.",
}


@dataclass(frozen=True)
class CotDoiChieu:
    chu_so: str                      # chữ số chốt ('?' nếu không chốt được)
    chac: bool                       # True = không cần giáo viên xem cột này
    ly_do: tuple[str, ...]           # mã trong MA_LY_DO_OCR; () khi chắc
    chi_trong_bubble: bool = False   # True = chắc CHỈ vì bubble (ô viết tay trống) – còn điều kiện danh sách thí sinh


def doi_chieu_cot(bubble: str, bubble_cx: bool, cnn: str, cnn_p: float, cnn_chac: bool, o_trong: bool,
                  tau_khop: float = 0.5, loi_o: str = "") -> CotDoiChieu:
    """Một cột chữ số. bubble: '0'–'9' hoặc '?'; cnn: chữ số CNN dự đoán, cnn_p: xác suất đã hiệu chỉnh, cnn_chac: qua ngưỡng τ, δ
    (chỉ dùng khi KHÔNG có bubble để đối chiếu – nhưng khi đó vẫn là 'cần xem', xem bảng); o_trong: ô viết tay không có mực.
      bubble chắc + CNN cùng chữ số với p ≥ τ_khop            -> chắc
      bubble chắc + CNN khác chữ số / p < τ_khop              -> cần xem (lech_bubble / tin_cay_thap)
      bubble chắc + ô viết tay trống                          -> chắc theo bubble, ĐIỀU KIỆN danh sách (xem doi_chieu_truong, Q3)
      bubble '?' hoặc bị OMR gắn cần xem                      -> cần xem (không tự nhận một kênh duy nhất)
      loi_o ('o_it_muc' | 'khong_phai_chu_so': ô viết tay không đọc được, KHÁC ô trống) -> cần xem, KHÔNG nhận theo bubble"""
    if bubble == "?" or bubble_cx:
        ly = ["thieu_bubble" if bubble == "?" else "bubble_cx"] + ([loi_o] if loi_o else [])
        return CotDoiChieu(bubble if bubble != "?" else (cnn if not (o_trong or loi_o) else "?"), False, tuple(ly))
    if loi_o:
        return CotDoiChieu(bubble, False, (loi_o,))
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


# =============================================================================================
# Suy luận CNN bằng NumPy + JSON (Tuần 6 Phần C). Mô hình huấn luyện bằng PyTorch (tools/huan_luyen_ocr.py), xuất ra models/ocr_cnn.json
# bởi tools/xuat_ocr.py; ở đây KHÔNG import torch. Kiến trúc: Conv16 3×3 → pool → Conv32 3×3 → pool → Dense64 → 10 (xem H.tao_cnn).
# =============================================================================================
DUONG_DAN_MO_HINH = Path(__file__).resolve().parent.parent / "models" / "ocr_cnn.json"
NGUONG_TRONG = 30        # ink_px < ngưỡng -> ô viết tay trống (đo trên 4 612 ô dev: ô ít mực nhất 167 px; CHƯA kiểm trên ô trống thật)
NGUONG_IT_MUC = 100      # 30 <= ink_px < 100: có vết nhưng quá ít để đọc -> cần xem (dev: không ô nào, min 167)
NGUONG_TI_LE_MUC = 0.36  # > 36% diện tích ô là mực -> không phải chữ số (dev: max 0,25; ngưỡng ≈ 1,4 × max dev, nghiêng về cần xem)
NGUONG_N_TP = 7          # >= 7 mảnh mực rời -> không phải chữ số (dev: max 5)
NGUONG_FR_TOI = 0.30     # > 30% pixel ô tối (ô bị bôi đen: nền = trung vị ô bị đảo nên ink_px sai) -> không phải chữ số (dev 4 504 ô: max 0,21, p99,9 0,18)
LE_BAN_DO_TOI = 100      # px: lề quanh vùng 9 ô khi tính bản đồ tối cục bộ (cửa sổ closing 15 px ≪ lề)


@dataclass
class MoHinhOCR:
    thanh_vien: list          # mỗi phần tử: dict(c1w, c1b, c2w, c2b, d1w, d1b, d2w, d2b, T) – mảng float32
    tau: float                # ngưỡng độ tin cậy chữ số (CNN một mình) – chỉ để báo cáo, luật nhận là doi_chieu_cot
    delta: float
    tau_khop: float           # đối chiếu bubble: CNN cùng chữ số với p ≥ tau_khop
    sieu_du_lieu: dict = field(default_factory=dict)


def nap_mo_hinh_ocr(duong_dan: str | Path | None = None) -> MoHinhOCR:
    """Nạp models/ocr_cnn.json (một lần). Trọng số JSON -> float32."""
    d = json.loads(Path(duong_dan or DUONG_DAN_MO_HINH).read_text(encoding="utf-8"))
    tv = []
    for m in d["thanh_vien"]:
        tv.append({k: (np.asarray(v, np.float32) if k != "T" else float(v)) for k, v in m.items() if k != "seed"})
    return MoHinhOCR(tv, d["tau"], d["delta"], d["tau_khop"], d.get("sieu_du_lieu", {}))


def _conv3(x: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Conv 3×3, padding 1, + ReLU. x [N,C,H,W], w [O,C,3,3] -> [N,O,H,W]."""
    xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    win = sliding_window_view(xp, (3, 3), axis=(2, 3))                    # [N,C,H,W,3,3]
    y = np.einsum("nchwij,ocij->nohw", win, w, optimize=True) + b[None, :, None, None]
    return np.maximum(y, 0.0)


def _pool2(x: np.ndarray) -> np.ndarray:
    n, c, h, w = x.shape
    return x.reshape(n, c, h // 2, 2, w // 2, 2).max(axis=(3, 5))


def logit_mot_thanh_vien(m: dict, x: np.ndarray) -> np.ndarray:
    """Logit [N,10] của một CNN. x uint8 [N,28,28] (nền 0, nét 255)."""
    a = x.astype(np.float32)[:, None] / 255.0
    a = _pool2(_conv3(a, m["c1w"], m["c1b"]))
    a = _pool2(_conv3(a, m["c2w"], m["c2b"]))
    a = a.reshape(len(a), -1)                                              # (C, H, W) -> giống torch flatten(1)
    return np.maximum(a @ m["d1w"].T + m["d1b"], 0.0) @ m["d2w"].T + m["d2b"]


def du_doan_xac_suat(mh: MoHinhOCR, x: np.ndarray) -> np.ndarray:
    """Xác suất [N,10] đã hiệu chỉnh nhiệt độ, TRUNG BÌNH xác suất của các thành viên (ensemble)."""
    if len(x) == 0:
        return np.zeros((0, 10), np.float32)
    ps = []
    for m in mh.thanh_vien:
        z = logit_mot_thanh_vien(m, x) / m["T"]
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        ps.append(e / e.sum(axis=1, keepdims=True))
    return np.mean(ps, axis=0)


@dataclass
class CotOCR:
    """Một ô viết tay đã đọc."""
    vi_tri: int
    chu_so: str                       # chữ số CNN đọc ('?' khi ô trống / không đọc được)
    top_k: list                       # [(chữ số, xác suất)] 3 chữ số đầu ([] khi không chạy CNN)
    p: float                          # xác suất của chữ số đọc được (0 khi '?')
    o_trong: bool                     # ô không có mực
    loi_o: str                        # '' | 'o_it_muc' | 'khong_phai_chu_so'
    ok_vien: bool                     # False: không dò được khung ô (dùng vị trí ước lượng) – chỉ thông tin
    cnn_chac: bool                    # p ≥ τ và (p1 − p2) ≥ δ (chỉ thông tin: luật nhận là đối chiếu bubble)
    anh28: np.ndarray | None = None   # ảnh kiểu MNIST đưa vào CNN (để lưu / xem)
    anh_o: np.ndarray | None = None   # ô cắt đã bỏ viền (uint8 0–255, nền trắng) để hiển thị


@dataclass
class KetQuaOCR:
    sbd: list                         # 6 CotOCR
    ma_de: list                       # 3 CotOCR
    thoi_gian_ms: float = 0.0


def _ban_do_toi_cuc_bo(xam: np.ndarray, rects) -> np.ndarray:
    """Bản đồ tối chỉ tính quanh các ô (lề LE_BAN_DO_TOI), phần còn lại 0. Cùng giá trị với ban_do_toi() cả trang trong vùng đó."""
    H, W = xam.shape
    x0 = max(int(min(r[0] for r in rects)) - LE_BAN_DO_TOI, 0)
    y0 = max(int(min(r[1] for r in rects)) - LE_BAN_DO_TOI, 0)
    x1 = min(int(max(r[0] + r[2] for r in rects)) + LE_BAN_DO_TOI, W)
    y1 = min(int(max(r[1] + r[3] for r in rects)) + LE_BAN_DO_TOI, H)
    m = 16
    a, b, c, d = max(x0 - m, 0), max(y0 - m, 0), min(x1 + m, W), min(y1 + m, H)
    toi = np.zeros((H, W), np.float32)
    toi[y0:y1, x0:x1] = ban_do_toi(xam[b:d, a:c])[y0 - b:y1 - b, x0 - a:x1 - a]
    return toi


def _hop_ly_o(o: OChuSo) -> str:
    if o.fr_toi > NGUONG_FR_TOI:
        return "khong_phai_chu_so"
    if o.ink_px < NGUONG_TRONG:
        return "trong"
    if o.ink_px < NGUONG_IT_MUC:
        return "o_it_muc"
    if o.ti_le_muc > NGUONG_TI_LE_MUC or o.n_tp >= NGUONG_N_TP:
        return "khong_phai_chu_so"
    return ""


def doc_chu_so(kq, layout: dict, mo_hinh: MoHinhOCR) -> KetQuaOCR:
    """Đọc 9 ô viết tay (SBD 6 + mã đề 3) của một phiếu đã nắn. kq = preprocess(...) với kq.ok = True (không thì ValueError).
    Cắt trên `anh_nan` (nguồn đã chọn bằng thí nghiệm Tuần 6), CNN NumPy. Ô trống / ít mực / không phải chữ số KHÔNG qua CNN
    (chu_so = '?'). Không đoán: quyết định nhận hay cần xem nằm ở doi_chieu_cot / doi_chieu_truong."""
    if not kq.ok:
        raise ValueError(f"doc_chu_so cần ảnh đã nắn hợp lệ (ok=True), nhận ly_do={kq.ly_do!r}")
    t0 = time.perf_counter()
    nhom = [[tuple(r) for r in layout["sbd"]["handwriting_boxes"]], [tuple(r) for r in layout["exam_code"]["handwriting_boxes"]]]
    xam = kq.anh_nan
    toi = _ban_do_toi_cuc_bo(xam, [r for n in nhom for r in n])
    cat = cat_anh(xam, nhom, toi)
    tat_ca = [(i, j, o) for i, h in enumerate(cat) for j, o in enumerate(h)]
    hop_ly = [_hop_ly_o(o) for _, _, o in tat_ca]
    doc = [k for k, h in enumerate(hop_ly) if h == "" and tat_ca[k][2].anh28 is not None]
    p = du_doan_xac_suat(mo_hinh, np.stack([tat_ca[k][2].anh28 for k in doc])) if doc else np.zeros((0, 10), np.float32)
    ra: list[list[CotOCR]] = [[], []]
    vi = {k: n for n, k in enumerate(doc)}
    for k, (i, j, o) in enumerate(tat_ca):
        loi = hop_ly[k] if hop_ly[k] not in ("", "trong") else ""
        a_o = np.clip(255.0 * (1.0 - o.ink), 0, 255).astype(np.uint8)
        if k in vi:
            pk = p[vi[k]]
            top = np.argsort(-pk)[:3]
            cx = bool(pk[top[0]] >= mo_hinh.tau and pk[top[0]] - pk[top[1]] >= mo_hinh.delta)
            ra[i].append(CotOCR(j, str(int(top[0])), [(int(d), float(pk[d])) for d in top], float(pk[top[0]]), False, "", o.ok_vien, cx, o.anh28, a_o))
        else:
            ra[i].append(CotOCR(j, "?", [], 0.0, hop_ly[k] == "trong", loi, o.ok_vien, False, o.anh28, a_o))
    return KetQuaOCR(ra[0], ra[1], (time.perf_counter() - t0) * 1000.0)


def doi_chieu_dinh_danh(omr, ocr_kq: KetQuaOCR, sbd_trong_ds: bool | None, ma_de_trong_ds: bool | None, tau_khop: float | None = None,
                        mo_hinh: MoHinhOCR | None = None) -> dict:
    """Đối chiếu SBD và mã đề giữa bubble (omr = KetQuaOMR) và viết tay. *_trong_ds: True / False / None (chưa kiểm được) – Q3.
    Trả {'sbd': (giá trị, chắc, lý do), 'ma_de': (...), 'cot': {'sbd': [CotDoiChieu], 'ma_de': [...]}, 'can_xem': bool}."""
    tk = tau_khop if tau_khop is not None else (mo_hinh.tau_khop if mo_hinh else 0.5)
    ra, cot = {}, {}
    for ten, om_cot, cs, ds in (("sbd", omr.sbd_cot, ocr_kq.sbd, sbd_trong_ds), ("ma_de", omr.ma_de_cot, ocr_kq.ma_de, ma_de_trong_ds)):
        cc = [doi_chieu_cot(b.chu_so, bool(b.can_xem), c.chu_so, c.p, c.cnn_chac, c.o_trong, tk, c.loi_o) for b, c in zip(om_cot, cs)]
        ra[ten] = doi_chieu_truong(cc, ds)
        cot[ten] = cc
    ra["cot"] = cot
    ra["can_xem"] = not (ra["sbd"][1] and ra["ma_de"][1])
    return ra
