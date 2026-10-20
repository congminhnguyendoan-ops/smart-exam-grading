"""
kiem_vi_tri_eval.py - Tuần 5 PHẦN B1b: kiểm chính PHÉP ĐO VỊ TRÍ ĐỘC LẬP của eval_omr.py bằng ảnh dịch giả (nợ #13).

eval_omr.vi_tri_doc_lap đo vị trí từng hàng / cột bằng phaseCorrelate + tâm vòng tròn in sẵn (khác omr.dinh_vi). Nếu phép đo đó tự khớp
nhầm thì cờ "vị trí đáng ngờ" của eval vô nghĩa. Ở đây dịch ảnh đã nắn (train, ảnh đệm) một khoảng biết trước rồi đo lại:
  Δ = đo(ảnh dịch) − đo(ảnh gốc) phải ≈ khoảng dịch. Mỗi (ảnh, độ dịch) xếp: ĐÚNG (mọi phần tử |Δ − dịch| <= 0,3 mm) /
  DỪNG (eval tự ném RuntimeError – an toàn) / SAI IM LẶNG (đo ra khác mà không báo – lỗ hổng của phép đo).
Chỉ ảnh train 0001–0028. Không dùng nhãn.

  python tools/kiem_vi_tri_eval.py   -> data/_eval/omr/kiem_vi_tri_eval.json + .md
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "answer_sheet"))
import eval_omr as E  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402
from omr_du_lieu import anh_da_nan, ds_anh  # noqa: E402

OUT = ROOT / "data" / "_eval" / "omr"
SAI_SO_MM = 0.3
# (dx, dy) mm: dưới nửa chu kỳ, gần nửa chu kỳ, và ĐÚNG một chu kỳ ô (ngang 7, dọc 11, bubble dọc 5,8) – ca khớp nhầm kinh điển
DICH = [(0.5, 0), (2.0, 0), (3.5, 0), (4.0, 0), (-4.0, 0), (7.0, 0), (0, 0.5), (0, 2.0), (0, 3.5), (0, 5.0), (0, -5.0), (0, 5.8), (0, 11.0),
        (2.0, 2.0), (-3.0, 3.0)]


def dich_anh(a: np.ndarray, dx_mm: float, dy_mm: float, px_mm: float) -> np.ndarray:
    M = np.float32([[1, 0, dx_mm / px_mm], [0, 1, dy_mm / px_mm]])
    return cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def chay(so_anh_moi_dk: int = 2) -> dict:
    L = nap_layout("phieu")
    px_mm = 25.4 / L["dpi"]
    mau = E._mau_pdf(L)
    rows = ds_anh("train")
    chon, dem = [], {}
    for r in rows:
        if dem.get(r["dieu_kien"], 0) < so_anh_moi_dk:
            dem[r["dieu_kien"]] = dem.get(r["dieu_kien"], 0) + 1
            chon.append(r["anh"])
    kq = {}
    for ten in chon:
        nan, _ = anh_da_nan(ten, L)
        goc = E.vi_tri_doc_lap(nan, L, mau)
        for dx, dy in DICH:
            khoa = f"{dx:+g},{dy:+g}"
            try:
                m = E.vi_tri_doc_lap(dich_anh(nan, dx, dy, px_mm), L, mau)
            except RuntimeError as e:
                kq.setdefault(khoa, {})[ten] = {"loai": "dung_lai", "ly_do": str(e)[:80]}
                continue
            sai = max(max(abs((m[k][0] - goc[k][0]) - dx), abs((m[k][1] - goc[k][1]) - dy)) for k in goc)
            n_sai = sum(max(abs((m[k][0] - goc[k][0]) - dx), abs((m[k][1] - goc[k][1]) - dy)) > SAI_SO_MM for k in goc)
            kq.setdefault(khoa, {})[ten] = {"loai": "dung" if n_sai == 0 else "sai_im_lang", "sai_max_mm": round(sai, 3), "n_phan_tu_sai": n_sai}
        print(f"{ten} xong")
    L_md = ["# B1b – kiểm phép đo vị trí độc lập của eval_omr bằng ảnh dịch giả",
            f"{len(chon)} ảnh train ({', '.join(chon)}) × {len(DICH)} độ dịch (dx, dy mm). ĐÚNG = mọi hàng / cột |Δ − dịch| ≤ {SAI_SO_MM} mm; "
            "DỪNG = eval tự từ chối (RuntimeError); SAI IM LẶNG = đo sai mà không báo.", "",
            "| dịch (dx, dy) mm | đúng | dừng lại | SAI IM LẶNG | sai lớn nhất (mm) |", "|---|---|---|---|---|"]
    tong = {"dung": 0, "dung_lai": 0, "sai_im_lang": 0}
    for khoa, v in kq.items():
        c = {k: sum(x["loai"] == k for x in v.values()) for k in tong}
        for k in tong:
            tong[k] += c[k]
        mx = max([x.get("sai_max_mm", 0) for x in v.values()] + [0])
        L_md.append(f"| {khoa} | {c['dung']} | {c['dung_lai']} | {c['sai_im_lang']} | {mx} |")
    L_md += ["", f"**Tổng: đúng {tong['dung']} · dừng lại {tong['dung_lai']} · SAI IM LẶNG {tong['sai_im_lang']}** (trên {sum(tong.values())} lượt)."]
    (OUT / "kiem_vi_tri_eval.md").write_text("\n".join(L_md) + "\n", encoding="utf-8")
    (OUT / "kiem_vi_tri_eval.json").write_text(json.dumps({"tong": tong, "chi_tiet": kq}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L_md))
    return {"tong": tong, "chi_tiet": kq}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    chay()
