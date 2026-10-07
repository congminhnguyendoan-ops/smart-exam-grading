"""
tao_tham_chieu.py - Ảnh tham chiếu cho bộ kiểm thử tests/ (Tuần 4, Bước 6 – docs/ke_hoach_tuan4.md).

Ghi TRƯỚC khi sửa cv_engine/preprocessing.py ở Bước 6 (lệnh tự chặn nếu file đã bị sửa so với HEAD):
  - data/_eval/tham_chieu_kiem_thu/<ảnh>_anh_nan.png, <ảnh>_anh_chuan_hoa.png (PNG, không mất dữ liệu) cho các ảnh
    dev đại diện; mỗi ảnh phải có SHA-256 trùng vân tay v4 (anh_nan) và v5 (anh_chuan_hoa) thì mới ghi.
  - tham_chieu.json: SHA, ok, huong_xoay + phiên bản python / cv2 / numpy / nền tảng.
  - data/_eval/v4_verify/anh_nan_sha256_moi_truong.json: phiên bản môi trường của vân tay v4 (ghi bổ sung: vân tay
    ghi 07/10/2026 cùng venv; bằng chứng cùng môi trường = SHA chạy lại hôm nay trùng vân tay).
Vì sao cần ảnh, không chỉ SHA: SHA phụ thuộc phiên bản OpenCV / nền tảng. Khác phiên bản thì tests/ so CÓ DUNG SAI
(|Δ| ≤ 2 mức xám, ≥ 99,9% điểm ảnh khớp) – phải có ảnh mới đo được Δ.

Chạy (từ thư mục smart_exam_db/):  python tools/tao_tham_chieu.py
Chỉ ảnh dev; chỉ ghi data/_eval/.
"""
import csv
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_preprocessing import EVAL_DIR, ROOT, list_images, nap_layout_loai  # noqa: E402
import cv_engine.preprocessing as pp  # noqa: E402

OUT = EVAL_DIR / "tham_chieu_kiem_thu"
VAN_TAY = EVAL_DIR / "v4_verify" / "anh_nan_sha256.csv"
V5 = EVAL_DIR / "v5_chuan_hoa" / "so_pixel_dev.csv"
# Đại diện: C1 · C2 tối · C3 nghiêng nhất · C4 vệt bóng · ảnh nằm ngang (huong_xoay 90) · giấy cong · trang chữ số
ANH = ("0001_C1", "0005_C2", "0015_C3", "0032_C4", "0006_C2", "0014_C2", "D003")


def moi_truong() -> dict:
    return {"python": sys.version.split()[0], "cv2": cv2.__version__, "numpy": np.__version__,
            "nen_tang": platform.platform(), "may": platform.machine()}


def sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def main() -> None:
    if subprocess.run(["git", "status", "--porcelain", "--", "cv_engine/preprocessing.py"], cwd=ROOT,
                      capture_output=True, text=True, check=True).stdout.strip():
        sys.exit("cv_engine/preprocessing.py đã bị sửa so với HEAD – tham chiếu phải ghi trên code v5.")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()
    v4 = {r["anh"]: r for r in csv.DictReader(VAN_TAY.open(encoding="utf-8-sig"))}
    v5 = {r["anh"]: r for r in csv.DictReader(V5.open(encoding="utf-8-sig"))}
    xs = {x.ten: x for x in list_images("dev")}
    OUT.mkdir(parents=True, exist_ok=True)
    mt = moi_truong()
    ds = {}
    for t in ANH:
        x = xs[t]
        kq = pp.preprocess(x.duong_dan, nap_layout_loai(x.loai))
        s_nan, s_ch = sha(kq.anh_nan), sha(kq.anh_chuan_hoa)
        if s_nan != v4[t]["sha256"] or s_ch != v5[t]["sha256_anh_chuan_hoa"]:
            sys.exit(f"{t}: SHA không trùng vân tay v4/v5 – môi trường hoặc code đã đổi, không ghi tham chiếu.")
        for ten, a in (("anh_nan", kq.anh_nan), ("anh_chuan_hoa", kq.anh_chuan_hoa)):
            p = OUT / f"{t}_{ten}.png"
            cv2.imencode(".png", a, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tofile(str(p))
            doc_lai = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_UNCHANGED)
            if sha(doc_lai) != sha(a):
                sys.exit(f"{p}: đọc lại PNG không giống từng byte")
        ds[t] = {"loai": x.loai, "dieu_kien": x.dieu_kien, "ok": bool(kq.ok), "huong_xoay": kq.huong_xoay,
                 "sha256_anh_nan": s_nan, "sha256_anh_chuan_hoa": s_ch}
        print(f"  {t}: ok, huong_xoay {kq.huong_xoay}°, SHA trùng v4/v5 -> PNG")
    (OUT / "tham_chieu.json").write_text(json.dumps(
        {"git_head": head, "moi_truong": mt, "anh": ds,
         "ghi_chu": "anh_nan trùng vân tay v4 (data/_eval/v4_verify/anh_nan_sha256.csv), anh_chuan_hoa trùng v5 "
                    "(data/_eval/v5_chuan_hoa/so_pixel_dev.csv)"}, ensure_ascii=False, indent=1), encoding="utf-8")
    (EVAL_DIR / "v4_verify" / "anh_nan_sha256_moi_truong.json").write_text(json.dumps(
        {"moi_truong": mt, "ghi_chu": "Ghi bổ sung ở Bước 6 (07/10/2026). Vân tay anh_nan_sha256.csv ghi cùng ngày, cùng "
         ".venv; bằng chứng cùng môi trường: tools/tao_tham_chieu.py chạy lại 7 ảnh đại diện ra SHA trùng từng byte."},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(ds)} ảnh, HEAD {head}, cv2 {mt['cv2']}, numpy {mt['numpy']} -> {OUT}")


if __name__ == "__main__":
    main()
