"""
omr_c2.py - Tuần 5 PHẦN B2 (và B3 dùng lại): sửa "cần xem thừa" C2 (3,79% > 3%), mọi số đo bằng NESTED CV (omr_long.py).

Ứng viên (CHỐT TRƯỚC khi chạy, cùng 9 đặc trưng trừ khi ghi khác; mọi siêu tham số cố định, không dò bằng dữ liệu):
  m1            logistic C=1, class_weight balanced (mốc Phần A)
  m1_khong_cb   như m1 nhưng KHÔNG class_weight (giảm áp lực đẩy câu mơ hồ sang "mờ")
  m1_logS       m1 + đặc trưng log(S_anh) (thang bút / độ sáng ảnh, để mô hình biết chì nhạt vs bi)
  m1_bac2       logistic trên đặc trưng bậc 2 (tương tác, 54 cột) C=1, balanced
  hgb           HistGradientBoosting depth 3, 150 vòng, lr 0,1, balanced, seed 2026
Tiêu chí chọn (chốt trước): (1) lỗi nặng = 0 (câu + cột; nested); (2) cần xem thừa ≤ 3% Ở MỌI điều kiện C1–C4 (nested);
(3) F1 faint không THẤP HƠN m1 ngoài CI ghép cặp ở điều kiện nào (CI bootstrap theo phiếu của hiệu F1, cận trên hiệu < 0 = thấp hơn thật)
VÀ maximin F1 không giảm điểm; hoà giữa các ứng viên đạt -> m1 (đơn giản nhất). Không ứng viên nào đạt -> báo trung thực, không nới tiêu chí.
Chỉ 56 ảnh train. Không đọc val / test.

  python tools/omr_c2.py chay  -> data/_eval/omr/c2_ung_vien.json + .md
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_omr as H  # noqa: E402
import omr_long as N  # noqa: E402

OUT = ROOT / "data" / "_eval" / "omr"
DK = H.DIEU_KIEN
SEED = 2026
UNG_VIEN = ("m1", "m1_khong_cb", "m1_logS", "m1_bac2", "hgb")
warnings.filterwarnings("ignore")


def tao(ten):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    if ten in ("m1", "m1_logS"):
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000))
    if ten == "m1_khong_cb":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
    if ten == "m1_bac2":
        return make_pipeline(StandardScaler(), PolynomialFeatures(2, include_bias=False), StandardScaler(),
                             LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000))
    if ten == "hgb":
        return HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.1, class_weight="balanced", random_state=SEED)
    raise ValueError(ten)


def ma_tran_ung_vien(sel, ten):
    X = H.ma_tran(sel)
    if ten == "m1_logS":
        X = np.hstack([X, np.log(np.array([[float(r["S_anh"])] for r in sel]))])
    return X


def f1_faint_dk(sel, y, d, dk_list=DK):
    out = {}
    dk = np.array([r["dieu_kien"] for r in sel])
    for c in dk_list:
        s = dk == c
        out[c] = H.f1_lop(y[s], d[s], 1)
    return out


def chon_ro_min_dk(rows, P, luat):
    """Luật chọn ro_min THEO TỪNG ĐIỀU KIỆN (khớp tiêu chí "cần xem thừa ≤ 3% mọi điều kiện"): lớn nhất trong lưới có 0 lỗi nặng và
    cần xem thừa ≤ 2,5% Ở MỌI điều kiện; không có thì lấy ro_min có thừa-xấu-nhất nhỏ nhất (dự phòng, ghi rõ)."""
    ok, xau = [], {}
    for ro in H.RO_LUOI:
        d = N.dem_cau(rows, P, {**luat, "ro_min": ro})
        t = N.tong(d)
        w = max(d[c]["thua"] / max(d[c]["ro_that"], 1) for c in DK)
        xau[ro] = (w if t["nang"] == 0 else 9.0)
        if t["nang"] == 0 and w <= H.THUA_MAX_CHON:
            ok.append(ro)
    return max(ok) if ok else min(xau, key=lambda r: (xau[r], -r))


def chay(luat_chon="gop"):
    sel = [r for r in H.doc_dac_trung("nan") if r["loai"] == "cau"]
    y = np.array([H.LOP_CAU.index(r["nhan"]) for r in sel])
    fold = np.array([int(r["fold"]) for r in sel])
    phieu = np.array([r["phieu"] for r in sel])
    dkv = np.array([r["dieu_kien"] for r in sel])
    luat0 = {"trong_min": 0.90, "to_min": 0.50}
    rng = np.random.default_rng(SEED)
    ds_phieu = sorted(set(phieu))
    rut = [rng.choice(ds_phieu, len(ds_phieu), replace=True) for _ in range(H.SO_BOOT)]
    idx_phieu = {p: np.flatnonzero(phieu == p) for p in ds_phieu}
    ket, boot = {}, {}
    for ten in UNG_VIEN:
        X = ma_tran_ung_vien(sel, ten)

        def fp(tr, te):
            m = tao(ten)
            m.fit(X[tr], y[tr])
            P = np.zeros((int(te.sum()), 3))
            P[:, m.classes_.astype(int)] = m.predict_proba(X[te])
            return P
        ngoai = {k: dict(cau=0, ro_that=0, nang=0, nhe=0, thua=0, can_xem=0) for k in DK}
        P_oof = np.zeros((len(sel), 3))
        chon = {}
        for k in range(1, 8):
            con = [f for f in range(1, 8) if f != k]
            P_trong = np.zeros((len(sel), 3))
            for j in con:
                P_trong[fold == j] = fp(np.isin(fold, [f for f in con if f != j]), fold == j)
            ii = np.flatnonzero(np.isin(fold, con))
            ro = (N.chon_ro_min if luat_chon == "gop" else chon_ro_min_dk)([sel[i] for i in ii], P_trong[ii], luat0)
            chon[k] = ro
            te = fold == k
            P_oof[te] = fp(np.isin(fold, con), te)
            jj = np.flatnonzero(te)
            d = N.dem_cau([sel[i] for i in jj], P_oof[jj], {**luat0, "ro_min": ro if ro is not None else 0.5})
            for dk in DK:
                for kk in ngoai[dk]:
                    ngoai[dk][kk] += d[dk][kk]
        d_arg = P_oof.argmax(1)
        f1 = f1_faint_dk(sel, y, d_arg)
        bs = {}
        for c in DK:
            s = dkv == c
            vals = []
            for rr in rut:
                ii = np.concatenate([idx_phieu[p][s[idx_phieu[p]]] for p in rr])
                vals.append(H.f1_lop(y[ii], d_arg[ii], 1))
            bs[c] = np.array(vals)
        boot[ten] = bs
        ket[ten] = {"ro_min_theo_fold": chon, "nested_theo_dk": ngoai, "nested_tong": N.tong(ngoai), "f1_faint": f1,
                    "nham_trong_co_to": int(((y == 0) & (d_arg > 0)).sum() + ((y > 0) & (d_arg == 0)).sum())}
        t = ket[ten]["nested_tong"]
        print(f"{ten}: nặng {t['nang']} nhẹ {t['nhe']} thừa {t['thua']}/{t['ro_that']} ({100 * t['thua'] / t['ro_that']:.2f}%) "
              f"thừa/dk {[round(100 * ngoai[c]['thua'] / ngoai[c]['ro_that'], 2) for c in DK]} F1 {[round(f1[c], 3) for c in DK]} ro_min {list(chon.values())}")
    # so với m1 (ghép cặp)
    dat, L = [], ["# B2 – ứng viên giảm cần xem thừa C2 (nested CV, 56 ảnh train)", "",
                  "| Ứng viên | lỗi nặng | lỗi nhẹ | thừa gộp | thừa C1 / C2 / C3 / C4 | F1 faint C1 / C2 / C3 / C4 | F1 thấp hơn m1 ngoài CI | đạt? |", "|---|---|---|---|---|---|---|---|"]
    for ten in UNG_VIEN:
        r = ket[ten]
        t = r["nested_tong"]
        thua_dk = {c: r["nested_theo_dk"][c]["thua"] / r["nested_theo_dk"][c]["ro_that"] for c in DK}
        thap = []
        for c in DK:
            diff = boot[ten][c] - boot["m1"][c]
            if ten != "m1" and np.nanpercentile(diff, 97.5) < 0:
                thap.append(c)
        mm = min(r["f1_faint"].values())
        mm1 = min(ket["m1"]["f1_faint"].values())
        ok = t["nang"] == 0 and all(v <= 0.03 for v in thua_dk.values()) and not thap and mm >= mm1 - 1e-9
        r.update(thua_dk=thua_dk, f1_thap_hon_m1=thap, dat=bool(ok), maximin=mm)
        if ok:
            dat.append(ten)
        L.append(f"| {ten} | {t['nang']} | {t['nhe']} | {100 * t['thua'] / t['ro_that']:.2f}% | "
                 + " / ".join(f"{100 * thua_dk[c]:.2f}" for c in DK) + " | " + " / ".join(f"{r['f1_faint'][c]:.3f}" for c in DK)
                 + f" | {', '.join(thap) or '–'} | {'ĐẠT' if ok else 'không'} |")
    chon_ten = "m1" if "m1" in dat or not dat else None
    if dat and "m1" not in dat:
        # chọn theo quy tắc: trong các ứng viên đạt, maximin F1 cao nhất, hoà (trong 0,005) -> đơn giản hơn (thứ tự UNG_VIEN)
        best = max(dat, key=lambda t_: (round(ket[t_]["maximin"], 2), -UNG_VIEN.index(t_)))
        chon_ten = best
    L += ["", f"**Ứng viên đạt cả 3 tiêu chí: {dat or 'KHÔNG CÓ'}** → chọn: **{chon_ten}** (hoà → m1; không ứng viên nào đạt → báo trung thực)."]
    L.insert(0, f"(luật chọn ro_min: **{'gộp (Phần A)' if luat_chon == 'gop' else 'theo từng điều kiện (≤ 2,5% mọi điều kiện)'}**)")
    (OUT / f"c2_ung_vien_{luat_chon}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / f"c2_ung_vien_{luat_chon}.json").write_text(json.dumps({"ung_vien": ket, "dat": dat, "chon": chon_ten}, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "chay":
        chay(sys.argv[2] if len(sys.argv) > 2 else "gop")
