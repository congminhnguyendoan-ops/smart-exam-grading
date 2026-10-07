"""
eval_preprocessing.py - Đánh giá một phương pháp nắn phẳng ảnh phiếu (Tuần 4, docs/ke_hoach_tuan4.md).

Phương pháp được chấm có giao diện  f(duong_dan) -> (anh_nan | None, ly_do):
  - phương pháp TỰ ĐỌC FILE (để bước đọc ảnh / EXIF cũng được chấm),
  - anh_nan là ảnh xám 2480x3508 (300 DPI, toạ độ layout.json); None = từ chối, ly_do ghi vào CSV.

Ba phép kiểm tra "nắn đúng" (độc lập với phương pháp; phép 2, 3 CHỈ dùng trong file này,
preprocessing.py không được dùng lại):
  1. Marker  : độ đen tâm 6x6 mm của 4 marker (marker_fill() của prepare_photos.py, như audit).
               Không độc lập với align() – chỉ là tín hiệu phụ.
  2. Nét     : so bản đồ cạnh của ảnh nắn với bản đồ cạnh của trang mẫu (phiếu / trang chữ số) ở 150 DPI,
               bỏ vùng quanh 4 marker và vùng "Mã phiếu/Mã trang". Ánh sáng được chuẩn hoá trước (chia cho
               nền giấy ước lượng) nên ảnh tối (C2) / đèn vàng (C4) không ảnh hưởng.
               - lech_toan_trang: tìm độ lệch ±15 mm trên dải tiêu đề (chữ in, không lặp chu kỳ)
               - lưới 6x8 ô: mỗi ô tìm độ lệch ±6 mm quanh lech_toan_trang, ghi điểm khớp + độ duy nhất
                 (đỉnh nhất − đỉnh thứ hai cách xa > 2 mm: ô tròn lặp đều 7/11/5,8 mm dễ cho đỉnh giả).
                 lech_trungvi/lech_max chỉ tính trên ô tin cậy (duy_nhat >= nguong.json:duy_nhat_min).
               - khop_net: % điểm nét của mẫu có nét ảnh trong vòng 1 mm (chỉ chiều mẫu→ảnh: chì/chữ
                 viết tay thêm nét không làm giảm điểm)
  3. Nhãn    : (chỉ phiếu) ô filled theo cell_labels.csv phải tối hơn ô blank cùng hàng/cột,
               đo tại toạ độ layout (không dò lại vị trí) bằng local_darkness() của check_labels.py.

Bước 1 (lệnh run): CHƯA có ngưỡng – mọi ảnh là 'xem'; xuất HTML để người dùng xem bằng mắt.
Chỉ ghi vào data/_eval/, không đụng data/raw/, data/raw_digits/.

Chạy (từ thư mục smart_exam_db/):
  python tools/eval_preprocessing.py run --phuong-phap align_cu --split dev
  python tools/eval_preprocessing.py finalize --phuong-phap v2_load --ke-thua align_cu
  python tools/eval_preprocessing.py report --phuong-phap v2_load --so-voi align_cu
Bước 7 (tập test, MỘT LẦN, xem bằng mắt MÙ – docs/ke_hoach_tuan4.md Bước 7):
  python tools/eval_preprocessing.py run --phuong-phap v6_api --split test --xac-nhan-test
  python tools/eval_preprocessing.py finalize --phuong-phap v6_api --split test      # cấm --ke-thua
  python tools/eval_preprocessing.py report --phuong-phap v6_api --split test --so-voi align_cu
  python tools/eval_preprocessing.py report-cuoi
"""
import argparse
import csv
import html
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent          # smart_exam_db/
ANSWER_SHEET = ROOT / "answer_sheet"
DATA = ROOT / "data"
EVAL_DIR = DATA / "_eval"
sys.path.insert(0, str(ANSWER_SHEET))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from check_layout import align, render_pdf_page  # noqa: E402  (không sửa check_layout.py)
from cv_engine.preprocessing import find_markers, load_image, preprocess  # noqa: E402
from prepare_photos import marker_fill  # noqa: E402
from check_labels import SEARCH_MM, item_box, local_darkness, register  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_DEV, PHIEU_TEST  # noqa: E402

SPLITS = {"dev": PHIEU_DEV, "test": PHIEU_TEST}     # mã phiếu (nguồn duy nhất: cv_engine/tap_du_lieu.py); D001–D010 thuộc dev
WORK_DPI = 150                       # độ phân giải làm phép 2 (0,17 mm/px – đủ đo lệch cỡ 0,5 mm)
PX = WORK_DPI / 25.4                 # px / mm ở WORK_DPI
MARKER_MASK_MM = 10.0                # bỏ ô 20x20 mm quanh tâm mỗi marker
CODE_MASK_MM = (178, 22, 192, 30)    # x0, y0, x1, y1: vùng chữ số "Mã phiếu/Mã trang" (chỉ chỗ này khác giữa các trang)
HEADER_MM = (20, 17, 190, 44)        # dải tiêu đề + "Họ và tên/Người viết": chữ in, không lặp chu kỳ
GLOBAL_SEARCH_MM = 15.0              # > chu kỳ dài nhất của ô tròn (11 mm)
GRID = (6, 8)                        # số ô lưới ngang x dọc
GRID_AREA_MM = (20, 20, 190, 277)    # vùng chia lưới (bên trong 4 marker)
TILE_SEARCH_MM = 6.0
PEAK_EXCLUDE_MM = 2.0                # đỉnh thứ hai phải cách đỉnh nhất hơn bấy nhiêu
# Mọi ngưỡng (kèm căn cứ chọn) nằm trong data/_eval/nguong.json – không khai báo lại ở đây.
NGUONG_PATH = EVAL_DIR / "nguong.json"
NGUONG = json.loads(NGUONG_PATH.read_text(encoding="utf-8")) if NGUONG_PATH.exists() else None
QUYET_DINH = [k for k, v in (NGUONG or {}).items() if isinstance(v, dict) and v.get("vai_tro") == "quyet_dinh"]


def nguong(khoa: str) -> float:
    if NGUONG is None:
        sys.exit(f"Thiếu {NGUONG_PATH} – file ngưỡng (xem docs/ke_hoach_tuan4.md, Bước 1).")
    return NGUONG[khoa]["gia_tri"]
MIN_TILE_EDGE = 0.01                 # ô lưới có < 1% điểm nét của mẫu: quá trống, bỏ
NEAR_MM = 1.0                        # khop_net: nét ảnh trong vòng 1 mm


# ============================================================================ tập ảnh
@dataclass
class Anh:
    ten: str            # 0001_C1 / D001
    duong_dan: Path
    loai: str           # 'phieu' | 'chu_so'
    ma: str             # 0001 / D001
    dieu_kien: str      # C1..C4 / D


def list_images(split: str) -> list[Anh]:
    out = []
    for p in sorted((DATA / "raw").glob("*.jpg")):
        ma, cond = p.stem.split("_")
        if int(ma) in SPLITS[split]:
            out.append(Anh(p.stem, p, "phieu", ma, cond))
    if split == "dev":
        out += [Anh(p.stem, p, "chu_so", p.stem, "D") for p in sorted((DATA / "raw_digits").glob("D*.jpg"))]
    return out


# ============================================================================ phương pháp được chấm
def doc_xam(duong_dan: Path) -> np.ndarray:
    """Đọc ảnh xám, an toàn với đường dẫn Unicode (cv2.imread không đọc được trên Windows)."""
    return cv2.imdecode(np.fromfile(duong_dan, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def align_cu(duong_dan: Path):
    """align() của check_layout.py (bản đầu) bọc theo giao diện chung: đọc file + nắn."""
    gray = doc_xam(duong_dan)
    if gray is None:
        return None, "không đọc được file"
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    return align(gray, layout), ""


def v2_load(duong_dan: Path):
    """Bước 2: load_image() của cv_engine + align() cũ. Kiểm tra hồi quy: phải cho kết quả giống hệt align_cu."""
    gray = load_image(duong_dan)                    # ném LoiDocAnh -> goi_phuong_phap() ghi là từ chối
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    return align(gray, layout), ""


def v3_hinh_hoc(duong_dan: Path):
    """Bước 3c: load_image() + find_markers() mới (bộ 4 theo hình học, tâm dưới pixel) + warpPerspective như align().
    Chiều phiếu chỉ quyết dọc/ngang (0° hay 180° để Bước 4). Trả thêm chi tiết (4 tâm + ứng viên) để vẽ lên ảnh gốc."""
    gray = load_image(duong_dan)
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    tam, ly_do, ct = find_markers(gray, layout)
    chi_tiet = {"marker": tam, "ung_vien": [(u.x, u.y) for u in ct["ung_vien"]], "so_bo_dat": len(ct["bo_dat"])}
    if tam is None:
        return None, ly_do, chi_tiet
    m = layout["markers"]["centers"]
    M = cv2.getPerspectiveTransform(tam, np.float32([m["tl"], m["tr"], m["br"], m["bl"]]))
    return cv2.warpPerspective(gray, M, tuple(layout["page_px"])), "", chi_tiet


def nap_layout_loai(loai: str) -> dict:
    ten = "layout.json" if loai == "phieu" else "digit_sheet_layout.json"
    return json.loads((ANSWER_SHEET / "output" / ten).read_text(encoding="utf-8"))


def v4_verify(duong_dan: Path, loai: str | None = None):
    """Bước 4: preprocess() = find_markers v3 + warp + verify() (chiều 0°/180° bằng nội dung, từ chối có lý do).
    Layout theo loại trang mong đợi: tên D* -> trang chữ số, còn lại phiếu (lúc chạy thật backend biết loại trang)."""
    loai = loai or ("chu_so" if Path(duong_dan).stem.startswith("D") else "phieu")
    kq = preprocess(duong_dan, nap_layout_loai(loai))
    ct = {"marker": kq.marker, "ung_vien": kq.chi_tiet.get("ung_vien", []), "so_bo_dat": kq.chi_tiet.get("so_bo_dat", ""),
          "huong_xoay": kq.huong_xoay if kq.huong_xoay is not None else "",
          **{k: kq.chi_tiet[k] for k in V4_COT if k in kq.chi_tiet}}
    return (kq.anh_nan if kq.ok else None), kq.ly_do, ct


def kiem_chuan_hoa(kq, ten) -> None:
    """Bước 5: ok ⇔ có anh_chuan_hoa uint8 cùng cỡ anh_nan (sai -> dừng hẳn, không ghi số đo lẫn lộn)."""
    if kq.ok != (kq.anh_chuan_hoa is not None):
        sys.exit(f"{ten}: ok={kq.ok} nhưng anh_chuan_hoa {'thiếu' if kq.ok else 'có'}")
    if kq.ok and (kq.anh_chuan_hoa.dtype != np.uint8 or kq.anh_chuan_hoa.shape != kq.anh_nan.shape):
        sys.exit(f"{ten}: anh_chuan_hoa {kq.anh_chuan_hoa.dtype} {kq.anh_chuan_hoa.shape} – phải uint8 {kq.anh_nan.shape}")


def v5_chuan_hoa(duong_dan: Path, loai: str | None = None):
    """Bước 5: preprocess() như v4 + điền anh_chuan_hoa khi ok. Eval vị trí chấm anh_nan (phải giống v4 từng điểm ảnh:
    tools/kiem_chuan_hoa.py so-anh-nan); tác dụng của chuẩn hoá đo riêng bằng kiem_chuan_hoa.py khao-sat / so-sanh."""
    loai = loai or ("chu_so" if Path(duong_dan).stem.startswith("D") else "phieu")
    kq = preprocess(duong_dan, nap_layout_loai(loai))
    kiem_chuan_hoa(kq, Path(duong_dan).stem)
    ct = {"marker": kq.marker, "ung_vien": kq.chi_tiet.get("ung_vien", []), "so_bo_dat": kq.chi_tiet.get("so_bo_dat", ""),
          "huong_xoay": kq.huong_xoay if kq.huong_xoay is not None else "",
          **{k: kq.chi_tiet[k] for k in V4_COT if k in kq.chi_tiet}}
    return (kq.anh_nan if kq.ok else None), kq.ly_do, ct


def v6_api(duong_dan: Path, loai: str | None = None):
    """Bước 6: API chốt – preprocess(path) = doc_anh + preprocess_anh(gray). Cùng hàm bọc với v5: hành vi phải giống v5
    từng byte (anh_nan theo vân tay v4, anh_chuan_hoa theo v5: tools/kiem_chuan_hoa.py so-anh-nan --phuong-phap v6_api)."""
    return v5_chuan_hoa(duong_dan, loai)


V4_COT = ["S0", "S180", "bien_chieu", "blur_score", "loi_marker"]
PHUONG_PHAP = {"align_cu": align_cu, "v2_load": v2_load, "v3_hinh_hoc": v3_hinh_hoc, "v4_verify": v4_verify,
               "v5_chuan_hoa": v5_chuan_hoa, "v6_api": v6_api}


def huong_tu_marker(m) -> int:
    dx, dy = np.asarray(m[1], float) - np.asarray(m[0], float)
    return int(round(np.degrees(np.arctan2(dy, dx)) / 90.0)) % 4 * 90


def marker_v3() -> dict:
    """4 tâm marker v3_hinh_hoc (TL, TR, BR, BL thật – 78/78 ảnh dev nắn đúng và đúng chiều, phép 2 + mắt)."""
    out = {}
    p = EVAL_DIR / "v3_hinh_hoc" / "diem_dev.csv"
    for r in csv.DictReader(p.open(encoding="utf-8-sig")):
        if r["tra_anh"] == "co":
            out[r["anh"]] = np.array([[float(r[f"marker_{g}_{c}"]) for c in "xy"] for g in ("tl", "tr", "br", "bl")])
    return out


def goi_phuong_phap(f, anh: Anh, page_px, chi_tiet: dict | None = None) -> tuple:
    """(ảnh nắn | None, lý do, giây). Phương pháp ném lỗi = từ chối. Sai kích thước = lỗi giao diện -> dừng.
    Phương pháp có thể trả thêm phần tử thứ 3 (dict chi tiết, vd 4 tâm marker) -> chép vào `chi_tiet` nếu được truyền."""
    t0 = time.perf_counter()
    try:
        kq = f(anh.duong_dan)
        out, ly_do = kq[0], kq[1]
        if chi_tiet is not None and len(kq) > 2:
            chi_tiet.update(kq[2])
    except Exception as e:  # noqa: BLE001
        out, ly_do = None, f"lỗi: {e}"
    giay = time.perf_counter() - t0
    if out is not None and (out.shape[1], out.shape[0]) != tuple(page_px):
        sys.exit(f"LỖI GIAO DIỆN: {anh.ten} trả ảnh {out.shape[1]}x{out.shape[0]}, cần {page_px[0]}x{page_px[1]}")
    if out is None and not ly_do:
        ly_do = "từ chối (không ghi lý do)"
    return out, ly_do, giay


# ============================================================================ phép 2: so nét
def to_work(gray300: np.ndarray, page_px) -> np.ndarray:
    w, h = round(page_px[0] * WORK_DPI / 300), round(page_px[1] * WORK_DPI / 300)
    return cv2.resize(gray300, (w, h), interpolation=cv2.INTER_AREA)


def ban_do_net(g: np.ndarray) -> np.ndarray:
    """Cạnh (0/255) sau khi chia cho nền giấy: không phụ thuộc độ sáng tuyệt đối."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(10 * PX) | 1,) * 2)   # > ô tô kín 5 mm, < marker
    bg = cv2.GaussianBlur(cv2.dilate(g, k), (0, 0), 3 * PX)
    norm = np.clip(g.astype(np.float32) / np.maximum(bg.astype(np.float32), 1) * 255, 0, 255).astype(np.uint8)
    return cv2.Canny(cv2.GaussianBlur(norm, (0, 0), 1.0), 40, 120)


def mat_na(layout, shape) -> np.ndarray:
    """1 = được so; 0 = vùng marker + vùng chữ số mã trang."""
    m = np.ones(shape, np.uint8)
    s = layout["dpi"] / 25.4                                   # layout ở 300 DPI -> mm
    for cx, cy in layout["markers"]["centers"].values():
        x, y = cx / s, cy / s
        m[int((y - MARKER_MASK_MM) * PX):int((y + MARKER_MASK_MM) * PX),
          int((x - MARKER_MASK_MM) * PX):int((x + MARKER_MASK_MM) * PX)] = 0
    x0, y0, x1, y1 = CODE_MASK_MM
    m[int(y0 * PX):int(y1 * PX), int(x0 * PX):int(x1 * PX)] = 0
    return m


def mem(e: np.ndarray) -> np.ndarray:
    """Nét làm mềm để so khớp chịu được nét lệch vài px."""
    return cv2.GaussianBlur(e.astype(np.float32), (0, 0), 1.5)


def dinh_duoi_pixel(R, bx, by) -> tuple[float, float]:
    """Nội suy parabol 3 điểm quanh đỉnh (mỗi trục riêng) -> phần lẻ (-0,5..0,5 px).
    Không nội suy được (đỉnh ở mép bản đồ / không lồi) -> 0."""
    def off(a, b, c):
        den = a - 2 * b + c
        return float(np.clip(0.5 * (a - c) / den, -0.5, 0.5)) if den < 0 else 0.0
    ox = off(R[by, bx - 1], R[by, bx], R[by, bx + 1]) if 0 < bx < R.shape[1] - 1 else 0.0
    oy = off(R[by - 1, bx], R[by, bx], R[by + 1, bx]) if 0 < by < R.shape[0] - 1 else 0.0
    return ox, oy


def khop(anh_s, mau_s, box_px, goc, search_px) -> tuple:
    """So vùng box của mẫu với ảnh quanh độ lệch goc (dx, dy) trong ±search_px.
    Trả (dx, dy, điểm, độ duy nhất) – dx, dy tuyệt đối (px, dưới pixel nhờ nội suy parabol)."""
    x0, y0, x1, y1 = box_px
    goc = (int(round(goc[0])), int(round(goc[1])))
    T = mau_s[y0:y1, x0:x1]
    H, W = anh_s.shape
    sx0, sy0 = x0 + goc[0] - search_px, y0 + goc[1] - search_px
    sx1, sy1 = x1 + goc[0] + search_px, y1 + goc[1] + search_px
    cx0, cy0, cx1, cy1 = max(sx0, 0), max(sy0, 0), min(sx1, W), min(sy1, H)
    if cx1 - cx0 < T.shape[1] or cy1 - cy0 < T.shape[0] or T.std() == 0:
        return None
    R = cv2.matchTemplate(anh_s[cy0:cy1, cx0:cx1], T, cv2.TM_CCOEFF_NORMED)
    _, best, _, (bx, by) = cv2.minMaxLoc(R)
    r = int(PEAK_EXCLUDE_MM * PX)
    R2 = R.copy()
    R2[max(by - r, 0):by + r + 1, max(bx - r, 0):bx + r + 1] = -1
    second = float(R2.max()) if (R2 > -1).any() else -1.0
    ox, oy = dinh_duoi_pixel(R, bx, by)
    return cx0 + bx + ox - x0, cy0 + by + oy - y0, float(best), float(best - second)


def p2_net(anh_w, mau_e, mask, layout) -> tuple[dict, list]:
    """Số đo phép 2 cho 1 ảnh (ở WORK_DPI) + danh sách ô lưới."""
    e = ban_do_net(anh_w)
    mau_m = (mau_e > 0) & (mask > 0)
    anh_s, mau_s = mem(e), mem(np.where(mask > 0, mau_e, 0))

    # khop_net ở độ lệch 0 (đúng như ảnh trả về)
    dist = cv2.distanceTransform((e == 0).astype(np.uint8), cv2.DIST_L2, 3)
    khop_net = float((dist[mau_m] <= NEAR_MM * PX).mean())

    hx0, hy0, hx1, hy1 = (int(v * PX) for v in HEADER_MM)
    g = khop(anh_s, mau_s, (hx0, hy0, hx1, hy1), (0, 0), int(GLOBAL_SEARCH_MM * PX))
    gdx, gdy, gdiem, gduy = g if g else (0, 0, -1.0, 0.0)

    x0, y0, x1, y1 = GRID_AREA_MM
    tw, th = (x1 - x0) / GRID[0], (y1 - y0) / GRID[1]
    tiles = []
    for j in range(GRID[1]):
        for i in range(GRID[0]):
            b = (int((x0 + i * tw) * PX), int((y0 + j * th) * PX),
                 int((x0 + (i + 1) * tw) * PX), int((y0 + (j + 1) * th) * PX))
            frac = float(mau_m[b[1]:b[3], b[0]:b[2]].mean())
            t = {"i": i, "j": j, "box": b, "ti_le_net": frac, "dx": None, "dy": None, "diem": None, "duy_nhat": None}
            if frac >= MIN_TILE_EDGE:
                r = khop(anh_s, mau_s, b, (gdx, gdy), int(TILE_SEARCH_MM * PX))
                if r:
                    t.update(dx=r[0], dy=r[1], diem=r[2], duy_nhat=r[3])
            tiles.append(t)

    measured = [t for t in tiles if t["dx"] is not None]
    for t in tiles:
        t["tin_cay"] = t["dx"] is not None and t["duy_nhat"] >= nguong("duy_nhat_min")
    ok = [t for t in tiles if t["tin_cay"]]           # chỉ ô có đỉnh khớp duy nhất (tránh khớp nhầm chu kỳ)
    lech = np.array([np.hypot(t["dx"], t["dy"]) / PX for t in ok]) if ok else np.array([np.nan])
    lech_all = np.array([np.hypot(t["dx"], t["dy"]) / PX for t in measured]) if measured else np.array([np.nan])
    # độ nhất quán: lệch của mỗi ô so với trung vị các ô lân cận (8 hướng)
    by_ij = {(t["i"], t["j"]): t for t in ok}
    incons = []
    for t in ok:
        nb = [by_ij[(t["i"] + a, t["j"] + b)] for a in (-1, 0, 1) for b in (-1, 0, 1)
              if (a or b) and (t["i"] + a, t["j"] + b) in by_ij]
        if nb:
            mdx, mdy = np.median([n["dx"] for n in nb]), np.median([n["dy"] for n in nb])
            incons.append(np.hypot(t["dx"] - mdx, t["dy"] - mdy) / PX)
    diem = [t["diem"] for t in ok] or [np.nan]
    duy = [t["duy_nhat"] for t in measured] or [np.nan]
    d = {
        "khop_net": khop_net,
        "lech_toan_trang_mm": float(np.hypot(gdx, gdy) / PX),
        "lech_toan_trang_dx_mm": gdx / PX, "lech_toan_trang_dy_mm": gdy / PX,
        "diem_tieu_de": gdiem, "duy_nhat_tieu_de": gduy,
        "lech_trungvi_mm": float(np.median(lech)), "lech_max_mm": float(np.max(lech)),
        "lech_max_ca_o_khong_duy_nhat_mm": float(np.max(lech_all)),
        "so_o_luoi": len(measured), "so_o_tin_cay": len(ok),
        "diem_o_min": float(np.min(diem)), "diem_o_trungvi": float(np.median(diem)),
        "duy_nhat_o_min": float(np.min(duy)),
        "do_nhat_quan_mm": float(max(incons)) if incons else float("nan"),
    }
    return d, tiles, e


# ============================================================================ phép 3: nhãn
def doc_nhan_o() -> dict:
    """{ma_phieu: {(question, option): nhãn}} từ data/cell_labels.csv."""
    out = {}
    with (DATA / "cell_labels.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["sheet_id"], {})[(r["question"], r["option"])] = r["cell_label"]
    return out


def p3_nhan(aligned, layout, nhan: dict, phieu_trang=None) -> dict:
    """Mỗi hàng câu / cột chữ số có ô filled: hiệu = min(filled) − max(blank) (độ tối local_darkness).
    Mặc định đo tại toạ độ layout (không dò lại). phieu_trang (ảnh 300 DPI của phieu_trang.pdf) -> chế độ
    'dò lại': mỗi hàng câu / mỗi khối SBD, mã đề dò lệch ±4 mm như check_labels.py audit (dùng cho dung-sai).
    Trả số đo gộp + tách 'dap_an_*' (ô Ø5 mm) và 'chu_so_*' (bubble SBD/mã đề Ø4,4 mm, bước dọc 5,8 mm)."""
    groups = []                                              # [(loại, item dò lại, tâm, bán kính, nhãn)]
    ans = layout["answers"]
    for q in range(1, ans["num_questions"] + 1):
        groups.append(("dap_an", ("q", q), [ans["centers"][str(q)][o] for o in ans["options"]],
                       ans["bubble_radius"], [nhan[(str(q), o)] for o in ans["options"]]))
    for field in ("sbd", "exam_code"):
        f = layout[field]
        for c, col in enumerate(f["bubbles"]):
            groups.append(("chu_so", (field, 0), col, f["bubble_radius"],
                           [nhan[(f"{field}{c + 1}", str(k))] for k in range(10)]))
    shift = {}
    if phieu_trang is not None:
        search = round(SEARCH_MM * layout["dpi"] / 25.4)
        for item in {g[1] for g in groups}:
            shift[item] = register(aligned, phieu_trang, item_box(layout, item), search)
    hieu = {"dap_an": [], "chu_so": []}
    for kind, item, centers, r, labs in groups:
        if "filled" not in labs or "blank" not in labs:
            continue
        sx, sy = shift.get(item, (0, 0))
        d = [local_darkness(aligned, cx + sx, cy + sy, r) for cx, cy in centers]
        hieu[kind].append(min(v for v, l in zip(d, labs) if l == "filled") - max(v for v, l in zip(d, labs) if l == "blank"))

    def stats(h, p=""):
        h = np.array(h)
        return {f"{p}so_hang": len(h), f"{p}ti_le_hang_duong": float((h > 0).mean()), f"{p}hieu_min": float(h.min()),
                f"{p}hieu_p10": float(np.percentile(h, 10)), f"{p}hieu_trungvi": float(np.median(h))}
    return {**stats(hieu["dap_an"] + hieu["chu_so"]), **stats(hieu["dap_an"], "dap_an_"), **stats(hieu["chu_so"], "chu_so_")}


# ============================================================================ kết luận tự động
def ket_luan_tu_dong(r: dict) -> tuple[str, str]:
    """('dung'|'sai'|'xem', lý do) theo nguong.json['luat']:
    dung = đạt TẤT CẢ phép quyết định; sai = trượt rõ >= 2 phép; còn lại = xem. Thiếu/NaN = trượt rõ.
    ti_le_hang_duong chỉ áp dụng cho phiếu."""
    if r["tra_anh"] != "co":
        return "", ""                                      # từ chối: không cần kết luận nắn đúng/sai
    if NGUONG is None:
        return "xem", "chưa có nguong.json"
    truot, ro = [], []
    for k in QUYET_DINH:
        n = NGUONG[k]
        if n.get("ap_dung") == "chi_phieu" and r.get("loai") != "phieu":
            continue
        v = r.get(n["so_do"])
        v = float(v) if v not in (None, "") else float("nan")
        if not np.isfinite(v):
            truot.append(f"{n['so_do']}=?")
            ro.append(n["so_do"])
            continue
        lo = n["huong"] == "min"
        if (v < n["gia_tri"]) if lo else (v > n["gia_tri"]):
            truot.append(f"{n['so_do']}={v:.3g}")
            if (v < n["truot_ro"]) if lo else (v > n["truot_ro"]):
                ro.append(n["so_do"])
    if not truot:
        return "dung", "đạt mọi phép"
    if len(ro) >= 2:
        return "sai", "trượt rõ: " + ", ".join(t for t in truot if t.split("=")[0] in ro)
    return "xem", "trượt: " + ", ".join(truot) + (f" (rõ: {', '.join(ro)})" if ro else "")


def co_giay_cong(r: dict) -> bool:
    """Chỉ với ảnh 'dung': ảnh nắn sai thì lech_max lớn là đương nhiên, cờ vô nghĩa."""
    if r.get("ket_luan_tu_dong") != "dung":
        return False
    v = r.get("lech_max_mm")
    return v not in (None, "") and np.isfinite(float(v)) and float(v) > nguong("giay_cong_lech_max_mm")


# ============================================================================ xuất ảnh / HTML
def anh_chong(anh_w, mau_e, tiles, mu: bool = False) -> np.ndarray:
    """Ảnh nắn (xám nhạt) + nét mẫu màu đỏ + mũi tên lệch từng ô lưới (phóng x5; xanh dương = ô tin cậy,
    xám = đỉnh khớp không duy nhất, không tính vào lech_*). mu = True (xem mù, Bước 7): KHÔNG vẽ lưới / mũi tên / số mm."""
    base = cv2.cvtColor(cv2.addWeighted(anh_w, 0.6, np.full_like(anh_w, 255), 0.4, 0), cv2.COLOR_GRAY2BGR)
    base[mau_e > 0] = (0, 0, 230)
    for t in ([] if mu else tiles):
        x0, y0, x1, y1 = t["box"]
        cv2.rectangle(base, (x0, y0), (x1, y1), (200, 200, 200), 1)
        if t["dx"] is None:
            continue
        c = ((x0 + x1) // 2, (y0 + y1) // 2)
        color = (200, 80, 0) if t["tin_cay"] else (150, 150, 150)
        cv2.arrowedLine(base, c, (int(c[0] + 5 * t["dx"]), int(c[1] + 5 * t["dy"])), color, 2, tipLength=0.2)
        cv2.putText(base, f"{np.hypot(t['dx'], t['dy']) / PX:.1f}" + ("" if t["tin_cay"] else "?"), (x0 + 4, y0 + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return base


def ghi_jpg(path: Path, img, max_w=None, q=85):
    if max_w and img.shape[1] > max_w:
        img = cv2.resize(img, (max_w, round(img.shape[0] * max_w / img.shape[1])), interpolation=cv2.INTER_AREA)
    cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tofile(path)


COND_COLOR = {"C1": "#2a7", "C2": "#555", "C3": "#c50", "C4": "#c90", "D": "#36c"}
STRIP_METRICS = [("khop_net", "phép 2: khop_net (cao = khớp)"),
                 ("lech_toan_trang_mm", "phép 2: lech_toan_trang_mm"),
                 ("lech_trungvi_mm", "phép 2: lech_trungvi_mm"),
                 ("lech_max_mm", "phép 2: lech_max_mm"),
                 ("do_nhat_quan_mm", "phép 2: do_nhat_quan_mm"),
                 ("duy_nhat_tieu_de", "phép 2: duy_nhat_tieu_de"),
                 ("ti_le_hang_duong", "phép 3: ti_le_hang_duong (chỉ phiếu)"),
                 ("hieu_p10", "phép 3: hieu_p10 (chỉ phiếu)"),
                 ("den_min", "phép 1: den_min marker")]


def strip_svg(rows, key, title) -> str:
    """Biểu đồ dải: mỗi ảnh 1 chấm (màu theo điều kiện chụp), rê chuột thấy tên ảnh."""
    vals = [(r["anh"], r["dieu_kien"], r[key]) for r in rows
            if isinstance(r.get(key), float) and np.isfinite(r[key])]
    if not vals:
        return ""
    lo, hi = min(v[2] for v in vals), max(v[2] for v in vals)
    if hi == lo:
        hi = lo + 1
    W, H, pad = 760, 70, 30
    rng = np.random.default_rng(0)
    dots = []
    for name, cond, v in vals:
        x = pad + (v - lo) / (hi - lo) * (W - 2 * pad)
        y = 18 + rng.uniform(0, H - 36)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{COND_COLOR[cond]}" fill-opacity="0.75">'
                    f'<title>{name}: {v:.3f}</title></circle>')
    ticks = "".join(f'<text x="{pad + k / 4 * (W - 2 * pad):.0f}" y="{H - 4}" font-size="10" text-anchor="middle">'
                    f'{lo + k / 4 * (hi - lo):.2f}</text>' for k in range(5))
    return (f'<div class="strip"><b>{html.escape(title)}</b><br><svg width="{W}" height="{H}">'
            f'<line x1="{pad}" y1="{H - 16}" x2="{W - pad}" y2="{H - 16}" stroke="#999"/>{"".join(dots)}{ticks}</svg></div>')


def fmt(v, nd=3) -> str:
    if isinstance(v, float):
        return "" if not np.isfinite(v) else f"{v:.{nd}f}"
    return html.escape(str(v))


def ve_tu_giac(gray: np.ndarray, ct: dict) -> np.ndarray:
    """Ảnh gốc (màu) + ứng viên marker (vòng xanh dương) + tứ giác 4 marker được chọn (xanh lá) + TL (chấm đỏ).
    Kiểm marker bằng mắt phải xem TỨ GIÁC có khớp 4 góc tờ chính không, không chỉ từng ô (bài học 3a, 0007_C3)."""
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    d = max(gray.shape) / 1400                       # nét vẽ theo cỡ ảnh để còn thấy khi thu nhỏ
    for x, y in ct["ung_vien"]:
        cv2.circle(img, (int(x), int(y)), int(40 * d), (230, 120, 0), max(1, int(3 * d)))
    if ct.get("marker") is not None:
        q = np.int32(ct["marker"])
        cv2.polylines(img, [q], True, (0, 190, 0), max(2, int(4 * d)), cv2.LINE_AA)
        cv2.circle(img, tuple(q[0]), int(22 * d), (0, 0, 230), -1)
        cv2.putText(img, "TL", (int(q[0][0] + 30 * d), int(q[0][1] - 20 * d)), cv2.FONT_HERSHEY_SIMPLEX, 1.6 * d,
                    (0, 0, 230), max(2, int(4 * d)), cv2.LINE_AA)
    return img


def viet_html_mu(rows, path: Path, ten_pp: str, split: str):
    """Xem bằng mắt MÙ (Bước 7, đăng ký trước): CHỈ ảnh gốc + tứ giác 4 marker + ảnh nắn chồng nét mẫu (không lưới, không
    mũi tên, không số mm). Không kết luận máy, không số đo, không thời gian; sắp theo tên ảnh (không theo số đo)."""
    body = []
    for r in sorted(rows, key=lambda r: r["anh"]):
        al = (f'<a href="anh/{r["anh"]}_chong.jpg" target="_blank"><img src="anh/{r["anh"]}_chong_nho.jpg" width="420"></a>'
              if r["tra_anh"] == "co" else "<b>Phương pháp KHÔNG trả ảnh nắn</b> (từ chối)")
        lon = "_goc_lon" if "so_ung_vien" in r else "_goc"
        goc = f'<a href="anh/{r["anh"]}{lon}.jpg" target="_blank"><img src="anh/{r["anh"]}_goc.jpg" width="320"></a>'
        body.append(f'<tr id="{r["anh"]}"><td><b>{r["anh"]}</b><br>{r["dieu_kien"]}</td><td>{al}</td><td>{goc}</td></tr>')
    path.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Xem mù – {ten_pp} – {split}</title>
<style>body{{font-family:sans-serif;margin:16px}} td{{vertical-align:top;border-bottom:1px solid #ddd;padding:6px}}
img{{border:1px solid #ccc}}</style></head><body>
<h2>Xem bằng mắt MÙ: phương pháp <code>{ten_pp}</code>, tập {split} ({len(rows)} ảnh)</h2>
<p>Không có kết luận máy và số đo (đăng ký trước, Bước 7). Ảnh giữa: ảnh nắn (xám) + <span style="color:#e00">nét phiếu
mẫu (đỏ)</span> – nắn đúng ⇒ nét đỏ đè lên nét in ở MỌI vùng trang, đúng chiều (tiêu đề ở trên). Ảnh phải: ảnh gốc
{"+ <span style='color:#0a0'>tứ giác 4 marker được chọn</span> (chấm đỏ = TL)" if any("so_ung_vien" in r for r in rows) else ""}.
Bấm ảnh để xem cỡ lớn.<br>Ghi kết luận cho MỌI ảnh có ảnh nắn vào <code>{ten_xem(split)['csv']}</code>, cột
<code>ket_luan_mat</code> = <code>dung</code> / <code>sai</code>, lý do vào <code>ghi_chu</code>.</p>
<table><tr><th>Ảnh</th><th>Ảnh nắn + nét mẫu</th><th>Ảnh gốc</th></tr>{"".join(body)}</table></body></html>""",
                    encoding="utf-8")


def viet_html(rows, path: Path, ten_pp: str, split: str, mu: bool = False):
    if mu:
        return viet_html_mu(rows, path, ten_pp, split)
    legend = " ".join(f'<span style="color:{c}">● {k}</span>' for k, c in COND_COLOR.items())
    strips = "".join(strip_svg(rows, k, t) for k, t in STRIP_METRICS)
    rows = sorted(rows, key=lambda r: (r["tra_anh"] == "co", r.get("khop_net", 0)))   # từ chối, rồi khớp kém nhất
    body = []
    for r in rows:
        metrics = "<br>".join(f"{k}: <b>{fmt(r.get(k))}</b>" for k, _ in STRIP_METRICS if k in r) + \
                  f"<br>dx, dy toàn trang (mm): {fmt(r.get('lech_toan_trang_dx_mm'), 2)}, {fmt(r.get('lech_toan_trang_dy_mm'), 2)}" \
                  f"<br>diem_o_min / trungvi: {fmt(r.get('diem_o_min'), 2)} / {fmt(r.get('diem_o_trungvi'), 2)}" \
                  f"<br>duy_nhat_o_min: {fmt(r.get('duy_nhat_o_min'), 3)}; ô lưới tin cậy: " \
                  f"<b>{r.get('so_o_tin_cay', '')}</b>/{r.get('so_o_luoi', '')}" \
                  f"<br>lech_max kể cả ô không duy nhất: {fmt(r.get('lech_max_ca_o_khong_duy_nhat_mm'), 2)} mm" \
                  f"<br>tự động: <b>{r['ket_luan_tu_dong']}</b> ({html.escape(r['ly_do_tu_dong'])})" \
                  if r["tra_anh"] == "co" else f"<b>TỪ CHỐI</b>: {html.escape(r['ly_do'])}"
        if "huong_xoay" in r:
            metrics += (f"<br><b>verify</b>: hướng {r['huong_xoay']}° (đúng {r['huong_dung']}°), S0 {fmt(r.get('S0'))}, "
                        f"S180 {fmt(r.get('S180'))}, biên chiều {fmt(r.get('bien_chieu'))}, blur {fmt(r.get('blur_score'), 4)}, "
                        f"lõi marker {fmt(r.get('loi_marker'))}")
        al = (f'<a href="anh/{r["anh"]}_chong.jpg" target="_blank"><img src="anh/{r["anh"]}_chong_nho.jpg" width="420"></a>'
              if r["tra_anh"] == "co" else "")
        goc = (f'<a href="anh/{r["anh"]}_goc_lon.jpg" target="_blank"><img src="anh/{r["anh"]}_goc.jpg" width="320"></a>'
               f'<br><small>{r["so_ung_vien"]} ứng viên, {r.get("so_bo_dat", "")} bộ 4 đạt</small>'
               if "so_ung_vien" in r else
               f'<a href="anh/{r["anh"]}_goc.jpg" target="_blank"><img src="anh/{r["anh"]}_goc.jpg" width="200"></a>')
        body.append(f'<tr id="{r["anh"]}"><td><b>{r["anh"]}</b><br>{r["dieu_kien"]}<br>{r["giay"]:.1f} s</td>'
                    f'<td class="m">{metrics}</td><td>{al}</td><td>{goc}</td></tr>')
    path.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Xem bằng mắt – {ten_pp} – {split}</title>
<style>body{{font-family:sans-serif;margin:16px}} td{{vertical-align:top;border-bottom:1px solid #ddd;padding:6px}}
td.m{{font-size:12px;width:300px}} .strip{{margin:6px 0}} img{{border:1px solid #ccc}}</style></head><body>
<h2>Xem bằng mắt: phương pháp <code>{ten_pp}</code>, tập {split} ({len(rows)} ảnh)</h2>
<p>Chưa có ngưỡng – mọi ảnh đang là <b>xem</b>. Ảnh giữa: ảnh nắn (xám) + <span style="color:#e00">nét phiếu mẫu (đỏ)</span>
+ <span style="color:#05c">mũi tên lệch từng ô lưới, phóng ×5, số = mm</span> (xám + "?" = đỉnh khớp không duy nhất,
không tính vào lech_*); bấm để xem cỡ 150 DPI.
Nắn đúng ⇒ nét đỏ nằm đè lên nét in trên ảnh. Ảnh phải: ảnh gốc (đúng như phương pháp đọc){
"; nếu phương pháp báo marker: <span style='color:#0a0'>tứ giác xanh lá</span> = 4 marker được chọn, "
"<span style='color:#e00'>chấm đỏ</span> = góc gán TL, <span style='color:#07e'>vòng xanh dương</span> = ứng viên – "
"<b>kiểm tứ giác có khớp 4 góc tờ chính không</b> (bấm để xem cỡ lớn)" if any("so_ung_vien" in r for r in rows) else ""}.
Sắp xếp: từ chối trước, rồi <code>khop_net</code> thấp → cao.<br>
Ghi kết luận vào <code>xem_bang_mat.csv</code>, cột <code>ket_luan_mat</code> = <code>dung</code> / <code>sai</code> (để trống nếu chưa xem).</p>
<p>{legend}</p>{strips}
<table><tr><th>Ảnh</th><th>Số đo</th><th>Ảnh nắn + nét mẫu</th><th>Ảnh gốc</th></tr>{"".join(body)}</table>
</body></html>""", encoding="utf-8")


# ============================================================================ lệnh run
def nap_mau(layout) -> dict:
    """Loại trang -> ảnh xám trang mẫu 300 DPI (trang 1 của PDF; các trang chỉ khác chữ số mã)."""
    return {loai: render_pdf_page(ANSWER_SHEET / "output" / pdf, layout["dpi"])
            for loai, pdf in (("phieu", "phieu_danh_so.pdf"), ("chu_so", "trang_chu_so.pdf"))}


def ten_xem(split: str) -> dict:
    """Tên file xem bằng mắt theo tập. Dev giữ tên cũ (không đổi file của Bước 1–6); tập khác có hậu tố _<split>."""
    h = "" if split == "dev" else f"_{split}"
    return {"html": f"xem_bang_mat{h}.html", "csv": f"xem_bang_mat{h}.csv", "can": f"can_xem{h}.html"}


def cmd_run(a) -> None:
    if a.split == "test" and not a.xac_nhan_test:
        sys.exit("Tập test (0035–0040) chỉ chạy MỘT LẦN ở Bước 7 (docs/ke_hoach_tuan4.md). "
                 "Nếu đúng là lúc đó, thêm --xac-nhan-test.")
    f = PHUONG_PHAP[a.phuong_phap]
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    page_px = layout["page_px"]
    out = EVAL_DIR / a.phuong_phap
    mu = a.split != "dev"           # Bước 7: xem bằng mắt MÙ – không hiện / in kết luận máy và số đo
    if mu and (out / f"diem_{a.split}.csv").exists():
        sys.exit(f"{out / f'diem_{a.split}.csv'} đã có – tập {a.split} chỉ chạy MỘT LẦN (đăng ký trước, Bước 7). "
                 f"Không chạy lại để lấy số khác.")
    (out / "anh").mkdir(parents=True, exist_ok=True)

    mau = {loai: ban_do_net(to_work(g, page_px)) for loai, g in nap_mau(layout).items()}
    mask = mat_na(layout, mau["phieu"].shape)
    nhan = doc_nhan_o()

    rows, tile_rows = [], []
    mv3 = marker_v3() if a.phuong_phap not in ("align_cu", "v2_load", "v3_hinh_hoc") else {}
    images = list_images(a.split)
    for n, anh in enumerate(images, 1):
        ct = {}
        aligned, ly_do, giay = goi_phuong_phap(f, anh, page_px, ct)
        r = {"phuong_phap": a.phuong_phap, "anh": anh.ten, "loai": anh.loai, "dieu_kien": anh.dieu_kien,
             "tra_anh": "co" if aligned is not None else "khong", "ly_do": ly_do, "giay": giay}
        goc = doc_xam(anh.duong_dan)
        if "ung_vien" in ct:        # phương pháp báo marker -> vẽ tứ giác + ứng viên lên ảnh gốc (bài học 3a)
            goc = ve_tu_giac(goc, ct)
            ghi_jpg(out / "anh" / f"{anh.ten}_goc_lon.jpg", goc, max_w=1400, q=85)
            r["so_ung_vien"], r["so_bo_dat"] = len(ct["ung_vien"]), ct.get("so_bo_dat", "")
            if ct.get("marker") is not None:
                for g, (x, y) in zip(("tl", "tr", "br", "bl"), ct["marker"]):
                    r[f"marker_{g}_x"], r[f"marker_{g}_y"] = float(x), float(y)
        if "huong_xoay" in ct:      # v4+: chiều phiếu + số đo của verify(); chiều đúng lấy từ v3_hinh_hoc
            r["huong_xoay"] = ct["huong_xoay"]
            r["huong_dung"] = huong_tu_marker(mv3[anh.ten]) if anh.ten in mv3 else ""
            r.update({k: float(ct[k]) for k in V4_COT if k in ct})
        ghi_jpg(out / "anh" / f"{anh.ten}_goc.jpg", goc, max_w=400, q=80)
        if aligned is not None:
            fill = marker_fill(aligned, layout)
            r.update({f"den_{c}": float(v) for c, v in fill.items()})
            r["den_min"] = float(min(fill.values()))
            anh_w = to_work(aligned, page_px)
            d2, tiles, _ = p2_net(anh_w, mau[anh.loai], mask, layout)
            r.update(d2)
            for t in tiles:
                tile_rows.append({"anh": anh.ten, "i": t["i"], "j": t["j"], "ti_le_net": t["ti_le_net"],
                                  "dx_mm": t["dx"] / PX if t["dx"] is not None else "",
                                  "dy_mm": t["dy"] / PX if t["dy"] is not None else "",
                                  "diem": t["diem"] if t["diem"] is not None else "",
                                  "duy_nhat": t["duy_nhat"] if t["duy_nhat"] is not None else "",
                                  "tin_cay": int(t["tin_cay"])})
            if anh.loai == "phieu":
                r.update(p3_nhan(aligned, layout, nhan[anh.ma]))
            chong = anh_chong(anh_w, mau[anh.loai], tiles, mu=mu)
            ghi_jpg(out / "anh" / f"{anh.ten}_chong.jpg", chong)
            ghi_jpg(out / "anh" / f"{anh.ten}_chong_nho.jpg", chong, max_w=840, q=80)
        r["ket_luan_tu_dong"], r["ly_do_tu_dong"] = ket_luan_tu_dong(r)
        r["giay_cong"] = int(co_giay_cong(r))
        rows.append(r)
        if mu:
            tom = "đã xử lý" if aligned is not None else f"TỪ CHỐI: {ly_do}"
        else:
            tom = (f"khop_net={r['khop_net']:.2f} lech_trungvi={r['lech_trungvi_mm']:.1f}mm "
                   f"lech_max={r['lech_max_mm']:.1f}mm" if aligned is not None else f"TỪ CHỐI: {ly_do}")
        print(f"[{n:2d}/{len(images)}] {anh.ten:8s} {tom}")

    cols = ["phuong_phap", "anh", "loai", "dieu_kien", "tra_anh", "ly_do", "giay", "ket_luan_tu_dong", "ly_do_tu_dong",
            "giay_cong",
            "den_tl", "den_tr", "den_br", "den_bl", "den_min",
            "khop_net", "lech_toan_trang_mm", "lech_toan_trang_dx_mm", "lech_toan_trang_dy_mm",
            "diem_tieu_de", "duy_nhat_tieu_de", "lech_trungvi_mm", "lech_max_mm",
            "lech_max_ca_o_khong_duy_nhat_mm", "so_o_luoi", "so_o_tin_cay",
            "diem_o_min", "diem_o_trungvi", "duy_nhat_o_min", "do_nhat_quan_mm",
            "so_hang", "ti_le_hang_duong", "hieu_min", "hieu_p10", "hieu_trungvi"]
    if any("so_ung_vien" in r for r in rows):      # chỉ phương pháp báo marker – CSV của phương pháp cũ giữ nguyên cột
        cols += ["so_ung_vien", "so_bo_dat"] + [f"marker_{g}_{c}" for g in ("tl", "tr", "br", "bl") for c in "xy"]
    if any("huong_xoay" in r for r in rows):        # chỉ v4+ – CSV của phương pháp cũ giữ nguyên cột
        cols += ["huong_xoay", "huong_dung"] + V4_COT
    with (out / f"diem_{a.split}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items() if k in cols})
    with (out / f"o_luoi_{a.split}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tile_rows[0]) if tile_rows else ["anh"])
        w.writeheader()
        for t in tile_rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in t.items()})

    tx = ten_xem(a.split)
    viet_html(rows, out / tx["html"], a.phuong_phap, a.split, mu=mu)
    if "huong_xoay" in rows[0] and not mu:      # mù: người dùng xem MỌI ảnh, không có danh sách "cần xem" của máy
        can = [r for r in rows if r["tra_anh"] != "co" or r["ket_luan_tu_dong"] in ("sai", "xem")
               or r["huong_xoay"] != r["huong_dung"]]
        viet_html(can, out / tx["can"], a.phuong_phap, a.split)
        print(f"{tx['can']}: {len(can)} ảnh cần xem bằng mắt (từ chối / sai / xem / lệch chiều)")
    review = out / tx["csv"]
    if review.exists():
        print(f"\nGIỮ NGUYÊN {review} (đã có – có thể chứa kết luận bằng mắt).")
    else:
        with review.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["phuong_phap", "anh", "dieu_kien", "ket_luan_mat", "ghi_chu"])
            for r in sorted(rows, key=lambda r: r["anh"]) if mu else rows:
                w.writerow([a.phuong_phap, r["anh"], r["dieu_kien"], "", ""])

    print(f"\nĐã ghi vào {out}:")
    print(f"  diem_{a.split}.csv, o_luoi_{a.split}.csv, {tx['html']}, {tx['csv']}, anh/")
    tu_choi = [r for r in rows if r["tra_anh"] == "khong"]
    print(f"Trả ảnh: {len(rows) - len(tu_choi)}/{len(rows)}; từ chối: {len(tu_choi)}"
          + (" (" + ", ".join(r["anh"] for r in tu_choi) + ")" if tu_choi else ""))
    if mu:
        print(f"XEM MÙ: mở {tx['html']}, ghi ket_luan_mat (dung / sai) cho MỌI ảnh trả về vào {tx['csv']}. "
              f"KHÔNG mở diem_{a.split}.csv trước khi ghi xong. Kết luận máy chỉ hiện ở finalize.")
        return
    from collections import Counter
    dem = Counter(r["ket_luan_tu_dong"] for r in rows if r["tra_anh"] == "co")
    print(f"Kết luận tự động: dung {dem['dung']}, sai {dem['sai']}, xem {dem['xem']}; "
          f"cờ giấy cong: {', '.join(r['anh'] for r in rows if r.get('giay_cong')) or 'không'}")


# ============================================================================ lệnh tu-kiem (kiểm chứng phép 2)
def dich(gray300, dx_mm, dy_mm) -> np.ndarray:
    """Dịch ảnh 300 DPI một lượng (mm) dưới pixel; vùng lộ ra tô trắng như giấy."""
    s = 300 / 25.4
    M = np.float32([[1, 0, dx_mm * s], [0, 1, dy_mm * s]])
    return cv2.warpAffine(gray300, M, (gray300.shape[1], gray300.shape[0]), flags=cv2.INTER_LINEAR, borderValue=255)


TU_KIEM_MAU = [("mau_khong_dich", 0.0, 0.0), ("mau_dich_0_5mm_doc", 0.0, 0.5)]


def cmd_tu_kiem(a) -> None:
    """Phép 2 trên chính trang mẫu render (không qua ảnh chụp): độ lệch đo được phải bằng độ lệch đã dịch.
    Sai lệch ở đây là sai lệch của PHÉP ĐO (không thể do marker hay máy in)."""
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    page_px = layout["page_px"]
    goc = nap_mau(layout)
    mau = {loai: ban_do_net(to_work(g, page_px)) for loai, g in goc.items()}
    mask = mat_na(layout, mau["phieu"].shape)
    out_rows = []
    print(f"{'ca':22s} {'trang':7s} {'đã dịch dx,dy':>14s} | {'tiêu đề dx,dy':>14s} | {'ô lưới tb dx,dy':>16s} | "
          f"{'sai số tb':>9s} {'sai số max':>10s} {'ô tin cậy':>9s}")
    for ten, dx, dy in TU_KIEM_MAU:
        for loai, g in goc.items():
            d, tiles, _ = p2_net(to_work(dich(g, dx, dy), page_px), mau[loai], mask, layout)
            ok = [t for t in tiles if t["tin_cay"]]
            tdx = np.array([t["dx"] / PX for t in ok]); tdy = np.array([t["dy"] / PX for t in ok])
            err = np.hypot(tdx - dx, tdy - dy)
            row = {"ca": ten, "trang": loai, "dich_dx_mm": dx, "dich_dy_mm": dy,
                   "tieu_de_dx_mm": d["lech_toan_trang_dx_mm"], "tieu_de_dy_mm": d["lech_toan_trang_dy_mm"],
                   "o_luoi_dx_tb_mm": float(tdx.mean()), "o_luoi_dy_tb_mm": float(tdy.mean()),
                   "sai_so_tb_mm": float(err.mean()), "sai_so_max_mm": float(err.max()), "so_o_tin_cay": len(ok)}
            out_rows.append(row)
            print(f"{ten:22s} {loai:7s} {dx:6.2f},{dy:6.2f}  | {row['tieu_de_dx_mm']:6.3f},{row['tieu_de_dy_mm']:6.3f} | "
                  f"{row['o_luoi_dx_tb_mm']:7.3f},{row['o_luoi_dy_tb_mm']:7.3f} | {row['sai_so_tb_mm']:9.3f} "
                  f"{row['sai_so_max_mm']:10.3f} {len(ok):9d}")
    path = EVAL_DIR / "_tu_kiem" / "mau.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        for r in out_rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
    print(f"\nĐã ghi {path}")
    tu_kiem_anh_that(a, layout, goc, mau, mask)


def ghi_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})


def anh_dung_bang_mat(ten_pp: str, chi_phieu=False) -> list[Anh]:
    """Ảnh dev mà người dùng đã kết luận 'dung' bằng mắt (xem_bang_mat.csv của phương pháp)."""
    p = EVAL_DIR / ten_pp / "xem_bang_mat.csv"
    dung = {r["anh"] for r in csv.DictReader(p.open(encoding="utf-8-sig")) if r["ket_luan_mat"] == "dung"}
    return [x for x in list_images("dev") if x.ten in dung and (x.loai == "phieu" or not chi_phieu)]


def xoay(gray300, goc_do) -> np.ndarray:
    h, w = gray300.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), goc_do, 1.0)
    return cv2.warpAffine(gray300, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)


# (tên ca, hàm làm hỏng ảnh nắn 300 DPI, có đổi loại trang mẫu không)
CA_LAM_HONG = [
    ("goc", lambda g: g, False),
    ("dich_2mm_doc", lambda g: dich(g, 0, 2), False),
    ("dich_7mm_ngang", lambda g: dich(g, 7, 0), False),
    ("dich_11mm_doc", lambda g: dich(g, 0, 11), False),
    ("dich_5_8mm_doc", lambda g: dich(g, 0, 5.8), False),
    ("xoay_1do", lambda g: xoay(g, 1), False),
    ("xoay_180", lambda g: np.ascontiguousarray(g[::-1, ::-1]), False),
    ("nham_loai_trang", lambda g: g, True),
]
def tu_kiem_anh_that(a, layout, goc, mau, mask) -> None:
    """Kiểm chứng LUẬT kết luận (nguong.json) trên ảnh thật:
    (a) mọi ảnh không bị kết luận 'sai' bằng mắt phải ra 'dung' (đọc ket_luan_tu_dong trong diem_dev.csv – cần chạy
        run sau khi đổi nguong.json);
    (b) ảnh 'dung' bằng mắt bị làm hỏng cố ý phải ra 'sai' hoặc 'xem' – không ca nào được 'dung'."""
    out = EVAL_DIR / a.phuong_phap
    mat = {r["anh"]: r["ket_luan_mat"] for r in csv.DictReader((out / "xem_bang_mat.csv").open(encoding="utf-8-sig"))}
    diem = list(csv.DictReader((out / "diem_dev.csv").open(encoding="utf-8-sig")))
    tot = [r for r in diem if mat[r["anh"]] != "sai"]
    hong_tot = [r for r in tot if r["ket_luan_tu_dong"] != "dung"]
    sai_mat = [r for r in diem if mat[r["anh"]] == "sai"]
    from collections import Counter
    print(f"\n(a) {len(tot)} ảnh không-sai bằng mắt -> dung {len(tot) - len(hong_tot)}/{len(tot)}"
          + ("" if not hong_tot else " – KHÔNG ĐẠT: " + ", ".join(f"{r['anh']} {r['ket_luan_tu_dong']} ({r['ly_do_tu_dong']})"
                                                         for r in hong_tot)))
    print(f"    (thêm) {len(sai_mat)} ảnh sai bằng mắt -> {dict(Counter(r['ket_luan_tu_dong'] for r in sai_mat))}"
          + "".join(f"\n      {r['anh']}: {r['ket_luan_tu_dong']} ({r['ly_do_tu_dong']})" for r in sai_mat
                    if r["ket_luan_tu_dong"] != "sai"))
    nhan = doc_nhan_o()
    f = PHUONG_PHAP[a.phuong_phap]
    rows = []
    images = anh_dung_bang_mat(a.phuong_phap)
    print(f"\n(b) Ảnh 'dung' bằng mắt bị làm hỏng: {', '.join(x.ten for x in images)}")
    print(f"{'ca':16s} {'ảnh':8s} {'den':>5s} {'tđề':>5s} {'ô tc':>4s} {'hàng+':>5s} {'lệch tt':>7s} {'lệch tv':>7s}  kết luận")
    for anh in images:
        aligned, _, _ = goi_phuong_phap(f, anh, layout["page_px"])
        for ten, ham, doi_trang in CA_LAM_HONG:
            g = ham(aligned)
            loai_mau = ("chu_so" if anh.loai == "phieu" else "phieu") if doi_trang else anh.loai
            r = {"ca": ten, "anh": anh.ten, "loai": anh.loai, "dieu_kien": anh.dieu_kien, "loai_mau": loai_mau,
                 "tra_anh": "co", "den_min": float(min(marker_fill(g, layout).values()))}
            d2, _, _ = p2_net(to_work(g, layout["page_px"]), mau[loai_mau], mask, layout)
            r.update({k: d2[k] for k in ("khop_net", "diem_tieu_de", "so_o_tin_cay", "lech_toan_trang_mm",
                                         "lech_trungvi_mm", "lech_max_mm")})
            r["ti_le_hang_duong"] = p3_nhan(g, layout, nhan[anh.ma])["ti_le_hang_duong"] if anh.loai == "phieu" else ""
            r["ket_luan_tu_dong"], r["ly_do_tu_dong"] = ket_luan_tu_dong(r)
            rows.append(r)
            hd = f"{r['ti_le_hang_duong']:5.2f}" if r["ti_le_hang_duong"] != "" else "    -"
            print(f"{ten:16s} {anh.ten:8s} {r['den_min']:5.2f} {r['diem_tieu_de']:5.2f} "
                  f"{r['so_o_tin_cay']:4d} {hd} {r['lech_toan_trang_mm']:7.2f} {r['lech_trungvi_mm']:7.2f}  "
                  f"{r['ket_luan_tu_dong']:4s} ({r['ly_do_tu_dong']})")
    ghi_csv(out / "tu_kiem_anh_dev.csv", rows)
    hong = [r for r in rows if r["ca"] != "goc"]
    lot = [r for r in hong if r["ket_luan_tu_dong"] == "dung"]
    goc_khong_dung = [r for r in rows if r["ca"] == "goc" and r["ket_luan_tu_dong"] != "dung"]
    print(f"\n(b) {len(hong)} ca làm hỏng -> {dict(Counter(r['ket_luan_tu_dong'] for r in hong))}; "
          f"ra 'dung' (LỌT): {len(lot)}" + (" – " + ", ".join(f"{r['ca']}:{r['anh']}" for r in lot) if lot else ""))
    print("Bảng ca × kết luận (số ảnh):")
    for ten, _, _ in CA_LAM_HONG:
        c = Counter(r["ket_luan_tu_dong"] for r in rows if r["ca"] == ten)
        print(f"  {ten:16s} dung {c['dung']}  xem {c['xem']}  sai {c['sai']}")
    if goc_khong_dung:
        print("CHÚ Ý – ảnh gốc chưa làm hỏng không ra 'dung': " + ", ".join(f"{r['anh']} ({r['ly_do_tu_dong']})" for r in goc_khong_dung))
    print(f"Đã ghi {out / 'tu_kiem_anh_dev.csv'}")


# ============================================================================ lệnh dung-sai (dung sai OMR)
DUNG_SAI_MM = [round(0.25 * k, 2) for k in range(17)]                      # 0 … 4 mm
HUONG = [(1, 0), (-1, 0), (0, 1), (0, -1), (0.7071, 0.7071), (-0.7071, 0.7071), (0.7071, -0.7071), (-0.7071, -0.7071)]


def cmd_dung_sai(a) -> None:
    """Dung sai lệch của OMR: dịch ảnh phiếu nắn đúng (bằng mắt) d mm theo 8 hướng, đo lại phép 3 ở 2 chế độ:
    co_dinh (đọc tại toạ độ layout) và do_lai (dò lại từng hàng / khối ±4 mm như audit). Dung sai = d lớn nhất
    mà mọi hàng câu / cột chữ số vẫn có ô filled tối hơn mọi ô blank (ti_le_hang_duong = 1) ở mọi ảnh, mọi hướng,
    mọi d' ≤ d. Không tính 0014_C2 (giấy cong: đã lệch cục bộ ~4 mm khi d = 0) vào dung sai, chỉ in kèm."""
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    out = EVAL_DIR / a.phuong_phap
    nhan = doc_nhan_o()
    trang = render_pdf_page(ANSWER_SHEET / "output" / "phieu_trang.pdf", layout["dpi"])
    f = PHUONG_PHAP[a.phuong_phap]
    images = anh_dung_bang_mat(a.phuong_phap, chi_phieu=True)
    print(f"Ảnh phiếu 'dung' bằng mắt: {', '.join(x.ten for x in images)}  (dung sai không tính 0014_C2)")
    rows = []
    for anh in images:
        aligned, _, _ = goi_phuong_phap(f, anh, layout["page_px"])
        for d in DUNG_SAI_MM:
            for hx, hy in (HUONG if d > 0 else [(0, 0)]):
                g = dich(aligned, d * hx, d * hy)
                for che_do, pt in (("co_dinh", None), ("do_lai", trang)):
                    m = p3_nhan(g, layout, nhan[anh.ma], pt)
                    for kind in ("dap_an", "chu_so"):
                        rows.append({"anh": anh.ten, "che_do": che_do, "loai_o": kind, "d_mm": d,
                                     "huong_x": hx, "huong_y": hy,
                                     "ti_le_hang_duong": m[f"{kind}_ti_le_hang_duong"],
                                     "hieu_min": m[f"{kind}_hieu_min"], "hieu_p10": m[f"{kind}_hieu_p10"]})
        print(f"  xong {anh.ten}")
    ghi_csv(out / "dung_sai_dev.csv", rows)

    for che_do in ("co_dinh", "do_lai"):
        for kind, ten in (("dap_an", "ô đáp án Ø5"), ("chu_so", "bubble SBD/mã đề Ø4,4")):
            print(f"\n[{che_do}] {ten}: theo d (mm) – ti_le_hang_duong nhỏ nhất | hieu_min nhỏ nhất (qua 8 hướng)")
            print(f"{'d':>5s} " + " ".join(f"{x.ten:>15s}" for x in images))
            dung_sai, con_dat = None, True
            for d in DUNG_SAI_MM:
                cells, all_ok = [], True
                for anh in images:
                    s = [r for r in rows if r["anh"] == anh.ten and r["che_do"] == che_do and r["loai_o"] == kind and r["d_mm"] == d]
                    tl, hm = min(r["ti_le_hang_duong"] for r in s), min(r["hieu_min"] for r in s)
                    cells.append(f"{tl:6.3f} | {hm:+.3f}")
                    if anh.ten != "0014_C2" and tl < 1:
                        all_ok = False
                print(f"{d:5.2f} " + " ".join(f"{c:>15s}" for c in cells))
                con_dat = con_dat and all_ok              # mọi d' ≤ d đều phải đạt
                if con_dat:
                    dung_sai = d
            print(f"  -> dung sai ({che_do}, {ten}): {dung_sai if dung_sai is not None else 'không đạt cả ở d = 0'} mm")
    print(f"\nĐã ghi {out / 'dung_sai_dev.csv'}")


# ============================================================================ lệnh finalize / report
def kiem_ke_thua(out: Path, nguon: str) -> None:
    """Điều kiện để thừa kế kết luận bằng mắt của phương pháp `nguon` (dừng nếu không đạt):
    (1) so_pixel_dev.csv (tools/kiem_load_image.py so-pixel): ảnh đọc vào giống từng điểm ảnh, đủ mọi ảnh dev;
    (2) mọi số đo trong diem_dev.csv và o_luoi_dev.csv trùng khớp với `nguon` (trừ cột phuong_phap, giay)."""
    p = out / "so_pixel_dev.csv"
    if not p.exists():
        sys.exit(f"--ke-thua: thiếu {p} – chạy trước: python tools/kiem_load_image.py so-pixel")
    px = {r["anh"]: r for r in csv.DictReader(p.open(encoding="utf-8-sig"))}
    dev = {x.ten for x in list_images("dev")}
    khac = sorted(t for t in dev if t not in px or px[t]["so_diem_khac"] != "0")
    if khac:
        sys.exit(f"--ke-thua: {len(khac)} ảnh không giống từng điểm ảnh (hoặc chưa so): {', '.join(khac)}")
    loi = []
    for ten_file, bo in (("diem_dev.csv", {"phuong_phap", "giay"}), ("o_luoi_dev.csv", set())):
        moi = list(csv.DictReader((out / ten_file).open(encoding="utf-8-sig")))
        cu = list(csv.DictReader((EVAL_DIR / nguon / ten_file).open(encoding="utf-8-sig")))
        if len(moi) != len(cu):
            loi.append(f"{ten_file}: {len(moi)} dòng, {nguon} có {len(cu)}")
            continue
        for rm, rc in zip(moi, cu):
            lech = [k for k in rc if k not in bo and rm.get(k) != rc[k]]
            if lech:
                loi.append(f"{ten_file} {rc.get('anh')}: khác ở {', '.join(lech[:5])}")
    if loi:
        sys.exit(f"--ke-thua: số đo KHÔNG trùng khớp với {nguon} ({len(loi)} chỗ) – phải xem bằng mắt:\n  "
                 + "\n  ".join(loi[:20]))
    print(f"--ke-thua {nguon}: {len(dev)} ảnh giống từng điểm ảnh, mọi số đo trùng khớp -> dùng kết luận bằng mắt của {nguon}.")


def cmd_finalize(a) -> None:
    """diem_dev.csv (kết luận tự động) + xem_bang_mat.csv (kết luận bằng mắt) -> truth_dev.csv.
    Mắt ưu tiên hơn máy. Chỉ ảnh máy kết luận 'dung' được lấy tự động; ảnh 'sai' hoặc 'xem' chưa có kết luận
    bằng mắt -> dừng, không ghi file (lỗi im lặng không được dựa hoàn toàn vào máy).
    --ke-thua <pp>: lấy kết luận bằng mắt của <pp> (nguon = mat_<pp>), chỉ khi kiem_ke_thua() đạt.
    --split test (Bước 7, xem MÙ): CẤM --ke-thua; MỌI ảnh có ảnh nắn phải có kết luận bằng mắt mới (không lấy tự động)."""
    split = getattr(a, "split", "dev")
    if split != "dev" and a.ke_thua:
        sys.exit(f"finalize --split {split}: không được --ke-thua – kết luận bằng mắt trên tập {split} phải là kết luận mới.")
    out = EVAL_DIR / a.phuong_phap
    nguon_mat = "mat"
    xem = out / ten_xem(split)["csv"]
    if a.ke_thua:
        kiem_ke_thua(out, a.ke_thua)
        nguon_mat, xem = f"mat_{a.ke_thua}", EVAL_DIR / a.ke_thua / "xem_bang_mat.csv"
    mat = {r["anh"]: r for r in csv.DictReader(xem.open(encoding="utf-8-sig"))}
    rows, thieu, lech = [], [], []
    for r in csv.DictReader((out / f"diem_{split}.csv").open(encoding="utf-8-sig")):
        m = mat[r["anh"]]
        ghi_chu = [m["ghi_chu"]] if m["ghi_chu"] else []
        if r["giay_cong"] == "1":
            ghi_chu.append(f"giay_cong (lech_max {float(r['lech_max_mm']):.2f} mm)")
        if r["tra_anh"] != "co":
            ket_luan, nguon = "", "tu_dong"
            ghi_chu.append(f"từ chối: {r['ly_do']}")
        elif m["ket_luan_mat"]:
            ket_luan, nguon = m["ket_luan_mat"], nguon_mat
            if r["ket_luan_tu_dong"] in ("dung", "sai") and r["ket_luan_tu_dong"] != ket_luan:
                lech.append(f"{r['anh']}: máy {r['ket_luan_tu_dong']}, mắt {ket_luan}")
                ghi_chu.append(f"máy kết luận {r['ket_luan_tu_dong']} ({r['ly_do_tu_dong']})")
        elif r["ket_luan_tu_dong"] == "dung" and split == "dev":
            ket_luan, nguon = "dung", "tu_dong"
        else:  # máy kết luận 'sai'/'xem' (dev) hoặc mọi ảnh trả về (test, xem mù) -> bắt buộc xem bằng mắt
            thieu.append(r["anh"] + (f" ({r['ly_do_tu_dong']})" if split == "dev" else ""))
            continue
        phan_loai = "bi_tu_choi" if r["tra_anh"] != "co" else ("dung" if ket_luan == "dung" else "loi_im_lang")
        rows.append({"phuong_phap": a.phuong_phap, "anh": r["anh"], "dieu_kien": r["dieu_kien"], "tra_anh": r["tra_anh"],
                     "ket_luan": ket_luan, "nguon": nguon, "phan_loai": phan_loai, "ghi_chu": "; ".join(ghi_chu)})
    if lech:
        print("CHÚ Ý – máy và mắt kết luận khác nhau (giữ kết luận của mắt):\n  " + "\n  ".join(lech))
    if thieu:
        loai = "'sai'/'xem'" if split == "dev" else "trả ảnh nắn (xem mù: phải xem MỌI ảnh)"
        sys.exit(f"Còn {len(thieu)} ảnh {loai} chưa có kết luận bằng mắt – chưa ghi truth_{split}.csv:\n  "
                 + "\n  ".join(thieu))
    ghi_csv(out / f"truth_{split}.csv", rows)
    from collections import Counter
    print(f"Đã ghi {out / f'truth_{split}.csv'}: {len(rows)} ảnh; nguồn {dict(Counter(r['nguon'] for r in rows))}; "
          f"kết luận {dict(Counter(r['ket_luan'] or '(từ chối)' for r in rows))}")


def cmd_report(a) -> None:
    """Bảng đúng / lỗi im lặng / bị từ chối theo điều kiện chụp – đọc DUY NHẤT truth_<split>.csv."""
    split = getattr(a, "split", "dev")
    path = EVAL_DIR / a.phuong_phap / f"truth_{split}.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    print(f"Phương pháp {a.phuong_phap} – tập {split} ({path})")
    print(f"{'Điều kiện':10s} {'Số ảnh':>6s} {'Đúng':>10s} {'Lỗi im lặng':>13s} {'Bị từ chối':>12s} {'Giấy cong':>10s}")
    for c in ["C1", "C2", "C3", "C4", "D", "Tổng"]:
        s = rows if c == "Tổng" else [r for r in rows if r["dieu_kien"] == c]
        n = len(s)
        if n == 0:
            continue
        k = {p: sum(r["phan_loai"] == p for r in s) for p in ("dung", "loi_im_lang", "bi_tu_choi")}
        gc = sum("giay_cong" in r["ghi_chu"] for r in s)
        print(f"{c:10s} {n:6d} " + " ".join(f"{k[p]:4d} ({k[p] / n:4.0%})".rjust(w)
                                           for p, w in (("dung", 10), ("loi_im_lang", 13), ("bi_tu_choi", 12)))
              + f" {gc:10d}")
    print("(D = 10 trang chữ số D001–D010)")
    tap = {p: {r["anh"] for r in rows if r["phan_loai"] == p} for p in ("loi_im_lang", "bi_tu_choi")}
    for p, ten in (("loi_im_lang", "Lỗi im lặng"), ("bi_tu_choi", "Bị từ chối")):
        print(f"{ten} ({len(tap[p])}): {', '.join(sorted(tap[p])) or '-'}")
    print(f"  (ảnh {split} thật đều hợp lệ ⇒ mọi ảnh 'bị từ chối' ở bảng này là TỪ CHỐI NHẦM; "
          "từ chối đúng đo trên ảnh giả: lệnh run-gia)")
    diem = EVAL_DIR / a.phuong_phap / f"diem_{split}.csv"
    if diem.exists():
        g = np.array([float(r["giay"]) for r in csv.DictReader(diem.open(encoding="utf-8-sig"))])
        print(f"Thời gian phương pháp mỗi ảnh (gồm đọc file): trung vị {np.median(g) * 1000:.0f} ms, "
              f"lớn nhất {g.max() * 1000:.0f} ms")
    if a.so_voi:
        cu = list(csv.DictReader((EVAL_DIR / a.so_voi / f"truth_{split}.csv").open(encoding="utf-8-sig")))
        cu_pl = {r["anh"]: r["phan_loai"] for r in cu}
        moi_pl = {r["anh"]: r["phan_loai"] for r in rows}
        doi = sorted(t for t in cu_pl.keys() | moi_pl.keys() if cu_pl.get(t) != moi_pl.get(t))
        print(f"\nSo với {a.so_voi}: {len(doi)} ảnh đổi phân loại"
              + "".join(f"\n  {t}: {cu_pl.get(t, '(không có)')} -> {moi_pl.get(t, '(không có)')}" for t in doi))


# ============================================================================ lệnh report-cuoi (Bước 7)
PP_CUOI = ("align_cu", "v6_api")            # trước / sau – đăng ký trước ở Bước 7, không thêm phương pháp khác
PHAN_LOAI = ("dung", "loi_im_lang", "bi_tu_choi")


def cp_tren(k: int, n: int, alpha: float = 0.05) -> float:
    """Cận trên khoảng tin cậy Clopper–Pearson hai phía (1 − alpha) của tỉ lệ khi quan sát k / n:
    p sao cho P(X ≤ k | n, p) = alpha / 2. k = 0 -> 1 − (alpha / 2)^(1 / n) (n = 12: 0,264)."""
    from math import comb
    if n == 0 or k >= n:
        return 1.0
    cdf = lambda p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))  # noqa: E731
    lo, hi = k / n, 1.0
    for _ in range(80):                     # cdf giảm theo p -> chia đôi
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > alpha / 2 else (lo, mid)
    return (lo + hi) / 2


def phoi_canh_4(t: np.ndarray) -> float:
    """Độ phối cảnh 4 tâm TL, TR, BR, BL – đúng công thức K2 (preprocessing.do_bo_4, kiem_verify.phoi_canh)."""
    d = lambda i, j: float(np.hypot(*(t[i] - t[j])))     # noqa: E731
    return min(min(r, 1 / r) for r in (d(0, 1) / d(3, 2), d(0, 3) / d(1, 2)))


def doc_tap(pp: str, split: str) -> tuple[list, dict] | None:
    t, d = EVAL_DIR / pp / f"truth_{split}.csv", EVAL_DIR / pp / f"diem_{split}.csv"
    if not (t.exists() and d.exists()):
        return None
    return (list(csv.DictReader(t.open(encoding="utf-8-sig"))),
            {r["anh"]: r for r in csv.DictReader(d.open(encoding="utf-8-sig"))})


def cmd_report_cuoi(a) -> None:
    """Báo cáo cuối Tuần 4 (đăng ký trước, docs/ke_hoach_tuan4.md Bước 7) – CHỈ đọc truth_* / diem_* đã có:
    (1) đúng / lỗi im lặng / bị từ chối theo C1–C4, D cho dev, test, gộp (n từng điều kiện; cận trên 95% của tỉ lệ lỗi
    im lặng: Clopper–Pearson và quy tắc số 3 khi 0 lỗi); (2) độ chính xác ảnh nắn đúng (lech_trungvi_mm, lech_max_mm,
    không tính ảnh cờ giấy cong); (3) thời gian; (4) độ phối cảnh (K2) từ 4 tâm marker của v6_api – nhỏ nhất của test."""
    md = ["# Tuần 4 – báo cáo cuối preprocessing (`report-cuoi`)\n"]
    du_lieu = {pp: {s: doc_tap(pp, s) for s in ("dev", "test")} for pp in PP_CUOI}
    for pp in PP_CUOI:
        for s in ("dev", "test"):
            if du_lieu[pp][s] is None:
                md.append(f"- `{pp}` / {s}: **CHƯA CHẠY** (thiếu truth_{s}.csv / diem_{s}.csv)")
    md.append("")
    for tap in ("dev", "test", "gop"):
        md.append(f"## {'Dev (0001–0034 + D001–D010)' if tap == 'dev' else 'Test (0035–0040)' if tap == 'test' else 'Gộp dev + test (80 ảnh phiếu + 10 trang chữ số)'}\n")
        if tap == "gop":
            md.append("**Lưu ý: dev là tập đã dùng để chỉnh tham số / ngưỡng** – số gộp lạc quan hơn số test; số khách quan "
                      "là bảng Test.\n")
        dong = []
        for pp in PP_CUOI:
            parts = [du_lieu[pp][s] for s in (("dev", "test") if tap == "gop" else (tap,))]
            if any(p is None for p in parts):
                dong.append([pp, "chưa đủ dữ liệu", "", "", "", "", ""])
                continue
            rows = [r for p in parts for r in p[0]]
            for c in ("C1", "C2", "C3", "C4", "D", "Tổng"):
                s = rows if c == "Tổng" else [r for r in rows if r["dieu_kien"] == c]
                n = len(s)
                if n == 0:
                    continue
                k = {p: sum(r["phan_loai"] == p for r in s) for p in PHAN_LOAI}
                cp = cp_tren(k["loi_im_lang"], n)
                ba = f"; quy tắc số 3: {3 / n:.0%}" if k["loi_im_lang"] == 0 else ""
                dong.append([pp, c, n, k["dung"], f"{k['loi_im_lang']} (cận trên 95% {cp:.0%}{ba})", k["bi_tu_choi"],
                             ", ".join(sorted(r["anh"] for r in s if r["phan_loai"] != "dung")) or "–"])
        md.append(bang_md_cuoi(["phương pháp", "ĐK", "n", "đúng", "lỗi im lặng", "bị từ chối (= nhầm)", "ảnh không đúng"], dong))
        md.append("")
    md.append("## Độ chính xác ảnh nắn ĐÚNG (phép 2, ô lưới tin cậy; bỏ ảnh cờ giấy cong) – sàn chung ~0,3 mm (máy in)\n")
    dong = []
    for pp in PP_CUOI:
        for s in ("dev", "test"):
            if du_lieu[pp][s] is None:
                continue
            truth, diem = du_lieu[pp][s]
            ok = [diem[r["anh"]] for r in truth if r["phan_loai"] == "dung" and diem[r["anh"]].get("giay_cong") != "1"]
            if not ok:
                dong.append([pp, s, 0, "", "", ""])
                continue
            tv = np.array([float(r["lech_trungvi_mm"]) for r in ok])
            mx = np.array([float(r["lech_max_mm"]) for r in ok])
            i = int(np.argmax(mx))
            dong.append([pp, s, len(ok), f"{tv.mean():.2f} / {np.median(tv):.2f}", f"{np.median(mx):.2f}",
                         f"{mx[i]:.2f} ({ok[i]['anh']})"])
    # So công bằng trước/sau: CÙNG tập ảnh mà cả hai phương pháp nắn đúng (align_cu sai gần hết C3 – ảnh C3 lệch thật
    # nhiều hơn, nên so tập "ảnh đúng" riêng của từng phương pháp sẽ thiên vị align_cu)
    for s in ("dev", "test"):
        if any(du_lieu[pp][s] is None for pp in PP_CUOI):
            continue
        chung = set.intersection(*({r["anh"] for r in du_lieu[pp][s][0] if r["phan_loai"] == "dung"
                                    and du_lieu[pp][s][1][r["anh"]].get("giay_cong") != "1"} for pp in PP_CUOI))
        for pp in PP_CUOI:
            ok = [du_lieu[pp][s][1][t] for t in sorted(chung)]
            if not ok:
                continue
            tv = np.array([float(r["lech_trungvi_mm"]) for r in ok])
            mx = np.array([float(r["lech_max_mm"]) for r in ok])
            i = int(np.argmax(mx))
            dong.append([f"{pp} (ảnh đúng ở CẢ HAI)", s, len(ok), f"{tv.mean():.2f} / {np.median(tv):.2f}",
                         f"{np.median(mx):.2f}", f"{mx[i]:.2f} ({ok[i]['anh']})"])
    md.append(bang_md_cuoi(["phương pháp", "tập", "n ảnh đúng", "lech_trungvi TB / TV (mm)", "lech_max TV (mm)",
                            "lech_max lớn nhất (mm)"], dong))
    md.append("\n## Thời gian mỗi ảnh (gồm đọc file)\n")
    dong = []
    for pp in PP_CUOI:
        for s in ("dev", "test"):
            if du_lieu[pp][s] is not None:
                g = np.array([float(r["giay"]) for r in du_lieu[pp][s][1].values()]) * 1000
                dong.append([pp, s, len(g), f"{np.median(g):.0f}", f"{g.max():.0f}"])
    md.append(bang_md_cuoi(["phương pháp", "tập", "n", "trung vị (ms)", "lớn nhất (ms)"], dong))
    md.append(f"\n## Độ phối cảnh K2 (4 tâm marker của v6_api; ngưỡng từ chối K2 < {0.50}) – cho Hướng dẫn chụp\n")
    dong = []
    for s in ("dev", "test"):
        if du_lieu["v6_api"][s] is None:
            continue
        pc = []
        for r in du_lieu["v6_api"][s][1].values():
            if r.get("marker_tl_x"):
                t = np.array([[float(r[f"marker_{g}_{c}"]) for c in "xy"] for g in ("tl", "tr", "br", "bl")])
                pc.append((phoi_canh_4(t), r["anh"], r["dieu_kien"]))
        thieu = [r["anh"] for r in du_lieu["v6_api"][s][1].values() if not r.get("marker_tl_x")]
        for c in ("C1", "C2", "C3", "C4", "D", "Tổng"):
            x = [p for p in pc if c == "Tổng" or p[2] == c]
            if x:
                m = min(x)
                dong.append([s, c, len(x), f"{m[0]:.3f} ({m[1]})", f"{np.median([p[0] for p in x]):.3f}",
                             ", ".join(thieu) if c == "Tổng" and thieu else ""])
    md.append(bang_md_cuoi(["tập", "ĐK", "n", "nhỏ nhất (ảnh)", "trung vị", "không có 4 tâm (bị từ chối trước khi chọn bộ)"],
                           dong))
    out = EVAL_DIR / "bao_cao_cuoi_tuan4.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\n-> {out}")


def bang_md_cuoi(tieu_de: list, dong: list) -> str:
    return "\n".join(["| " + " | ".join(tieu_de) + " |", "|" + "---|" * len(tieu_de)]
                     + ["| " + " | ".join(str(v) for v in d) + " |" for d in dong])


# ============================================================================ lệnh tam-marker (kiểm tra B)
MARKER_WIN_MM = 8.0          # cửa sổ ±8 mm quanh tâm marker chuẩn (marker cạnh 8 mm)


def tam_marker(aligned, layout) -> dict:
    """Tâm thật (dưới pixel) của 4 ô đen marker trên ảnh nắn, so với layout.json -> {góc: (dx, dy, cạnh) mm}.
    Otsu trong cửa sổ, lấy thành phần đen chứa/gần tâm cửa sổ nhất, tâm = trọng tâm điểm ảnh."""
    s = layout["dpi"] / 25.4
    r = int(MARKER_WIN_MM * s)
    out = {}
    for c, (cx, cy) in layout["markers"]["centers"].items():
        x0, y0 = int(round(cx)) - r, int(round(cy)) - r
        win = aligned[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
        th = cv2.threshold(cv2.GaussianBlur(win, (5, 5), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        n, lab, st, cen = cv2.connectedComponentsWithStats(th)
        if n < 2:
            out[c] = (np.nan, np.nan, np.nan)
            continue
        k = 1 + int(np.argmin(np.hypot(cen[1:, 0] - r, cen[1:, 1] - r) - st[1:, cv2.CC_STAT_AREA] / 1e4))
        out[c] = ((x0 + cen[k, 0] - cx) / s, (y0 + cen[k, 1] - cy) / s,
                  float(np.sqrt(st[k, cv2.CC_STAT_AREA]) / s))
    return out


def cmd_tam_marker(a) -> None:
    """Kiểm tra B: ảnh nắn đúng (không 'sai' bằng mắt) – tâm marker có nằm đúng layout không, so với độ lệch
    nội dung (ô lưới tin cậy, o_luoi_dev.csv). Kèm dòng đối chứng: trang mẫu render (phải ~0)."""
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    out = EVAL_DIR / a.phuong_phap
    mat = {r["anh"]: r["ket_luan_mat"] for r in csv.DictReader((out / "xem_bang_mat.csv").open(encoding="utf-8-sig"))}
    noi_dung = {}
    for r in csv.DictReader((out / "o_luoi_dev.csv").open(encoding="utf-8-sig")):
        if r["tin_cay"] == "1":
            noi_dung.setdefault(r["anh"], []).append((float(r["dx_mm"]), float(r["dy_mm"])))
    rows = []
    for loai, g in nap_mau(layout).items():
        m = tam_marker(g, layout)
        print(f"Đối chứng – mẫu render {loai}: " + ", ".join(f"{c} ({v[0]:+.3f}, {v[1]:+.3f}) cạnh {v[2]:.2f}"
                                                            for c, v in m.items()))
    f = PHUONG_PHAP[a.phuong_phap]
    for anh in list_images("dev"):
        if mat.get(anh.ten) == "sai" or anh.ten == "0014_C2":
            continue
        aligned, _, _ = goi_phuong_phap(f, anh, layout["page_px"])
        m = tam_marker(aligned, layout)
        nd = np.array(noi_dung[anh.ten])
        r = {"anh": anh.ten, "dieu_kien": anh.dieu_kien,
             "noi_dung_dx_mm": float(nd[:, 0].mean()), "noi_dung_dy_mm": float(nd[:, 1].mean())}
        for c, (dx, dy, canh) in m.items():
            r.update({f"{c}_dx_mm": dx, f"{c}_dy_mm": dy, f"{c}_canh_mm": canh})
        r["marker_dx_tb_mm"] = float(np.mean([m[c][0] for c in m]))
        r["marker_dy_tb_mm"] = float(np.mean([m[c][1] for c in m]))
        rows.append(r)
        print(f"{anh.ten:8s} marker dy tb {r['marker_dy_tb_mm']:+.3f} | nội dung dy tb {r['noi_dung_dy_mm']:+.3f}")
    path = out / "tam_marker_dev.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})

    def tb(key, sel=lambda r: True):
        v = [r[key] for r in rows if sel(r)]
        return f"{np.mean(v):+.3f}"
    print(f"\n{len(rows)} ảnh (bỏ 0014_C2 giấy cong). Trung bình (mm):")
    print(f"{'nhóm':6s} " + " ".join(f"{c + ' dx':>8s} {c + ' dy':>8s}" for c in ("tl", "tr", "br", "bl"))
          + f" {'mk dy':>7s} {'nd dy':>7s}")
    for cond in ("tất cả", "C1", "C2", "C3", "C4", "D"):
        sel = (lambda r: True) if cond == "tất cả" else (lambda r, c=cond: r["dieu_kien"] == c)
        if not any(sel(r) for r in rows):
            continue
        print(f"{cond:6s} " + " ".join(f"{tb(c + '_dx_mm', sel):>8s} {tb(c + '_dy_mm', sel):>8s}" for c in ("tl", "tr", "br", "bl"))
              + f" {tb('marker_dy_tb_mm', sel):>7s} {tb('noi_dung_dy_mm', sel):>7s}")
    canh = [r[f"{c}_canh_mm"] for r in rows for c in ("tl", "tr", "br", "bl")]
    print(f"Cạnh marker đo được (căn diện tích): {np.min(canh):.2f}–{np.max(canh):.2f} mm (thiết kế 8,00)")
    mk, nd = np.array([r["marker_dy_tb_mm"] for r in rows]), np.array([r["noi_dung_dy_mm"] for r in rows])
    print(f"Tương quan dy marker ↔ dy nội dung giữa các ảnh: r = {np.corrcoef(mk, nd)[0, 1]:+.2f}")
    print(f"Đã ghi {path}")


# ============================================================================ lệnh run-gia (Bước 4)
GIA_DIR = EVAL_DIR / "_gia_v4"
NHOM_MA = {"khong_du_marker": {"thieu_marker", "marker_khong_dat"}}
KHOP_MARKER_PX = 3.0         # ca 'ok': 4 tâm trả về cách H · (tâm v3 của ảnh nguồn) ≤ 3 px
PHAN_LOAI_GIA = ["dung", "tu_choi_dung", "LOI_IM_LANG", "lot_qua_nan_dung", "sai_ma", "sai_ma_da_biet", "tu_choi_nham"]
# Giới hạn ĐÃ BIẾT (người dùng duyệt dừng C, 06/10/2026): mo_huong chỉ xét trục x/y – mờ chéo 45° và mờ có nhiễu lọt qua
# anh_mo, hiện bị chặn bởi khong_khop_bo_cuc (sai mã, vẫn an toàn). Sửa ở Tuần 6 (blur 4 hướng + trừ nhiễu). Chỉ áp khi
# ca đó VẪN BỊ TỪ CHỐI với đúng mã này; nếu trả ảnh thì vẫn tính lỗi như thường.
SAI_MA_DA_BIET = {t: "khong_khop_bo_cuc" for t in ("mo_cheo30_0001_C1", "mo_cheo15_0015_C3",
                                                    "mo_toi_nhieu_0001_C1", "mo_toi_nhieu_0008_C4")}


def cmd_run_gia(a) -> None:
    """Chấm preprocess() trên ảnh giả data/_eval/_gia_v4/ (kiem_verify.py tao-gia) theo kết quả mong đợi chốt trước:
      dung            – mong ok/ok_hoac, trả ảnh, 4 tâm khớp ≤ 3 px và huong_xoay đúng
      tu_choi_dung    – mong tu_choi/ok_hoac, từ chối với mã thuộc tập mong đợi
      LOI_IM_LANG     – trả ảnh mà 4 tâm / chiều KHÔNG khớp (lỗi nguy hiểm nhất)
      lot_qua_nan_dung– mong từ chối nhưng trả ảnh (nắn khớp) – không nguy hiểm bằng, vẫn là KHÔNG ĐẠT
      sai_ma          – từ chối nhưng mã ngoài tập mong đợi
      sai_ma_da_biet  – như sai_ma nhưng là giới hạn đã biết (SAI_MA_DA_BIET) – vẫn an toàn, không phải từ chối nhầm
      tu_choi_nham    – mong ok mà bị từ chối
    Ảnh giả chỉ kiểm LOGIC (lấy từ ảnh dev); khả năng tổng quát hoá đo ở Bước 7."""
    out = EVAL_DIR / a.phuong_phap
    (out / "anh_gia").mkdir(parents=True, exist_ok=True)
    mv3 = marker_v3()
    rows = []
    for d in csv.DictReader((GIA_DIR / "danh_sach.csv").open(encoding="utf-8-sig")):
        t0 = time.perf_counter()
        kq = preprocess(GIA_DIR / f"{d['ten']}.jpg", nap_layout_loai(d["layout"]))
        giay = time.perf_counter() - t0
        if a.phuong_phap != "v4_verify":
            kiem_chuan_hoa(kq, d["ten"])
        chap_nhan = set()
        for m in filter(None, d["ly_do_mong_doi"].split("|")):
            chap_nhan |= NHOM_MA.get(m, {m})
        tam_md = None
        if d["H"]:
            tam_md = cv2.perspectiveTransform(mv3[d["nguon"].split("+")[0]][None], np.array(json.loads(d["H"])))[0]
        lech = huong_md = None
        if kq.ok and tam_md is not None:
            lech = float(np.max(np.hypot(*(kq.marker - tam_md).T)))
            huong_md = huong_tu_marker(tam_md)
        khop = lech is not None and lech <= KHOP_MARKER_PX and kq.huong_xoay == huong_md
        if kq.ok:
            pl = ("dung" if d["mong_doi"] in ("ok", "ok_hoac") else "lot_qua_nan_dung") if khop else "LOI_IM_LANG"
        elif d["mong_doi"] == "ok":
            pl = "tu_choi_nham"
        else:
            pl = "tu_choi_dung" if kq.ly_do in chap_nhan else (
                "sai_ma_da_biet" if SAI_MA_DA_BIET.get(d["ten"]) == kq.ly_do else "sai_ma")
        r = {"ten": d["ten"], "nhom": d["nhom"], "nguon": d["nguon"], "bien_the": d["bien_the"], "mong_doi": d["mong_doi"],
             "ly_do_mong_doi": d["ly_do_mong_doi"], "huong_mong_doi": huong_md if huong_md is not None else d["huong_mong_doi"],
             "ok": int(kq.ok), "ly_do": kq.ly_do, "huong_xoay": kq.huong_xoay if kq.huong_xoay is not None else "",
             "lech_marker_px": lech if lech is not None else "", "phan_loai": pl, "giay": giay,
             **{k: kq.chi_tiet[k] for k in V4_COT if k in kq.chi_tiet}}
        rows.append(r)
        print(f"{d['ten']:30s} {pl:16s} {('ok ' + str(kq.huong_xoay) + '°') if kq.ok else kq.ly_do:20s} "
              f"(mong {d['mong_doi']} {d['ly_do_mong_doi'] or d['huong_mong_doi']})")
        # ảnh xem: ảnh giả thu nhỏ + tứ giác trả về (xanh lá) + tứ giác mong đợi (tím); ảnh nắn nếu có
        g = cv2.imdecode(np.fromfile(GIA_DIR / f"{d['ten']}.jpg", np.uint8), cv2.IMREAD_GRAYSCALE)
        img = ve_tu_giac(g, {"ung_vien": kq.chi_tiet.get("ung_vien", []), "marker": kq.marker})
        if tam_md is not None:
            cv2.polylines(img, [np.int32(tam_md)], True, (200, 0, 200), max(2, int(2 * max(g.shape) / 1400)), cv2.LINE_AA)
        ghi_jpg(out / "anh_gia" / f"{d['ten']}_goc.jpg", img, max_w=700, q=80)
        if kq.anh_nan is not None:
            ghi_jpg(out / "anh_gia" / f"{d['ten']}_nan.jpg", kq.anh_nan, max_w=500, q=80)
    ghi_csv(out / "gia.csv", rows)

    from collections import Counter
    print(f"\nẢnh giả ({len(rows)}) – phân loại theo nhóm:")
    print(f"{'nhóm':12s} " + " ".join(f"{p:>16s}" for p in PHAN_LOAI_GIA))
    for nh in list(dict.fromkeys(r["nhom"] for r in rows)) + ["Tổng"]:
        s = rows if nh == "Tổng" else [r for r in rows if r["nhom"] == nh]
        c = Counter(r["phan_loai"] for r in s)
        print(f"{nh:12s} " + " ".join(f"{c[p]:16d}" for p in PHAN_LOAI_GIA))
    hong = [r for r in rows if r["phan_loai"] not in ("dung", "tu_choi_dung")]
    print("KHÔNG ĐẠT:" + ("".join(f"\n  {r['ten']}: {r['phan_loai']} – trả {('ok ' + str(r['huong_xoay'])) if r['ok'] else r['ly_do']}"
                                  f", mong {r['mong_doi']} {r['ly_do_mong_doi'] or r['huong_mong_doi']}" for r in hong) or " không"))
    g = np.array([r["giay"] for r in rows])
    print(f"Thời gian mỗi ảnh giả: trung vị {np.median(g) * 1000:.0f} ms, lớn nhất {g.max() * 1000:.0f} ms")

    # HTML: ca không đạt trước, rồi mọi ca theo nhóm
    def dong(r):
        nan = (f'<a href="anh_gia/{r["ten"]}_nan.jpg" target="_blank"><img src="anh_gia/{r["ten"]}_nan.jpg" width="240"></a>'
               if (out / "anh_gia" / f"{r['ten']}_nan.jpg").exists() else "")
        so = ", ".join(f"{k} {fmt(r[k], 4 if k == 'blur_score' else 3)}" for k in V4_COT if k in r)
        mau = "#c00" if r["phan_loai"] not in ("dung", "tu_choi_dung") else "#080"
        return (f'<tr><td><b>{r["ten"]}</b><br>{html.escape(r["bien_the"])}<br>mong: {r["mong_doi"]} '
                f'{html.escape(r["ly_do_mong_doi"] or str(r["huong_mong_doi"]) + "°")}<br>trả: '
                f'{("ok " + str(r["huong_xoay"]) + "°") if r["ok"] else html.escape(r["ly_do"])}'
                f'<br><b style="color:{mau}">{r["phan_loai"]}</b><br><small>{so}<br>lệch marker {fmt(r["lech_marker_px"], 2)} px'
                f'</small></td><td><a href="anh_gia/{r["ten"]}_goc.jpg" target="_blank"><img src="anh_gia/{r["ten"]}_goc.jpg" '
                f'width="320"></a></td><td>{nan}</td></tr>')
    sap = sorted(rows, key=lambda r: (r["phan_loai"] in ("dung", "tu_choi_dung"), r["nhom"]))
    (out / "gia.html").write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Ảnh giả {a.phuong_phap}</title>
<style>body{{font-family:sans-serif;margin:16px}} td{{vertical-align:top;border-bottom:1px solid #ddd;padding:6px;font-size:13px}}
img{{border:1px solid #ccc}}</style></head><body><h2>Ảnh giả lỗi cố ý – <code>{a.phuong_phap}</code> ({len(rows)} ảnh,
không đạt: {len(hong)})</h2><p>Ảnh giữa: ảnh giả + <span style="color:#0a0">tứ giác 4 marker trả về</span> (chấm đỏ = TL),
<span style="color:#c0c">tứ giác mong đợi</span> (H · tâm v3 của ảnh nguồn), vòng xanh dương = ứng viên. Ảnh phải: ảnh nắn
(cả khi bị từ chối ở verify). Sắp xếp: không đạt trước.</p><table>{"".join(dong(r) for r in sap)}</table></body></html>""",
                                  encoding="utf-8")
    print(f"Đã ghi {out / 'gia.csv'}, {out / 'gia.html'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Đánh giá phương pháp nắn phẳng ảnh (Tuần 4)")
    sub = ap.add_subparsers(dest="lenh", required=True)
    r = sub.add_parser("run", help="chạy phương pháp + 3 phép kiểm tra, xuất CSV/HTML")
    r.add_argument("--phuong-phap", default="align_cu", choices=sorted(PHUONG_PHAP))
    r.add_argument("--split", default="dev", choices=sorted(SPLITS))
    r.add_argument("--xac-nhan-test", action="store_true", help="bắt buộc khi --split test (chỉ dùng ở Bước 7)")
    t = sub.add_parser("tu-kiem", help="kiểm chứng phép đo: trang mẫu render + ảnh 'dung' bằng mắt bị làm hỏng cố ý")
    t.add_argument("--phuong-phap", default="align_cu", choices=sorted(PHUONG_PHAP))
    t = sub.add_parser("dung-sai", help="dung sai lệch của OMR (toạ độ cố định / dò lại từng hàng)")
    t.add_argument("--phuong-phap", default="align_cu", choices=sorted(PHUONG_PHAP))
    t = sub.add_parser("tam-marker", help="kiểm tra B: tâm marker trên ảnh nắn đúng so với layout (cần run + xem_bang_mat.csv)")
    t.add_argument("--phuong-phap", default="align_cu", choices=sorted(PHUONG_PHAP))
    for ten, h in (("finalize", "ghép kết luận máy + mắt -> truth_<split>.csv"),
                   ("report", "bảng C1–C4 + D từ truth_<split>.csv")):
        t = sub.add_parser(ten, help=h)
        t.add_argument("--phuong-phap", default="align_cu", choices=sorted(PHUONG_PHAP))
        t.add_argument("--split", default="dev", choices=sorted(SPLITS))
        if ten == "finalize":
            t.add_argument("--ke-thua", choices=sorted(PHUONG_PHAP), default=None,
                           help="dùng kết luận bằng mắt của phương pháp này (chỉ khi ảnh đọc vào giống từng điểm ảnh "
                                "VÀ mọi số đo trùng khớp)")
        else:
            t.add_argument("--so-voi", choices=sorted(PHUONG_PHAP), default=None,
                           help="liệt kê ảnh đổi phân loại so với phương pháp này")
    t = sub.add_parser("run-gia", help="chấm preprocess() trên ảnh giả lỗi cố ý (data/_eval/_gia_v4) theo kết quả mong đợi")
    t.add_argument("--phuong-phap", default="v6_api", choices=["v4_verify", "v5_chuan_hoa", "v6_api"])
    sub.add_parser("report-cuoi", help="báo cáo cuối Tuần 4: align_cu vs v6_api, dev / test / gộp (Bước 7)")
    a = ap.parse_args()
    {"run": cmd_run, "tu-kiem": cmd_tu_kiem, "dung-sai": cmd_dung_sai, "tam-marker": cmd_tam_marker,
     "finalize": cmd_finalize, "report": cmd_report, "run-gia": cmd_run_gia, "report-cuoi": cmd_report_cuoi}[a.lenh](a)


if __name__ == "__main__":
    main()
