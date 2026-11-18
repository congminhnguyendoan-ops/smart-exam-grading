"""Cải tiến 27/10/2026 (mục 6.4) – đo nợ "thang S_anh phụ thuộc cả tờ" (CHỈ ĐỌC; chỉ ghi data/_eval/omr/s_anh/).

omr.py đo độ tối ô theo thang của CHÍNH TỜ (S_anh, sàn S_SAN). Công cụ này đo trên 56 ảnh train (mô hình OOF theo fold, như
eval_omr.py m1) và trên ảnh vẽ giả:
  a) phân phối S_anh theo C1–C4, số ảnh chạm sàn;
  b) độ tối TUYỆT ĐỐI ld (= 1 − TB lõi / giấy vành, CHƯA chia S_anh) của ô được đọc "rõ chắc" (câu 1 ô, không cờ), và của ô nhãn faint
     theo lớp máy đọc;
  c) số ô "rõ chắc" có ld < 0,35 / 0,40 / 0,45 / 0,50 (luật "ld thấp ⇒ cần xem" sẽ gắn cờ thêm bao nhiêu câu thật);
  d) ảnh giả: nền đệm bút xám 30 / 90 / 150 / 190, vệt lạc 1 ô ở xám 120 … 230 -> trạng thái + can_xem.
Dùng: python tools/omr_s_anh.py do | gia | tat_ca      Chỉ tập train (omr_du_lieu.ds_anh, chan_test); không đọc val / test.
"""
import argparse
import base64
import csv
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

RA = ROOT / "data" / "_eval" / "omr" / "s_anh"
FOLD = ROOT / "data" / "_omr" / "mo_hinh_fold"
PHAN_VI = (0.1, 1, 5, 50)
MUC_LD = (0.35, 0.40, 0.45, 0.50)
NEN = (30, 90, 150, 190)
VET = (120, 150, 170, 190, 210, 230)
DK = ("C1", "C2", "C3", "C4")


def do_anh_that(L, mau):
    nhan = dl.nhan_o()
    hang_ro, o_faint, s_anh = [], [], []
    mh = {}
    for row in dl.ds_anh("train"):
        ten, ph, dk, fold = row["anh"], row["phieu"], row["dieu_kien"], row["fold"]
        if fold not in mh:
            mh[fold] = omr.nap_mo_hinh(FOLD / f"omr_m1_fold{fold}.json")
        nan, ch = dl.anh_da_nan(ten, L)
        res = omr.doc_phieu(SimpleNamespace(ok=True, anh_nan=nan, anh_chuan_hoa=ch), L, mh[fold], mau)
        dv = omr.dinh_vi(nan, L, mau)
        cau_dt, _, S = omr.dac_trung_o(nan, L, dv)
        s_anh.append(dict(anh=ten, dk=dk, S=float(S)))
        for q, k in enumerate(res.cau):
            for j, o in enumerate(L["answers"]["options"]):
                ld = float(cau_dt[q, j, 0])
                cls = max(k.xac_suat[o], key=k.xac_suat[o].get)
                if nhan[(ph, str(q + 1), o)] == "faint":
                    o_faint.append(dict(anh=ten, dk=dk, q=q + 1, o=o, ld=ld, may=cls))
            if k.trang_thai == "ro" and not k.can_xem and len(k.dap_an) == 1:
                j = "ABCD".index(k.dap_an)
                hang_ro.append(dict(anh=ten, dk=dk, q=q + 1, o=k.dap_an, ld=float(cau_dt[q, j, 0]),
                                    tam=(L["answers"]["centers"][str(q + 1)][k.dap_an], dv.dich[f"q{q + 1}"])))
    return s_anh, hang_ro, o_faint


def pv(v, p):
    return float(np.percentile(v, p)) if len(v) else float("nan")


def md_that(s_anh, hang_ro, o_faint):
    Lm = ["# Đo thang S_anh trên 56 ảnh train", "", "Tái tạo: `python tools/omr_s_anh.py do`.", "",
          f"## a) S_anh (sàn S_SAN = {omr.S_SAN})", "", "| điều kiện | ảnh | min | p50 | max | chạm sàn |", "|---|---|---|---|---|---|"]
    for dk in DK + ("tất cả",):
        v = [x["S"] for x in s_anh if dk == "tất cả" or x["dk"] == dk]
        Lm.append(f"| {dk} | {len(v)} | {min(v):.3f} | {pv(v, 50):.3f} | {max(v):.3f} | {sum(x <= omr.S_SAN + 1e-9 for x in v)} |")
    Lm += ["", "## b) ld tuyệt đối của ô \"rõ chắc\" (câu 1 ô, không cờ)", "",
           "| điều kiện | n | " + " | ".join(f"p{p}" for p in PHAN_VI) + " |", "|---|---|" + "---|" * len(PHAN_VI)]
    for dk in DK + ("tất cả",):
        v = [x["ld"] for x in hang_ro if dk == "tất cả" or x["dk"] == dk]
        Lm.append(f"| {dk} | {len(v)} | " + " | ".join(f"{pv(v, p):.3f}" for p in PHAN_VI) + " |")
    Lm += ["", "Ô nhãn faint (366), ld theo lớp máy đọc:", "", "| máy đọc | n | " + " | ".join(f"p{p}" for p in PHAN_VI) + " |",
           "|---|---|" + "---|" * len(PHAN_VI)]
    for c in ("blank", "faint", "filled"):
        v = [x["ld"] for x in o_faint if x["may"] == c]
        if v:
            Lm.append(f"| {c} | {len(v)} | " + " | ".join(f"{pv(v, p):.3f}" for p in PHAN_VI) + " |")
    Lm += ["", "## c) Số ô \"rõ chắc\" có ld < mức (= số câu thật bị gắn cờ thêm)", "",
           "| điều kiện | n rõ chắc | " + " | ".join(f"< {m}" for m in MUC_LD) + " |", "|---|---|" + "---|" * len(MUC_LD)]
    for dk in DK + ("tất cả",):
        v = np.array([x["ld"] for x in hang_ro if dk == "tất cả" or x["dk"] == dk])
        Lm.append(f"| {dk} | {len(v)} | " + " | ".join(f"{int((v < m).sum())} ({100 * (v < m).mean():.2f}%)" for m in MUC_LD) + " |")
    return "\n".join(Lm)


def ve_gia(nen, vet, n_vet=None):
    L, mau = nap_layout("phieu"), omr.nap_mau()
    ans = L["answers"]
    R = ans["bubble_radius"]
    anh = mau.copy()
    for q in range(1, 41):
        o, g = ("A", vet[q - 1]) if q <= len(vet) else ("C", nen)
        cx, cy = ans["centers"][str(q)][o]
        cv2.circle(anh, (int(round(cx)), int(round(cy))), int(round(0.85 * R)), int(g), -1)
    kq = SimpleNamespace(ok=True, anh_nan=anh, anh_chuan_hoa=anh)
    res = omr.doc_phieu(kq, L, omr.nap_mo_hinh(), mau)
    cau_dt, _, S = omr.dac_trung_o(anh, L, omr.dinh_vi(anh, L, mau))
    return res.cau[:len(vet)], cau_dt[:len(vet), 0, 0], float(S)


def md_gia():
    Lm = ["## d) Ảnh giả: vệt lạc 1 ô (xám cột) trên nền đệm bút (xám hàng); ô = trạng thái / cờ cần xem [ld tuyệt đối]", "",
          "| nền đệm (S_anh) | " + " | ".join(f"vệt {v}" for v in VET) + " |", "|---|" + "---|" * len(VET)]
    for nen in NEN:
        cau, ld, S = ve_gia(nen, VET)
        Lm.append(f"| {nen} (S={S:.2f}) | " + " | ".join(
            f"{k.trang_thai}/{'XEM' if k.can_xem else '–'} [{l:.2f}]" for k, l in zip(cau, ld)) + " |")
    return "\n".join(Lm)


def png_b64(a, k=4):
    a = cv2.resize(a, None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST)
    return base64.b64encode(cv2.imencode(".png", a)[1].tobytes()).decode()


def html_ld_thap(L, hang_ro, n=20):
    r = L["answers"]["bubble_radius"]
    H = ["<meta charset='utf-8'><title>Ô rõ chắc có ld thấp nhất</title><style>body{font-family:sans-serif}"
         "td{padding:4px;border:1px solid #888;text-align:center;font-size:12px}img{image-rendering:pixelated}</style>",
         f"<h2>{n} ô thật \"rõ chắc\" có ld tuyệt đối thấp nhất (56 ảnh train)</h2><table><tr>"]
    for i, x in enumerate(sorted(hang_ro, key=lambda x: x["ld"])[:n]):
        (cx, cy), (dx, dy) = x["tam"]
        nan, _ = dl.anh_da_nan(x["anh"], L)
        cx, cy = cx + dx, cy + dy
        x0, y0, m = int(round(cx - 2 * r)), int(round(cy - 2 * r)), int(round(4 * r))
        patch = np.clip(omr._cat(nan, x0, y0, x0 + m, y0 + m), 0, 255).astype(np.uint8)
        if i % 4 == 0 and i:
            H.append("</tr><tr>")
        H.append(f"<td><img src='data:image/png;base64,{png_b64(patch, 3)}'><br>{x['anh']} câu {x['q']} ô {x['o']}<br>ld = {x['ld']:.3f}</td>")
    H.append("</tr></table>")
    return "\n".join(H)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["do", "gia", "tat_ca"])
    lenh = ap.parse_args().lenh
    sys.stdout.reconfigure(encoding="utf-8")
    RA.mkdir(parents=True, exist_ok=True)
    out = []
    if lenh in ("do", "tat_ca"):
        L, mau = nap_layout("phieu"), omr.nap_mau()
        s_anh, hang_ro, o_faint = do_anh_that(L, mau)
        with (RA / "o_ro_chac.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["anh", "dieu_kien", "q", "o", "ld"])
            w.writerows((x["anh"], x["dk"], x["q"], x["o"], round(x["ld"], 4)) for x in hang_ro)
        (RA / "ld_thap.html").write_text(html_ld_thap(L, hang_ro), encoding="utf-8")
        out.append(md_that(s_anh, hang_ro, o_faint))
    if lenh in ("gia", "tat_ca"):
        out.append(md_gia())
    md = "\n\n".join(out) + "\n"
    (RA / f"bang_{lenh}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
