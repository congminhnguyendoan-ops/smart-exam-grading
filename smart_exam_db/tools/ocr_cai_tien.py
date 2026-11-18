import argparse
import copy
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402
import ocr_do_luong as L  # noqa: E402
from cv_engine import ocr  # noqa: E402

CAP = H.OCR / "cap"
NGUON = "anh_nan"
SEEDS = (2026, 1, 2)
FT = dict(lr=3e-4, epochs=6, batch=64)
PRE = dict(lr=2e-3, epochs=10)


def kieu_la(x, y, rng):
    ox, oy = [], []
    for img, lab in zip(x, y):
        if lab not in (1, 7):
            continue
        im = img.copy()
        ys, xs = np.nonzero(im > 80)
        if len(ys) < 5:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        dam = int(rng.integers(1, 3))
        if lab == 1:
            xt = int(round(xs[ys == y0].mean()))
            dai, goc = rng.uniform(4, 9), np.deg2rad(rng.uniform(25, 70))
            cv2.line(im, (xt, int(y0)), (int(round(xt - dai * np.cos(goc))), int(round(y0 + dai * np.sin(goc)))), 255, dam, cv2.LINE_AA)
        else:
            yy = int(y0 + rng.uniform(0.5, 0.7) * (y1 - y0))
            hang = xs[ys == yy]
            xc = int(round(hang.mean())) if len(hang) else int((x0 + x1) // 2)
            nua = int(rng.integers(3, 7))
            cv2.line(im, (xc - nua, yy), (xc + nua, yy), 255, dam, cv2.LINE_AA)
        v = ocr.ve_mnist(im.astype(np.float32) / 255.0)
        if v is not None:
            ox.append(v)
            oy.append(lab)
    return np.stack(ox), np.array(oy)


def tang_cuong_v2(x, g):
    torch, _, F = H._torch()
    n = x.shape[0]
    u = lambda lo, hi: lo + (hi - lo) * torch.rand(n, generator=g)
    th, sx, sy, sh = u(-12, 12) * np.pi / 180, u(0.85, 1.15), u(0.85, 1.15), u(-0.25, 0.25)
    c, s = torch.cos(th), torch.sin(th)
    R = torch.stack([torch.stack([c, -s], 1), torch.stack([s, c], 1)], 1)
    S = torch.diag_embed(torch.stack([1 / sx, 1 / sy], 1))
    Sh = torch.stack([torch.stack([torch.ones(n), sh], 1), torch.stack([torch.zeros(n), torch.ones(n)], 1)], 1)
    A2 = R @ S @ Sh
    A = torch.cat([A2, torch.stack([u(-2.5, 2.5) / 14.0, u(-2.5, 2.5) / 14.0], 1).unsqueeze(2)], 2)
    x = F.grid_sample(x, F.affine_grid(A, x.shape, align_corners=False), align_corners=False, padding_mode="zeros")
    r = torch.rand(n, generator=g).view(n, 1, 1, 1)
    mong = -F.max_pool2d(-x, 3, 1, 1)
    day = F.max_pool2d(x, 3, 1, 1)
    rat_day = F.max_pool2d(day, 3, 1, 1)
    x = torch.where(r < 0.25, mong, torch.where(r < 0.5, x, torch.where(r < 0.8, day, rat_day)))
    nhoe = F.avg_pool2d(x, 3, 1, 1)
    x = torch.where(torch.rand(n, 1, 1, 1, generator=g) < 0.2, nhoe, x)
    x = x * u(0.4, 1.0).view(n, 1, 1, 1)
    x = x + 0.03 * torch.rand(x.shape, generator=g) * (torch.rand(n, 1, 1, 1, generator=g) < 0.5)
    return x.clamp(0, 1)


def du_lieu_truoc(nguon_truoc: str):
    xtr, ytr, _, _ = H.doc_mnist()
    pm = np.random.default_rng(H.SEED).permutation(len(xtr))
    tr = pm[5000:]
    x, y = xtr[tr], ytr[tr]
    if nguon_truoc.startswith("emnist"):
        xe, ye = doc_emnist()
        x, y = np.concatenate([x, xe]), np.concatenate([y, ye])
    if nguon_truoc.endswith("kieu"):
        kx, ky = kieu_la(x, y, np.random.default_rng(7))
        x, y = np.concatenate([x, kx]), np.concatenate([y, ky])
    return x, y


def doc_emnist():
    import gzip
    d = H.OCR / "nguon_emnist_hf"
    def idx(ten, anh):
        with gzip.open(d / ten, "rb") as f:
            b = f.read()
        if anh:
            n, h, w = (int.from_bytes(b[4 + 4 * i:8 + 4 * i], "big") for i in range(3))
            return np.frombuffer(b, np.uint8, offset=16).reshape(n, h, w)
        return np.frombuffer(b, np.uint8, offset=8)
    x = idx("emnist-digits-train-images-idx3-ubyte.gz", True)
    return np.ascontiguousarray(x.transpose(0, 2, 1)), idx("emnist-digits-train-labels-idx1-ubyte.gz", False).astype(np.int64)


def tien_huan_luyen(nguon_truoc: str, aug: str, seed: int):
    torch, _, _ = H._torch()
    f = CAP / f"pre_{nguon_truoc}_{aug}_{seed}.pt"
    if f.exists():
        m = H.tao_cnn()
        m.load_state_dict(torch.load(f))
        return m.eval()
    x, y = du_lieu_truoc(nguon_truoc)
    t0 = time.time()
    ep = PRE["epochs"] if not nguon_truoc.startswith("emnist") else 4
    m = H.huan_luyen_cnn(x, y, ep, PRE["lr"], seed, aug_fn=tang_cuong_v2 if aug == "v2" else None, tran=f"pre {nguon_truoc}/{aug}/{seed}")
    print(f"  tiền huấn luyện {nguon_truoc}/{aug}/seed {seed}: {len(x)} ảnh, {time.time() - t0:.0f} s")
    CAP.mkdir(parents=True, exist_ok=True)
    torch.save(m.state_dict(), f)
    return m


def oof(pre, ft_aug: str, seed: int, nguon=NGUON):
    t = H.tap_do(nguon)
    ng_tr = np.array([int(r["nguoi"]) for r in t["trang"]["meta"]])
    ng_ph = np.array([int(r["nguoi"]) for r in t["phieu"]["meta"]])
    lt, lp = np.zeros((len(ng_tr), 10), np.float32), np.zeros((len(ng_ph), 10), np.float32)
    for nguoi in range(1, 6):
        tr = ng_tr != nguoi
        m = H.huan_luyen_cnn(t["trang"]["x"][tr], t["trang"]["y"][tr], FT["epochs"], FT["lr"], seed, mo_hinh=copy.deepcopy(pre),
                             batch=FT["batch"], aug_fn=tang_cuong_v2 if ft_aug == "v2" else None)
        lt[~tr] = H.logits(m, t["trang"]["x"][~tr])
        if (ng_ph == nguoi).any():
            lp[ng_ph == nguoi] = H.logits(m, t["phieu"]["x"][ng_ph == nguoi])
    return lt, lp


CAU_HINH = {
    "g0_goc": ("mnist", "co_ban", "co_ban"),
    "a1_aug_manh_truoc": ("mnist", "v2", "co_ban"),
    "a2_aug_manh_kieu_la": ("mnist_kieu", "v2", "co_ban"),
    "a3_aug_manh_ca_hai": ("mnist_kieu", "v2", "v2"),
    "c1_emnist": ("emnist", "co_ban", "co_ban"),
    "c2_emnist_aug": ("emnist_kieu", "v2", "v2"),
}


def chay_cau_hinh(ten: str, seeds=SEEDS):
    CAP.mkdir(parents=True, exist_ok=True)
    nt, a_pre, a_ft = CAU_HINH[ten]
    for sd in seeds:
        f = CAP / f"oof_{ten}_{sd}.npz"
        if f.exists():
            continue
        t0 = time.time()
        pre = tien_huan_luyen(nt, a_pre, sd)
        lt, lp = oof(pre, a_ft, sd)
        np.savez_compressed(f, trang=lt, phieu=lp)
        print(f"[{ten} seed {sd}] OOF xong ({time.time() - t0:.0f} s)")


def doi_chieu_dev(p_ph, meta_p, omr, tau_khop=L.TAU_KHOP):
    cot = defaultdict(list)
    for i, r in enumerate(meta_p):
        o = omr[r["anh"]]
        b, bcx = (o[r["loai"]][int(r["vi_tri"])] if "tu_choi" not in o else ["?", True])
        cot[(r["anh"], r["loai"])].append((int(r["vi_tri"]), ocr.doi_chieu_cot(b, bcx, str(int(p_ph[i].argmax())), float(p_ph[i].max()), True,
                                                                              r["trong"] == "1", tau_khop), int(r["nhan"])))
    out = {}
    for k, v in cot.items():
        v.sort(key=lambda x: x[0])
        gt, chac, ly = ocr.doi_chieu_truong([x[1] for x in v], True)
        out[k] = (gt, chac, ly, gt == "".join(str(x[2]) for x in v))
    return out


def danh_gia(p_tr, p_ph, t, omr, tau_khop=L.TAU_KHOP):
    y_tr, yp, meta_p = t["trang"]["y"], t["phieu"]["y"], t["phieu"]["meta"]
    r = {"acc_trang": H.tom_tat(y_tr, p_tr.argmax(1))["acc"], "theo_nguoi_trang": {k: float(v["acc"]) for k, v in H.theo_nguoi(y_tr, p_tr.argmax(1), t["trang"]["meta"]).items()}}
    tp = H.tom_tat(yp, p_ph.argmax(1))
    r["acc_phieu"], r["acc_phieu_ci"], r["dung_phieu"], r["n_phieu"] = tp["acc"], tp["ci95"], tp["dung"], tp["n"]
    r["theo_nguoi_phieu"] = {k: float(v["acc"]) for k, v in H.theo_nguoi(yp, p_ph.argmax(1), meta_p).items()}
    r["theo_dk_phieu"] = {k: v["acc"] for k, v in H.theo_dieu_kien(yp, p_ph.argmax(1), meta_p).items()}
    ng = L.chon_nguong(p_tr, y_tr)
    r["tau_delta_T1"] = list(ng[1:]) if ng else None
    r["cx_chu_so_T1"] = round(ng[0], 4) if ng else None
    dc = doi_chieu_dev(p_ph, meta_p, omr, tau_khop)
    anhs = sorted({k[0] for k in dc})
    gan = {a: any(not dc[(a, lo)][1] for lo in ("sbd", "ma_de")) for a in anhs}
    r["T4_gan"], r["T4_anh"] = sum(gan.values()), len(anhs)
    r["T4"] = round(r["T4_gan"] / len(anhs), 4)
    r["T4_ci"] = [round(v, 4) for v in H.cp_ci(r["T4_gan"], len(anhs))]
    r["gan_theo_anh"] = {a: bool(v) for a, v in gan.items()}
    for lo in ("sbd", "ma_de"):
        ds = [v for (a, l), v in dc.items() if l == lo]
        chac = [v for v in ds if v[1]]
        r[lo] = {"n": len(ds), "chac": len(chac), "im_lang": sum(1 for v in chac if not v[3])}
        r[lo]["im_lang_anh"] = [a for (a, l), v in dc.items() if l == lo and v[1] and not v[3]]
        r[lo]["im_lang_cp_hi"] = round(H.cp_ci(r[lo]["im_lang"], len(chac) or 1)[1], 4)
    r["IL"] = r["sbd"]["im_lang"] + r["ma_de"]["im_lang"]
    return r


def xac_suat_hieu_chinh(ten: str, seeds, t):
    pt, pp, Ts = [], [], []
    for sd in seeds:
        z = np.load(CAP / f"oof_{ten}_{sd}.npz")
        T = L.chon_nhiet(z["trang"], t["trang"]["y"])
        pt.append(L.softmax(z["trang"] / T))
        pp.append(L.softmax(z["phieu"] / T))
        Ts.append(round(T, 2))
    return np.mean(pt, 0), np.mean(pp, 0), Ts


def cmd_bang(a):
    from scipy.stats import binomtest
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    t = H.tap_do(NGUON)
    kq = {}
    for ten in CAU_HINH:
        if not all((CAP / f"oof_{ten}_{sd}.npz").exists() for sd in SEEDS):
            continue
        for che_do, seeds in (("1seed", SEEDS[:1]), ("3seed_tb_seed_don", None), ("ensemble3", SEEDS)):
            if che_do == "3seed_tb_seed_don":
                rs = [danh_gia(*xac_suat_hieu_chinh(ten, (sd,), t)[:2], t, omr) for sd in SEEDS]
                kq[f"{ten}|seed_don"] = {"acc_phieu_3seed": [x["acc_phieu"] for x in rs], "T4_3seed": [x["T4"] for x in rs], "IL_3seed": [x["IL"] for x in rs],
                                         "acc_trang_3seed": [x["acc_trang"] for x in rs]}
                continue
            pt, pp, Ts = xac_suat_hieu_chinh(ten, seeds, t)
            r = danh_gia(pt, pp, t, omr)
            r["T"] = Ts
            kq[f"{ten}|{che_do}"] = r
    print(f"{'cấu hình':34s} {'trang':>6s} {'phiếu T3 [CI]':>24s} {'T4 [CI]':>20s} {'IL':>3s} {'SBD IL':>6s} {'MĐ IL':>5s}  theo người trang")
    for k, r in kq.items():
        if "acc_phieu_3seed" in r:
            print(f"{k:34s} 3 seed: trang {np.round(r['acc_trang_3seed'], 3).tolist()} phiếu {np.round(r['acc_phieu_3seed'], 3).tolist()} T4 {r['T4_3seed']} IL {r['IL_3seed']}")
            continue
        print(f"{k:34s} {r['acc_trang']:6.3f} {r['acc_phieu']:6.3f} [{r['acc_phieu_ci'][0]:.3f}-{r['acc_phieu_ci'][1]:.3f}] "
              f"{r['T4']:6.3f} [{r['T4_ci'][0]:.2f}-{r['T4_ci'][1]:.2f}] {r['IL']:3d} {r['sbd']['im_lang']:6d} {r['ma_de']['im_lang']:5d}  {r['theo_nguoi_trang']}")
    def dau(a_, b_):
        ga, gb = kq[a_]["gan_theo_anh"], kq[b_]["gan_theo_anh"]
        gk = [x for x in ga if ga[x] != gb[x]]
        k = sum(1 for x in gk if gb[x] and not ga[x])
        return len(gk), k, (binomtest(k, len(gk), 0.5).pvalue if gk else 1.0)
    print("\nKiểm định dấu cặp theo ảnh (A ít gắn hơn B?):")
    for che_do in ("1seed", "ensemble3"):
        base = f"g0_goc|{che_do}"
        if base not in kq:
            continue
        for k in kq:
            if k.endswith(che_do) and k != base:
                n, kb, p = dau(k, base)
                print(f"  {k:34s} vs {base}: ảnh khác nhau {n}, cấu hình này ít gắn hơn ở {kb}/{n} ảnh; p = {p:.3f}")
    (H.EVAL / "thu_nghiem_buoc2.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nGhi {H.EVAL / 'thu_nghiem_buoc2.json'}")


def cmd_luat_mem(a):
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    t = H.tap_do(NGUON)
    _, pp, _ = xac_suat_hieu_chinh(a.cau_hinh[0], tuple(a.seeds), t)
    meta = t["phieu"]["meta"]
    cot = defaultdict(list)
    for i, r in enumerate(meta):
        o = omr[r["anh"]]
        b, bcx = (o[r["loai"]][int(r["vi_tri"])] if "tu_choi" not in o else ["?", True])
        cot[(r["anh"], r["loai"])].append((int(r["vi_tri"]), b, bcx, pp[i], int(r["nhan"])))
    kq = {}
    for tm in (None, 0.5, 0.3, 0.2, 0.1, 0.05, 0.02):
        nhan_ds, sai_ds, mo_phong, so_mp, anh_gan = 0, 0, 0, 0, set()
        anh_all = set()
        for (anh, lo), v in cot.items():
            v.sort(key=lambda x: x[0])
            anh_all.add(anh)
            if tm is None:
                ok = [b != "?" and not bcx and int(p.argmax()) == int(b) and p.max() >= L.TAU_KHOP for _, b, bcx, p, _ in v]
                chap = lambda p, w: int(p.argmax()) == w and p.max() >= L.TAU_KHOP
            else:
                ok = [b != "?" and not bcx and p[int(b)] >= tm for _, b, bcx, p, _ in v]
                chap = lambda p, w, tm=tm: p[w] >= tm
            if all(ok):
                nhan_ds += 1
                sai_ds += "".join(b for _, b, _, _, _ in v) != "".join(str(n) for *_, n in v)
            else:
                anh_gan.add(anh)
            for j, (_, b, bcx, p, _) in enumerate(v):
                if not all(ok[:j] + ok[j + 1:]):
                    continue
                for w in range(10):
                    if b == "?" or w == int(b):
                        continue
                    so_mp += 1
                    mo_phong += bool(chap(p, w))
        kq["hien_hanh" if tm is None else f"mem_{tm}"] = {
            "truong_nhan": nhan_ds, "truong": len(cot), "loi_im_lang_that": int(sai_ds), "anh_gan_T4": round(len(anh_gan) / len(anh_all), 4),
            "mo_phong_bubble_sai_nhan_nham": mo_phong, "mo_phong_tong": so_mp,
            "ti_le_nhan_nham_mo_phong": round(mo_phong / so_mp, 4) if so_mp else None}
    print(f"{'luật':14s} {'trường nhận':>12s} {'IL thật':>8s} {'T4(ảnh gắn)':>12s}   mô phỏng 1 cột bubble SAI: bị nhận nhầm")
    for k, r in kq.items():
        print(f"{k:14s} {r['truong_nhan']:>6d}/{r['truong']:<5d} {r['loi_im_lang_that']:>8d} {r['anh_gan_T4']:>12.3f}   "
              f"{r['mo_phong_bubble_sai_nhan_nham']}/{r['mo_phong_tong']} = {r['ti_le_nhan_nham_mo_phong']:.4f}")
    (H.EVAL / "luat_mem_de_xuat.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_chay(a):
    for ten in (a.cau_hinh or CAU_HINH):
        if ten.startswith("c") and not (H.OCR / "nguon_emnist_hf" / "tai.done").exists():
            print(f"BỎ {ten}: chưa tải xong EMNIST (data/_ocr/nguon_emnist_hf)")
            continue
        chay_cau_hinh(ten)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["chay", "bang", "luat-mem"])
    ap.add_argument("--cau-hinh", nargs="*")
    ap.add_argument("--seeds", type=int, nargs="+", default=[2026])
    a = ap.parse_args()
    if a.lenh == "luat-mem" and not a.cau_hinh:
        a.cau_hinh = ["g0_goc"]
    {"chay": cmd_chay, "bang": cmd_bang, "luat-mem": cmd_luat_mem}[a.lenh](a)
