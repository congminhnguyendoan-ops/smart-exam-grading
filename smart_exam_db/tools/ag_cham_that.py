"""
ag_cham_that.py - Lệnh AG: chấm ảnh chụp GIẤY THẬT so với kịch bản (data/_eval/ag/kich_ban.json) theo tiêu chí docs/tieu_chi_thu_giay_that.md
(commit 18fd340 – chốt TRƯỚC công cụ này). Pipeline OFFLINE giống backend: preprocess -> omr.doc_phieu -> ocr.doc_chu_so -> ocr.doi_chieu_dinh_danh;
không CSDL, không server. KHÔNG thêm tiêu chí mới.

  python tools/ag_cham_that.py cham [--thu-muc data/anh_that_ag] [--ra data/_eval/ag]   # -> ket_qua.md + ket_qua.json
  python tools/ag_cham_that.py tu-kiem      # ảnh GIẢ LẬP vẽ từ kịch bản (thư mục tạm, xoá khi xong) -> data/_eval/ag/tu_kiem/ – KHÔNG dùng kết luận H3

Tên ảnh: T01.jpg … T10.jpg (điều kiện thường), T0X_kho.jpg (điều kiện khó). JPG / JPEG / PNG / HEIC / HEIF, không phân biệt hoa thường.
Tên khác -> liệt kê "bỏ qua (tên không đúng)". Ảnh bị tiền xử lý từ chối -> liệt kê kèm lý do (KHÔNG phải sai âm thầm). Tờ không có ảnh đọc được -> báo rõ.
"Trường được nhận" = đối chiếu hai kênh chắc VÀ SBD / mã đề có trong danh sách kỳ thi 1633 (giống backend: ngoài danh sách -> giữ lại cần xem).
"""
import argparse
import json
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

AG = ROOT / "data" / "_eval" / "ag"
KICH_BAN = AG / "kich_ban.json"
THU_MUC_ANH = ROOT / "data" / "anh_that_ag"
DUOI = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
TEN = re.compile(r"^(T\d{2})(_kho)?$", re.IGNORECASE)
LOAI = ("binh_thuong", "bo_trong", "nhat", "hai_o", "te", "vet")
TEN_LOAI = {"binh_thuong": "bình thường (1 ô đậm)", "bo_trong": "bỏ trống", "nhat": "nhạt", "hai_o": "hai ô", "te": "tẩy", "vet": "vết"}
DOT2 = {"binh_thuong": (11, 272), "bo_trong": (0, 118), "anh_sbd_ma_de": (9, 20)}       # docs/ket_qua_dot2.md – để đối chiếu C2
THETA1 = 0.95                                                                             # ĐX1 (lệnh AE) – chỉ để báo C3


# ------------------------------------------------------------------------------------------------ so sánh (THUẦN – pytest không cần ảnh)
def phan_loai_cau(dap_an: str, doc: str, can_xem: bool) -> str:
    """tieu_chi mục 2: cx -> can_xem; không cx và tập ô đọc = tập ô đúng -> doc_dung; còn lại -> sai_am_tham."""
    if can_xem:
        return "can_xem"
    return "doc_dung" if "".join(sorted(doc)) == "".join(sorted(dap_an)) else "sai_am_tham"


def phan_loai_cot(bubble_dung: str, bubble_doc: str, can_xem: bool) -> str:
    """Cột SBD / mã đề. bubble_dung = chữ số tô ('?' với cột thiếu bubble). Không cần xem mà bubble đọc ≠ đúng -> sai_am_tham."""
    if can_xem:
        return "can_xem"
    return "doc_dung" if bubble_doc == bubble_dung else "sai_am_tham"


def cp(k: int, n: int) -> list:
    """Clopper–Pearson 95%."""
    from scipy.stats import beta
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [round(lo, 4), round(hi, 4)]


def danh_gia_anh(rec: dict, to: dict) -> dict:
    """So một ảnh đã đọc (rec – xem doc_anh) với kịch bản của tờ. Trả bản ghi từng câu / cột / trường. THUẦN."""
    ra = {"anh": rec["anh"], "to": rec["to"], "dieu_kien": rec["dieu_kien"], "but": to["but"], "cau": [], "cot": [], "truong": {}}
    for c in rec["cau"]:
        kb = to["cau"][str(c["n"])]
        kq = phan_loai_cau(kb["dap_an"], c["doc_o"], c["cx"])
        ra["cau"].append({"n": c["n"], "loai": kb["loai"], "dap_an": kb["dap_an"], "doc": c["doc_o"], "trang_thai": c["doc_tt"], "cx": c["cx"],
                          "ly_do": c["ly_do"], "ket_qua": kq, "chap_nhan": kq in kb["chap_nhan"], "P": c.get("P"),
                          "to_truoc": kb.get("to_truoc"), "cham": kb.get("cham")})
    tb = {(x["truong"], x["vi_tri"]) for x in to["thieu_bubble"]}
    for ten in ("sbd", "ma_de"):
        gia = to[ten]
        cot = [x for x in rec["cot"] if x["truong"] == ten]
        for x in cot:
            thieu = (ten, x["i"] + 1) in tb
            bd = "?" if thieu else gia[x["i"]]
            kq = phan_loai_cot(bd, x["b"], not x["chac"])
            ra["cot"].append({"truong": ten, "vi_tri": x["i"] + 1, "thieu_bubble": thieu, "bubble_dung": bd, "bubble_doc": x["b"], "viet_dung": gia[x["i"]],
                              "cnn_doc": x["cnn"], "cnn_p": x["cnn_p"], "cx": not x["chac"], "ly_do": x["ly_do"], "ket_qua": kq,
                              "bubble_kenh_dung": x["b"] == bd, "viet_kenh_dung": x["cnn"] == gia[x["i"]]})
        t = rec["truong"][ten]
        nhan = bool(t["chac"]) and t["trong_ds"] is True
        co_thieu = any(tr == ten for tr, _ in tb)
        ra["truong"][ten] = {"gia_tri": t["gia_tri"], "dung": gia, "nhan": nhan, "ly_do": t["ly_do"],
                             "ket_qua": "can_xem" if not nhan else ("doc_dung" if t["gia_tri"] == gia else "sai_am_tham"),
                             "co_cot_thieu_bubble": co_thieu,
                             "h3b_dat": None if not co_thieu else (not nhan and any(c["thieu_bubble"] and "thieu_bubble" in c["ly_do"]
                                                                                    for c in ra["cot"] if c["truong"] == ten))}
    ra["phai_xem"] = any(c["cx"] for c in ra["cau"]) or any(v["ket_qua"] == "can_xem" for v in ra["truong"].values())
    ra["sbd_ma_de_phai_xem"] = any(v["ket_qua"] == "can_xem" for v in ra["truong"].values())
    return ra


def tong_hop(danh_gia: list[dict], kb: dict, tu_choi: list[dict], bo_qua: list[str]) -> dict:
    """Bảng theo loại, SBD / mã đề, điều kiện, bút; C1 / C2 / C3 / H3. THUẦN."""
    def bang(cau):
        d = defaultdict(Counter)
        for c in cau:
            d[c["loai"]]["n"] += 1
            d[c["loai"]][c["ket_qua"]] += 1
        return {l: {"n": d[l]["n"], "doc_dung": d[l]["doc_dung"], "can_xem": d[l]["can_xem"], "sai_am_tham": d[l]["sai_am_tham"],
                    "ti_le_can_xem": round(d[l]["can_xem"] / d[l]["n"], 4) if d[l]["n"] else None,
                    "ci_can_xem": cp(d[l]["can_xem"], d[l]["n"])} for l in LOAI if d[l]["n"]}
    cau = [dict(c, anh=a["anh"], to=a["to"], dieu_kien=a["dieu_kien"], but=a["but"]) for a in danh_gia for c in a["cau"]]
    cot = [dict(c, anh=a["anh"]) for a in danh_gia for c in a["cot"]]
    truong = [dict(v, anh=a["anh"], truong=k) for a in danh_gia for k, v in a["truong"].items()]
    kq = {"so_anh_doc": len(danh_gia), "tu_choi": tu_choi, "bo_qua": bo_qua,
          "to_chua_kiem": sorted(set(kb["to"]) - {a["to"] for a in danh_gia}),
          "theo_loai": bang(cau), "theo_dieu_kien": {dk: bang([c for c in cau if c["dieu_kien"] == dk]) for dk in ("thuong", "kho")},
          "theo_but": {b: bang([c for c in cau if c["but"] == b]) for b in ("bi", "chi")}}
    # SBD / mã đề
    kq["cot"] = {"n": len(cot), "can_xem": sum(c["cx"] for c in cot), "sai_am_tham": sum(c["ket_qua"] == "sai_am_tham" for c in cot),
                 "doc_dung": sum(c["ket_qua"] == "doc_dung" for c in cot), "bubble_kenh_dung": sum(c["bubble_kenh_dung"] for c in cot),
                 "viet_kenh_dung": sum(c["viet_kenh_dung"] for c in cot)}
    kq["truong"] = {"n": len(truong), "nhan": sum(t["nhan"] for t in truong), "can_xem": sum(t["ket_qua"] == "can_xem" for t in truong),
                    "sai_am_tham": sum(t["ket_qua"] == "sai_am_tham" for t in truong)}
    kq["anh_phai_xem"] = sum(a["phai_xem"] for a in danh_gia)
    kq["anh_sbd_ma_de_phai_xem"] = sum(a["sbd_ma_de_phai_xem"] for a in danh_gia)
    # C1
    sai = [c for c in cau if c["ket_qua"] == "sai_am_tham"]
    sai_cot = [c for c in cot if c["ket_qua"] == "sai_am_tham"]
    sai_tr = [t for t in truong if t["ket_qua"] == "sai_am_tham"]
    kq["sai_am_tham"] = {"cau": [{k: c[k] for k in ("anh", "to", "n", "loai", "dap_an", "doc", "trang_thai", "ly_do", "P")} for c in sai],
                         "cot": [{k: c[k] for k in ("anh", "truong", "vi_tri", "thieu_bubble", "bubble_dung", "bubble_doc", "cnn_doc", "cnn_p")} for c in sai_cot],
                         "truong": [{k: t[k] for k in ("anh", "truong", "gia_tri", "dung")} for t in sai_tr]}
    kq["C1"] = "chưa kiểm được (không có ảnh đọc được)" if not danh_gia else ("ĐẠT" if not (sai or sai_cot or sai_tr) else "KHÔNG ĐẠT")
    kq["C1_ci_cau"] = cp(len(sai), len(cau))
    # C3: câu tẩy
    te = [c for c in cau if c["loai"] == "te"]
    def ro(c, nguong):
        return bool(c["P"]) and all((c["P"]["ABCD".index(o)][2] / max(c["P"]["ABCD".index(o)][1] + c["P"]["ABCD".index(o)][2], 1e-9)) >= nguong
                                    for o in c["doc"])
    nhieu_te = [c for c in te if c["to_truoc"] and c["to_truoc"] in c["doc"] and c["dap_an"] in c["doc"] and "nhieu_o" in c["ly_do"]]
    kq["C3"] = {"n": len(te), "doc_dung": sum(c["ket_qua"] == "doc_dung" for c in te), "can_xem": sum(c["ket_qua"] == "can_xem" for c in te),
                "sai_am_tham": sum(c["ket_qua"] == "sai_am_tham" for c in te), "doc_thanh_nhieu_o": len(nhieu_te),
                "nhieu_o_moi_o_ro_05": sum(ro(c, 0.5) for c in nhieu_te), "nhieu_o_moi_o_ro_theta1": sum(ro(c, THETA1) for c in nhieu_te),
                "chi_tiet": [{k: c[k] for k in ("anh", "n", "to_truoc", "dap_an", "doc", "trang_thai", "ly_do", "ket_qua")} for c in te]}
    # H3
    h3b = [t for t in truong if t["co_cot_thieu_bubble"]]
    kq["H3"] = {"H3a_truong_nhan_ma_sai": len(sai_tr), "H3b_so_truong_kiem": len(h3b), "H3b_vi_pham": sum(t["h3b_dat"] is False for t in h3b),
                "H3b_to_chua_kiem": sorted({m for m, t in kb["to"].items() if t["thieu_bubble"]} - {a["to"] for a in danh_gia})}
    if not danh_gia or not h3b:
        kq["H3"]["ket_luan"] = "chưa kết luận được"
    elif len(sai_tr) or kq["H3"]["H3b_vi_pham"]:
        kq["H3"]["ket_luan"] = "KHÔNG ĐẠT"
    elif kq["H3"]["H3b_to_chua_kiem"]:
        kq["H3"]["ket_luan"] = "ĐẠT phần đã kiểm; tờ " + ", ".join(kq["H3"]["H3b_to_chua_kiem"]) + " chưa kiểm được H3b"
    else:
        kq["H3"]["ket_luan"] = "ĐẠT"
    return kq


# ------------------------------------------------------------------------------------------------ đọc ảnh (pipeline OFFLINE)
def liet_ke(thu_muc: Path) -> tuple[list[tuple[Path, str, str]], list[str]]:
    anh, bo = [], []
    for p in sorted(thu_muc.iterdir()) if thu_muc.exists() else []:
        if not p.is_file():
            continue
        m = TEN.match(p.stem)
        if p.suffix.lower() not in DUOI or not m:
            bo.append(p.name)
            continue
        anh.append((p, m.group(1).upper(), "kho" if m.group(2) else "thuong"))
    return anh, bo


def doc_anh(p: Path, to_ma: str, dk: str, lay, mh, mh_ocr, ds_sbd, ds_ma) -> dict:
    from cv_engine import ocr
    from cv_engine.omr import doc_phieu
    from cv_engine.preprocessing import preprocess
    kq = preprocess(str(p), lay)
    rec = {"anh": p.name, "to": to_ma, "dieu_kien": dk, "tu_choi": "" if kq.ok else kq.ly_do}
    if not kq.ok:
        return rec
    om = doc_phieu(kq, lay, mh)
    hv = ocr.doc_chu_so(kq, lay, mh_ocr)
    sbd_trong = None if "?" in om.sbd else om.sbd in ds_sbd                     # giống service.py
    ma_trong = None if "?" in om.ma_de else om.ma_de in ds_ma
    dc = ocr.doi_chieu_dinh_danh(om, hv, sbd_trong, ma_trong, mo_hinh=mh_ocr)
    rec["cau"] = [{"n": c.cau, "doc_o": c.dap_an, "doc_tt": c.trang_thai, "cx": bool(c.can_xem), "ly_do": list(c.ly_do),
                   "P": [[c.xac_suat[o][k] for k in ("blank", "faint", "filled")] for o in "ABCD"]} for c in om.cau]
    rec["cot"] = []
    for ten, om_cot, hv_cot in (("sbd", om.sbd_cot, hv.sbd), ("ma_de", om.ma_de_cot, hv.ma_de)):
        for i, (b, h, d) in enumerate(zip(om_cot, hv_cot, dc["cot"][ten])):
            rec["cot"].append({"truong": ten, "i": i, "b": b.chu_so, "cnn": h.chu_so, "cnn_p": round(float(h.p), 4), "chac": d.chac, "ly_do": list(d.ly_do)})
    rec["truong"] = {ten: {"gia_tri": dc[ten][0], "chac": dc[ten][1], "ly_do": list(dc[ten][2]), "trong_ds": tr}
                     for ten, tr in (("sbd", sbd_trong), ("ma_de", ma_trong))}
    return rec


def cham(thu_muc: Path, ra: Path, ghi_chu: str = "") -> dict:
    from cv_engine import ocr
    from cv_engine.omr import nap_mo_hinh
    from cv_engine.preprocessing import nap_layout
    kb = json.loads(KICH_BAN.read_text(encoding="utf-8"))
    anh, bo = liet_ke(thu_muc)
    lay, mh, mh_ocr = nap_layout("phieu"), nap_mo_hinh(), ocr.nap_mo_hinh_ocr()
    ds_sbd, ds_ma = set(kb["ky_thi_danh_sach"]["sbd"]), set(kb["ky_thi_danh_sach"]["ma_de"])
    dg, tu_choi, t0 = [], [], time.time()
    for p, ma, dk in anh:
        if ma not in kb["to"]:
            bo.append(f"{p.name} (không có tờ {ma} trong kịch bản)")
            continue
        rec = doc_anh(p, ma, dk, lay, mh, mh_ocr, ds_sbd, ds_ma)
        if rec["tu_choi"]:
            from cv_engine.preprocessing import MA_LY_DO
            tu_choi.append({"anh": p.name, "to": ma, "ly_do": rec["tu_choi"], "thong_bao": MA_LY_DO.get(rec["tu_choi"], "")})
            print(f"  {p.name}: BỊ TỪ CHỐI – {rec['tu_choi']}")
            continue
        dg.append(danh_gia_anh(rec, kb["to"][ma]))
        print(f"  {p.name}: đọc xong")
    kq = tong_hop(dg, kb, tu_choi, bo)
    kq["thu_muc"], kq["ghi_chu"], kq["giay"] = str(thu_muc), ghi_chu, round(time.time() - t0, 1)
    kq["chi_tiet_anh"] = dg
    ra.mkdir(parents=True, exist_ok=True)
    (ra / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (ra / "ket_qua.md").write_text(bao_cao_md(kq), encoding="utf-8")
    print(f"Ghi {ra / 'ket_qua.md'}  |  C1: {kq['C1']}  |  H3: {kq['H3']['ket_luan']}")
    return kq


def bao_cao_md(kq: dict) -> str:
    def pt(k, n):
        return f"{k}/{n} ({100 * k / n:.1f}%)" if n else "–"
    L = [f"# Kết quả thử giấy thật (lệnh AG){' – ' + kq['ghi_chu'] if kq['ghi_chu'] else ''}", "",
         f"Tiêu chí: `docs/tieu_chi_thu_giay_that.md` (commit 18fd340). Thư mục ảnh: `{kq['thu_muc']}`. Ảnh đọc được: {kq['so_anh_doc']}.", "",
         f"## Kết luận theo tiêu chí", "", f"- **C1 (sai âm thầm = 0): {kq['C1']}** – CP95 tỉ lệ câu sai âm thầm {kq['C1_ci_cau']}",
         f"- **H3: {kq['H3']['ket_luan']}** – H3a trường nhận mà sai: {kq['H3']['H3a_truong_nhan_ma_sai']}; H3b vi phạm {kq['H3']['H3b_vi_pham']} / "
         f"{kq['H3']['H3b_so_truong_kiem']} trường có cột thiếu bubble",
         "- C2, C3: chỉ báo cáo (không có ngưỡng). Mẫu nhỏ, khoảng tin cậy rộng.", ""]
    if kq["tu_choi"] or kq["bo_qua"] or kq["to_chua_kiem"]:
        L += ["## Ảnh bị loại / tờ chưa kiểm", ""]
        L += [f"- {x['anh']} (tờ {x['to']}): **bị tiền xử lý từ chối** – `{x['ly_do']}` {x['thong_bao']}" for x in kq["tu_choi"]]
        L += [f"- {x}: bỏ qua (tên không đúng mẫu T01.jpg / T01_kho.jpg)" for x in kq["bo_qua"]]
        L += [f"- **Tờ {m}: chưa kiểm được** (không có ảnh đọc được)" for m in kq["to_chua_kiem"]] + [""]
    L += ["## Câu theo loại kịch bản (mọi ảnh)", "", "| Loại | Số câu | Đọc đúng | Cần xem (CP95) | Sai âm thầm |", "|---|---|---|---|---|"]
    for l, v in kq["theo_loai"].items():
        L.append(f"| {TEN_LOAI[l]} | {v['n']} | {v['doc_dung']} | {pt(v['can_xem'], v['n'])} {v['ci_can_xem']} | **{v['sai_am_tham']}** |")
    d2 = DOT2
    bt, btr = kq["theo_loai"].get("binh_thuong"), kq["theo_loai"].get("bo_trong")
    L += ["", "**C2 – đối chiếu đợt 2:** câu 1 ô đậm cần xem: lần này " + (pt(bt["can_xem"], bt["n"]) if bt else "–")
          + f" · đợt 2 {pt(*d2['binh_thuong'])}; câu trống: lần này " + (pt(btr["can_xem"], btr["n"]) if btr else "–") + f" · đợt 2 {pt(*d2['bo_trong'])}; "
          f"ảnh có SBD / mã đề cần xem: lần này {pt(kq['anh_sbd_ma_de_phai_xem'], kq['so_anh_doc'])} · đợt 2 {pt(*d2['anh_sbd_ma_de'])}; "
          f"ảnh phải xem (câu hoặc SBD / mã đề): {pt(kq['anh_phai_xem'], kq['so_anh_doc'])}.", ""]
    for nhom, ten in (("theo_dieu_kien", "điều kiện chụp"), ("theo_but", "bút")):
        L += [f"### Theo {ten}", "", "| Nhóm | Loại | Số câu | Đọc đúng | Cần xem | Sai âm thầm |", "|---|---|---|---|---|---|"]
        for g, b in kq[nhom].items():
            for l, v in b.items():
                L.append(f"| {g} | {TEN_LOAI[l]} | {v['n']} | {v['doc_dung']} | {v['can_xem']} | {v['sai_am_tham']} |")
        L.append("")
    c, t = kq["cot"], kq["truong"]
    L += ["## SBD / mã đề", "", "| Mức | Số | Đọc đúng | Cần xem | Sai âm thầm |", "|---|---|---|---|---|",
          f"| Cột | {c['n']} | {c['doc_dung']} | {c['can_xem']} | **{c['sai_am_tham']}** |",
          f"| Trường | {t['n']} | {t['nhan'] - t['sai_am_tham']} (nhận đúng) | {t['can_xem']} | **{t['sai_am_tham']}** |", "",
          f"Kênh riêng (mọi cột): bubble đúng {pt(c['bubble_kenh_dung'], c['n'])} · chữ viết tay (CNN) đúng {pt(c['viet_kenh_dung'], c['n'])}.", ""]
    c3 = kq["C3"]
    L += ["## C3 – câu tẩy", "", f"{c3['n']} câu: đọc đúng {c3['doc_dung']}, cần xem {c3['can_xem']}, sai âm thầm **{c3['sai_am_tham']}**; đọc thành 'nhiều ô' (cả ô tẩy + ô tô lại) "
          f"**{c3['doc_thanh_nhieu_o']}**, trong đó mọi ô 'rõ' (p rõ | có tô ≥ 0,5): {c3['nhieu_o_moi_o_ro_05']}, ≥ θ1 {THETA1} (luật ĐX1): **{c3['nhieu_o_moi_o_ro_theta1']}**.", ""]
    if c3["chi_tiet"]:
        L += ["| Ảnh | Câu | Tẩy | Tô lại | Máy đọc | Trạng thái | Lý do | Kết quả |", "|---|---|---|---|---|---|---|---|"]
        L += [f"| {x['anh']} | {x['n']} | {x['to_truoc']} | {x['dap_an']} | {x['doc'] or '–'} | {x['trang_thai']} | {', '.join(x['ly_do']) or '–'} | {x['ket_qua']} |"
              for x in c3["chi_tiet"]] + [""]
    s = kq["sai_am_tham"]
    L += ["## Danh sách sai âm thầm", ""]
    if not (s["cau"] or s["cot"] or s["truong"]):
        L.append("Không có.")
    for x in s["cau"]:
        pd = {o: round(x["P"]["ABCD".index(o)][1] + x["P"]["ABCD".index(o)][2], 3) for o in "ABCD"} if x["P"] else {}
        L.append(f"- Câu: {x['anh']} câu {x['n']} – kịch bản `{x['loai']}` đúng `{x['dap_an'] or 'trống'}`, máy đọc `{x['doc'] or 'trống'}` ({x['trang_thai']}), p(có tô) {pd}")
    for x in s["cot"]:
        L.append(f"- Cột: {x['anh']} {x['truong']} cột {x['vi_tri']}{' (thiếu bubble)' if x['thieu_bubble'] else ''} – bubble đúng `{x['bubble_dung']}`, "
                 f"đọc `{x['bubble_doc']}`, CNN `{x['cnn_doc']}` ({x['cnn_p']})")
    for x in s["truong"]:
        L.append(f"- Trường: {x['anh']} {x['truong']} nhận `{x['gia_tri']}` ≠ `{x['dung']}`")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------ tự kiểm (ảnh giả lập)
XAM = {"dam": 30, "nhat": 170, "te_vet_tay": 215, "cham": 30}      # cùng mức xám ảnh giả đợt 2 (tools/eval_dot2.tao_gia); vết tẩy xám nhạt 215


def ve_to(to: dict, sai_co_y: dict | None = None):
    """Vẽ một tờ giả lập từ kịch bản lên phiếu trắng (ảnh xám 300 DPI). sai_co_y = {câu: ô} -> tô ĐẬM ô khác kịch bản (đối chứng âm)."""
    import cv2
    import numpy as np
    L = json.loads((ROOT / "answer_sheet" / "output" / "layout.json").read_text(encoding="utf-8"))
    anh = cv2.imdecode(np.fromfile(ROOT / "answer_sheet" / "output" / "phieu_trang_300dpi.png", np.uint8), cv2.IMREAD_GRAYSCALE)
    ans, R = L["answers"], L["answers"]["bubble_radius"]

    def tron(c, r, g):
        cv2.circle(anh, (int(round(c[0])), int(round(c[1]))), int(round(r)), int(g), -1)
    for n, c in to["cau"].items():
        tam = ans["centers"][n]
        if sai_co_y and int(n) in sai_co_y:
            tron(tam[sai_co_y[int(n)]], 0.85 * R, XAM["dam"])
            continue
        l = c["loai"]
        if l == "nhat":
            tron(tam[c["dap_an"]], 0.85 * R, XAM["nhat"])
        elif l == "te":
            tron(tam[c["to_truoc"]], 0.85 * R, XAM["te_vet_tay"])
            tron(tam[c["dap_an"]], 0.85 * R, XAM["dam"])
        elif l == "vet":
            tron(tam[c["cham"]], 0.3 * R, XAM["cham"])
            tron(tam[c["dap_an"]], 0.85 * R, XAM["dam"])
        else:
            for o in c["dap_an"]:
                tron(tam[o], 0.85 * R, XAM["dam"])
    tb = {(x["truong"], x["vi_tri"]) for x in to["thieu_bubble"]}
    for ten, key in (("sbd", "sbd"), ("ma_de", "exam_code")):
        for i, ch in enumerate(to[ten]):
            if (ten, i + 1) not in tb:
                tron(L[key]["bubbles"][i][int(ch)], 0.85 * L[key]["bubble_radius"], XAM["dam"])
            x, y, w, h = L[key]["handwriting_boxes"][i]                       # chữ số "viết tay" bằng font Hershey (chỉ để kênh CNN có mực)
            cv2.putText(anh, ch, (int(x + 0.22 * w), int(y + 0.78 * h)), cv2.FONT_HERSHEY_SIMPLEX, 2.4, 40, 6, cv2.LINE_AA)
    return anh


def lam_kho(anh):
    """Điều kiện khó giả lập: bóng đổ chéo + phối cảnh nhẹ trên nền tối hơn (không thay cho ảnh khó thật)."""
    import cv2
    import numpy as np
    h, w = anh.shape
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    bong = 1 - 0.35 * np.clip((X / w + Y / h) - 0.6, 0, 1)
    a = (anh.astype(np.float32) * bong).clip(0, 255).astype(np.uint8)
    pad = 200
    nen = np.full((h + 2 * pad, w + 2 * pad), 90, np.uint8)
    nen[pad:pad + h, pad:pad + w] = a
    src = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    dst = np.float32([[pad + 60, pad + 40], [pad + w - 30, pad], [pad + w, pad + h], [pad + 20, pad + h - 30]])
    return cv2.warpPerspective(nen, cv2.getPerspectiveTransform(src, dst), (w + 2 * pad, h + 2 * pad), borderValue=90)


SAI_CO_Y = {"T02": None}            # điền khi chạy: 3 câu bình thường của T02 bị tô ĐẬM ô khác -> phải ra đúng 3 sai âm thầm


def cmd_tu_kiem(a):
    import cv2
    kb = json.loads(KICH_BAN.read_text(encoding="utf-8"))
    tam = AG / "_tam_tu_kiem"
    if tam.exists():
        shutil.rmtree(tam)
    ok_dir, sai_dir = tam / "dung_kich_ban", tam / "doi_chung_am"
    ok_dir.mkdir(parents=True)
    sai_dir.mkdir(parents=True)
    try:
        for ma, to in kb["to"].items():
            anh = ve_to(to)
            cv2.imencode(".jpg", anh, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(ok_dir / f"{ma}.jpg"))
            if ma in ("T01", "T05", "T09"):
                cv2.imencode(".jpg", lam_kho(anh), [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(ok_dir / f"{ma}_kho.jpg"))
        (ok_dir / "ghi_chu.txt").write_text("tệp tên sai – phải bị liệt kê 'bỏ qua'", encoding="utf-8")
        thuong = [int(n) for n, c in kb["to"]["T02"]["cau"].items() if c["loai"] == "binh_thuong"][:3]
        cai = {n: next(o for o in "ABCD" if o != kb["to"]["T02"]["cau"][str(n)]["dap_an"]) for n in thuong}
        cv2.imencode(".jpg", ve_to(kb["to"]["T02"], cai), [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(str(sai_dir / "T02.jpg"))
        print("Tự kiểm 1/2: ảnh giả lập ĐÚNG kịch bản (13 ảnh)")
        k1 = cham(ok_dir, AG / "tu_kiem" / "dung_kich_ban", "TỰ KIỂM trên ảnh GIẢ LẬP – không dùng kết luận H3")
        print(f"Tự kiểm 2/2: đối chứng âm – T02 cố ý tô sai câu {sorted(cai)} -> công cụ phải báo đúng các câu này là sai âm thầm")
        k2 = cham(sai_dir, AG / "tu_kiem" / "doi_chung_am", "ĐỐI CHỨNG ÂM (ảnh giả lập cố ý sai) – không dùng kết luận H3")
    finally:
        shutil.rmtree(tam, ignore_errors=True)
    bat = sorted(x["n"] for x in k2["sai_am_tham"]["cau"])
    tk = {"dung_kich_ban": {"C1": k1["C1"], "sai_am_tham": k1["sai_am_tham"], "theo_loai": k1["theo_loai"], "H3": k1["H3"], "tu_choi": k1["tu_choi"],
                            "bo_qua": k1["bo_qua"], "C3": {k: v for k, v in k1["C3"].items() if k != "chi_tiet"}},
          "doi_chung_am": {"cau_cai": sorted(cai), "cau_bat_duoc": bat, "dat": bat == sorted(cai)}, "thu_muc_tam_da_xoa": not tam.exists()}
    (AG / "tu_kiem" / "tom_tat.json").write_text(json.dumps(tk, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"Đối chứng âm: cài {sorted(cai)}, bắt được {bat} -> {'ĐẠT' if tk['doi_chung_am']['dat'] else 'KHÔNG ĐẠT'}; thư mục tạm đã xoá: {tk['thu_muc_tam_da_xoa']}")
    return tk


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["cham", "tu-kiem"])
    ap.add_argument("--thu-muc", default=str(THU_MUC_ANH))
    ap.add_argument("--ra", default=str(AG))
    a = ap.parse_args()
    if a.lenh == "cham":
        if not Path(a.thu_muc).exists():
            sys.exit(f"Chưa có thư mục ảnh {a.thu_muc} – xem docs/huong_dan_thu_giay_that.md")
        cham(Path(a.thu_muc), Path(a.ra))
    else:
        cmd_tu_kiem(a)
