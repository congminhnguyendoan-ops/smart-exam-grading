"""
so_sanh_ocr.py - Lệnh D: so sánh CNN chữ số hiện tại với M0 (HOG + logistic) và một thư viện OCR, CHỈ ĐO trên dữ liệu DEV. Không sửa hệ thống,
không đổi trọng số, không ghi CSDL. Kết quả -> data/_eval/so_sanh_ocr/. Báo cáo: docs/so_sanh_ocr_cnn.md.

  python tools/so_sanh_ocr.py do-cnn       # Bước 1: tham số, dung lượng, RAM, phụ thuộc, thời gian (chữ số / 9 chữ số / cả phiếu)
  python tools/so_sanh_ocr.py so-sanh      # Bước 2–3: M0 + CNN (+ OCR nếu đã có data/_eval/so_sanh_ocr/du_doan_ocr.csv) trên CÙNG tập chữ số

TẬP ĐO (định nghĩa có sẵn: tools/huan_luyen_ocr.py tap_do – phiếu lọc theo cv_engine.tap_du_lieu.PHIEU_TRAIN NGAY KHI ĐỌC):
  P = 504 chữ số viết tay trên phiếu dev 0001–0028 (56 ảnh × 9). KHÔNG mô hình nào học các chữ số này -> tập so sánh CHÍNH.
      M0 và CNN sản xuất cùng học trang D (CNN thêm MNIST); người viết 1–4 của P cũng viết trang D (nét đã gặp, chữ số khác).
  D = 3 872 chữ số trang D001–D010 (bỏ 128 ô không dò được khung). CNN SẢN XUẤT ĐÃ HỌC D -> chỉ báo riêng ("đã học"), KHÔNG so.
      So công bằng trên D bằng OOF 5-fold THEO NGƯỜI VIẾT: CNN = bộ đệm data/_ocr/cap/oof_g0_goc_2026.npz (đúng cấu hình sản xuất g0, seed 2026,
      tinh chỉnh trên 4 người, đọc người thứ 5); M0 huấn luyện lại theo đúng 5 fold đó.
  KHÔNG dùng phiếu val 0029–0034, test 0035–0040, đợt 2 0101–0110 (bộ đệm ô cắt có val: bị lọc bỏ khi đọc, không tính gì trên đó).
"""
import argparse
import csv
import ctypes
import json
import math
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402  (định nghĩa tập đo + HOG + MNIST – không import torch)
from cv_engine import ocr  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_TRAIN, chan_test, ma_phieu  # noqa: E402

RA = ROOT / "data" / "_eval" / "so_sanh_ocr"
NGUON = "anh_nan"
OOF_CNN = H.OCR / "cap" / "oof_g0_goc_2026.npz"
C_M0 = 10.0                    # chọn ở Tuần 6 Bước 4 trên val NỘI BỘ MNIST (data/_eval/ocr/m0_buoc4.json) – không dùng dữ liệu dev


# ------------------------------------------------------------------------------------------------ tiện ích
def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def bo_nho_tien_trinh_mb() -> float | None:
    """Working set của tiến trình (Windows, K32GetProcessMemoryInfo) – MB; khác Windows / lỗi -> None.
    (Bản 27/10 gọi psapi không khai báo kiểu handle 64-bit -> lời gọi thất bại, luôn trả 0: số RAM working set bản đó KHÔNG hợp lệ.)"""
    try:
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return None
        return c.WorkingSetSize / 2 ** 20
    except Exception:  # noqa: BLE001
        return None


def pct(a, q) -> float:
    return round(float(np.percentile(np.asarray(a, float), q)), 3)


def softmax(z: np.ndarray, T: float = 1.0) -> np.ndarray:
    z = z / T
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def so_tham_so_cnn(mh) -> int:
    return int(sum(np.asarray(v).size for m in mh.thanh_vien for k, v in m.items() if k != "T"))


# ------------------------------------------------------------------------------------------------ Bước 1
def do_cnn() -> dict:
    RA.mkdir(parents=True, exist_ok=True)
    tep = ocr.DUONG_DAN_MO_HINH
    r0 = bo_nho_tien_trinh_mb()
    tracemalloc.start()
    t0 = time.perf_counter()
    mh = ocr.nap_mo_hinh_ocr()
    t_nap = (time.perf_counter() - t0) * 1000
    _, dinh = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    r1 = bo_nho_tien_trinh_mb()
    trong_so_mb = sum(np.asarray(v).nbytes for m in mh.thanh_vien for k, v in m.items() if k != "T") / 2 ** 20
    x = H.tap_do(NGUON)["phieu"]["x"]
    for _ in range(20):
        ocr.du_doan_xac_suat(mh, x[:1])
    t1 = []
    for i in range(1000):
        a = time.perf_counter(); ocr.du_doan_xac_suat(mh, x[i % len(x)][None]); t1.append((time.perf_counter() - a) * 1000)
    t9 = []
    for i in range(300):
        j = (9 * i) % (len(x) - 9)
        a = time.perf_counter(); ocr.du_doan_xac_suat(mh, x[j:j + 9]); t9.append((time.perf_counter() - a) * 1000)
    # cả phiếu: doc_chu_so (dò khung + cắt 9 ô + CNN) trên ảnh dev 0001–0028 đã nắn (preprocess KHÔNG tính giờ)
    from cv_engine.preprocessing import nap_layout, preprocess
    layout = nap_layout("phieu")
    anh = sorted(p for p in (ROOT / "data" / "raw").glob("00[0-2][0-9]_C?.jpg") if (ma_phieu(p.stem) or 0) in PHIEU_TRAIN)
    t_phieu = []
    for p in anh:
        chan_test([p.stem])
        kq = preprocess(str(p), layout)
        if not kq.ok:
            continue
        a = time.perf_counter(); ocr.doc_chu_so(kq, layout, mh); t_phieu.append((time.perf_counter() - a) * 1000)
    imp = sorted({l.split()[1].split(".")[0] for l in Path(ocr.__file__).read_text(encoding="utf-8").splitlines() if l.startswith(("import ", "from "))})
    kq = {"mo_hinh": "CNN chữ số sản xuất (cv_engine/ocr.py + models/ocr_cnn.json)", "kien_truc": "Conv3×3·16 → pool → Conv3×3·32 → pool → Dense 64 → 10",
          "tham_so": so_tham_so_cnn(mh), "so_thanh_vien": len(mh.thanh_vien), "tep": str(tep.relative_to(ROOT)), "tep_mb": round(tep.stat().st_size / 2 ** 20, 2),
          "trong_so_float32_mb": round(trong_so_mb, 3), "nap_ms": round(t_nap, 1), "ram_dinh_khi_nap_mb_tracemalloc": round(dinh / 2 ** 20, 2),
          "ram_tang_working_set_mb": None if r0 is None else round(r1 - r0, 1),
          "phu_thuoc_luc_chay": imp, "ghi_chu_phu_thuoc": "chỉ NumPy (+ OpenCV để dò khung / cắt ô); không torch, không Internet, không GPU",
          "ms_1_chu_so": {"p50": pct(t1, 50), "p95": pct(t1, 95), "n": len(t1)}, "ms_9_chu_so_mot_lo": {"p50": pct(t9, 50), "p95": pct(t9, 95), "n": len(t9)},
          "ms_ca_phieu_doc_chu_so": {"p50": pct(t_phieu, 50), "p95": pct(t_phieu, 95), "n": len(t_phieu),
                                     "gom": "dò khung 9 ô + cắt + chuẩn hoá 28×28 + CNN, trên ảnh dev 0001–0028 đã nắn"},
          "lenh": "python tools/so_sanh_ocr.py do-cnn"}
    (RA / "cnn_hien_tai.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    return kq


# ------------------------------------------------------------------------------------------------ Bước 2–3
def danh_gia(ten: str, y: np.ndarray, prob: np.ndarray, nguong: dict) -> dict:
    """Độ đúng (Wilson 95%), cặp nhầm nhiều nhất, 'sai mà tự tin' theo từng ngưỡng {tên: hàm(prob)->mask chắc}."""
    p = prob.argmax(1)
    n, k = len(y), int((p == y).sum())
    cap = Counter((int(a), int(b)) for a, b in zip(y, p) if a != b)
    sai = p != y
    tt = {}
    for tn, f in nguong.items():
        chac = f(prob)
        tt[tn] = {"sai_ma_tu_tin": int((sai & chac).sum()), "ti_le_tren_tong": round(float((sai & chac).mean()), 4),
                  "ti_le_tren_so_sai": round(float((sai & chac).sum() / max(1, sai.sum())), 4), "ti_le_chu_so_duoc_tin": round(float(chac.mean()), 4)}
    return {"mo_hinh": ten, "n": n, "dung": k, "acc": round(k / n, 4), "wilson95": wilson(k, n),
            "cap_nham_nhieu_nhat": [f"{a}→{b}: {c}" for (a, b), c in cap.most_common(6)], "sai_ma_tu_tin": tt}


def nguong_cnn(mh):
    return {"p≥τ_khop 0,5 (cổng nhận khi đối chiếu bubble)": lambda q: q.max(1) >= mh.tau_khop,
            "cnn_chac p≥0,9995 & lề≥0,99 (chỉ báo cáo)": lambda q: (q.max(1) >= mh.tau) & (np.sort(q, 1)[:, -1] - np.sort(q, 1)[:, -2] >= mh.delta)}


def mcnemar(y, pa, pb) -> dict:
    """Kiểm định McNemar CHÍNH XÁC (nhị thức trên các cặp bất đồng) – cùng chữ số, hai mô hình."""
    from scipy.stats import binomtest
    a_dung_b_sai, a_sai_b_dung = int(((pa == y) & (pb != y)).sum()), int(((pa != y) & (pb == y)).sum())
    n = a_dung_b_sai + a_sai_b_dung
    return {"A_dung_B_sai": a_dung_b_sai, "A_sai_B_dung": a_sai_b_dung, "p": round(binomtest(a_dung_b_sai, n, 0.5).pvalue, 4) if n else 1.0}


def tac_dong_he_thong(prob_p: np.ndarray, meta_p: list[dict], tau_khop: float | None = None) -> dict:
    """Áp LUẬT SẢN XUẤT (đối chiếu hai kênh Q3, τ_khop 0,5 – tools/ocr_cai_tien.doi_chieu_dev, bubble OMR dev data/_ocr/omr_dev.json)
    với xác suất của mô hình chữ số: T4 = % ảnh (56) có SBD hoặc mã đề "cần xem"; IL = trường được NHẬN mà SAI (lỗi thầm lặng)."""
    import ocr_cai_tien as CT
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    dc = CT.doi_chieu_dev(prob_p, meta_p, omr) if tau_khop is None else CT.doi_chieu_dev(prob_p, meta_p, omr, tau_khop)
    anhs = sorted({k[0] for k in dc})
    gan = sum(any(not dc[(a, lo)][1] for lo in ("sbd", "ma_de")) for a in anhs)
    nhan = [v for v in dc.values() if v[1]]
    return {"anh": len(anhs), "anh_can_xem": gan, "T4": round(gan / len(anhs), 4), "truong": len(dc), "truong_nhan_tu_dong": len(nhan),
            "loi_tham_lang_muc_truong": sum(1 for v in nhan if not v[3])}


def hoc_m0(x, y):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=C_M0, max_iter=300, random_state=H.SEED).fit(H.hog28(x), y)


def so_sanh() -> dict:
    RA.mkdir(parents=True, exist_ok=True)
    t = H.tap_do(NGUON)
    P, D = t["phieu"], t["trang"]
    assert all((ma_phieu(r["anh"]) or 0) in PHIEU_TRAIN for r in P["meta"]) and len(P["y"]) == 504 and len(D["y"]) == 3872
    chan_test([r["anh"] for r in P["meta"]])
    mh = ocr.nap_mo_hinh_ocr()
    ng = nguong_cnn(mh)
    xtr, ytr, _, _ = H.doc_mnist()
    mn = np.random.default_rng(H.SEED).permutation(len(xtr))[5000:]          # như Tuần 6: bỏ 5 000 ảnh val nội bộ MNIST
    xm, ym = xtr[mn], ytr[mn].astype(np.int64)
    ket = {"tap": {"P": "504 chữ số phiếu dev 0001–0028 (không mô hình nào học)", "D": "3 872 chữ số trang D001–D010"}, "C_M0": C_M0}
    dong = []

    # --- tập P: M0 (MNIST + toàn bộ D) vs CNN sản xuất (MNIST + toàn bộ D) – cả hai CHƯA thấy P
    t0 = time.perf_counter()
    m0 = hoc_m0(np.concatenate([xm, D["x"]]), np.concatenate([ym, D["y"]]))
    ket["m0_hoc_giay"] = round(time.perf_counter() - t0, 1)
    q_m0 = m0.predict_proba(H.hog28(P["x"]))
    q_cnn = ocr.du_doan_xac_suat(mh, P["x"])
    ng_m0 = {"p≥0,5": lambda q: q.max(1) >= 0.5, "p≥0,9995 & lề≥0,99": lambda q: (q.max(1) >= 0.9995) & (np.sort(q, 1)[:, -1] - np.sort(q, 1)[:, -2] >= 0.99)}
    ket["P"] = {"M0": danh_gia("M0 HOG+logistic (MNIST + trang D)", P["y"], q_m0, ng_m0),
                "CNN": danh_gia("CNN sản xuất (MNIST + trang D)", P["y"], q_cnn, ng)}
    # CNN người lạ trên P (OOF): phiếu của người k đọc bằng mô hình bỏ người k – từ bộ đệm cùng cấu hình
    z = np.load(OOF_CNN)
    q_oof_p, q_oof_d = softmax(z["phieu"], mh.thanh_vien[0]["T"]), softmax(z["trang"], mh.thanh_vien[0]["T"])
    ket["P"]["CNN_OOF_nguoi_la"] = danh_gia("CNN cùng cấu hình, OOF theo người viết", P["y"], q_oof_p, ng)

    # --- tập D: CNN sản xuất đã học D -> chỉ báo riêng; so công bằng bằng OOF 5-fold theo người viết
    ket["D_CNN_san_xuat_DA_HOC"] = danh_gia("CNN sản xuất trên D (ĐÃ HỌC – không so)", D["y"], ocr.du_doan_xac_suat(mh, D["x"]), ng)
    ng_d = np.array([int(r["nguoi"]) for r in D["meta"]])
    ng_p = np.array([int(r["nguoi"]) for r in P["meta"]])
    q_m0_d, q_m0_poof = np.zeros((len(D["y"]), 10)), np.zeros((len(P["y"]), 10))
    for k in range(1, 6):
        tr = ng_d != k
        m = hoc_m0(np.concatenate([xm, D["x"][tr]]), np.concatenate([ym, D["y"][tr]]))
        q_m0_d[~tr] = m.predict_proba(H.hog28(D["x"][~tr]))
        if (ng_p == k).any():
            q_m0_poof[ng_p == k] = m.predict_proba(H.hog28(P["x"][ng_p == k]))
        print(f"  M0 fold người {k} xong")
    ket["D_OOF"] = {"M0": danh_gia("M0 OOF theo người viết", D["y"], q_m0_d, ng_m0), "CNN": danh_gia("CNN OOF theo người viết", D["y"], q_oof_d, ng)}
    ket["P"]["M0_OOF_nguoi_la"] = danh_gia("M0 OOF theo người viết", P["y"], q_m0_poof, ng_m0)

    # --- kiểm định cặp + tác động lên hệ thống (luật đối chiếu hai kênh của sản xuất)
    am = lambda q: q.argmax(1)   # noqa: E731
    ket["mcnemar"] = {"P: CNN vs M0": mcnemar(P["y"], am(q_cnn), am(q_m0)), "P OOF: CNN vs M0": mcnemar(P["y"], am(q_oof_p), am(q_m0_poof)),
                      "D OOF: CNN vs M0": mcnemar(D["y"], am(q_oof_d), am(q_m0_d))}
    ket["he_thong_P"] = {"M0": tac_dong_he_thong(q_m0, P["meta"]), "CNN": tac_dong_he_thong(q_cnn, P["meta"]),
                         "M0_OOF": tac_dong_he_thong(q_m0_poof, P["meta"]), "CNN_OOF": tac_dong_he_thong(q_oof_p, P["meta"])}

    # --- thời gian + dung lượng M0 (suy luận được bằng NumPy: HOG NumPy + 324×10 hệ số)
    t1 = []
    for i in range(500):
        a = time.perf_counter(); m0.predict_proba(H.hog28(P["x"][i % 504][None])); t1.append((time.perf_counter() - a) * 1000)
    t9 = []
    for i in range(200):
        j = (9 * i) % 495
        a = time.perf_counter(); m0.predict_proba(H.hog28(P["x"][j:j + 9])); t9.append((time.perf_counter() - a) * 1000)
    hs = {"coef": m0.coef_.astype(np.float32).tolist(), "intercept": m0.intercept_.astype(np.float32).tolist()}
    (RA / "m0_he_so.json").write_text(json.dumps(hs), encoding="utf-8")
    ket["M0_chi_phi"] = {"tham_so": int(m0.coef_.size + m0.intercept_.size), "tep_json_kb": round((RA / "m0_he_so.json").stat().st_size / 1024, 1),
                         "ms_1_chu_so": {"p50": pct(t1, 50), "p95": pct(t1, 95)}, "ms_9_chu_so": {"p50": pct(t9, 50), "p95": pct(t9, 95)},
                         "phu_thuoc": "huấn luyện: scikit-learn; suy luận: NumPy được (HOG NumPy + tích ma trận) – đo ở đây qua sklearn"}

    # --- OCR A' (đã chạy trong môi trường riêng bằng tools/so_sanh_ocr_rapid.py: du_doan_ocr_<bien>_<giai_ma>.csv)
    #     Chọn biến thể chính theo tập D (3 872 chữ số, OCR không học gì của D) – KHÔNG chọn theo P để P vẫn là phép đo không lạc quan.
    bt = {}
    for f in sorted(RA.glob("du_doan_ocr_*_*.csv")):
        ten = f.stem.removeprefix("du_doan_ocr_")
        bt[ten] = doc_ocr(f, P["y"], D["y"])
    if bt:
        chinh = max(bt, key=lambda k: bt[k]["D"]["acc"])
        o = bt[chinh]
        ket["OCR"] = {"bien_the": bt, "chinh_chon_theo_D": chinh,
                      "mcnemar": {"P: CNN vs OCR": mcnemar(P["y"], am(q_cnn), o["P"]["_doc"]), "P: M0 vs OCR": mcnemar(P["y"], am(q_m0), o["P"]["_doc"]),
                                  "D: CNN OOF vs OCR": mcnemar(D["y"], am(q_oof_d), o["D"]["_doc"]), "D: M0 OOF vs OCR": mcnemar(D["y"], am(q_m0_d), o["D"]["_doc"])},
                      "he_thong_P": {k: tac_dong_he_thong(v["P"]["_q"], P["meta"]) for k, v in bt.items()},
                      # chẩn đoán (KHÔNG chỉnh ngưỡng theo P): τ_khop 0,5 được hiệu chỉnh cho CNN (nhiệt độ T); điểm OCR không hiệu chỉnh.
                      # Cùng một cổng τ_khop = 0 (nhận khi chữ viết tay TRÙNG bubble, bỏ cổng tin cậy) cho mọi ứng viên:
                      "he_thong_P_tau0": {"CNN": tac_dong_he_thong(q_cnn, P["meta"], 0.0), "M0": tac_dong_he_thong(q_m0, P["meta"], 0.0),
                                          "OCR_" + chinh: tac_dong_he_thong(o["P"]["_q"], P["meta"], 0.0)},
                      "dung_ma_p_duoi_0_5": {"P CNN": int(((am(q_cnn) == P["y"]) & (q_cnn.max(1) < 0.5)).sum()),
                                             "P OCR": int(((o["P"]["_doc"] == P["y"]) & (o["P"]["_q"].max(1) < 0.5)).sum()),
                                             "D CNN OOF": int(((am(q_oof_d) == D["y"]) & (q_oof_d.max(1) < 0.5)).sum()),
                                             "D OCR": int(((o["D"]["_doc"] == D["y"]) & (o["D"]["_q"].max(1) < 0.5)).sum())},
                      "chi_phi": json.loads((RA / "ocr_chi_phi.json").read_text(encoding="utf-8")) if (RA / "ocr_chi_phi.json").exists() else None}
        for v in bt.values():
            for tap in ("P", "D"):
                for k in ("_doc", "_q"):
                    v[tap].pop(k)

    for tap, d, cot in (("P", P, {"M0": q_m0, "CNN": q_cnn, "CNN_OOF": q_oof_p, "M0_OOF": q_m0_poof}), ("D", D, {"M0_OOF": q_m0_d, "CNN_OOF": q_oof_d})):
        for i, r in enumerate(d["meta"]):
            dong.append({"tap": tap, "i": i, "anh": r["anh"], "loai": r["loai"], "vi_tri": r["vi_tri"], "nguoi": r["nguoi"], "nhan": int(d["y"][i]),
                         **{f"{k}_doc": int(v[i].argmax()) for k, v in cot.items()}, **{f"{k}_p": round(float(v[i].max()), 4) for k, v in cot.items()}})
    with (RA / "du_doan_tung_chu_so.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dong[0]) + [k for k in dong[-1] if k not in dong[0]])
        w.writeheader()
        w.writerows(dong)
    ket["lenh"] = "python tools/so_sanh_ocr.py so-sanh"
    (RA / "ket_qua.json").write_text(json.dumps(ket, ensure_ascii=False, indent=1), encoding="utf-8")
    return ket


def xuat_o() -> dict:
    """Bước OCR-1 (venv chính): xuất ô chữ số cho môi trường OCR riêng (chỉ numpy + onnxruntime, không cv2) -> o_chu_so.npz.
    Hai biến thể đầu vào, CÙNG thứ tự với tap_do (P, D): x28 = ảnh MNIST 28×28 đã có; goc_* = ô cắt GỐC đã bỏ viền (mực 0–255 ở độ phân giải
    ảnh nắn 300 DPI, trước khi co về 28×28). Cắt lại bằng đúng ocr.cat_anh + thứ tự của tools/ocr_du_lieu.py cat; kiểm x28 trùng bộ đệm từng byte."""
    import ocr_du_lieu as OD
    from cv_engine.preprocessing import nap_layout, preprocess
    t = H.tap_do(NGUON)
    lay_t, lay_p = nap_layout("chu_so"), nap_layout("phieu")
    nhan = OD._doc_nhan_phieu()
    goc = {}                                                     # (anh, loai, vi_tri) -> (anh28, ink uint8)
    for path, ten, loai in OD._liet_ke():
        if loai != "trang" and (ma_phieu(ten) or 0) not in PHIEU_TRAIN:
            continue                                             # val 0029–0034: không cắt
        kq = preprocess(str(path), lay_t if loai == "trang" else lay_p)
        if not kq.ok:
            continue
        nhoms = OD._nhom_cua_anh(ten, loai, lay_t, lay_p, nhan)
        for (lo, nhom), cac_o in zip(nhoms, ocr.cat_anh(kq.anh_nan, [[r for _, _, r in nh] for _, nh in nhoms])):
            for (vt, _, _), o in zip(nhom, cac_o):
                goc[(ten, lo, str(vt))] = (o.anh28, np.clip(o.ink * 255 + 0.5, 0, 255).astype(np.uint8))
        print(f"  cắt {ten}")
    ra = {}
    for tap, d in (("P", t["phieu"]), ("D", t["trang"])):
        x28, inks = d["x"], []
        for i, r in enumerate(d["meta"]):
            a28, ink = goc[(r["anh"], r["loai"], r["vi_tri"])]
            assert np.array_equal(a28 if a28 is not None else np.zeros((28, 28), np.uint8), x28[i]), (tap, i)
            inks.append(ink)
        ra[f"{tap}_x28"], ra[f"{tap}_y"] = x28, d["y"]
        ra[f"{tap}_goc"] = np.concatenate([o.ravel() for o in inks])
        ra[f"{tap}_goc_hw"] = np.array([o.shape for o in inks], np.int32)
        ra[f"{tap}_trong"] = np.array([r["trong"] == "1" for r in d["meta"]])
    np.savez_compressed(RA / "o_chu_so.npz", **ra)
    return {"tep": str((RA / "o_chu_so.npz").relative_to(ROOT)), "P": len(ra["P_y"]), "D": len(ra["D_y"]),
            "co_goc_P_trung_vi_hw": np.median(ra["P_goc_hw"], 0).tolist(), "kiem_x28_trung_bo_dem": True}


def doc_ocr(f: Path, yP, yD) -> dict:
    """Một biến thể OCR: độ đúng (∅ = không đọc được tính là SAI), cặp nhầm, sai mà tự tin (đọc ra chữ số SAI và tin cậy ≥ ngưỡng).
    Kèm _doc (nhãn đọc, -1 = ∅) và _q (ma trận 10 cột: tin cậy ở chữ số đọc được, 0 nếu ∅) cho McNemar / luật đối chiếu – bỏ trước khi ghi."""
    rows = list(csv.DictReader(f.open(encoding="utf-8-sig")))
    out = {}
    for tap, y in (("P", yP), ("D", yD)):
        r = sorted((x for x in rows if x["tap"] == tap), key=lambda x: int(x["i"]))
        assert len(r) == len(y), (f, tap)
        doc = np.array([int(x["chu_so"]) if x["chu_so"].isdigit() else -1 for x in r])
        tc = np.array([float(x["tin_cay"] or 0) for x in r])
        sai = doc != y
        k = int((~sai).sum())
        cap = Counter((int(a), int(b)) for a, b in zip(y, doc) if a != b)
        q = np.zeros((len(y), 10))
        q[doc >= 0, doc[doc >= 0]] = tc[doc >= 0]
        out[tap] = {"n": len(y), "dung": k, "acc": round(k / len(y), 4), "wilson95": wilson(k, len(y)), "sai": int(sai.sum()), "khong_doc_duoc": int((doc < 0).sum()),
                    "cap_nham_nhieu_nhat": [f"{a}→{'∅' if b < 0 else b}: {c}" for (a, b), c in cap.most_common(6)],
                    "sai_ma_tu_tin": {str(t): int((sai & (doc >= 0) & (tc >= t)).sum()) for t in (0.5, 0.9, 0.9995)},
                    "ti_le_sai_tu_tin_0_5_tren_so_sai": round(float((sai & (doc >= 0) & (tc >= 0.5)).sum() / max(1, sai.sum())), 4),
                    "_doc": doc, "_q": q}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lenh", choices=["do-cnn", "xuat-o", "so-sanh"])
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    kq = {"do-cnn": do_cnn, "xuat-o": xuat_o, "so-sanh": so_sanh}[a.lenh]()
    print(json.dumps(kq, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
