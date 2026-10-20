"""
eval_omr.py - Đánh giá ĐỘC LẬP cv_engine/omr.py (Tuần 5; docs/ke_hoach_tuan5.md mục 2, 3).

Độc lập (như eval Tuần 4): KHÔNG import luật, ngưỡng, định vị, đặc trưng hay dự đoán của omr.py – chỉ gọi API công khai
omr.doc_phieu / omr.nap_mo_hinh (pytest kiểm điều này). Có:
  - bộ đọc nhãn riêng: tự phân tích mã ground_truth.csv (chữ hoa rõ / chữ thường mờ / 2 chữ / '-'), đối chiếu chéo với
    cell_labels.csv – lệch nhau thì DỪNG;
  - đo vị trí riêng: độ dịch thô cả khối bằng cv2.phaseCorrelate với trang mẫu render từ PDF (không dùng PNG mẫu của omr),
    rồi tâm từng VÒNG TRÒN in sẵn bằng nhân vành trên bản đồ cạnh, bám theo hàng / cột; so với dich_chuyen_mm omr báo ra –
    lệch > 0,5 mm = "vị trí đáng ngờ";
  - bộ đếm riêng: lỗi nặng / nhẹ, cần xem cần thiết / thừa, ma trận nhầm lẫn, F1 faint + CI bootstrap theo phiếu.

Phương pháp: 'm0' (models/omr_m0.json) và 'm1' (OOF: ảnh fold k đọc bằng data/_omr/mo_hinh_fold/omr_m1_fold{k}.json – mô hình
không thấy phiếu của ảnh đó). Phần A: chỉ --split train (56 ảnh 0001–0028). val cần --cho-phep-val (Phần B); test bị chặn.

  python tools/eval_omr.py run --phuong-phap m0
  python tools/eval_omr.py run --phuong-phap m1
  python tools/eval_omr.py report                 # bảng M0 vs M1 theo C1–C4 -> data/_eval/omr/bao_cao_phan_a.md + HTML xem bằng mắt
"""
import argparse
import csv
import html
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "answer_sheet"))
from cv_engine import omr  # noqa: E402  (CHỈ dùng omr.doc_phieu, omr.nap_mo_hinh)
from cv_engine.preprocessing import nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_TEST, PHIEU_TRAIN, PHIEU_VAL, chan_test  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "_eval" / "omr"
MO_HINH = {"m0": lambda fold: ROOT / "models" / "omr_m0.json",
           "m1": lambda fold: DATA / "_omr" / "mo_hinh_fold" / f"omr_m1_fold{fold}.json"}
TEN_PP = {"m0": "M0 (ngưỡng cố định)", "m1": "M1 (logistic, OOF 7-fold)"}
DIEU_KIEN = ("C1", "C2", "C3", "C4")
LOP = ("blank", "faint", "filled")
SEED, SO_BOOT = 2026, 1000
VI_TRI_SAI_MM = 0.5
CA_THU = [("0019", 24, "C"), ("0020", 33, "C"), ("0033", 4, "C")]     # 0033 thuộc val – Phần A bỏ qua


# ------------------------------------------------------------------------------------------------ nhãn (bộ đọc riêng)
def giai_ma(code: str) -> dict:
    """Mã câu ground_truth -> {ô: 'filled'/'faint'} (ô không có = trống)."""
    if code == "-":
        return {}
    if len(code) == 1:
        return {code.upper(): "filled" if code.isupper() else "faint"}
    if all(c.isupper() for c in code):
        return {c: "filled" for c in code}
    raise ValueError(f"mã câu không hiểu: {code!r}")


def trang_thai_that(o: dict) -> str:
    if not o:
        return "trong"
    if len(o) > 1:
        return "nhieu"
    return "ro" if next(iter(o.values())) == "filled" else "mo"


def doc_nhan(phieu_cho_phep: set) -> dict:
    """{phieu: {'cau': {q: {ô: mức}}, 'sbd': '06238-', 'ma_de': '101'}} – chỉ phiếu được phép; đối chiếu cell_labels."""
    out = {}
    with (DATA / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            p = int(r["sheet_id"])
            if p not in phieu_cho_phep:
                continue                                        # dòng phiếu ngoài tập: bỏ ngay, không giữ
            out[r["sheet_id"]] = {"cau": {q: giai_ma(r[f"q{q}"]) for q in range(1, 41)},
                                  "sbd": r["sbd_bubble"], "ma_de": r["exam_code_bubble"]}
    lech = 0
    with (DATA / "cell_labels.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["sheet_id"] not in out:
                continue
            n = out[r["sheet_id"]]
            q, o = r["question"], r["option"]
            if q.isdigit():
                mong = n["cau"][int(q)].get(o, "blank")
            else:
                truong, i = ("sbd", int(q[3:])) if q.startswith("sbd") else ("ma_de", int(q[9:]))
                mong = "filled" if n[truong][i - 1] == o else "blank"
            lech += mong != r["cell_label"]
    if lech:
        raise SystemExit(f"ground_truth.csv và cell_labels.csv lệch {lech} ô – DỪNG (make_dataset_plan.py --from-csv?)")
    return out


def ds_anh(split: str, cho_phep_val: bool) -> list[dict]:
    if split == "test":
        raise SystemExit("Tập test 0035–0040 chỉ chạy ở đánh giá cuối có đăng ký trước (Phần B) – chưa mở trong eval_omr.py")
    if split == "val" and not cho_phep_val:
        raise SystemExit("Phần A không dùng val 0029–0034 (★Q3) – cần --cho-phep-val (Phần B)")
    with (DATA / "split.csv").open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["tap"] == split]
    chan_test([r["anh"] for r in rows], False, "eval_omr")
    ok = PHIEU_TRAIN if split == "train" else PHIEU_VAL
    assert all(int(r["phieu"]) in ok and int(r["phieu"]) not in PHIEU_TEST for r in rows)
    return rows


# ------------------------------------------------------------------------------------------------ vị trí (cách riêng)
def _mau_pdf(layout) -> np.ndarray:
    from check_layout import render_pdf_page
    a = render_pdf_page(ROOT / "answer_sheet" / "output" / "phieu_trang.pdf", layout["dpi"])
    return a[:layout["page_px"][1], :layout["page_px"][0]]


def _nhan_vanh(r: float) -> np.ndarray:
    n = int(np.ceil(1.3 * r))
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    d = np.hypot(xx, yy)
    k = ((d >= 0.85 * r) & (d <= 1.15 * r)).astype(np.float32)
    return k - k.mean()


def _tam_vong(canh: np.ndarray, cx: float, cy: float, r: float, ban_kinh: int) -> tuple[float, float]:
    """Tâm vòng tròn in sẵn gần (cx, cy) nhất theo nhân vành trên bản đồ cạnh, tìm trong ±ban_kinh px."""
    k = _nhan_vanh(r)
    h = k.shape[0] // 2
    x0, y0 = int(round(cx)) - ban_kinh - h, int(round(cy)) - ban_kinh - h
    vung = canh[y0:y0 + 2 * (ban_kinh + h) + 1, x0:x0 + 2 * (ban_kinh + h) + 1]       # ô luôn xa mép trang
    res = cv2.filter2D(vung, cv2.CV_32F, k)[h:-h, h:-h]
    iy, ix = np.unravel_index(int(np.argmax(res)), res.shape)
    return x0 + h + ix, y0 + h + iy


def vi_tri_doc_lap(anh: np.ndarray, layout: dict, mau_pdf: np.ndarray) -> dict:
    """{'q1'..'q40', 'sbd1'.., 'ma_de1'..: (dx, dy) mm} đo bằng phaseCorrelate (thô) + tâm vòng tròn in sẵn (từng ô)."""
    px_mm = 25.4 / layout["dpi"]
    k4 = 4
    gx = cv2.Sobel(anh, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(anh, cv2.CV_32F, 0, 1)
    canh = cv2.magnitude(gx, gy)

    def canh_nho(a):
        a = a.astype(np.float32)
        return cv2.resize(cv2.magnitude(cv2.Sobel(a, cv2.CV_32F, 1, 0), cv2.Sobel(a, cv2.CV_32F, 0, 1)), None,
                          fx=1 / k4, fy=1 / k4, interpolation=cv2.INTER_AREA)
    ban = int(round(2.5 / px_mm))                                # ±2,5 mm < nửa khoảng cách ô ngang (3,5) / bubble (2,9)
    ans = layout["answers"]
    pts = np.array([xy for q in ans["centers"].values() for xy in q.values()])
    x0, y0 = (pts.min(0) / k4 - 40).astype(int)
    x1, y1 = (pts.max(0) / k4 + 40).astype(int)
    # phaseCorrelate trên BẢN ĐỒ CẠNH (không phụ thuộc bóng / độ sáng; cửa sổ Hanning làm hỏng 0004_C4 – thử 07/10)
    (sx, sy), dap_ung = cv2.phaseCorrelate(canh_nho(mau_pdf)[y0:y1, x0:x1], canh_nho(anh)[y0:y1, x0:x1])
    tho = (sx * k4, sy * k4)
    if dap_ung < 0.05 or max(abs(sx), abs(sy)) * k4 * px_mm > 6:
        raise RuntimeError(f"phaseCorrelate không tin được (đáp ứng {dap_ung:.3f}, dịch {tho}) – eval không đo được vị trí")
    out = {}

    def day(ten, cac_o_theo_hang, r):
        du = np.array(tho)
        for key, o_list in zip(ten, cac_o_theo_hang):
            lech = [np.array(_tam_vong(canh, cx + du[0], cy + du[1], r, ban)) - np.array([cx, cy]) for cx, cy in o_list]
            d = np.median(np.array(lech), axis=0)
            out[key] = (round(float(d[0] * px_mm), 3), round(float(d[1] * px_mm), 3))
            du = d

    for g0 in range(0, ans["num_questions"], 10):
        qs = range(g0 + 1, g0 + 11)
        day([f"q{q}" for q in qs], [[ans["centers"][str(q)][o] for o in ans["options"]] for q in qs], ans["bubble_radius"])
    for kh, truong in (("sbd", "sbd"), ("ma_de", "exam_code")):
        f = layout[truong]
        day([f"{kh}{i + 1}" for i in range(len(f["bubbles"]))], f["bubbles"], f["bubble_radius"])
    return out


# ------------------------------------------------------------------------------------------------ run
def cmd_run(pp: str, split: str, cho_phep_val: bool) -> None:
    L = nap_layout("phieu")
    rows = ds_anh(split, cho_phep_val)
    nhan = doc_nhan({int(r["phieu"]) for r in rows})
    mau_pdf = _mau_pdf(L)
    out = OUT / pp
    out.mkdir(parents=True, exist_ok=True)
    cau_rows, cot_rows, o_rows, anh_rows = [], [], [], []
    cache = {}
    for r in rows:
        # train: OOF (mô hình bỏ fold của ảnh); val (Phần B): mô hình ĐẦY ĐỦ models/omr_<pp>.json huấn luyện trên cả 56 ảnh train
        khoa = r["fold"] if split == "train" else "cuoi"
        mo_hinh = cache.setdefault(khoa, omr.nap_mo_hinh(MO_HINH[pp](r["fold"]) if split == "train" else ROOT / "models" / f"omr_{pp}.json"))
        t = time.perf_counter()
        kq = preprocess(DATA / "raw" / f"{r['anh']}.jpg", L)
        t_pre = (time.perf_counter() - t) * 1000
        if not kq.ok:
            raise SystemExit(f"{r['anh']}: preprocess từ chối ({kq.ly_do}) – ảnh dev phải ok")
        res = omr.doc_phieu(kq, L, mo_hinh)
        vt = vi_tri_doc_lap(kq.anh_nan, L, mau_pdf)
        lech_vt = {k: max(abs(vt[k][0] - res.dich_chuyen_mm[k][0]), abs(vt[k][1] - res.dich_chuyen_mm[k][1])) for k in vt}
        n = nhan[r["phieu"]]
        base = {"anh": r["anh"], "phieu": r["phieu"], "dieu_kien": r["dieu_kien"], "but": r["but"], "fold": r["fold"]}
        for k in res.cau:
            that = n["cau"][k.cau]
            for o, p in k.xac_suat.items():
                o_rows.append({**base, "loai": "cau", "phan_tu": f"q{k.cau}", "o": o, "nhan": that.get(o, "blank"),
                               "du_doan": max(p, key=p.get), **{f"p_{l}": p[l] for l in LOP}})
            cau_rows.append({**base, "cau": k.cau, "that": trang_thai_that(that), "that_o": "".join(sorted(that)),
                             "doc": k.trang_thai, "doc_o": k.dap_an, "can_xem": int(k.can_xem), "ly_do": "|".join(k.ly_do),
                             "do_tin_cay": k.do_tin_cay, "lech_vi_tri_mm": round(lech_vt[f"q{k.cau}"], 3),
                             "dx_mm": res.dich_chuyen_mm[f"q{k.cau}"][0], "dy_mm": res.dich_chuyen_mm[f"q{k.cau}"][1]})
        for truong, cots in (("sbd", res.sbd_cot), ("ma_de", res.ma_de_cot)):
            for c in cots:
                that = n[truong][c.vi_tri - 1]
                for d, p in enumerate(c.xac_suat_to):
                    o_rows.append({**base, "loai": "bubble", "phan_tu": f"{truong}{c.vi_tri}", "o": str(d),
                                   "nhan": "filled" if that == str(d) else "blank",
                                   "du_doan": "filled" if p >= 0.5 else "blank", "p_blank": round(1 - p, 4), "p_faint": 0,
                                   "p_filled": p})
                cot_rows.append({**base, "truong": truong, "vi_tri": c.vi_tri, "that": that, "doc": c.chu_so,
                                 "can_xem": int(c.can_xem), "ly_do": "|".join(c.ly_do), "do_tin_cay": c.do_tin_cay,
                                 "lech_vi_tri_mm": round(lech_vt[f"{truong}{c.vi_tri}"], 3)})
        anh_rows.append({**base, "sbd_that": n["sbd"], "sbd_doc": res.sbd, "sbd_can_xem": int(res.sbd_can_xem),
                         "ma_de_that": n["ma_de"], "ma_de_doc": res.ma_de, "ma_de_can_xem": int(res.ma_de_can_xem),
                         "ms_preprocess": round(t_pre), "ms_omr": res.thoi_gian_ms,
                         "lech_vi_tri_max_mm": round(max(lech_vt.values()), 3)})
        print(f"{r['anh']}: SBD {res.sbd} (thật {n['sbd']}), mã đề {res.ma_de}, cần xem "
              f"{sum(k.can_xem for k in res.cau)} câu, omr {res.thoi_gian_ms:.0f} ms, lệch vị trí max "
              f"{max(lech_vt.values()):.2f} mm")
    for ten, ds in ((f"cau_{split}.csv", cau_rows), (f"cot_{split}.csv", cot_rows), (f"o_{split}.csv", o_rows),
                    (f"anh_{split}.csv", anh_rows)):
        with (out / ten).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ds[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(ds)
    print(f"-> {out}")


# ------------------------------------------------------------------------------------------------ đếm (bộ đếm riêng)
def doc_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def loai_cau(r: dict) -> str:
    """Xếp 1 lượt (ảnh, câu) vào đúng 1 loại (mục 2 + ★Q1)."""
    dung_o = r["that_o"] == "".join(sorted(r["doc_o"]))
    if r["can_xem"] == "1":
        if r["that"] in ("mo", "nhieu"):
            return "can_xem_can_thiet" if dung_o else "can_xem_can_thiet_doc_sai"
        return "can_xem_thua" if dung_o else "can_xem_thua_doc_sai"
    if not dung_o:
        return "loi_nang"
    if r["doc"] != r["that"]:
        return "loi_nhe"
    return "dung_chac_chan"


def loai_cot(r: dict) -> str:
    if r["can_xem"] == "1":
        if r["that"] == "-":
            return "can_xem_can_thiet"
        return "can_xem_thua" if r["doc"] == r["that"] else "can_xem_thua_doc_sai"
    return "dung_chac_chan" if r["doc"] == r["that"] else "loi_nang"


def f1(y, d, k="faint"):
    tp = sum(a == k and b == k for a, b in zip(y, d))
    fp = sum(a != k and b == k for a, b in zip(y, d))
    fn = sum(a == k and b != k for a, b in zip(y, d))
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")


def cp_tren(k: int, n: int) -> float:
    """Cận trên 95% Clopper–Pearson (hai phía) của tỉ lệ k/n."""
    if k >= n:
        return 1.0
    from math import comb
    lo, hi = k / n, 1.0
    for _ in range(60):                                          # tìm p: P(X ≤ k | n, p) = 0,025
        mid = (lo + hi) / 2
        cdf = sum(comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(k + 1))
        lo, hi = (mid, hi) if cdf > 0.025 else (lo, mid)
    return hi


def bang(pp: str, split: str) -> dict:
    d = OUT / pp
    cau, cot, o, anh = (doc_csv(d / f"{t}_{split}.csv") for t in ("cau", "cot", "o", "anh"))
    rng = np.random.default_rng(SEED)
    phieu = sorted({r["phieu"] for r in anh})
    rut = [rng.choice(phieu, len(phieu), replace=True) for _ in range(SO_BOOT)]
    kq = {"pp": pp, "dk": {}}
    for dk in DIEU_KIEN + ("tong",):
        sel = (lambda r: True) if dk == "tong" else (lambda r, dk=dk: r["dieu_kien"] == dk)
        oc = [r for r in o if r["loai"] == "cau" and sel(r)]
        ob = [r for r in o if r["loai"] == "bubble" and sel(r)]
        cm = [[sum(r["nhan"] == a and r["du_doan"] == b for r in oc) for b in LOP] for a in LOP]
        cmb = [[sum(r["nhan"] == a and r["du_doan"] == b for r in ob) for b in ("blank", "filled")] for a in ("blank", "filled")]
        f1v = f1([r["nhan"] for r in oc], [r["du_doan"] for r in oc])
        theo_phieu = {}
        for r in oc:
            theo_phieu.setdefault(r["phieu"], []).append(r)
        bs = []
        for rr in rut:
            s = [x for p in rr for x in theo_phieu.get(p, [])]
            bs.append(f1([x["nhan"] for x in s], [x["du_doan"] for x in s]) if s else np.nan)
        ci = np.nanpercentile(bs, [2.5, 97.5]).tolist()
        cs, ct = [r for r in cau if sel(r)], [r for r in cot if sel(r)]
        lc = {}
        for r in cs:
            lc[loai_cau(r)] = lc.get(loai_cau(r), 0) + 1
        lt = {}
        for r in ct:
            lt[loai_cot(r)] = lt.get(loai_cot(r), 0) + 1
        n_ro = sum(r["that"] == "ro" for r in cs)
        n_trong = sum(r["that"] == "trong" for r in cs)
        thua_ro = sum(r["that"] == "ro" and r["can_xem"] == "1" for r in cs)
        thua_trong = sum(r["that"] == "trong" and r["can_xem"] == "1" for r in cs)
        an = [r for r in anh if sel(r)]
        kq["dk"][dk] = {
            "n_anh": len(an), "n_cau": len(cs), "n_cot": len(ct), "cm": cm, "cm_bubble": cmb, "f1_faint": f1v, "f1_ci": ci,
            "n_faint": sum(r["nhan"] == "faint" for r in oc), "loai_cau": lc, "loai_cot": lt,
            "dung_o_cau": sum(r["that_o"] == "".join(sorted(r["doc_o"])) for r in cs),
            "dung_tt_cau": sum(r["that_o"] == "".join(sorted(r["doc_o"])) and r["doc"] == r["that"] for r in cs),
            "nang": lc.get("loi_nang", 0) + lt.get("loi_nang", 0), "nhe": lc.get("loi_nhe", 0),
            "nang_cp": cp_tren(lc.get("loi_nang", 0) + lt.get("loi_nang", 0), len(cs) + len(ct)),
            "thua_ro": thua_ro, "n_ro": n_ro, "thua_trong": thua_trong, "n_trong": n_trong,
            "can_xem": sum(r["can_xem"] == "1" for r in cs), "can_xem_cot": sum(r["can_xem"] == "1" for r in ct),
            "sbd_dung_chac": sum(r["sbd_doc"] == r["sbd_that"] and r["sbd_can_xem"] == "0" for r in an),
            "sbd_can_xem": sum(r["sbd_can_xem"] == "1" for r in an),
            "sbd_sai_im_lang": sum(r["sbd_doc"] != r["sbd_that"] and r["sbd_can_xem"] == "0" for r in an),
            "ma_de_dung_chac": sum(r["ma_de_doc"] == r["ma_de_that"] and r["ma_de_can_xem"] == "0" for r in an),
            "ma_de_can_xem": sum(r["ma_de_can_xem"] == "1" for r in an),
            "ma_de_sai_im_lang": sum(r["ma_de_doc"] != r["ma_de_that"] and r["ma_de_can_xem"] == "0" for r in an),
            "ms_omr": [float(np.median([float(r["ms_omr"]) for r in an])), max(float(r["ms_omr"]) for r in an)] if an else [],
            "ms_pre": [float(np.median([float(r["ms_preprocess"]) for r in an]))] if an else [],
            "vi_tri_dang_ngo": sum(float(r["lech_vi_tri_mm"]) > VI_TRI_SAI_MM for r in cs + ct),
            "lech_vi_tri_max": max(float(r["lech_vi_tri_mm"]) for r in cs + ct) if cs else 0,
            "anh_co_loi_nang": len({r["anh"] for r in cs if loai_cau(r) == "loi_nang"} |
                                   {r["anh"] for r in ct if loai_cot(r) == "loi_nang"}),
        }
    return kq


def pct(a, b):
    return f"{100 * a / b:.2f}%" if b else "–"


def cmd_report(split: str) -> None:
    kq = {pp: bang(pp, split) for pp in ("m0", "m1") if (OUT / pp / f"cau_{split}.csv").exists()}
    L = ["# Tuần 5 – Phần A: đánh giá OMR độc lập (tools/eval_omr.py)", "",
         (f"Tập: **{split}** (56 ảnh 0001–0028; M1 = dự đoán NGOÀI FOLD, 7 fold theo phiếu). Không dùng val 0029–0034, test." if split == "train" else
          f"Tập: **{split}** (val 0029–0034, 12 ảnh; mô hình huấn luyện trên 56 ảnh train, KHÔNG thấy val). Không dùng test."),
         "Đơn vị: lượt (ảnh, câu) / (ảnh, cột). CI 95%: bootstrap theo phiếu 1000 lần, seed 2026. Cận trên lỗi nặng: "
         "Clopper–Pearson 95% (lạc quan – lượt cùng ảnh không độc lập).", ""]
    for pp, b in kq.items():
        L += [f"## {TEN_PP[pp]}", "",
              "| | C1 | C2 | C3 | C4 | Tổng |", "|---|---|---|---|---|---|"]

        def dong(ten, f):
            L.append(f"| {ten} | " + " | ".join(f(b["dk"][dk]) for dk in DIEU_KIEN + ("tong",)) + " |")
        dong("Ảnh / lượt câu", lambda x: f"{x['n_anh']} / {x['n_cau']}")
        dong("F1 faint cấp ô [CI] (n faint)", lambda x: f"{x['f1_faint']:.3f} [{x['f1_ci'][0]:.3f}; {x['f1_ci'][1]:.3f}] ({x['n_faint']})")
        dong("Độ đúng câu: tập ô", lambda x: pct(x["dung_o_cau"], x["n_cau"]))
        dong("Độ đúng câu: tập ô + mức", lambda x: pct(x["dung_tt_cau"], x["n_cau"]))
        dong("**LỖI NẶNG** (câu + cột) [CP 95% trên]", lambda x: f"**{x['nang']}** [{100 * x['nang_cp']:.2f}%]")
        dong("Ảnh có ≥ 1 lỗi nặng", lambda x: str(x["anh_co_loi_nang"]))
        dong("Lỗi nhẹ (mờ đọc rõ, chắc chắn)", lambda x: str(x["nhe"]))
        dong("Cần xem cần thiết (mờ / nhiều ô)", lambda x: str(x["loai_cau"].get("can_xem_can_thiet", 0)
                                                                 + x["loai_cau"].get("can_xem_can_thiet_doc_sai", 0)))
        dong("Cần xem thừa: câu rõ 1 ô", lambda x: f"{x['thua_ro']} / {x['n_ro']} ({pct(x['thua_ro'], x['n_ro'])})")
        dong("Cần xem thừa: câu trống", lambda x: f"{x['thua_trong']} / {x['n_trong']} ({pct(x['thua_trong'], x['n_trong'])})")
        dong("Cần xem mà đọc sai tập ô", lambda x: str(x["loai_cau"].get("can_xem_can_thiet_doc_sai", 0)
                                                        + x["loai_cau"].get("can_xem_thua_doc_sai", 0)))
        dong("Tổng câu cần xem", lambda x: f"{x['can_xem']} ({pct(x['can_xem'], x['n_cau'])})")
        dong("SBD đúng & chắc / cần xem / sai im lặng", lambda x: f"{x['sbd_dung_chac']} / {x['sbd_can_xem']} / {x['sbd_sai_im_lang']}")
        dong("Mã đề đúng & chắc / cần xem / sai im lặng", lambda x: f"{x['ma_de_dung_chac']} / {x['ma_de_can_xem']} / {x['ma_de_sai_im_lang']}")
        dong("Cột cần xem (cần thiết + thừa)", lambda x: f"{x['loai_cot'].get('can_xem_can_thiet', 0)} + {x['loai_cot'].get('can_xem_thua', 0)}")
        dong("Vị trí đáng ngờ (lệch đo độc lập > 0,5 mm) / lệch max", lambda x: f"{x['vi_tri_dang_ngo']} / {x['lech_vi_tri_max']:.2f} mm")
        dong("Thời gian doc_phieu: trung vị / max (ms)", lambda x: f"{x['ms_omr'][0]:.0f} / {x['ms_omr'][1]:.0f}")
        L += ["", "Ma trận nhầm lẫn cấp ô đáp án (hàng = nhãn blank / faint / filled; cột = dự đoán argmax):", ""]
        for dk in DIEU_KIEN:
            L.append(f"- {dk}: {b['dk'][dk]['cm']} · bubble (blank / filled): {b['dk'][dk]['cm_bubble']}")
        L.append("")
    # ca thử
    L += ["## Ca thử (ô C, nhãn faint – đã so giấy; n 0,23–0,26 sát ngưỡng cố định)", ""]
    for p, q, o in CA_THU:
        if (int(p) in PHIEU_TRAIN) != (split == "train"):
            L.append(f"- {p} câu {q}: thuộc tập khác ({'val 0029–0034' if int(p) in PHIEU_VAL else 'train'}), không có trong tập {split}.")
            continue
        for pp in kq:
            oo = [r for r in doc_csv(OUT / pp / f"o_{split}.csv") if r["phieu"] == p and r["phan_tu"] == f"q{q}" and r["o"] == o]
            cc = {r["anh"]: r for r in doc_csv(OUT / pp / f"cau_{split}.csv") if r["phieu"] == p and r["cau"] == str(q)}
            L.append(f"- {p} câu {q} ô {o} – {TEN_PP[pp]}: " + "; ".join(
                f"{r['anh']}: ô {r['du_doan']} (p mờ {float(r['p_faint']):.3f}, rõ {float(r['p_filled']):.3f}), câu đọc "
                f"'{cc[r['anh']]['doc_o'] or '-'}' {cc[r['anh']]['doc']}, cần xem {cc[r['anh']]['can_xem']} "
                f"({cc[r['anh']]['ly_do'] or '–'})" for r in oo))
    # tiêu chí
    if "m1" in kq:
        t = kq["m1"]["dk"]
        L += ["", "## Đối chiếu tiêu chí ★Q2 (M1, OOF train)", "",
              f"- Lỗi nặng = 0: **{'ĐẠT' if t['tong']['nang'] == 0 else 'KHÔNG ĐẠT'}** ({t['tong']['nang']} trên "
              f"{t['tong']['n_cau']} lượt câu + {t['tong']['n_cot']} lượt cột; cận trên CP 95% "
              f"{100 * t['tong']['nang_cp']:.2f}%)",
              "- F1 faint ≥ 0,90 mỗi C1–C4: " + ", ".join(
                  f"{dk} {t[dk]['f1_faint']:.3f} [{t[dk]['f1_ci'][0]:.3f}; {t[dk]['f1_ci'][1]:.3f}] "
                  f"{'đạt' if t[dk]['f1_faint'] >= 0.9 else 'KHÔNG ĐẠT'}" for dk in DIEU_KIEN),
              f"- Cần xem thừa ≤ 3% (câu rõ 1 ô): **{pct(t['tong']['thua_ro'], t['tong']['n_ro'])}** "
              f"{'đạt' if t['tong']['thua_ro'] <= 0.03 * t['tong']['n_ro'] else 'KHÔNG ĐẠT'} (gộp); theo điều kiện: " + ", ".join(
                  f"{dk} {pct(t[dk]['thua_ro'], t[dk]['n_ro'])}"
                  f"{'' if t[dk]['thua_ro'] <= 0.03 * t[dk]['n_ro'] else ' (KHÔNG ĐẠT)'}" for dk in DIEU_KIEN)]
    (OUT / f"bao_cao_phan_a_{split}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    json.dump(kq, (OUT / f"bao_cao_phan_a_{split}.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1,
              default=float)
    print("\n".join(L))
    for pp in kq:
        xuat_html(pp, split)
        xuat_html(pp, split, chi_can_thiet=True)


# ------------------------------------------------------------------------------------------------ HTML xem bằng mắt
def xuat_html(pp: str, split: str, chi_can_thiet: bool = False) -> None:
    """Ca lỗi nặng / nhẹ, cần xem thừa, cần xem mà đọc sai, vị trí đáng ngờ, ca thử: ảnh cắt hàng câu (vòng tròn tại vị trí omr
    báo, màu theo dự đoán ô) + nhãn + kết quả. Phần A: người dùng xem SAU (không chặn)."""
    L = nap_layout("phieu")
    d = OUT / pp
    img_dir = d / "xem"
    img_dir.mkdir(exist_ok=True)
    cau = doc_csv(d / f"cau_{split}.csv")
    cot = doc_csv(d / f"cot_{split}.csv")
    o = {(r["anh"], r["phan_tu"], r["o"]): r for r in doc_csv(d / f"o_{split}.csv")}
    ca_thu = {(p, str(q)) for p, q, _ in CA_THU}
    chon = []
    for r in cau:
        loai = loai_cau(r)
        if chi_can_thiet:                      # Phần B1c: LIỆT KÊ CẢ câu "cần xem cần thiết" đọc đúng (mờ / nhiều ô) để kiểm nhãn rõ / mờ
            if loai == "can_xem_can_thiet":
                chon.append(("cau", loai, r))
            continue
        if loai in ("loi_nang", "loi_nhe", "can_xem_thua", "can_xem_thua_doc_sai", "can_xem_can_thiet_doc_sai") \
                or float(r["lech_vi_tri_mm"]) > VI_TRI_SAI_MM or (r["phieu"], r["cau"]) in ca_thu \
                or "tin_cay_thap" in r["ly_do"] or "vi_tri" in r["ly_do"]:
            chon.append(("cau", loai, r))
    for r in ([] if chi_can_thiet else cot):
        loai = loai_cot(r)
        if loai != "dung_chac_chan" or float(r["lech_vi_tri_mm"]) > VI_TRI_SAI_MM:
            chon.append(("cot", loai, r))
    thu_tu = {"loi_nang": 0, "can_xem_thua_doc_sai": 1, "can_xem_can_thiet_doc_sai": 1, "loi_nhe": 2, "can_xem_thua": 3}
    chon.sort(key=lambda x: (thu_tu.get(x[1], 4), x[2]["anh"]))
    anh_cache: dict = {}
    px = L["dpi"] / 25.4
    mau = {"blank": (160, 160, 160), "faint": (0, 165, 255), "filled": (0, 0, 220)}
    khoi = []
    for kind, loai, r in chon:
        if r["anh"] not in anh_cache:
            anh_cache.clear()
            anh_cache[r["anh"]] = preprocess(DATA / "raw" / f"{r['anh']}.jpg", L).anh_nan
        a = cv2.cvtColor(anh_cache[r["anh"]], cv2.COLOR_GRAY2BGR)
        if kind == "cau":
            q = int(r["cau"])
            c = L["answers"]["centers"][str(q)]
            dx, dy = float(r["dx_mm"]) * px, float(r["dy_mm"]) * px
            xs = [c[k][0] + dx for k in "ABCD"]
            cy = c["A"][1] + dy
            for k in "ABCD":
                rr = o[(r["anh"], f"q{q}", k)]
                cv2.circle(a, (int(c[k][0] + dx), int(cy)), int(L["answers"]["bubble_radius"] * 1.25), mau[rr["du_doan"]], 2)
            x0, y0, x1, y1 = int(min(xs) - 12 * px), int(cy - 5 * px), int(max(xs) + 5 * px), int(cy + 5 * px)
            ten = f"{r['anh']}_q{q:02d}.png"
            mo_ta = (f"<b>{r['anh']} câu {q}</b> ({r['dieu_kien']}, {html.escape(r['but'])}) – <b>{loai}</b><br>nhãn: "
                     f"<code>{r['that_o'] or '-'}</code> {r['that']} · đọc: <code>{r['doc_o'] or '-'}</code> {r['doc']} · "
                     f"cần xem {r['can_xem']} ({r['ly_do'] or '–'}) · lệch vị trí độc lập {r['lech_vi_tri_mm']} mm<br>"
                     + " ".join(f"{k}: {float(o[(r['anh'], f'q{q}', k)]['p_blank']):.2f}/"
                                f"{float(o[(r['anh'], f'q{q}', k)]['p_faint']):.2f}/"
                                f"{float(o[(r['anh'], f'q{q}', k)]['p_filled']):.2f}" for k in "ABCD")
                     + " <small>(p trống/mờ/rõ)</small>")
        else:
            truong = "sbd" if r["truong"] == "sbd" else "exam_code"
            col = L[truong]["bubbles"][int(r["vi_tri"]) - 1]
            x0, y0 = int(col[0][0] - 6 * px), int(col[0][1] - 18 * px)
            x1, y1 = int(col[0][0] + 6 * px), int(col[-1][1] + 4 * px)
            ten = f"{r['anh']}_{r['truong']}{r['vi_tri']}.png"
            mo_ta = (f"<b>{r['anh']} {r['truong']} cột {r['vi_tri']}</b> – <b>{loai}</b><br>nhãn: {r['that']} · đọc: "
                     f"{r['doc']} · cần xem {r['can_xem']} ({r['ly_do'] or '–'}) · lệch vị trí độc lập {r['lech_vi_tri_mm']} mm")
        crop = a[max(y0, 0):y1, max(x0, 0):x1]
        cv2.imencode(".png", cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))[1].tofile(img_dir / ten)
        khoi.append(f"<div class='o'><img src='xem/{ten}'><p>{mo_ta}</p></div>")
    trang = d / ("xem_can_xem_can_thiet.html" if chi_can_thiet else f"xem_bang_mat{'' if split == 'train' else '_' + split}.html")
    trang.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>OMR {pp} – xem bằng mắt</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:16px;background:#fafafa;color:#222}}
.o{{background:#fff;border:1px solid #ccc;padding:8px;margin:8px 0}} img{{border:1px solid #888;max-width:100%}}
code{{font-size:15px}}</style></head><body><h2>{TEN_PP[pp]} – {len(khoi)} mục {'"cần xem cần thiết" (đọc đúng tập ô; kiểm nhãn rõ / mờ)' if chi_can_thiet else 'cần xem bằng mắt'} ({split})</h2>
<p>Thứ tự: lỗi nặng → cần xem mà đọc sai → lỗi nhẹ → cần xem thừa → còn lại (lưng chừng, vị trí, ca thử, cột).
Vòng tròn tại vị trí omr.py báo: <span style="color:#dc0000">đỏ = rõ</span>, <span style="color:#ffa500">cam = mờ</span>,
xám = trống (dự đoán argmax). Nghi nhãn sai → so giấy thật, KHÔNG sửa ground_truth.csv khi chưa xác nhận.</p>
{''.join(khoi)}</body></html>""", encoding="utf-8")
    print(f"HTML: {trang} ({len(khoi)} mục)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Đánh giá độc lập OMR (Tuần 5)")
    ap.add_argument("lenh", choices=["run", "report"])
    ap.add_argument("--phuong-phap", choices=list(MO_HINH), default="m1")
    ap.add_argument("--split", default="train", choices=["train", "val", "test"])
    ap.add_argument("--cho-phep-val", action="store_true", help="Phần B: cho phép val 0029–0034")
    a = ap.parse_args()
    if a.split != "train" and a.lenh == "run":
        ds_anh(a.split, a.cho_phep_val)                       # chặn trước khi làm gì
    if a.lenh == "run":
        cmd_run(a.phuong_phap, a.split, a.cho_phep_val)
    else:
        cmd_report(a.split)


if __name__ == "__main__":
    main()
