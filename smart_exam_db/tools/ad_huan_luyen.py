import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402
import ocr_cai_tien as C  # noqa: E402
import ocr_do_luong as L  # noqa: E402
from cv_engine import ocr  # noqa: E402

AD = ROOT / "data" / "_eval" / "ad"
TAM = AD / "tam"
OOF = AD / "oof"
SEEDS = (2026, 1, 2)
CAU_HINH = ("baseline", "ad1")
PRE_AD1 = dict(lr=2e-3, epochs=4)
TAU_KHOP = L.TAU_KHOP


def du_lieu_ad1():
    x, y = C.du_lieu_truoc("mnist")
    e = np.load(ROOT / "data" / "nguon_ngoai" / "emnist_digits.npz")
    g = np.load(AD / "o_gia.npz")
    print(f"  ad1: MNIST {len(x)} + EMNIST {len(e['y_train'])} + ô giả {len(g['y'])}")
    return (np.concatenate([x, e["x_train_chuan"], g["x"]]),
            np.concatenate([y.astype(np.int64), e["y_train"].astype(np.int64), g["y"].astype(np.int64)]))


def tien_huan_luyen(ten: str, seed: int, nhat_ky: dict):
    torch, _, _ = H._torch()
    TAM.mkdir(parents=True, exist_ok=True)
    f = TAM / f"pre_{ten}_{seed}.pt"
    if f.exists():
        m = H.tao_cnn()
        m.load_state_dict(torch.load(f))
        return m.eval()
    t0 = time.time()
    if ten == "baseline":
        cu = C.CAP / f"pre_mnist_co_ban_{seed}.pt"
        if seed == 2026:
            x, y = C.du_lieu_truoc("mnist")
            m = H.huan_luyen_cnn(x, y, C.PRE["epochs"], C.PRE["lr"], seed, tran=f"pre baseline/{seed}")
            if cu.exists():
                sd_cu = torch.load(cu)
                chenh = max(float((v - sd_cu[k]).abs().max()) for k, v in m.state_dict().items())
                nhat_ky[f"pre_baseline_{seed}_chenh_trong_so_so_voi_tuan6"] = chenh
                print(f"  baseline seed {seed}: chênh trọng số lớn nhất so với bộ đệm Tuần 6 = {chenh:.3g}")
        else:
            m = H.tao_cnn()
            m.load_state_dict(torch.load(cu))
            m.eval()
            nhat_ky[f"pre_baseline_{seed}"] = f"bộ đệm Tuần 6 {cu.name}"
    else:
        x, y = du_lieu_ad1()
        m = H.huan_luyen_cnn(x, y, PRE_AD1["epochs"], PRE_AD1["lr"], seed, tran=f"pre ad1/{seed}")
    nhat_ky[f"pre_{ten}_{seed}_giay"] = round(time.time() - t0)
    torch.save(m.state_dict(), f)
    return m


def cmd_chay(a):
    OOF.mkdir(parents=True, exist_ok=True)
    nk_f = AD / "nhat_ky_chay.json"
    nk = json.loads(nk_f.read_text(encoding="utf-8")) if nk_f.exists() else {}
    for ten in a.cau_hinh:
        for sd in a.seeds:
            f = OOF / f"oof_{ten}_{sd}.npz"
            if f.exists():
                print(f"  đã có {f.name}")
                continue
            t0 = time.time()
            pre = tien_huan_luyen(ten, sd, nk)
            lt, lp = C.oof(pre, "co_ban", sd)
            np.savez_compressed(f, trang=lt, phieu=lp)
            if ten == "baseline":
                cu = C.CAP / f"oof_g0_goc_{sd}.npz"
                if cu.exists():
                    z = np.load(cu)
                    ch = max(float(np.abs(z["trang"] - lt).max()), float(np.abs(z["phieu"] - lp).max()))
                    nk[f"oof_baseline_{sd}_chenh_logit_so_voi_tuan6"] = ch
                    print(f"  baseline seed {sd}: chênh logit OOF lớn nhất so với Tuần 6 = {ch:.3g}")
            print(f"[{ten} seed {sd}] OOF xong ({time.time() - t0:.0f} s)")
            nk_f.write_text(json.dumps(nk, ensure_ascii=False, indent=1), encoding="utf-8")


def xac_suat(ten, sd, t):
    z = np.load(OOF / f"oof_{ten}_{sd}.npz")
    T = L.chon_nhiet(z["trang"], t["trang"]["y"])
    return L.softmax(z["trang"] / T), L.softmax(z["phieu"] / T), T


def so_do(p_tr, p_ph, t, omr) -> dict:
    y_tr, meta_tr = t["trang"]["y"], t["trang"]["meta"]
    y_ph, meta_ph = t["phieu"]["y"], t["phieu"]["meta"]
    ng_tr = np.array([int(r["nguoi"]) for r in meta_tr])
    co_muc = np.array([r["trong"] != "1" for r in meta_ph])
    a_tr, a_ph = p_tr.argmax(1), p_ph.argmax(1)
    r = {"theo_nguoi_trang": {str(k): float((a_tr[ng_tr == k] == y_tr[ng_tr == k]).mean()) for k in range(1, 6)}}
    r["tc1_macro_trang"] = float(np.mean(list(r["theo_nguoi_trang"].values())))
    r["acc_trang_micro"] = float((a_tr == y_tr).mean())
    r["acc_phieu"] = float((a_ph == y_ph).mean())
    r["acc_phieu_co_muc"] = float((a_ph[co_muc] == y_ph[co_muc]).mean())
    ng_ph = np.array([int(m["nguoi"]) for m in meta_ph])
    r["theo_nguoi_phieu"] = {str(k): float((a_ph[ng_ph == k] == y_ph[ng_ph == k]).mean()) for k in range(1, 6) if (ng_ph == k).any()}
    sai_tt_tr = (a_tr != y_tr) & (p_tr.max(1) >= TAU_KHOP)
    sai_tt_ph = (a_ph != y_ph) & (p_ph.max(1) >= TAU_KHOP) & co_muc
    r["tc2_sai_tu_tin"] = int(sai_tt_tr.sum() + sai_tt_ph.sum())
    r["sai_tu_tin_trang"], r["sai_tu_tin_phieu"] = int(sai_tt_tr.sum()), int(sai_tt_ph.sum())
    r["sai_tong"] = int((a_tr != y_tr).sum() + ((a_ph != y_ph) & co_muc).sum())
    cx = []
    for i, m in enumerate(meta_ph):
        o = omr[m["anh"]]
        b, bcx = (o[m["loai"]][int(m["vi_tri"])] if "tu_choi" not in o else ["?", True])
        c = ocr.doi_chieu_cot(b, bcx, str(int(a_ph[i])), float(p_ph[i].max()), True, m["trong"] == "1", TAU_KHOP)
        cx.append(not c.chac)
    r["tc3_cot_can_xem"] = float(np.mean(cx))
    r["cot_can_xem_n"], r["cot_n"] = int(np.sum(cx)), len(cx)
    d = C.danh_gia(p_tr, p_ph, t, omr)
    r["T4_anh_can_xem"], r["T4_gan"], r["T4_anh"], r["loi_im_lang_truong"] = d["T4"], d["T4_gan"], d["T4_anh"], d["IL"]
    cm = np.zeros((10, 10), int)
    for yy, pp in zip(np.concatenate([y_tr, y_ph[co_muc]]), np.concatenate([a_tr, a_ph[co_muc]])):
        cm[yy, pp] += 1
    r["confusion"] = cm.tolist()
    r["dung_tung_o"] = np.concatenate([a_tr == y_tr, (a_ph == y_ph)[co_muc]]).tolist()
    return r


def cmd_bang(a):
    from scipy.stats import binomtest
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    t = H.tap_do(C.NGUON)
    kq = {"tieu_chi": "docs/lenh_ad.md Bước 3 (commit 5af47ab)", "seeds": list(SEEDS), "theo_seed": {}, "tb": {}}
    for ten in CAU_HINH:
        rs = []
        for sd in SEEDS:
            p_tr, p_ph, T = xac_suat(ten, sd, t)
            r = so_do(p_tr, p_ph, t, omr)
            r["T"] = round(T, 2)
            kq["theo_seed"][f"{ten}|{sd}"] = r
            rs.append(r)
        tb = {k: float(np.mean([r[k] for r in rs])) for k in ("tc1_macro_trang", "acc_trang_micro", "acc_phieu", "acc_phieu_co_muc",
                                                               "tc3_cot_can_xem", "T4_anh_can_xem")}
        tb["tc2_sai_tu_tin_cong3"] = int(sum(r["tc2_sai_tu_tin"] for r in rs))
        tb["sai_tong_cong3"] = int(sum(r["sai_tong"] for r in rs))
        tb["loi_im_lang_truong_cong3"] = int(sum(r["loi_im_lang_truong"] for r in rs))
        tb["theo_nguoi_trang"] = {k: float(np.mean([r["theo_nguoi_trang"][k] for r in rs])) for k in rs[0]["theo_nguoi_trang"]}
        tb["theo_nguoi_phieu"] = {k: float(np.mean([r["theo_nguoi_phieu"][k] for r in rs])) for k in rs[0]["theo_nguoi_phieu"]}
        cm = np.sum([np.array(r["confusion"]) for r in rs], axis=0)
        tb["confusion_cong3"] = cm.tolist()
        tb["cap_nham"] = {f"{i}<->{j}": [int(cm[i, j]), int(cm[j, i])] for i, j in ((8, 6), (1, 7), (0, 6), (4, 9), (3, 5), (2, 7))}
        kq["tb"][ten] = tb
    b, u = kq["tb"]["baseline"], kq["tb"]["ad1"]
    d1 = 100 * (u["tc1_macro_trang"] - b["tc1_macro_trang"])
    dat1, dat2, dat3 = d1 >= 1.0, u["tc2_sai_tu_tin_cong3"] <= b["tc2_sai_tu_tin_cong3"], u["tc3_cot_can_xem"] <= b["tc3_cot_can_xem"] + 1e-12
    kq["ket_luan"] = {"tc1_chenh_diem": round(d1, 3), "tc1_dat": dat1, "tc2_dat": dat2, "tc3_dat": dat3, "dat_ca_ba": dat1 and dat2 and dat3}
    bd = np.concatenate([kq["theo_seed"][f"baseline|{s}"]["dung_tung_o"] for s in SEEDS])
    ud = np.concatenate([kq["theo_seed"][f"ad1|{s}"]["dung_tung_o"] for s in SEEDS])
    n10, n01 = int((bd & ~ud).sum()), int((~bd & ud).sum())
    kq["ket_luan"]["cap_o_baseline_dung_ad1_sai"], kq["ket_luan"]["cap_o_ad1_dung_baseline_sai"] = n10, n01
    kq["ket_luan"]["p_dau"] = float(binomtest(n01, n10 + n01, 0.5).pvalue) if n10 + n01 else 1.0
    for v in kq["theo_seed"].values():
        v.pop("dung_tung_o")
    AD.mkdir(parents=True, exist_ok=True)
    (AD / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    dong = ["| Số đo | baseline | ad1 | Tiêu chí |", "|---|---|---|---|",
            f"| (1) Độ đúng trang D, macro 5 người, TB 3 seed | {100 * b['tc1_macro_trang']:.2f}% | {100 * u['tc1_macro_trang']:.2f}% | "
            f"chênh {d1:+.2f} điểm, cần ≥ +1,00 → {'ĐẠT' if dat1 else 'KHÔNG ĐẠT'} |",
            f"| (2) Sai mà tự tin (p ≥ 0,5), cộng 3 seed | {b['tc2_sai_tu_tin_cong3']} | {u['tc2_sai_tu_tin_cong3']} | ≤ baseline → {'ĐẠT' if dat2 else 'KHÔNG ĐẠT'} |",
            f"| (3) Cột SBD / mã đề cần xem, TB 3 seed | {100 * b['tc3_cot_can_xem']:.2f}% | {100 * u['tc3_cot_can_xem']:.2f}% | ≤ baseline → {'ĐẠT' if dat3 else 'KHÔNG ĐẠT'} |",
            f"| Độ đúng trang D (micro) | {100 * b['acc_trang_micro']:.2f}% | {100 * u['acc_trang_micro']:.2f}% | phụ |",
            f"| Độ đúng ô phiếu dev có mực | {100 * b['acc_phieu_co_muc']:.2f}% | {100 * u['acc_phieu_co_muc']:.2f}% | phụ |",
            f"| Ảnh có SBD / mã đề cần xem (T4) | {100 * b['T4_anh_can_xem']:.1f}% | {100 * u['T4_anh_can_xem']:.1f}% | phụ |",
            f"| Lỗi im lặng mức trường (cộng 3 seed) | {b['loi_im_lang_truong_cong3']} | {u['loi_im_lang_truong_cong3']} | phải 0 |",
            f"| Tổng chữ số sai (cộng 3 seed) | {b['sai_tong_cong3']} | {u['sai_tong_cong3']} | phụ |"]
    for k in b["theo_nguoi_trang"]:
        dong.append(f"| Trang D người {k} (TB 3 seed) | {100 * b['theo_nguoi_trang'][k]:.2f}% | {100 * u['theo_nguoi_trang'][k]:.2f}% | phụ |")
    for k in b["cap_nham"]:
        dong.append(f"| Nhầm {k} (thật→đoán, hai chiều, cộng 3 seed) | {b['cap_nham'][k]} | {u['cap_nham'][k]} | phụ |")
    for sd in SEEDS:
        bs, us = kq["theo_seed"][f"baseline|{sd}"], kq["theo_seed"][f"ad1|{sd}"]
        dong.append(f"| seed {sd}: (1) / (2) / (3) / T4 | {100 * bs['tc1_macro_trang']:.2f}% / {bs['tc2_sai_tu_tin']} / {100 * bs['tc3_cot_can_xem']:.2f}% / "
                    f"{100 * bs['T4_anh_can_xem']:.1f}% | {100 * us['tc1_macro_trang']:.2f}% / {us['tc2_sai_tu_tin']} / {100 * us['tc3_cot_can_xem']:.2f}% / "
                    f"{100 * us['T4_anh_can_xem']:.1f}% | phụ |")
    kl = kq["ket_luan"]
    dong += ["", f"Kiểm định dấu cặp theo ô (cộng 3 seed): baseline đúng / ad1 sai {kl['cap_o_baseline_dung_ad1_sai']}, "
                 f"ad1 đúng / baseline sai {kl['cap_o_ad1_dung_baseline_sai']}, p = {kl['p_dau']:.3f}",
             "", f"**KẾT LUẬN: {'ĐẠT cả 3 tiêu chí – đề nghị xem xét thay' if kl['dat_ca_ba'] else 'KHÔNG ĐẠT, giữ mô hình cũ'}**"]
    (AD / "ket_qua.md").write_text("\n".join(dong) + "\n", encoding="utf-8")
    print("\n".join(dong))


def cmd_xuat(a):
    import xuat_ocr as X
    kq = json.loads((AD / "ket_qua.json").read_text(encoding="utf-8"))
    if not kq["ket_luan"]["dat_ca_ba"]:
        sys.exit("DỪNG: ứng viên KHÔNG đạt cả 3 tiêu chí – không xuất (lệnh AD).")
    torch, _, _ = H._torch()
    t = H.tap_do(C.NGUON)
    x, y = t["trang"]["x"], t["trang"]["y"]
    sd = 2026
    pre = tien_huan_luyen("ad1", sd, {})
    m = H.huan_luyen_cnn(x, y, C.FT["epochs"], C.FT["lr"], sd, mo_hinh=copy.deepcopy(pre), batch=C.FT["batch"])
    p_tr, _, T = xac_suat("ad1", sd, t)
    ng = L.chon_nguong(p_tr, y)
    tau, delta = (ng[1], ng[2]) if ng else (0.9999, 0.99)
    out = {"phien_ban": "ocr_cnn_v1", "kien_truc": "Conv16(3x3)-pool-Conv32(3x3)-pool-Dense64-Dense10, ReLU, padding 1",
           "thanh_vien": [{"seed": sd, "T": round(T, 4), **{k: X.lam_tron(v) for k, v in X.tham_so(m).items()}}],
           "tau": tau, "delta": delta, "tau_khop": L.TAU_KHOP,
           "sieu_du_lieu": {"cau_hinh": "ad1 (lệnh AD) – ỨNG VIÊN, KHÔNG phải mô hình thật", "git_head": X.git("rev-parse", "HEAD"),
                            "ket_qua": kq["tb"]["ad1"] | {"ket_luan": kq["ket_luan"]}}}
    dich = AD / "ocr_cnn_ung_vien.json"
    dich.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    mh = ocr.nap_mo_hinh_ocr(dich)
    xs = np.concatenate([t["trang"]["x"], t["phieu"]["x"]])
    p_np = ocr.du_doan_xac_suat(mh, xs)
    p_t = L.softmax(H.logits(m, xs).astype(np.float64) / T)
    chenh = float(np.abs(p_np - p_t).max())
    print(f"Ghi {dich}; NumPy ↔ PyTorch trên {len(xs)} chữ số: cùng nhãn {(p_np.argmax(1) == p_t.argmax(1)).mean():.4%}, chênh {chenh:.2e}")
    if chenh >= 1e-4:
        sys.exit("KHÔNG ĐẠT: NumPy khác PyTorch")


def cmd_don(a):
    if TAM.exists():
        n = sum(f.stat().st_size for f in TAM.rglob("*") if f.is_file())
        shutil.rmtree(TAM)
        print(f"Xoá {TAM} ({n / 1e6:.1f} MB)")
    else:
        print("Không có thư mục tạm.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["chay", "bang", "xuat", "don"])
    ap.add_argument("--cau-hinh", nargs="+", default=list(CAU_HINH), choices=list(CAU_HINH))
    ap.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    a = ap.parse_args()
    {"chay": cmd_chay, "bang": cmd_bang, "xuat": cmd_xuat, "don": cmd_don}[a.lenh](a)
