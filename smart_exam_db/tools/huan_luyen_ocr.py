import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine.tap_du_lieu import PHIEU_TRAIN, ma_phieu, nguoi_viet  # noqa: E402

DATA = ROOT / "data"
OCR = DATA / "_ocr"
EVAL = DATA / "_eval" / "ocr"
NGUON = ("anh_nan", "anh_chuan_hoa")
SEED = 2026


def doc_mnist():
    def idx(ten, anh):
        with gzip.open(OCR / "nguon" / ten, "rb") as f:
            b = f.read()
        if anh:
            n, h, w = (int.from_bytes(b[4 + 4 * i:8 + 4 * i], "big") for i in range(3))
            return np.frombuffer(b, np.uint8, offset=16).reshape(n, h, w)
        return np.frombuffer(b, np.uint8, offset=8)
    return (idx("train-images-idx3-ubyte.gz", True), idx("train-labels-idx1-ubyte.gz", False),
            idx("t10k-images-idx3-ubyte.gz", True), idx("t10k-labels-idx1-ubyte.gz", False))


def doc_cat(nguon: str):
    x = np.load(OCR / "cat" / f"{nguon}.npz")["x"]
    with (OCR / "cat" / f"{nguon}.csv").open(encoding="utf-8", newline="") as f:
        m = list(csv.DictReader(f))
    assert len(m) == len(x)
    return x, m


def tap_do(nguon: str):
    x, m = doc_cat(nguon)
    out = {}
    tr = [i for i, r in enumerate(m) if r["loai"] == "trang"]
    giu = [i for i in tr if m[i]["ok_vien"] == "1"]
    out["trang"] = {"x": x[giu], "y": np.array([int(m[i]["nhan"]) for i in giu]), "meta": [m[i] for i in giu], "bo": len(tr) - len(giu),
                    "tong": len(tr)}
    ph = [i for i, r in enumerate(m) if r["loai"] != "trang" and (ma_phieu(r["anh"]) or 0) in PHIEU_TRAIN]
    out["phieu"] = {"x": x[ph], "y": np.array([int(m[i]["nhan"]) for i in ph]), "meta": [m[i] for i in ph], "bo": 0, "tong": len(ph)}
    return out


def cp_ci(k: int, n: int, a: float = 0.05) -> tuple[float, float]:
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


def f1_lop(y, p):
    out = []
    for c in range(10):
        tp = int(((y == c) & (p == c)).sum())
        fp, fn = int(((y != c) & (p == c)).sum()), int(((y == c) & (p != c)).sum())
        out.append(round(2 * tp / (2 * tp + fp + fn), 4) if tp + fp + fn else None)
    return out


def tom_tat(y, p) -> dict:
    n, k = len(y), int((y == p).sum())
    lo, hi = cp_ci(k, n)
    cm = np.zeros((10, 10), int)
    for a, b in zip(y, p):
        cm[a, b] += 1
    return {"n": n, "dung": k, "acc": round(k / n, 4), "ci95": [round(lo, 4), round(hi, 4)], "f1_lop": f1_lop(y, p), "confusion": cm.tolist()}


def theo_nguoi(y, p, meta) -> dict:
    out = {}
    ng = np.array([int(r["nguoi"]) for r in meta])
    for n in range(1, 6):
        s = ng == n
        if s.any():
            k = int((y[s] == p[s]).sum())
            lo, hi = cp_ci(k, int(s.sum()))
            out[str(n)] = {"n": int(s.sum()), "acc": round(k / s.sum(), 4), "ci95": [round(lo, 4), round(hi, 4)]}
    return out


def theo_dieu_kien(y, p, meta) -> dict:
    out = {}
    dk = np.array([r["anh"].split("_")[-1] for r in meta])
    for c in ("C1", "C2", "C3", "C4"):
        s = dk == c
        if s.any():
            k = int((y[s] == p[s]).sum())
            lo, hi = cp_ci(k, int(s.sum()))
            out[c] = {"n": int(s.sum()), "acc": round(k / s.sum(), 4), "ci95": [round(lo, 4), round(hi, 4)]}
    return out


def muc_truong(y, p, meta) -> dict:
    t = {}
    for yi, pi, r in zip(y, p, meta):
        k = (r["anh"], r["loai"])
        t.setdefault(k, []).append((int(r["vi_tri"]), yi == pi))
    out = {}
    for lo in ("sbd", "ma_de"):
        s = [all(ok for _, ok in v) for (a, l), v in t.items() if l == lo]
        k = sum(s)
        lo_, hi_ = cp_ci(k, len(s))
        out[lo] = {"n": len(s), "dung": k, "acc": round(k / len(s), 4), "ci95": [round(lo_, 4), round(hi_, 4)]}
    return out


def do_mo_hinh(du_doan, ten: str, ghi: dict):
    _, _, xte, yte = doc_mnist()
    p = du_doan(xte)
    ghi["mnist_test"] = tom_tat(yte, p)
    print(f"[{ten}] MNIST test  acc {ghi['mnist_test']['acc']:.4f}  CI95 {ghi['mnist_test']['ci95']}")
    for nguon in NGUON:
        t = tap_do(nguon)
        g = ghi.setdefault(nguon, {})
        for ten_tap, d in t.items():
            p = du_doan(d["x"])
            r = tom_tat(d["y"], p)
            r["theo_nguoi"] = theo_nguoi(d["y"], p, d["meta"])
            r["bo_o"], r["tong_o"] = d["bo"], d["tong"]
            if ten_tap == "phieu":
                r["theo_dieu_kien"] = theo_dieu_kien(d["y"], p, d["meta"])
                r["muc_truong"] = muc_truong(d["y"], p, d["meta"])
            g[ten_tap] = r
            ng = " ".join(f"n{k}:{v['acc']:.3f}" for k, v in r["theo_nguoi"].items())
            print(f"[{ten}] {nguon:14s} {ten_tap:5s} n={r['n']:5d} acc {r['acc']:.4f} CI95 {r['ci95']} | {ng}"
                  + (" | " + " ".join(f"{k}:{v['acc']:.3f}" for k, v in r["theo_dieu_kien"].items()) if ten_tap == "phieu" else "")
                  + (f" | trường SBD {r['muc_truong']['sbd']['acc']:.3f} mã đề {r['muc_truong']['ma_de']['acc']:.3f}" if ten_tap == "phieu" else ""))


def hog28(x: np.ndarray) -> np.ndarray:
    if len(x) > 2000:
        return np.concatenate([hog28(x[i:i + 2000]) for i in range(0, len(x), 2000)])
    return _hog28(x)


def _hog28(x: np.ndarray) -> np.ndarray:
    g = x.astype(np.float32) / 255.0
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, :, 1:-1] = g[:, :, 2:] - g[:, :, :-2]
    gy[:, 1:-1, :] = g[:, 2:, :] - g[:, :-2, :]
    mag = np.hypot(gx, gy)
    ang = (np.arctan2(gy, gx) % np.pi) / np.pi * 9.0
    b0 = np.floor(ang).astype(int) % 9
    w1 = ang - np.floor(ang)
    n = len(x)
    cell = np.zeros((n, 4, 4, 9), np.float32)
    for k, w in ((b0, mag * (1 - w1)), ((b0 + 1) % 9, mag * w1)):
        oh = np.zeros((n, 28, 28, 9), np.float32)
        np.put_along_axis(oh, k[..., None], w[..., None], axis=3)
        cell += oh.reshape(n, 4, 7, 4, 7, 9).sum(axis=(2, 4))
    blk = np.concatenate([cell[:, i:i + 2, j:j + 2].reshape(n, 1, 36) for i in range(3) for j in range(3)], axis=1)
    blk /= np.sqrt((blk ** 2).sum(axis=2, keepdims=True) + 1e-6)
    return blk.reshape(n, 324)


def cmd_m0(a):
    from sklearn.linear_model import LogisticRegression
    EVAL.mkdir(parents=True, exist_ok=True)
    xtr, ytr, xte, yte = doc_mnist()
    rng = np.random.default_rng(SEED)
    pm = rng.permutation(len(xtr))
    va, tr = pm[:5000], pm[5000:]
    t0 = time.time()
    ftr, fva = hog28(xtr[tr]), hog28(xtr[va])
    print(f"HOG {len(tr)}+{len(va)} ảnh: {time.time() - t0:.0f} s")
    best = None
    for C in (0.1, 1.0, 10.0):
        m = LogisticRegression(C=C, max_iter=300, random_state=SEED).fit(ftr, ytr[tr])
        acc = float((m.predict(fva) == ytr[va]).mean())
        print(f"  C={C:<5} val MNIST {acc:.4f}")
        if best is None or acc > best[0]:
            best = (acc, C, m)
    _, C, m = best
    ghi = {"mo_hinh": "M0 HOG + hồi quy logistic", "C": C, "val_mnist_noi_bo": round(best[0], 4), "seed": SEED, "hog_dim": 324}
    do_mo_hinh(lambda x: m.predict(hog28(x)), "M0", ghi)
    (EVAL / "m0_buoc4.json").write_text(json.dumps(ghi, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Ghi {EVAL / 'm0_buoc4.json'}")


def _torch():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    return torch, nn, F


def tao_cnn():
    torch, nn, F = _torch()

    class CNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.c1, self.c2 = nn.Conv2d(1, 16, 3, padding=1), nn.Conv2d(16, 32, 3, padding=1)
            self.d1, self.d2 = nn.Linear(32 * 7 * 7, 64), nn.Linear(64, 10)
            self.drop = nn.Dropout(0.3)

        def forward(self, x):
            x = F.max_pool2d(F.relu(self.c1(x)), 2)
            x = F.max_pool2d(F.relu(self.c2(x)), 2)
            x = self.drop(x.flatten(1))
            return self.d2(F.relu(self.d1(x)))
    return CNN()


def tang_cuong(x, g):
    torch, _, F = _torch()
    n = x.shape[0]
    u = lambda lo, hi: lo + (hi - lo) * torch.rand(n, generator=g)
    th, s = u(-10, 10) * np.pi / 180, u(0.9, 1.1)
    tx, ty = u(-2, 2) / 14.0, u(-2, 2) / 14.0
    A = torch.stack([torch.stack([torch.cos(th) / s, -torch.sin(th) / s, tx], 1),
                     torch.stack([torch.sin(th) / s, torch.cos(th) / s, ty], 1)], 1)
    x = F.grid_sample(x, F.affine_grid(A, x.shape, align_corners=False), align_corners=False, padding_mode="zeros")
    r = torch.rand(n, generator=g).view(n, 1, 1, 1)
    xm = -F.max_pool2d(-x, 3, 1, 1)
    xd = F.max_pool2d(x, 3, 1, 1)
    x = torch.where(r < 0.3, xm, torch.where(r > 0.8, xd, x))
    x = x * u(0.5, 1.0).view(n, 1, 1, 1)
    x = x + 0.03 * torch.rand(x.shape, generator=g) * (torch.rand(n, 1, 1, 1, generator=g) < 0.5)
    return x.clamp(0, 1)


def huan_luyen_cnn(x, y, epochs, lr, seed, mo_hinh=None, aug=True, batch=128, tran="", dong_bang=(), aug_fn=None):
    torch, nn, F = _torch()
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    m = mo_hinh or tao_cnn()
    X = torch.from_numpy(np.array(x)).float().div(255.0).unsqueeze(1)
    Y = torch.from_numpy(y).long()
    for ten, pa in m.named_parameters():
        pa.requires_grad = not any(ten.startswith(f) for f in dong_bang)
    opt = torch.optim.Adam([pa for pa in m.parameters() if pa.requires_grad], lr=lr)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs * ((len(X) + batch - 1) // batch))
    for ep in range(epochs):
        m.train()
        pm = torch.randperm(len(X), generator=g)
        tong = 0.0
        for i in range(0, len(X), batch):
            ix = pm[i:i + batch]
            xb = (aug_fn or tang_cuong)(X[ix], g) if aug else X[ix]
            loss = F.cross_entropy(m(xb), Y[ix])
            opt.zero_grad()
            loss.backward()
            opt.step()
            sch.step()
            tong += loss.item() * len(ix)
        if tran:
            print(f"  {tran} epoch {ep + 1}/{epochs} loss {tong / len(X):.4f}")
    return m.eval()


def xac_suat(m, x, lo=1024):
    torch, _, F = _torch()
    out = []
    with torch.no_grad():
        for i in range(0, len(x), lo):
            xb = torch.from_numpy(np.array(x[i:i + lo])).float().div(255.0).unsqueeze(1)
            out.append(F.softmax(m(xb), dim=1).numpy())
    return np.concatenate(out) if out else np.zeros((0, 10), np.float32)


def logits(m, x, lo=1024):
    torch, _, _ = _torch()
    out = []
    with torch.no_grad():
        for i in range(0, len(x), lo):
            out.append(m(torch.from_numpy(np.array(x[i:i + lo])).float().div(255.0).unsqueeze(1)).numpy())
    return np.concatenate(out) if out else np.zeros((0, 10), np.float32)


def nap_m1():
    torch, _, _ = _torch()
    m = tao_cnn()
    m.load_state_dict(torch.load(OCR / "m1_mnist.pt"))
    return m.eval()


CAU_HINH_M2 = {"dense": dict(dong_bang=("c1", "c2"), lr=1e-3, epochs=6), "toan_bo": dict(dong_bang=(), lr=3e-4, epochs=6)}


def cmd_m2(a):
    import copy
    torch, _, _ = _torch()
    m1 = nap_m1()
    for nguon in NGUON:
        t = tap_do(nguon)
        ng_tr = np.array([int(r["nguoi"]) for r in t["trang"]["meta"]])
        ng_ph = np.array([int(r["nguoi"]) for r in t["phieu"]["meta"]])
        for kieu, cfg in CAU_HINH_M2.items():
            lt, lp = np.zeros((len(ng_tr), 10), np.float32), np.zeros((len(ng_ph), 10), np.float32)
            for nguoi in range(1, 6):
                t0 = time.time()
                tr = ng_tr != nguoi
                m = huan_luyen_cnn(t["trang"]["x"][tr], t["trang"]["y"][tr], cfg["epochs"], cfg["lr"], SEED, mo_hinh=copy.deepcopy(m1),
                                   batch=64, dong_bang=cfg["dong_bang"])
                lt[~tr] = logits(m, t["trang"]["x"][~tr])
                if (ng_ph == nguoi).any():
                    lp[ng_ph == nguoi] = logits(m, t["phieu"]["x"][ng_ph == nguoi])
                print(f"[M2 {kieu} {nguon}] bỏ người {nguoi}: train {int(tr.sum())} ô, đo {int((~tr).sum())} ô trang + "
                      f"{int((ng_ph == nguoi).sum())} ô phiếu ({time.time() - t0:.0f} s)")
            np.savez_compressed(OCR / f"oof_m2_{kieu}_{nguon}.npz", trang=lt, phieu=lp)
    print("Xong M2 OOF -> data/_ocr/oof_m2_*.npz")


def cmd_m1(a):
    torch, _, _ = _torch()
    EVAL.mkdir(parents=True, exist_ok=True)
    xtr, ytr, xte, yte = doc_mnist()
    pm = np.random.default_rng(SEED).permutation(len(xtr))
    va, tr = pm[:5000], pm[5000:]
    ghi = {"mo_hinh": "M1 CNN nhỏ (~106 k tham số) + augmentation, huấn luyện MNIST", "epochs": a.epochs, "lr": a.lr, "seeds": a.seeds,
           "torch": torch.__version__, "tham_so": int(sum(p.numel() for p in tao_cnn().parameters()))}
    mh = None
    for sd in a.seeds:
        t0 = time.time()
        m = huan_luyen_cnn(xtr[tr], ytr[tr], a.epochs, a.lr, sd, tran=f"seed {sd}")
        acc_va = float((xac_suat(m, xtr[va]).argmax(1) == ytr[va]).mean())
        print(f"[M1 seed {sd}] val MNIST nội bộ {acc_va:.4f} ({time.time() - t0:.0f} s)")
        ghi.setdefault("val_mnist_noi_bo", {})[str(sd)] = round(acc_va, 4)
        if sd == a.seeds[0]:
            mh = m
            torch.save(m.state_dict(), OCR / "m1_mnist.pt")
            do_mo_hinh(lambda x: xac_suat(m, x).argmax(1), f"M1 seed {sd}", ghi)
        else:
            ghi.setdefault("seed_phu", {})[str(sd)] = {}
            _, _, xte2, yte2 = doc_mnist()
            ghi["seed_phu"][str(sd)]["mnist_test"] = tom_tat(yte2, xac_suat(m, xte2).argmax(1))["acc"]
            for ten_tap, d in tap_do("anh_nan").items():
                ghi["seed_phu"][str(sd)][ten_tap] = tom_tat(d["y"], xac_suat(m, d["x"]).argmax(1))["acc"]
            print(f"  seed {sd} phụ: {ghi['seed_phu'][str(sd)]}")
    (EVAL / "m1_buoc5.json").write_text(json.dumps(ghi, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Ghi {EVAL / 'm1_buoc5.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["m0", "m1", "m2"])
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--seeds", type=int, nargs="+", default=[SEED, 1, 2])
    a = ap.parse_args()
    {"m0": cmd_m0, "m1": cmd_m1, "m2": cmd_m2}[a.lenh](a)
