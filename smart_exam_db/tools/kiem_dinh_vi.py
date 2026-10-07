"""
kiem_dinh_vi.py - Kiểm khâu định vị 2 tầng của cv_engine/omr.py (Tuần 5, Phần A mốc A1; docs/ke_hoach_tuan5.md).

Chỉ dùng ảnh TRAIN 0001–0028 (Phần A không chạm val 0029–0034; test bị chặn). Ghi data/_eval/omr/dinh_vi/.

  python tools/kiem_dinh_vi.py thong-ke     # 56 ảnh thật: điểm khớp khối / hàng, độ duy nhất đỉnh, lệch lân cận, cờ
  python tools/kiem_dinh_vi.py dich-gia     # ảnh dịch giả: dịch cả trang đúng 1 khoảng cách ô (ngang 7 mm; dọc 11 mm,
                                            # 5,8 mm) và 2 / 3,5 / 4 mm -> mỗi hàng / cột: ĐÚNG hoặc GẮN CỜ; đếm "khớp nhầm
                                            # không cờ" (phải = 0)

"Đúng" của ảnh dịch giả: độ dịch tìm được = độ dịch của chính ảnh đó khi chưa dịch + độ dịch giả (sai ≤ 0,5 mm mỗi trục).
Đây là phép thử TƯƠNG ĐỐI (không cần biết vị trí thật); vị trí tuyệt đối đo độc lập ở tools/eval_omr.py (cách khác omr.py).
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402
from omr_du_lieu import anh_da_nan, ds_anh  # noqa: E402

OUT = ROOT / "data" / "_eval" / "omr" / "dinh_vi"
PX_MM = 25.4 / 300
SAI_MM = 0.5
DICH_GIA_MM = [(7, 0), (-7, 0), (0, 11), (0, -11), (0, 5.8), (0, -5.8),
               (2, 0), (-2, 0), (0, 2), (0, -2), (3.5, 0), (-3.5, 0), (0, 3.5), (0, -3.5),
               (4, 0), (-4, 0), (0, 4), (0, -4), (2, 2), (-3, 3)]


def dich_anh(anh: np.ndarray, dx_mm: float, dy_mm: float) -> np.ndarray:
    """Dịch cả trang (dx, dy) mm, phần lộ ra điền mức giấy (trung vị ảnh)."""
    M = np.float32([[1, 0, dx_mm / PX_MM], [0, 1, dy_mm / PX_MM]])
    return cv2.warpAffine(anh, M, (anh.shape[1], anh.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=int(np.median(anh)))


def cmd_thong_ke(L, mau) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, items = [], []
    for r in ds_anh("train"):
        nan, _ = anh_da_nan(r["anh"], L)
        t = time.perf_counter()
        kq = omr.dinh_vi(nan, L, mau)
        ms = (time.perf_counter() - t) * 1000
        for k, v in kq.khoi.items():
            rows.append({"anh": r["anh"], "dieu_kien": r["dieu_kien"], "khoi": k, "dx_mm": round(v.dich[0] * PX_MM, 3),
                         "dy_mm": round(v.dich[1] * PX_MM, 3), "diem": round(v.diem, 4),
                         "bien_duy_nhat": round(v.diem - v.diem_thu_hai, 4), "co": "|".join(v.co), "ms": round(ms)})
        for key in kq.dich:
            items.append({"anh": r["anh"], "dieu_kien": r["dieu_kien"], "phan_tu": key,
                          "dx_mm": round(kq.dich[key][0] * PX_MM, 3), "dy_mm": round(kq.dich[key][1] * PX_MM, 3),
                          "diem": round(kq.diem[key], 4), "lech_lan_can_mm": round(kq.lech[key] * PX_MM, 3),
                          "co": "|".join(kq.co[key])})
    for ten, ds in (("khoi_train.csv", rows), ("phan_tu_train.csv", items)):
        with (OUT / ten).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ds[0]))
            w.writeheader()
            w.writerows(ds)
    for k in ("dap_an", "sbd", "ma_de"):
        d = [x for x in rows if x["khoi"] == k]
        print(f"Khối {k:6s}: điểm min {min(x['diem'] for x in d):.3f} (ảnh {min(d, key=lambda x: x['diem'])['anh']}), "
              f"biên duy nhất min {min(x['bien_duy_nhat'] for x in d):.3f} "
              f"({min(d, key=lambda x: x['bien_duy_nhat'])['anh']}), |dịch| max "
              f"{max(max(abs(x['dx_mm']), abs(x['dy_mm'])) for x in d):.2f} mm, cờ {sum(bool(x['co']) for x in d)}")
    for loai, pre in (("hàng câu", "q"), ("cột chữ số", "")):
        d = [x for x in items if x["phan_tu"].startswith("q") == (pre == "q")]
        print(f"{loai}: {len(d)} lượt, điểm min {min(x['diem'] for x in d):.3f} "
              f"({min(d, key=lambda x: x['diem'])['anh']} {min(d, key=lambda x: x['diem'])['phan_tu']}), lệch lân cận max "
              f"{max(x['lech_lan_can_mm'] for x in d):.2f} mm "
              f"({max(d, key=lambda x: x['lech_lan_can_mm'])['anh']} {max(d, key=lambda x: x['lech_lan_can_mm'])['phan_tu']}), "
              f"|dịch| max {max(max(abs(x['dx_mm']), abs(x['dy_mm'])) for x in d):.2f} mm, gắn cờ {sum(bool(x['co']) for x in d)}")
    co = [x for x in items if x["co"]]
    for x in co[:20]:
        print("   CỜ", x["anh"], x["phan_tu"], x["co"])
    ms = [x["ms"] for x in rows[::3]]
    print(f"Thời gian dinh_vi: trung vị {np.median(ms):.0f} ms, max {max(ms)} ms. -> {OUT}")


def cmd_dich_gia(L, mau, gioi_han: int | None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tong = {"dung": 0, "co": 0, "nham_khong_co": 0, "bo_qua": 0}
    chi_tiet = []
    ds = ds_anh("train")[:gioi_han] if gioi_han else ds_anh("train")
    for r in ds:
        nan, _ = anh_da_nan(r["anh"], L)
        goc = omr.dinh_vi(nan, L, mau)
        for dx, dy in DICH_GIA_MM:
            kq = omr.dinh_vi(dich_anh(nan, dx, dy), L, mau)
            dem = {"dung": 0, "co": 0, "nham_khong_co": 0, "bo_qua": 0}
            nham = []
            for key in kq.dich:
                if goc.co[key]:
                    dem["bo_qua"] += 1                    # ảnh gốc đã không tin được phần tử này
                    continue
                mong = np.array(goc.dich[key]) + np.array([dx, dy]) / PX_MM
                sai = np.abs(np.array(kq.dich[key]) - mong).max() * PX_MM
                if sai <= SAI_MM:
                    dem["dung"] += 1
                elif kq.co[key]:
                    dem["co"] += 1
                else:
                    dem["nham_khong_co"] += 1
                    nham.append(f"{key}({sai:.1f}mm)")
            for k in tong:
                tong[k] += dem[k]
            chi_tiet.append({"anh": r["anh"], "dx_mm": dx, "dy_mm": dy, **dem, "nham": " ".join(nham)})
            if nham:
                print(f"   KHỚP NHẦM KHÔNG CỜ: {r['anh']} dịch ({dx}, {dy}) mm: {' '.join(nham[:8])}")
    with (OUT / "dich_gia_train.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(chi_tiet[0]))
        w.writeheader()
        w.writerows(chi_tiet)
    print("\nTheo độ dịch giả (tổng trên các ảnh): đúng / gắn cờ / KHỚP NHẦM KHÔNG CỜ")
    for dx, dy in DICH_GIA_MM:
        d = [x for x in chi_tiet if (x["dx_mm"], x["dy_mm"]) == (dx, dy)]
        print(f"  ({dx:5}, {dy:5}) mm: {sum(x['dung'] for x in d):5d} / {sum(x['co'] for x in d):5d} / "
              f"{sum(x['nham_khong_co'] for x in d):3d}")
    print(f"TỔNG ({len(ds)} ảnh × {len(DICH_GIA_MM)} độ dịch): đúng {tong['dung']}, gắn cờ {tong['co']}, "
          f"KHỚP NHẦM KHÔNG CỜ {tong['nham_khong_co']}, bỏ qua (gốc có cờ) {tong['bo_qua']} -> {OUT / 'dich_gia_train.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Kiểm định vị 2 tầng của omr.py (ảnh train)")
    ap.add_argument("lenh", choices=["thong-ke", "dich-gia"])
    ap.add_argument("--gioi-han", type=int, help="chỉ N ảnh đầu (thử nhanh)")
    a = ap.parse_args()
    L = nap_layout("phieu")
    mau = omr.nap_mau()
    if a.lenh == "thong-ke":
        cmd_thong_ke(L, mau)
    else:
        cmd_dich_gia(L, mau, a.gioi_han)


if __name__ == "__main__":
    main()
