"""
am_cnn_sau.py - Lệnh AM giai đoạn 2: huấn luyện CNN sâu "sau_2x2" (467 818 tham số) đúng giao thức CNN triển khai và đo tiêu chí (a)–(d)
của docs/tieu_chi_cnn_sau.md (đăng ký TRƯỚC, commit 4f97e6f). KHÔNG sửa tiêu chí, KHÔNG ghi vào models/. Cần torch + scikit-learn.

  python tools/am_cnn_sau.py huan-luyen   # 3 seed (2026, 1, 2); chạy tiếp được (ghi data/_eval/am/tien_do.txt, bỏ qua bước đã có tệp)
  python tools/am_cnn_sau.py do           # (c) (d) từng mô hình + (a) (b) -> data/_eval/am/ket_qua.json

Giao thức mỗi seed (giống CNN triển khai, quy trình của ak_so_sanh_mo_rong.py):
  tiền huấn luyện MNIST 55 000 (10 epoch, Adam 2e-3 + cosine) -> (a) OOF 5-fold theo người viết trang D (tinh chỉnh 6 epoch, lr 3e-4, lô 64) cho 504 ô phiếu dev
  -> mô hình ỨNG VIÊN = tinh chỉnh trên TOÀN BỘ trang D (5 người) -> data/_eval/am/ocr_cnn_sau_seed{N}.json (tau = 0,9995, delta = 0,99 giữ nguyên;
  T = nhiệt độ cực tiểu NLL trên OOF trang D). (b) AG: đọc 117 ô đã cắt sẵn (ag_o.npz, từ ak ag-cat; KHÔNG gọi ag_cham_that.cham).
Baseline = CNN hiện tại cùng cách đo: OOF g0_goc (data/_eval/ak/tam/E2b_cnn_*) + CNN triển khai trên ô AG (AG_cnn_trien_khai_2026.npz).
"""
import argparse
import copy
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import ai_so_sanh_thuat_toan as A  # noqa: E402
import ak_so_sanh_mo_rong as K  # noqa: E402
import huan_luyen_ocr as H  # noqa: E402
import ocr_cai_tien as C  # noqa: E402
import ocr_do_luong as L  # noqa: E402
import xuat_ocr as X  # noqa: E402
from cv_engine import ocr  # noqa: E402

AM = ROOT / "data" / "_eval" / "am"
TAM = AM / "tam"
AK_TAM = ROOT / "data" / "_eval" / "ak" / "tam"
SEEDS = (2026, 1, 2)
TAU, DELTA, TAU_KHOP = 0.9995, 0.99, 0.5            # GIỮ NGUYÊN theo lệnh – không chỉnh theo dev
A.TAM = TAM                                         # K.pre_net / A.luu / A.nap ghi + đọc ở đây (K đã đặt A.TAM = AK/tam lúc import)


def ghi_tien_do(msg: str):
    AM.mkdir(parents=True, exist_ok=True)
    with (AM / "tien_do.txt").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    print(msg, flush=True)


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def cmd_huan_luyen(a):
    torch, _, _ = H._torch()
    TAM.mkdir(parents=True, exist_ok=True)
    D = A.du_lieu()
    xt, yt, _ = D["trang"]
    x_ag = np.load(K.AK / "ag_o.npz")["x"]
    for seed in SEEDS:
        f_json, f_pt = AM / f"ocr_cnn_sau_seed{seed}.json", TAM / f"final_sau_{seed}.pt"
        if f_json.exists() and f_pt.exists() and (TAM / f"AG_cnnsau_{seed}.npz").exists():
            ghi_tien_do(f"seed {seed}: ĐÃ XONG trước đó – bỏ qua")
            continue
        try:
            t0 = time.time()
            ghi = {"thi_nghiem": "E2b", "thuat_toan": "cnnsau", "seed": seed, "theo_fold": {}}
            pre = K.pre_net("cnnsau", seed, ghi)
            ghi_tien_do(f"seed {seed}: tiền huấn luyện MNIST xong ({time.time() - t0:.0f} s tính từ đầu seed)")
            if not (TAM / f"E2b_cnnsau_{seed}.npz").exists():
                t1 = time.time()
                lt, lp = C.oof(pre, "co_ban", seed)
                A.luu("E2b", "cnnsau", seed, {"trang": lt[D["idx_trang"]], "phieu": lp[D["idx_phieu"]]}, dict(ghi, giay=round(time.time() - t1, 1)))
            ghi_tien_do(f"seed {seed}: OOF 5-fold theo người viết xong")
            m = H.huan_luyen_cnn(xt, yt, C.FT["epochs"], C.FT["lr"], seed, mo_hinh=copy.deepcopy(pre), batch=C.FT["batch"]).eval()
            torch.save(m.state_dict(), f_pt)
            z = np.load(TAM / f"E2b_cnnsau_{seed}.npz")
            T = L.chon_nhiet(z["trang"], yt)
            out = {"phien_ban": "ocr_cnn_sau_am_v1", "kien_truc": ocr.KIEN_TRUC_SAU, "tau": TAU, "delta": DELTA, "tau_khop": TAU_KHOP,
                   "thanh_vien": [{"seed": seed, "T": round(T, 4), **{k: X.lam_tron(v) for k, v in X.tham_so(m).items()}}],
                   "sieu_du_lieu": {"ngay": time.strftime("%Y-%m-%d %H:%M"), "git_head": git_head(), "lenh": "AM giai đoạn 2 – ỨNG VIÊN, KHÔNG triển khai",
                                    "tien_huan_luyen": "MNIST 55 000, 10 epoch, Adam 2e-3 + cosine", "tinh_chinh": "toàn bộ trang D (5 người), 6 epoch, lr 3e-4, lô 64",
                                    "nhiet_do_T": T, "so_tham_so": 467818}}
            f_json.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            np.savez_compressed(TAM / f"AG_cnnsau_{seed}.npz", z=H.logits(m, x_ag))
            ghi_tien_do(f"seed {seed}: XONG (T = {T:.2f}; tổng {time.time() - t0:.0f} s) -> {f_json.name}")
        except Exception as e:                                       # báo đúng như vậy, KHÔNG bỏ / thay seed
            ghi_tien_do(f"seed {seed}: LỖI {type(e).__name__}: {e}")
            raise


# ------------------------------------------------------------------------------------------- đo
def thoi_gian_tung_o(mh, x, vong=3, n=500):
    """≥ 3 lần đo, mỗi lần n lời gọi từng ô một (đã làm nóng): (trung vị, p95) ms mỗi lần."""
    for i in range(60):
        ocr.du_doan_xac_suat(mh, x[i:i + 1])
    kq = []
    for _ in range(vong):
        ts = []
        for i in range(n):
            t = time.perf_counter(); ocr.du_doan_xac_suat(mh, x[i:i + 1]); ts.append((time.perf_counter() - t) * 1000)
        kq.append({"trung_vi": statistics.median(ts), "p95": float(np.percentile(ts, 95))})
    return kq


def cmd_do(a):
    torch, _, _ = H._torch()
    D = A.du_lieu()
    yt = D["trang"][1]
    x_kt = np.concatenate([H.doc_mnist()[2][:2000], D["phieu"][0]])               # 2000 ô MNIST test + 504 ô phiếu dev
    kq = {"ngay": time.strftime("%Y-%m-%d %H:%M"), "git_head": git_head(), "c": {}, "d": {}}
    # ---- (c) + (d) từng mô hình
    for seed in SEEDS:
        mh = ocr.nap_mo_hinh_ocr(AM / f"ocr_cnn_sau_seed{seed}.json")
        net = K.tao_cnn_sau()
        net.load_state_dict(torch.load(TAM / f"final_sau_{seed}.pt"))
        net.eval()
        z_np, z_pt = ocr.logit_mot_thanh_vien(mh.thanh_vien[0], x_kt), H.logits(net, x_kt)
        kq["c"][seed] = {"so_o": len(x_kt), "cung_nhan": float((z_np.argmax(1) == z_pt.argmax(1)).mean()), "logit_lech_max": float(np.abs(z_np - z_pt).max()),
                         "logit_lech_tb": float(np.abs(z_np - z_pt).mean()), "logit_do_lon_max": float(np.abs(z_pt).max())}
        kq["d"][str(seed)] = thoi_gian_tung_o(mh, x_kt)
    kq["d"]["hien_tai"] = thoi_gian_tung_o(ocr.nap_mo_hinh_ocr(), x_kt)
    # ---- (a) + (b): cùng cách R4 của AK
    A.TAM = AK_TAM
    cnn_cu = A.nap("E2b", "cnn")
    A.TAM = TAM
    sau = A.nap("E2b", "cnnsau")
    ra_cu = K.r4a({"cnn": cnn_cu}, yt)["cnn"]
    ra_sau = {sd: K.r4a({"s": [l]}, yt)["s"] for sd, l in zip(SEEDS, sau)}
    ra_tb = K.r4a({"sau": sau}, yt)["sau"]
    nap_b = {"cnn_trien_khai": [(2026, np.load(AK_TAM / "AG_cnn_trien_khai_2026.npz")["z"], 1.0)]}
    for sd, l in zip(SEEDS, sau):                                      # l = (seed, npz OOF, ghi)
        nap_b[f"sau_{sd}"] = [(sd, np.load(TAM / f"AG_cnnsau_{sd}.npz")["z"], L.chon_nhiet(l[1]["trang"], yt))]
    rb, meta_b = K.r4b(nap_b, yt)
    hw = [ra_sau[s]["hw_gop"] for s in SEEDS]
    kq["a"] = {"baseline": {k: v for k, v in ra_cu.items()}, "tung_seed": {str(s): ra_sau[s] for s in SEEDS}, "tb": ra_tb,
               "hw_gop_tung_seed": hw, "hw_gop_tb": float(np.mean(hw)), "hw_gop_sd": float(np.std(hw, ddof=1)), "hw_gop_baseline": ra_cu["hw_gop"],
               "chenh_diem": 100 * (float(np.mean(hw)) - ra_cu["hw_gop"])}
    kq["b"] = {"dev_sai_khong_co_tung_seed": {str(s): ra_sau[s]["sai_khong_co"] for s in SEEDS}, "dev_baseline": ra_cu["sai_khong_co"],
               "ag": rb, "ag_meta": meta_b}
    AM.mkdir(parents=True, exist_ok=True)
    (AM / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: kq[k] for k in ("c", "d")}, indent=1, default=float))
    print(json.dumps({"a": {k: kq["a"][k] for k in ("hw_gop_tung_seed", "hw_gop_tb", "hw_gop_sd", "hw_gop_baseline", "chenh_diem")}, "b": kq["b"]["dev_sai_khong_co_tung_seed"]}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="lenh", required=True)
    sp.add_parser("huan-luyen").set_defaults(f=cmd_huan_luyen)
    sp.add_parser("do").set_defaults(f=cmd_do)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
