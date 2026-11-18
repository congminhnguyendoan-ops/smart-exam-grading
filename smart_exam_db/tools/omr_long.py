import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_omr as H  # noqa: E402
from cv_engine import omr  # noqa: E402

OUT = ROOT / "data" / "_eval" / "omr"
DK = H.DIEU_KIEN


def dem_cau(rows, P, luat_cau):
    nhom = {}
    for i, r in enumerate(rows):
        nhom.setdefault((r["anh"], r["phan_tu"]), []).append(i)
    d = {k: dict(cau=0, ro_that=0, nang=0, nhe=0, thua=0, can_xem=0) for k in DK}
    for idx in nhom.values():
        dk = rows[idx[0]]["dieu_kien"]
        tt, to = H.trang_thai_that([rows[i]["nhan"] for i in idx])
        k = omr.ap_luat_cau(0, P[idx], luat_cau)
        doc = frozenset("ABCD".index(c) for c in k.dap_an)
        x = d[dk]
        x["cau"] += 1
        x["ro_that"] += tt == "ro"
        x["can_xem"] += k.can_xem
        if not k.can_xem:
            x["nang"] += doc != to
            x["nhe"] += doc == to and k.trang_thai != tt
        x["thua"] += k.can_xem and tt == "ro"
    return d


def tong(d):
    return {k: sum(d[dk][k] for dk in DK) for k in ("cau", "ro_that", "nang", "nhe", "thua", "can_xem")}


def chon_ro_min(rows, P, luat):
    ok = []
    for ro in H.RO_LUOI:
        t = tong(dem_cau(rows, P, {**luat, "ro_min": ro}))
        if t["nang"] == 0 and t["thua"] / t["ro_that"] <= H.THUA_MAX_CHON:
            ok.append(ro)
    return max(ok) if ok else None


def fit_predict(X, y, tr, te):
    m = H.m1_huan_luyen(X[tr], y[tr])
    return m.predict_proba(X[te])


def chay():
    rows_all = H.doc_dac_trung("nan")
    sel = [r for r in rows_all if r["loai"] == "cau"]
    X = H.ma_tran(sel)
    y = np.array([H.LOP_CAU.index(r["nhan"]) for r in sel])
    fold = np.array([int(r["fold"]) for r in sel])
    luat0 = {"trong_min": 0.90, "to_min": 0.50}
    cu = json.loads((H.OMR_DIR / "luat.json").read_text(encoding="utf-8"))["cau"]
    ro_cu = cu["ro_min"]
    ngoai = {k: dict(cau=0, ro_that=0, nang=0, nhe=0, thua=0, can_xem=0) for k in DK}
    chon = {}
    P_oof_cu = np.load(H.OMR_DIR / "oof_cau_m1_nan.npy")
    cu_d = dem_cau(sel, P_oof_cu, cu)
    for k in range(1, 8):
        con = [f for f in range(1, 8) if f != k]
        P_trong = np.zeros((len(sel), 3))
        for j in con:
            tr = np.isin(fold, [f for f in con if f != j])
            P_trong[fold == j] = fit_predict(X, y, tr, fold == j)
        idx = np.flatnonzero(np.isin(fold, con))
        ro = chon_ro_min([sel[i] for i in idx], P_trong[idx], luat0)
        chon[k] = ro
        te = fold == k
        P_ngoai = np.zeros((len(sel), 3))
        P_ngoai[te] = fit_predict(X, y, np.isin(fold, con), te)
        ii = np.flatnonzero(te)
        d = dem_cau([sel[i] for i in ii], P_ngoai[ii], {**luat0, "ro_min": ro if ro is not None else 0.5})
        for dk in DK:
            for kk in ngoai[dk]:
                ngoai[dk][kk] += d[dk][kk]
        print(f"fold ngoài {k}: ro_min chọn trên 6 fold trong = {ro}")
    tn, tc = tong(ngoai), tong(cu_d)
    ket = {"ro_min_theo_fold": chon, "ro_min_phan_a": ro_cu, "nested": {"theo_dk": ngoai, "tong": tn}, "phan_a": {"theo_dk": cu_d, "tong": tc}}
    L = ["# B1a – nested CV: số đo OMR không lạc quan (56 ảnh train, 2 240 lượt câu)", "",
         f"ro_min chọn trên 6 fold trong cho từng fold ngoài: {chon} (Phần A chọn 1 lần trên cả OOF: {ro_cu}).", "",
         "| | Phần A (chọn + đo trên cùng OOF) | **Nested (đo ngoài mẫu chọn)** |", "|---|---|---|",
         f"| Lỗi nặng | {tc['nang']} | **{tn['nang']}** |", f"| Lỗi nhẹ | {tc['nhe']} | {tn['nhe']} |",
         f"| Cần xem thừa (câu rõ 1 ô), gộp | {tc['thua']}/{tc['ro_that']} ({100 * tc['thua'] / tc['ro_that']:.2f}%) | "
         f"{tn['thua']}/{tn['ro_that']} ({100 * tn['thua'] / tn['ro_that']:.2f}%) |"]
    for dk in DK:
        a, b = cu_d[dk], ngoai[dk]
        L.append(f"| Cần xem thừa {dk} | {a['thua']}/{a['ro_that']} ({100 * a['thua'] / a['ro_that']:.2f}%) | "
                 f"{b['thua']}/{b['ro_that']} ({100 * b['thua'] / b['ro_that']:.2f}%) |")
    L.append(f"| Tổng câu cần xem | {tc['can_xem']} ({100 * tc['can_xem'] / tc['cau']:.1f}%) | {tn['can_xem']} ({100 * tn['can_xem'] / tn['cau']:.1f}%) |")
    (OUT / "long_nested.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / "long_nested.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1, default=int), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    chay()
