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
from cv_engine.preprocessing import load_image  # noqa: E402

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


def ung_vien(gray: np.ndarray) -> list[dict]:
    """Mọi vết mực đặc, gần vuông (lỏng). Chuẩn hoá theo nền giấy cục bộ để ảnh tối (C2) / bóng không ảnh hưởng.
    Trả về danh sách xếp theo độ vuông giảm dần; 'so' = số thứ tự (1, 2, ...) dùng trong HTML/CSV."""
    H, W = gray.shape
    k = max(H, W) // 20 | 1
    nen = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_RECT, (k // 4 | 1, k // 4 | 1)))   # max cục bộ
    nen = cv2.GaussianBlur(nen, (k, k), 0)
    muc = (gray.astype(np.float32) < NGUONG_MUC * np.maximum(nen, 1)).astype(np.uint8)
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


BO_LOC = {"cu": ung_vien_cu}


def cmd_ung_vien(a) -> None:
    """Khâu TÌM: ảnh có đủ 4 marker thật trong danh sách ứng viên không, mỗi ảnh bao nhiêu ứng viên.
    Tách lỗi 'không tìm thấy' (marker thật không có trong danh sách) với 'chọn sai' (có đủ mà vẫn nắn sai)."""
    from collections import defaultdict
    that = {r["anh"]: np.array([[float(r[f"x{i}"]), float(r[f"y{i}"])] for i in range(4)])
            for r in csv.DictReader((OUT / "marker_that_dev.csv").open(encoding="utf-8-sig"))}
    phan_loai = {r["anh"]: r["phan_loai"] for r in
                 csv.DictReader((EVAL_DIR / "align_cu" / "truth_dev.csv").open(encoding="utf-8-sig"))}
    f = BO_LOC[a.bo_loc]
    rows = []
    for anh in list_images("dev"):
        g = load_image(anh.duong_dan)
        c = np.array(f(g), np.float64).reshape(-1, 2)
        if a.bo_loc == "cu" and len(c) >= 4:     # kiểm tra bản sao: 4 điểm find_markers() phải nằm trong danh sách
            fm = find_markers(g)
            if max(np.min(np.hypot(*(c - p).T)) for p in fm) > 1e-3:
                sys.exit(f"LỖI: ung_vien_cu() không khớp find_markers() trên {anh.ten} – bản sao sai")
        d = [float(np.min(np.hypot(*(c - p).T))) if len(c) else np.inf for p in that[anh.ten]]
        tim = sum(x <= KHOP_PX for x in d)
        rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "so_ung_vien": len(c), "so_marker_tim_thay": tim,
                     "d_max_tim_thay_px": max([x for x in d if x <= KHOP_PX], default=float("nan")),
                     "align_cu": phan_loai[anh.ten]})
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
        print(f"{nhan:6s} {len(rs):3d} ảnh | đủ 4 marker thật: {len(du):3d} ({100 * len(du) / len(rs):5.1f}%) | "
              f"ứng viên/ảnh TB {n.mean():6.1f}, trung vị {np.median(n):5.0f}, min {n.min():4d}, max {n.max():4d} | "
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
    print(f"Đã ghi {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("de-xuat", help="tìm ứng viên lỏng, đoán 4 marker, xuất HTML + xac_nhan.csv")
    sub.add_parser("chot", help="ghép xac_nhan.csv + align_cu đúng -> marker_that_dev.csv")
    t = sub.add_parser("ung-vien", help="đo khâu TÌM của một bộ lọc ứng viên so với marker_that_dev.csv")
    t.add_argument("--bo-loc", default="cu", choices=sorted(BO_LOC))
    a = ap.parse_args()
    {"de-xuat": cmd_de_xuat, "chot": cmd_chot, "ung-vien": cmd_ung_vien}[a.lenh](a)


if __name__ == "__main__":
    main()
