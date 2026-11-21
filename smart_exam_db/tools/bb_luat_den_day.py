import argparse
import json
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import omr_du_lieu as D  # noqa: E402
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout, preprocess  # noqa: E402

RA = ROOT / "data" / "_eval" / "bb"
AG = ROOT / "data" / "anh_that_ag"
KICH_BAN = ROOT / "data" / "_eval" / "ag" / "kich_ban.json"
LECH = ROOT / "data" / "_eval" / "ag" / "lech_kich_ban.json"
UPLOADS = ROOT / "storage" / "uploads" / "9696"
NGUONG = {"phu_dam": 0.85, "tuyet_doi": 0.65, "phu_nhe": 0.95}
BIEN_TOI_THIEU = 0.20
OPTS = ("A", "B", "C", "D")
IDX = {k: omr.TEN_DAC_TRUNG.index(k) for k in NGUONG}
PHIEU_SHA = {"fdcd3572": 23533, "43de3be6": 23534, "f231d104": 23535, "637e41f6": 23536}
CHEO = {23535: {13: "C", 21: "B", 28: "C"}, 23536: {10: "A"}}
NHAT = {23536: {1: None, 33: None}, 23535: {10: "D", 40: "C"}}


def ap_luat_local(cau: tuple, cau_dt: np.ndarray) -> tuple:
    ra = []
    for k in cau:
        if len(k.dap_an) == 1 and k.trang_thai == "mo" and k.ly_do == ("o_mo",):
            v = cau_dt[k.cau - 1, OPTS.index(k.dap_an)]
            if all(v[IDX[f]] >= t for f, t in NGUONG.items()):
                k = replace(k, trang_thai="ro", can_xem=False, ly_do=())
        ra.append(k)
    return tuple(ra)


def doc_nhom(kq, layout, mh, mau):
    anh = kq.anh_nan if mh["nguon_anh"] == "anh_nan" else kq.anh_chuan_hoa
    dv = omr.dinh_vi(kq.anh_nan, layout, mau)
    cau_dt, _, _ = omr.dac_trung_o(anh, layout, dv)
    omr_la = omr.them_den_day if hasattr(omr, "them_den_day") else None
    if omr_la is not None:
        omr.them_den_day = lambda cau, *a, **k: cau
    try:
        truoc = omr.doc_phieu(kq, layout, mh, mau)
    finally:
        if omr_la is not None:
            omr.them_den_day = omr_la
    return cau_dt, truoc


def anh_dev(ten, layout):
    nan, ch = D.anh_da_nan(ten, layout)
    return SimpleNamespace(ok=True, anh_nan=nan, anh_chuan_hoa=ch)


def nhan_cau(nhan, phieu, q):
    return "".join(o for o in OPTS if nhan.get((phieu, str(q), o), "blank") != "blank")


def duyet_tap(layout, mh, mau):
    ds = D.ds_anh("train") + D.ds_anh("val", cho_phep_val=True)
    nhan = D.nhan_o(cho_phep_val=True)
    for r in ds:
        kq = anh_dev(r["anh"], layout)
        cau_dt, truoc = doc_nhom(kq, layout, mh, mau)
        yield r, nhan, cau_dt, truoc


def cmd_phan_bo(_a):
    layout, mh, mau = nap_layout("phieu"), omr.nap_mo_hinh(), omr.nap_mau()
    gia_tri = {"faint": defaultdict(list), "filled": defaultdict(list)}
    bien, khoi_lua = [], []
    for r, nhan, cau_dt, _t in duyet_tap(layout, mh, mau):
        for q in range(1, 41):
            non = [o for o in OPTS if nhan.get((r["phieu"], str(q), o), "blank") != "blank"]
            if len(non) != 1:
                continue
            lab = nhan[(r["phieu"], str(q), non[0])]
            if lab not in gia_tri:
                continue
            v = cau_dt[q - 1, OPTS.index(non[0])]
            for f in NGUONG:
                gia_tri[lab][f].append(float(v[IDX[f]]))
            if lab == "faint":
                bien.append((max(NGUONG[f] - float(v[IDX[f]]) for f in NGUONG), r["anh"], q, non[0]))
                if all(v[IDX[f]] >= NGUONG[f] for f in NGUONG):
                    khoi_lua.append((r["anh"], q, non[0]))
    dong = ["| nhãn | đặc trưng | n | min | p1 | p5 | trung vị | p95 | p99 | max |", "|---|---|---|---|---|---|---|---|---|---|"]
    for lab in ("faint", "filled"):
        for f in NGUONG:
            a = np.array(gia_tri[lab][f])
            q = np.percentile(a, [1, 5, 50, 95, 99])
            dong.append(f"| {lab} | {f} | {len(a)} | {a.min():.3f} | {q[0]:.3f} | {q[1]:.3f} | {q[2]:.3f} | {q[3]:.3f} | {q[4]:.3f} | {a.max():.3f} |")
    bien.sort()
    ra = ["# Phân bố đặc trưng ô được chọn (train + val, ô một lựa chọn theo nhãn)", ""] + dong + [
        "", f"Ngưỡng đăng ký: {NGUONG}",
        f"Ô mờ thoả cả ba điều kiện (luật sẽ kích hoạt): {len(khoi_lua)} {khoi_lua[:10]}",
        f"min g(c) (biên, cần ≥ {BIEN_TOI_THIEU}): {bien[0][0]:.3f} tại {bien[0][1:]}",
        "5 ô mờ có biên nhỏ nhất: " + "; ".join(f"{g:.3f} ({a} câu {q}{o})" for g, a, q, o in bien[:5])]
    RA.mkdir(parents=True, exist_ok=True)
    (RA / "phan_bo.md").write_text("\n".join(ra), encoding="utf-8")
    print("\n".join(ra))


def so_sanh_cau(truoc, sau):
    out = []
    for a, b in zip(truoc, sau):
        if a != b:
            out.append((a.cau, a.dap_an, a.trang_thai, tuple(a.ly_do), b.trang_thai, tuple(b.ly_do)))
    return out


def cmd_do(_a):
    layout, mh, mau = nap_layout("phieu"), omr.nap_mo_hinh(), omr.nap_mau()
    kq = {"a": {}, "b": {}}
    tong = {"loi_nang_truoc": 0, "loi_nang_sau": 0, "can_xem_truoc": 0, "can_xem_sau": 0, "doi": 0, "doi_sai": 0, "faint_thanh_ro": 0}
    ds_doi = []
    for r, nhan, cau_dt, truoc in duyet_tap(layout, mh, mau):
        sau = ap_luat_local(truoc.cau, cau_dt)
        dev = r["tap"] == "train"
        for a, b in zip(truoc.cau, sau):
            lab = nhan_cau(nhan, r["phieu"], a.cau)
            if dev:
                tong["loi_nang_truoc"] += (not a.can_xem) and a.dap_an != lab
                tong["loi_nang_sau"] += (not b.can_xem) and b.dap_an != lab
                tong["can_xem_truoc"] += a.can_xem
                tong["can_xem_sau"] += b.can_xem
            if a != b:
                tong["doi"] += dev
                kieu = [nhan.get((r["phieu"], str(a.cau), o), "blank") for o in OPTS]
                ds_doi.append({"anh": r["anh"], "tap": r["tap"], "cau": a.cau, "may": a.dap_an, "nhan": lab, "nhan_o": kieu})
                tong["doi_sai"] += dev and (a.dap_an != lab or "filled" not in kieu or "faint" in kieu)
                tong["faint_thanh_ro"] += "faint" in kieu
    kq["a"] = {"tong": tong, "cau_doi": ds_doi}
    kq["c"] = do_bon_phieu(layout, mh, mau)
    kq["d"] = do_ag(layout, mh, mau)
    RA.mkdir(parents=True, exist_ok=True)
    (RA / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    in_ket_qua(kq)


def do_bon_phieu(layout, mh, mau):
    out = {}
    for p in sorted(UPLOADS.rglob("*.jpg")):
        ma = PHIEU_SHA.get(p.name[:8])
        if ma is None:
            continue
        k = preprocess(str(p), layout)
        if not k.ok:
            out[ma] = {"tu_choi": k.ly_do}
            continue
        cau_dt, truoc = doc_nhom(k, layout, mh, mau)
        sau = ap_luat_local(truoc.cau, cau_dt)
        ct = {c.cau: c for c in truoc.cau}
        cs = {c.cau: c for c in sau}
        cx_t = [(c.cau, c.dap_an, list(c.ly_do)) for c in truoc.cau if c.can_xem]
        cx_s = [(c.cau, c.dap_an, list(c.ly_do)) for c in sau if c.can_xem]

        def vec(q, o):
            return {f: round(float(cau_dt[q - 1, OPTS.index(o), IDX[f]]), 3) for f in NGUONG}
        cheo = {q: {"o": o, "truoc": [ct[q].trang_thai, list(ct[q].ly_do)], "sau": [cs[q].trang_thai, list(cs[q].ly_do)], "dac_trung": vec(q, o)}
                for q, o in CHEO.get(ma, {}).items()}
        nhat = {q: {"o": ct[q].dap_an, "truoc": [ct[q].trang_thai, list(ct[q].ly_do)], "sau": [cs[q].trang_thai, list(cs[q].ly_do)]}
                for q in NHAT.get(ma, {})}
        out[ma] = {"tep": p.name[:8], "to_nhat": truoc.to_nhat, "can_xem_truoc": cx_t, "can_xem_sau": cx_s, "cheo": cheo, "nhat": nhat,
                   "doi": so_sanh_cau(truoc.cau, sau)}
    return out


def do_ag(layout, mh, mau):
    kb = json.loads(KICH_BAN.read_text(encoding="utf-8"))
    lech = {(x["anh"], int(x["cau"])): "".join(sorted(x["dap_an_thuc_te"].upper())) for x in json.loads(LECH.read_text(encoding="utf-8"))["lech"]}
    out = {"anh": [], "im_lang_moi_kb": [], "im_lang_moi_sau_xac_minh": [], "thoat_hang_doi": 0}
    for p in sorted(AG.iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".heic") or not p.is_file():
            continue
        to = p.stem.split("_")[0].upper()
        k = preprocess(str(p), layout)
        if not k.ok:
            out["anh"].append({"anh": p.name, "tu_choi": k.ly_do})
            continue
        cau_dt, truoc = doc_nhom(k, layout, mh, mau)
        sau = ap_luat_local(truoc.cau, cau_dt)
        dem = {"anh": p.name, "doi": []}
        for a, b in zip(truoc.cau, sau):
            dung_kb = "".join(sorted(kb["to"][to]["cau"][str(a.cau)]["dap_an"]))
            dung_sx = lech.get((p.name, a.cau), dung_kb)
            if a != b:
                out["thoat_hang_doi"] += 1
                dem["doi"].append({"cau": a.cau, "may": a.dap_an, "kich_ban": dung_kb, "sau_xac_minh": dung_sx})
            for ten, dung in (("kb", dung_kb), ("sau_xac_minh", dung_sx)):
                im_t = (not a.can_xem) and "".join(sorted(a.dap_an)) != dung
                im_s = (not b.can_xem) and "".join(sorted(b.dap_an)) != dung
                if im_s and not im_t:
                    out["im_lang_moi_kb" if ten == "kb" else "im_lang_moi_sau_xac_minh"].append({"anh": p.name, "cau": a.cau, "may": b.dap_an, "dung": dung})
        out["anh"].append(dem)
    return out


def in_ket_qua(kq):
    a = kq["a"]["tong"]
    print("(a) 56 ảnh dev:", json.dumps(a, ensure_ascii=False))
    print("    câu đổi (train + val):", len(kq["a"]["cau_doi"]))
    for x in kq["a"]["cau_doi"]:
        print("     ", x)
    print("(c) 4 phiếu:")
    for ma, v in kq["c"].items():
        print(" ", ma, json.dumps(v, ensure_ascii=False))
    d = kq["d"]
    print("(d) AG: thoát hàng đợi", d["thoat_hang_doi"], "| im lặng mới (kịch bản):", d["im_lang_moi_kb"],
          "| (sau xác minh):", d["im_lang_moi_sau_xac_minh"])
    for x in d["anh"]:
        print("   ", x)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("phan-bo").set_defaults(f=cmd_phan_bo)
    sub.add_parser("do").set_defaults(f=cmd_do)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
