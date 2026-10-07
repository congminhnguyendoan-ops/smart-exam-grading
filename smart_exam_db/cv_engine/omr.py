"""
omr.py - Đọc ô trả lời (40 câu × A–D), bubble SBD (6 cột) và mã đề (3 cột) từ ảnh đã nắn của preprocess() (Tuần 5).

Kế hoạch + số liệu: docs/ke_hoach_tuan5.md. Mục tiêu số 1: KHÔNG có lỗi im lặng (đọc sai mà không gắn "cần xem").

Các khâu:
  1. dinh_vi()      – dò lại vị trí 2 tầng: (1) cả khối (đáp án / SBD / mã đề) ±4 mm, một độ dịch chung, kèm kiểm đỉnh
                      khớp DUY NHẤT trên vùng ±14 mm (bắt ca lệch đúng 1 khoảng cách ô); (2) từng hàng câu / từng cột chữ
                      số ±1,5 mm (< nửa khoảng cách ô nhỏ nhất 2,9 mm) + kiểm hàng lệch bất thường so với hàng lân cận.
                      Chỗ nào không tin được -> cờ 'vi_tri' (câu / cột đó "cần xem"), không đoán.
  2. dac_trung_o()  – đặc trưng từng ô (tương đối quanh ô, trong hàng, trong ảnh; tuyệt đối; kết cấu). Không dùng nhãn.
  3. mô hình        – JSON trong models/ (hồi quy logistic: chuẩn hoá + softmax, chỉ cần NumPy; hoặc ngưỡng cố định M0).
  4. luật ô -> câu / cột + "cần xem" (ap_luat_cau, ap_luat_cot).

Lúc chạy chỉ cần NumPy + OpenCV + JSON (scikit-learn chỉ dùng trong tools/huan_luyen_omr.py).
Toạ độ: pixel 300 DPI của layout.json, trên anh_nan / anh_chuan_hoa (2480×3508).
"""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

GOC_DU_AN = Path(__file__).resolve().parent.parent                  # smart_exam_db/
MAU_PNG = GOC_DU_AN / "answer_sheet" / "output" / "phieu_trang_300dpi.png"

# ------------------------------------------------------------------------------------------------ định vị
KHOI_DICH_MM = 4.0          # tầng 1: độ dịch chung của khối tìm trong ±4 mm (ảnh nắn đúng lệch tới 2,31 mm – Tuần 4)
KHOI_QUET_MM = 14.0         # tầng 1: quét rộng ±14 mm (> khoảng cách hàng 11 mm + biên) chỉ để kiểm đỉnh duy nhất
KHOI_THU_NHO = 4            # tầng 1 làm trên ảnh thu 1/4 (75 DPI, 0,34 mm/px) – tầng 2 tinh chỉnh ở 300 DPI
KHOI_LOAI_TRU_MM = 2.0      # đỉnh thứ hai tính ngoài bán kính này quanh đỉnh nhất (< mọi chu kỳ ô: 5,8 / 7 / 11 mm)
HANG_DICH_MM = 1.5          # tầng 2: ±1,5 mm < nửa khoảng cách ô nhỏ nhất (bubble chữ số 5,8 mm -> 2,9 mm)
# Khung khớp tầng 1 quanh hộp bao tâm ô (mm: trái, phải, trên, dưới) – bao cả khung viền / tiêu đề / số câu in sẵn
# (phần KHÔNG lặp) theo generate_sheets.py: khung đáp án 17–193 × 133–257 mm; khung chữ số y 45,5–126 mm.
KHUNG_DAP_AN_MM = (19.0, 11.0, 21.0, 8.0)
KHUNG_CHU_SO_MM = (11.0, 6.5, 24.5, 8.0)
# Khung tầng 2: hàng câu = số câu in sẵn bên trái + 4 ô (như check_labels.item_box); cột chữ số = ô viết tay + 10 bubble.
HANG_TRAI_MM, HANG_PHAI_MM, HANG_NUA_CAO_MM = 12.0, 5.0, 4.5
COT_NUA_RONG_MM, COT_TREN_MM, COT_DUOI_MM = 3.3, 16.0, 3.2
# Ngưỡng cờ 'vi_tri' – chọn 07/10/2026 trên 56 ảnh train + ảnh dịch giả (tools/kiem_dinh_vi.py; docs/ke_hoach_tuan5.md A1).
# Ảnh thật: điểm khối nhỏ nhất 0,224 (0014_C2 giấy cong; ảnh khác ≥ 0,353), biên duy nhất nhỏ nhất 0,056 (0025_C2 mã đề);
# ảnh dịch đúng 1 khoảng cách ô: điểm khối tới 0,56 (KHÔNG tách được bằng điểm) nhưng biên duy nhất ≤ −0,016 (đỉnh thật nằm
# ngoài cửa sổ ±4 mm và cao hơn) hoặc đỉnh chạm biên cửa sổ ⇒ chặn bằng biên duy nhất + chạm biên; điểm chỉ chặn khối hỏng.
KHOI_DIEM_MIN = 0.15        # điểm khớp tầng 1 (TM_CCOEFF_NORMED) tối thiểu
KHOI_BIEN_MIN = 0.03        # đỉnh nhất − đỉnh thứ hai tối thiểu (đỉnh duy nhất); thật ≥ 0,056, dịch 1 ô ≤ −0,016
HANG_DIEM_MIN = 0.20        # điểm khớp tầng 2 tối thiểu; thật ≥ 0,315 (hàng câu), ≥ 0,333 (cột chữ số)
LAN_CAN_MM = 0.8            # lệch so với đường thẳng các hàng / cột lân cận; thật ≤ 0,44 mm (0014_C2 cong)


def mm_px(layout: dict, mm: float) -> float:
    return mm * layout["dpi"] / 25.4


_MAU_CACHE: dict = {}


def nap_mau(path: Path | str = MAU_PNG, kiem_sha: bool = True) -> np.ndarray:
    """PNG mẫu phiếu trắng (sinh bởi answer_sheet/generate_sheets.py --chi-mau-png). Kiểm SHA điểm ảnh với file .json đi kèm."""
    path = Path(path)
    if path in _MAU_CACHE:
        return _MAU_CACHE[path]
    img = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"không đọc được mẫu phiếu {path} – chạy: python generate_sheets.py --chi-mau-png")
    if kiem_sha:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        sha = hashlib.sha256(np.ascontiguousarray(img).tobytes()).hexdigest()
        if sha != meta["sha256_diem_anh"]:
            raise ValueError(f"mẫu phiếu {path.name}: SHA điểm ảnh {sha[:12]}… ≠ {meta['sha256_diem_anh'][:12]}… trong .json")
    _MAU_CACHE[path] = img
    return img


def _hop(x0, y0, x1, y1) -> tuple[int, int, int, int]:
    return int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))


def hop_khoi(layout: dict, khoi: str) -> tuple[int, int, int, int]:
    """Khung (x0, y0, x1, y1) px của khối 'dap_an' / 'sbd' / 'ma_de' trên phiếu chuẩn."""
    if khoi == "dap_an":
        c = layout["answers"]["centers"]
        pts = np.array([xy for q in c.values() for xy in q.values()], float)
        l, r, t, b = KHUNG_DAP_AN_MM
    else:
        f = layout["sbd" if khoi == "sbd" else "exam_code"]
        pts = np.array([xy for col in f["bubbles"] for xy in col], float)
        l, r, t, b = KHUNG_CHU_SO_MM
    k = lambda v: mm_px(layout, v)  # noqa: E731
    return _hop(pts[:, 0].min() - k(l), pts[:, 1].min() - k(t), pts[:, 0].max() + k(r), pts[:, 1].max() + k(b))


def hop_hang(layout: dict, q: int) -> tuple[int, int, int, int]:
    ans = layout["answers"]
    c = ans["centers"][str(q)]
    xs = [c[o][0] for o in ans["options"]]
    cy = c[ans["options"][0]][1]
    k = lambda v: mm_px(layout, v)  # noqa: E731
    return _hop(min(xs) - k(HANG_TRAI_MM), cy - k(HANG_NUA_CAO_MM), max(xs) + k(HANG_PHAI_MM), cy + k(HANG_NUA_CAO_MM))


def hop_cot(layout: dict, truong: str, i: int) -> tuple[int, int, int, int]:
    f = layout[truong]
    col = f["bubbles"][i]
    cx = col[0][0]
    k = lambda v: mm_px(layout, v)  # noqa: E731
    return _hop(cx - k(COT_NUA_RONG_MM), col[0][1] - k(COT_TREN_MM), cx + k(COT_NUA_RONG_MM), col[-1][1] + k(COT_DUOI_MM))


def _cat(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, nen: int = 255) -> np.ndarray:
    """Cắt vùng, phần ngoài ảnh điền màu giấy (không ném lỗi ở mép trang)."""
    h, w = img.shape[:2]
    out = np.full((y1 - y0, x1 - x0), nen, img.dtype)
    sx0, sy0, sx1, sy1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = img[sy0:sy1, sx0:sx1]
    return out


def _khop(anh: np.ndarray, mau: np.ndarray, hop: tuple, tam: tuple[float, float], ban_kinh: int) -> np.ndarray:
    """Bản đồ TM_CCOEFF_NORMED của mẫu[hop] trên ảnh quanh vị trí hop + tam, độ dịch −ban_kinh..+ban_kinh mỗi trục.
    Ô [ban_kinh + dy, ban_kinh + dx] = điểm khớp khi độ dịch (so với layout) = tam + (dx, dy)."""
    x0, y0, x1, y1 = hop
    tx, ty = int(round(tam[0])), int(round(tam[1]))
    vung = _cat(anh, x0 + tx - ban_kinh, y0 + ty - ban_kinh, x1 + tx + ban_kinh, y1 + ty + ban_kinh)
    return cv2.matchTemplate(vung, mau[y0:y1, x0:x1], cv2.TM_CCOEFF_NORMED)


def _dinh_parabol(m: np.ndarray, iy: int, ix: int) -> tuple[float, float]:
    """Tinh chỉnh dưới pixel đỉnh bản đồ khớp bằng parabol 3 điểm mỗi trục."""
    def p(a, b, c):
        d = a - 2 * b + c
        return 0.0 if d >= 0 else float(np.clip(0.5 * (a - c) / d, -0.5, 0.5))
    h, w = m.shape
    ox = p(m[iy, ix - 1], m[iy, ix], m[iy, ix + 1]) if 0 < ix < w - 1 else 0.0
    oy = p(m[iy - 1, ix], m[iy, ix], m[iy + 1, ix]) if 0 < iy < h - 1 else 0.0
    return ix + ox, iy + oy


@dataclass
class KhoiDinhVi:
    dich: tuple[float, float]       # px @300 DPI so với layout
    diem: float                     # điểm khớp đỉnh nhất (trong ±KHOI_DICH_MM)
    diem_thu_hai: float             # đỉnh cao nhất ngoài bán kính loại trừ, trên toàn vùng quét ±KHOI_QUET_MM
    cham_bien: bool                 # đỉnh nhất nằm ở mép cửa sổ ±KHOI_DICH_MM
    co: tuple[str, ...]             # lý do không tin được ('' = tin được)


@dataclass
class KetQuaDinhVi:
    """dich[key] = (dx, dy) px tổng (tầng 1 + tầng 2) so với layout; key 'q1'..'q40', 'sbd1'..'sbd6', 'ma_de1'..'ma_de3'.
    co[key] = các lý do không tin được vị trí (rỗng = tin được)."""
    khoi: dict[str, KhoiDinhVi]
    dich: dict[str, tuple[float, float]]
    diem: dict[str, float]
    co: dict[str, tuple[str, ...]] = field(default_factory=dict)
    lech: dict[str, float] = field(default_factory=dict)      # px: lệch so với đường thẳng các hàng / cột lân cận


TRUONG_KHOI = {"sbd": "sbd", "ma_de": "exam_code"}


def dinh_vi_khoi(anh: np.ndarray, mau: np.ndarray, layout: dict, khoi: str) -> KhoiDinhVi:
    k = KHOI_THU_NHO
    nho = cv2.resize(anh, (anh.shape[1] // k, anh.shape[0] // k), interpolation=cv2.INTER_AREA)
    mau_nho = cv2.resize(mau, (mau.shape[1] // k, mau.shape[0] // k), interpolation=cv2.INTER_AREA)
    x0, y0, x1, y1 = hop_khoi(layout, khoi)
    hop_nho = (x0 // k, y0 // k, x1 // k, y1 // k)
    quet = int(round(mm_px(layout, KHOI_QUET_MM) / k))
    cua_so = int(round(mm_px(layout, KHOI_DICH_MM) / k))
    loai = mm_px(layout, KHOI_LOAI_TRU_MM) / k
    m = _khop(nho, mau_nho, hop_nho, (0, 0), quet)
    trong = np.full(m.shape, -np.inf, np.float32)
    trong[quet - cua_so:quet + cua_so + 1, quet - cua_so:quet + cua_so + 1] = \
        m[quet - cua_so:quet + cua_so + 1, quet - cua_so:quet + cua_so + 1]
    iy, ix = np.unravel_index(int(np.argmax(trong)), m.shape)
    s1 = float(m[iy, ix])
    yy, xx = np.mgrid[:m.shape[0], :m.shape[1]]
    ngoai = (yy - iy) ** 2 + (xx - ix) ** 2 > loai ** 2
    s2 = float(m[ngoai].max())
    cham = abs(ix - quet) >= cua_so or abs(iy - quet) >= cua_so
    fx, fy = _dinh_parabol(m, iy, ix)
    co = []
    if s1 < KHOI_DIEM_MIN:
        co.append("khoi_khop_yeu")
    if s1 - s2 < KHOI_BIEN_MIN:
        co.append("khoi_dinh_khong_duy_nhat")
    if cham:
        co.append("khoi_cham_bien")
    return KhoiDinhVi(((fx - quet) * k, (fy - quet) * k), s1, s2, cham, tuple(co))


def _tang2(anh, mau, hop, tam, layout) -> tuple[tuple[float, float], float, bool]:
    r = int(round(mm_px(layout, HANG_DICH_MM)))
    m = _khop(anh, mau, hop, tam, r)
    iy, ix = np.unravel_index(int(np.argmax(m)), m.shape)
    fx, fy = _dinh_parabol(m, iy, ix)
    cham = ix in (0, m.shape[1] - 1) or iy in (0, m.shape[0] - 1)
    return (round(tam[0]) + fx - r, round(tam[1]) + fy - r), float(m[iy, ix]), cham


def _lech_lan_can(ds: list[tuple[float, float]], i: int, ban_kinh: int) -> float:
    """Lệch lớn nhất (px, theo trục) của phần tử i so với đường thẳng khớp các phần tử lân cận trong ±ban_kinh (trừ chính
    nó) – giấy cong làm độ dịch đổi dần theo hàng (0014_C2: ~0,4 mm / hàng), so với trung vị sẽ báo nhầm ở hàng đầu / cuối."""
    idx = [j for j in range(max(0, i - ban_kinh), min(len(ds), i + ban_kinh + 1)) if j != i]
    if not idx:
        return 0.0
    v = np.array([ds[j] for j in idx], float)
    if len(idx) == 1:
        du = v[0]
    else:
        du = np.array([np.polyval(np.polyfit(idx, v[:, a], 1), i) for a in range(2)])
    return float(np.max(np.abs(np.array(ds[i]) - du)))


def _bam_theo(anh, mau, layout, cac_hop: list, tam_khoi: tuple[float, float]) -> list:
    """Tầng 2 cho một dãy phần tử liền nhau (10 hàng một cột câu / các cột chữ số của một khối).
    Neo = phần tử khớp tốt nhất khi đặt cửa sổ ±HANG_DICH_MM quanh độ dịch khối (không chạm biên). Từ neo đi lần ra hai
    phía: cửa sổ ±HANG_DICH_MM đặt quanh độ dịch NGOẠI SUY từ 1–2 phần tử vừa định vị – cửa sổ luôn < nửa khoảng cách ô so
    với dự đoán, nên không khớp sang ô bên cạnh, mà vẫn theo được giấy cong (0014_C2 lệch tới ~4,5 mm ở cuối cột câu)."""
    dau = [_tang2(anh, mau, h, tam_khoi, layout) for h in cac_hop]
    ung = [i for i, (_, _, cham) in enumerate(dau) if not cham]
    neo = max(ung or range(len(dau)), key=lambda i: dau[i][1])
    ket: list = [None] * len(cac_hop)
    ket[neo] = dau[neo]
    for buoc in (1, -1):
        i = neo + buoc
        while 0 <= i < len(cac_hop):
            t1 = np.array(ket[i - buoc][0])
            j = i - 2 * buoc
            du = 2 * t1 - np.array(ket[j][0]) if 0 <= j < len(cac_hop) and ket[j] is not None and \
                (j - neo) * buoc >= 0 else t1
            ket[i] = _tang2(anh, mau, cac_hop[i], tuple(du), layout)
            i += buoc
    return ket


def dinh_vi(anh: np.ndarray, layout: dict, mau: np.ndarray | None = None) -> KetQuaDinhVi:
    """Dò lại vị trí 2 tầng trên ảnh đã nắn (xem docstring đầu file). Không dùng nhãn."""
    mau = nap_mau() if mau is None else mau
    if anh.shape != mau.shape:
        raise ValueError(f"ảnh {anh.shape} khác cỡ mẫu {mau.shape} – cần anh_nan / anh_chuan_hoa của preprocess()")
    khoi = {kh: dinh_vi_khoi(anh, mau, layout, kh) for kh in ("dap_an", "sbd", "ma_de")}
    dich, diem, co, lech = {}, {}, {}, {}
    lan_can = mm_px(layout, LAN_CAN_MM)

    def ghi(nhom: list[str], ket: list, ten_khoi: str, ban_kinh: int):
        ds = [d for d, _, _ in ket]
        for i, key in enumerate(nhom):
            d, s, cham = ket[i]
            dich[key], diem[key] = d, s
            lech[key] = _lech_lan_can(ds, i, ban_kinh)
            ly = list(khoi[ten_khoi].co)
            if s < HANG_DIEM_MIN:
                ly.append("hang_khop_yeu")
            if cham:
                ly.append("hang_cham_bien")
            if lech[key] > lan_can:
                ly.append("hang_lech_lan_can")
            co[key] = tuple(ly)

    nq = layout["answers"]["num_questions"]
    # một dãy = các hàng cùng cột câu (10 câu / cột, đánh số theo cột: 1–10, 11–20, …)
    for g0 in range(0, nq, 10):
        cau = list(range(g0 + 1, min(g0 + 10, nq) + 1))
        ket = _bam_theo(anh, mau, layout, [hop_hang(layout, q) for q in cau], khoi["dap_an"].dich)
        ghi([f"q{q}" for q in cau], ket, "dap_an", 3)
    for kh, truong in TRUONG_KHOI.items():
        n = len(layout[truong]["bubbles"])
        ket = _bam_theo(anh, mau, layout, [hop_cot(layout, truong, i) for i in range(n)], khoi[kh].dich)
        ghi([f"{kh}{i + 1}" for i in range(n)], ket, kh, 3)
    return KetQuaDinhVi(khoi, dich, diem, co, lech)


# ------------------------------------------------------------------------------------------------ đặc trưng ô
# Thứ tự cột của ma trận đặc trưng (mô hình JSON ghi lại tên cột – nạp mô hình kiểm khớp):
#   ld        local_darkness: 1 − trung bình lõi (0,75r) / giấy vành 1,15–1,45r (ngoài viền in) – gần bất biến với bóng
#   ld_hang   ld − min(ld trong hàng 4 ô)    (bubble: ld − trung vị cột 10 ô) – khử viền + chữ A–D / 0–9 in sẵn trong ô
#   ld_anh    ld_hang / S_anh – thang theo ẢNH, KHÔNG dùng nhãn (bút chì nhạt vs bi đen, ảnh C2 tối)
#   tuyet_doi 1 − trung bình lõi / 255
#   phu_nhe   tỉ lệ điểm lõi tối hơn 0,85 × giấy;   phu_dam: tối hơn 0,6 × giấy  (tô mờ thường loang, không phủ kín)
#   do_lech   độ lệch chuẩn lõi / giấy
#   hang      hạng trong hàng / cột (0 = ô tối nhất)
#   giay      mức giấy vành / 255
TEN_DAC_TRUNG = ("ld", "ld_hang", "ld_anh", "tuyet_doi", "phu_nhe", "phu_dam", "do_lech", "hang", "giay")
S_PHAN_VI = 90              # S_anh: trung vị độ chênh (max − min) của các hàng có chênh ≥ 0,5 × phân vị 90 của 40 hàng
S_SAN = 0.20                # sàn của S_anh (phiếu gần như bỏ trống: S nhỏ -> khuếch đại nhiễu); chọn A2 – xem kế hoạch


def _do_o(anh: np.ndarray, cx: float, cy: float, r: float) -> tuple:
    """(ld, tuyet_doi, phu_nhe, phu_dam, do_lech, giay) của 1 ô tròn tâm (cx, cy) bán kính r px."""
    x0, y0 = int(round(cx - 1.5 * r)), int(round(cy - 1.5 * r))
    n = int(round(3 * r)) + 1
    patch = _cat(anh, x0, y0, x0 + n, y0 + n).astype(np.float32)
    yy, xx = np.ogrid[:n, :n]
    d2 = (xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2
    loi = patch[d2 <= (0.75 * r) ** 2]
    giay = max(float(np.median(patch[(d2 >= (1.15 * r) ** 2) & (d2 <= (1.45 * r) ** 2)])), 1.0)
    m = float(loi.mean())
    return (float(np.clip(1 - m / giay, 0, 1)), 1 - m / 255, float(np.mean(loi < 0.85 * giay)),
            float(np.mean(loi < 0.6 * giay)), float(loi.std() / giay), giay / 255)


def _hang_trong(v: np.ndarray) -> np.ndarray:
    """Hạng theo hàng (trục cuối): 0 = lớn nhất."""
    return np.argsort(np.argsort(-v, axis=-1, kind="stable"), axis=-1, kind="stable").astype(np.float32)


def thang_anh(ld_hang_cau: np.ndarray) -> float:
    """S_anh từ ma trận ld_hang 40×4 của ô đáp án – không dùng nhãn."""
    chenh = ld_hang_cau.max(axis=1)
    nguong = 0.5 * np.percentile(chenh, S_PHAN_VI)
    return max(float(np.median(chenh[chenh >= nguong])), S_SAN)


def dac_trung_o(anh: np.ndarray, layout: dict, dv: KetQuaDinhVi) -> tuple[np.ndarray, np.ndarray, float]:
    """Ma trận đặc trưng (cột theo TEN_DAC_TRUNG): ô đáp án (40, 4, F) và bubble (9, 10, F) theo thứ tự sbd1..6, ma_de1..3.
    Toạ độ ô = layout + độ dịch của hàng / cột (dv). Trả kèm S_anh. KHÔNG dùng nhãn."""
    ans = layout["answers"]
    nq, opts, r = ans["num_questions"], ans["options"], ans["bubble_radius"]
    tho = np.zeros((nq, len(opts), 6), np.float32)
    for q in range(1, nq + 1):
        dx, dy = dv.dich[f"q{q}"]
        for j, o in enumerate(opts):
            cx, cy = ans["centers"][str(q)][o]
            tho[q - 1, j] = _do_o(anh, cx + dx, cy + dy, r)
    ld = tho[..., 0]
    ld_hang = ld - ld.min(axis=1, keepdims=True)
    S = thang_anh(ld_hang)
    cau = np.concatenate([ld[..., None], ld_hang[..., None], (ld_hang / S)[..., None], tho[..., 1:5],
                          _hang_trong(ld)[..., None], tho[..., 5:6]], axis=-1)
    cot = []
    for kh, truong in TRUONG_KHOI.items():
        f = layout[truong]
        for i, col in enumerate(f["bubbles"]):
            dx, dy = dv.dich[f"{kh}{i + 1}"]
            cot.append([_do_o(anh, cx + dx, cy + dy, f["bubble_radius"]) for cx, cy in col])
    tho_b = np.array(cot, np.float32)
    ld_b = tho_b[..., 0]
    ld_cot = ld_b - np.median(ld_b, axis=1, keepdims=True)
    # thang bubble: trung vị (ô tối nhất − nền) qua các cột, sàn 0,5 × S_anh (khối không tô ô nào – vd mã đề '---')
    S_b = max(float(np.median(ld_cot.max(axis=1))), 0.5 * S)
    bub = np.concatenate([ld_b[..., None], ld_cot[..., None], (ld_cot / S_b)[..., None], tho_b[..., 1:5],
                          _hang_trong(ld_b)[..., None], tho_b[..., 5:6]], axis=-1)
    return cau, bub, S


# ------------------------------------------------------------------------------------------------ mô hình JSON
MODELS_DIR = GOC_DU_AN / "models"
MO_HINH_MAC_DINH = MODELS_DIR / "omr_m1.json"
LOP_CAU = ("blank", "faint", "filled")
LOP_BUBBLE = ("blank", "filled")


def nap_mo_hinh(path: Path | str = MO_HINH_MAC_DINH) -> dict:
    """Nạp mô hình JSON (tools/huan_luyen_omr.py xuat). Kiểm tên đặc trưng khớp code hiện tại."""
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    if tuple(m["ten_dac_trung"]) != TEN_DAC_TRUNG:
        raise ValueError(f"mô hình {Path(path).name}: đặc trưng {m['ten_dac_trung']} ≠ code {TEN_DAC_TRUNG}")
    for k in ("cau", "bubble"):
        if k not in m.get("luat", {}):
            raise ValueError(f"mô hình {Path(path).name} thiếu ngưỡng luật '{k}'")
    return m


def du_doan(mo_hinh: dict, loai: str, X: np.ndarray) -> np.ndarray:
    """Xác suất từng lớp cho ma trận đặc trưng X (n, F). loai 'cau' -> 3 lớp LOP_CAU; 'bubble' -> 2 lớp LOP_BUBBLE."""
    X = np.asarray(X, np.float64).reshape(-1, len(TEN_DAC_TRUNG))
    lop = LOP_CAU if loai == "cau" else LOP_BUBBLE
    if mo_hinh["loai"] == "nguong":                          # M0: ngưỡng cố định trên ld_anh -> xác suất "cứng"
        v = X[:, TEN_DAC_TRUNG.index("ld_anh")]
        ng = mo_hinh["nguong"]
        k = (np.where(v < ng["mark_min"], 0, np.where(v < ng["filled_min"], 1, 2)) if loai == "cau"
             else (v >= ng["mark_min"]).astype(int))
        P = np.zeros((len(v), len(lop)))
        P[np.arange(len(v)), k] = 1.0
        return P
    if mo_hinh["loai"] != "logistic":
        raise ValueError(f"loại mô hình không hỗ trợ: {mo_hinh['loai']}")
    m = mo_hinh[loai]
    if tuple(m["lop"]) != lop:
        raise ValueError(f"mô hình '{loai}': lớp {m['lop']} ≠ {lop}")
    z = (X - np.array(m["trung_binh"])) / np.array(m["do_lech"])
    logit = z @ np.array(m["he_so"]).T + np.array(m["chan"])
    if logit.shape[1] == 1:                                    # 2 lớp: sklearn lưu 1 hàng hệ số cho lớp 1
        p1 = 1 / (1 + np.exp(-logit[:, 0]))
        return np.column_stack([1 - p1, p1])
    logit -= logit.max(axis=1, keepdims=True)
    e = np.exp(logit)
    return e / e.sum(axis=1, keepdims=True)


# ------------------------------------------------------------------------------------------------ luật ô -> câu / cột
MA_LY_DO_OMR = {
    "o_mo": "Ô được tô mờ – kiểm tra thí sinh có chọn đáp án / chữ số này không.",
    "nhieu_o": "Tô nhiều hơn một ô – kiểm tra lại câu / chữ số này.",
    "khong_o_nao": "Cột chữ số không tô ô nào – nhập chữ số bằng tay.",
    "tin_cay_thap": "Máy không chắc ô nào được tô (vết tô sát ngưỡng) – kiểm tra bằng mắt.",
    "vi_tri": "Không xác định chắc vị trí hàng / cột trên ảnh (giấy cong, lệch) – kiểm tra bằng mắt hoặc chụp lại.",
}
TRANG_THAI_DB = {"trong": "blank", "ro": "filled", "mo": "faint", "nhieu": "multiple"}   # -> ENUM bubble_state


def sang_bubble_state(trang_thai: str) -> str:
    """trang_thai câu ('trong' / 'ro' / 'mo' / 'nhieu') -> giá trị ENUM bubble_state của sheet_answers.state."""
    return TRANG_THAI_DB[trang_thai]


@dataclass(frozen=True)
class KetQuaCau:
    cau: int                                   # 1..40
    trang_thai: str                            # 'trong' | 'ro' | 'mo' | 'nhieu'  (sang_bubble_state -> DB)
    dap_an: str                                # '' | 'A' | 'AC' (thứ tự A–D) = sheet_answers.selected_options
    xac_suat: dict                             # {'A': {'blank': .97, 'faint': .02, 'filled': .01}, ...} = option_probs
    do_tin_cay: float                          # min trên 4 ô của max(p trống, p có tô) – 0..1
    can_xem: bool
    ly_do: tuple[str, ...]                     # mã trong MA_LY_DO_OMR; () khi chắc chắn


@dataclass(frozen=True)
class KetQuaCot:
    truong: str                                # 'sbd' | 'ma_de'
    vi_tri: int                                # 1..6 / 1..3
    chu_so: str                                # '0'..'9', hoặc '?' (không ô nào / nhiều ô)
    xac_suat_to: tuple[float, ...]             # p(có tô) của ô 0..9
    do_tin_cay: float
    can_xem: bool
    ly_do: tuple[str, ...]


def ap_luat_cau(cau: int, P: np.ndarray, luat: dict, options=("A", "B", "C", "D"), vi_tri_xau: bool = False) -> KetQuaCau:
    """Luật ô -> câu (docs/ke_hoach_tuan5.md mục 5 + ★Q1). P: (4, 3) xác suất blank / faint / filled của 4 ô.
    Ô 'trống chắc' khi p(trống) ≥ trong_min; 'tô chắc' khi p(có tô) ≥ to_min; còn lại 'lưng chừng' -> câu cần xem
    (tin_cay_thap). Đáp án dự đoán = các ô có p(có tô) ≥ 0,5. 1 ô: rõ nếu p(rõ | có tô) ≥ ro_min, không thì mờ (cần xem).
    ≥ 2 ô: nhiều ô (cần xem). 0 ô: trống – KHÔNG cần xem nếu cả 4 ô trống chắc (★Q1)."""
    P = np.asarray(P, np.float64)
    p_to = P[:, 1] + P[:, 2]
    ly = ["vi_tri"] if vi_tri_xau else []
    if np.any((P[:, 0] < luat["trong_min"]) & (p_to < luat["to_min"])):
        ly.append("tin_cay_thap")
    chon = [i for i in range(len(options)) if p_to[i] >= 0.5]
    if not chon:
        tt = "trong"
    elif len(chon) > 1:
        tt = "nhieu"
        ly.append("nhieu_o")
    else:
        i = chon[0]
        tt = "ro" if P[i, 2] / p_to[i] >= luat["ro_min"] else "mo"
        if tt == "mo":
            ly.append("o_mo")
    xs = {o: {lop: round(float(P[i, k]), 4) for k, lop in enumerate(LOP_CAU)} for i, o in enumerate(options)}
    tin = float(np.min(np.maximum(P[:, 0], p_to)))
    return KetQuaCau(cau, tt, "".join(options[i] for i in chon), xs, round(tin, 4), bool(ly), tuple(dict.fromkeys(ly)))


def ap_luat_cot(truong: str, vi_tri: int, P: np.ndarray, luat: dict, vi_tri_xau: bool = False,
                ld_anh: np.ndarray | None = None) -> KetQuaCot:
    """Luật 10 ô bubble -> 1 chữ số. P: (10, 2) xác suất blank / filled; ld_anh: (10,) đặc trưng ld_anh của 10 ô.
    Mô hình bubble chỉ có 2 lớp (dev không có bubble mờ) nên thêm 2 luật an toàn: (1) xác suất lưng chừng -> tin_cay_thap;
    (2) ô được chọn mà ld_anh < ro_min_ld_anh (bubble tô thật trên train ≥ 0,798; ô đáp án mờ trung vị 0,61) -> 'o_mo'
    cần xem – vết mờ có thể là vết tẩy / vô tình (pytest: bubble xám nhạt vẽ giả p = 0,76 vẫn bị bắt)."""
    P = np.asarray(P, np.float64)
    p_to = P[:, 1]
    ly = ["vi_tri"] if vi_tri_xau else []
    if np.any((P[:, 0] < luat["trong_min"]) & (p_to < luat["to_min"])):
        ly.append("tin_cay_thap")
    chon = [d for d in range(len(p_to)) if p_to[d] >= 0.5]
    if len(chon) == 1:
        cs = str(chon[0])
        if ld_anh is not None and ld_anh[chon[0]] < luat["ro_min_ld_anh"]:
            ly.append("o_mo")
    else:
        cs = "?"
        ly.append("khong_o_nao" if not chon else "nhieu_o")
    tin = float(np.min(np.maximum(P[:, 0], p_to)))
    return KetQuaCot(truong, vi_tri, cs, tuple(round(float(v), 4) for v in p_to), round(tin, 4), bool(ly),
                     tuple(dict.fromkeys(ly)))


@dataclass(frozen=True)
class KetQuaOMR:
    """Kết quả đọc 1 ảnh phiếu. Mọi mục can_xem = True phải qua giáo viên (Tuần 9–10); lý do: MA_LY_DO_OMR."""
    cau: tuple[KetQuaCau, ...]                 # 40 câu
    sbd: str                                   # 6 ký tự, '?' ở cột không đọc được
    sbd_cot: tuple[KetQuaCot, ...]
    ma_de: str                                 # 3 ký tự
    ma_de_cot: tuple[KetQuaCot, ...]
    can_xem: bool                              # có ≥ 1 câu / cột cần xem
    sbd_can_xem: bool
    ma_de_can_xem: bool
    dich_chuyen_mm: dict                       # 'q1'..'q40', 'sbd1'.., 'ma_de1'.. -> (dx, dy) mm so với layout (gỡ lỗi)
    nguon_anh: str                             # 'anh_nan' | 'anh_chuan_hoa'
    phien_ban_mo_hinh: str                     # -> ml_models
    thoi_gian_ms: float


def doc_phieu(kq, layout: dict, mo_hinh: dict | None = None, mau: np.ndarray | None = None) -> KetQuaOMR:
    """Đọc 40 câu + SBD + mã đề từ KetQuaTienXuLy (preprocess). Chỉ nhận kq.ok = True (ảnh bị từ chối không được chấm).
    Không đọc nhãn, không ghi file."""
    import time
    t0 = time.perf_counter()
    if not getattr(kq, "ok", False):
        raise ValueError(f"không đọc OMR ảnh bị preprocess từ chối (ly_do='{getattr(kq, 'ly_do', '')}')")
    mo_hinh = nap_mo_hinh() if mo_hinh is None else mo_hinh
    mau = nap_mau() if mau is None else mau
    anh = kq.anh_nan if mo_hinh["nguon_anh"] == "anh_nan" else kq.anh_chuan_hoa
    dv = dinh_vi(kq.anh_nan, layout, mau)
    cau_dt, bub_dt, _ = dac_trung_o(anh, layout, dv)
    P_cau = du_doan(mo_hinh, "cau", cau_dt.reshape(-1, cau_dt.shape[-1])).reshape(cau_dt.shape[0], cau_dt.shape[1], -1)
    P_bub = du_doan(mo_hinh, "bubble", bub_dt.reshape(-1, bub_dt.shape[-1])).reshape(bub_dt.shape[0], bub_dt.shape[1], -1)
    luat = mo_hinh["luat"]
    opts = tuple(layout["answers"]["options"])
    cau = tuple(ap_luat_cau(q + 1, P_cau[q], luat["cau"], opts, bool(dv.co[f"q{q + 1}"])) for q in range(P_cau.shape[0]))
    cot, c = {}, 0
    for kh, truong in TRUONG_KHOI.items():
        cot[kh] = []
        for i in range(len(layout[truong]["bubbles"])):
            cot[kh].append(ap_luat_cot(kh, i + 1, P_bub[c], luat["bubble"], bool(dv.co[f"{kh}{i + 1}"]),
                                       bub_dt[c, :, TEN_DAC_TRUNG.index("ld_anh")]))
            c += 1
    k_mm = 25.4 / layout["dpi"]
    return KetQuaOMR(
        cau=cau, sbd="".join(x.chu_so for x in cot["sbd"]), sbd_cot=tuple(cot["sbd"]),
        ma_de="".join(x.chu_so for x in cot["ma_de"]), ma_de_cot=tuple(cot["ma_de"]),
        can_xem=any(x.can_xem for x in cau) or any(x.can_xem for v in cot.values() for x in v),
        sbd_can_xem=any(x.can_xem for x in cot["sbd"]), ma_de_can_xem=any(x.can_xem for x in cot["ma_de"]),
        dich_chuyen_mm={k: (round(v[0] * k_mm, 3), round(v[1] * k_mm, 3)) for k, v in dv.dich.items()},
        nguon_anh=mo_hinh["nguon_anh"], phien_ban_mo_hinh=mo_hinh.get("phien_ban", ""),
        thoi_gian_ms=round((time.perf_counter() - t0) * 1000, 1))
