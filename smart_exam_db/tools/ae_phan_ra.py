"""
ae_phan_ra.py - Lệnh AE: vì sao "cần xem"? CHỈ ĐO, KHÔNG SỬA MÃ HỆ THỐNG (không ghi CSDL, không bật server).

  python tools/ae_phan_ra.py doc --tap dev        # chạy pipeline OFFLINE (cv_engine) trên 56 ảnh phiếu 0001–0028 -> data/_eval/ae/doc_dev.json
  python tools/ae_phan_ra.py doc --tap dot2       # 20 ảnh đợt 2 (data/raw_dot2) + đối chiếu với data/_eval/dot2/that/ket_qua.json (lần chạy duy nhất qua API)
  python tools/ae_phan_ra.py phan-ra --tap dev|dot2   # bảng a) câu trả lời, b) SBD / mã đề, c) "cần xem không cần thiết" -> data/_eval/ae/phan_ra_<tap>.md
  python tools/ae_phan_ra.py de-xuat              # 3 đề xuất: CHỈNH trên dev, THỬ trên đợt 2 -> data/_eval/ae/de_xuat.md (KHÔNG áp dụng vào hệ thống)

Đường đọc = backend: preprocess -> omr.doc_phieu -> ocr.doc_chu_so -> ocr.doi_chieu_dinh_danh (SBD / mã đề coi như CÓ trong danh sách kỳ thi,
như lần chạy đợt 2 – mọi thí sinh đã được thêm vào). Phiếu val 0029–0034 / test 0035–0040 KHÔNG đọc (chan_test).
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine import ocr  # noqa: E402
from cv_engine.omr import doc_phieu, nap_mo_hinh  # noqa: E402
from cv_engine.preprocessing import nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_TRAIN, chan_test, ma_phieu  # noqa: E402

DATA = ROOT / "data"
AE = DATA / "_eval" / "ae"
KQ_DOT2 = DATA / "_eval" / "dot2" / "that" / "ket_qua.json"


# ------------------------------------------------------------------------------------------- nhãn (cùng quy ước tools/eval_dot2.py)
def tap_chon(lab: str) -> str:
    """Tập ô thật: '-' hoặc vết chấm ('*B') -> ''; 'bD' -> 'BD'."""
    return "" if lab == "-" or lab.startswith("*") else "".join(sorted(lab.upper()))


def trang_thai_that(lab: str) -> str:
    if lab == "-":
        return "trong"
    if lab.startswith("*"):
        return "vet"
    if len(lab) > 1:
        return "nhieu"
    return "ro" if lab.isupper() else "mo"


def loai_cau(lab: str) -> str:
    if lab == "-":
        return "trống"
    if lab.startswith("*"):
        return "vết (chấm nhỏ)"
    n, hoa = len(lab), sum(c.isupper() for c in lab)
    if n == 1:
        return "1 đậm" if hoa else "1 mờ"
    ten = {2: ("hai đậm", "đậm + mờ", "hai mờ"), 3: ("ba đậm", "ba hỗn hợp", "ba mờ")}.get(n, ("≥4 đậm", "≥4 hỗn hợp", "≥4 mờ"))
    return ten[0] if hoa == n else ten[2] if hoa == 0 else ten[1]


def doc_nhan(tap: str) -> dict:
    p = DATA / "ground_truth.csv" if tap == "dev" else DATA / "dot2" / "ground_truth_dot2_da_sua.csv"
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        ms = int(r["sheet_id"])
        if tap == "dev" and ms not in PHIEU_TRAIN:
            continue                                   # chỉ 0001–0028: KHÔNG giữ dòng nhãn val / test
        out[r["sheet_id"]] = {"q": {q: r[f"q{q}"] for q in range(1, 41)}, "sbd": r["sbd"], "ma_de": r["exam_code"],
                              "sbd_bubble": r["sbd_bubble"], "ma_de_bubble": r["exam_code_bubble"], "nguoi": r.get("writer", "")}
    return out


def danh_sach_anh(tap: str) -> list[Path]:
    if tap == "dev":
        anh = sorted(p for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in PHIEU_TRAIN)
        chan_test(anh, xac_nhan=False, viec="ae_phan_ra doc dev")
        return anh
    return sorted(p for p in (DATA / "raw_dot2").iterdir() if p.suffix.lower() == ".jpg")   # Windows: glob không phân biệt hoa thường


# ------------------------------------------------------------------------------------------- doc
def cmd_doc(a):
    from cv_engine.tap_du_lieu import nguoi_viet
    lay, mh, mh_ocr = nap_layout("phieu"), nap_mo_hinh(), ocr.nap_mo_hinh_ocr()
    nhan = doc_nhan(a.tap)
    out, t0 = [], time.time()
    for p in danh_sach_anh(a.tap):
        ms = p.stem.split("_")[0]
        t = nhan[ms]
        kq = preprocess(str(p), lay)
        rec = {"anh": p.stem, "phieu": ms, "dk": p.stem.split("_")[1],
               "nguoi": t["nguoi"] or (str(nguoi_viet(p.stem)) if a.tap == "dev" else ""), "tu_choi": "" if kq.ok else kq.ly_do}
        if not kq.ok:
            out.append(rec)
            continue
        om = doc_phieu(kq, lay, mh)
        hv = ocr.doc_chu_so(kq, lay, mh_ocr)
        dc = ocr.doi_chieu_dinh_danh(om, hv, True, True, mo_hinh=mh_ocr)
        rec["to_nhat"], rec["T_to"] = bool(om.to_nhat), float(om.do_toi_to)
        rec["cau"] = []
        for c in om.cau:
            lab = t["q"][c.cau]
            rec["cau"].append({"n": c.cau, "lab": lab, "loai": loai_cau(lab), "tt_that": trang_thai_that(lab), "chon_that": tap_chon(lab),
                               "doc_tt": c.trang_thai, "doc_o": c.dap_an, "P": [[c.xac_suat[o][k] for k in ("blank", "faint", "filled")] for o in "ABCD"],
                               "tin": c.do_tin_cay, "cx": bool(c.can_xem), "ly_do": list(c.ly_do)})
        rec["cot"], rec["truong"] = [], {}
        for ten, om_cot, hv_cot, viet, bub in (("sbd", om.sbd_cot, hv.sbd, t["sbd"], t["sbd_bubble"]),
                                               ("ma_de", om.ma_de_cot, hv.ma_de, t["ma_de"], t["ma_de_bubble"])):
            for i, (b, h, d) in enumerate(zip(om_cot, hv_cot, dc["cot"][ten])):
                rec["cot"].append({"truong": ten, "i": i, "viet": viet[i], "that_bubble": "?" if bub[i] == "-" else bub[i],
                                   "b": b.chu_so, "b_cx": bool(b.can_xem), "b_ly": list(b.ly_do), "b_p": list(b.xac_suat_to), "b_tin": b.do_tin_cay,
                                   "cnn": h.chu_so, "cnn_p": h.p, "top": h.top_k, "p_bub": None, "o_trong": h.o_trong, "loi_o": h.loi_o,
                                   "chac": d.chac, "ly_do": list(d.ly_do)})
            rec["truong"][ten] = {"gia_tri": dc[ten][0], "chac": dc[ten][1], "ly_do": list(dc[ten][2]), "that": viet}
        out.append(rec)
        print(f"  {p.stem}: câu cần xem {sum(c['cx'] for c in rec['cau'])}/40, SBD chắc {rec['truong']['sbd']['chac']}, mã đề chắc {rec['truong']['ma_de']['chac']}")
    AE.mkdir(parents=True, exist_ok=True)
    f = AE / f"doc_{a.tap}.json"
    f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"Ghi {f}: {len(out)} ảnh, {time.time() - t0:.0f} s")
    if a.tap == "dot2":
        doi_chieu_dot2(out)


def doi_chieu_dot2(out: list[dict]):
    """Đường offline phải trùng lần chạy API đợt 2 (cùng mã đóng băng): cùng trạng thái, ô, cờ, lý do từng câu và từng cột."""
    kq = {r["anh"]: r for r in json.loads(KQ_DOT2.read_text(encoding="utf-8"))["anh"]}
    khac_cau, khac_cot, n_cau, n_cot = [], [], 0, 0
    for r in out:
        k = kq[r["anh"]]
        for c, ck in zip(r["cau"], k["cau"]):
            n_cau += 1
            if (sang_db(c["doc_tt"]), c["doc_o"], c["cx"], sorted(c["ly_do"])) != (ck["doc"], ck["doc_o"], ck["cx"], sorted(ck["ly_do"])):
                khac_cau.append((r["anh"], c["n"]))
        for c, ck in zip(r["cot"], k["cot"]):
            n_cot += 1
            if (c["b"], c["cnn"], (not c["chac"]), sorted(c["ly_do"])) != (ck["bubble"], ck["may"], ck["cx"], sorted(ck["ly_do"])):
                khac_cot.append((r["anh"], c["truong"], c["i"]))
    print(f"Đối chiếu với lần chạy API đợt 2: câu khác {len(khac_cau)}/{n_cau}, cột khác {len(khac_cot)}/{n_cot}"
          + (f"; vd {khac_cau[:3]} {khac_cot[:3]}" if khac_cau or khac_cot else " – TRÙNG"))
    (AE / "doi_chieu_dot2.json").write_text(json.dumps({"cau_khac": khac_cau, "cot_khac": khac_cot, "n_cau": n_cau, "n_cot": n_cot},
                                                       ensure_ascii=False), encoding="utf-8")


def sang_db(tt: str) -> str:
    return {"trong": "blank", "ro": "filled", "mo": "faint", "nhieu": "multiple"}[tt]


# ------------------------------------------------------------------------------------------- phân rã
def nap(tap: str) -> list[dict]:
    return [r for r in json.loads((AE / f"doc_{tap}.json").read_text(encoding="utf-8")) if not r["tu_choi"]]


def ly_do_chinh(ly: list[str]) -> str:
    """Gộp lý do của 1 câu thành 1 nhóm (thứ tự ưu tiên: vị trí > nhiều ô > ô mờ > lưng chừng > vết nhỏ > tô nhạt cả tờ)."""
    for m in ("vi_tri", "nhieu_o", "o_mo", "tin_cay_thap", "vet_nho", "to_nhat"):
        if m in ly:
            return m
    return "+".join(ly) or "(không)"


TEN_LY = {"vi_tri": "vị trí", "nhieu_o": "nhiều ô", "o_mo": "ô mờ", "tin_cay_thap": "lưng chừng (tin cậy thấp)", "vet_nho": "vết nhỏ",
          "to_nhat": "tô nhạt cả tờ"}


def phan_loai_cau(c: dict) -> str:
    """Câu CẦN XEM thuộc nhóm nào: 'sai' (máy đọc sai ô) / 'dung_chinh_sach' (đọc đúng nhưng câu thật mờ / nhiều ô / vết – người phải quyết
    hoặc chính sách) / 'khong_can' (câu thật 1 đậm hoặc trống, máy đọc đúng ô VÀ đúng trạng thái)."""
    dung_o = c["doc_o"] == c["chon_that"]
    if not dung_o:
        return "sai"
    if c["tt_that"] in ("ro", "trong") and (c["doc_tt"] == c["tt_that"]):
        return "khong_can"
    return "dung_chinh_sach"


def bang_cau(rs: list[dict]) -> list[str]:
    cau = [c for r in rs for c in r["cau"]]
    cx = [c for c in cau if c["cx"]]
    d = ["### a) Câu trả lời", "", f"{len(cau)} câu, cần xem {len(cx)} ({100 * len(cx) / len(cau):.1f}%). "
         "Đúng ô = tập ô máy đọc trùng tập ô thật (vết chấm = trống). Đúng hết = đúng ô + đúng trạng thái rõ / mờ / nhiều / trống.", "",
         "| Lý do chính | Số câu | % câu cần xem | Đúng ô | Đúng hết | Máy đọc SAI ô |", "|---|---|---|---|---|---|"]
    nhom = defaultdict(list)
    for c in cx:
        nhom[ly_do_chinh(c["ly_do"])].append(c)
    for k, v in sorted(nhom.items(), key=lambda kv: -len(kv[1])):
        do = sum(c["doc_o"] == c["chon_that"] for c in v)
        dh = sum(c["doc_o"] == c["chon_that"] and phan_loai_cau(c) != "sai" and c["doc_tt"] == ("trong" if c["tt_that"] == "vet" else c["tt_that"]) for c in v)
        d.append(f"| {TEN_LY.get(k, k)} | {len(v)} | {100 * len(v) / len(cx):.1f}% | {do} ({100 * do / len(v):.0f}%) | {dh} ({100 * dh / len(v):.0f}%) | {len(v) - do} |")
    d += ["", "Theo loại câu THẬT (nhãn trên giấy):", "", "| Loại thật | Số câu | Cần xem | Trong đó máy đọc đúng ô |", "|---|---|---|---|"]
    lo = defaultdict(list)
    for c in cau:
        lo[c["loai"]].append(c)
    for k, v in sorted(lo.items(), key=lambda kv: -len(kv[1])):
        x = [c for c in v if c["cx"]]
        d.append(f"| {k} | {len(v)} | {len(x)} ({100 * len(x) / len(v):.0f}%) | {sum(c['doc_o'] == c['chon_that'] for c in x)} |")
    sai_khong_co = [c for c in cau if not c["cx"] and c["doc_o"] != c["chon_that"]]
    d += ["", f"Câu KHÔNG cần xem mà đọc sai ô (sai âm thầm): **{len(sai_khong_co)}**"]
    return d


def bang_cot(rs: list[dict]) -> list[str]:
    cot = [c for r in rs for c in r["cot"]]
    cx = [c for c in cot if not c["chac"]]
    d = ["### b) SBD / mã đề (từng cột chữ số)", "", f"{len(cot)} cột, cần xem {len(cx)} ({100 * len(cx) / len(cot):.1f}%). "
         "'Bubble đúng' = chữ số bubble máy đọc = chữ số thật (chữ viết tay trên giấy = SBD thật). 'Chỉ tin bubble' = bubble đọc được ('?' tính sai) và đúng.", "",
         "| Lý do | Số cột | % cột cần xem | Bubble đúng | Chữ viết tay (CNN) đúng | Bubble đọc được | Chỉ tin bubble đúng |", "|---|---|---|---|---|---|---|"]
    nhom = defaultdict(list)
    for c in cx:
        nhom["+".join(c["ly_do"]) or "(không)"].append(c)
    for k, v in sorted(nhom.items(), key=lambda kv: -len(kv[1])):
        bd = sum(c["b"] == c["viet"] for c in v)
        hd = sum(c["cnn"] == c["viet"] for c in v)
        bdd = sum(c["b"] != "?" for c in v)
        d.append(f"| {k} | {len(v)} | {100 * len(v) / len(cx):.1f}% | {bd} ({100 * bd / len(v):.0f}%) | {hd} ({100 * hd / len(v):.0f}%) | {bdd} | "
                 f"{bd}/{len(v)} |")
    ok = [c for c in cot if c["chac"]]
    d += ["", f"Cột chắc (không cần xem): {len(ok)}; bubble đúng {sum(c['b'] == c['viet'] for c in ok)}/{len(ok)}; "
          f"CNN đúng {sum(c['cnn'] == c['viet'] for c in ok)}/{len(ok)}."]
    tr = [(r["anh"], k, v) for r in rs for k, v in r["truong"].items()]
    sai_il = [(a, k) for a, k, v in tr if v["chac"] and v["gia_tri"] != v["that"]]
    anh_cx = sum(any(not v["chac"] for v in r["truong"].values()) for r in rs)
    d += [f"Ảnh có SBD hoặc mã đề cần xem: {anh_cx}/{len(rs)} ({100 * anh_cx / len(rs):.1f}%). Trường nhận mà sai (sai âm thầm): **{len(sai_il)}** {sai_il}"]
    return d


def mot_dap_an(s: str) -> str:
    """Quy tắc điểm thật (tools/eval_he_thong.dung_that): câu đúng ⇔ có ĐÚNG một dấu (rõ hoặc mờ) trùng đáp án. Trả chữ đó, '' nếu 0 / ≥ 2 dấu."""
    return s if len(s) == 1 else ""


def cung_ket_qua(c: dict) -> bool:
    """Bỏ cờ và chấm theo ô máy đọc thì điểm trùng điểm thật với MỌI đáp án có thể (A/B/C/D)."""
    return mot_dap_an(c["doc_o"]) == mot_dap_an(c["chon_that"])


NHOM_THAT = {"1 đậm": "1 đậm / trống", "trống": "1 đậm / trống", "1 mờ": "1 mờ", "vết (chấm nhỏ)": "vết",
             "hai đậm": "nhiều đậm", "ba đậm": "nhiều đậm", "≥4 đậm": "nhiều đậm"}


def bang_khong_can(rs: list[dict]) -> list[str]:
    cau = [c for r in rs for c in r["cau"] if c["cx"]]
    d = ["### c) \"Cần xem không cần thiết\"", "",
         "Định nghĩa: bỏ cờ, chấm theo ô máy đọc (1 ô = chọn ô đó; 0 / ≥ 2 ô = sai) mà điểm TRÙNG điểm thật với mọi đáp án có thể (quy tắc điểm thật của "
         "đợt 2: đúng ⇔ có đúng một dấu, rõ HOẶC mờ, trùng đáp án). Cột còn lại = cờ làm thay đổi điểm (cần thật).", "",
         "| Lý do chính | Cần xem | Cờ cần thật (điểm sẽ sai) | Không cần: thật 1 đậm / trống | thật nhiều ô TOÀN đậm | thật 1 mờ | thật nhiều ô có mờ | thật vết | Tổng không cần |",
         "|---|---|---|---|---|---|---|---|---|"]
    nhom = defaultdict(list)
    for c in cau:
        nhom[ly_do_chinh(c["ly_do"])].append(c)
    tong = Counter()
    for k, v in sorted(nhom.items(), key=lambda kv: -len(kv[1])):
        dem = Counter("can" if not cung_ket_qua(c) else NHOM_THAT.get(c["loai"], "nhiều có mờ") for c in v)
        kc = len(v) - dem["can"]
        tong.update(dem)
        tong["kc"] += kc
        d.append(f"| {TEN_LY.get(k, k)} | {len(v)} | {dem['can']} | {dem['1 đậm / trống']} | {dem['nhiều đậm']} | {dem['1 mờ']} | {dem['nhiều có mờ']} | "
                 f"{dem['vết']} | {kc} |")
    n = len(cau) or 1
    kq = tong["1 đậm / trống"] + tong["nhiều đậm"]
    d.append(f"| **Tổng** | {len(cau)} | {tong['can']} ({100 * tong['can'] / n:.1f}%) | {tong['1 đậm / trống']} | {tong['nhiều đậm']} | {tong['1 mờ']} | "
             f"{tong['nhiều có mờ']} | {tong['vết']} | **{tong['kc']} ({100 * tong['kc'] / n:.1f}%)** |")
    d += ["", f"Trong đó KHÔNG phụ thuộc quy ước nhãn (thật 1 đậm / trống, thật nhiều ô toàn đậm): **{kq} ({100 * kq / n:.1f}%)**. Phần còn lại ('mờ', "
          "'nhiều có mờ', 'vết') chỉ 'không cần' THEO QUY ƯỚC của bộ dữ liệu (mờ = có chọn, chấm = không chọn); ngoài đời dấu mờ có thể là vết tẩy, "
          "chấm có thể là ý chọn – đó là lý do thiết kế bắt người xem."]
    cot = [c for r in rs for c in r["cot"] if not c["chac"]]
    kc = [c for c in cot if c["b"] == c["viet"] and c["b"] == c["that_bubble"] and not c["b_cx"]]
    d += ["", f"SBD / mã đề: {len(cot)} cột cần xem; trong đó bubble đọc được, OMR không gắn cờ và ĐÚNG chữ số thật: **{len(kc)} ({100 * len(kc) / max(len(cot), 1):.1f}%)** "
          f"– phần này 'không cần' NẾU chỉ tin bubble (lý do: {dict(Counter('+'.join(c['ly_do']) for c in kc))})."]
    return d


def cmd_phan_ra(a):
    rs = nap(a.tap)
    d = [f"## Phân rã \"cần xem\" – tập {a.tap} ({len(rs)} ảnh, đường đọc offline = backend)", ""]
    d += bang_cau(rs) + [""] + bang_cot(rs) + [""] + bang_khong_can(rs)
    (AE / f"phan_ra_{a.tap}.md").write_text("\n".join(d) + "\n", encoding="utf-8")
    print("\n".join(d))


# ------------------------------------------------------------------------------------------- đề xuất: CHỈNH trên dev, THỬ trên đợt 2
LUOI_THETA1 = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)
LUOI_TAU2 = (0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.05)
TRAN_MO_PHONG = 0.01          # ĐX2: tỉ lệ nhận nhầm khi MÔ PHỎNG tô sai bubble phải ≤ 1% trên tập chỉnh (chốt trước khi tính)


def ti_le_ro(P_o) -> float:
    p_to = P_o[1] + P_o[2]
    return P_o[2] / p_to if p_to > 0 else 0.0


def dx1_nhan(c: dict, theta: float) -> bool:
    """ĐX1: câu 'nhiều ô' CHỈ có lý do nhieu_o, MỌI ô được chọn đều 'rõ' với p(rõ | có tô) ≥ θ -> chấm sai tự động (không cần xem)."""
    if c["doc_tt"] != "nhieu" or c["ly_do"] != ["nhieu_o"]:
        return False
    return all(ti_le_ro(c["P"]["ABCD".index(o)]) >= theta for o in c["doc_o"])


def p_cnn(c: dict, d: str) -> float:
    """Xác suất CNN của chữ số d. Chỉ lưu top-3: chữ số ngoài top-3 lấy CẬN TRÊN = phần xác suất còn lại (thận trọng: tăng rủi ro mô phỏng)."""
    top = {str(k): v for k, v in c["top"]}
    return top.get(d, max(0.0, 1.0 - sum(top.values())))


def dx2_cot_chac(c: dict, tau: float) -> bool:
    """ĐX2 (luật mềm): cột đang cần xem vì lech_bubble / tin_cay_thap; bubble đọc được, OMR không gắn cờ, ô viết tay đọc được; nhận nếu
    p_CNN(chữ số bubble) ≥ τ (không đòi argmax trùng). Lý do khác giữ nguyên cần xem."""
    if c["chac"]:
        return True
    if set(c["ly_do"]) - {"lech_bubble", "tin_cay_thap"} or c["b"] == "?" or c["b_cx"] or c["o_trong"] or c["loi_o"]:
        return False
    return p_cnn(c, c["b"]) >= tau


def dx2_mo_phong(rs: list[dict], tau: float, truong=("sbd",)) -> tuple[int, int]:
    """Mô phỏng thí sinh TÔ SAI bubble 1 cột: thay chữ số bubble bằng mỗi chữ số sai w; luật mềm nhận nhầm khi p_CNN(w) ≥ τ
    (luật hiện hành nhận nhầm khi argmax = w và p ≥ 0,5). Chỉ cột có ô viết tay đọc được."""
    nham = tong = 0
    for r in rs:
        for c in r["cot"]:
            if c["truong"] not in truong or c["o_trong"] or c["loi_o"] or c["cnn"] == "?":
                continue
            for w in "0123456789":
                if w == c["viet"]:
                    continue
                tong += 1
                nham += p_cnn(c, w) >= tau
    return nham, tong


def dx2_danh_gia(rs: list[dict], tau: float, truong=("sbd",)) -> dict:
    cot_cx = cot_go = sai = 0
    anh_cx_cu = anh_cx_moi = 0
    for r in rs:
        cx_cu, cx_moi = False, False
        for ten in ("sbd", "ma_de"):
            cs = [c for c in r["cot"] if c["truong"] == ten]
            chac_moi = [dx2_cot_chac(c, tau) if ten in truong else c["chac"] for c in cs]
            cot_cx += sum(not c["chac"] for c in cs)
            cot_go += sum((not c["chac"]) and m for c, m in zip(cs, chac_moi))
            # trường MỚI được nhận (trước đó cần xem) mà SAI = sai âm thầm do đề xuất; giá trị nhận = chữ số bubble mọi cột (như doi_chieu_cot)
            if all(chac_moi) and not r["truong"][ten]["chac"] and "".join(c["b"] for c in cs) != r["truong"][ten]["that"]:
                sai += 1
            cx_cu |= not r["truong"][ten]["chac"]
            cx_moi |= not all(chac_moi)
        anh_cx_cu += cx_cu
        anh_cx_moi += cx_moi
    nham, tong = dx2_mo_phong(rs, tau, truong)
    return {"cot_cx": cot_cx, "cot_go": cot_go, "anh_cx_cu": anh_cx_cu, "anh_cx_moi": anh_cx_moi, "n_anh": len(rs), "sai_am_tham": sai,
            "mo_phong_nham": nham, "mo_phong_tong": tong}


def cmd_de_xuat(a):
    dev, d2 = nap("dev"), nap("dot2")
    out = {"tap_chinh": "dev 0001–0028 (56 ảnh)", "tap_thu": "đợt 2 0101–0110 (20 ảnh)"}
    L = ["## Đề xuất (CHƯA áp dụng) – chỉnh ngưỡng trên DEV 0001–0028, kết luận trên ĐỢT 2", ""]

    # ---- ĐX1
    r_mo = [ti_le_ro(c["P"]["ABCD".index(o)]) for r in dev for c in r["cau"] for o in c["chon_that"]
            if any(ch.islower() for ch in c["lab"]) and o.lower() in c["lab"] and o in c["doc_o"]]
    theta = next(t for t in LUOI_THETA1 if t > max(r_mo))
    out["dx1"] = {"theta": theta, "max_ti_le_ro_o_mo_dev": max(r_mo), "n_o_mo_dev": len(r_mo)}
    L += ["### ĐX1 – Câu tô nhiều ô, MỌI ô đều đậm chắc -> chấm SAI tự động (không cần xem)",
          f"Chỉnh trên dev: θ1 = giá trị nhỏ nhất trong {LUOI_THETA1} LỚN HƠN p(rõ | có tô) lớn nhất của ô MỜ thật được chọn ({len(r_mo)} ô, max {max(r_mo):.3f}) "
          f"-> **θ1 = {theta}**. Chỉ áp dụng khi lý do DUY NHẤT là `nhieu_o`.", "",
          "| Tập | Câu cần xem | Gỡ được | Gỡ đúng (thật nhiều ô toàn đậm) | Gỡ mà thật có dấu mờ / vết (rủi ro nếu dấu mờ là vết tẩy) | Gỡ mà điểm SAI |", "|---|---|---|---|---|---|"]
    for ten, rs in (("dev (chỉnh)", dev), ("đợt 2 (thử)", d2)):
        cx = [c for r in rs for c in r["cau"] if c["cx"]]
        go = [c for c in cx if dx1_nhan(c, theta)]
        dung = sum(c["loai"] in ("hai đậm", "ba đậm", "≥4 đậm") for c in go)
        sai_diem = sum(not cung_ket_qua(c) for c in go)
        L.append(f"| {ten} | {len(cx)} | {len(go)} ({100 * len(go) / len(cx):.1f}%) | {dung} | {len(go) - dung} | {sai_diem} |")
        out["dx1"][ten] = {"cx": len(cx), "go": len(go), "dung": dung, "rui_ro_mo": len(go) - dung, "sai_diem": sai_diem}

    # ---- ĐX2
    L += ["", "### ĐX2 – Luật mềm SBD: bubble sạch + p_CNN(chữ số bubble) ≥ τ2 -> nhận (vẫn đòi SBD có trong danh sách kỳ thi)",
          f"Chỉnh trên dev: τ2 = giá trị NHỎ NHẤT trong {LUOI_TAU2} mà tỉ lệ nhận nhầm khi MÔ PHỎNG tô sai bubble 1 cột ≤ {TRAN_MO_PHONG:.0%} "
          "(chữ số ngoài top-3 lấy cận trên). Luật hiện hành tương ứng argmax = bubble và p ≥ 0,5.", "",
          "| τ2 | dev: mô phỏng nhận nhầm | dev: cột SBD gỡ / cần xem |", "|---|---|---|"]
    chon = None
    for tau in LUOI_TAU2:
        nh, tg = dx2_mo_phong(dev, tau)
        g = dx2_danh_gia(dev, tau)
        L.append(f"| {tau} | {nh}/{tg} = {100 * nh / tg:.2f}% | {g['cot_go']}/{g['cot_cx']} (cả mã đề không đổi) |")
        if nh / tg <= TRAN_MO_PHONG:
            chon = tau
    if chon is None:
        sys.exit("ĐX2: không τ2 nào đạt trần mô phỏng trên dev – không đề xuất.")
    out["dx2"] = {"tau": chon}
    L += ["", f"-> **τ2 = {chon}**. Thử:", "",
          "| Tập | Cột cần xem (SBD+mã đề) | Cột SBD gỡ được | Ảnh có SBD/mã đề cần xem: trước -> sau | Trường nhận mà SAI | Mô phỏng tô sai bubble bị nhận |",
          "|---|---|---|---|---|---|"]
    for ten, rs in (("dev (chỉnh)", dev), ("đợt 2 (thử)", d2)):
        g = dx2_danh_gia(rs, chon)
        out["dx2"][ten] = g
        L.append(f"| {ten} | {g['cot_cx']} | {g['cot_go']} | {g['anh_cx_cu']}/{g['n_anh']} -> {g['anh_cx_moi']}/{g['n_anh']} | {g['sai_am_tham']} | "
                 f"{g['mo_phong_nham']}/{g['mo_phong_tong']} = {100 * g['mo_phong_nham'] / g['mo_phong_tong']:.2f}% |")
    tb = [(r["anh"], c["i"], c["viet"], c["b"], round(p_cnn(c, c["b"]), 3)) for r in d2 for c in r["cot"] if c["b"] != c["viet"] and c["b"] != "?"]
    L += ["", f"Ca tô sai bubble THẬT ở đợt 2 (viết ≠ bubble): {tb} – p_CNN(chữ số bubble) phải < τ2 thì luật mềm mới không nhận nhầm."]

    # ---- ĐX3
    L += ["", "### ĐX3 – Chính sách \"một dấu mờ = có chọn\": tự chấm câu chỉ có lý do `o_mo` (KHÔNG có ngưỡng chỉnh được – xem dưới)", "",
          "| Tập | Câu cần xem | Gỡ được | Gỡ mà điểm SAI (vết / tẩy đọc thành mờ) | p(có tô) của ca gỡ sai |", "|---|---|---|---|---|"]
    out["dx3"] = {}
    for ten, rs in (("dev (chỉnh)", dev), ("đợt 2 (thử)", d2)):
        cx = [c for r in rs for c in r["cau"] if c["cx"]]
        go = [c for c in cx if c["ly_do"] == ["o_mo"]]
        sai = [c for c in go if not cung_ket_qua(c)]
        ps = sorted(round(1 - c["P"]["ABCD".index(c["doc_o"])][0], 2) for c in sai)
        L.append(f"| {ten} | {len(cx)} | {len(go)} ({100 * len(go) / len(cx):.1f}%) | {len(sai)} | {ps} |")
        out["dx3"][ten] = {"cx": len(cx), "go": len(go), "sai": len(sai)}
    p_mo_that = sorted(1 - c["P"]["ABCD".index(c["doc_o"])][0] for r in d2 for c in r["cau"] if c["ly_do"] == ["o_mo"] and c["loai"] == "1 mờ")
    p_vet = [1 - c["P"]["ABCD".index(c["doc_o"])][0] for r in d2 for c in r["cau"] if c["ly_do"] == ["o_mo"] and not cung_ket_qua(c)]
    chong = sum(p >= p_mo_that[0] for p in p_vet)
    L += ["", f"Đợt 2: p(có tô) của dấu mờ THẬT (n = {len(p_mo_that)}) nằm trong [{p_mo_that[0]:.2f}; {p_mo_that[-1]:.2f}]; {chong}/{len(p_vet)} ca gỡ sai có p "
          f"≥ {p_mo_that[0]:.2f} (CHỒNG) – kể cả ngưỡng đặt đúng ở dấu mờ thật thấp nhất (nhìn tập thử, không hợp lệ) vẫn còn {chong} sai âm thầm. "
          "Dev không có vết chấm nên KHÔNG chỉnh được ngưỡng trên dev."]
    (AE / "de_xuat.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (AE / "de_xuat.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["doc", "phan-ra", "de-xuat"])
    ap.add_argument("--tap", choices=["dev", "dot2"], default="dev")
    a = ap.parse_args()
    {"doc": cmd_doc, "phan-ra": cmd_phan_ra}[a.lenh](a) if a.lenh != "de-xuat" else cmd_de_xuat(a)  # noqa: F821
