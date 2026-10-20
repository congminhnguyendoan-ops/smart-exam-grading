"""
ocr_phan_tich.py - Tuần 6 Phần C, Bước 1: vì sao ~54% phiếu dev "cần xem" ở SBD / mã đề? Chỉ dev (phiếu 0001–0028, 56 ảnh).
Dùng M2 sơ bộ (OOF theo người viết, toan_bo/anh_nan, nhiệt độ T) + OMR bubble (data/_ocr/omr_dev.json) + luật đối chiếu hiện có.

  python tools/ocr_phan_tich.py [--oof data/_ocr/oof_m2_toan_bo_anh_nan.npz]   -> in bảng + data/_eval/ocr/phan_tich_buoc1.json
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402
import ocr_do_luong as L  # noqa: E402
from cv_engine import ocr  # noqa: E402


def phan_loai_cot(b, bcx, cnn, p, nhan, ok_vien, tau_khop=L.TAU_KHOP):
    """Nguyên nhân MỘT cột bị gắn cần xem (None nếu chắc). Phân rã mịn hơn MA_LY_DO_OCR để biết lỗi do kênh nào."""
    if b == "?":
        return "bubble_khong_doc"            # không tô / tô nhiều ô (OMR trả '?')
    if bcx:
        return "bubble_cx"
    if str(cnn) == b and p >= tau_khop:
        return None
    if str(cnn) == b:
        return "cnn_khong_chac"              # cùng chữ số nhưng p < τ_khop
    # hai kênh lệch nhau: ai sai? (nhãn = chữ viết tay thật)
    if not ok_vien:
        return "lech_do_o_that_bai"
    if str(cnn) != str(nhan) and b == str(nhan):
        return "lech_cnn_sai"                # bubble đúng, CNN đọc sai
    if str(cnn) == str(nhan) and b != str(nhan):
        return "lech_bubble_sai"             # CNN đúng, bubble khác chữ viết (người tô khác số viết, hoặc OMR sai)
    return "lech_ca_hai_khac_nhan"


def chay(oof_path: Path, nguon="anh_nan"):
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    t = H.tap_do(nguon)
    z = np.load(oof_path)
    T = L.chon_nhiet(z["trang"], t["trang"]["y"])
    p = L.softmax(z["phieu"] / T)
    meta = t["phieu"]["meta"]
    cot = defaultdict(list)
    for i, r in enumerate(meta):
        o = omr[r["anh"]]
        b, bcx = (o[r["loai"]][int(r["vi_tri"])] if "tu_choi" not in o else ["?", True])
        nguyen_nhan = phan_loai_cot(b, bcx, int(p[i].argmax()), float(p[i].max()), r["nhan"], r["ok_vien"] == "1")
        cot[(r["anh"], r["loai"])].append((int(r["vi_tri"]), nguyen_nhan, r["ok_vien"] == "1", r))
    return cot, T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oof", default=str(H.OCR / "oof_m2_toan_bo_anh_nan.npz"))
    a = ap.parse_args()
    cot, T = chay(Path(a.oof))
    print(f"T = {T:.2f}; {len(cot)} trường (ảnh × SBD|mã đề)")
    # 1) mức cột
    c_cot = Counter(nn or "chac" for v in cot.values() for _, nn, _, _ in v)
    tong_cot = sum(c_cot.values())
    print(f"\nMức CỘT ({tong_cot} chữ số):")
    for k, n in c_cot.most_common():
        print(f"  {k:24s} {n:4d}  {n / tong_cot:6.1%}")
    # 2) mức trường: trường bị gắn, theo nguyên nhân (tập các nguyên nhân)
    ds_anh = defaultdict(dict)
    ket = {}
    for (anh, lo), v in cot.items():
        nn = [x[1] for x in v if x[1]]
        ds_anh[anh][lo] = bool(nn)
        ket[(anh, lo)] = nn
    print("\nMức TRƯỜNG: trường bị gắn theo nguyên nhân (một trường có thể có nhiều cột/nguyên nhân):")
    for lo in ("sbd", "ma_de"):
        ds = [k for k in ket if k[1] == lo]
        gan = [k for k in ds if ket[k]]
        print(f"  {lo}: {len(gan)}/{len(ds)} bị gắn")
        c_t = Counter(frozenset(ket[k]) for k in gan)
        c_any = Counter(n for k in gan for n in set(ket[k]))
        print("    có ít nhất 1 cột loại:", dict(c_any.most_common()))
        print("    chỉ gồm các loại:", {"+".join(sorted(f)): n for f, n in c_t.most_common()})
    # nguyên nhân đầu (ưu tiên) cho mỗi PHIẾU bị gắn: bubble > ô thất bại > cnn sai > bubble sai > khác
    uu_tien = ["bubble_khong_doc", "bubble_cx", "lech_do_o_that_bai", "lech_cnn_sai", "lech_ca_hai_khac_nhan", "lech_bubble_sai", "cnn_khong_chac"]
    c_phieu = Counter()
    phieu_gan = {}
    for anh, d in ds_anh.items():
        nn = {n for lo in ("sbd", "ma_de") for n in ket.get((anh, lo), [])}
        if nn:
            phieu_gan[anh] = next(u for u in uu_tien if u in nn)
            c_phieu[phieu_gan[anh]] += 1
    print(f"\nMức PHIẾU(ảnh): {len(phieu_gan)}/{len(ds_anh)} bị gắn ({len(phieu_gan) / len(ds_anh):.1%}); theo nguyên nhân ưu tiên:")
    for k, n in c_phieu.most_common():
        print(f"  {k:24s} {n:3d}")
    # 3) theo người viết, theo điều kiện
    def bang(khoa, ten):
        print(f"\nTỉ lệ ảnh bị gắn theo {ten}:")
        g = defaultdict(lambda: [0, 0, Counter()])
        for anh in ds_anh:
            r = next(x[3] for v in cot.values() for x in v if x[3]["anh"] == anh)
            k = khoa(r)
            g[k][0] += 1
            if anh in phieu_gan:
                g[k][1] += 1
                g[k][2][phieu_gan[anh]] += 1
        for k in sorted(g):
            n, m, c = g[k]
            print(f"  {k}: {m}/{n} = {m / n:5.1%}  {dict(c.most_common())}")
    bang(lambda r: f"người {r['nguoi']}", "người viết")
    bang(lambda r: r["anh"].split("_")[-1], "điều kiện C1–C4")
    # 4) dò ô
    print("\nDò ô (ok_vien):")
    for lo in ("sbd", "ma_de"):
        xs = [x for (an, l), v in cot.items() if l == lo for x in v]
        sai = [x for x in xs if not x[2]]
        print(f"  {lo}: {len(sai)}/{len(xs)} ô không dò được khung ({len(sai) / len(xs):.1%}); trong đó bị gắn: {sum(1 for x in sai if x[1])}")
    # 5) CNN đơn thuần: tỉ lệ cột sai theo ok_vien
    ok, ko = [], []
    for (an, lo), v in cot.items():
        for _, nn, okv, r in v:
            pass
    ghi = {"T": T, "cot": dict(c_cot), "phieu": dict(c_phieu), "n_phieu": len(ds_anh), "phieu_gan": len(phieu_gan)}
    (H.EVAL / "phan_tich_buoc1.json").write_text(json.dumps(ghi, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
