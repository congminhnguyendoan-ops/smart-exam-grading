"""
tao_split.py - Sinh data/split.csv cho OMR (Tuần 5, kế hoạch docs/ke_hoach_tuan5.md mục 1).

Ranh giới lấy từ cv_engine/tap_du_lieu.py (PHIEU_TRAIN / PHIEU_VAL / PHIEU_TEST) – KHÔNG định nghĩa lại.
Trong train 0001–0028: 7 fold nhóm theo phiếu, phân tầng theo cặp điều kiện (C1+C2 / C2+C3 / C3+C4 / C4+C1): mỗi fold
có đúng 1 phiếu mỗi cặp (4 phiếu, 8 ảnh, mỗi điều kiện C1–C4 2 ảnh); 2 ảnh cùng phiếu luôn cùng fold. Seed 2026.

Tập test: chỉ ghi TÊN file (liệt kê data/raw), điều kiện suy từ tên; KHÔNG đọc ảnh, KHÔNG đọc dòng nhãn của phiếu test
(cột but để trống). Nhãn dev chỉ đọc 2 cột conditions, pen.

Chạy (từ smart_exam_db/):  python tools/tao_split.py            # ghi data/split.csv
                           python tools/tao_split.py --kiem     # chỉ kiểm file hiện có = file sinh lại (từng byte)
"""
import argparse
import csv
import io
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine.tap_du_lieu import PHIEU_TEST, PHIEU_TRAIN, PHIEU_VAL, ma_phieu  # noqa: E402

SEED = 2026
SO_FOLD = 7
COT = ["anh", "phieu", "dieu_kien", "but", "tap", "fold"]


def doc_nhan_dev(gt_path: Path) -> dict:
    """{phieu: (conditions, pen)} – chỉ phiếu train/val; dòng phiếu test bỏ ngay khi đọc."""
    out = {}
    with gt_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            p = int(r["sheet_id"])
            if p in PHIEU_TRAIN or p in PHIEU_VAL:
                out[p] = (r["conditions"], r["pen"])
    return out


def chia_fold(nhan: dict) -> dict:
    """{phieu train: fold 1..7}: mỗi cặp điều kiện (7 phiếu) xáo bằng seed rồi rải 1 phiếu / fold."""
    rng = random.Random(SEED)
    theo_cap = {}
    for p in PHIEU_TRAIN:
        theo_cap.setdefault(nhan[p][0], []).append(p)
    fold = {}
    for cap in sorted(theo_cap):
        ds = sorted(theo_cap[cap])
        if len(ds) != SO_FOLD:
            raise SystemExit(f"cặp {cap} có {len(ds)} phiếu train, cần {SO_FOLD} – không phân tầng đều được")
        rng.shuffle(ds)
        for i, p in enumerate(ds):
            fold[p] = i + 1
    return fold


def tao_noi_dung(raw: Path, gt: Path) -> str:
    nhan = doc_nhan_dev(gt)
    fold = chia_fold(nhan)
    dong = []
    for f in sorted(raw.glob("*.jpg")):                       # chỉ tên file
        p = ma_phieu(f.stem)
        if p is None:
            continue
        dk = f.stem.split("_")[1].upper()
        if p in PHIEU_TRAIN:
            dong.append([f.stem, f"{p:04d}", dk, nhan[p][1], "train", str(fold[p])])
        elif p in PHIEU_VAL:
            dong.append([f.stem, f"{p:04d}", dk, nhan[p][1], "val", ""])
        elif p in PHIEU_TEST:
            dong.append([f.stem, f"{p:04d}", dk, "", "test", ""])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COT)
    w.writerows(dong)
    return buf.getvalue()


def kiem_rang_buoc(noi_dung: str) -> list[str]:
    """Ràng buộc của split (dùng cả trong pytest). Trả danh sách lỗi (rỗng = đạt)."""
    rows = list(csv.DictReader(io.StringIO(noi_dung)))
    loi = []
    tap_cua_phieu, fold_cua_phieu = {}, {}
    for r in rows:
        p = int(r["phieu"])
        mong = "train" if p in PHIEU_TRAIN else "val" if p in PHIEU_VAL else "test" if p in PHIEU_TEST else "?"
        if r["tap"] != mong:
            loi.append(f"{r['anh']}: tập {r['tap']} ≠ {mong} (tap_du_lieu)")
        tap_cua_phieu.setdefault(p, set()).add(r["tap"])
        fold_cua_phieu.setdefault(p, set()).add(r["fold"])
    loi += [f"phiếu {p:04d} ở {len(s)} tập" for p, s in tap_cua_phieu.items() if len(s) > 1]
    loi += [f"phiếu {p:04d} ở {len(s)} fold" for p, s in fold_cua_phieu.items() if len(s) > 1]
    train = [r for r in rows if r["tap"] == "train"]
    for k in range(1, SO_FOLD + 1):
        f = [r for r in train if r["fold"] == str(k)]
        if len({r["phieu"] for r in f}) != 4 or len(f) != 8:
            loi.append(f"fold {k}: {len({r['phieu'] for r in f})} phiếu / {len(f)} ảnh (cần 4 / 8)")
        for dk in ("C1", "C2", "C3", "C4"):
            n = sum(r["dieu_kien"] == dk for r in f)
            if n != 2:
                loi.append(f"fold {k}: {n} ảnh {dk} (cần 2)")
    if any(r["fold"] for r in rows if r["tap"] != "train"):
        loi.append("phiếu val/test có fold")
    if any(r["but"] for r in rows if r["tap"] == "test"):
        loi.append("phiếu test có cột but (không được đọc nhãn test)")
    return loi


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh / kiểm data/split.csv (OMR Tuần 5)")
    ap.add_argument("--raw", default=ROOT / "data" / "raw")
    ap.add_argument("--ground-truth", default=ROOT / "data" / "ground_truth.csv")
    ap.add_argument("--out", default=ROOT / "data" / "split.csv")
    ap.add_argument("--kiem", action="store_true", help="chỉ so file hiện có với bản sinh lại")
    a = ap.parse_args()
    nd = tao_noi_dung(Path(a.raw), Path(a.ground_truth))
    loi = kiem_rang_buoc(nd)
    if loi:
        raise SystemExit("split KHÔNG đạt ràng buộc:\n  " + "\n  ".join(loi))
    out = Path(a.out)
    if a.kiem:
        cu = out.read_text(encoding="utf-8") if out.exists() else None
        print("split.csv GIỐNG bản sinh lại" if cu == nd else "split.csv KHÁC bản sinh lại (hoặc chưa có)")
        sys.exit(0 if cu == nd else 1)
    out.write_text(nd, encoding="utf-8", newline="")
    rows = list(csv.DictReader(io.StringIO(nd)))
    print(f"Đã ghi {out}: " + ", ".join(f"{t} {sum(r['tap'] == t for r in rows)} ảnh" for t in ("train", "val", "test")))


if __name__ == "__main__":
    main()
