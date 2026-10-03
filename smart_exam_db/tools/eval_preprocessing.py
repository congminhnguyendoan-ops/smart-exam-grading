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
                 lech_trungvi/lech_max chỉ tính trên ô tin cậy (duy_nhat >= DUY_NHAT_MIN); ảnh có
                 < SO_O_TIN_CAY_MIN ô tin cậy luôn là 'xem'.
               - khop_net: % điểm nét của mẫu có nét ảnh trong vòng 1 mm (chỉ chiều mẫu→ảnh: chì/chữ
                 viết tay thêm nét không làm giảm điểm)
  3. Nhãn    : (chỉ phiếu) ô filled theo cell_labels.csv phải tối hơn ô blank cùng hàng/cột,
               đo tại toạ độ layout (không dò lại vị trí) bằng local_darkness() của check_labels.py.

Bước 1 (lệnh run): CHƯA có ngưỡng – mọi ảnh là 'xem'; xuất HTML để người dùng xem bằng mắt.
Chỉ ghi vào data/_eval/, không đụng data/raw/, data/raw_digits/.

Chạy (từ thư mục smart_exam_db/):
  python tools/eval_preprocessing.py run --phuong-phap align_cu --split dev
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
from check_layout import align, render_pdf_page  # noqa: E402  (không sửa check_layout.py)
from prepare_photos import marker_fill  # noqa: E402
from check_labels import local_darkness  # noqa: E402

SPLITS = {"dev": range(1, 35), "test": range(35, 41)}     # mã phiếu; trang chữ số D001–D010 thuộc dev
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
# Ô lưới "tin cậy" = đỉnh khớp duy nhất. Chọn từ lần chạy align_cu/dev 03/10/2026: 4 ô khớp nhầm 1 bước bubble
# SBD (5,2–5,8 mm) có duy_nhat 0,0006–0,016; ô vùng bubble SBD/mã đề thường ≤ 0,03; mọi ô khác trên 59 ảnh
# khớp ≥ 0,088. 0,05 nằm giữa khoảng trống 0,03–0,088.
DUY_NHAT_MIN = 0.05
# Ít ô tin cậy hơn thế -> không đủ căn cứ, ảnh luôn là 'xem'. Cùng lần chạy: 59 ảnh khớp có 45–48 ô,
# 19 ảnh lệch có 1–22 ô (lưới 48 ô). Đặt 40: chừa ~5 ô bị bóng/che so với ảnh khớp kém nhất.
SO_O_TIN_CAY_MIN = 40
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


PHUONG_PHAP = {"align_cu": align_cu}


def goi_phuong_phap(f, anh: Anh, page_px) -> tuple:
    """(ảnh nắn | None, lý do, giây). Phương pháp ném lỗi = từ chối. Sai kích thước = lỗi giao diện -> dừng."""
    t0 = time.perf_counter()
    try:
        out, ly_do = f(anh.duong_dan)
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


def khop(anh_s, mau_s, box_px, goc, search_px) -> tuple:
    """So vùng box của mẫu với ảnh quanh độ lệch goc (dx, dy) trong ±search_px.
    Trả (dx, dy, điểm, độ duy nhất) – dx, dy tuyệt đối (px)."""
    x0, y0, x1, y1 = box_px
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
    return cx0 + bx - x0, cy0 + by - y0, float(best), float(best - second)


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
        t["tin_cay"] = t["dx"] is not None and t["duy_nhat"] >= DUY_NHAT_MIN
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


def p3_nhan(aligned, layout, nhan: dict) -> dict:
    """Mỗi hàng câu / cột chữ số có ô filled: hiệu = min(filled) − max(blank) (độ tối local_darkness)."""
    groups = []                                              # [(tâm, bán kính, {ô: nhãn})]
    ans = layout["answers"]
    for q in range(1, ans["num_questions"] + 1):
        groups.append(([ans["centers"][str(q)][o] for o in ans["options"]], ans["bubble_radius"],
                       [nhan[(str(q), o)] for o in ans["options"]]))
    for field in ("sbd", "exam_code"):
        f = layout[field]
        for c, col in enumerate(f["bubbles"]):
            groups.append((col, f["bubble_radius"], [nhan[(f"{field}{c + 1}", str(k))] for k in range(10)]))
    hieu = []
    for centers, r, labs in groups:
        if "filled" not in labs or "blank" not in labs:
            continue
        d = [local_darkness(aligned, cx, cy, r) for cx, cy in centers]
        hieu.append(min(v for v, l in zip(d, labs) if l == "filled") - max(v for v, l in zip(d, labs) if l == "blank"))
    h = np.array(hieu)
    return {"so_hang": len(h), "ti_le_hang_duong": float((h > 0).mean()), "hieu_min": float(h.min()),
            "hieu_p10": float(np.percentile(h, 10)), "hieu_trungvi": float(np.median(h))}


# ============================================================================ kết luận tự động
def ket_luan_tu_dong(r: dict, nguong=None) -> tuple[str, str]:
    """('dung'|'sai'|'xem', lý do). Bước 1 chưa có nguong.json -> luôn 'xem'.
    Luật cố định: ít ô lưới tin cậy (< SO_O_TIN_CAY_MIN) -> 'xem' dù có ngưỡng."""
    if r["tra_anh"] != "co":
        return "", ""                                      # từ chối: không cần kết luận nắn đúng/sai
    if r["so_o_tin_cay"] < SO_O_TIN_CAY_MIN:
        return "xem", f"chỉ {r['so_o_tin_cay']} ô lưới tin cậy (< {SO_O_TIN_CAY_MIN})"
    if nguong is None:
        return "xem", "chưa có ngưỡng"
    raise NotImplementedError("luật theo nguong.json: làm sau khi chốt ngưỡng")


# ============================================================================ xuất ảnh / HTML
def anh_chong(anh_w, mau_e, tiles) -> np.ndarray:
    """Ảnh nắn (xám nhạt) + nét mẫu màu đỏ + mũi tên lệch từng ô lưới (phóng x5; xanh dương = ô tin cậy,
    xám = đỉnh khớp không duy nhất, không tính vào lech_*)."""
    base = cv2.cvtColor(cv2.addWeighted(anh_w, 0.6, np.full_like(anh_w, 255), 0.4, 0), cv2.COLOR_GRAY2BGR)
    base[mau_e > 0] = (0, 0, 230)
    for t in tiles:
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


def viet_html(rows, path: Path, ten_pp: str, split: str):
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
        al = (f'<a href="anh/{r["anh"]}_chong.jpg" target="_blank"><img src="anh/{r["anh"]}_chong_nho.jpg" width="420"></a>'
              if r["tra_anh"] == "co" else "")
        body.append(f'<tr id="{r["anh"]}"><td><b>{r["anh"]}</b><br>{r["dieu_kien"]}<br>{r["giay"]:.1f} s</td>'
                    f'<td class="m">{metrics}</td><td>{al}</td>'
                    f'<td><a href="anh/{r["anh"]}_goc.jpg" target="_blank"><img src="anh/{r["anh"]}_goc.jpg" width="200"></a></td></tr>')
    path.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Xem bằng mắt – {ten_pp} – {split}</title>
<style>body{{font-family:sans-serif;margin:16px}} td{{vertical-align:top;border-bottom:1px solid #ddd;padding:6px}}
td.m{{font-size:12px;width:300px}} .strip{{margin:6px 0}} img{{border:1px solid #ccc}}</style></head><body>
<h2>Xem bằng mắt: phương pháp <code>{ten_pp}</code>, tập {split} ({len(rows)} ảnh)</h2>
<p>Chưa có ngưỡng – mọi ảnh đang là <b>xem</b>. Ảnh giữa: ảnh nắn (xám) + <span style="color:#e00">nét phiếu mẫu (đỏ)</span>
+ <span style="color:#05c">mũi tên lệch từng ô lưới, phóng ×5, số = mm</span> (xám + "?" = đỉnh khớp không duy nhất,
không tính vào lech_*); bấm để xem cỡ 150 DPI.
Nắn đúng ⇒ nét đỏ nằm đè lên nét in trên ảnh. Ảnh phải: ảnh gốc (đúng như phương pháp đọc).
Sắp xếp: từ chối trước, rồi <code>khop_net</code> thấp → cao.<br>
Ghi kết luận vào <code>xem_bang_mat.csv</code>, cột <code>ket_luan_mat</code> = <code>dung</code> / <code>sai</code> (để trống nếu chưa xem).</p>
<p>{legend}</p>{strips}
<table><tr><th>Ảnh</th><th>Số đo</th><th>Ảnh nắn + nét mẫu</th><th>Ảnh gốc</th></tr>{"".join(body)}</table>
</body></html>""", encoding="utf-8")


# ============================================================================ lệnh run
def cmd_run(a) -> None:
    if a.split == "test" and not a.xac_nhan_test:
        sys.exit("Tập test (0035–0040) chỉ chạy MỘT LẦN ở Bước 7 (docs/ke_hoach_tuan4.md). "
                 "Nếu đúng là lúc đó, thêm --xac-nhan-test.")
    f = PHUONG_PHAP[a.phuong_phap]
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    page_px = layout["page_px"]
    out = EVAL_DIR / a.phuong_phap
    (out / "anh").mkdir(parents=True, exist_ok=True)

    mau = {}                                   # loại trang -> nét mẫu ở WORK_DPI (trang 1; các trang chỉ khác mã)
    for loai, pdf in (("phieu", "phieu_danh_so.pdf"), ("chu_so", "trang_chu_so.pdf")):
        g = to_work(render_pdf_page(ANSWER_SHEET / "output" / pdf, layout["dpi"]), page_px)
        mau[loai] = ban_do_net(g)
    mask = mat_na(layout, mau["phieu"].shape)
    nhan = doc_nhan_o()

    rows, tile_rows = [], []
    images = list_images(a.split)
    for n, anh in enumerate(images, 1):
        aligned, ly_do, giay = goi_phuong_phap(f, anh, page_px)
        r = {"phuong_phap": a.phuong_phap, "anh": anh.ten, "loai": anh.loai, "dieu_kien": anh.dieu_kien,
             "tra_anh": "co" if aligned is not None else "khong", "ly_do": ly_do, "giay": giay}
        ghi_jpg(out / "anh" / f"{anh.ten}_goc.jpg", doc_xam(anh.duong_dan), max_w=400, q=80)
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
            chong = anh_chong(anh_w, mau[anh.loai], tiles)
            ghi_jpg(out / "anh" / f"{anh.ten}_chong.jpg", chong)
            ghi_jpg(out / "anh" / f"{anh.ten}_chong_nho.jpg", chong, max_w=840, q=80)
        r["ket_luan_tu_dong"], r["ly_do_tu_dong"] = ket_luan_tu_dong(r)
        rows.append(r)
        tom = (f"khop_net={r['khop_net']:.2f} lech_trungvi={r['lech_trungvi_mm']:.1f}mm "
               f"lech_max={r['lech_max_mm']:.1f}mm" if aligned is not None else f"TỪ CHỐI: {ly_do}")
        print(f"[{n:2d}/{len(images)}] {anh.ten:8s} {tom}")

    cols = ["phuong_phap", "anh", "loai", "dieu_kien", "tra_anh", "ly_do", "giay", "ket_luan_tu_dong", "ly_do_tu_dong",
            "den_tl", "den_tr", "den_br", "den_bl", "den_min",
            "khop_net", "lech_toan_trang_mm", "lech_toan_trang_dx_mm", "lech_toan_trang_dy_mm",
            "diem_tieu_de", "duy_nhat_tieu_de", "lech_trungvi_mm", "lech_max_mm",
            "lech_max_ca_o_khong_duy_nhat_mm", "so_o_luoi", "so_o_tin_cay",
            "diem_o_min", "diem_o_trungvi", "duy_nhat_o_min", "do_nhat_quan_mm",
            "so_hang", "ti_le_hang_duong", "hieu_min", "hieu_p10", "hieu_trungvi"]
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

    viet_html(rows, out / "xem_bang_mat.html", a.phuong_phap, a.split)
    review = out / "xem_bang_mat.csv"
    if review.exists():
        print(f"\nGIỮ NGUYÊN {review} (đã có – có thể chứa kết luận bằng mắt).")
    else:
        with review.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["phuong_phap", "anh", "dieu_kien", "ket_luan_mat", "ghi_chu"])
            for r in rows:
                w.writerow([a.phuong_phap, r["anh"], r["dieu_kien"], "", ""])

    print(f"\nĐã ghi vào {out}:")
    print(f"  diem_{a.split}.csv, o_luoi_{a.split}.csv, xem_bang_mat.html, xem_bang_mat.csv, anh/")
    tu_choi = [r for r in rows if r["tra_anh"] == "khong"]
    print(f"Trả ảnh: {len(rows) - len(tu_choi)}/{len(rows)}; từ chối: {len(tu_choi)}"
          + (" (" + ", ".join(r["anh"] for r in tu_choi) + ")" if tu_choi else ""))
    print("Chưa có ngưỡng: mọi ảnh là 'xem' – mở xem_bang_mat.html để kiểm tra bằng mắt.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Đánh giá phương pháp nắn phẳng ảnh (Tuần 4)")
    sub = ap.add_subparsers(dest="lenh", required=True)
    r = sub.add_parser("run", help="chạy phương pháp + 3 phép kiểm tra, xuất CSV/HTML")
    r.add_argument("--phuong-phap", default="align_cu", choices=sorted(PHUONG_PHAP))
    r.add_argument("--split", default="dev", choices=sorted(SPLITS))
    r.add_argument("--xac-nhan-test", action="store_true", help="bắt buộc khi --split test (chỉ dùng ở Bước 7)")
    a = ap.parse_args()
    if a.lenh == "run":
        cmd_run(a)


if __name__ == "__main__":
    main()
