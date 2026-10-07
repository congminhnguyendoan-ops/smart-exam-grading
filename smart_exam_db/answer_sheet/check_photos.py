"""
check_photos.py - Kiểm tra nhanh ảnh vừa chụp: đặt tên đúng chưa, đủ độ phân giải không, nắn phẳng được không.
Chạy NGAY sau mỗi buổi chụp để chụp lại ảnh hỏng khi phiếu còn trong tay.

Nắn bằng cv_engine.preprocessing.preprocess() (Tuần 4, Bước 6 – thay align() cũ, vốn chọn nhầm marker mà vẫn báo OK).
Ảnh bị từ chối được báo rõ: tên + mã lý do + thông báo (MA_LY_DO) – không âm thầm bỏ qua.

Quy ước đặt tên:  data/raw/0001_C1.jpg   (mã phiếu 4 số + điều kiện chụp C1..C4)
                  data/raw_digits/D001.jpg (trang thu chữ số)
Chạy:             python check_photos.py --dir ../data/raw
Kết quả:          bảng OK / LỖI + data/_aligned/photo_report_<tên thư mục>.csv; ảnh đã nắn (anh_nan, JPEG q95, CHỈ ĐỂ XEM)
                  vào data/_aligned/<tên thư mục>/. KHÔNG ghi vào thư mục ảnh gốc (data/raw*).
Tập test 0035–0040 bị bỏ qua (không đọc) trừ khi có --xac-nhan-test (cv_engine/tap_du_lieu.py).
"""
import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                      # smart_exam_db/
sys.path.insert(0, str(ROOT))
from cv_engine.preprocessing import MA_LY_DO, nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import la_test  # noqa: E402

NAME_RE = re.compile(r"^(\d{4})_(C[1-4])\.(jpg|jpeg|png|heic)$", re.I)
DIGIT_RE = re.compile(r"^(D\d{3})\.(jpg|jpeg|png|heic)$", re.I)
MIN_CANH = 1500         # cạnh ngắn tối thiểu (px)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=ROOT / "data" / "raw")
    ap.add_argument("--out", default=None, help="mặc định data/_aligned/<tên thư mục --dir>")
    ap.add_argument("--xac-nhan-test", action="store_true", help="đọc cả ảnh test 0035–0040 (chỉ ở đánh giá cuối)")
    a = ap.parse_args()
    src = Path(a.dir).resolve()
    out = Path(a.out) if a.out else ROOT / "data" / "_aligned" / src.name
    if out.resolve() == src or src in out.resolve().parents:
        sys.exit(f"Không ghi vào thư mục ảnh gốc {src} – chọn --out khác.")
    out.mkdir(parents=True, exist_ok=True)
    layout = {"phieu": nap_layout("phieu"), "chu_so": nap_layout("chu_so")}

    rows, bad, bo_qua = [], 0, []
    for p in sorted(x for x in src.iterdir() if x.is_file()):
        fn = p.name
        if p.suffix.lower() == ".csv":
            continue
        m, md = NAME_RE.match(fn), DIGIT_RE.match(fn)
        if not (m or md):
            rows.append({"file": fn, "status": "LỖI", "ly_do": "sai_ten",
                         "thong_bao": "Sai tên file (cần 0001_C1.jpg hoặc D001.jpg)"})
            bad += 1
            continue
        if la_test(fn) and not a.xac_nhan_test:
            bo_qua.append(fn)                       # không đọc ảnh test
            continue
        try:
            with Image.open(p) as im:               # chỉ đọc header
                size = im.size
        except Exception:  # noqa: BLE001 – file hỏng: preprocess sẽ báo khong_doc_duoc
            size = None
        if size and min(size) < MIN_CANH:
            rows.append({"file": fn, "size": f"{size[0]}x{size[1]}", "status": "LỖI", "ly_do": "do_phan_giai_thap",
                         "thong_bao": f"Độ phân giải thấp, cần cạnh ngắn ≥ {MIN_CANH} px"})
            bad += 1
            continue
        kq = preprocess(p, layout["phieu" if m else "chu_so"])
        r = {"file": fn, "size": f"{size[0]}x{size[1]}" if size else "", "status": "OK" if kq.ok else "LỖI",
             "ly_do": kq.ly_do, "thong_bao": MA_LY_DO.get(kq.ly_do, ""),
             "huong_xoay": kq.huong_xoay if kq.huong_xoay is not None else "",
             "blur_score": f"{kq.blur_score:.4f}" if kq.blur_score is not None else ""}
        if kq.ok:
            r["sha256_anh_nan"] = hashlib.sha256(np.ascontiguousarray(kq.anh_nan).tobytes()).hexdigest()
            cv2.imencode(".jpg", kq.anh_nan, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(out / f"{p.stem}.jpg"))
        if r["status"] != "OK":
            bad += 1
        rows.append(r)

    report = out.parent / f"photo_report_{src.name}.csv"
    cols = ["file", "size", "status", "ly_do", "thong_bao", "huong_xoay", "blur_score", "sha256_anh_nan"]
    with report.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in cols} for r in rows)
    for r in rows:
        tb = "" if r["status"] == "OK" else f"TỪ CHỐI – {r['ly_do']} ({r['thong_bao']})"
        print(f"{r['file']:<18} {r.get('size', ''):>11}  {r['status']:<4} {tb}")
    tong = {}
    for r in rows:
        if r["status"] != "OK":
            tong[r["ly_do"]] = tong.get(r["ly_do"], 0) + 1
    print(f"\nTổng {len(rows)} ảnh đã kiểm, {bad} lỗi" + (f" ({', '.join(f'{k}: {v}' for k, v in tong.items())})" if tong
                                                     else "") + f". Báo cáo: {report}")
    if bo_qua:
        print(f"BỎ QUA {len(bo_qua)} ảnh tập TEST (không đọc; chỉ chạy ở đánh giá cuối với --xac-nhan-test): "
              f"{', '.join(bo_qua)}")
    print(f"Ảnh đã nắn (chỉ để xem) nằm trong {out} – mở vài ảnh để xem có thẳng không.")


if __name__ == "__main__":
    main()
