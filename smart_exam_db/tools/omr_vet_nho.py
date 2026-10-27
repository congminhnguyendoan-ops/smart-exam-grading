"""Cải tiến 27/10/2026 – đo phân phối "vết tối nhỏ" trong lõi ô đáp án (CHỈ ĐỌC, chỉ ghi data/_eval/omr/vet_nho/).

Lỗ hổng: chấm nhỏ đậm (0,3r, xám 30) bị mô hình đọc là TRỐNG và không cần xem. Công cụ này đo hai đại lượng
trên ô đáp án của 56 ảnh train (nhãn cell_labels.csv) và trên ảnh vẽ giả, để chọn ngưỡng cho luật phụ "vet_nho":
  a) phan_dam_05 = tỉ lệ điểm lõi (0,75r) tối hơn 0,5 × mức giấy vành;
  b) vet_px      = diện tích (px @300 DPI) cụm liên thông lớn nhất của các điểm lõi tối hơn 0,6 × giấy vành SAU PHÉP MỞ
                   hình thái (elip MO_K × MO_K): nét chữ A–D in sẵn dày ~3–4 px bị xoá, khối đặc (vết bút / chấm) còn lại.
  (Hai biến thể "trừ nét in sẵn của mẫu phiếu trắng" đã thử và loại: chấm giữa ô bị che bởi chữ, còn chữ thật trên ảnh
   sắc nét hơn mẫu nên lọt ra – số liệu trong docs/ke_hoach_cai_tien_27-10.md mục 6.3.)
Dùng: python tools/omr_vet_nho.py do        # ghi vet_nho_o.csv + phan_phoi.md + vet_nho.html
      python tools/omr_vet_nho.py gia       # chỉ in bảng ảnh vẽ giả
Chỉ tập train (omr_du_lieu.ds_anh, chan_test); không đọc val / test.
"""
import argparse
import base64
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402
import omr_du_lieu as dl  # noqa: E402

RA = ROOT / "data" / "_eval" / "omr" / "vet_nho"
HE_SO_TOI = 0.6        # điểm "tối" = tối hơn 0,6 × giấy vành (cùng ngưỡng phu_dam của omr.py)
HE_SO_DAM = 0.5        # (a)
MO_K = 7               # px, cạnh elip của phép mở (nét chữ dày ~3–4 px; chấm 0,2r có đường kính ≈ 12 px)
PHAN_VI = (50, 90, 99, 99.9, 100)


def do_vet(anh, cx, cy, r):
    """(phan_dam_05, vet_px, mask_vet, patch_anh) của 1 ô tâm (cx, cy) bán kính r px trên ảnh nắn."""
    n = int(round(3 * r)) + 1
    x0, y0 = int(round(cx - 1.5 * r)), int(round(cy - 1.5 * r))
    pa = omr._cat(anh, x0, y0, x0 + n, y0 + n).astype(np.float32)
    yy, xx = np.ogrid[:n, :n]
    d2 = (xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2
    loi = d2 <= (0.75 * r) ** 2
    giay = max(float(np.median(pa[(d2 >= (1.15 * r) ** 2) & (d2 <= (1.45 * r) ** 2)])), 1.0)
    dam = float(np.mean(pa[loi] < HE_SO_DAM * giay))
    toi = (loi & (pa < HE_SO_TOI * giay)).astype(np.uint8)
    thua = cv2.morphologyEx(toi, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MO_K, MO_K)))
    k, lab, st, _ = cv2.connectedComponentsWithStats(thua, connectivity=8)
    vet = int(st[1:, cv2.CC_STAT_AREA].max()) if k > 1 else 0
    return dam, vet, thua, pa


def do_anh_that(layout, mau):
    nhan = dl.nhan_o()
    out, chi_tiet = [], {}
    ans = layout["answers"]
    r = ans["bubble_radius"]
    for row in dl.ds_anh("train"):
        ten, ph = row["anh"], row["phieu"]
        nan, _ = dl.anh_da_nan(ten, layout)
        dv = omr.dinh_vi(nan, layout, mau)
        for q in range(1, ans["num_questions"] + 1):
            dx, dy = dv.dich[f"q{q}"]
            xau = bool(dv.co[f"q{q}"])
            for o in ans["options"]:
                cx, cy = ans["centers"][str(q)][o]
                dam, vet, thua, pa = do_vet(nan, cx + dx, cy + dy, r)
                nh = nhan[(ph, str(q), o)]
                out.append(dict(anh=ten, dieu_kien=row["dieu_kien"], q=q, o=o, nhan=nh, vi_tri_xau=int(xau),
                                phan_dam_05=round(dam, 5), vet_px=vet))
                chi_tiet[(ten, q, o)] = (thua, pa)
    return out, chi_tiet


def bang_phan_vi(rows, khoa):
    v = np.array([x[khoa] for x in rows], float)
    return [float(np.percentile(v, p)) for p in PHAN_VI] if len(v) else [float("nan")] * len(PHAN_VI)


def md_phan_phoi(rows):
    L = ["# Phân phối vết tối nhỏ trên ô đáp án – 56 ảnh train", "",
         "Tái tạo: `python tools/omr_vet_nho.py do`. (a) = phan_dam_05, (b) = vet_px (px @300 DPI; lõi 0,75r ≈ "
         f"{int(np.pi * (0.75 * 29.5) ** 2)} px).", ""]
    for khoa, ten in (("vet_px", "(b) vet_px"), ("phan_dam_05", "(a) phan_dam_05")):
        L += [f"## {ten} – phân vị {'/'.join(str(p) for p in PHAN_VI)}", "", "| nhãn | điều kiện | n | " +
              " | ".join(f"p{p}" for p in PHAN_VI) + " |", "|---|---|---|" + "---|" * len(PHAN_VI)]
        for nh in ("blank", "faint", "filled"):
            for dk in ("C1", "C2", "C3", "C4", "tất cả"):
                sub = [x for x in rows if x["nhan"] == nh and (dk == "tất cả" or x["dieu_kien"] == dk)]
                if sub:
                    L.append(f"| {nh} | {dk} | {len(sub)} | " + " | ".join(f"{v:.4g}" for v in bang_phan_vi(sub, khoa)) + " |")
        L.append("")
    return "\n".join(L)


def anh_gia(layout, mau):
    """Chấm giả bán kính (0,2–0,5)r × xám (30, 90, 150) trên phiếu trắng: (a), (b) – ô B của 40 câu, lấy trung vị."""
    ans = layout["answers"]
    r = ans["bubble_radius"]
    ket = []
    for kr in (0.2, 0.3, 0.4, 0.5):
        for g in (30, 90, 150):
            anh = mau.copy()
            for q in range(1, 41):
                cx, cy = ans["centers"][str(q)]["B"]
                cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(kr * r)), int(g), -1)
            d, v = [], []
            for q in range(1, 41):
                cx, cy = ans["centers"][str(q)]["B"]
                a, b, _, _ = do_vet(anh, cx, cy, r)
                d.append(a)
                v.append(b)
            ket.append((kr, g, float(np.min(d)), float(np.min(v)), float(np.max(v))))
    return ket


def md_gia(ket):
    L = ["## Chấm nhỏ giả trên phiếu trắng (ô B, 40 câu): min qua 40 câu", "",
         "| bán kính | xám | min (a) | min (b) px | max (b) px |", "|---|---|---|---|---|"]
    L += [f"| {kr}r | {g} | {d:.4f} | {vmin:.0f} | {vmax:.0f} |" for kr, g, d, vmin, vmax in ket]
    return "\n".join(L)


def png_b64(a, k=4):
    a = cv2.resize(a, None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST)
    return base64.b64encode(cv2.imencode(".png", a)[1].tobytes()).decode()


def html_blank(rows, chi_tiet, n=20):
    top = sorted((x for x in rows if x["nhan"] == "blank"), key=lambda x: -x["vet_px"])[:n]
    H = ["<meta charset='utf-8'><title>Ô blank có vết thừa lớn nhất</title><style>body{font-family:sans-serif}"
         "td{padding:4px;border:1px solid #888;text-align:center;font-size:12px}img{image-rendering:pixelated}</style>",
         "<h2>20 ô blank có (b) lớn nhất – trái: ảnh nắn; phải: khối đặc sau phép mở (đỏ)</h2><table><tr>"]
    for i, x in enumerate(top):
        thua, pa = chi_tiet[(x["anh"], x["q"], x["o"])]
        pa8 = np.clip(pa, 0, 255).astype(np.uint8)
        rgb = cv2.cvtColor(pa8, cv2.COLOR_GRAY2BGR)
        rgb[thua > 0] = (0, 0, 255)
        if i % 4 == 0 and i:
            H.append("</tr><tr>")
        H.append(f"<td><img src='data:image/png;base64,{png_b64(pa8)}'> <img src='data:image/png;base64,{png_b64(rgb)}'>"
                 f"<br>{x['anh']} câu {x['q']} ô {x['o']}<br>b = {x['vet_px']} px · a = {x['phan_dam_05']:.3f}"
                 f"{' · vị trí xấu' if x['vi_tri_xau'] else ''}</td>")
    H.append("</tr></table>")
    return "\n".join(H)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["do", "gia"])
    lenh = ap.parse_args().lenh
    sys.stdout.reconfigure(encoding="utf-8")
    layout, mau = nap_layout("phieu"), omr.nap_mau()
    RA.mkdir(parents=True, exist_ok=True)
    ket = anh_gia(layout, mau)
    print(md_gia(ket))
    if lenh == "gia":
        return
    rows, chi_tiet = do_anh_that(layout, mau)
    with (RA / "vet_nho_o.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = md_phan_phoi(rows) + "\n\n" + md_gia(ket) + "\n"
    (RA / "phan_phoi.md").write_text(md, encoding="utf-8")
    (RA / "vet_nho.html").write_text(html_blank(rows, chi_tiet), encoding="utf-8")
    print(md_phan_phoi(rows))
    print(f"Đã ghi {RA}")


if __name__ == "__main__":
    main()
