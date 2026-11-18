"""
kiem_chuan_hoa.py - Đo tác dụng của normalize() (Tuần 4, Bước 5 `v5_chuan_hoa` – docs/ke_hoach_tuan4.md).

CHỈ ảnh dev (0001–0034 + D001–D010); không đọc ảnh test 0035–0040. Chỉ ghi data/_eval/v5_chuan_hoa/ và
data/_eval/v4_verify/anh_nan_sha256.csv; không đụng data/raw/, data/raw_digits/.

Mọi phép đo nằm ở ĐÂY (eval), normalize() không dùng chúng: mặt nạ giấy trắng lấy từ PDF render, độ tách lấy từ
nhãn cell_labels.csv – normalize() chỉ được dùng anh_nan + layout.

  a. Nền giấy (mặt nạ giấy trắng: trang mẫu render 300 DPI, điểm ≥ 250 cách mọi nét in ≥ 2 mm, bỏ phần tử layout
     nới 3 mm, bỏ vùng viết tay tự do, vùng mã, 20×20 mm quanh marker):
       bong  = (p95 − p5 trung vị 140 ô lưới 10×14) / p50 giấy – bóng / độ dốc sáng (CHỈ SỐ QUYẾT ĐỊNH)
       dan   = (p95 − p5) / p50 mọi điểm giấy;  std_td = độ lệch chuẩn / p50
       nhieu = trung bình |ảnh − median 5×5| trên giấy (bỏ 1% lớn nhất) / p50 – nhiễu hạt (C2)
       muc_marker = trung bình lõi 6×6 mm 4 marker (mức đen) – để đo cân bằng sáng GIỮA các ảnh
  b. Độ tách theo nhãn (phiếu): độ dịch ±4 mm dò MỘT LẦN trên anh_nan (register với phieu_trang.pdf), dùng lại cho
     mọi cách chuẩn hoá -> khác biệt chỉ do cường độ. Hai đặc trưng mỗi ô:
       local  = local_darkness (lõi so với vành giấy quanh ô – đặc trưng OMR hiện tại, gần như bất biến với bóng)
       tuyet_doi = 1 − trung bình lõi / 255 (không vành nền – nơi chuẩn hoá phải thể hiện lợi ích)
     Mỗi hàng: hiệu = min(lớp) − max(blank); tương đối = hiệu / (trung vị filled − trung vị blank ô đáp án của ảnh).
     Gộp theo điều kiện (ô đáp án): AUC và p1(faint) − p99(blank), khoảng tin cậy bootstrap theo ảnh.
  c. Trang D: mỗi ô viết (dò lệch theo hàng ±4 mm, co 1 mm khỏi viền): giấy = trung vị, nét = p2,
     tương phản = (giấy − nét) / giấy, nét/nhiễu = (giấy − nét) / (nhieu · p50).
  d. Thời gian normalize (ms / ảnh).

Chạy (từ thư mục smart_exam_db/):
  python tools/kiem_chuan_hoa.py van-tay      # SHA-256 anh_nan v4 – chạy TRƯỚC khi sửa preprocessing.py
  python tools/kiem_chuan_hoa.py mat-na       # mặt nạ giấy trắng + ảnh chồng -> xem_mat_na.html (xem bằng mắt)
  python tools/kiem_chuan_hoa.py tu-kiem      # tự kiểm phép đo: đồng nhất (Δ = 0) + gradient nhân tạo
  python tools/kiem_chuan_hoa.py khao-sat     # 12 cấu hình (pp.CACH_CHUAN_HOA) -> nen_/o_/hang_/chu_so_/tom_tat_<cách>
  python tools/kiem_chuan_hoa.py so-sanh      # cổng 1–3, xếp hạng maximin, bootstrap ghép cặp -> so_sanh.md / .json
  python tools/kiem_chuan_hoa.py xem-b        # ảnh trước/sau 12 cấu hình -> xem_b.html
  python tools/kiem_chuan_hoa.py so-anh-nan   # anh_nan hiện tại vs vân tay v4 -> so_pixel_dev.csv (cho --ke-thua v4_verify)
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_preprocessing import (ANSWER_SHEET, CODE_MASK_MM, EVAL_DIR, HEADER_MM, MARKER_MASK_MM, ROOT,  # noqa: E402
                                doc_nhan_o, list_images, nap_layout_loai, render_pdf_page)
from check_labels import SEARCH_MM, item_box, local_darkness, register  # noqa: E402
import cv_engine.preprocessing as pp  # noqa: E402

OUT = EVAL_DIR / "v5_chuan_hoa"
VAN_TAY = EVAL_DIR / "v4_verify" / "anh_nan_sha256.csv"
MM = 300 / 25.4
PDF = {"phieu": "phieu_trang.pdf", "chu_so": "trang_chu_so.pdf"}

GIAY_TRANG_MIN = 250
CO_GIAY_MM = 2.0
NOI_PHAN_TU_MM = 3.0
VUNG_TRONG_MM = (14, 14, 196, 283)
CHU_KY_MM = (14, 259, 196, 283)
LUOI_NEN = (10, 14)
LUOI_MIN = 0.05
LOI_MARKER_MM = 3.0

LOI_TI_LE = 0.75
BOOT_N, BOOT_SEED = 1000, 2026
CO_O_VIET_MM = 1.0
DIEU_KIEN = ("C1", "C2", "C3", "C4")
ANH_GRADIENT = ("0001_C1", "0008_C1")


def ghi_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


def ghi_jpg(path: Path, img, rong=1000, q=85) -> None:
    if img.shape[1] > rong:
        img = cv2.resize(img, (rong, round(img.shape[0] * rong / img.shape[1])), interpolation=cv2.INTER_AREA)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tofile(str(path))


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def anh_nan_v(x) -> np.ndarray:
    kq = pp.preprocess(x.duong_dan, nap_layout_loai(x.loai))
    if not kq.ok:
        sys.exit(f"{x.ten}: preprocess từ chối ({kq.ly_do}) – v4 trên dev phải ok 78/78")
    return kq.anh_nan


def f4(v) -> str:
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.4f}"


def cmd_van_tay(a) -> None:
    if VAN_TAY.exists() and not a.ghi_de:
        sys.exit(f"{VAN_TAY} đã có – vân tay v4 chỉ ghi một lần (thêm --ghi-de nếu chắc chắn code vẫn là v4).")
    if git("status", "--porcelain", "--", "cv_engine/preprocessing.py"):
        sys.exit("cv_engine/preprocessing.py đã bị sửa so với HEAD – vân tay v4 phải ghi trên code v4.")
    head = git("rev-parse", "--short", "HEAD")
    rows = []
    for x in list_images("dev"):
        kq = pp.preprocess(x.duong_dan, nap_layout_loai(x.loai))
        a_n = np.ascontiguousarray(kq.anh_nan)
        rows.append({"anh": x.ten, "dieu_kien": x.dieu_kien, "ok": int(kq.ok), "ly_do": kq.ly_do,
                     "huong_xoay": kq.huong_xoay, "cao": a_n.shape[0], "rong": a_n.shape[1], "dtype": str(a_n.dtype),
                     "sha256": hashlib.sha256(a_n.tobytes()).hexdigest(), "git_head": head})
        print(f"  {x.ten}: ok={int(kq.ok)} {rows[-1]['sha256'][:12]}")
    ghi_csv(VAN_TAY, rows)
    print(f"\n{len(rows)} ảnh dev, ok {sum(r['ok'] for r in rows)}/{len(rows)}, HEAD {head} -> {VAN_TAY}")


def cmd_so_anh_nan(a) -> None:
    if not VAN_TAY.exists():
        sys.exit(f"Thiếu {VAN_TAY} – vân tay v4 phải ghi trước khi sửa preprocessing.py (lệnh van-tay).")
    ref = {r["anh"]: r for r in csv.DictReader(VAN_TAY.open(encoding="utf-8-sig"))}
    v5 = {}
    if a.phuong_phap != "v5_chuan_hoa":
        v5 = {r["anh"]: r["sha256_anh_chuan_hoa"] for r in csv.DictReader((OUT / "so_pixel_dev.csv").open(encoding="utf-8-sig"))}
    out = EVAL_DIR / a.phuong_phap
    rows, khac = [], []
    for x in list_images("dev"):
        kq = pp.preprocess(x.duong_dan, nap_layout_loai(x.loai))
        a_n = np.ascontiguousarray(kq.anh_nan)
        sha = hashlib.sha256(a_n.tobytes()).hexdigest()
        r0 = ref[x.ten]
        ch = kq.anh_chuan_hoa
        sha_ch = hashlib.sha256(np.ascontiguousarray(ch).tobytes()).hexdigest() if ch is not None else ""
        giong = sha == r0["sha256"] and str(kq.ok and 1 or 0) == r0["ok"] and kq.ly_do == r0["ly_do"]
        if v5:
            giong = giong and sha_ch == v5[x.ten]
        if not giong:
            khac.append(x.ten)
        rows.append({"anh": x.ten, "so_diem_khac": 0 if giong else "sha_khac", "sha256_anh_nan": sha,
                     "sha256_v4": r0["sha256"], "ok": int(kq.ok), "ly_do": kq.ly_do, "sha256_anh_chuan_hoa": sha_ch,
                     **({"sha256_chuan_hoa_v5": v5[x.ten]} if v5 else {})})
    ghi_csv(out / "so_pixel_dev.csv", rows)
    print(f"{len(rows) - len(khac)}/{len(rows)} ảnh dev: anh_nan giống vân tay v4 từng byte (kèm ok, ly_do)"
          + (", anh_chuan_hoa giống v5 từng byte" if v5 else "")
          + (f"; KHÁC: {', '.join(khac)}" if khac else "") + f" -> {out / 'so_pixel_dev.csv'}")


def mm_px(v) -> int:
    return round(v * MM)


def mat_na_giay(loai: str, layout: dict, mau: np.ndarray) -> np.ndarray:
    nen_in = (mau < GIAY_TRANG_MIN).astype(np.uint8)
    dist = cv2.distanceTransform(1 - nen_in, cv2.DIST_L2, 5)
    m = (dist >= CO_GIAY_MM * MM).astype(np.uint8)
    bo = np.zeros_like(m)
    noi = NOI_PHAN_TU_MM * MM
    if loai == "phieu":
        a = layout["answers"]
        tron = [(c, a["bubble_radius"]) for q in a["centers"].values() for c in q.values()]
        for f in ("sbd", "exam_code"):
            tron += [(p, layout[f]["bubble_radius"]) for col in layout[f]["bubbles"] for p in col]
            for x, y, w, h in layout[f]["handwriting_boxes"]:
                cv2.rectangle(bo, (round(x - noi), round(y - noi)), (round(x + w + noi), round(y + h + noi)), 1, -1)
        for (cx, cy), r in tron:
            cv2.circle(bo, (round(cx), round(cy)), round(r + noi), 1, -1)
        vung_tu_do = [HEADER_MM, CHU_KY_MM]
    else:
        for b in layout["boxes"]:
            x, y, w, h = b["rect"]
            cv2.rectangle(bo, (round(x - noi), round(y - noi)), (round(x + w + noi), round(y + h + noi)), 1, -1)
        vung_tu_do = [HEADER_MM]
    for x0, y0, x1, y1 in vung_tu_do + [CODE_MASK_MM]:
        bo[mm_px(y0):mm_px(y1), mm_px(x0):mm_px(x1)] = 1
    k = MARKER_MASK_MM * MM
    for cx, cy in layout["markers"]["centers"].values():
        bo[max(0, round(cy - k)):round(cy + k), max(0, round(cx - k)):round(cx + k)] = 1
    trong = np.zeros_like(m)
    x0, y0, x1, y1 = VUNG_TRONG_MM
    trong[mm_px(y0):mm_px(y1), mm_px(x0):mm_px(x1)] = 1
    return (m == 1) & (bo == 0) & (trong == 1)


def nap_tai_nguyen() -> dict:
    L = {lo: nap_layout_loai(lo) for lo in PDF}
    mau = {}
    for lo in PDF:
        W, H = L[lo]["page_px"]
        m = render_pdf_page(ANSWER_SHEET / "output" / PDF[lo], 300)
        if m.shape[0] < H or m.shape[1] < W:
            sys.exit(f"Trang mẫu {PDF[lo]} {m.shape} nhỏ hơn page_px {W}×{H}")
        mau[lo] = np.ascontiguousarray(m[:H, :W])
    return {"layout": L, "mau": mau, "mat_na": {lo: mat_na_giay(lo, L[lo], mau[lo]) for lo in PDF}}


def o_luoi() -> list[tuple[slice, slice]]:
    x0, y0, x1, y1 = (mm_px(v) for v in VUNG_TRONG_MM)
    xs, ys = np.linspace(x0, x1, LUOI_NEN[0] + 1).round().astype(int), np.linspace(y0, y1, LUOI_NEN[1] + 1).round().astype(int)
    return [(slice(ys[j], ys[j + 1]), slice(xs[i], xs[i + 1])) for j in range(LUOI_NEN[1]) for i in range(LUOI_NEN[0])]


def muc_marker(anh: np.ndarray, layout: dict) -> float:
    k = LOI_MARKER_MM * MM
    return float(np.mean([anh[round(cy - k):round(cy + k), round(cx - k):round(cx + k)].mean()
                          for cx, cy in layout["markers"]["centers"].values()]))


def do_nen(anh: np.ndarray, mask: np.ndarray, layout: dict) -> dict:
    v = anh[mask].astype(np.float32)
    p5, p50, p95 = np.percentile(v, (5, 50, 95))
    med = []
    for sy, sx in o_luoi():
        m = mask[sy, sx]
        if m.mean() >= LUOI_MIN:
            med.append(float(np.median(anh[sy, sx][m])))
    med = np.array(med)
    q5, q95 = np.percentile(med, (5, 95))
    d = np.abs(anh.astype(np.float32) - cv2.medianBlur(anh, 5).astype(np.float32))[mask]
    d = d[d <= np.percentile(d, 99)]
    mk = muc_marker(anh, layout)
    return {"giay_p50": float(p50), "bong": float((q95 - q5) / p50), "bong_tho": float(q95 - q5),
            "luoi_min": float(med.min()), "luoi_max": float(med.max()), "so_o_luoi": len(med),
            "dan": float((p95 - p5) / p50), "std_td": float(v.std() / p50), "nhieu": float(d.mean() / p50),
            "muc_marker": mk, "muc_marker_td": mk / float(p50)}


def nhom_o(layout: dict, nhan: dict) -> list[tuple]:
    out = []
    a = layout["answers"]
    for q in range(1, a["num_questions"] + 1):
        out.append(("dap_an", ("q", q), str(q), [(a["centers"][str(q)][o], nhan[(str(q), o)], o) for o in a["options"]],
                    a["bubble_radius"]))
    for f in ("sbd", "exam_code"):
        for c, col in enumerate(layout[f]["bubbles"]):
            out.append(("chu_so", (f, 0), f"{f}{c + 1}", [(p, nhan[(f"{f}{c + 1}", str(k))], str(k))
                                                          for k, p in enumerate(col)], layout[f]["bubble_radius"]))
    return out


def tinh_dich(anh_nan: np.ndarray, layout: dict, mau: np.ndarray) -> dict:
    s = round(SEARCH_MM * layout["dpi"] / 25.4)
    items = [("q", q) for q in range(1, layout["answers"]["num_questions"] + 1)] + [("sbd", 0), ("exam_code", 0)]
    return {it: register(anh_nan, mau, item_box(layout, it), s) for it in items}


def loi_tb(anh: np.ndarray, cx: float, cy: float, r: float) -> float:
    x0, y0 = int(cx - r), int(cy - r)
    p = anh[y0:int(cy + r) + 1, x0:int(cx + r) + 1].astype(np.float32)
    yy, xx = np.ogrid[:p.shape[0], :p.shape[1]]
    return float(p[(xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2 <= (LOI_TI_LE * r) ** 2].mean())


def vanh_giay(anh: np.ndarray, cx: float, cy: float, r: float) -> float:
    x0, y0 = int(cx - 1.5 * r), int(cy - 1.5 * r)
    p = anh[y0:int(cy + 1.5 * r), x0:int(cx + 1.5 * r)].astype(np.float32)
    yy, xx = np.ogrid[:p.shape[0], :p.shape[1]]
    d2 = (xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2
    return float(np.median(p[(d2 >= (1.15 * r) ** 2) & (d2 <= (1.45 * r) ** 2)]))


def do_o(anh: np.ndarray, layout: dict, nhan: dict, dich: dict) -> list[dict]:
    rows = []
    for loai, it, hang, o, r in nhom_o(layout, nhan):
        dx, dy = dich[it]
        for (cx, cy), lab, ten in o:
            rows.append({"loai": loai, "hang": hang, "o": ten, "nhan": lab,
                         "local": local_darkness(anh, cx + dx, cy + dy, r),
                         "tuyet_doi": 1.0 - loi_tb(anh, cx + dx, cy + dy, r) / 255.0,
                         "giay_vanh": vanh_giay(anh, cx + dx, cy + dy, r)})
    return rows


def thang(o: list[dict], k: str) -> float:
    f = [r[k] for r in o if r["loai"] == "dap_an" and r["nhan"] == "filled"]
    b = [r[k] for r in o if r["loai"] == "dap_an" and r["nhan"] == "blank"]
    return float(np.median(f) - np.median(b))


def hang_tu_o(o: list[dict]) -> list[dict]:
    th = {k: thang(o, k) for k in ("local", "tuyet_doi")}
    nhom: dict = {}
    for r in o:
        nhom.setdefault((r["loai"], r["hang"]), []).append(r)
    out = []
    for (loai, hang), rs in nhom.items():
        for lop in ("filled", "faint"):
            if not any(r["nhan"] == lop for r in rs) or not any(r["nhan"] == "blank" for r in rs):
                continue
            row = {"loai": loai, "hang": hang, "lop": lop}
            for k in ("local", "tuyet_doi"):
                h = min(r[k] for r in rs if r["nhan"] == lop) - max(r[k] for r in rs if r["nhan"] == "blank")
                row[f"hieu_{k}"], row[f"td_{k}"], row[f"thang_{k}"] = h, h / th[k], th[k]
            out.append(row)
    return out


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    neg = np.sort(neg)
    lo, hi = np.searchsorted(neg, pos, "left"), np.searchsorted(neg, pos, "right")
    return float((lo + (hi - lo) / 2).sum() / (len(pos) * len(neg)))


def khoang(pos: np.ndarray, neg: np.ndarray) -> float:
    return float(np.percentile(pos, 1) - np.percentile(neg, 99))


def gop(theo_anh: dict, lop: str, k: str, rng) -> dict:
    ten = list(theo_anh)
    P = np.concatenate([theo_anh[t][0] for t in ten])
    N = np.concatenate([theo_anh[t][1] for t in ten])
    out = {f"{k}_auc": auc(P, N), f"{k}_khoang": khoang(P, N)}
    bo_a, bo_k, bo_qua = [], [], 0
    for _ in range(BOOT_N):
        chon = [ten[i] for i in rng.integers(0, len(ten), len(ten))]
        p = np.concatenate([theo_anh[t][0] for t in chon])
        if len(p) == 0:
            bo_qua += 1
            continue
        n = np.concatenate([theo_anh[t][1] for t in chon])
        bo_a.append(auc(p, n))
        bo_k.append(khoang(p, n))
    for ten_s, b in (("auc", bo_a), ("khoang", bo_k)):
        out[f"{k}_{ten_s}_ci"] = (float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5)))
    out["boot_bo_qua"] = bo_qua
    return out


def tom_tat_tach(o_rows: list[dict], h_rows: list[dict]) -> dict:
    out = {}
    for dk in DIEU_KIEN:
        o = [r for r in o_rows if r["dieu_kien"] == dk and r["loai"] == "dap_an"]
        anh = sorted({r["anh"] for r in o})
        s = {"so_anh": len(anh), **{f"so_{l}": sum(r["nhan"] == l for r in o) for l in ("filled", "faint", "blank")},
             "so_anh_co_faint": len({r["anh"] for r in o if r["nhan"] == "faint"})}
        for lop in ("faint", "filled"):
            hs = [r for r in h_rows if r["dieu_kien"] == dk and r["lop"] == lop]
            s[f"{lop}_so_hang"] = len(hs)
            for k in ("local", "tuyet_doi"):
                v = np.array([r[f"hieu_{k}"] for r in hs])
                t = np.array([r[f"td_{k}"] for r in hs])
                i = int(np.argmin(t))
                s[f"{lop}_{k}_hang_tach"] = int((v > 0).sum())
                s[f"{lop}_{k}_td_min"] = float(t[i])
                s[f"{lop}_{k}_td_min_o"] = f"{hs[i]['anh']}:{hs[i]['hang']}"
                s[f"{lop}_{k}_td_p5"] = float(np.percentile(t, 5))
                s[f"{lop}_{k}_hieu_min"] = float(v.min())
            rng = np.random.default_rng(BOOT_SEED)
            for k in ("tuyet_doi", "local"):
                theo = {t: (np.array([r[k] for r in o if r["anh"] == t and r["nhan"] == lop]),
                            np.array([r[k] for r in o if r["anh"] == t and r["nhan"] == "blank"])) for t in anh}
                s.update({f"{lop}_{kk}": vv for kk, vv in gop(theo, lop, k, rng).items()})
        out[dk] = s
    return out


def do_chu_so(anh: np.ndarray, layout: dict, dich: dict, nen: dict) -> dict:
    co = CO_O_VIET_MM * MM
    sigma = nen["nhieu"] * nen["giay_p50"]
    tp, snr, net, giay = [], [], [], []
    for b in layout["boxes"]:
        dx, dy = dich[b["row"]]
        x, y, w, h = b["rect"]
        p = anh[round(y + dy + co):round(y + dy + h - co), round(x + dx + co):round(x + dx + w - co)].astype(np.float32)
        g, n = float(np.median(p)), float(np.percentile(p, 2))
        tp.append((g - n) / g)
        snr.append((g - n) / sigma)
        net.append(n)
        giay.append(g)
    tp, snr = np.array(tp), np.array(snr)
    return {"so_o": len(tp), "tp_trungvi": float(np.median(tp)), "tp_p5": float(np.percentile(tp, 5)),
            "tp_min": float(tp.min()), "snr_trungvi": float(np.median(snr)), "snr_p5": float(np.percentile(snr, 5)),
            "net_trungvi": float(np.median(net)), "giay_o_trungvi": float(np.median(giay))}


def dich_chu_so(anh_nan: np.ndarray, layout: dict, mau: np.ndarray) -> dict:
    s = round(SEARCH_MM * layout["dpi"] / 25.4)
    noi = NOI_PHAN_TU_MM * MM
    out = {}
    for row in sorted({b["row"] for b in layout["boxes"]}):
        R = np.array([b["rect"] for b in layout["boxes"] if b["row"] == row])
        box = (int(R[:, 0].min() - noi), int(R[:, 1].min() - noi),
               int((R[:, 0] + R[:, 2]).max() + noi), int((R[:, 1] + R[:, 3]).max() + noi))
        out[row] = register(anh_nan, mau, box, s)
    return out


CACH = {c: (lambda anh_nan, layout, c=c: pp.normalize(anh_nan, layout, c)) for c in pp.CACH_CHUAN_HOA}
HO = {"khong": 0, "chia_nen": 1, "chia_nen_keo": 2, "clahe": 3}
CA_BIEN_TD = 0.012


def ho(c: str) -> int:
    return HO[pp.CACH_CHUAN_HOA[c][0]]


def do_mot_anh(x, anh_nan, tn, nhan, cach_ten) -> dict:
    L, M, mau = tn["layout"][x.loai], tn["mat_na"][x.loai], tn["mau"][x.loai]
    if x.loai == "phieu":
        dich = tinh_dich(anh_nan, L, mau)
    else:
        dich = dich_chu_so(anh_nan, L, mau)
    out = {}
    for c in cach_ten:
        t0 = time.perf_counter()
        anh = CACH[c](anh_nan, L)
        ms = (time.perf_counter() - t0) * 1000
        if anh.dtype != np.uint8 or anh.shape != anh_nan.shape:
            sys.exit(f"{c}: {x.ten} trả {anh.dtype} {anh.shape} – phải uint8 {anh_nan.shape}")
        nen = {"anh": x.ten, "dieu_kien": x.dieu_kien, "cach": c, "ms": ms, **do_nen(anh, M, L)}
        base = {"anh": x.ten, "dieu_kien": x.dieu_kien, "cach": c}
        if x.loai == "phieu":
            o = do_o(anh, L, nhan[x.ma], dich)
            h = hang_tu_o(o)
            out[c] = (nen, [{**base, **r} for r in o], [{**base, **r} for r in h], None)
        else:
            out[c] = (nen, [], [], {**base, **do_chu_so(anh, L, dich, nen)})
    return out


XEM_MAT_NA = ("0001_C1", "0005_C2", "0015_C3", "0032_C4", "D003")


def cmd_mat_na(a) -> None:
    tn = nap_tai_nguyen()
    OUT.mkdir(parents=True, exist_ok=True)
    the = []
    for lo in PDF:
        m = tn["mat_na"][lo]
        ghi_jpg(OUT / "mat_na" / f"mat_na_{lo}.jpg", (m * 255).astype(np.uint8))
        nho = cv2.cvtColor(tn["mau"][lo], cv2.COLOR_GRAY2BGR)
        nho[m] = (0.45 * nho[m] + 0.55 * np.array([60, 200, 60])).astype(np.uint8)
        ghi_jpg(OUT / "mat_na" / f"mau_{lo}.jpg", nho)
        print(f"  mặt nạ {lo}: {m.mean() * 100:.1f}% trang, {m.sum():,} điểm")
        the.append(f"<figure><img src='mat_na/mau_{lo}.jpg'><figcaption>Mặt nạ {lo} trên trang mẫu render "
                   f"({m.mean() * 100:.1f}% trang)</figcaption></figure>")
    xs = {x.ten: x for x in list_images("dev")}
    for ten in XEM_MAT_NA:
        x = xs[ten]
        anh = anh_nan_v(x)
        m = tn["mat_na"][x.loai]
        c = cv2.cvtColor(anh, cv2.COLOR_GRAY2BGR)
        c[m] = (0.55 * c[m] + 0.45 * np.array([60, 200, 60])).astype(np.uint8)
        for sy, sx in o_luoi():
            cv2.rectangle(c, (sx.start, sy.start), (sx.stop, sy.stop), (200, 120, 0), 2)
        ghi_jpg(OUT / "mat_na" / f"chong_{ten}.jpg", c, rong=1240)
        the.append(f"<figure><img src='mat_na/chong_{ten}.jpg'><figcaption>{ten} – anh_nan v4, mặt nạ xanh, "
                   f"lưới 10×14 đo bóng</figcaption></figure>")
    (OUT / "xem_mat_na.html").write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Mặt nạ giấy trắng – Bước 5</title><style>body{{font-family:sans-serif;margin:16px}}
figure{{display:inline-block;margin:8px;vertical-align:top}}img{{width:600px;border:1px solid #999}}</style></head><body>
<h2>Mặt nạ giấy trắng (chỉ dùng trong eval)</h2>
<p>Xanh = điểm đo nền: trang mẫu ≥ {GIAY_TRANG_MIN}, cách mọi nét in ≥ {CO_GIAY_MM} mm, bỏ ô tròn / ô viết nới
{NOI_PHAN_TU_MM} mm, bỏ dải tiêu đề + họ tên {HEADER_MM}, dải chữ ký {CHU_KY_MM} (phiếu), vùng mã {CODE_MASK_MM},
20×20 mm quanh marker; chỉ bên trong {VUNG_TRONG_MM} mm. Cần kiểm: vùng xanh trên ảnh thật KHÔNG chứa chữ in, viền,
ô tô, chữ viết tay.</p>{"".join(the)}</body></html>""", encoding="utf-8")
    print(f"-> {OUT / 'xem_mat_na.html'}")


HUONG_GRADIENT = {"tl_br": (1, 1), "br_tl": (-1, -1), "tr_bl": (-1, 1), "bl_tr": (1, -1)}
BONG_TANG_MIN = 1.5
CHIA_NEN_HOI_PHUC = 1.25
LOCAL_DELTA_MAX = 0.02


def gradient(shape, huong=(1, 1), lo=0.6, hi=1.0) -> np.ndarray:
    H, W = shape
    yy, xx = np.mgrid[:H, :W].astype(np.float32)
    u = xx / (W - 1) if huong[0] > 0 else 1 - xx / (W - 1)
    v = yy / (H - 1) if huong[1] > 0 else 1 - yy / (H - 1)
    return lo + (hi - lo) * (u + v) / 2


def chia_nen_thu(anh: np.ndarray) -> np.ndarray:
    return np.clip(anh.astype(np.float32) / np.maximum(pp.uoc_luong_nen(anh), 1.0) * 240, 0, 255).round().astype(np.uint8)


def so_sanh_hang(ref: list[dict], moi: list[dict]) -> dict:
    R = {(r["anh"], r["loai"], r["hang"], r["lop"]): r for r in ref}
    lat, d_tho, d_td = [], [], []
    for r in moi:
        q = R[(r["anh"], r["loai"], r["hang"], r["lop"])]
        if q["hieu_local"] > 0 and r["hieu_local"] <= 0:
            lat.append(f"{r['anh']}:{r['hang']}:{r['lop']} {q['hieu_local']:.4f}->{r['hieu_local']:.4f}")
        d_tho.append(r["hieu_local"] - q["hieu_local"])
        d_td.append(r["td_local"] - q["td_local"])
    return {"so_hang": len(moi), "lat": lat, "d_tho_min": min(d_tho), "d_tho_max": max(d_tho),
            "d_td_min": min(d_td), "d_td_max": max(d_td)}


def cmd_tu_kiem(a) -> None:
    tn = nap_tai_nguyen()
    nhan = doc_nhan_o()
    xs = {x.ten: x for x in list_images("dev")}
    dat = True
    print("1. Đồng nhất: cách 'khong' đo hai lần trên cùng anh_nan -> mọi Δ phải = 0")
    for ten in ANH_GRADIENT:
        x = xs[ten]
        anh = anh_nan_v(x)
        r1 = do_mot_anh(x, anh, tn, nhan, ["khong"])["khong"]
        r2 = do_mot_anh(x, anh.copy(), tn, nhan, ["khong"])["khong"]
        ss = so_sanh_hang(r1[2], r2[2])
        nen_khac = [k for k in r1[0] if k != "ms" and r1[0][k] != r2[0][k]]
        ok = not ss["lat"] and ss["d_tho_min"] == ss["d_tho_max"] == 0 and not nen_khac
        dat &= ok
        print(f"   {ten}: {ss['so_hang']} hàng, lật {len(ss['lat'])}, Δ hiệu [{ss['d_tho_min']}, {ss['d_tho_max']}], "
              f"số đo nền khác: {nen_khac or 'không'} -> {'ĐẠT' if ok else 'KHÔNG ĐẠT'}")
    print("\n2. Gradient nhân tạo 0,6 -> 1,0 theo 4 hướng chéo, nhân vào anh_nan. Mong đợi:")
    print(f"   (i) hướng xấu nhất: bóng ≥ {BONG_TANG_MIN} × bóng gốc; (ii) mọi hướng: bóng sau chia nền thử ≤ "
          f"{CHIA_NEN_HOI_PHUC} × (gốc + chia nền thử); (iii) local_darkness |Δ| ≤ {LOCAL_DELTA_MAX}, 0 hàng lật")
    rows = []
    for ten in ANH_GRADIENT:
        x = xs[ten]
        L, M = tn["layout"]["phieu"], tn["mat_na"]["phieu"]
        anh = anh_nan_v(x)
        dich = tinh_dich(anh, L, tn["mau"]["phieu"])
        o_goc = do_o(anh, L, nhan[x.ma], dich)
        h_goc = [{"anh": ten, **r} for r in hang_tu_o(o_goc)]
        bien = {"goc": anh, "goc_chia_nen_thu": chia_nen_thu(anh)}
        for hg, d in HUONG_GRADIENT.items():
            g = np.clip(anh.astype(np.float32) * gradient(anh.shape, d), 0, 255).round().astype(np.uint8)
            bien[f"gradient_{hg}"], bien[f"gradient_{hg}_chia_nen_thu"] = g, chia_nen_thu(g)
        for k, im in bien.items():
            o = do_o(im, L, nhan[x.ma], dich)
            ss = so_sanh_hang(h_goc, [{"anh": ten, **r} for r in hang_tu_o(o)])
            d_loc = np.array([oo["local"] for oo in o]) - np.array([oo["local"] for oo in o_goc])
            rows.append({"anh": ten, "bien_the": k, **do_nen(im, M, L), "local_max_abs_delta": float(np.abs(d_loc).max()),
                         "hang_lat": len(ss["lat"]), "d_td_min": ss["d_td_min"], "d_td_max": ss["d_td_max"]})
        R = {r["bien_the"]: r for r in rows if r["anh"] == ten}
        b0, bc = R["goc"]["bong"], R["goc_chia_nen_thu"]["bong"]
        xau = max(HUONG_GRADIENT, key=lambda hg: R[f"gradient_{hg}"]["bong"])
        ok1 = R[f"gradient_{xau}"]["bong"] >= BONG_TANG_MIN * b0
        ok2 = all(R[f"gradient_{hg}_chia_nen_thu"]["bong"] <= CHIA_NEN_HOI_PHUC * bc for hg in HUONG_GRADIENT)
        gr = [R[f"gradient_{hg}"] for hg in HUONG_GRADIENT]
        ok3 = all(r["local_max_abs_delta"] <= LOCAL_DELTA_MAX and r["hang_lat"] == 0 for r in gr)
        dat &= ok1 and ok2 and ok3
        print(f"   {ten}: bóng gốc {b0:.4f}, gốc + chia nền thử {bc:.4f}")
        for hg in HUONG_GRADIENT:
            r, rc = R[f"gradient_{hg}"], R[f"gradient_{hg}_chia_nen_thu"]
            print(f"      {hg}: bóng {r['bong']:.4f} (×{r['bong'] / b0:.2f}) -> chia nền thử {rc['bong']:.4f} "
                  f"(×{rc['bong'] / bc:.2f}); local |Δ| max {r['local_max_abs_delta']:.4f}, lật {r['hang_lat']}, "
                  f"Δ tương đối [{r['d_td_min']:+.4f}, {r['d_td_max']:+.4f}]")
        print(f"      (i) {'ĐẠT' if ok1 else 'KHÔNG ĐẠT'} ({xau})  (ii) {'ĐẠT' if ok2 else 'KHÔNG ĐẠT'}  "
              f"(iii) {'ĐẠT' if ok3 else 'KHÔNG ĐẠT'}")
    ghi_csv(OUT / "tu_kiem_gradient.csv", rows)
    print(f"\nTỰ KIỂM: {'ĐẠT' if dat else 'KHÔNG ĐẠT'}  (-> {OUT / 'tu_kiem_gradient.csv'})")


def bang_md(tieu_de: list[str], dong: list[list]) -> str:
    return "\n".join(["| " + " | ".join(tieu_de) + " |", "|" + "---|" * len(tieu_de)]
                     + ["| " + " | ".join(str(v) for v in d) + " |" for d in dong])


def ci(v) -> str:
    return f"[{v[0]:.3f}, {v[1]:.3f}]"


def tom_tat(c: str, nen: list, o: list, h: list, cs: list) -> str:
    md = [f"# Bước 5 – khảo sát cách `{c}` (dev, {len(nen)} ảnh)\n"]
    dong = []
    for dk in DIEU_KIEN + ("D",):
        r = [x for x in nen if x["dieu_kien"] == dk]
        b = np.array([x["bong"] for x in r])
        i = int(np.argmax(b))
        dong.append([dk, len(r), f"{np.median(b):.4f}", f"{b[i]:.4f} ({r[i]['anh']})",
                     f"{np.median([x['dan'] for x in r]):.4f}", f"{np.median([x['std_td'] for x in r]):.4f}",
                     f"{np.median([x['nhieu'] for x in r]):.4f}", f"{max(x['nhieu'] for x in r):.4f}",
                     f"{np.median([x['giay_p50'] for x in r]):.1f}", f"{np.median([x['muc_marker'] for x in r]):.1f}"])
    md.append("## a. Nền giấy\n")
    md.append(bang_md(["ĐK", "ảnh", "bóng TV", "bóng max (ảnh)", "dàn TV", "std/p50 TV", "nhiễu TV", "nhiễu max",
                       "giấy p50 TV", "mực marker TV"], dong))
    gp, mk = np.array([x["giay_p50"] for x in nen]), np.array([x["muc_marker"] for x in nen])
    md.append(f"\nCân bằng GIỮA các ảnh (78 ảnh): giấy p50 std {gp.std():.1f} (min {gp.min():.0f}, max {gp.max():.0f}); "
              f"mực marker std {mk.std():.1f} (min {mk.min():.0f}, max {mk.max():.0f}).\n")
    T = tom_tat_tach(o, h)
    md.append("## b. Cỡ mẫu (ô đáp án)\n")
    md.append(bang_md(["ĐK", "ảnh", "ảnh có faint", "faint", "filled", "blank", "hàng faint", "hàng filled"],
                      [[dk, T[dk]["so_anh"], T[dk]["so_anh_co_faint"], T[dk]["so_faint"], T[dk]["so_filled"],
                        T[dk]["so_blank"], T[dk]["faint_so_hang"], T[dk]["filled_so_hang"]] for dk in DIEU_KIEN]))
    md.append("\n(Hàng filled gồm cả 9 cột chữ số SBD/mã đề mỗi phiếu có ô tô; hàng faint chỉ ở ô đáp án.)\n")
    for lop in ("faint", "filled"):
        md.append(f"## b. {lop} / blank theo hàng\n")
        md.append(bang_md(["ĐK", "đặc trưng", "hàng tách", "hiệu min", "tương đối min (ảnh:hàng)", "tương đối p5"],
                          [[dk, k, f"{T[dk][f'{lop}_{k}_hang_tach']}/{T[dk][f'{lop}_so_hang']}",
                            f"{T[dk][f'{lop}_{k}_hieu_min']:+.4f}",
                            f"{T[dk][f'{lop}_{k}_td_min']:+.4f} ({T[dk][f'{lop}_{k}_td_min_o']})",
                            f"{T[dk][f'{lop}_{k}_td_p5']:+.4f}"] for dk in DIEU_KIEN for k in ("local", "tuyet_doi")]))
        md.append(f"\n## b. {lop} / blank gộp ô đáp án (CI 95% bootstrap theo ảnh, {BOOT_N} lần, seed {BOOT_SEED})\n")
        md.append(bang_md(["ĐK", "đặc trưng", "AUC", "CI AUC", "p1(lớp) − p99(blank)", "CI"],
                          [[dk, k, f"{T[dk][f'{lop}_{k}_auc']:.4f}", ci(T[dk][f'{lop}_{k}_auc_ci']),
                            f"{T[dk][f'{lop}_{k}_khoang']:+.4f}", ci(T[dk][f'{lop}_{k}_khoang_ci'])]
                           for dk in DIEU_KIEN for k in ("tuyet_doi", "local")]))
        md.append("")
    md.append("## b. 0032_C4 (vệt bóng) – từng hàng có faint / hiệu filled nhỏ nhất\n")
    r32 = sorted([r for r in h if r["anh"] == "0032_C4"], key=lambda r: r["td_local"])
    md.append(bang_md(["hàng", "lớp", "hiệu local", "tương đối local", "hiệu tuyệt đối", "tương đối tuyệt đối"],
                      [[r["hang"], r["lop"], f"{r['hieu_local']:+.4f}", f"{r['td_local']:+.4f}",
                        f"{r['hieu_tuyet_doi']:+.4f}", f"{r['td_tuyet_doi']:+.4f}"]
                       for r in r32 if r["lop"] == "faint"] + [[r["hang"], r["lop"], f"{r['hieu_local']:+.4f}",
                        f"{r['td_local']:+.4f}", f"{r['hieu_tuyet_doi']:+.4f}", f"{r['td_tuyet_doi']:+.4f}"]
                       for r in r32 if r["lop"] == "filled"][:5]))
    kho = sorted([r for r in h if r["lop"] == "faint"], key=lambda r: r["td_local"])[:10]
    md.append("\n## b. 10 hàng faint khó nhất (tương đối local nhỏ nhất)\n")
    md.append(bang_md(["ảnh", "hàng", "hiệu local", "tương đối local", "hiệu tuyệt đối", "tương đối tuyệt đối"],
                      [[r["anh"], r["hang"], f"{r['hieu_local']:+.4f}", f"{r['td_local']:+.4f}",
                        f"{r['hieu_tuyet_doi']:+.4f}", f"{r['td_tuyet_doi']:+.4f}"] for r in kho]))
    md.append("\n## c. Trang chữ số D\n")
    md.append(bang_md(["trang", "ô", "tương phản TV", "tương phản p5", "nét/nhiễu TV", "nét/nhiễu p5", "mức nét TV",
                       "giấy trong ô TV"],
                      [[r["anh"], r["so_o"], f"{r['tp_trungvi']:.3f}", f"{r['tp_p5']:.3f}", f"{r['snr_trungvi']:.1f}",
                        f"{r['snr_p5']:.1f}", f"{r['net_trungvi']:.1f}", f"{r['giay_o_trungvi']:.1f}"] for r in cs]))
    net = np.array([r["net_trungvi"] for r in cs])
    md.append(f"\nMức nét giữa 10 trang: std {net.std():.1f} (min {net.min():.0f}, max {net.max():.0f}).\n")
    ms = np.array([x["ms"] for x in nen])
    md.append(f"## d. Thời gian `{c}`: trung vị {np.median(ms):.1f} ms, max {ms.max():.1f} ms "
              f"({nen[int(np.argmax(ms))]['anh']})\n")
    return "\n".join(md), T


def cmd_khao_sat(a) -> None:
    tn = nap_tai_nguyen()
    nhan = doc_nhan_o()
    OUT.mkdir(parents=True, exist_ok=True)
    kq = {c: ([], [], [], []) for c in a.cach}
    t0 = time.perf_counter()
    for x in list_images("dev"):
        anh = anh_nan_v(x)
        for c, (nen, o, h, cs) in do_mot_anh(x, anh, tn, nhan, a.cach).items():
            kq[c][0].append(nen)
            kq[c][1].extend(o)
            kq[c][2].extend(h)
            if cs:
                kq[c][3].append(cs)
        print(f"  {x.ten}")
    for c, (nen, o, h, cs) in kq.items():
        ghi_csv(OUT / f"nen_{c}.csv", nen)
        ghi_csv(OUT / f"o_{c}.csv", o)
        ghi_csv(OUT / f"hang_{c}.csv", h)
        ghi_csv(OUT / f"chu_so_{c}.csv", cs)
        md, T = tom_tat(c, nen, o, h, cs)
        (OUT / f"tom_tat_{c}.md").write_text(md, encoding="utf-8")
        (OUT / f"tom_tat_{c}.json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        print(md if len(kq) == 1 else f"  -> tom_tat_{c}.md")
    print(f"\n{(time.perf_counter() - t0):.0f} s -> {OUT}")


def doc_csv(path: Path) -> list[dict]:
    so = {"local", "tuyet_doi", "giay_vanh", "hieu_local", "td_local", "hieu_tuyet_doi", "td_tuyet_doi", "ms", "bong",
          "nhieu", "giay_p50", "muc_marker", "tp_trungvi", "tp_p5", "snr_trungvi", "snr_p5", "net_trungvi", "dan"}
    with path.open(encoding="utf-8-sig") as f:
        return [{k: (float(v) if k in so else v) for k, v in r.items()} for r in csv.DictReader(f)]


def nap_ket_qua(c: str) -> dict:
    return {k: doc_csv(OUT / f"{k}_{c}.csv") for k in ("nen", "o", "hang", "chu_so")}


def mau_bootstrap(anh_theo_dk: dict) -> dict:
    rng = np.random.default_rng(BOOT_SEED)
    return {dk: rng.integers(0, len(ds), (BOOT_N, len(ds))) for dk, ds in anh_theo_dk.items()}


def gop_ghep_cap(o: list[dict], anh_theo_dk: dict, rut: dict, k="tuyet_doi", lop="faint") -> dict:
    out = {}
    for dk, ds in anh_theo_dk.items():
        P = {t: [] for t in ds}
        N = {t: [] for t in ds}
        for r in o:
            if r["dieu_kien"] == dk and r["loai"] == "dap_an":
                if r["nhan"] == lop:
                    P[r["anh"]].append(r[k])
                elif r["nhan"] == "blank":
                    N[r["anh"]].append(r[k])
        P = [np.array(P[t]) for t in ds]
        N = [np.array(N[t]) for t in ds]
        p, n = np.concatenate(P), np.concatenate(N)
        ab, kb = np.empty(BOOT_N), np.empty(BOOT_N)
        for b, idx in enumerate(rut[dk]):
            pp_, nn = np.concatenate([P[i] for i in idx]), np.concatenate([N[i] for i in idx])
            ab[b], kb[b] = auc(pp_, nn), khoang(pp_, nn)
        out[dk] = (auc(p, n), khoang(p, n), ab, kb)
    return out


def ci_hieu(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    d = a - b
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def cmd_so_sanh(a) -> None:
    ds_cach = [c for c in CACH if (OUT / f"o_{c}.csv").exists()]
    if "khong" not in ds_cach or len(ds_cach) < 2:
        sys.exit("Chạy trước: python tools/kiem_chuan_hoa.py khao-sat")
    K = {c: nap_ket_qua(c) for c in ds_cach}
    o0 = K["khong"]["o"]
    anh_theo_dk = {dk: sorted({r["anh"] for r in o0 if r["dieu_kien"] == dk}) for dk in DIEU_KIEN}
    rut = mau_bootstrap(anh_theo_dk)
    G = {c: {(lop): gop_ghep_cap(K[c]["o"], anh_theo_dk, rut, "tuyet_doi", lop) for lop in ("faint", "filled")}
         for c in ds_cach}
    H0 = {(r["anh"], r["loai"], r["hang"], r["lop"]): r for r in K["khong"]["hang"]}
    doc = {}
    for r in o0:
        doc.setdefault((r["anh"], r["loai"], r["hang"]), []).append(r["giay_vanh"])
    doc = {k: (max(v) - min(v)) / max(v) for k, v in doc.items()}
    nen0 = {dk: np.median([r["bong"] for r in K["khong"]["nen"] if r["dieu_kien"] == dk]) for dk in DIEU_KIEN + ("D",)}
    bang, chi_tiet, md = {}, {}, ["# Bước 5 dừng B – so 11 cấu hình với `khong` (dev)\n"]
    for c in ds_cach:
        R = K[c]
        s = {"ho": pp.CACH_CHUAN_HOA[c][0], "ms_tv": float(np.median([r["ms"] for r in R["nen"]])),
             "ms_max": float(max(r["ms"] for r in R["nen"]))}
        lat, giam = [], {lop: [] for lop in ("faint", "filled")}
        for r in R["hang"]:
            q = H0[(r["anh"], r["loai"], r["hang"], r["lop"])]
            d = r["td_local"] - q["td_local"]
            giam[r["lop"]].append((d, f"{r['anh']}:{r['hang']}"))
            if q["hieu_local"] > 0 >= r["hieu_local"]:
                lat.append({"hang": f"{r['anh']}:{r['hang']}:{r['lop']}", "truoc": q["hieu_local"], "sau": r["hieu_local"],
                            "d_td": d, "ca_bien": abs(d) <= CA_BIEN_TD})
        s["lat"] = lat
        s["cong1"] = not lat
        for lop in giam:
            d, o_ = min(giam[lop])
            s[f"{lop}_d_td_min"], s[f"{lop}_d_td_min_o"] = d, o_
            s[f"{lop}_so_giam_qua_bien"] = sum(x < -CA_BIEN_TD for x, _ in giam[lop])
        s["bong"] = {dk: float(np.median([r["bong"] for r in R["nen"] if r["dieu_kien"] == dk])) for dk in nen0}
        s["bong_max"] = {dk: max((r["bong"], r["anh"]) for r in R["nen"] if r["dieu_kien"] == dk) for dk in nen0}
        b0 = {r["anh"]: r["bong"] for r in K["khong"]["nen"]}
        s["so_anh_bong_tang"] = sum(r["bong"] > b0[r["anh"]] for r in R["nen"])
        s["cong2"] = c != "khong" and all(s["bong"][dk] < nen0[dk] for dk in nen0)
        s["nhieu"] = {dk: float(np.median([r["nhieu"] for r in R["nen"] if r["dieu_kien"] == dk])) for dk in nen0}
        gp = np.array([r["giay_p50"] for r in R["nen"]])
        mk = np.array([r["muc_marker"] for r in R["nen"]])
        s["giay_std"], s["muc_std"] = float(gp.std()), float(mk.std())
        s["cong3"] = True
        for lop in ("faint", "filled"):
            for dk in DIEU_KIEN:
                au, kh, ab, kb = G[c][lop][dk]
                au0, kh0, ab0, kb0 = G["khong"][lop][dk]
                s[f"{lop}_{dk}"] = {"auc": au, "khoang": kh, "d_auc": au - au0, "d_khoang": kh - kh0,
                                    "ci_d_auc": ci_hieu(ab, ab0), "ci_d_khoang": ci_hieu(kb, kb0)}
                if lop == "faint" and (au < au0 or kh < kh0):
                    s["cong3"] = False
        diem = np.min([G[c]["faint"][dk][2] for dk in DIEU_KIEN], axis=0)
        s["diem"] = min(G[c]["faint"][dk][0] for dk in DIEU_KIEN)
        s["dk_xau"] = min(DIEU_KIEN, key=lambda dk: G[c]["faint"][dk][0])
        chi_tiet[c] = diem
        cs = R["chu_so"]
        s["D_tp"] = float(np.median([r["tp_trungvi"] for r in cs]))
        s["D_snr"] = float(np.median([r["snr_trungvi"] for r in cs]))
        s["D_net_std"] = float(np.std([r["net_trungvi"] for r in cs]))
        bang[c] = s
    qua = [c for c in ds_cach if bang[c]["cong1"] and bang[c]["cong3"] and (bang[c]["cong2"] or c == "khong")]
    tot = max(qua, key=lambda c: bang[c]["diem"])
    hoa = []
    for c in qua:
        lo_, hi_ = ci_hieu(chi_tiet[tot], chi_tiet[c])
        bang[c]["ci_kem_tot"] = (lo_, hi_)
        if c == tot or lo_ <= 0:
            hoa.append(c)
    chon = min(hoa, key=lambda c: (ho(c), bang[c]["nhieu"]["C2"], bang[c]["ms_tv"]))
    md.append(f"Cấu hình qua cổng (`khong` là đối chứng, miễn cổng 2): {', '.join(qua)}\n")
    md.append(f"Tốt nhất theo maximin AUC faint tuyệt đối: **{tot}** ({bang[tot]['diem']:.4f}); hoà với nó (CI ghép cặp "
              f"của Δ điểm maximin chứa 0): {', '.join(hoa)}\n")
    md.append(f"**Đề xuất (đơn giản nhất trong nhóm hoà, rồi ít nhiễu C2, rồi nhanh): `{chon}`**\n")
    md.append("## Cổng + xếp hạng\n")
    md.append(bang_md(["cấu hình", "cổng 1 (lật / ca biên)", "cổng 2 bóng", "cổng 3", "maximin AUC (ĐK)",
                       "CI Δ so với tốt nhất", "ms TV / max"],
                      [[c, "ĐẠT" if b["cong1"] else f"TRƯỢT {len(b['lat'])} / {sum(x['ca_bien'] for x in b['lat'])}",
                        "đối chứng" if c == "khong" else ("ĐẠT" if b["cong2"] else "TRƯỢT"),
                        "ĐẠT" if b["cong3"] else "TRƯỢT", f"{b['diem']:.4f} ({b['dk_xau']})",
                        ci(b["ci_kem_tot"]) if "ci_kem_tot" in b else "–", f"{b['ms_tv']:.0f} / {b['ms_max']:.0f}"]
                       for c, b in bang.items()]))
    md.append("\n## a. Bóng (trung vị theo điều kiện; tệ nhất) + số ảnh bóng tăng\n")
    md.append(bang_md(["cấu hình"] + [f"{dk}" for dk in nen0] + ["ảnh bóng tăng", "tệ nhất C2"],
                      [[c] + [f"{b['bong'][dk]:.3f}" for dk in nen0] + [b["so_anh_bong_tang"],
                       f"{b['bong_max']['C2'][0]:.3f} ({b['bong_max']['C2'][1]})"] for c, b in bang.items()]))
    md.append("\n## a. Nhiễu hạt (trung vị / p50) + cân bằng giữa ảnh (std mức giấy, std mực marker)\n")
    md.append(bang_md(["cấu hình"] + list(nen0) + ["C2 / khong", "std giấy", "std mực"],
                      [[c] + [f"{b['nhieu'][dk]:.4f}" for dk in nen0] + [f"×{b['nhieu']['C2'] / bang['khong']['nhieu']['C2']:.2f}",
                       f"{b['giay_std']:.1f}", f"{b['muc_std']:.1f}"] for c, b in bang.items()]))
    for lop in ("faint", "filled"):
        md.append(f"\n## b. {lop}/blank gộp, đặc trưng tuyệt đối: AUC (Δ so với khong, CI ghép cặp của Δ)\n")
        md.append(bang_md(["cấu hình"] + list(DIEU_KIEN),
                          [[c] + [f"{b[f'{lop}_{dk}']['auc']:.4f} ({b[f'{lop}_{dk}']['d_auc']:+.4f} "
                                  f"{ci(b[f'{lop}_{dk}']['ci_d_auc'])})" for dk in DIEU_KIEN] for c, b in bang.items()]))
        md.append(f"\n## b. {lop}/blank gộp, tuyệt đối: p1(lớp) − p99(blank) (Δ, CI ghép cặp)\n")
        md.append(bang_md(["cấu hình"] + list(DIEU_KIEN),
                          [[c] + [f"{b[f'{lop}_{dk}']['khoang']:+.4f} ({b[f'{lop}_{dk}']['d_khoang']:+.4f} "
                                  f"{ci(b[f'{lop}_{dk}']['ci_d_khoang'])})" for dk in DIEU_KIEN] for c, b in bang.items()]))
    md.append("\n## b. Theo hàng, local_darkness: giảm lớn nhất của hiệu tương đối (kể cả trong sai số) + số hàng giảm "
              f"quá {CA_BIEN_TD}\n")
    md.append(bang_md(["cấu hình", "faint Δ min (ảnh:hàng)", "faint giảm > biên", "filled Δ min (ảnh:hàng)",
                       "filled giảm > biên"],
                      [[c, f"{b['faint_d_td_min']:+.4f} ({b['faint_d_td_min_o']})", b["faint_so_giam_qua_bien"],
                        f"{b['filled_d_td_min']:+.4f} ({b['filled_d_td_min_o']})", b["filled_so_giam_qua_bien"]]
                       for c, b in bang.items()]))
    lat_all = [(c, x) for c, b in bang.items() for x in b["lat"]]
    if lat_all:
        md.append("\n## Cổng 1 – các hàng lật (tách -> không tách)\n")
        md.append(bang_md(["cấu hình", "hàng", "hiệu trước", "hiệu sau", "Δ tương đối", "ca biên"],
                          [[c, x["hang"], f"{x['truoc']:+.4f}", f"{x['sau']:+.4f}", f"{x['d_td']:+.4f}",
                            "CA BIÊN" if x["ca_bien"] else ""] for c, x in lat_all]))
    md.append("\n## c. Trang D: tương phản nét TV, nét/nhiễu TV, std mức nét giữa 10 trang\n")
    md.append(bang_md(["cấu hình", "tương phản", "nét/nhiễu", "std mức nét"],
                      [[c, f"{b['D_tp']:.3f}", f"{b['D_snr']:.1f}", f"{b['D_net_std']:.1f}"] for c, b in bang.items()]))
    h32 = sorted({(r["loai"], r["hang"]) for r in o0 if r["anh"] == "0032_C4"},
                 key=lambda k: -doc[("0032_C4",) + k])[:10]
    md.append("\n## 0032_C4 – 10 hàng có độ dốc nền trong hàng lớn nhất (gần mép bóng; trên anh_nan), Δ hiệu tương đối "
              "local (faint nếu hàng có faint, không thì filled)\n")
    Hc = {c: {(r["anh"], r["loai"], r["hang"], r["lop"]): r for r in K[c]["hang"]} for c in ds_cach}
    dong = []
    for lo, hg in h32:
        lop = "faint" if ("0032_C4", lo, hg, "faint") in H0 else "filled"
        k = ("0032_C4", lo, hg, lop)
        if k not in H0:
            continue
        dong.append([f"{hg} ({lop})", f"{doc[('0032_C4', lo, hg)]:.3f}", f"{H0[k]['td_local']:+.3f}"]
                    + [f"{Hc[c][k]['td_local'] - H0[k]['td_local']:+.3f}" for c in ds_cach if c != "khong"])
    md.append(bang_md(["hàng", "dốc nền", "td khong"] + [c for c in ds_cach if c != "khong"], dong))
    (OUT / "so_sanh.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "so_sanh.json").write_text(json.dumps({"qua": qua, "tot": tot, "hoa": hoa, "chon": chon, "bang": bang},
                                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n".join(md))
    print(f"\n-> {OUT / 'so_sanh.md'}")


XEM_B_TRANG = ("0032_C4", "0010_C2", "0019_C3", "0028_C4", "D007")
XEM_B_HANG = [("0019_C3", ("q", 30)), ("0019_C4", ("q", 30)), ("0033_C2", ("q", 4)), ("0034_C2", ("q", 7)),
              ("0028_C4", ("sbd", 0)), ("0032_C4", ("q", 32))]


def cmd_xem_b(a) -> None:
    tn = nap_tai_nguyen()
    xs = {x.ten: x for x in list_images("dev")}
    thu = OUT / "xem_b"
    the = []
    ds = list(CACH)
    for ten in XEM_B_TRANG:
        x = xs[ten]
        anh = anh_nan_v(x)
        L = tn["layout"][x.loai]
        o = []
        for c in ds:
            ghi_jpg(thu / f"{ten}_{c}.jpg", CACH[c](anh, L), rong=500, q=80)
            o.append(f"<figure><img src='xem_b/{ten}_{c}.jpg' class=trang><figcaption>{c}</figcaption></figure>")
        the.append(f"<h3>{ten} – cả trang</h3>{''.join(o)}")
    for ten, it in XEM_B_HANG:
        x = xs[ten]
        anh = anh_nan_v(x)
        L = tn["layout"]["phieu"]
        dx, dy = tinh_dich(anh, L, tn["mau"]["phieu"])[it]
        x0, y0, x1, y1 = item_box(L, it)
        o = []
        for c in ds:
            cat = CACH[c](anh, L)[max(0, y0 + dy):y1 + dy, max(0, x0 + dx):x1 + dx]
            ghi_jpg(thu / f"hang_{ten}_{it[0]}{it[1]}_{c}.jpg", cat, rong=2000, q=92)
            o.append(f"<figure><img src='xem_b/hang_{ten}_{it[0]}{it[1]}_{c}.jpg' class=hang><figcaption>{c}"
                     f"</figcaption></figure>")
        the.append(f"<h3>{ten} – {it[0]} {it[1]} (cắt đúng độ phân giải)</h3>{''.join(o)}")
    so = (OUT / "so_sanh.md").read_text(encoding="utf-8") if (OUT / "so_sanh.md").exists() else ""
    (OUT / "xem_b.html").write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Chuẩn hoá – trước/sau</title><style>body{{font-family:sans-serif;margin:16px}}
figure{{display:inline-block;margin:4px;vertical-align:top}}img.trang{{width:250px}}img.hang{{height:150px}}
img{{border:1px solid #999}}pre{{white-space:pre-wrap;font-size:12px}}</style></head><body>
<h2>Bước 5 dừng B – anh_nan (khong) và 11 cấu hình</h2>{''.join(the)}<h2>so_sanh.md</h2><pre>{so}</pre></body></html>""",
                                    encoding="utf-8")
    print(f"-> {OUT / 'xem_b.html'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lenh", required=True)
    t = sub.add_parser("van-tay")
    t.add_argument("--ghi-de", action="store_true")
    sub.add_parser("mat-na")
    sub.add_parser("tu-kiem")
    t = sub.add_parser("khao-sat")
    t.add_argument("--cach", nargs="+", default=list(CACH), choices=list(CACH))
    sub.add_parser("so-sanh")
    sub.add_parser("xem-b")
    t = sub.add_parser("so-anh-nan")
    t.add_argument("--phuong-phap", default="v5_chuan_hoa", choices=["v5_chuan_hoa", "v6_api"])
    a = ap.parse_args()
    {"van-tay": cmd_van_tay, "mat-na": cmd_mat_na, "tu-kiem": cmd_tu_kiem, "khao-sat": cmd_khao_sat,
     "so-sanh": cmd_so_sanh, "xem-b": cmd_xem_b, "so-anh-nan": cmd_so_anh_nan}[a.lenh](a)


if __name__ == "__main__":
    main()
