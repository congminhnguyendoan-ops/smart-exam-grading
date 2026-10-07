"""
huan_luyen_omr.py - Huấn luyện + chọn mô hình ô cho cv_engine/omr.py (Tuần 5, Phần A; docs/ke_hoach_tuan5.md).

Chỉ dùng 56 ảnh TRAIN 0001–0028, 7 fold theo phiếu (data/split.csv). Phần A không chạm val 0029–0034; test bị chặn.
scikit-learn CHỈ dùng ở đây; mô hình xuất ra JSON để omr.py chạy bằng NumPy.

  python tools/huan_luyen_omr.py dac-trung      # đặc trưng 56 ảnh × 250 ô cho anh_nan và anh_chuan_hoa -> data/_omr/
  python tools/huan_luyen_omr.py cv             # M0 (ngưỡng cố định) + M1 (logistic) 7-fold OOF, F1 faint theo C1–C4 + CI,
                                                # so anh_nan / anh_chuan_hoa, chọn nguồn -> data/_omr/chon_nguon.json
  python tools/huan_luyen_omr.py xuat           # mô hình JSON: models/omr_m0.json, models/omr_m1.json (huấn luyện trên cả
                                                # 56 ảnh train) + mô hình từng fold data/_omr/mo_hinh_fold/ (cho eval OOF)
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402
from omr_du_lieu import anh_da_nan, ds_anh, nhan_o  # noqa: E402

OMR_DIR = ROOT / "data" / "_omr"
MODELS = ROOT / "models"
NGUON = {"nan": "anh_nan", "chuan": "anh_chuan_hoa"}
LOP_CAU = ("blank", "faint", "filled")
LOP_BUBBLE = ("blank", "filled")
SEED = 2026
SO_BOOT = 1000
DIEU_KIEN = ("C1", "C2", "C3", "C4")
C_LOGISTIC = 1.0            # cố định (Nợ kỹ thuật #2: không dò C trên OOF rồi báo trên chính OOF)
# M0: ngưỡng cố định của audit Tuần 4 (check_labels MARK_MIN / FILLED_MIN) trên thang ld_anh (S không dùng nhãn)
M0_NGUONG = {"mark_min": 0.25, "filled_min": 0.80}


# ------------------------------------------------------------------------------------------------ đặc trưng
def cmd_dac_trung() -> None:
    L = nap_layout("phieu")
    mau = omr.nap_mau()
    nhan = nhan_o()
    OMR_DIR.mkdir(parents=True, exist_ok=True)
    cot_nhan = {f"sbd{i}": f"sbd{i}" for i in range(1, 7)} | {f"ma_de{i}": f"exam_code{i}" for i in range(1, 4)}
    ghi = {k: [] for k in NGUON}
    for r in ds_anh("train"):
        nan, chuan = anh_da_nan(r["anh"], L)
        dv = omr.dinh_vi(nan, L, mau)                 # định vị luôn trên anh_nan (mẫu trắng; chuẩn hoá không đổi hình học)
        if any(dv.co.values()):
            raise SystemExit(f"{r['anh']}: định vị có cờ – A1 đã kiểm 56/56 không cờ, xem lại trước khi huấn luyện")
        for k, anh in (("nan", nan), ("chuan", chuan)):
            cau, bub, S = omr.dac_trung_o(anh, L, dv)
            base = {"anh": r["anh"], "phieu": r["phieu"], "dieu_kien": r["dieu_kien"], "but": r["but"],
                    "fold": r["fold"], "S_anh": round(S, 5)}
            for q in range(cau.shape[0]):
                for j, o in enumerate(L["answers"]["options"]):
                    ghi[k].append({**base, "loai": "cau", "phan_tu": f"q{q + 1}", "o": o,
                                   "nhan": nhan[(r["phieu"], str(q + 1), o)],
                                   **{t: round(float(v), 6) for t, v in zip(omr.TEN_DAC_TRUNG, cau[q, j])}})
            keys = [f"sbd{i}" for i in range(1, 7)] + [f"ma_de{i}" for i in range(1, 4)]
            for c, key in enumerate(keys):
                for d in range(10):
                    ghi[k].append({**base, "loai": "bubble", "phan_tu": key, "o": str(d),
                                   "nhan": nhan[(r["phieu"], cot_nhan[key], str(d))],
                                   **{t: round(float(v), 6) for t, v in zip(omr.TEN_DAC_TRUNG, bub[c, d])}})
        print(f"{r['anh']}: S_anh nan {omr.dac_trung_o(nan, L, dv)[2]:.3f}")
    for k, rows in ghi.items():
        p = OMR_DIR / f"dac_trung_{k}.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"-> {p} ({len(rows)} dòng)")


def doc_dac_trung(k: str) -> list[dict]:
    with (OMR_DIR / f"dac_trung_{k}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ma_tran(rows: list[dict]) -> np.ndarray:
    return np.array([[float(r[t]) for t in omr.TEN_DAC_TRUNG] for r in rows], np.float64)


# ------------------------------------------------------------------------------------------------ mô hình
def m0_du_doan(X: np.ndarray, lop: tuple) -> np.ndarray:
    """M0: xác suất 'cứng' (0/1) từ ngưỡng cố định trên ld_anh."""
    v = X[:, omr.TEN_DAC_TRUNG.index("ld_anh")]
    P = np.zeros((len(v), len(lop)))
    if lop == LOP_CAU:
        k = np.where(v < M0_NGUONG["mark_min"], 0, np.where(v < M0_NGUONG["filled_min"], 1, 2))
    else:
        k = (v >= M0_NGUONG["mark_min"]).astype(int)
    P[np.arange(len(v)), k] = 1.0
    return P


def m1_huan_luyen(X: np.ndarray, y: np.ndarray):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    m = make_pipeline(StandardScaler(), LogisticRegression(C=C_LOGISTIC, class_weight="balanced", max_iter=5000))
    return m.fit(X, y)


def m1_sang_json(m, lop: tuple) -> dict:
    sc, lr = m.named_steps["standardscaler"], m.named_steps["logisticregression"]
    assert tuple(lr.classes_) == tuple(range(len(lop)))
    return {"trung_binh": sc.mean_.tolist(), "do_lech": sc.scale_.tolist(), "he_so": lr.coef_.tolist(),
            "chan": lr.intercept_.tolist(), "lop": list(lop)}


def oof(rows: list[dict], loai: str, mo_hinh: str) -> np.ndarray:
    """Xác suất ngoài fold (OOF) cho các dòng loai ('cau' / 'bubble')."""
    lop = LOP_CAU if loai == "cau" else LOP_BUBBLE
    idx = [i for i, r in enumerate(rows) if r["loai"] == loai]
    X = ma_tran([rows[i] for i in idx])
    y = np.array([lop.index(rows[i]["nhan"]) for i in idx])
    fold = np.array([int(rows[i]["fold"]) for i in idx])
    P = np.zeros((len(idx), len(lop)))
    for k in range(1, 8):
        te = fold == k
        if mo_hinh == "m0":
            P[te] = m0_du_doan(X[te], lop)
        else:
            m = m1_huan_luyen(X[~te], y[~te])
            P[te] = m.predict_proba(X[te])
    return P


# ------------------------------------------------------------------------------------------------ đo
def f1_lop(y: np.ndarray, d: np.ndarray, k: int) -> float:
    tp = np.sum((y == k) & (d == k))
    fp = np.sum((y != k) & (d == k))
    fn = np.sum((y == k) & (d != k))
    return float(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else float("nan")


def boot_f1(rows_c, y, d, k, rng_idx) -> np.ndarray:
    """F1 lớp k trên mỗi mẫu bootstrap theo phiếu (rng_idx: danh sách mảng phiếu được rút)."""
    phieu = np.array([r["phieu"] for r in rows_c])
    out = []
    for rut in rng_idx:
        sel = np.concatenate([np.flatnonzero(phieu == p) for p in rut])
        out.append(f1_lop(y[sel], d[sel], k) if len(sel) else np.nan)
    return np.array(out)


def cmd_cv() -> None:
    rng = np.random.default_rng(SEED)
    rows = {k: doc_dac_trung(k) for k in NGUON}
    cau = {k: [r for r in rows[k] if r["loai"] == "cau"] for k in NGUON}
    phieu_ds = sorted({r["phieu"] for r in cau["nan"]})
    rut = [rng.choice(phieu_ds, len(phieu_ds), replace=True) for _ in range(SO_BOOT)]    # ghép cặp: dùng chung mọi cấu hình
    y = np.array([LOP_CAU.index(r["nhan"]) for r in cau["nan"]])
    assert all(r1["anh"] == r2["anh"] and r1["phan_tu"] == r2["phan_tu"] and r1["o"] == r2["o"]
               for r1, r2 in zip(cau["nan"], cau["chuan"]))
    ket, boot = {}, {}
    for k in NGUON:
        for mh in ("m0", "m1"):
            P = oof(rows[k], "cau", mh)
            d = P.argmax(1)
            np.save(OMR_DIR / f"oof_cau_{mh}_{k}.npy", P)
            ket[(mh, k)] = {}
            for dk in DIEU_KIEN:
                s = np.array([r["dieu_kien"] == dk for r in cau[k]])
                cm = np.zeros((3, 3), int)
                np.add.at(cm, (y[s], d[s]), 1)
                rc = [r for r, m in zip(cau[k], s) if m]
                b = boot_f1(rc, y[s], d[s], 1, rut)
                boot[(mh, k, dk)] = b
                ket[(mh, k)][dk] = {"f1_faint": f1_lop(y[s], d[s], 1), "ci": np.nanpercentile(b, [2.5, 97.5]).tolist(),
                                    "n_faint": int(np.sum(y[s] == 1)), "cm": cm.tolist(),
                                    "macro_f1": float(np.mean([f1_lop(y[s], d[s], c) for c in range(3)]))}
            Pb = oof(rows[k], "bubble", mh)
            np.save(OMR_DIR / f"oof_bubble_{mh}_{k}.npy", Pb)
    # báo cáo
    dong = ["# A2 – M0 / M1, anh_nan / anh_chuan_hoa (OOF 7-fold, 56 ảnh train 0001–0028)", "",
            f"Bootstrap theo phiếu {SO_BOOT} lần, seed {SEED}, CI 95% (ghép cặp giữa các cấu hình). F1 lớp faint, cấp ô.", "",
            "| Mô hình | Nguồn | " + " | ".join(f"{dk} F1 faint [CI] (n)" for dk in DIEU_KIEN) + " | maximin |",
            "|---|---|" + "---|" * (len(DIEU_KIEN) + 1)]
    for (mh, k), v in ket.items():
        mm = min(v[dk]["f1_faint"] for dk in DIEU_KIEN)
        dong.append(f"| {mh.upper()} | {NGUON[k]} | " + " | ".join(
            f"{v[dk]['f1_faint']:.3f} [{v[dk]['ci'][0]:.3f}; {v[dk]['ci'][1]:.3f}] ({v[dk]['n_faint']})" for dk in DIEU_KIEN)
            + f" | {mm:.3f} |")
    dong += ["", "Ma trận nhầm lẫn M1 (hàng = nhãn blank/faint/filled, cột = dự đoán):", ""]
    for k in NGUON:
        for dk in DIEU_KIEN:
            dong.append(f"- {NGUON[k]} {dk}: {ket[('m1', k)][dk]['cm']}")
    # so nguồn (M1): hiệu F1 faint chuan − nan theo điều kiện + maximin, CI ghép cặp
    diff = {dk: boot[("m1", "chuan", dk)] - boot[("m1", "nan", dk)] for dk in DIEU_KIEN}
    mm_b = {k: np.nanmin(np.vstack([boot[("m1", k, dk)] for dk in DIEU_KIEN]), axis=0) for k in NGUON}
    d_mm = mm_b["chuan"] - mm_b["nan"]
    ci_mm = np.nanpercentile(d_mm, [2.5, 97.5])
    dong += ["", "Hiệu F1 faint M1 (anh_chuan_hoa − anh_nan), CI ghép cặp:", ""]
    xau_hon = []
    for dk in DIEU_KIEN:
        ci = np.nanpercentile(diff[dk], [2.5, 97.5])
        dd = ket[("m1", "chuan")][dk]["f1_faint"] - ket[("m1", "nan")][dk]["f1_faint"]
        dong.append(f"- {dk}: {dd:+.3f} [{ci[0]:+.3f}; {ci[1]:+.3f}]")
        if ci[1] < 0:
            xau_hon.append(dk)
    mm = {k: min(ket[("m1", k)][dk]["f1_faint"] for dk in DIEU_KIEN) for k in NGUON}
    dong.append(f"- maximin: {mm['chuan'] - mm['nan']:+.3f} [{ci_mm[0]:+.3f}; {ci_mm[1]:+.3f}]")
    # quy tắc mục 4d: chuẩn hoá chỉ khi maximin cao hơn ngoài CI và không điều kiện nào thấp hơn ngoài CI; hoà -> anh_nan
    chon = "chuan" if (ci_mm[0] > 0 and not xau_hon) else "nan"
    ly_do = ("maximin F1 faint của anh_chuan_hoa cao hơn ngoài CI, không điều kiện nào thấp hơn ngoài CI"
             if chon == "chuan" else
             "không đủ bằng chứng anh_chuan_hoa tốt hơn (CI của hiệu maximin chứa 0 hoặc âm"
             + (f"; thấp hơn ngoài CI ở {', '.join(xau_hon)}" if xau_hon else "") + ") ⇒ HOÀ/kém → anh_nan (quy tắc 4d)")
    dong += ["", f"**Chọn nguồn: `{NGUON[chon]}`** – {ly_do}."]
    (OMR_DIR / "a2_so_sanh.md").write_text("\n".join(dong) + "\n", encoding="utf-8")
    json.dump({"nguon": NGUON[chon], "ly_do": ly_do, "maximin": {NGUON[k]: mm[k] for k in NGUON},
               "hieu_maximin_ci": ci_mm.tolist(),
               "f1_faint": {f"{mh}_{NGUON[k]}": {dk: v[dk]["f1_faint"] for dk in DIEU_KIEN} for (mh, k), v in ket.items()}},
              (OMR_DIR / "chon_nguon.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(dong))


# ------------------------------------------------------------------------------------------------ xuất mô hình
def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def sieu_du_lieu(k: str, fold_huan_luyen: list[int]) -> dict:
    import sklearn
    return {"ngay": dt.date.today().isoformat(), "git_head": _git_head(), "nguon_anh": NGUON[k],
            "tap_huan_luyen": "train 0001–0028 (data/split.csv)", "fold_huan_luyen": fold_huan_luyen,
            "sha256_dac_trung": _sha_file(OMR_DIR / f"dac_trung_{k}.csv"),
            "sha256_cell_labels": _sha_file(ROOT / "data" / "cell_labels.csv"),
            "sha256_split": _sha_file(ROOT / "data" / "split.csv"), "sklearn": sklearn.__version__,
            "C_logistic": C_LOGISTIC, "class_weight": "balanced"}


def tao_m1(rows: list[dict], fold_bo: int | None, k: str, luat: dict) -> dict:
    """Mô hình M1 JSON huấn luyện trên các fold ≠ fold_bo (None = cả 7 fold)."""
    out = {"loai": "logistic", "phien_ban": "omr_m1", "ten_dac_trung": list(omr.TEN_DAC_TRUNG),
           "nguon_anh": NGUON[k], "luat": luat}
    folds = [f for f in range(1, 8) if f != fold_bo]
    for loai, lop in (("cau", LOP_CAU), ("bubble", LOP_BUBBLE)):
        sel = [r for r in rows if r["loai"] == loai and int(r["fold"]) in folds]
        m = m1_huan_luyen(ma_tran(sel), np.array([lop.index(r["nhan"]) for r in sel]))
        out[loai] = m1_sang_json(m, lop)
    out["sieu_du_lieu"] = sieu_du_lieu(k, folds)
    return out


def tao_m0(k: str, luat: dict) -> dict:
    return {"loai": "nguong", "phien_ban": "omr_m0", "ten_dac_trung": list(omr.TEN_DAC_TRUNG), "nguon_anh": NGUON[k],
            "nguong": M0_NGUONG, "luat": luat,
            "sieu_du_lieu": {**sieu_du_lieu(k, []), "ghi_chu": "M0 không học – ngưỡng audit Tuần 4"}}


def cmd_xuat(luat_path: Path) -> None:
    chon = json.loads((OMR_DIR / "chon_nguon.json").read_text(encoding="utf-8"))
    k = {v: kk for kk, v in NGUON.items()}[chon["nguon"]]
    luat = json.loads(luat_path.read_text(encoding="utf-8")) if luat_path.exists() else {}
    rows = doc_dac_trung(k)
    MODELS.mkdir(exist_ok=True)
    (OMR_DIR / "mo_hinh_fold").mkdir(parents=True, exist_ok=True)
    for f in range(1, 8):
        m = tao_m1(rows, f, k, luat)
        (OMR_DIR / "mo_hinh_fold" / f"omr_m1_fold{f}.json").write_text(json.dumps(m, ensure_ascii=False, indent=1),
                                                                      encoding="utf-8")
    m = tao_m1(rows, None, k, luat)
    (MODELS / "omr_m1.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    m0 = tao_m0(k, luat.get("m0", luat))
    (MODELS / "omr_m0.json").write_text(json.dumps(m0, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {MODELS / 'omr_m1.json'}, {MODELS / 'omr_m0.json'}, {OMR_DIR / 'mo_hinh_fold'} (7 fold), nguồn {NGUON[k]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Huấn luyện mô hình ô OMR (Tuần 5, train 0001–0028)")
    ap.add_argument("lenh", choices=["dac-trung", "cv", "xuat"])
    ap.add_argument("--luat", default=OMR_DIR / "luat.json", help="ngưỡng luật ô -> câu (chọn ở A3)")
    a = ap.parse_args()
    {"dac-trung": cmd_dac_trung, "cv": cmd_cv}.get(a.lenh, lambda: cmd_xuat(Path(a.luat)))()


if __name__ == "__main__":
    main()
