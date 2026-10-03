"""
kiem_load_image.py - Kiểm tra load_image() của cv_engine/preprocessing.py (Tuần 4, Bước 2).

Lệnh:
  exif      (a) Tạo ảnh thử EXIF Orientation 1/3/6/8 từ data/raw/0001_C1.jpg (phiếu dev, C1) vào
            data/_eval/_exif/: điểm ảnh lưu bị xoay NGƯỢC, thẻ EXIF = k -> đọc đúng phải ra lại ảnh gốc.
            JPEG mã hoá lại nên không thể giống hệt: đạt = cùng kích thước + sai khác trung bình < 2 mức xám,
            đồng thời mọi chiều sai phải khác xa (chứng minh phép đo phân biệt được).
            Kèm: ca HEIC thật (IMG_4214.HEIC = 0001_C1, tra mapping.csv) – bắt lỗi xoay 2 lần;
            đường dẫn có dấu tiếng Việt; file không tồn tại / file hỏng -> LoiDocAnh.
  so-pixel  (b) 78 ảnh dev: load_image(p) phải GIỐNG TỪNG ĐIỂM ẢNH cv2.imdecode(np.fromfile(p), GRAYSCALE)
            -> data/_eval/v2_load/so_pixel_dev.csv (finalize --ke-thua đọc file này).

Chỉ ghi vào data/_eval/. Không đụng data/raw/, data/raw_heic/, data/raw_digits/.
Chạy (từ thư mục smart_exam_db/):
  python tools/kiem_load_image.py exif
  python tools/kiem_load_image.py so-pixel
"""
import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

ROOT = Path(__file__).resolve().parent.parent          # smart_exam_db/
DATA = ROOT / "data"
EVAL_DIR = DATA / "_eval"
EXIF_DIR = EVAL_DIR / "_exif"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine.preprocessing import LoiDocAnh, ap_exif_orientation, doc_anh, load_image  # noqa: E402
from eval_preprocessing import ghi_csv, list_images  # noqa: E402

register_heif_opener()

ANH_GOC = "0001_C1"
MAD_DAT = 2.0            # sai khác trung bình (mức xám) tối đa khi đọc đúng chiều (JPEG mã hoá lại q=95)
MAD_SAI_MIN = 20.0       # mọi chiều SAI phải khác ít nhất bấy nhiêu (nếu cùng kích thước)
# Điểm ảnh lưu trong file = ảnh gốc xoay NGƯỢC với phép xoay mà thẻ EXIF yêu cầu.
# Viết độc lập với ap_exif_orientation() (cv2.rotate thay vì np.rot90) để không tự kiểm chính mình.
LUU_NGUOC = {
    1: lambda a: a,
    3: lambda a: cv2.rotate(a, cv2.ROTATE_180),
    6: lambda a: cv2.rotate(a, cv2.ROTATE_90_COUNTERCLOCKWISE),     # xem: xoay 90° theo chiều kim đồng hồ
    8: lambda a: cv2.rotate(a, cv2.ROTATE_90_CLOCKWISE),            # xem: xoay 90° ngược chiều kim đồng hồ
}


def doc_cv2(p: Path, flags=cv2.IMREAD_GRAYSCALE) -> np.ndarray:
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), flags)


def mad(a: np.ndarray, b: np.ndarray):
    """Sai khác tuyệt đối trung bình; None nếu khác kích thước."""
    if a.shape != b.shape:
        return None
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def heic_cua(ten: str) -> Path:
    for r in csv.DictReader((DATA / "_prepare" / "mapping.csv").open(encoding="utf-8-sig")):
        if r["new_name"] == f"{ten}.jpg":
            return DATA / "raw_heic" / r["heic_name"]
    sys.exit(f"Không thấy {ten}.jpg trong mapping.csv")


def nho(g: np.ndarray, h=420) -> np.ndarray:
    return cv2.resize(g, (round(g.shape[1] * h / g.shape[0]), h), interpolation=cv2.INTER_AREA)


def ghi_jpg(path: Path, g: np.ndarray, q=90) -> None:
    ok, buf = cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, q])
    buf.tofile(path)                                     # tofile: an toàn với đường dẫn Unicode


def cmd_exif(_a) -> None:
    EXIF_DIR.mkdir(parents=True, exist_ok=True)
    src = DATA / "raw" / f"{ANH_GOC}.jpg"
    goc = doc_cv2(src)
    rgb = cv2.cvtColor(doc_cv2(src, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    print(f"Ảnh gốc: {src.name} {goc.shape[1]}x{goc.shape[0]} (rộng x cao)\n")
    print(f"{'ca':12s} {'lưu (rxc)':>11s} {'EXIF đọc':>8s} {'ra (rxc)':>11s} {'MAD đúng':>8s} "
          f"{'MAD sai nhỏ nhất':>16s} {'PIL':>6s} {'OpenCV':>6s}  kết luận")
    rows, xem = [], []
    for k, luu in LUU_NGUOC.items():
        p = EXIF_DIR / f"exif_{k}.jpg"
        stored = luu(rgb)
        exif = Image.Exif()
        exif[274] = k
        Image.fromarray(stored).save(p, "JPEG", quality=95, exif=exif.tobytes())

        ra, ori = doc_anh(p)
        m = mad(ra, goc)
        # chiều sai: áp mọi giá trị EXIF khác k lên điểm ảnh đã lưu
        luu_xam = doc_cv2(p, cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
        sai = [mad(ap_exif_orientation(luu_xam, k2), goc) for k2 in range(1, 9) if k2 != k]
        sai_cung_co = [x for x in sai if x is not None]
        m_sai = min(sai_cung_co) if sai_cung_co else None
        # đối chứng độc lập: Pillow exif_transpose và OpenCV tự xoay EXIF (kiểm chính file thử)
        with Image.open(p) as im:
            m_pil = mad(cv2.cvtColor(np.asarray(ImageOps.exif_transpose(im).convert("RGB")), cv2.COLOR_RGB2GRAY), goc)
        m_cv = mad(doc_cv2(p), goc)
        dat = (ori == k and m is not None and m < MAD_DAT and (m_sai is None or m_sai > MAD_SAI_MIN))
        rows.append({"ca": f"exif_{k}", "exif_ghi": k, "exif_doc": ori,
                     "luu_rong": stored.shape[1], "luu_cao": stored.shape[0], "ra_rong": ra.shape[1], "ra_cao": ra.shape[0],
                     "mad_dung": m if m is not None else "", "mad_sai_min": m_sai if m_sai is not None else "",
                     "mad_pil": m_pil if m_pil is not None else "", "mad_opencv": m_cv if m_cv is not None else "",
                     "dat": int(dat)})
        f = lambda x: f"{x:.2f}" if x is not None else "khác cỡ"
        print(f"exif_{k:<7d} {stored.shape[1]:>5d}x{stored.shape[0]:<5d} {ori:>8d} {ra.shape[1]:>5d}x{ra.shape[0]:<5d} "
              f"{f(m):>8s} {f(m_sai):>16s} {f(m_pil):>6s} {f(m_cv):>6s}  {'ĐẠT' if dat else 'KHÔNG ĐẠT'}")
        xem.append((f"exif_{k}", ra))

    # ---- ca HEIC thật
    heic = heic_cua(ANH_GOC)
    with Image.open(heic) as im:
        exif_heic = im.getexif().get(274)
        info_ori = im.info.get("original_orientation")
    ra, ori = doc_anh(heic)
    m = mad(ra, goc)
    dat = m is not None and m < MAD_DAT * 2           # JPG gốc được mã hoá từ HEIC này (q mặc định) -> nới gấp đôi
    rows.append({"ca": f"heic {heic.name}", "exif_ghi": info_ori if info_ori is not None else "",
                 "exif_doc": ori, "luu_rong": "", "luu_cao": "", "ra_rong": ra.shape[1], "ra_cao": ra.shape[0],
                 "mad_dung": m if m is not None else "", "mad_sai_min": "", "mad_pil": "", "mad_opencv": "", "dat": int(dat)})
    m_txt = f"{m:.2f}" if m is not None else "KHÁC CỠ (xoay sai)"
    print(f"\nHEIC thật {heic.name}: Orientation trong EXIF khi mở = {exif_heic}, 'original_orientation' = {info_ori}; "
          f"ra {ra.shape[1]}x{ra.shape[0]}, MAD so với {ANH_GOC}.jpg = {m_txt}")
    print(f"  -> {'ĐẠT' if dat else 'KHÔNG ĐẠT'} (ngưỡng {MAD_DAT * 2})")
    xem.append(("HEIC", ra))
    xem.insert(0, ("gốc", goc))

    # ---- đường dẫn Unicode
    p_vn = EXIF_DIR / "ảnh_thử_đường_dẫn_tiếng_việt.jpg"
    p_vn.write_bytes((EXIF_DIR / "exif_6.jpg").read_bytes())
    m = mad(load_image(p_vn), goc)
    imread_none = cv2.imread(str(p_vn)) is None
    dat_vn = m is not None and m < MAD_DAT
    print(f"\nĐường dẫn có dấu: load_image MAD = {m:.2f} -> {'ĐẠT' if dat_vn else 'KHÔNG ĐẠT'}; "
          f"cv2.imread trả None: {imread_none} (lý do không dùng cv2.imread)")
    rows.append({"ca": "duong_dan_tieng_viet", "exif_doc": 6, "mad_dung": m, "dat": int(dat_vn)})

    # ---- file không đọc được
    hong = EXIF_DIR / "hong.jpg"
    hong.write_bytes(b"day khong phai anh JPEG")
    for ten, p in (("file_khong_ton_tai", EXIF_DIR / "khong_co.jpg"), ("file_hong", hong)):
        try:
            load_image(p)
            ok, msg = False, "không ném lỗi"
        except LoiDocAnh as e:
            ok, msg = True, f"LoiDocAnh: {e}"
        print(f"{ten}: {'ĐẠT' if ok else 'KHÔNG ĐẠT'} ({msg})")
        rows.append({"ca": ten, "dat": int(ok)})

    cols = ["ca", "exif_ghi", "exif_doc", "luu_rong", "luu_cao", "ra_rong", "ra_cao",
            "mad_dung", "mad_sai_min", "mad_pil", "mad_opencv", "dat"]
    ghi_csv(EXIF_DIR / "ket_qua.csv", [{c: r.get(c, "") for c in cols} for r in rows])
    # ảnh xem bằng mắt: mọi ảnh đọc ra phải đứng thẳng như ảnh gốc
    tiles = []
    for ten, g in xem:
        t = cv2.cvtColor(nho(g), cv2.COLOR_GRAY2BGR)
        cv2.putText(t, ten, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        tiles.append(t)
    ghi_jpg(EXIF_DIR / "xem.jpg", np.hstack(tiles))
    n_dat = sum(r["dat"] for r in rows)
    print(f"\nTổng: {n_dat}/{len(rows)} ca ĐẠT. Đã ghi {EXIF_DIR / 'ket_qua.csv'}, {EXIF_DIR / 'xem.jpg'}")


def cmd_so_pixel(_a) -> None:
    out = EVAL_DIR / "v2_load"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for anh in list_images("dev"):
        a, ori = doc_anh(anh.duong_dan)
        b = doc_cv2(anh.duong_dan)
        cung_co = a.shape == b.shape
        khac = int(np.count_nonzero(a != b)) if cung_co else a.size
        rows.append({"anh": anh.ten, "dieu_kien": anh.dieu_kien, "rong": a.shape[1], "cao": a.shape[0],
                     "cung_kich_thuoc": int(cung_co), "exif_orientation": ori, "so_diem_khac": khac,
                     "khac_max": int(np.abs(a.astype(np.int16) - b).max()) if cung_co else ""})
    ghi_csv(out / "so_pixel_dev.csv", rows)
    giong = [r for r in rows if r["so_diem_khac"] == 0]
    from collections import Counter
    print(f"{len(giong)}/{len(rows)} ảnh dev giống từng điểm ảnh với cv2.imdecode(GRAYSCALE). "
          f"EXIF Orientation: {dict(Counter(r['exif_orientation'] for r in rows))}")
    for r in rows:
        if r["so_diem_khac"]:
            print(f"  KHÁC: {r['anh']} – {r['so_diem_khac']} điểm, lệch max {r['khac_max']}")
    print(f"Đã ghi {out / 'so_pixel_dev.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Kiểm tra load_image() (Tuần 4, Bước 2)")
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("exif", help="(a) ảnh thử EXIF 1/3/6/8 + HEIC thật + đường dẫn Unicode + file hỏng")
    sub.add_parser("so-pixel", help="(b) 78 ảnh dev: load_image giống từng điểm ảnh cv2.imdecode")
    a = ap.parse_args()
    {"exif": cmd_exif, "so-pixel": cmd_so_pixel}[a.lenh](a)


if __name__ == "__main__":
    main()
