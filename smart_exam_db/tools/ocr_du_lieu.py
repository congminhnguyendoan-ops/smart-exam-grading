"""
ocr_du_lieu.py - Dữ liệu cho CNN chữ số (Tuần 6, docs/ke_hoach_tuan6.md Bước 2–3).

  cat   : cắt 400 ô/trang × 10 trang (data/raw_digits) và 9 ô/ảnh × phiếu DEV 0001–0034 (data/raw), từ `anh_nan` VÀ `anh_chuan_hoa`
          (preprocess()); bỏ viền ô; chuẩn hoá kiểu MNIST -> data/_ocr/cat/<nguon>.npz + <nguon>.csv  (nguon = anh_nan | anh_chuan_hoa)
  xem   : lưới ảnh để xem bằng mắt (ô cắt đã bỏ viền + ảnh MNIST), danh sách ô trống / chạm viền / lạ -> data/_ocr/cat/xem/
  split : data/ocr_split.csv (người viết, fold, tập) – CHỈ dùng cv_engine/tap_du_lieu.py
  kiem  : kiểm split đang có = sinh lại từng byte; không phiếu test trong bất kỳ file nào

Phiếu test 0035–0040: KHÔNG đọc ảnh, KHÔNG đọc dòng nhãn (chan_test + bỏ dòng khi đọc ground_truth). Không ghi vào data/raw*.
Chạy (từ smart_exam_db/):  python tools/ocr_du_lieu.py cat | xem | split | kiem
"""
import argparse
import csv
import io
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine import ocr  # noqa: E402
from cv_engine.preprocessing import nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import (PHIEU_DEV, PHIEU_TRAIN, PHIEU_VAL, chan_test, fold_nguoi_viet, ma_phieu,  # noqa: E402
                                   ma_trang, nguoi_viet, nguoi_viet_trang)

DATA = ROOT / "data"
CAT = DATA / "_ocr" / "cat"
NGUON = ("anh_nan", "anh_chuan_hoa")
COT_META = ["nguon_anh", "anh", "loai", "vi_tri", "nhan", "nguoi", "fold", "ink_px", "ti_le_muc", "n_tp", "cao", "rong",
            "cham_vien", "vien_con", "lech_x", "lech_y", "ok_vien", "trong"]
NGUONG_TRONG = 30        # ink_px < ngưỡng -> ô coi là trống (đã so với phân bố ở bước `xem`)
COT_SPLIT = ["anh", "loai", "nguoi", "fold", "tap"]


def _doc_nhan_phieu() -> dict[int, tuple[str, str]]:
    """{phiếu: (sbd viết tay, mã đề viết tay)} – chỉ phiếu DEV; dòng phiếu test bỏ ngay khi đọc."""
    out = {}
    with (DATA / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            p = int(r["sheet_id"])
            if p in PHIEU_DEV:
                out[p] = (r["sbd"], r["exam_code"])
    return out


def _liet_ke():
    """[(đường dẫn, tên, loại)]: 10 trang chữ số + ảnh phiếu dev (chỉ TÊN file, rồi chan_test)."""
    ds = [(p, p.stem, "trang") for p in sorted((DATA / "raw_digits").glob("D*.jpg"))]
    ph = [(p, p.stem, "phieu") for p in sorted((DATA / "raw").glob("*.jpg")) if ma_phieu(p.stem) in PHIEU_DEV]
    chan_test([p for p, _, _ in ds + ph], xac_nhan=False, viec="ocr_du_lieu cat")
    return ds + ph


def _nhom_cua_anh(ten: str, loai: str, lay_trang: dict, lay_phieu: dict, nhan_phieu: dict):
    """Sinh các NHÓM ô cùng hàng của 1 ảnh: [(loai_o, [(vi_tri, nhan, rect), ...])]. Trang: 20 hàng × 20 ô; phiếu: SBD 6 + mã đề 3."""
    if loai == "trang":
        hang: dict[int, list] = {}
        for b in lay_trang["boxes"]:
            hang.setdefault(b["row"], []).append((b["row"] * 20 + b["col"], str(b["label"]), b["rect"]))
        return [("trang", v) for _, v in sorted(hang.items())]
    sbd, ma = nhan_phieu[ma_phieu(ten)]
    return [(lo, [(i, txt[i], r) for i, r in enumerate(lay_phieu[fld]["handwriting_boxes"])])
            for fld, txt, lo in (("sbd", sbd, "sbd"), ("exam_code", ma, "ma_de"))]


def cmd_cat(a):
    lay_t, lay_p = nap_layout("chu_so"), nap_layout("phieu")
    nhan = _doc_nhan_phieu()
    ds = _liet_ke()
    CAT.mkdir(parents=True, exist_ok=True)
    X = {n: [] for n in NGUON}
    M = {n: [] for n in NGUON}
    loi = []
    t0 = time.time()
    for path, ten, loai in ds:
        kq = preprocess(str(path), lay_t if loai == "trang" else lay_p)
        if not kq.ok:
            loi.append((ten, kq.ly_do))
            continue
        for n, img in zip(NGUON, (kq.anh_nan, kq.anh_chuan_hoa)):
            toi = ocr.ban_do_toi(img)
            nhoms = _nhom_cua_anh(ten, loai, lay_t, lay_p, nhan)
            for (lo, nhom), cac_o in zip(nhoms, ocr.cat_anh(img, [[r for _, _, r in nh] for _, nh in nhoms], toi)):
                for (vt, nh, _), o in zip(nhom, cac_o):
                    X[n].append(o.anh28 if o.anh28 is not None else np.zeros((28, 28), np.uint8))
                    M[n].append([n, ten, lo, vt, nh, nguoi_viet(ten), fold_nguoi_viet(ten), o.ink_px, f"{o.ti_le_muc:.5f}", o.n_tp,
                                 o.cao, o.rong, o.cham_vien, f"{o.vien_con:.3f}", o.lech_vien[0], o.lech_vien[1], int(o.ok_vien), int(o.ink_px < NGUONG_TRONG)])
    for n in NGUON:
        np.savez_compressed(CAT / f"{n}.npz", x=np.array(X[n], np.uint8))
        with (CAT / f"{n}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(COT_META)
            w.writerows(M[n])
    print(f"Đã cắt {len(ds) - len(loi)}/{len(ds)} ảnh trong {time.time() - t0:.0f} s -> {CAT}")
    for ten, ly in loi:
        print(f"  BỊ TỪ CHỐI: {ten} ({ly})")
    cmd_thong_ke(a)


def _doc_meta(n):
    with (CAT / f"{n}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cmd_thong_ke(a):
    for n in NGUON:
        m = _doc_meta(n)
        print(f"\n== {n}: {len(m)} ô")
        for lo in ("trang", "sbd", "ma_de"):
            r = [x for x in m if x["loai"] == lo]
            ink = np.array([int(x["ink_px"]) for x in r])
            print(f"  {lo:6s} {len(r):5d} ô | ok_vien {sum(int(x['ok_vien']) for x in r) / len(r):.1%} | trống {sum(int(x['trong']) for x in r)} "
                  f"| còn vệt viền {sum(float(x['vien_con']) > 0.5 for x in r)} | chạm vành>20px {sum(int(x['cham_vien']) > 20 for x in r)} | n_tp>1 {sum(int(x['n_tp']) > 1 for x in r)} "
                  f"| ink_px p1/p50/p99 {np.percentile(ink, 1):.0f}/{np.percentile(ink, 50):.0f}/{np.percentile(ink, 99):.0f}")


def _luoi(imgs, cot, o_w, o_h, nhan=None, nen=255):
    """Ghép danh sách ảnh xám (cùng cỡ) thành lưới, có nhãn góc."""
    hang = []
    for i in range(0, len(imgs), cot):
        r = imgs[i:i + cot]
        r = r + [np.full((o_h, o_w), nen, np.uint8)] * (cot - len(r))
        hang.append(np.hstack(r))
    return np.vstack(hang)


def cmd_xem(a):
    """Lưới mỗi trang (400 ô: hàng = chữ số 0–9 × 2 hàng) – ô MNIST và ô cắt; tách riêng danh sách đáng ngờ."""
    out = CAT / "xem"
    out.mkdir(parents=True, exist_ok=True)
    lay_t = nap_layout("chu_so")
    x = np.load(CAT / "anh_nan.npz")["x"]
    m = _doc_meta("anh_nan")
    idx = {}
    for i, r in enumerate(m):
        idx.setdefault(r["anh"], []).append(i)
    for ten, ii in idx.items():
        if not ten.startswith("D"):
            continue
        t = [cv2.resize(255 - x[i], (56, 56), interpolation=cv2.INTER_NEAREST) for i in ii]
        g = _luoi(t, 20, 56, 56)
        cv2.imwrite(str(out / f"{ten}_mnist.png"), g)
    dang_ngo = [r for r in m if int(r["trong"]) or float(r["vien_con"]) > 0.5 or int(r["ok_vien"]) == 0]
    with (out / "dang_ngo.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anh", "loai", "vi_tri", "nhan", "ink_px", "vien_con", "ok_vien", "trong"])
        for r in dang_ngo:
            w.writerow([r["anh"], r["loai"], r["vi_tri"], r["nhan"], r["ink_px"], r["vien_con"], r["ok_vien"], r["trong"]])
    print(f"Ghi {sum(k.startswith('D') for k in idx)} lưới + {len(dang_ngo)} ô đáng ngờ -> {out}")


def tao_split() -> str:
    """Nội dung data/ocr_split.csv: mỗi dòng 1 ẢNH (trang chữ số + ảnh phiếu dev; test chỉ ghi TÊN, không có nhãn)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COT_SPLIT)
    ten = [f"D{t:03d}" for t in range(1, 11)]
    for t in ten:
        w.writerow([t, "trang", nguoi_viet(t), fold_nguoi_viet(t), "tinh_chinh_cv"])
    for p in sorted((DATA / "raw").glob("*.jpg")):
        mp = ma_phieu(p.stem)
        tap = "test" if mp not in PHIEU_DEV else ("train" if mp in PHIEU_TRAIN else "val")
        w.writerow([p.stem, "phieu", nguoi_viet(p.stem), fold_nguoi_viet(p.stem) if tap != "test" else "", "dev_do" if tap == "train" else tap])
    return buf.getvalue()


def cmd_split(a):
    (DATA / "ocr_split.csv").write_text(tao_split(), encoding="utf-8", newline="")
    print("Đã ghi data/ocr_split.csv")


def cmd_kiem(a):
    cu = (DATA / "ocr_split.csv").read_text(encoding="utf-8")
    assert cu == tao_split(), "ocr_split.csv khác bản sinh lại"
    rows = list(csv.DictReader(io.StringIO(cu)))
    trang = [r for r in rows if r["loai"] == "trang"]
    assert len(trang) == 10 and {r["fold"] for r in trang} == {"0", "1", "2", "3", "4"}
    for f in range(5):
        assert sorted(r["anh"] for r in trang if r["fold"] == str(f)) == [f"D{2 * f + 1:03d}", f"D{2 * f + 2:03d}"]
    assert all(ma_trang(r["anh"]) for r in trang)
    for fi in sorted(CAT.glob("*.csv")):                       # không phiếu test trong file cắt
        for r in csv.DictReader(fi.open(encoding="utf-8")):
            if ma_phieu(r["anh"]) is not None:
                assert ma_phieu(r["anh"]) in PHIEU_DEV, f"{fi.name}: có phiếu test {r['anh']}"
    n_test = sum(r["tap"] == "test" for r in rows if r["loai"] == "phieu")
    print(f"OK: split khớp bản sinh lại; 5 fold × 2 trang; {n_test} ảnh test chỉ có tên; 0 phiếu test trong dữ liệu cắt.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["cat", "thong-ke", "xem", "split", "kiem"])
    a = ap.parse_args()
    {"cat": cmd_cat, "thong-ke": cmd_thong_ke, "xem": cmd_xem, "split": cmd_split, "kiem": cmd_kiem}[a.lenh](a)
