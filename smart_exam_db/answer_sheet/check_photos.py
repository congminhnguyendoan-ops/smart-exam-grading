"""
check_photos.py - Kiểm tra nhanh ảnh vừa chụp: đặt tên đúng chưa, có mờ không, có tìm được
4 marker không. Chạy NGAY sau mỗi buổi chụp để chụp lại ảnh hỏng khi phiếu còn trong tay.

Quy ước đặt tên:  data/raw/0001_C1.jpg   (mã phiếu 4 số + điều kiện chụp C1..C4)
                  data/raw_digits/D001.jpg (trang thu chữ số)
Chạy:             python check_photos.py --dir ../data/raw
Kết quả:          in bảng OK / LỖI + ghi photo_report.csv, lưu ảnh đã nắn vào <dir>/_aligned/
"""
import argparse
import csv
import json
import os
import re

import cv2

from check_layout import align

HERE = os.path.dirname(os.path.abspath(__file__))
NAME_RE = re.compile(r"^(\d{4})_(C[1-4])\.(jpg|jpeg|png)$", re.I)
DIGIT_RE = re.compile(r"^(D\d{3})\.(jpg|jpeg|png)$", re.I)
MIN_BLUR = 100.0      # khớp system_settings.min_blur_score trong database


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(HERE, "..", "data", "raw"))
    a = ap.parse_args()
    sheet_layout = json.load(open(os.path.join(HERE, "output", "layout.json"), encoding="utf-8"))
    digit_layout = json.load(open(os.path.join(HERE, "output", "digit_sheet_layout.json"), encoding="utf-8"))
    aligned_dir = os.path.join(a.dir, "_aligned")
    os.makedirs(aligned_dir, exist_ok=True)

    rows, bad = [], 0
    for fn in sorted(os.listdir(a.dir)):
        path = os.path.join(a.dir, fn)
        if not os.path.isfile(path):
            continue
        m, md = NAME_RE.match(fn), DIGIT_RE.match(fn)
        if not (m or md):
            rows.append([fn, "", "", "LỖI", "Sai tên file (cần 0001_C1.jpg hoặc D001.jpg)"])
            bad += 1
            continue
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            rows.append([fn, "", "", "LỖI", "Không đọc được ảnh"])
            bad += 1
            continue
        h, w = img.shape
        blur = cv2.Laplacian(img, cv2.CV_64F).var()
        status, note = "OK", ""
        if min(h, w) < 1500:
            status, note = "LỖI", f"Độ phân giải thấp ({w}x{h}), cần cạnh ngắn >= 1500px"
        elif blur < MIN_BLUR:
            status, note = "LỖI", f"Ảnh mờ (blur={blur:.0f} < {MIN_BLUR:.0f})"
        else:
            try:
                al = align(img, sheet_layout if m else digit_layout)
                cv2.imwrite(os.path.join(aligned_dir, fn), al)
            except Exception as e:  # noqa: BLE001
                status, note = "LỖI", f"Không tìm đủ 4 marker ({e}) - chụp lại, đủ 4 góc trong khung"
        if status != "OK":
            bad += 1
        rows.append([fn, f"{w}x{h}", f"{blur:.0f}", status, note])

    with open(os.path.join(a.dir, "photo_report.csv"), "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows([["file", "size", "blur", "status", "note"]] + rows)
    for r in rows:
        print(f"{r[0]:<18} {r[1]:>11} blur={r[2]:>5}  {r[3]:<4} {r[4]}")
    print(f"\nTổng {len(rows)} ảnh, {bad} lỗi. Ảnh đã nắn nằm trong {aligned_dir} - mở vài ảnh để xem có thẳng không.")


if __name__ == "__main__":
    main()
