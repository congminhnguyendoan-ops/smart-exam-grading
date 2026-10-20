"""
eval_ocr.py - Đánh giá ĐỘC LẬP đường đọc SBD / mã đề hai kênh (Tuần 6 Phần C, Bước 3–5). CHỈ gọi cv_engine.preprocessing, omr.doc_phieu,
ocr.doc_chu_so, ocr.doi_chieu_dinh_danh (pytest kiểm điều này): không import công cụ huấn luyện, không đọc cache cắt ô.
Nhãn chữ viết tay (SBD, mã đề) lấy từ data/ground_truth.csv, CHỈ cho các phiếu thuộc tập được chọn.

  python tools/eval_ocr.py run --tap dev                 # phiếu 0001–0028 (56 ảnh): số đo đầy đủ -> data/_eval/ocr/eval_<tap>.json + .md
  python tools/eval_ocr.py run --tap val --xac-nhan-val  # 0029–0034 (12 ảnh): CHỈ chạy khi đã đăng ký trước (docs/ke_hoach_tuan6.md mục 11)
  (tập test 0035–0040: không có lệnh ở công cụ này – đánh giá cuối là bước riêng, có chan_test)

Số đo: T3 = độ đúng chữ số CNN (argmax, người LẠ chỉ đúng với dev khi mô hình chưa thấy phiếu; xem hạn chế trong kế hoạch),
T4 = % ảnh có SBD hoặc mã đề bị gắn "cần xem", lỗi im lặng mức trường (nhận mà sai so với chữ VIẾT TAY thật) – bắt buộc 0,
CP 95%, theo người viết và C1–C4, thời gian `doc_chu_so`. SBD / mã đề "có trong danh sách" = đúng (kỳ thi mô phỏng đủ thí sinh).
"""
import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine import ocr, omr  # noqa: E402
from cv_engine.preprocessing import nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_TRAIN, PHIEU_VAL, ma_phieu, nguoi_viet  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "_eval" / "ocr"
TAP = {"dev": PHIEU_TRAIN, "val": PHIEU_VAL}


def cp_ci(k: int, n: int, a: float = 0.05):
    from scipy.stats import beta
    return (0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1)), 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k)))


def doc_nhan(tap) -> dict:
    """{'0001': (sbd viết tay, mã đề viết tay)} CHỈ cho phiếu của `tap`; dòng phiếu khác bỏ ngay khi đọc."""
    out = {}
    with (DATA / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if int(r["sheet_id"]) in tap:
                out[r["sheet_id"]] = (r["sbd"], r["exam_code"])
    return out


def luoi_html(o: list) -> str:
    """Lưới HTML để xem bằng mắt: mỗi ảnh một hàng 9 ô = ảnh ô viết tay + chữ số bubble + chữ số máy đọc (%); ô cần xem tô vàng."""
    import base64

    import cv2
    h = ["<meta charset=utf-8><style>body{font:13px sans-serif}td{border:1px solid #ccc;text-align:center;padding:2px}.cx{background:#fff1d6}"
         "img{height:64px;image-rendering:pixelated}</style><h3>eval_ocr --xem</h3>"]
    for r in o:
        if "cells" not in r:
            continue
        h.append(f"<p><b>{r['anh']}</b> · SBD {'chắc' if r['sbd_chac'] else 'CẦN XEM'} {r['sbd_ly']} · mã đề {'chắc' if r['ma_chac'] else 'CẦN XEM'} {r['ma_ly']}</p><table><tr>")
        for c in r["cells"]:
            b = base64.b64encode(cv2.imencode(".png", c["anh"])[1].tobytes()).decode()
            h.append(f"<td class='{'cx' if c['cx'] else ''}'><img src='data:image/png;base64,{b}'><br>ô tô <b>{c['bubble']}</b><br>máy <b>{c['cnn']}</b> {c['p']:.0%}</td>")
        h.append("</tr></table>")
    return "\n".join(h)


def chay(ten_tap: str, dau_ra: bool = True, xem: bool = False) -> dict:
    tap = TAP[ten_tap]
    nhan = doc_nhan(tap)
    anhs = sorted(p for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in tap)
    lay, mo_om, mo_oc = nap_layout("phieu"), omr.nap_mo_hinh(), ocr.nap_mo_hinh_ocr()
    rows, ms = [], []
    for p in anhs:
        sbd_t, ma_t = nhan[f"{ma_phieu(p.stem):04d}"]
        kq = preprocess(str(p), lay)
        r = {"anh": p.stem, "nguoi": nguoi_viet(p.stem), "dk": p.stem.split("_")[1], "truth_sbd": sbd_t, "truth_ma": ma_t}
        if not kq.ok:
            rows.append({**r, "tu_choi": kq.ly_do})
            continue
        res = omr.doc_phieu(kq, lay, mo_om)
        hv = ocr.doc_chu_so(kq, lay, mo_oc)
        ms.append(hv.thoi_gian_ms)
        dc = ocr.doi_chieu_dinh_danh(res, hv, True, True, mo_hinh=mo_oc)
        r.update(bubble_sbd=res.sbd, bubble_ma=res.ma_de, cnn_sbd="".join(c.chu_so for c in hv.sbd), cnn_ma="".join(c.chu_so for c in hv.ma_de),
                 sbd_chac=bool(dc["sbd"][1]), ma_chac=bool(dc["ma_de"][1]), sbd_ly=list(dc["sbd"][2]), ma_ly=list(dc["ma_de"][2]),
                 sbd_dung=dc["sbd"][0] == sbd_t, ma_dung=dc["ma_de"][0] == ma_t,
                 sbd_nhan_sai=bool(dc["sbd"][1] and res.sbd != sbd_t), ma_nhan_sai=bool(dc["ma_de"][1] and res.ma_de != ma_t),
                 chu_so_cnn_dung=sum(a == b for a, b in zip(r_cnn(hv), sbd_t + ma_t)), ms=hv.thoi_gian_ms)
        if xem:
            bub = list(res.sbd) + list(res.ma_de)
            cx = [not c.chac for c in dc["cot"]["sbd"]] + [not c.chac for c in dc["cot"]["ma_de"]]
            r["cells"] = [{"anh": c.anh_o, "bubble": b, "cnn": c.chu_so, "p": c.p, "cx": x} for c, b, x in zip(hv.sbd + hv.ma_de, bub, cx)]
        rows.append(r)
        if dau_ra:
            print(f"{p.stem}: SBD {'chắc' if r['sbd_chac'] else 'cần xem'} {r['sbd_ly']} · mã đề {'chắc' if r['ma_chac'] else 'cần xem'} {r['ma_ly']}")
    ok = [r for r in rows if "tu_choi" not in r]
    n_cs = 9 * len(ok)
    k_cs = sum(r["chu_so_cnn_dung"] for r in ok)
    gan = [r for r in ok if not (r["sbd_chac"] and r["ma_chac"])]
    il = [r["anh"] for r in ok if r["sbd_nhan_sai"] or r["ma_nhan_sai"]]
    tom = {"tap": ten_tap, "anh": len(rows), "tu_choi": len(rows) - len(ok), "mo_hinh_xuat_tu_commit": ocr.nap_mo_hinh_ocr().sieu_du_lieu.get("git_head"),
           "T3_chu_so_dung": k_cs, "T3_n": n_cs, "T3": round(k_cs / n_cs, 4) if n_cs else None, "T3_ci95": [round(v, 4) for v in cp_ci(k_cs, n_cs)] if n_cs else None,
           "T4_gan": len(gan), "T4_n": len(ok), "T4": round(len(gan) / len(ok), 4) if ok else None,
           "T4_ci95": [round(v, 4) for v in cp_ci(len(gan), len(ok))] if ok else None,
           "T4_can_xem_thua": sum(1 for r in gan if r["sbd_dung"] and r["ma_dung"]),
           "loi_im_lang_truong_sbd": sum(r["sbd_nhan_sai"] for r in ok), "loi_im_lang_truong_ma": sum(r["ma_nhan_sai"] for r in ok), "loi_im_lang_anh": il,
           "sbd_chac": sum(r["sbd_chac"] for r in ok), "ma_chac": sum(r["ma_chac"] for r in ok),
           "ms_trung_vi": round(statistics.median(ms), 1) if ms else None, "ms_max": round(max(ms), 1) if ms else None}
    n_nhan = tom["sbd_chac"] + tom["ma_chac"]
    tom["loi_im_lang_ci95_tren_so_truong_nhan"] = round(cp_ci(tom["loi_im_lang_truong_sbd"] + tom["loi_im_lang_truong_ma"], n_nhan or 1)[1], 4)
    for khoa, f in (("nguoi", lambda r: str(r["nguoi"])), ("dieu_kien", lambda r: r["dk"])):
        g = defaultdict(lambda: [0, 0, 0])
        for r in ok:
            x = g[f(r)]
            x[0] += 1
            x[1] += not (r["sbd_chac"] and r["ma_chac"])
            x[2] += r["chu_so_cnn_dung"]
        tom[f"theo_{khoa}"] = {k: {"anh": v[0], "T4": round(v[1] / v[0], 4), "T3": round(v[2] / (9 * v[0]), 4)} for k, v in sorted(g.items())}
    ly = defaultdict(int)
    for r in ok:
        for m in r["sbd_ly"] + r["ma_ly"]:
            ly[m] += 1
    tom["ly_do"] = dict(ly)
    return {"tom_tat": tom, "anh": rows}


def r_cnn(hv):
    return [c.chu_so for c in hv.sbd] + [c.chu_so for c in hv.ma_de]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["run"])
    ap.add_argument("--tap", choices=list(TAP), required=True)
    ap.add_argument("--xac-nhan-val", action="store_true", help="bắt buộc cho --tap val (đã đăng ký trước, chạy MỘT lần)")
    ap.add_argument("--xem", action="store_true", help="ghi thêm data/_eval/ocr/xem_<tap>.html (lưới ảnh ô viết tay để xem bằng mắt)")
    a = ap.parse_args()
    if a.tap == "val" and not a.xac_nhan_val:
        sys.exit("DỪNG: tập val 0029–0034 chỉ chạy sau khi đăng ký trước và có lệnh 'chạy val' của người dùng (thêm --xac-nhan-val).")
    kq = chay(a.tap, xem=a.xem)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.xem:
        (OUT / f"xem_{a.tap}.html").write_text(luoi_html(kq["anh"]), encoding="utf-8")
    for r in kq["anh"]:
        r.pop("cells", None)
    (OUT / f"eval_{a.tap}.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    t = kq["tom_tat"]
    print(json.dumps(t, ensure_ascii=False, indent=1))
    sys.exit(0 if not t["loi_im_lang_anh"] else 1)


if __name__ == "__main__":
    main()
