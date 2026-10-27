"""Cải tiến 28/10/2026 (mục 6.6) – đo thống kê MỨC TỜ "tô nhạt cả tờ" (CHỈ ĐỌC; chỉ ghi data/_eval/omr/to_nhat/).

T = trung vị độ tối TUYỆT ĐỐI ld (= 1 − TB lõi / giấy vành) của các ô đọc "rõ chắc" (câu 1 ô, không cờ) trong MỘT phiếu;
kèm n (số ô) và p10, p25. Đo:
  a) 56 ảnh train (mô hình OOF theo fold như eval_omr.py m1): phân phối T theo C1–C4, n nhỏ nhất, 5 phiếu T thấp nhất;
  b) ảnh giả cả-tờ-một-độ-đậm: 40 câu, mỗi câu 1 ô, xám 30 / 60 / 90 / 120 / 150 / 190;
  c) ảnh giả "tờ nhạt + vệt lạc": nền đệm 150 / 190, một câu không tô thật mà có vệt lạc 1 ô xám 170 / 190 / 210.
Dùng: python tools/omr_to_nhat.py tat_ca | do | gia      Chỉ tập train (omr_du_lieu.ds_anh, chan_test); không đọc val / test / đợt 2.
"""
import argparse
import base64
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402
import omr_du_lieu as dl  # noqa: E402

RA = ROOT / "data" / "_eval" / "omr" / "to_nhat"
FOLD = ROOT / "data" / "_omr" / "mo_hinh_fold"
DK = ("C1", "C2", "C3", "C4")
XAM = (30, 60, 90, 120, 150, 190)
NEN = (150, 190)
VET = (170, 190, 210)


def o_ro_chac(res_cau, cau_dt):
    """[(q, ô, ld)] của các câu 'rõ chắc' (1 ô, không cờ)."""
    out = []
    for q, k in enumerate(res_cau):
        if k.trang_thai == "ro" and not k.can_xem and len(k.dap_an) == 1:
            out.append((q + 1, k.dap_an, float(cau_dt[q, "ABCD".index(k.dap_an), 0])))
    return out


def thong_ke(ro):
    v = np.array([x[2] for x in ro])
    if not len(v):
        return dict(n=0, T=float("nan"), p10=float("nan"), p25=float("nan"))
    return dict(n=len(v), T=float(np.median(v)), p10=float(np.percentile(v, 10)), p25=float(np.percentile(v, 25)))


def doc_anh(anh, L, mau, mo_hinh):
    kq = SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh)
    res = omr.doc_phieu(kq, L, mo_hinh, mau)
    cau_dt, _, _ = omr.dac_trung_o(anh, L, omr.dinh_vi(anh, L, mau))
    return res, cau_dt


def do_that(L, mau):
    mh, rows = {}, []
    for row in dl.ds_anh("train"):
        ten, fold = row["anh"], row["fold"]
        if fold not in mh:
            mh[fold] = omr.nap_mo_hinh(FOLD / f"omr_m1_fold{fold}.json")
        nan, ch = dl.anh_da_nan(ten, L)
        res = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=nan, anh_chuan_hoa=ch), L, mh[fold], mau)
        dv = omr.dinh_vi(nan, L, mau)
        cau_dt, _, _ = omr.dac_trung_o(nan, L, dv)
        ro = o_ro_chac(res.cau, cau_dt)
        rows.append(dict(anh=ten, dk=row["dieu_kien"], ro=ro, dv=dv, **thong_ke(ro)))
    return rows


def md_that(rows):
    Lm = ["# Thống kê mức tờ T (56 ảnh train)", "", "Tái tạo: `python tools/omr_to_nhat.py do`. T = trung vị ld của ô \"rõ chắc\" mỗi phiếu.", "",
          "## a) Phân phối T", "", "| điều kiện | ảnh | T min | T p5 | T p50 | n min | p10 min | p25 min |", "|---|---|---|---|---|---|---|---|"]
    for dk in DK + ("tất cả",):
        r = [x for x in rows if dk == "tất cả" or x["dk"] == dk]
        T = [x["T"] for x in r]
        Lm.append(f"| {dk} | {len(r)} | {min(T):.3f} | {np.percentile(T, 5):.3f} | {np.percentile(T, 50):.3f} | "
                  f"{min(x['n'] for x in r)} | {min(x['p10'] for x in r):.3f} | {min(x['p25'] for x in r):.3f} |")
    Lm += ["", "5 ảnh có T thấp nhất:", "", "| ảnh | T | n | p10 | p25 |", "|---|---|---|---|---|"]
    for x in sorted(rows, key=lambda x: x["T"])[:5]:
        Lm.append(f"| {x['anh']} | {x['T']:.3f} | {x['n']} | {x['p10']:.3f} | {x['p25']:.3f} |")
    return "\n".join(Lm)


def ve(cases, L, mau, nen=None):
    """cases: danh sách {ô: xám} cho các câu đầu; các câu còn lại tô ô C ở xám `nen` (None = không tô)."""
    ans = L["answers"]
    R = ans["bubble_radius"]
    anh = mau.copy()
    cases = list(cases) + [({"C": nen} if nen is not None else {})] * (40 - len(cases))
    for q, cs in enumerate(cases, 1):
        for o, g in cs.items():
            cx, cy = ans["centers"][str(q)][o]
            cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(0.85 * R)), int(g), -1)
    return anh


def md_gia(L, mau, mo_hinh):
    Lm = ["## b) Ảnh giả cả-tờ-một-độ-đậm (40 câu, mỗi câu 1 ô A–D xoay vòng)", "",
          "| xám | ld lý thuyết (1 − xám/255) | T đo | n | p10 | trạng thái 40 câu |", "|---|---|---|---|---|---|"]
    for g in XAM:
        anh = ve([{"ABCD"[q % 4]: g} for q in range(40)], L, mau)
        res, dt = doc_anh(anh, L, mau, mo_hinh)
        s = thong_ke(o_ro_chac(res.cau, dt))
        tt = {}
        for k in res.cau:
            kk = f"{k.trang_thai}/{'XEM' if k.can_xem else '–'}"
            tt[kk] = tt.get(kk, 0) + 1
        Lm.append(f"| {g} | {1 - g / 255:.3f} | {s['T']:.3f} | {s['n']} | {s['p10']:.3f} | " + ", ".join(f"{a} ×{b}" for a, b in tt.items()) + " |")
    Lm += ["", "## c) Tờ nhạt + vệt lạc (câu 1 = vệt lạc 1 ô A; 39 câu còn lại tô ô C ở xám nền) – trạng thái HIỆN TẠI của câu vệt", "",
           "| nền | T đo | n | " + " | ".join(f"vệt {v}" for v in VET) + " |", "|---|---|---|" + "---|" * len(VET)]
    for nen in NEN:
        c, Ts = [], None
        for v in VET:
            anh = ve([{"A": v}], L, mau, nen)
            res, dt = doc_anh(anh, L, mau, mo_hinh)
            k = res.cau[0]
            c.append(f"{k.trang_thai}/{'XEM' if k.can_xem else '–'}")
            Ts = thong_ke(o_ro_chac(res.cau, dt))
        Lm.append(f"| {nen} | {Ts['T']:.3f} | {Ts['n']} | " + " | ".join(c) + " |")
    return "\n".join(Lm)


def png_b64(a, k=3):
    a = cv2.resize(a, None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST)
    return base64.b64encode(cv2.imencode(".png", a)[1].tobytes()).decode()


def html_t_thap(rows, L, n_phieu=3, n_o=16):
    r = L["answers"]["bubble_radius"]
    H = ["<meta charset='utf-8'><title>Phiếu có T thấp nhất</title><style>body{font-family:sans-serif}"
         "td{padding:3px;border:1px solid #888;text-align:center;font-size:11px}img{image-rendering:pixelated}</style>"]
    for x in sorted(rows, key=lambda x: x["T"])[:n_phieu]:
        nan, _ = dl.anh_da_nan(x["anh"], L)
        H.append(f"<h2>{x['anh']} – T = {x['T']:.3f} (n = {x['n']}); {n_o} ô \"rõ chắc\" có ld thấp nhất</h2><table><tr>")
        for i, (q, o, ld) in enumerate(sorted(x["ro"], key=lambda t: t[2])[:n_o]):
            cx, cy = L["answers"]["centers"][str(q)][o]
            dx, dy = x["dv"].dich[f"q{q}"]
            x0, y0, m = int(round(cx + dx - 2 * r)), int(round(cy + dy - 2 * r)), int(round(4 * r))
            patch = np.clip(omr._cat(nan, x0, y0, x0 + m, y0 + m), 0, 255).astype(np.uint8)
            if i % 8 == 0 and i:
                H.append("</tr><tr>")
            H.append(f"<td><img src='data:image/png;base64,{png_b64(patch)}'><br>câu {q} ô {o}<br>ld {ld:.3f}</td>")
        H.append("</tr></table>")
    return "\n".join(H)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["do", "gia", "tat_ca"])
    lenh = ap.parse_args().lenh
    sys.stdout.reconfigure(encoding="utf-8")
    RA.mkdir(parents=True, exist_ok=True)
    L, mau = nap_layout("phieu"), omr.nap_mau()
    out = []
    if lenh in ("do", "tat_ca"):
        rows = do_that(L, mau)
        (RA / "t_thap.html").write_text(html_t_thap(rows, L), encoding="utf-8")
        out.append(md_that(rows))
    if lenh in ("gia", "tat_ca"):
        out.append(md_gia(L, mau, omr.nap_mo_hinh()))
    md = "\n\n".join(out) + "\n"
    (RA / f"bang_{lenh}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
