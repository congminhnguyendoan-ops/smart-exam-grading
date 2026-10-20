"""
omr_cnn.py - Tuần 5 PHẦN B3: so sánh M1 (logistic trên 9 đặc trưng) với M2 = CNN nhỏ trên ẢNH Ô (môn máy học: so sánh trung thực).
CHỈ để huấn luyện / so sánh (cần torch). Chỉ 56 ảnh train 0001–0028, cùng 7 fold theo phiếu (data/split.csv), cùng luật câu
(trong_min 0,90, to_min 0,50, ro_min chọn THEO TỪNG ĐIỀU KIỆN trong nested CV – omr_c2.chon_ro_min_dk), cùng đo.

Chốt trước khi chạy:
  - đầu vào CNN: ô đáp án cắt 3r × 3r quanh tâm (vị trí omr.dinh_vi), chia mức giấy vành (như đặc trưng M1), co về 32×32;
  - kiến trúc: Conv12(3×3)-pool-Conv24(3×3)-pool-Dense32-Dense3 (~52 k tham số), CE có trọng số cân bằng lớp, Adam 2e-3 cosine, 14 epoch,
    tăng cường: dịch ±2 px, nhân sáng 0,9–1,1; seed 2026; KHÔNG chọn epoch / siêu tham số bằng dữ liệu;
  - so với M1 bằng: F1 faint theo C1–C4 + CI ghép cặp (bootstrap theo phiếu), nested: lỗi nặng / nhẹ / cần xem thừa theo điều kiện;
  - quy tắc: M2 chỉ thay M1 nếu đạt tiêu chí B2 (nặng 0; thừa ≤ 3% mọi điều kiện) VÀ tốt hơn M1 NGOÀI CI ghép cặp (maximin F1 faint
    hoặc thừa gộp); hoà -> giữ M1. Không bắt buộc thắng.

  python tools/omr_cnn.py cat         # cắt ô -> data/_omr/cnn_o.npz (56 ảnh × 160 ô)
  python tools/omr_cnn.py so-sanh     # nested 7×(6+1) lần huấn luyện -> data/_eval/omr/b3_cnn.json + .md
"""
import json
import sys
import time
import warnings
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_omr as H  # noqa: E402
import omr_c2 as C  # noqa: E402
import omr_long as N  # noqa: E402
from cv_engine import omr  # noqa: E402
from cv_engine.preprocessing import nap_layout  # noqa: E402
from omr_du_lieu import anh_da_nan, ds_anh  # noqa: E402

OUT = ROOT / "data" / "_eval" / "omr"
NPZ = H.OMR_DIR / "cnn_o.npz"
DK = H.DIEU_KIEN
SEED = 2026
CO = 32
EPOCHS = 14
warnings.filterwarnings("ignore")


def cmd_cat():
    L = nap_layout("phieu")
    mau = omr.nap_mau()
    ans = L["answers"]
    r = ans["bubble_radius"]
    X, meta = [], []
    for row in ds_anh("train"):
        nan, _ = anh_da_nan(row["anh"], L)
        dv = omr.dinh_vi(nan, L, mau)
        if any(dv.co.values()):
            raise SystemExit(f"{row['anh']}: định vị có cờ")
        for q in range(1, ans["num_questions"] + 1):
            dx, dy = dv.dich[f"q{q}"]
            for o in ans["options"]:
                cx, cy = ans["centers"][str(q)][o]
                cx, cy = cx + dx, cy + dy
                x0, y0 = int(round(cx - 1.5 * r)), int(round(cy - 1.5 * r))
                n = int(round(3 * r)) + 1
                patch = omr._cat(nan, x0, y0, x0 + n, y0 + n).astype(np.float32)
                yy, xx = np.ogrid[:n, :n]
                d2 = (xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2
                giay = max(float(np.median(patch[(d2 >= (1.15 * r) ** 2) & (d2 <= (1.45 * r) ** 2)])), 1.0)
                X.append(cv2.resize(np.clip(patch / giay, 0, 1.2), (CO, CO), interpolation=cv2.INTER_AREA))
                meta.append((row["anh"], f"q{q}", o))
        print(row["anh"], end=" ", flush=True)
    np.savez_compressed(NPZ, x=np.array(X, np.float32), anh=np.array([m[0] for m in meta]), pt=np.array([m[1] for m in meta]),
                        o=np.array([m[2] for m in meta]))
    print(f"\n-> {NPZ} ({len(X)} ô)")


def tao_mang():
    import torch.nn as nn

    class Mang(nn.Module):
        def __init__(self):
            super().__init__()
            self.c1, self.c2 = nn.Conv2d(1, 12, 3, padding=1), nn.Conv2d(12, 24, 3, padding=1)
            self.f1, self.f2 = nn.Linear(24 * 8 * 8, 32), nn.Linear(32, 3)
            self.drop = nn.Dropout(0.3)

        def forward(self, x):
            import torch.nn.functional as F
            x = F.max_pool2d(F.relu(self.c1(x)), 2)
            x = F.max_pool2d(F.relu(self.c2(x)), 2)
            return self.f2(F.relu(self.f1(self.drop(x.flatten(1)))))
    return Mang()


def huan_luyen(x, y, seed=SEED):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    m = tao_mang()
    X = torch.from_numpy(x).unsqueeze(1)
    Y = torch.from_numpy(y).long()
    w = torch.tensor(len(y) / (3 * np.maximum(np.bincount(y, minlength=3), 1)), dtype=torch.float32)
    opt = torch.optim.Adam(m.parameters(), lr=2e-3)
    batch = 128
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS * ((len(X) + batch - 1) // batch))
    for _ in range(EPOCHS):
        m.train()
        pm = torch.randperm(len(X), generator=g)
        for i in range(0, len(X), batch):
            ix = pm[i:i + batch]
            xb = X[ix]
            n = len(ix)
            th = torch.zeros(n, 2, 3)
            th[:, 0, 0] = th[:, 1, 1] = 1
            th[:, :, 2] = (torch.rand(n, 2, generator=g) * 2 - 1) * (2 / (CO / 2))        # dịch ±2 px
            xb = F.grid_sample(xb, F.affine_grid(th, xb.shape, align_corners=False), align_corners=False, padding_mode="border")
            xb = xb * (0.9 + 0.2 * torch.rand(n, 1, 1, 1, generator=g))
            loss = F.cross_entropy(m(xb), Y[ix], weight=w)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sch.step()
    return m.eval()


def du_doan(m, x):
    import torch
    with torch.no_grad():
        return torch.softmax(m(torch.from_numpy(x).unsqueeze(1)), dim=1).numpy()


def cmd_so_sanh():
    sel = [r for r in H.doc_dac_trung("nan") if r["loai"] == "cau"]
    z = np.load(NPZ)
    assert all(r["anh"] == a and r["phan_tu"] == p and r["o"] == o for r, a, p, o in zip(sel, z["anh"], z["pt"], z["o"])), "lệch thứ tự ô"
    Xc = z["x"]
    Xf = H.ma_tran(sel)
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
    for ten in ("m1", "cnn"):
        def fp(tr, te):
            if ten == "m1":
                m = C.tao("m1").fit(Xf[tr], y[tr])
                return m.predict_proba(Xf[te])
            return du_doan(huan_luyen(Xc[tr], y[tr]), Xc[te])
        ngoai = {k: dict(cau=0, ro_that=0, nang=0, nhe=0, thua=0, can_xem=0) for k in DK}
        P_oof = np.zeros((len(sel), 3))
        chon = {}
        t0 = time.time()
        for k in range(1, 8):
            con = [f for f in range(1, 8) if f != k]
            P_trong = np.zeros((len(sel), 3))
            for j in con:
                P_trong[fold == j] = fp(np.isin(fold, [f for f in con if f != j]), fold == j)
            ii = np.flatnonzero(np.isin(fold, con))
            ro = C.chon_ro_min_dk([sel[i] for i in ii], P_trong[ii], luat0)
            chon[k] = ro
            te = fold == k
            P_oof[te] = fp(np.isin(fold, con), te)
            jj = np.flatnonzero(te)
            d = N.dem_cau([sel[i] for i in jj], P_oof[jj], {**luat0, "ro_min": ro})
            for dk in DK:
                for kk in ngoai[dk]:
                    ngoai[dk][kk] += d[dk][kk]
            print(f"[{ten}] fold ngoài {k}: ro_min {ro} ({time.time() - t0:.0f} s)", flush=True)
        d_arg = P_oof.argmax(1)
        f1 = C.f1_faint_dk(sel, y, d_arg)
        bs = {}
        for c in DK:
            s = dkv == c
            bs[c] = np.array([H.f1_lop(y[np.concatenate([idx_phieu[p][s[idx_phieu[p]]] for p in rr])],
                                       d_arg[np.concatenate([idx_phieu[p][s[idx_phieu[p]]] for p in rr])], 1) for rr in rut])
        boot[ten] = bs
        ket[ten] = {"ro_min_theo_fold": chon, "nested_theo_dk": ngoai, "nested_tong": N.tong(ngoai), "f1_faint": f1,
                    "nham_trong_co_to": int(((y == 0) & (d_arg > 0)).sum() + ((y > 0) & (d_arg == 0)).sum()),
                    "cm": np.bincount(3 * y + d_arg, minlength=9).reshape(3, 3).tolist()}
    # CI ghép cặp của hiệu (cnn − m1)
    diff = {c: boot["cnn"][c] - boot["m1"][c] for c in DK}
    mm = {t: np.nanmin(np.vstack([boot[t][c] for c in DK]), axis=0) for t in boot}
    d_mm = mm["cnn"] - mm["m1"]
    ci = {c: np.nanpercentile(diff[c], [2.5, 97.5]).tolist() for c in DK}
    ci_mm = np.nanpercentile(d_mm, [2.5, 97.5]).tolist()
    L = ["# B3 – M1 (logistic 9 đặc trưng) vs M2 (CNN nhỏ trên ảnh ô 32×32), nested CV 7 fold, 56 ảnh train", "",
         "| | lỗi nặng | lỗi nhẹ | thừa gộp | thừa C1 / C2 / C3 / C4 | F1 faint C1 / C2 / C3 / C4 | maximin F1 | ô nhầm trống↔có tô |", "|---|---|---|---|---|---|---|---|"]
    for t in ("m1", "cnn"):
        r = ket[t]
        n = r["nested_tong"]
        th = {c: r["nested_theo_dk"][c]["thua"] / r["nested_theo_dk"][c]["ro_that"] for c in DK}
        L.append(f"| {'M1 logistic' if t == 'm1' else 'M2 CNN'} | {n['nang']} | {n['nhe']} | {100 * n['thua'] / n['ro_that']:.2f}% | "
                 + " / ".join(f"{100 * th[c]:.2f}" for c in DK) + " | " + " / ".join(f"{r['f1_faint'][c]:.3f}" for c in DK)
                 + f" | {min(r['f1_faint'].values()):.3f} | {r['nham_trong_co_to']} |")
    L += ["", "Hiệu F1 faint (CNN − M1), CI 95% ghép cặp (bootstrap theo phiếu): " + "; ".join(f"{c} {np.mean(diff[c]):+.3f} [{ci[c][0]:+.3f}; {ci[c][1]:+.3f}]" for c in DK)
          + f"; maximin {np.mean(d_mm):+.3f} [{ci_mm[0]:+.3f}; {ci_mm[1]:+.3f}]"]
    thua_cnn = {c: ket["cnn"]["nested_theo_dk"][c]["thua"] / ket["cnn"]["nested_theo_dk"][c]["ro_that"] for c in DK}
    dat = ket["cnn"]["nested_tong"]["nang"] == 0 and all(v <= 0.03 for v in thua_cnn.values())
    tot_hon = ci_mm[0] > 0
    kem_hon = ci_mm[1] < 0
    ket_luan = ("M2 đạt tiêu chí và tốt hơn M1 ngoài CI -> THAY" if dat and tot_hon else
                "M2 KÉM hơn M1 ngoài CI (maximin F1 faint) -> GIỮ M1" if kem_hon else
                "HOÀ / không tốt hơn ngoài CI hoặc không đạt tiêu chí -> GIỮ M1")
    L += ["", f"M2 đạt tiêu chí B2 (nặng 0, thừa ≤ 3% mọi điều kiện): {'có' if dat else 'KHÔNG'}; tốt hơn M1 ngoài CI (maximin): {'có' if tot_hon else 'không'}.",
          f"**Kết luận: {ket_luan}.**"]
    (OUT / "b3_cnn.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / "b3_cnn.json").write_text(json.dumps({"ket": ket, "hieu_f1_ci": ci, "hieu_maximin_ci": ci_mm, "dat": dat, "tot_hon": tot_hon,
                                                 "ket_luan": ket_luan}, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    {"cat": cmd_cat, "so-sanh": cmd_so_sanh}[sys.argv[1]]()
