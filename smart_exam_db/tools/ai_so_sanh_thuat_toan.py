"""
ai_so_sanh_thuat_toan.py - Lệnh AI: so sánh CNN chữ số hiện tại với logistic regression / k-NN / SVM RBF / Random Forest / MLP trên CÙNG ảnh 28×28.
Tiêu chí ĐĂNG KÝ TRƯỚC: docs/tieu_chi_so_sanh_thuat_toan.md (commit 253a4b5 – trước công cụ này). CHỈ ĐO: không sửa models/*, mã hệ thống, CSDL.
Chỉ dev: MNIST, EMNIST Digits test, trang D001–D010, phiếu dev 0001–0028. KHÔNG đọc 0029–0040 / đợt 2 / giấy thật. Cần torch + scikit-learn.

  python tools/ai_so_sanh_thuat_toan.py kiem-ke     # số mẫu từng nguồn -> data/_eval/ai/kiem_ke.json (nguồn số liệu của docs/kiem_ke_du_lieu.md)
  python tools/ai_so_sanh_thuat_toan.py chay        # E1 + E2a + E2b, mọi thuật toán (mỗi đơn vị lưu ở data/_eval/ai/tam/, chạy tiếp được)
  python tools/ai_so_sanh_thuat_toan.py bang        # chỉ số + R1 / R2 -> data/_eval/ai/ket_qua.json, ket_qua.md
  python tools/ai_so_sanh_thuat_toan.py don         # xoá data/_eval/ai/tam/ (sau khi đã có ket_qua.json)
"""
import argparse
import copy
import json
import pickle
import shutil
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402
import ocr_cai_tien as C  # noqa: E402
import ocr_do_luong as L  # noqa: E402

AI = ROOT / "data" / "_eval" / "ai"
TAM = AI / "tam"
TIEU_CHI = "docs/tieu_chi_so_sanh_thuat_toan.md (commit 253a4b5)"
SEEDS = (2026, 1, 2)
SEED0 = 2026
NGUOI = (1, 2, 3, 4, 5)
TAU = 0.5                                     # = tau_khop
GIOI_HAN_FIT_S = 1200                         # 20 phút / lần fit (ghi lại nếu vượt)
N_SVM_E1, N_MNIST_E2B = 20000, 10000          # mẫu con chốt trước
W_LUOI = (1, 5, 20)                           # trọng số ô thật ở E2b
E2A_CNN = dict(lr=2e-3, epochs=30, batch=64)  # CNN / MLP từ đầu chỉ trên ô thật (cố định, không chỉnh)
EPS = 1e-6
THU = False                                   # --thu: chạy thử mã trên dữ liệu tí hon vào thư mục nháp (KHÔNG phải kết quả)

THUAT_TOAN = {   # tên: (nhãn hiển thị, lưới, có ngẫu nhiên?)
    "lr": ("Logistic regression (softmax, điểm ảnh)", [{"C": c} for c in (0.01, 0.1, 1.0)], False),
    "knn": ("k-NN (Euclid)", [{"k": k} for k in (1, 3, 5, 7, 9)], False),
    "svm": ("SVM nhân RBF", [{"C": c} for c in (1.0, 10.0)], False),
    "rf": ("Random Forest (300 cây)", [{"min_samples_leaf": m} for m in (1, 3)], True),
    "mlp": ("MLP 1 lớp ẩn (128)", [{}], True),
    "cnn": ("CNN hiện tại (Conv16–Conv32–Dense64)", [{}], True),
}
NUMPY_THUAN = {"lr": "có (W·x + b, softmax)", "knn": "có, nhưng phải mang theo toàn bộ dữ liệu huấn luyện",
               "svm": "có, cần vectơ hỗ trợ + hệ số đối ngẫu (một-một)", "rf": "có thể, phải tự viết duyệt 300 cây",
               "mlp": "có (2 phép nhân ma trận)", "cnn": "có – đang chạy bằng NumPy trong cv_engine/ocr.py"}


# ------------------------------------------------------------------------------------------- dữ liệu
def mau_con(y: np.ndarray, n: int, seed: int) -> np.ndarray:
    """Chỉ số mẫu con phân tầng theo lớp (tỉ lệ lớp giữ nguyên), cố định theo seed. THUẦN."""
    from sklearn.model_selection import train_test_split
    if n >= len(y):
        return np.arange(len(y))
    idx, _ = train_test_split(np.arange(len(y)), train_size=n, stratify=y, random_state=seed)
    return np.sort(idx)


def du_lieu():
    """Mọi nguồn, cùng định dạng uint8 [N,28,28]. MNIST: 55 000 huấn luyện (= tập tiền huấn luyện CNN) + 5 000 kiểm định nội bộ."""
    xtr, ytr, xte, yte = H.doc_mnist()
    pm = np.random.default_rng(H.SEED).permutation(len(xtr))
    va, tr = pm[:5000], pm[5000:]
    x55, y55 = C.du_lieu_truoc("mnist")
    assert THU or np.array_equal(x55, xtr[tr]) and np.array_equal(y55, ytr[tr])          # đúng tập tiền huấn luyện CNN cũ
    e = np.load(ROOT / "data" / "nguon_ngoai" / "emnist_digits.npz")
    t = H.tap_do("anh_nan")
    nt0, np0 = np.array([int(r["nguoi"]) for r in t["trang"]["meta"]]), np.array([int(r["nguoi"]) for r in t["phieu"]["meta"]])
    it, ip = np.arange(len(nt0)), np.arange(len(np0))
    if THU:                                                                     # chế độ THỬ mã: dữ liệu tí hon, kết quả vô nghĩa
        tr, va = tr[:3000], va[:500]
        g = np.random.default_rng(0)
        it = np.sort(np.concatenate([g.choice(np.where(nt0 == k)[0], 60, replace=False) for k in NGUOI]))
        ip = np.sort(np.concatenate([g.choice(np.where(np0 == k)[0], 30, replace=False) for k in NGUOI if (np0 == k).any()]))
    tt, tp = t["trang"], t["phieu"]
    return {"idx_trang": it, "idx_phieu": ip, "mnist_tr": (xtr[tr], ytr[tr].astype(np.int64)), "mnist_va": (xtr[va], ytr[va].astype(np.int64)),
            "mnist_te": (xte[:500 if THU else None], yte[:500 if THU else None].astype(np.int64)),
            "emnist_chuan": (e["x_test_chuan"][:500 if THU else None], e["y_test"][:500 if THU else None].astype(np.int64)),
            "emnist_tho": (e["x_test"][:500 if THU else None], e["y_test"][:500 if THU else None].astype(np.int64)),
            "trang": (tt["x"][it], tt["y"][it].astype(np.int64), nt0[it]), "phieu": (tp["x"][ip], tp["y"][ip].astype(np.int64), np0[ip])}


def vec(x: np.ndarray) -> np.ndarray:
    return x.reshape(len(x), -1).astype(np.float32) / 255.0


# ------------------------------------------------------------------------------------------- mô hình scikit-learn
def knn_phieu(nhan_lang_gieng: np.ndarray, k: int) -> np.ndarray:
    """Xác suất k-NN = tỉ lệ phiếu của k láng giềng gần nhất (đã sắp theo khoảng cách). THUẦN."""
    n = len(nhan_lang_gieng)
    p = np.zeros((n, 10))
    for j in range(k):
        p[np.arange(n), nhan_lang_gieng[:, j]] += 1
    return p / k


class KNN:
    """k-NN brute force; trọng số w của ô thật = nhân bản w lần (tiêu chí mục 3)."""
    def __init__(self, k):
        self.k = k

    def fit(self, X, y, w=None):
        from sklearn.neighbors import NearestNeighbors
        if w is not None:
            r = np.asarray(w).astype(int)
            X, y = np.repeat(X, r, axis=0), np.repeat(y, r)
        self.y = y
        self.nn = NearestNeighbors(algorithm="brute", n_jobs=-1).fit(X)
        return self

    def lang_gieng(self, X, k):
        out = []
        for i in range(0, len(X), 5000):
            out.append(self.nn.kneighbors(X[i:i + 5000], n_neighbors=k, return_distance=False))
        return self.y[np.concatenate(out)]

    def z(self, X, k=None):
        return np.log(knn_phieu(self.lang_gieng(X, k or self.k), k or self.k) + EPS)


def tao_sk(ten: str, g: dict, seed: int):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    if ten == "lr":
        return LogisticRegression(C=g["C"], max_iter=300)
    if ten == "svm":
        return SVC(kernel="rbf", gamma="scale", C=g["C"], decision_function_shape="ovr")
    if ten == "rf":
        return RandomForestClassifier(n_estimators=300, max_features="sqrt", min_samples_leaf=g["min_samples_leaf"], n_jobs=-1, random_state=seed)
    if ten == "knn":
        return KNN(g["k"])
    raise ValueError(ten)


def diem_sk(ten: str, m, X) -> np.ndarray:
    """z (trước nhiệt độ) [N,10]: LR = log xác suất; SVM = decision_function; RF / k-NN = log(p + 1e-6)."""
    if ten == "lr":
        return m.predict_log_proba(X)
    if ten == "svm":
        return m.decision_function(X)
    if ten == "rf":
        return np.log(m.predict_proba(X) + EPS)
    return m.z(X)


def fit_sk(ten, g, seed, X, y, w=None, ghi=None):
    assert len(np.unique(y)) == 10, "tập huấn luyện thiếu lớp"
    m = tao_sk(ten, g, seed)
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X, y, w) if ten == "knn" else m.fit(X, y, sample_weight=w)
    dt = time.time() - t0
    if ghi is not None:
        ghi.setdefault("fit_giay", []).append(round(dt, 1))
        if dt > GIOI_HAN_FIT_S:
            ghi.setdefault("qua_gioi_han", []).append(round(dt, 1))
    return m


def acc_macro(y, p, ng) -> float:
    return float(np.mean([(p[ng == k] == y[ng == k]).mean() for k in np.unique(ng)]))


# ------------------------------------------------------------------------------------------- mô hình PyTorch
def tao_mlp():
    """MLP 784 → 128 (ReLU, Dropout 0,3) → 10 = 101 770 tham số. Vào [N,1,28,28] như CNN."""
    torch, nn, F = H._torch()

    class MLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.d1, self.d2 = nn.Linear(784, 128), nn.Linear(128, 10)
            self.drop = nn.Dropout(0.3)

        def forward(self, x):
            return self.d2(self.drop(F.relu(self.d1(x.flatten(1)))))
    return MLP()


def tao_mang(ten):
    return H.tao_cnn() if ten == "cnn" else tao_mlp()


def so_tham_so(m) -> int:
    return int(sum(p.numel() for p in m.parameters()))


def tien_huan_luyen(ten: str, seed: int, ghi: dict):
    """CNN: bộ đệm Tuần 6 pre_mnist_co_ban_{seed}.pt (bước 1 của quy trình triển khai). MLP: CÙNG quy trình (10 epoch, Adam 2e-3 + cosine, tăng cường cơ bản)."""
    torch, _, _ = H._torch()
    if ten == "cnn":
        m = H.tao_cnn()
        m.load_state_dict(torch.load(C.CAP / f"pre_mnist_co_ban_{seed}.pt"))
        ghi["pre"] = f"bộ đệm {C.CAP.name}/pre_mnist_co_ban_{seed}.pt"
        return m.eval()
    f = TAM / f"pre_mlp_{seed}.pt"
    if f.exists():
        m = tao_mlp()
        m.load_state_dict(torch.load(f))
        return m.eval()
    x, y = C.du_lieu_truoc("mnist")
    if THU:
        x, y = x[:3000], y[:3000]
    t0 = time.time()
    m = H.huan_luyen_cnn(x, y, C.PRE["epochs"], C.PRE["lr"], seed, mo_hinh=tao_mlp())
    ghi["pre_giay"] = round(time.time() - t0, 1)
    TAM.mkdir(parents=True, exist_ok=True)
    torch.save(m.state_dict(), f)
    return m


# ------------------------------------------------------------------------------------------- đơn vị chạy (mỗi đơn vị một tệp trong tam/)
def tep(thi_nghiem, ten, seed):
    return TAM / f"{thi_nghiem}_{ten}_{seed}.npz"


def luu(thi_nghiem, ten, seed, z: dict, ghi: dict):
    TAM.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(tep(thi_nghiem, ten, seed), **z)
    (TAM / f"{thi_nghiem}_{ten}_{seed}.json").write_text(json.dumps(ghi, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def e1(ten, seed, D):
    ghi = {"thi_nghiem": "E1", "thuat_toan": ten, "seed": seed}
    bo = ("mnist_va", "mnist_te", "emnist_chuan", "emnist_tho")
    if ten in ("cnn", "mlp"):
        m = tien_huan_luyen(ten, seed, ghi)
        ghi["so_tham_so"] = so_tham_so(m)
        ghi["n_huan_luyen"] = len(D["mnist_tr"][1])
        return {b: H.logits(m, D[b][0]) for b in bo}, ghi
    x, y = D["mnist_tr"]
    if ten == "svm":
        i = mau_con(y, N_SVM_E1, SEED0)
        x, y = x[i], y[i]
        ghi["mau_con"] = f"{len(y)} / {len(D['mnist_tr'][1])} (phân tầng, seed {SEED0})"
    X, Xva, yva = vec(x), vec(D["mnist_va"][0]), D["mnist_va"][1]
    ghi["n_huan_luyen"] = len(y)
    ghi["kiem_dinh"] = {}
    if ten == "knn":                                                     # một lần láng giềng cho mọi k
        m = fit_sk(ten, {"k": 9}, seed, X, y, ghi=ghi)
        lg = m.lang_gieng(Xva, 9)
        for g in THUAT_TOAN[ten][1]:
            ghi["kiem_dinh"][json.dumps(g)] = float((knn_phieu(lg, g["k"]).argmax(1) == yva).mean())
        best = max(THUAT_TOAN[ten][1], key=lambda g: ghi["kiem_dinh"][json.dumps(g)])
        m.k = best["k"]
    else:
        best, m = None, None
        for g in THUAT_TOAN[ten][1]:
            mg = fit_sk(ten, g, seed, X, y, ghi=ghi)
            a = float((diem_sk(ten, mg, Xva).argmax(1) == yva).mean())
            ghi["kiem_dinh"][json.dumps(g)] = a
            if best is None or a > ghi["kiem_dinh"][json.dumps(best)]:
                best, m = g, mg
    ghi["chon"] = best
    t0 = time.time()
    z = {b: diem_sk(ten, m, vec(D[b][0])) for b in bo}
    ghi["du_doan_giay"] = round(time.time() - t0, 1)
    return z, ghi


def chon_e1(ten, seed):
    if not THUAT_TOAN[ten][1][0]:
        return {}
    return json.loads((TAM / f"E1_{ten}_{seed}.json").read_text(encoding="utf-8"))["chon"]


def e2(bien_the: str, ten: str, seed: int, D):
    """Leave-one-writer-out. bien_the 'a' = chỉ ô thật; 'b' = MNIST + ô thật. Trả z OOF trên trang D + phiếu dev (thứ tự tap_do)."""
    xt, yt, nt = D["trang"]
    xp, yp, npp = D["phieu"]
    zt, zp = np.zeros((len(yt), 10)), np.zeros((len(yp), 10))
    ghi = {"thi_nghiem": f"E2{bien_the}", "thuat_toan": ten, "seed": seed, "theo_fold": {}}
    if ten in ("cnn", "mlp"):
        if bien_the == "b":
            pre = tien_huan_luyen(ten, seed, ghi)
            lt, lp = C.oof(pre, "co_ban", seed)                          # tinh chỉnh 5 fold theo người – GIỐNG HỆT quy trình cũ
            if ten == "cnn":
                z0 = np.load(C.CAP / f"oof_g0_goc_{seed}.npz")
                ch = max(float(np.abs(z0["trang"] - lt).max()), float(np.abs(z0["phieu"] - lp).max()))
                ghi["chenh_logit_so_voi_bo_dem_g0_goc"] = ch
                if ch > 1e-4:
                    sys.exit(f"DỪNG: CNN E2b seed {seed} khác bộ đệm oof_g0_goc ({ch:.3g}) – tiêu chí mục 3")
            lt, lp = lt[D["idx_trang"]], lp[D["idx_phieu"]]
            if seed == SEED0 and ten == "mlp":
                m1 = H.huan_luyen_cnn(xt[nt != 1], yt[nt != 1], C.FT["epochs"], C.FT["lr"], seed, mo_hinh=copy.deepcopy(pre), batch=C.FT["batch"])
                ghi["trong_so_nguoi1"] = {k: v.numpy().tolist() for k, v in m1.state_dict().items()}
                ghi["so_tham_so"] = so_tham_so(m1)
            return {"trang": lt, "phieu": lp}, ghi
        for k in NGUOI:
            t0 = time.time()
            m = H.huan_luyen_cnn(xt[nt != k], yt[nt != k], E2A_CNN["epochs"], E2A_CNN["lr"], seed, mo_hinh=tao_mang(ten), batch=E2A_CNN["batch"])
            zt[nt == k] = H.logits(m, xt[nt == k])
            if (npp == k).any():
                zp[npp == k] = H.logits(m, xp[npp == k])
            ghi["theo_fold"][k] = {"fit_giay": round(time.time() - t0, 1)}
        return {"trang": zt, "phieu": zp}, ghi
    Xt, Xp = vec(xt), vec(xp)
    if bien_the == "b":
        xm, ym = D["mnist_tr"]
        im = mau_con(ym, N_MNIST_E2B, SEED0)
        Xm, ym = vec(xm[im]), ym[im]
        g_e1 = chon_e1(ten, seed if THUAT_TOAN[ten][2] else SEED0)
        ghi["mau_con_mnist"] = f"{len(ym)} (phân tầng, seed {SEED0})"
        ghi["sieu_tham_so_tu_E1"] = g_e1
    for k in NGUOI:
        tr = nt != k
        f = {"luoi": {}}
        if bien_the == "a":
            ung_vien = [(g, None) for g in THUAT_TOAN[ten][1]]
        else:
            ung_vien = [(g_e1, w) for w in W_LUOI]

        def bo_huan_luyen(chon, w):
            if bien_the == "a":
                return Xt[chon], yt[chon], None
            return (np.concatenate([Xm, Xt[chon]]), np.concatenate([ym, yt[chon]]),
                    np.concatenate([np.ones(len(ym)), np.full(int(chon.sum()), float(w))]))
        trong = [j for j in NGUOI if j != k]                             # kiểm định LỒNG: bỏ thêm 1 trong 4 người
        if ten == "knn" and bien_the == "a":
            dung = {json.dumps(g): [] for g, _ in ung_vien}
            for j in trong:
                c = tr & (nt != j)
                X_, y_, w_ = bo_huan_luyen(c, None)
                lg = fit_sk(ten, {"k": 9}, seed, X_, y_, w_, f).lang_gieng(Xt[nt == j], 9)
                for g, _ in ung_vien:
                    dung[json.dumps(g)].append(float((knn_phieu(lg, g["k"]).argmax(1) == yt[nt == j]).mean()))
            f["luoi"] = {g: float(np.mean(v)) for g, v in dung.items()}
        else:
            for g, w in ung_vien:
                khoa = json.dumps(g) if bien_the == "a" else f"w={w}"
                a = []
                for j in trong:
                    c = tr & (nt != j)
                    X_, y_, w_ = bo_huan_luyen(c, w)
                    m = fit_sk(ten, g, seed, X_, y_, w_, f)
                    a.append(float((diem_sk(ten, m, Xt[nt == j]).argmax(1) == yt[nt == j]).mean()))
                f["luoi"][khoa] = float(np.mean(a))
        i_best = int(np.argmax(list(f["luoi"].values())))
        g, w = ung_vien[i_best]
        f["chon"] = g if bien_the == "a" else {"w": w}
        X_, y_, w_ = bo_huan_luyen(tr, w)
        m = fit_sk(ten, g, seed, X_, y_, w_, f)
        zt[nt == k] = diem_sk(ten, m, Xt[nt == k])
        if (npp == k).any():
            zp[npp == k] = diem_sk(ten, m, Xp[npp == k])
        if k == 1 and seed == SEED0 and bien_the == "b":
            b = pickle.dumps(m, protocol=pickle.HIGHEST_PROTOCOL)
            ghi["kich_thuoc_pickle_byte"] = len(b)
            (TAM / f"mo_hinh_E2b_{ten}_nguoi1.pkl").write_bytes(b)
        ghi["theo_fold"][k] = f
        print(f"    E2{bien_the} {ten} seed {seed} người {k}: chọn {f['chon']}  (lưới {f['luoi']})")
    return {"trang": zt, "phieu": zp}, ghi


def cmd_chay(a):
    D = du_lieu()
    nk = AI / "nhat_ky_chay.json"
    log = json.loads(nk.read_text(encoding="utf-8")) if nk.exists() else {"bat_dau": time.strftime("%Y-%m-%d %H:%M:%S")}
    for thi in a.thi_nghiem:
        for ten in a.thuat_toan:
            for sd in (SEEDS if THUAT_TOAN[ten][2] else (SEED0,)):
                if tep(thi, ten, sd).exists():
                    print(f"  đã có {thi} {ten} {sd}")
                    continue
                t0 = time.time()
                print(f"[{thi} {ten} seed {sd}] bắt đầu {time.strftime('%H:%M:%S')}")
                z, ghi = e1(ten, sd, D) if thi == "E1" else e2(thi[-1], ten, sd, D)
                ghi["giay"] = round(time.time() - t0, 1)
                luu(thi, ten, sd, z, ghi)
                log[f"{thi}_{ten}_{sd}"] = ghi["giay"]
                nk.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"[{thi} {ten} seed {sd}] xong {ghi['giay']:.0f} s")
    log["ket_thuc"] = time.strftime("%Y-%m-%d %H:%M:%S")
    nk.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------------------------------- chỉ số (THUẦN)
def chi_so_e2(z_tr, z_ph, yt, nt, yp, npp) -> dict:
    """Một (thuật toán, seed): T trên OOF trang D (chon_nhiet), độ đúng theo người, sai mà tự tin p ≥ 0,5, ma trận nhầm lẫn."""
    T = L.chon_nhiet(z_tr, yt)
    pt, pp = L.softmax(z_tr / T), L.softmax(z_ph / T)
    at, ap = pt.argmax(1), pp.argmax(1)
    r = {"T": round(T, 2), "theo_nguoi": {str(k): float((at[nt == k] == yt[nt == k]).mean()) for k in NGUOI}}
    r["macro"] = float(np.mean(list(r["theo_nguoi"].values())))
    r["micro"] = float((at == yt).mean())
    r["phieu"] = float((ap == yp).mean())
    r["phieu_theo_nguoi"] = {str(k): float((ap[npp == k] == yp[npp == k]).mean()) for k in NGUOI if (npp == k).any()}
    r["sai_tu_tin_trang"] = int(((at != yt) & (pt.max(1) >= TAU)).sum())
    r["sai_tu_tin_phieu"] = int(((ap != yp) & (pp.max(1) >= TAU)).sum())
    r["sai_trang"] = int((at != yt).sum())
    cm = np.zeros((10, 10), int)
    np.add.at(cm, (yt, at), 1)
    r["confusion"] = cm.tolist()
    r["dung_tung_o"] = (at == yt)
    return r


def gop_seed(rs: list[dict]) -> dict:
    """Gộp các seed: macro TB, SD giữa 5 người (của độ đúng từng người TB qua seed), SD giữa seed, sai mà tự tin cộng các seed. THUẦN."""
    ng = {k: float(np.mean([r["theo_nguoi"][k] for r in rs])) for k in rs[0]["theo_nguoi"]}
    out = {"n_seed": len(rs), "macro": float(np.mean([r["macro"] for r in rs])), "sd_nguoi": float(np.std(list(ng.values()), ddof=1)),
           "sd_seed": float(np.std([r["macro"] for r in rs], ddof=1)) if len(rs) > 1 else 0.0, "theo_nguoi": ng,
           "micro": float(np.mean([r["micro"] for r in rs])), "phieu": float(np.mean([r["phieu"] for r in rs])),
           "sai_tu_tin_trang_cong": int(sum(r["sai_tu_tin_trang"] for r in rs)), "sai_tu_tin_phieu_cong": int(sum(r["sai_tu_tin_phieu"] for r in rs)),
           "sai_trang_cong": int(sum(r["sai_trang"] for r in rs)), "T": [r["T"] for r in rs],
           "confusion_cong": np.sum([np.array(r["confusion"]) for r in rs], axis=0).tolist()}
    return out


def ket_luan_r1(e2b: dict) -> dict:
    """R1: CNN hợp lý nếu macro E2b (TB seed) ≥ tốt nhất − 1,0 điểm %. THUẦN."""
    tot = max(e2b, key=lambda t: e2b[t]["macro"])
    chenh = 100 * (e2b[tot]["macro"] - e2b["cnn"]["macro"])
    return {"tot_nhat": tot, "macro_tot_nhat": e2b[tot]["macro"], "macro_cnn": e2b["cnn"]["macro"], "chenh_diem": round(chenh, 3),
            "hop_ly": bool(chenh <= 1.0 + 1e-9),
            "dung_hon_cnn": sorted([(t, round(100 * (v["macro"] - e2b["cnn"]["macro"]), 3)) for t, v in e2b.items()
                                    if t != "cnn" and v["macro"] > e2b["cnn"]["macro"]], key=lambda x: -x[1])}


# ------------------------------------------------------------------------------------------- kích thước + thời gian
def do_tg(f, x, lan=300) -> float:
    for i in range(10):
        f(x[i:i + 1])
    t = []
    for i in range(lan):
        a = time.perf_counter()
        f(x[i % len(x):i % len(x) + 1])
        t.append((time.perf_counter() - a) * 1000)
    return float(np.median(t))


def kich_thuoc_toc_do(D) -> dict:
    from cv_engine import ocr
    xt = D["trang"][0][:300]
    out = {}
    for ten in ("lr", "knn", "svm", "rf"):
        f = TAM / f"mo_hinh_E2b_{ten}_nguoi1.pkl"
        m = pickle.loads(f.read_bytes())
        if ten == "rf":
            m.n_jobs = 1
        if ten == "knn":
            m.nn.n_jobs = 1
        X = vec(xt)
        out[ten] = {"byte": f.stat().st_size, "ms_moi_o": do_tg(lambda v: diem_sk(ten, m, v), X), "nguon": "pickle mô hình E2b (người 1 giữ ra, seed 2026)"}
        if ten == "svm":
            out[ten]["so_vecto_ho_tro"] = int(m.support_vectors_.shape[0])
        if ten == "knn":
            out[ten]["so_mau_luu"] = int(len(m.y))
    g = json.loads((TAM / f"E2b_mlp_{SEED0}.json").read_text(encoding="utf-8"))
    W = {k: np.array(v, np.float32) for k, v in g["trong_so_nguoi1"].items()}
    n_mlp = int(sum(v.size for v in W.values()))

    def mlp_np(v):
        h = np.maximum(v.reshape(len(v), -1).astype(np.float32) / 255.0 @ W["d1.weight"].T + W["d1.bias"], 0)
        return L.softmax(h @ W["d2.weight"].T + W["d2.bias"])
    out["mlp"] = {"byte": 4 * n_mlp, "so_tham_so": n_mlp, "ms_moi_o": do_tg(mlp_np, xt), "nguon": "trọng số float32 (NumPy)"}
    mh = ocr.nap_mo_hinh_ocr()
    out["cnn"] = {"byte": 4 * 105866, "so_tham_so": 105866, "byte_json_trien_khai": (ROOT / "models" / "ocr_cnn.json").stat().st_size,
                  "ms_moi_o": do_tg(lambda v: ocr.du_doan_xac_suat(mh, v), xt), "nguon": "trọng số float32; đo bằng cv_engine.ocr (NumPy, mô hình triển khai)"}
    return out


# ------------------------------------------------------------------------------------------- bảng
def nap(thi, ten):
    seeds = SEEDS if THUAT_TOAN[ten][2] else (SEED0,)
    return [(sd, np.load(tep(thi, ten, sd)), json.loads((TAM / f"{thi}_{ten}_{sd}.json").read_text(encoding="utf-8"))) for sd in seeds]


def cmd_bang(a):
    from scipy.stats import binomtest
    D = du_lieu()
    yt, nt = D["trang"][1], D["trang"][2]
    yp, npp = D["phieu"][1], D["phieu"][2]
    kq = {"tieu_chi": TIEU_CHI, "ngay": time.strftime("%Y-%m-%d %H:%M"), "E1": {}, "E2a": {}, "E2b": {}, "chi_tiet_chay": {}}
    dung = {}
    for ten in THUAT_TOAN:
        r1 = []
        for sd, z, g in nap("E1", ten):
            T = L.chon_nhiet(z["mnist_va"], D["mnist_va"][1])
            r = {"T": round(T, 2)}
            for b in ("mnist_va", "mnist_te", "emnist_chuan", "emnist_tho"):
                p = L.softmax(z[b] / T)
                y = D[b][1]
                r[b] = float((p.argmax(1) == y).mean())
                r[f"{b}_sai_tu_tin"] = int(((p.argmax(1) != y) & (p.max(1) >= TAU)).sum())
            r1.append(r)
            kq["chi_tiet_chay"][f"E1|{ten}|{sd}"] = {k: v for k, v in g.items() if k != "trong_so_nguoi1"}
        kq["E1"][ten] = {b: float(np.mean([r[b] for r in r1])) for b in r1[0] if b != "T"}
        kq["E1"][ten]["sd_seed_mnist_te"] = float(np.std([r["mnist_te"] for r in r1], ddof=1)) if len(r1) > 1 else 0.0
        kq["E1"][ten]["n_seed"] = len(r1)
        for thi in ("E2a", "E2b"):
            rs = []
            for sd, z, g in nap(thi, ten):
                r = chi_so_e2(z["trang"], z["phieu"], yt, nt, yp, npp)
                dung[(thi, ten, sd)] = r.pop("dung_tung_o")
                rs.append(r)
                kq["chi_tiet_chay"][f"{thi}|{ten}|{sd}"] = {k: v for k, v in g.items() if k != "trong_so_nguoi1"} | {"T": r["T"], "macro": r["macro"]}
            kq[thi][ten] = gop_seed(rs)
    kq["R1"] = ket_luan_r1(kq["E2b"])
    tot = kq["R1"]["tot_nhat"]
    if tot != "cnn":                                                     # kiểm định dấu cặp theo ô, cộng 3 seed của CNN (thuật toán tất định: lặp lại)
        bd = np.concatenate([dung[("E2b", "cnn", s)] for s in SEEDS])
        ud = np.concatenate([dung[("E2b", tot, s if THUAT_TOAN[tot][2] else SEED0)] for s in SEEDS])
        n10, n01 = int((bd & ~ud).sum()), int((~bd & ud).sum())
        kq["R1"]["dau_cap"] = {"cnn_dung_kia_sai": n10, "kia_dung_cnn_sai": n01, "p": float(binomtest(n01, n10 + n01, 0.5).pvalue) if n10 + n01 else 1.0}
    kq["kich_thuoc_toc_do"] = kich_thuoc_toc_do(D)
    kq["numpy_thuan"] = NUMPY_THUAN
    import platform
    import sklearn
    import torch
    kq["moi_truong"] = {"cpu": platform.processor(), "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
                        "torch": torch.__version__}
    AI.mkdir(parents=True, exist_ok=True)
    (AI / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md = bao_cao(kq)
    (AI / "ket_qua.md").write_text(md, encoding="utf-8")
    print(md)


def pt(v):
    return f"{100 * v:.2f}%"


def bao_cao(kq: dict) -> str:
    kt = kq["kich_thuoc_toc_do"]
    L_ = [f"# So sánh CNN với các thuật toán khác (lệnh AI)", "", f"Tiêu chí: `{kq['tieu_chi']}`. Chạy: `python tools/ai_so_sanh_thuat_toan.py chay` rồi `bang`.", "",
          "## Bảng tổng hợp (dán vào báo cáo / slide)", "",
          "E1 = học MNIST, đo ảnh scan chuẩn. E2 = học 4 người viết, đo người thứ 5 (trang D, độ đúng TB 5 người ± độ lệch chuẩn giữa người; mô hình ngẫu nhiên TB 3 seed).", "",
          "| Thuật toán | E1 MNIST test (10 000) | E1 EMNIST test (40 000) | E2a: chỉ ô thật | **E2b: MNIST + ô thật** | Sai mà tự tin E2b (p ≥ 0,5, trang D) | Kích thước | ms / ô (CPU) | NumPy thuần |",
          "|---|---|---|---|---|---|---|---|---|"]
    for t, (nhan, _, ng) in THUAT_TOAN.items():
        e1, a, b, k = kq["E1"][t], kq["E2a"][t], kq["E2b"][t], kt[t]
        kb = f"{k['byte'] / 1e6:.2f} MB" if k["byte"] >= 1e5 else f"{k['byte'] / 1e3:.0f} KB"
        L_.append(f"| {'**' + nhan + '**' if t == 'cnn' else nhan} | {pt(e1['mnist_te'])} | {pt(e1['emnist_chuan'])} | {pt(a['macro'])} ± {100 * a['sd_nguoi']:.2f} | "
                  f"**{pt(b['macro'])} ± {100 * b['sd_nguoi']:.2f}** | {b['sai_tu_tin_trang_cong']}{' (3 seed)' if ng else ' (1 lần)'} | {kb} | {k['ms_moi_o']:.2f} | {NUMPY_THUAN[t]} |")
    r = kq["R1"]
    L_ += ["", "## Kết luận theo tiêu chí", "",
           f"- **R1**: thuật toán đúng nhất ở E2b là **{THUAT_TOAN[r['tot_nhat']][0]}** ({pt(r['macro_tot_nhat'])}); CNN {pt(r['macro_cnn'])}; "
           f"CNN thấp hơn tốt nhất **{r['chenh_diem']:.2f} điểm** (ngưỡng 1,0) → **{'CNN HỢP LÝ về độ đúng' if r['hop_ly'] else 'CNN KHÔNG đạt R1'}**."]
    if r["dung_hon_cnn"]:
        L_.append("- Thuật toán đúng hơn CNN ở E2b: " + "; ".join(f"{THUAT_TOAN[t][0]} +{d:.2f} điểm" for t, d in r["dung_hon_cnn"]) + ".")
    if "dau_cap" in r:
        d = r["dau_cap"]
        L_.append(f"- Kiểm định dấu cặp theo ô (phụ): CNN đúng / {r['tot_nhat']} sai {d['cnn_dung_kia_sai']}, ngược lại {d['kia_dung_cnn_sai']}, p = {d['p']:.3g}.")
    L_ += ["- **R2** (lý do phụ, không thay R1): kích thước và thời gian ở bảng trên.", "",
           "## E2 theo từng người viết (trang D, TB seed)", "", "| Thuật toán | Thí nghiệm | " + " | ".join(f"Người {k}" for k in NGUOI) + " | SD giữa seed | T |",
           "|---|---|" + "---|" * len(NGUOI) + "---|---|"]
    for thi in ("E2a", "E2b"):
        for t in THUAT_TOAN:
            v = kq[thi][t]
            L_.append(f"| {THUAT_TOAN[t][0]} | {thi} | " + " | ".join(pt(v["theo_nguoi"][str(k)]) for k in NGUOI) + f" | {100 * v['sd_seed']:.2f} | {v['T']} |")
    L_ += ["", "## Số phụ", "", "| Thuật toán | E1 kiểm định MNIST | E1 EMNIST thô (không qua ve_mnist) | E2a sai mà tự tin | E2b sai tổng (trang D) | E2b phiếu dev (504 ô, người 1–4) | E2b sai mà tự tin phiếu |",
           "|---|---|---|---|---|---|---|"]
    for t in THUAT_TOAN:
        e1, a, b = kq["E1"][t], kq["E2a"][t], kq["E2b"][t]
        L_.append(f"| {THUAT_TOAN[t][0]} | {pt(e1['mnist_va'])} | {pt(e1['emnist_tho'])} | {a['sai_tu_tin_trang_cong']} | {b['sai_trang_cong']} | {pt(b['phieu'])} | {b['sai_tu_tin_phieu_cong']} |")
    L_ += ["", "## Cặp nhầm hay gặp ở E2b (thật → đoán, cộng các seed)", ""]
    for t in THUAT_TOAN:
        cm = np.array(kq["E2b"][t]["confusion_cong"])
        np.fill_diagonal(cm, 0)
        top = sorted(((int(cm[i, j]), i, j) for i in range(10) for j in range(10) if cm[i, j]), reverse=True)[:5]
        L_.append(f"- {THUAT_TOAN[t][0]}: " + ", ".join(f"{i}→{j} ({n})" for n, i, j in top))
    L_ += ["", "## Siêu tham số đã chọn (kiểm định trong tập huấn luyện)", ""]
    for k, v in kq["chi_tiet_chay"].items():
        thi, t, sd = k.split("|")
        if thi == "E1" and "chon" in v:
            L_.append(f"- E1 {t} seed {sd}: {v['chon']} (kiểm định {v.get('kiem_dinh')}); huấn luyện {v.get('n_huan_luyen')} ảnh{' – mẫu con ' + v['mau_con'] if 'mau_con' in v else ''}")
        if thi != "E1" and v.get("theo_fold") and t not in ("cnn", "mlp"):
            L_.append(f"- {thi} {t} seed {sd}: " + "; ".join(f"người {f}: {d['chon']}" for f, d in v["theo_fold"].items()))
    qua = [k for k, v in kq["chi_tiet_chay"].items() if any(f.get("qua_gioi_han") for f in v.get("theo_fold", {}).values() if isinstance(f, dict)) or v.get("qua_gioi_han")]
    L_ += ["", f"Lần fit vượt 20 phút: {', '.join(qua) if qua else 'không có'}.",
           f"CNN E2b dựng lại so với bộ đệm `oof_g0_goc`: chênh logit lớn nhất "
           + ", ".join(f"seed {k.split('|')[2]} {v.get('chenh_logit_so_voi_bo_dem_g0_goc')}" for k, v in kq["chi_tiet_chay"].items() if k.startswith("E2b|cnn")) + ".",
           "", f"Môi trường: {kq['moi_truong']}. Thời gian: trung vị 300 lần gọi một ô, một luồng cho RF / k-NN."]
    return "\n".join(L_) + "\n"


# ------------------------------------------------------------------------------------------- kiểm kê
def cmd_kiem_ke(a):
    import csv
    import zipfile
    from collections import Counter
    m = list(csv.DictReader((H.OCR / "cat" / "anh_nan.csv").open(encoding="utf-8", newline="")))
    tr = [r for r in m if r["loai"] == "trang"]
    D = du_lieu()
    out = {"trang_tong": len(tr), "trang_ok_vien": sum(r["ok_vien"] == "1" for r in tr), "theo_nguoi": {}}
    for k in "12345":
        s = [r for r in tr if r["nguoi"] == k]
        ok = [r for r in s if r["ok_vien"] == "1"]
        out["theo_nguoi"][k] = {"trang": sorted({r["anh"] for r in s}), "tong": len(s), "ok_vien": len(ok),
                                "theo_chu_so_ok": [sum(r["nhan"] == str(d) for r in ok) for d in range(10)]}
    out["theo_chu_so_ok"] = [sum(r["nhan"] == str(d) and r["ok_vien"] == "1" for r in tr) for d in range(10)]
    yp, npp = D["phieu"][1], D["phieu"][2]
    out["phieu_dev"] = {"tong": len(yp), "theo_nguoi": {str(k): int((npp == k).sum()) for k in NGUOI if (npp == k).any()},
                        "theo_chu_so": np.bincount(yp, minlength=10).tolist(), "bo_dem_co": dict(Counter(r["loai"] for r in m if r["loai"] != "trang"))}
    out["mnist"] = {"train_goc": 60000, "huan_luyen": len(D["mnist_tr"][1]), "kiem_dinh_noi_bo": len(D["mnist_va"][1]), "test": len(D["mnist_te"][1])}
    z = zipfile.ZipFile(ROOT / "data" / "nguon_ngoai" / "emnist" / "emnist_archive.zip")
    out["emnist_zip"] = [(i.filename, i.file_size) for i in z.infolist()]
    e = np.load(ROOT / "data" / "nguon_ngoai" / "emnist_digits.npz")
    out["emnist_npz"] = {k: list(e[k].shape) for k in e.files if k != "sha256_zip"}
    g = np.load(ROOT / "data" / "_eval" / "ad" / "o_gia.npz", allow_pickle=True)
    out["o_gia"] = {"tong": len(g["y"]), "theo_nguon": {str(k): int(v) for k, v in Counter(g["nguon"].tolist()).items()},
                    "theo_chu_so": np.bincount(g["y"], minlength=10).tolist()}
    omr = list(csv.DictReader((ROOT / "data" / "_omr" / "dac_trung_nan.csv").open(encoding="utf-8", newline="")))
    out["omr_m1"] = {"tong": len(omr), "so_anh": len({r["anh"] for r in omr}), "so_phieu": len({r["phieu"] for r in omr}),
                     "theo_loai_nhan": {l: dict(Counter(r["nhan"] for r in omr if r["loai"] == l)) for l in ("cau", "bubble")},
                     "theo_fold": dict(sorted(Counter(r["fold"] for r in omr).items())), "theo_dieu_kien": dict(Counter(r["dieu_kien"] for r in omr))}
    AI.mkdir(parents=True, exist_ok=True)
    (AI / "kiem_ke.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "emnist_zip"}, ensure_ascii=False, indent=1))


def cmd_don(a):
    if not (AI / "ket_qua.json").exists():
        sys.exit("Chưa có ket_qua.json – không xoá thư mục tạm.")
    if TAM.exists():
        n = sum(f.stat().st_size for f in TAM.rglob("*") if f.is_file())
        shutil.rmtree(TAM)
        print(f"Xoá {TAM} ({n / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["kiem-ke", "chay", "bang", "don"])
    ap.add_argument("--thi-nghiem", nargs="+", default=["E1", "E2a", "E2b"], choices=["E1", "E2a", "E2b"])
    ap.add_argument("--thuat-toan", nargs="+", default=list(THUAT_TOAN), choices=list(THUAT_TOAN))
    ap.add_argument("--thu", metavar="THU_MUC_NHAP", help="chạy thử mã (dữ liệu tí hon) – ghi vào thư mục nháp, KHÔNG phải kết quả")
    a = ap.parse_args()
    if a.thu:
        THU, AI = True, Path(a.thu)
        TAM, N_SVM_E1, N_MNIST_E2B = AI / "tam", 1000, 1000
    {"kiem-ke": cmd_kiem_ke, "chay": cmd_chay, "bang": cmd_bang, "don": cmd_don}[a.lenh](a)
