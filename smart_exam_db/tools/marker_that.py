"""
marker_that.py - Vị trí "marker thật" trên ảnh dev (Tuần 4, Bước 3a – docs/ke_hoach_tuan4.md).

Dùng để đo khâu TÌM / CHỌN marker của preprocessing tách bạch nhau (Bước 3b, 3c): marker thật có nằm
trong danh sách ứng viên không, đứng hạng mấy. Không phải phương pháp nắn ảnh, không dùng trong preprocessing.py.

Nguồn marker thật (cột `nguon` của marker_that_dev.csv):
  - align_cu_dung : ảnh mà align_cu nắn ĐÚNG (data/_eval/align_cu/truth_dev.csv) -> 4 điểm find_markers() cũ
                    chọn chính là 4 marker thật (ảnh nắn đúng ⇒ 4 điểm đó chiếu đúng 4 tâm marker).
  - mat           : các ảnh còn lại (align_cu nắn sai) -> người dùng chọn bằng mắt trên HTML (de-xuat),
                    trong số ứng viên tìm bằng bộ lọc RẤT LỎNG bên dưới; máy chỉ đề xuất sẵn 4 ứng viên.

Chạy (từ thư mục smart_exam_db/):
  python tools/marker_that.py de-xuat     # -> data/_eval/marker_that/xac_nhan.html + xac_nhan.csv
  (mở HTML, điền cột `chon` trong xac_nhan.csv: "ok" = đồng ý đề xuất, hoặc 4 số thứ tự ứng viên)
  python tools/marker_that.py chot        # -> data/_eval/marker_that/marker_that_dev.csv (78 ảnh)
  python tools/marker_that.py ung-vien --bo-loc cu   # số "trước": bộ lọc của find_markers() cũ
Chỉ ghi vào data/_eval/marker_that/, không đụng data/raw/, data/raw_digits/.
"""
import argparse
import csv
import html
import itertools
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_preprocessing import EVAL_DIR, ghi_jpg, list_images  # noqa: E402
from check_layout import find_markers  # noqa: E402  (eval_preprocessing đã thêm answer_sheet/ vào sys.path)
from cv_engine.preprocessing import load_image, tim_ung_vien_marker  # noqa: E402

OUT = EVAL_DIR / "marker_that"
# Bộ lọc ứng viên CHO VIỆC GÁN NHÃN – cố ý rất lỏng (để marker méo/xa vẫn lọt), không phải bộ lọc của v3.
# Căn cứ (khảo sát 03/10/2026, 236 marker thật của 59 ảnh align_cu đúng): độ vuông 0,83–1,01, độ đặc 0,96–1,01,
# diện tích 4,8e-4–1,3e-3 ảnh; nhưng ở C3 marker phía xa chỉ ~2,9e-4 ảnh và cạnh ngắn/dài ~0,6.
NGUONG_MUC = 0.5          # điểm ảnh tối hơn 50% nền giấy cục bộ = mực
VUONG_MIN = 0.70          # diện tích / diện tích minAreaRect (ô vuông ~0,9–1,0; ô tròn ~π/4 = 0,785)
DAC_MIN = 0.85            # diện tích / diện tích bao lồi
DT_MIN, DT_MAX = 1e-4, 5e-3   # diện tích / diện tích ảnh
TOP_DOAN = 12             # máy đoán 4 marker trong 12 ứng viên vuông nhất
GHI_CHU_ANH = {
    "0013_C2": "Có tờ khác lọt khung – chọn marker của tờ CHÍNH (tờ 0013).",
    "0018_C2": "Có tờ khác lọt khung – chọn marker của tờ CHÍNH (tờ 0018).",
    "0021_C2": "Có tờ khác lọt khung – chọn marker của tờ CHÍNH (tờ 0021).",
    "0006_C2": "Ảnh nằm ngang – chỉ cần đúng 4 ô đen (thứ tự góc không quan trọng).",
    "0006_C3": "Ảnh nằm ngang – chỉ cần đúng 4 ô đen (thứ tự góc không quan trọng).",
}


def mat_na_3a(gray: np.ndarray) -> np.ndarray:
    """Mặt nạ mực của bộ lọc lỏng 3a: max cục bộ cửa sổ max(H, W)/80 (~51 px) rồi làm mượt max(H, W)/20."""
    H, W = gray.shape
    k = max(H, W) // 20 | 1
    nen = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_RECT, (k // 4 | 1, k // 4 | 1)))   # max cục bộ
    nen = cv2.GaussianBlur(nen, (k, k), 0)
    return (gray.astype(np.float32) < NGUONG_MUC * np.maximum(nen, 1)).astype(np.uint8)


def ung_vien(gray: np.ndarray) -> list[dict]:
    """Mọi vết mực đặc, gần vuông (lỏng). Chuẩn hoá theo nền giấy cục bộ để ảnh tối (C2) / bóng không ảnh hưởng.
    Trả về danh sách xếp theo độ vuông giảm dần; 'so' = số thứ tự (1, 2, ...) dùng trong HTML/CSV."""
    H, W = gray.shape
    muc = mat_na_3a(gray)
    n, lab, st, ct = cv2.connectedComponentsWithStats(muc, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not DT_MIN * H * W <= a <= DT_MAX * H * W:
            continue
        cnts, _ = cv2.findContours((lab[y:y + h, x:x + w] == i).astype(np.uint8), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_NONE)
        c = max(cnts, key=cv2.contourArea)
        _, (rw, rh), _ = cv2.minAreaRect(c)
        vuong = a / max(rw * rh, 1)
        dac = a / max(cv2.contourArea(cv2.convexHull(c)), 1)
        if vuong < VUONG_MIN or dac < DAC_MIN:
            continue
        out.append({"x": float(ct[i][0]), "y": float(ct[i][1]), "dien_tich": int(a), "vuong": float(vuong),
                    "dac": float(dac), "canh": float(min(rw, rh) / max(rw, rh, 1)),
                    "cham_mep": int(x == 0 or y == 0 or x + w == W or y + h == H)})
    out.sort(key=lambda u: -u["vuong"])
    for s, u in enumerate(out, 1):
        u["so"] = s
    return out


def theo_vong(pts: np.ndarray) -> np.ndarray:
    """Sắp 4 điểm theo góc quanh trọng tâm (để kiểm tra lồi / tính diện tích)."""
    c = pts.mean(axis=0)
    return pts[np.argsort(np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0]))]


def doan(uv: list[dict], shape) -> list[int]:
    """Máy ĐOÁN 4 marker (chỉ để điền sẵn cho người xem, không phải kết luận): trong TOP_DOAN ứng viên vuông
    nhất, bộ 4 tạo tứ giác lồi có tổng độ vuông lớn nhất (diện tích tứ giác chỉ để phân xử khi gần bằng)."""
    top = uv[:TOP_DOAN]
    best, best_s = [], -1.0
    for bo in itertools.combinations(top, 4):
        q = theo_vong(np.array([[u["x"], u["y"]] for u in bo], np.float32))
        if not cv2.isContourConvex(q.reshape(-1, 1, 2)):
            continue
        s = sum(u["vuong"] for u in bo) + 0.1 * cv2.contourArea(q) / (shape[0] * shape[1])
        if s > best_s:
            best, best_s = [u["so"] for u in bo], s
    return sorted(best)


def ve(gray, uv, chon, max_w) -> np.ndarray:
    f = max_w / gray.shape[1]
    img = cv2.cvtColor(cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
    for u in uv:
        p = (round(u["x"] * f), round(u["y"] * f))
        r = max(6, round(np.sqrt(u["dien_tich"]) * f * 0.9))
        mau, day = ((0, 0, 230), 3) if u["so"] in chon else ((230, 120, 0), 1)
        cv2.circle(img, p, r, mau, day)
        cv2.putText(img, str(u["so"]), (p[0] + r + 2, p[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5 if max_w < 1200 else 0.8,
                    mau, 2 if u["so"] in chon else 1, cv2.LINE_AA)
    return img


def cat_zoom(gray, u, cao=140) -> np.ndarray:
    s = max(30, int(np.sqrt(u["dien_tich"]) * 1.6))
    x0, y0 = max(0, int(u["x"]) - s), max(0, int(u["y"]) - s)
    p = gray[y0:int(u["y"]) + s, x0:int(u["x"]) + s]
    return cv2.resize(p, (round(p.shape[1] * cao / p.shape[0]), cao), interpolation=cv2.INTER_AREA)


# ============================================================================ lệnh de-xuat
def cmd_de_xuat(a) -> None:
    truth = {r["anh"]: r["phan_loai"] for r in
             csv.DictReader((EVAL_DIR / "align_cu" / "truth_dev.csv").open(encoding="utf-8-sig"))}
    (OUT / "anh").mkdir(parents=True, exist_ok=True)
    rows_uv, can_xem, kiem_doan = [], [], []
    for anh in list_images("dev"):
        g = load_image(anh.duong_dan)
        uv = ung_vien(g)
        for u in uv:
            rows_uv.append({"anh": anh.ten, **u})
        de_xuat = doan(uv, g.shape)
        if truth[anh.ten] == "dung":
            # kiểm tra cách đoán trên ảnh đã biết đáp án: 4 điểm align_cu -> số ứng viên gần nhất (≤ 5 px)
            that = []
            for mx, my in find_markers(g):
                d = [np.hypot(u["x"] - mx, u["y"] - my) for u in uv]
                that.append(uv[int(np.argmin(d))]["so"] if d and min(d) <= 5 else None)
            kiem_doan.append((anh.ten, sorted(that, key=lambda s: s or 0), de_xuat))
        else:
            can_xem.append((anh, g, uv, de_xuat))
        print(f"{anh.ten:8s} {len(uv):3d} ứng viên; đoán {de_xuat}" + ("" if truth[anh.ten] == "dung" else "  <- cần xem"))

    with (OUT / "ung_vien_dev.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["anh", "so", "x", "y", "dien_tich", "vuong", "dac", "canh", "cham_mep"])
        w.writeheader()
        for r in rows_uv:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})

    khop = [t for t in kiem_doan if t[1] == t[2]]
    thieu = [t for t in kiem_doan if None in t[1]]
    print(f"\nKiểm tra cách đoán trên {len(kiem_doan)} ảnh align_cu đúng: đoán trúng cả 4 marker {len(khop)}/{len(kiem_doan)}"
          + "".join(f"\n  {t[0]}: thật {t[1]}, đoán {t[2]}" for t in kiem_doan if t[1] != t[2]))
    if thieu:
        sys.exit("LỖI: marker thật (align_cu) không có trong ứng viên lỏng: " + ", ".join(t[0] for t in thieu))

    body = []
    for anh, g, uv, de_xuat in can_xem:
        ghi_jpg(OUT / "anh" / f"{anh.ten}.jpg", ve(g, uv, de_xuat, 900), q=85)
        ghi_jpg(OUT / "anh" / f"{anh.ten}_lon.jpg", ve(g, uv, de_xuat, 2000), q=85)
        zoom = []
        for s in de_xuat:
            u = uv[s - 1]
            ghi_jpg(OUT / "anh" / f"{anh.ten}_{s}.jpg", cat_zoom(g, u), q=90)
            zoom.append(f'<figure><img src="anh/{anh.ten}_{s}.jpg"><figcaption>số {s}<br>vuông {u["vuong"]:.2f}'
                        f'<br>{u["dien_tich"]} px²</figcaption></figure>')
        bang = "".join(f"<tr><td>{u['so']}</td><td>{u['x']:.0f}, {u['y']:.0f}</td><td>{u['vuong']:.2f}</td>"
                       f"<td>{u['dien_tich']}</td><td>{u['canh']:.2f}</td><td>{'có' if u['cham_mep'] else ''}</td></tr>"
                       for u in uv[:20])
        note = GHI_CHU_ANH.get(anh.ten, "")
        body.append(f"""<section id="{anh.ten}"><h3>{anh.ten} <small>({anh.dieu_kien}) – máy đoán: <b>{' '.join(map(str, de_xuat))}</b></small></h3>
{f'<p class="note">⚠ {html.escape(note)}</p>' if note else ''}
<div class="row"><a href="anh/{anh.ten}_lon.jpg" target="_blank"><img src="anh/{anh.ten}.jpg" width="600"></a>
<div><div class="zoom">{''.join(zoom)}</div>
<table class="uv"><tr><th>số</th><th>tâm (px)</th><th>vuông</th><th>px²</th><th>cạnh ngắn/dài</th><th>chạm mép</th></tr>{bang}</table>
<small>(20 ứng viên vuông nhất; bấm ảnh trái để phóng to)</small></div></div></section>""")
    (OUT / "xac_nhan.html").write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Marker thật – {len(can_xem)} ảnh cần xác nhận</title>
<style>body{{font-family:sans-serif;margin:16px;max-width:1300px}} section{{border-bottom:2px solid #ccc;padding:8px 0}}
.row{{display:flex;gap:16px;align-items:flex-start}} .zoom{{display:flex;gap:8px}} figure{{margin:0;text-align:center;font-size:12px}}
.note{{background:#fff3cd;padding:4px 8px}} table.uv{{font-size:12px;border-collapse:collapse;margin-top:8px}}
table.uv td,table.uv th{{border:1px solid #ddd;padding:1px 6px;text-align:right}} img{{border:1px solid #ccc}}</style></head><body>
<h2>Bước 3a – xác nhận 4 marker thật trên {len(can_xem)} ảnh mà align_cu nắn sai</h2>
<p><span style="color:#e00"><b>Đỏ đậm</b></span> = 4 ứng viên máy đoán (chưa tin – chỉ điền sẵn);
<span style="color:#07e">xanh</span> = các ứng viên khác (số thứ tự theo độ vuông giảm dần). Ở giữa: phóng to 4 ứng viên đoán.<br>
Điền cột <code>chon</code> trong <code>xac_nhan.csv</code>: <code>ok</code> nếu cả 4 ô đỏ là 4 marker của tờ chính;
nếu không, ghi 4 số đúng, cách nhau bởi dấu cách (vd <code>1 2 5 7</code>). Marker thật không có số nào → ghi
<code>thieu</code> và mô tả ở <code>ghi_chu</code>.<br>
Cách đoán được kiểm tra trước trên các ảnh đã biết đáp án (align_cu nắn đúng) – xem dòng cuối khi chạy lệnh.</p>
{''.join(body)}</body></html>""", encoding="utf-8")

    p = OUT / "xac_nhan.csv"
    if p.exists():
        print(f"\nGIỮ NGUYÊN {p} (đã có – có thể chứa lựa chọn của người dùng).")
    else:
        with p.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["anh", "dieu_kien", "de_xuat", "chon", "ghi_chu"])
            for anh, _, _, de_xuat in can_xem:
                w.writerow([anh.ten, anh.dieu_kien, " ".join(map(str, de_xuat)), "", GHI_CHU_ANH.get(anh.ten, "")])
    print(f"\nĐã ghi {OUT}: ung_vien_dev.csv, xac_nhan.html, xac_nhan.csv, anh/  ({len(can_xem)} ảnh cần xác nhận)")


# ============================================================================ lệnh chot
def cmd_chot(a) -> None:
    """xac_nhan.csv (người dùng) + 4 điểm align_cu trên ảnh đúng -> marker_that_dev.csv. Dừng nếu còn ảnh chưa chọn."""
    truth = {r["anh"]: r["phan_loai"] for r in
             csv.DictReader((EVAL_DIR / "align_cu" / "truth_dev.csv").open(encoding="utf-8-sig"))}
    uv = {}
    for r in csv.DictReader((OUT / "ung_vien_dev.csv").open(encoding="utf-8-sig")):
        uv.setdefault(r["anh"], {})[int(r["so"])] = (float(r["x"]), float(r["y"]))
    xn = {r["anh"]: r for r in csv.DictReader((OUT / "xac_nhan.csv").open(encoding="utf-8-sig"))}
    rows, loi = [], []
    for anh in list_images("dev"):
        if truth[anh.ten] == "dung":
            pts, nguon, ghi_chu = [tuple(map(float, p)) for p in find_markers(load_image(anh.duong_dan))], "align_cu_dung", ""
        else:
            r = xn.get(anh.ten)
            chon = (r["chon"].strip().lower() if r else "")
            if chon == "ok":
                chon = r["de_xuat"]
            try:
                so = [int(s) for s in chon.split()]
            except ValueError:
                so = []
            if len(so) != 4 or len(set(so)) != 4 or any(s not in uv.get(anh.ten, {}) for s in so):
                loi.append(f"{anh.ten}: chon = {r['chon'] if r else '(thiếu dòng)'!r}")
                continue
            pts, nguon, ghi_chu = [uv[anh.ten][s] for s in so], "mat", r["ghi_chu"]
        q = theo_vong(np.array(pts, np.float32))
        rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "nguon": nguon,
                     **{f"{c}{i}": f"{q[i][j]:.2f}" for i in range(4) for j, c in enumerate("xy")}, "ghi_chu": ghi_chu})
    if loi:
        sys.exit(f"Còn {len(loi)} ảnh chưa chọn hợp lệ (cần 'ok' hoặc 4 số ứng viên khác nhau) – chưa ghi:\n  "
                 + "\n  ".join(loi))
    with (OUT / "marker_that_dev.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"Đã ghi {OUT / 'marker_that_dev.csv'}: {len(rows)} ảnh; nguồn {dict(Counter(r['nguon'] for r in rows))}")


# ============================================================================ lệnh ung-vien (đo khâu TÌM)
KHOP_PX = 10.0            # ứng viên cách tâm marker thật ≤ 10 px = tìm thấy (marker nhỏ nhất ~60 px cạnh, ảnh C3)


def ung_vien_cu(gray: np.ndarray) -> list[tuple[float, float]]:
    """Bản sao NGUYÊN VĂN bộ lọc của find_markers() trong answer_sheet/check_layout.py (dòng 99–118), chỉ bỏ bước
    chọn 'gần góc ảnh nhất' để lấy cả danh sách ứng viên. Tính đúng bản sao được kiểm tra trong cmd_ung_vien()."""
    th = cv2.adaptiveThreshold(cv2.GaussianBlur(gray, (5, 5), 0), 255,
                               cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 15)
    cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area_img = gray.shape[0] * gray.shape[1]
    cands = []
    for c in cnts:
        a = cv2.contourArea(c)
        if not (area_img * 0.00015 < a < area_img * 0.004):
            continue
        x, y, w, h = cv2.boundingRect(c)
        if not (0.7 < w / h < 1.4):
            continue
        hull = cv2.contourArea(cv2.convexHull(c))
        if hull == 0 or a / hull < 0.9:
            continue
        approx = cv2.approxPolyDP(c, 0.06 * cv2.arcLength(c, True), True)
        if len(approx) != 4:
            continue
        m = cv2.moments(c)
        cands.append((m["m10"] / m["m00"], m["m01"] / m["m00"]))
    return cands


def ung_vien_moi(gray: np.ndarray) -> list[tuple[float, float]]:
    """Bộ lọc của Bước 3b (cv_engine.preprocessing.tim_ung_vien_marker), đã xếp theo điểm giảm dần."""
    return [(u.x, u.y) for u in tim_ung_vien_marker(gray)]


BO_LOC = {"cu": ung_vien_cu, "moi": ung_vien_moi}
CA_RIENG = ["0034_C3", "0031_C3", "0013_C2", "0018_C2", "0021_C2", "0006_C2", "0006_C3", "0007_C3"]


def doc_marker_that() -> dict[str, np.ndarray]:
    return {r["anh"]: np.array([[float(r[f"x{i}"]), float(r[f"y{i}"])] for i in range(4)])
            for r in csv.DictReader((OUT / "marker_that_dev.csv").open(encoding="utf-8-sig"))}


def ghep(c: np.ndarray, pts: np.ndarray) -> list[int | None]:
    """Với mỗi marker thật: chỉ số ứng viên gần nhất nếu cách ≤ KHOP_PX, không thì None."""
    out = []
    for p in pts:
        d = np.hypot(*(c - p).T) if len(c) else np.array([np.inf])
        j = int(np.argmin(d))
        out.append(j if d[j] <= KHOP_PX else None)
    return out


def cmd_ung_vien(a) -> None:
    """Khâu TÌM: ảnh có đủ 4 marker thật trong danh sách ứng viên không, mỗi ảnh bao nhiêu ứng viên.
    Tách lỗi 'không tìm thấy' (marker thật không có trong danh sách) với 'chọn sai' (có đủ mà vẫn nắn sai).
    Bộ lọc trả danh sách đã xếp hạng ('moi') -> thêm hạng lớn nhất của marker thật (1 = đầu danh sách)."""
    from collections import defaultdict
    from time import perf_counter
    that = doc_marker_that()
    phan_loai = {r["anh"]: r["phan_loai"] for r in
                 csv.DictReader((EVAL_DIR / "align_cu" / "truth_dev.csv").open(encoding="utf-8-sig"))}
    f = BO_LOC[a.bo_loc]
    xep_hang = a.bo_loc != "cu"
    rows, chi_tiet = [], {}
    for anh in list_images("dev"):
        g = load_image(anh.duong_dan)
        t0 = perf_counter()
        c = np.array(f(g), np.float64).reshape(-1, 2)
        ms = 1000 * (perf_counter() - t0)
        hang = [None if j is None else j + 1 for j in ghep(c, that[anh.ten])]
        chi_tiet[anh.ten] = hang
        if a.bo_loc == "cu" and len(c) >= 4:     # kiểm tra bản sao: 4 điểm find_markers() phải nằm trong danh sách
            fm = find_markers(g)
            if max(np.min(np.hypot(*(c - p).T)) for p in fm) > 1e-3:
                sys.exit(f"LỖI: ung_vien_cu() không khớp find_markers() trên {anh.ten} – bản sao sai")
        d = [float(np.min(np.hypot(*(c - p).T))) if len(c) else np.inf for p in that[anh.ten]]
        tim = sum(x <= KHOP_PX for x in d)
        rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "so_ung_vien": len(c), "so_marker_tim_thay": tim,
                     "d_max_tim_thay_px": max([x for x in d if x <= KHOP_PX], default=float("nan")),
                     "hang_max": (max([h for h in hang if h], default=0) if xep_hang else ""),
                     "thoi_gian_ms": ms, "align_cu": phan_loai[anh.ten]})
    out = OUT / f"ung_vien_{a.bo_loc}_dev.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.2f}" if isinstance(v, float) else v) for k, v in r.items()})

    def dong(nhan, rs):
        du = [r for r in rs if r["so_marker_tim_thay"] == 4]
        n = np.array([r["so_ung_vien"] for r in rs])
        chon_sai = [r for r in du if r["align_cu"] != "dung"]
        hm = f" | hạng lớn nhất {max(r['hang_max'] for r in rs):3d}" if xep_hang else ""
        print(f"{nhan:6s} {len(rs):3d} ảnh | đủ 4 marker thật: {len(du):3d} ({100 * len(du) / len(rs):5.1f}%) | "
              f"ứng viên/ảnh TB {n.mean():6.1f}, trung vị {np.median(n):5.0f}, min {n.min():4d}, max {n.max():4d}{hm} | "
              f"đủ 4 mà align_cu vẫn sai: {len(chon_sai)}")
    nhom = defaultdict(list)
    for r in rows:
        nhom[r["dieu_kien"]].append(r)
    print(f"Bộ lọc '{a.bo_loc}', khớp ≤ {KHOP_PX:.0f} px (xa nhất trong các marker tìm thấy: "
          f"{np.nanmax([r['d_max_tim_thay_px'] for r in rows]):.2f} px)")
    for k in sorted(nhom):
        dong(k, nhom[k])
    dong("Tổng", rows)
    thieu = [r for r in rows if r["so_marker_tim_thay"] < 4]
    print("Ảnh thiếu marker thật (số tìm thấy/4): "
          + (", ".join(f"{r['anh']} {r['so_marker_tim_thay']}/4" for r in thieu) or "không"))
    ms = np.array([r["thoi_gian_ms"] for r in rows])
    print(f"Thời gian lọc/ảnh (không tính đọc ảnh): trung vị {np.median(ms):.0f} ms, max {ms.max():.0f} ms "
          f"({rows[int(ms.argmax())]['anh']})")
    if xep_hang:
        print("Hạng của 4 marker thật ở các ca nêu riêng (thứ tự góc như marker_that_dev.csv):")
        for ten in CA_RIENG:
            if ten in chi_tiet:
                print(f"  {ten}: {chi_tiet[ten]}")
    print(f"Đã ghi {out}")


# ============================================================================ lệnh khao-sat (căn cứ ngưỡng 3b)
def cat_hai_anh(gray, muc, u, cao=300) -> np.ndarray:
    """Ảnh gốc | mặt nạ mực quanh vết u (vùng = hộp bao nới 1 cạnh mỗi phía), ghép ngang."""
    x, y, w, h = u.hop
    s = max(w, h)
    x0, y0 = max(0, x - s), max(0, y - s)
    x1, y1 = min(gray.shape[1], x + w + s), min(gray.shape[0], y + h + s)
    a, b = gray[y0:y1, x0:x1], (1 - muc[y0:y1, x0:x1]) * 255
    f = cao / a.shape[0]
    a, b = (cv2.resize(m.astype(np.uint8), None, fx=f, fy=f, interpolation=cv2.INTER_NEAREST) for m in (a, b))
    return np.hstack([a, np.full((a.shape[0], 6), 128, np.uint8), b])


def uoc_luong_bi_cat(r: dict, T: list[dict]) -> None:
    """Marker r chạm mép: ước lượng % bị cắt từ tỉ lệ (diện tích, bề rộng) góc này / góc cùng hàng ở các ảnh
    cùng điều kiện không chạm mép (bỏ 0006 nằm ngang). Giả sử phần mất là một dải dọc theo mép ảnh (theo x)."""
    cung_hang = {0: 1, 1: 0, 2: 3, 3: 2}[r["goc"]]          # TL<->TR, BR<->BL (thứ tự theo_vong)
    theo_anh = {}
    for x in T:
        theo_anh.setdefault(x["anh"], {})[x["goc"]] = x
    ti_dt, ti_w = [], []
    for anh, m in theo_anh.items():
        if anh == r["anh"] or anh.startswith("0006") or m[r["goc"]]["dieu_kien"] != r["dieu_kien"] \
                or any(v["cham_mep"] for v in m.values()):
            continue
        ti_dt.append(m[r["goc"]]["dien_tich"] / m[cung_hang]["dien_tich"])
        ti_w.append(m[r["goc"]]["w"] / m[cung_hang]["w"])
    ban = theo_anh[r["anh"]][cung_hang]
    for ten, q in (("p10", 10), ("trung vị", 50), ("p90", 90)):
        dt_mong = ban["dien_tich"] * np.percentile(ti_dt, q)
        mat = 1 - r["dien_tich"] / dt_mong
        w_mong = ban["w"] * np.percentile(ti_w, q)
        # tâm thật lệch về phía mép: phần mất (tỉ lệ mat) có tâm cách tâm phần còn ~ (w_con + w_mat) / 2
        lech = max(mat, 0) * (r["w"] + max(w_mong - r["w"], 0)) / 2
        print(f"     ước lượng ({ten} của {len(ti_dt)} ảnh {r['dieu_kien']}): diện tích mong đợi {dt_mong:.0f} px² -> "
              f"bị cắt {100 * mat:.0f}%; bề rộng mong đợi {w_mong:.0f} px (còn {r['w']}) -> tâm centroid lệch ~{lech:.0f} px")


def cmd_khao_sat(a) -> None:
    """Phân bố đặc trưng của marker thật vs ứng viên khác (mọi vết mực qua lọc diện tích), ngưỡng + biên,
    số ứng viên khác bị loại nhờ RIÊNG từng ngưỡng, hạng theo các cách xếp. Chỉ dev. Ghi dac_trung_moi_dev.csv."""
    import cv_engine.preprocessing as pp
    from collections import defaultdict
    that = doc_marker_that()
    (OUT / "khao_sat").mkdir(parents=True, exist_ok=True)
    rows, thieu, canh_max = [], [], (0, "")
    luu = {}                                   # ảnh -> (đường dẫn, cỡ, vết mực) – đọc lại ảnh khi cần cắt
    for anh in list_images("dev"):
        g = load_image(anh.duong_dan)
        vets = pp.do_vet_muc(g)
        c = np.array([(u.x, u.y) for u in vets]).reshape(-1, 2)
        idx = ghep(c, that[anh.ten])
        if None in idx:
            thieu.append(f"{anh.ten} {4 - idx.count(None)}/4")
        goc = {j: k for k, j in enumerate(idx) if j is not None}
        for j, u in enumerate(vets):
            rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "marker": int(j in goc), "goc": goc.get(j, ""),
                         "x": u.x, "y": u.y, "dien_tich": u.dien_tich, "dt_ti_le": u.dien_tich / g.size,
                         "w": u.hop[2], "h": u.hop[3], "dac": u.dac, "canh": u.canh, "tu_giac": u.tu_giac,
                         "vuong": u.vuong, "muc_vien": u.muc_vien, "den_trong": u.den_trong,
                         "cham_mep": int(u.cham_mep), "diem": u.diem})
            if j in goc and max(u.hop[2:]) > canh_max[0]:
                canh_max = (max(u.hop[2:]), anh.ten)
        luu[anh.ten] = (anh.duong_dan, g.shape, vets)
        print(f"{anh.ten:8s} {len(vets):4d} vết mực, marker thật ghép được {4 - idx.count(None)}/4", flush=True)
    with (OUT / "dac_trung_moi_dev.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.5f}" if isinstance(v, float) else v) for k, v in r.items()})

    T = [r for r in rows if r["marker"]]
    O = [r for r in rows if not r["marker"]]
    print(f"\n=== Ghép marker thật (≤ {KHOP_PX:.0f} px) với vết mực: {len(T)}/{4 * len(that)}; thiếu: {', '.join(thieu) or 'không'}")

    # --- 1. cửa sổ nền
    Hmax = max(max(v[1]) for v in luu.values())
    k_eff = (Hmax // pp.NEN_CUA_SO // pp.NEN_THU_NHO | 1) * pp.NEN_THU_NHO
    print(f"\n=== Cửa sổ nền: cạnh hộp bao marker thật lớn nhất {canh_max[0]} px ({canh_max[1]}). "
          f"Cửa sổ max mới {k_eff} px -> cửa sổ/marker = {k_eff / canh_max[0]:.2f}. "
          f"(Bộ lọc lỏng 3a: max 51 px -> {51 / canh_max[0]:.2f}; làm mượt 201 px)")

    # --- 2. phân bố
    print("\n=== Phân bố đặc trưng (marker thật n = %d | ứng viên khác n = %d)" % (len(T), len(O)))
    for k in ("dt_ti_le", "dac", "canh", "tu_giac", "vuong", "muc_vien", "den_trong"):
        t = np.array([r[k] for r in T]); o = np.array([r[k] for r in O])
        xau = (T[int(t.argmax())] if k in ("muc_vien", "den_trong") else T[int(t.argmin())])["anh"]
        print(f"{k:9s} thật: min {t.min():.4g} p1 {np.percentile(t, 1):.4g} p50 {np.median(t):.4g} p99 "
              f"{np.percentile(t, 99):.4g} max {t.max():.4g} (xấu nhất {xau}) | khác: p5 {np.percentile(o, 5):.4g} "
              f"p50 {np.median(o):.4g} p95 {np.percentile(o, 95):.4g} max {o.max():.4g}")

    # --- 3. ngưỡng: biên + loại riêng
    nguong = [("dac", pp.DAC_MIN), ("canh", pp.CANH_MIN), ("tu_giac", pp.TU_GIAC_MIN)]
    print("\n=== Ngưỡng lọc (≥): xấu nhất marker thật, biên, số marker thật trong 0,05 trên ngưỡng, "
          "ứng viên khác bị loại nhờ RIÊNG ngưỡng này (đã áp các ngưỡng còn lại)")
    for k, v in nguong:
        t = np.array([r[k] for r in T])
        xau = T[int(t.argmin())]["anh"]
        con_lai = [r for r in O if all(r[k2] >= v2 for k2, v2 in nguong if k2 != k)]
        loai = sum(r[k] < v for r in con_lai)
        print(f"{k:8s} ≥ {v:.2f}: xấu nhất {t.min():.3f} ({xau}), biên {t.min() - v:+.3f}, sát (< ngưỡng + 0,05): "
              f"{int((t < v + 0.05).sum())} | loại riêng {loai}/{len(con_lai)} ({100 * loai / max(len(con_lai), 1):.1f}%)")
    t_v = max(r["muc_vien"] for r in T)
    qua = [r for r in O if all(r[k] >= v for k, v in nguong)]
    print(f"(thử, KHÔNG áp) muc_vien ≤ {t_v + 0.1:.2f}: xấu nhất {t_v:.3f} "
          f"({max(T, key=lambda r: r['muc_vien'])['anh']}), biên 0,100 | loại riêng "
          f"{sum(r['muc_vien'] > t_v + 0.1 for r in qua)}/{len(qua)}")
    dt = np.array([r["dt_ti_le"] for r in T])
    print(f"diện tích {pp.DT_MIN:g}–{pp.DT_MAX:g} ảnh: marker thật {dt.min():.3g}–{dt.max():.3g} -> biên "
          f"×{dt.min() / pp.DT_MIN:.1f} dưới, ×{pp.DT_MAX / dt.max():.1f} trên (loại riêng: không đếm – vết vụn chưa tính đặc trưng)")
    print(f"ngưỡng mực {pp.MUC_TI_LE}: den_trong marker thật xấu nhất {max(r['den_trong'] for r in T):.3f} -> biên "
          f"{pp.MUC_TI_LE - max(r['den_trong'] for r in T):+.3f}")

    # --- 4. xếp hạng: hạng lớn nhất của marker thật theo từng cách xếp, trong các vết qua lọc
    cach = {"vuong (cũ)": lambda r: r["vuong"], "tu_giac": lambda r: r["tu_giac"],
            "diem = tu_giac×(1−muc_vien)": lambda r: r["diem"],
            "diem×(1−den_trong)": lambda r: r["diem"] * (1 - r["den_trong"])}
    theo_anh = defaultdict(list)
    for r in rows:
        if all(r[k] >= v for k, v in nguong):
            theo_anh[r["anh"]].append(r)
    print("\n=== Hạng lớn nhất của marker thật (trong các vết qua lọc), theo điều kiện chụp")
    dk_anh = {r["anh"]: r["dieu_kien"] for r in rows}
    for ten, fn in cach.items():
        hm = defaultdict(int); te = (0, "")
        for anh, rs in theo_anh.items():
            xs = sorted(rs, key=lambda r: -fn(r))
            h = max(i + 1 for i, r in enumerate(xs) if r["marker"])
            hm[dk_anh[anh]] = max(hm[dk_anh[anh]], h)
            te = max(te, (h, anh))
        print(f"{ten:30s} " + "  ".join(f"{d} {hm[d]}" for d in sorted(hm)) + f"  | tổng {te[0]} ({te[1]})")

    # --- 5. ca riêng: marker thật + vết khác điểm cao nhất
    print("\n=== Ca nêu riêng: (hạng theo diem) marker thật | 3 vết KHÁC điểm cao nhất")
    for ten in CA_RIENG:
        xs = sorted(theo_anh[ten], key=lambda r: -r["diem"])
        mk = [f"#{i + 1} g{r['goc']} tg {r['tu_giac']:.3f} vien {r['muc_vien']:.3f} den {r['den_trong']:.2f}"
              + (" CHẠM MÉP" if r["cham_mep"] else "") for i, r in enumerate(xs) if r["marker"]]
        kh = [f"#{i + 1} ({r['x']:.0f},{r['y']:.0f}) tg {r['tu_giac']:.3f} vien {r['muc_vien']:.3f} "
              f"den {r['den_trong']:.2f} {r['dien_tich']}px²" for i, r in enumerate(xs) if not r["marker"]][:3]
        print(f"{ten}: {len(xs)} ứng viên\n   thật: " + " | ".join(mk) + "\n   khác: " + " | ".join(kh))

    # --- 6. ảnh cắt: vuông kém nhất, vành nhiều mực nhất, marker chạm mép
    def cat(r, ten_file, ghi):
        duong_dan, _, vets = luu[r["anh"]]
        g = load_image(duong_dan)
        u = next(v for v in vets if abs(v.x - r["x"]) < 1e-3 and abs(v.y - r["y"]) < 1e-3)
        muc = (g.astype(np.float32) / np.maximum(pp.uoc_luong_nen(g), 1) < pp.MUC_TI_LE).astype(np.uint8)
        ghi_jpg(OUT / "khao_sat" / ten_file, cat_hai_anh(g, muc, u), q=92)
        print(f"  {ghi}: {r['anh']} góc {r['goc']} hộp {u.hop} {u.dien_tich} px² vuong {u.vuong:.3f} "
              f"tu_giac {u.tu_giac:.3f} dac {u.dac:.3f} vien {u.muc_vien:.3f} -> khao_sat/{ten_file}")
    print("\n=== Ảnh cắt (trái: ảnh gốc, phải: mặt nạ mực đen) trong data/_eval/marker_that/khao_sat/")
    r = min(T, key=lambda r: r["vuong"]); cat(r, f"{r['anh']}_vuong_kem_nhat.jpg", "vuông kém nhất")
    r = max(T, key=lambda r: r["muc_vien"]); cat(r, f"{r['anh']}_vien_nhieu_muc_nhat.jpg", "vành nhiều mực nhất")
    for r in [r for r in T if r["cham_mep"]]:
        cat(r, f"{r['anh']}_cham_mep_g{r['goc']}.jpg", "chạm mép")
        cung = [x for x in T if x["anh"] == r["anh"]]
        print("     4 marker cùng ảnh: " + ", ".join(f"g{x['goc']} {x['dien_tich']}px² hộp {x['w']}×{x['h']} "
                                                    f"tâm ({x['x']:.0f},{x['y']:.0f})" for x in cung))
        uoc_luong_bi_cat(r, T)

    # --- 7. 0034_C3: marker gần máy (lớn nhất) – mặt nạ cửa sổ cũ (3a) vs mới
    r = max((x for x in T if x["anh"] == "0034_C3"), key=lambda x: x["dien_tich"])
    duong_dan, _, vets = luu["0034_C3"]
    g = load_image(duong_dan)
    cu = min(ung_vien(g), key=lambda u: np.hypot(u["x"] - r["x"], u["y"] - r["y"]))
    u = next(v for v in vets if abs(v.x - r["x"]) < 1e-3 and abs(v.y - r["y"]) < 1e-3)
    moi = (g.astype(np.float32) / np.maximum(pp.uoc_luong_nen(g), 1) < pp.MUC_TI_LE).astype(np.uint8)
    a_cu, a_moi = cat_hai_anh(g, mat_na_3a(g), u), cat_hai_anh(g, moi, u)
    ghi_jpg(OUT / "khao_sat" / "0034_C3_marker_gan_cu_moi.jpg",
            np.hstack([a_cu, np.full((a_cu.shape[0], 6), 128, np.uint8), a_moi[:, a_cu.shape[1] // 2 + 3:]]), q=92)
    print(f"\n=== 0034_C3 marker gần máy g{r['goc']} (ảnh gốc | mặt nạ 3a | mặt nạ mới -> khao_sat/0034_C3_marker_gan_cu_moi.jpg)\n"
          f"  cửa sổ 3a : {cu['dien_tich']} px², vuong {cu['vuong']:.3f}, dac {cu['dac']:.3f}, tâm ({cu['x']:.1f},{cu['y']:.1f})\n"
          f"  cửa sổ mới: {u.dien_tich} px², vuong {u.vuong:.3f}, dac {u.dac:.3f}, tu_giac {u.tu_giac:.3f}, "
          f"tâm ({u.x:.1f},{u.y:.1f}) -> tâm lệch {np.hypot(u.x - cu['x'], u.y - cu['y']):.1f} px")
    print(f"\nĐã ghi {OUT / 'dac_trung_moi_dev.csv'} ({len(rows)} vết mực)")


# ============================================================================ Bước 3c: bộ 4 theo hình học
def nap_layout() -> dict:
    import json
    from eval_preprocessing import ANSWER_SHEET
    return json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))


def cmd_khao_sat_bo_4(a) -> None:
    """Căn cứ ngưỡng K2–K4: mọi bộ 4 trong top-K ứng viên của 78 ảnh dev; bộ 'thật' = đúng 4 marker của
    marker_that_dev.csv. Báo xấu nhất / biên / loại riêng, cách gán (xoay) được chọn, K4 cách gán tốt nhất vs cặp
    vuông góc. Ghi data/_eval/marker_that/bo_4_dev.csv."""
    import cv_engine.preprocessing as pp
    from collections import Counter, defaultdict
    layout, that = nap_layout(), doc_marker_that()
    rows, lech_tam = [], []
    for anh in list_images("dev"):
        g = load_image(anh.duong_dan)
        uv = pp.tim_ung_vien_marker(g)[:pp.K_UNG_VIEN]
        idx = ghep(np.array([(u.x, u.y) for u in uv]).reshape(-1, 2), that[anh.ten])
        bo_that = set(idx) if None not in idx else None
        for j in idx:
            if j is not None:
                lech_tam.append(np.hypot(uv[j].x - uv[j].tam[0], uv[j].y - uv[j].tam[1]))
        for bo in itertools.combinations(range(len(uv)), 4):
            ket = pp.do_bo_4([uv[i] for i in bo], layout)
            gan, vg = pp.chon_cach_gan(ket)
            cg = ket["cach_gan"]
            rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "bo": " ".join(map(str, bo)),
                         "that": int(bo_that == set(bo)), "loi": int(ket["loi"]), "phoi_canh": ket["phoi_canh"],
                         "xoay": gan["xoay"], "co_min": gan["co_min"], "co_max": gan["co_max"], "dinh_mm": gan["dinh_mm"],
                         "dinh_mm_vuong_goc": vg,
                         "lech_doi_xung_mm": abs(cg[gan["xoay"]]["dinh_mm"] - cg[(gan["xoay"] + 2) % 4]["dinh_mm"]),
                         "cham_mep": int(any(uv[i].cham_mep for i in bo))})
        print(f"{anh.ten:8s} {len(uv)} ứng viên, {sum(r['anh'] == anh.ten for r in rows)} bộ 4", flush=True)
    ghi_csv_moi(OUT / "bo_4_dev.csv", rows)

    T = [r for r in rows if r["that"]]
    O = [r for r in rows if not r["that"]]
    print(f"\n=== {len(T)} bộ thật / {len(set(r['anh'] for r in rows))} ảnh; {len(O)} bộ khác")
    print(f"Tâm chéo vs centroid (marker thật): trung vị {np.median(lech_tam):.2f} px, max {max(lech_tam):.2f} px")
    print(f"K1 lồi: bộ thật {sum(r['loi'] for r in T)}/{len(T)}; bộ khác lồi {sum(r['loi'] for r in O)}/{len(O)}")
    print(f"Cách gán chọn cho bộ thật: {dict(Counter(r['xoay'] for r in T))} – xoay ≠ 0: "
          + ", ".join(f"{r['anh']} ({r['xoay']})" for r in T if r["xoay"] != 0))
    print(f"Lệch K4 giữa cách gán r và r+2 (đối xứng 180°) của bộ thật: max {max(r['lech_doi_xung_mm'] for r in T):.3f} mm")

    tieu_chi = [("phoi_canh", "min", pp.PHOI_CANH_MIN), ("co_min", "min", pp.CO_MIN), ("co_max", "max", pp.CO_MAX),
                ("dinh_mm", "max", pp.DINH_MAX_MM)]
    qua = lambda r, k, h, v: (r[k] >= v) if h == "min" else (r[k] <= v)
    print("\n=== Ngưỡng (xấu nhất của bộ thật, biên, bộ khác (lồi) bị loại nhờ RIÊNG tiêu chí này)")
    for k, h, v in tieu_chi:
        xs = [r[k] for r in T]
        xau = (min if h == "min" else max)(T, key=lambda r: r[k])
        con = [r for r in O if r["loi"] and all(qua(r, k2, h2, v2) for k2, h2, v2 in tieu_chi if k2 != k)]
        loai = sum(not qua(r, k, h, v) for r in con)
        lo = [r for r in O if r["loi"]]
        mot_minh = sum(not qua(r, k, h, v) for r in lo)
        tot_nhat_khac = (max if h == "min" else min)(lo, key=lambda r: r[k])
        bien = (xau[k] - v) if h == "min" else (v - xau[k])
        ti = f" (×{xau[k] / v:.2f})" if h == "min" else f" (×{v / xau[k]:.2f})"
        print(f"{k:10s} {'≥' if h == 'min' else '≤'} {v:.3f}: xấu nhất {xau[k]:.3f} ({xau['anh']}), biên {bien:+.3f}{ti}"
              f" | p50 thật {np.median(xs):.3f} | loại riêng {loai}/{len(con)} | loại một mình {mot_minh}/{len(lo)}"
              f" (bộ khác tốt nhất {tot_nhat_khac[k]:.3f}, {tot_nhat_khac['anh']})")
    dat = [r for r in O if r["loi"] and all(qua(r, k, h, v) for k, h, v in tieu_chi)]
    print(f"\nBộ KHÁC đạt mọi tiêu chí: {len(dat)}" + "".join(
        f"\n  {r['anh']} bộ [{r['bo']}] pc {r['phoi_canh']:.3f} cỡ {r['co_min']:.3f}–{r['co_max']:.3f} "
        f"K4 {r['dinh_mm']:.2f} mm (vuông góc {r['dinh_mm_vuong_goc']:.2f})" for r in dat))
    # bộ khác gần đạt nhất theo K4 (để thấy biên phía bộ khác)
    gan = sorted([r for r in O if r["loi"] and all(qua(r, k, h, v) for k, h, v in tieu_chi[:3])], key=lambda r: r["dinh_mm"])[:5]
    print("Bộ khác qua K1–K3, K4 nhỏ nhất: " + "; ".join(f"{r['anh']} [{r['bo']}] {r['dinh_mm']:.2f} mm" for r in gan))
    theo_anh = defaultdict(int)
    for r in T + dat:
        theo_anh[r["anh"]] += int(r["loi"] and all(qua(r, k, h, v) for k, h, v in tieu_chi))
    print("Ảnh có số bộ đạt ≠ 1: " + (", ".join(f"{k} ({v})" for k, v in sorted(theo_anh.items()) if v != 1) or "không")
          + f"; ảnh có 0 bộ đạt: {', '.join(sorted({r['anh'] for r in T} - set(theo_anh))) or 'không'}")
    print("\n=== K4 (mm) từng ảnh: cách gán tốt nhất / cặp vuông góc tốt nhất (tỉ số)")
    print("  ".join(f"{r['anh']} {r['dinh_mm']:.2f}/{r['dinh_mm_vuong_goc']:.1f}" + (f"[x{r['xoay']}]" if r["xoay"] else "")
                    for r in T))
    ts = [r["dinh_mm_vuong_goc"] - r["dinh_mm"] for r in T]
    print(f"Khoảng cách vuông góc − tốt nhất: min {min(ts):.2f} mm ({T[int(np.argmin(ts))]['anh']}), trung vị {np.median(ts):.2f} mm")


def ghi_csv_moi(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})


def anh_gia(trang: np.ndarray, khung: tuple, cac_to: list, seed: int) -> tuple[np.ndarray, list]:
    """Ảnh giả: dán từng trang mẫu (300 DPI) vào khung (W, H) theo 4 đỉnh đích (TL, TR, BR, BL của trang),
    nền xám bàn 95, làm mờ + nhiễu như check_layout.py. Trả (ảnh, [H thật của từng tờ])."""
    W, H = khung
    rng = np.random.default_rng(seed)
    anh = np.full((H, W), 95, np.float32)
    h, w = trang.shape
    Hs = []
    for dich in cac_to:
        Ht = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(dich))
        anh_to = cv2.warpPerspective(trang, Ht, (W, H), flags=cv2.INTER_LINEAR)
        mat = cv2.warpPerspective(np.full_like(trang, 255), Ht, (W, H))
        anh = np.where(mat > 0, anh_to, anh)
        Hs.append(Ht)
    anh = cv2.GaussianBlur(anh, (5, 5), 1.2) + rng.normal(0, 4, anh.shape)
    return np.clip(anh, 0, 255).astype(np.uint8), Hs


def dinh_dich(trang_shape, khung, s, goc_do, tam=None, thu_tren=1.0) -> list:
    """4 đỉnh đích (TL, TR, BR, BL của trang) khi thu nhỏ s, xoay goc_do (chiều kim đồng hồ trên ảnh), đặt tại tam;
    thu_tren < 1: cạnh TRÊN của trang ngắn lại (phối cảnh kiểu C3)."""
    h, w = trang_shape
    p = np.array([[-w / 2 * thu_tren, -h / 2], [w / 2 * thu_tren, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]) * s
    t = np.deg2rad(goc_do)
    R = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    c = np.array(tam if tam is not None else (khung[0] / 2, khung[1] / 2))
    return (p @ R.T + c).tolist()


def cmd_tu_kiem_tam(a) -> None:
    """Kiểm chứng 3c trên ảnh giả có H biết trước (trang mẫu phieu_danh_so.pdf, ghi data/_eval/_gia/):
    (1) tâm dưới pixel: giao đường chéo vs centroid, so với H · tâm layout; (2) cách gán góc được chọn: 0° / 180° /
    sai dọc-ngang; (3) ảnh hai tờ -> phải 'nhieu_phieu'."""
    import cv_engine.preprocessing as pp
    from eval_preprocessing import ANSWER_SHEET, EVAL_DIR as ED, render_pdf_page
    layout = nap_layout()
    trang = render_pdf_page(ANSWER_SHEET / "output" / "phieu_danh_so.pdf", layout["dpi"])
    gia = ED / "_gia"
    gia.mkdir(parents=True, exist_ok=True)
    doc, ngang = (3024, 4032), (4032, 3024)
    sh = trang.shape
    ca = [("thang", doc, [dinh_dich(sh, doc, 1.1, 0)], "dung"),
          ("c1", doc, [[[250, 300], [2750, 260], [2850, 3800], [180, 3850]]], "dung"),
          ("c3_pc06", doc, [dinh_dich(sh, doc, 1.08, 0, (1512, 2150), thu_tren=0.6)], "dung"),
          ("xoay15", doc, [dinh_dich(sh, doc, 0.85, 15)], "dung"),
          ("xoay90_ngang", ngang, [dinh_dich(sh, ngang, 0.8, 90)], "dung"),
          ("xoay90_ngang_c3", ngang, [dinh_dich(sh, ngang, 0.8, 90, thu_tren=0.65)], "dung"),
          ("xoay180", doc, [dinh_dich(sh, doc, 0.85, 180)], "dung"),
          ("xoay270_ngang", ngang, [dinh_dich(sh, ngang, 0.8, 270)], "dung"),
          ("hai_to", ngang, [dinh_dich(sh, ngang, 0.75, 3, (1000, 1512)), dinh_dich(sh, ngang, 0.75, -2, (3030, 1512))],
           "nhieu_phieu")]
    tam_L = np.array([layout["markers"]["centers"][g] for g in pp.GOC], np.float32)
    # tâm đúng = trọng tâm ô đen trên chính trang render (ô vuông thẳng -> trọng tâm chính xác), tránh lệch quy ước
    # tâm pixel giữa layout.json và ảnh render (Bước 1: đối chứng tam-marker −0,04 mm)
    tam_R = []
    for cx, cy in tam_L:
        x0, y0 = int(cx) - 70, int(cy) - 70
        cua_so = (trang[y0:y0 + 141, x0:x0 + 141] < 128).astype(np.float64)
        ys, xs = np.nonzero(cua_so)
        tam_R.append((x0 + xs.mean(), y0 + ys.mean()))
    tam_R = np.array(tam_R, np.float32)
    print("Tâm marker trên trang render − layout.json (px): "
          + ", ".join(f"{g} ({d[0]:+.2f}, {d[1]:+.2f})" for g, d in zip(pp.GOC, tam_R - tam_L)))
    rows = []
    for i, (ten, khung, cac_to, mong) in enumerate(ca):
        img, Hs = anh_gia(trang, khung, cac_to, seed=i)
        ghi_jpg(gia / f"{ten}.jpg", img, q=92)
        uv = pp.tim_ung_vien_marker(img)
        e_cen, e_cheo, e_pc = [], [], []
        for Ht in Hs:
            for e in cv2.perspectiveTransform(tam_R[None], Ht)[0]:
                u = min(uv, key=lambda u: np.hypot(u.x - e[0], u.y - e[1]))
                e_cen.append(np.hypot(u.x - e[0], u.y - e[1]))
                c = pp.tam_cheo(u.dinh)
                e_cheo.append(np.hypot(c[0] - e[0], c[1] - e[1]))
                e_pc.append(np.hypot(u.tam[0] - e[0], u.tam[1] - e[1]))
        tam, ly_do, ct = pp.find_markers(img, layout, uv)
        ket = ly_do or "chon"
        if tam is not None:
            e = cv2.perspectiveTransform(tam_R[None], Hs[0])[0]
            goc_tl = pp.GOC[int(np.argmin(np.hypot(*(e - tam[0]).T)))]
            chieu = {"tl": "0°", "br": "180°"}.get(goc_tl, f"SAI dọc/ngang (TL ↦ {goc_tl})")
            xoay = {"tl": 0, "tr": 1, "br": 2, "bl": 3}[goc_tl]
            sai_so = float(np.max(np.hypot(*(np.roll(e, -xoay, axis=0) - tam).T)))
            g = ct["bo_dat"][0]
            ket += f", chiều {chieu}, sai số tâm {sai_so:.2f} px, K4 {g['gan']['dinh_mm']:.2f} mm (vuông góc {g['dinh_mm_vuong_goc']:.1f})"
        dat = "ĐẠT" if (mong == "dung" and tam is not None and "SAI" not in ket) or (mong == ly_do) else "KHÔNG ĐẠT"
        print(f"{ten:16s} tâm max (px): centroid {max(e_cen):.2f} | chéo {max(e_cheo):.2f} | phối cảnh {max(e_pc):.2f} "
              f"|| {ket} | mong đợi {mong}: {dat}")
        rows.append({"ca": ten, "centroid_max_px": max(e_cen), "centroid_tb_px": float(np.mean(e_cen)),
                     "cheo_max_px": max(e_cheo), "cheo_tb_px": float(np.mean(e_cheo)),
                     "phoi_canh_max_px": max(e_pc), "phoi_canh_tb_px": float(np.mean(e_pc)),
                     "ket_qua": ket, "mong_doi": mong, "dat": dat})
    ghi_csv_moi(gia / "tu_kiem_tam.csv", rows)
    print(f"Đã ghi {gia} (ảnh giả + tu_kiem_tam.csv)")


def cmd_chon_bo_4(a) -> None:
    """Khâu CHỌN: find_markers() trên 78 ảnh dev so với marker_that_dev.csv (trúng ≤ KHOP_PX). Bảng theo điều kiện,
    thời gian, ảnh ghép tứ giác của cả 78 ảnh (khao_sat/bo_4_ghep_*.jpg), ảnh nắn thử 0006_C2/C3."""
    import cv_engine.preprocessing as pp
    from collections import defaultdict
    from time import perf_counter
    layout, that = nap_layout(), doc_marker_that()
    rows, o = [], []
    for anh in list_images("dev"):
        g = load_image(anh.duong_dan)
        t0 = perf_counter()
        tam, ly_do, ct = pp.find_markers(g, layout)
        ms = 1000 * (perf_counter() - t0)
        if tam is not None:
            d = [float(np.min(np.hypot(*(that[anh.ten] - p).T))) for p in tam]
            kq = "chon_dung" if max(d) <= KHOP_PX else "chon_sai"
            gan = ct["bo_dat"][0]
        else:
            d, kq, gan = [], "tu_choi", None
        rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "ket_qua": kq, "ly_do": ly_do,
                     "so_bo_dat": len(ct["bo_dat"]), "kc_max_px": max(d) if d else "",
                     "xoay": gan["gan"]["xoay"] if gan else "", "dinh_mm": gan["gan"]["dinh_mm"] if gan else "",
                     "dinh_mm_vuong_goc": gan["dinh_mm_vuong_goc"] if gan else "", "thoi_gian_ms": ms})
        # ảnh nhỏ: ứng viên (xanh), tứ giác chọn (xanh lá), TL (đỏ)
        f = 380 / max(g.shape)
        v = cv2.cvtColor(cv2.resize(g, None, fx=f, fy=f, interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
        for u in ct["ung_vien"]:
            cv2.circle(v, (int(u.x * f), int(u.y * f)), 6, (230, 120, 0), 1)
        if tam is not None:
            cv2.polylines(v, [np.int32(tam * f)], True, (0, 190, 0), 2)
            cv2.circle(v, (int(tam[0][0] * f), int(tam[0][1] * f)), 7, (0, 0, 230), -1)
        o_anh = np.full((410, 390, 3), 255, np.uint8)
        o_anh[:v.shape[0], :v.shape[1]] = v
        cv2.putText(o_anh, f"{anh.ten} {kq if kq != 'chon_dung' else ''}{ly_do}", (4, 404), 0, 0.5, (200, 0, 0), 1, cv2.LINE_AA)
        o.append(o_anh)
        if anh.ten.startswith("0006") and tam is not None:
            M = cv2.getPerspectiveTransform(tam, np.float32([layout["markers"]["centers"][k] for k in pp.GOC]))
            ghi_jpg(OUT / "khao_sat" / f"{anh.ten}_nan_v3.jpg", cv2.warpPerspective(g, M, tuple(layout["page_px"])),
                    max_w=600, q=85)
        print(f"{anh.ten:8s} {kq:9s} {ly_do:15s} bộ đạt {len(ct['bo_dat'])} {ms:5.0f} ms", flush=True)
    ghi_csv_moi(OUT / "chon_bo_4_dev.csv", rows)
    while len(o) % 8:
        o.append(np.full((410, 390, 3), 255, np.uint8))
    hang = [np.hstack(o[i:i + 8]) for i in range(0, len(o), 8)]
    for k in range(0, len(hang), 5):
        ghi_jpg(OUT / "khao_sat" / f"bo_4_ghep_{k // 5 + 1}.jpg", np.vstack(hang[k:k + 5]), q=85)
    nhom = defaultdict(list)
    for r in rows:
        nhom[r["dieu_kien"]].append(r)
    print("\nĐiều kiện | ảnh | chọn đúng | chọn sai | từ chối (lý do)")
    for k in sorted(nhom) + ["Tổng"]:
        rs = rows if k == "Tổng" else nhom[k]
        tc = [r for r in rs if r["ket_qua"] == "tu_choi"]
        print(f"{k:5s} | {len(rs):3d} | {sum(r['ket_qua'] == 'chon_dung' for r in rs):3d} | "
              f"{sum(r['ket_qua'] == 'chon_sai' for r in rs):3d} | {len(tc):3d} "
              + ", ".join(f"{r['anh']}:{r['ly_do']}" for r in tc))
    kc = [r["kc_max_px"] for r in rows if r["kc_max_px"] != ""]
    ms = np.array([r["thoi_gian_ms"] for r in rows])
    print(f"Tâm chọn vs marker_that: max {max(kc):.2f} px. Thời gian find_markers (gồm lọc 3b): trung vị "
          f"{np.median(ms):.0f} ms, max {ms.max():.0f} ms. Xoay ≠ 0: "
          + ", ".join(f"{r['anh']} ({r['xoay']})" for r in rows if r["xoay"] not in ("", 0)))
    print(f"Đã ghi {OUT / 'chon_bo_4_dev.csv'}, khao_sat/bo_4_ghep_*.jpg")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("de-xuat", help="tìm ứng viên lỏng, đoán 4 marker, xuất HTML + xac_nhan.csv")
    sub.add_parser("chot", help="ghép xac_nhan.csv + align_cu đúng -> marker_that_dev.csv")
    t = sub.add_parser("ung-vien", help="đo khâu TÌM của một bộ lọc ứng viên so với marker_that_dev.csv")
    t.add_argument("--bo-loc", default="cu", choices=sorted(BO_LOC))
    sub.add_parser("khao-sat", help="phân bố đặc trưng marker thật vs vết khác -> căn cứ ngưỡng Bước 3b")
    sub.add_parser("khao-sat-bo-4", help="K2–K4 của bộ 4 thật vs bộ 4 khác -> căn cứ ngưỡng Bước 3c")
    sub.add_parser("tu-kiem-tam", help="ảnh giả có H biết trước: tâm dưới pixel, cách gán góc, hai tờ")
    sub.add_parser("chon-bo-4", help="find_markers() trên dev so với marker_that_dev.csv + ảnh ghép tứ giác")
    a = ap.parse_args()
    {"de-xuat": cmd_de_xuat, "chot": cmd_chot, "ung-vien": cmd_ung_vien, "khao-sat": cmd_khao_sat,
     "khao-sat-bo-4": cmd_khao_sat_bo_4, "tu-kiem-tam": cmd_tu_kiem_tam, "chon-bo-4": cmd_chon_bo_4}[a.lenh](a)


if __name__ == "__main__":
    main()
