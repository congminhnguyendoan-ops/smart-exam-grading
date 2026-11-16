"""am_do_giai_doan1.py - Lệnh AM giai đoạn 1: đo tiêu chí (c) và (d) của CNN sâu với trọng số ngẫu nhiên cố định seed (CHƯA huấn luyện).
Chạy từ smart_exam_db/:  python tools/am_do_giai_doan1.py  -> in JSON. Không ghi vào models/."""
import json
import statistics
import sys
import time
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import ak_so_sanh_mo_rong as K  # noqa: E402
import huan_luyen_ocr as H  # noqa: E402
import xuat_ocr as X  # noqa: E402
from cv_engine import ocr  # noqa: E402


def ms_mot_o(mh, x, n=500):
    """Trung vị ms/ô: (i) lô 500 ô, (ii) từng ô một (đã làm nóng)."""
    ocr.du_doan_xac_suat(mh, x[:50])
    lo = []
    for _ in range(5):
        t = time.perf_counter(); ocr.du_doan_xac_suat(mh, x[:n]); lo.append((time.perf_counter() - t) / n * 1000)
    mot = []
    for i in range(n):
        t = time.perf_counter(); ocr.du_doan_xac_suat(mh, x[i:i + 1]); mot.append((time.perf_counter() - t) * 1000)
    return {"lo_500": statistics.median(lo), "tung_o": statistics.median(mot), "p95_tung_o": float(np.percentile(mot, 95))}


def main():
    torch, _, _ = H._torch()
    x = H.doc_mnist()[2][:2000]
    torch.manual_seed(20261116)
    net = K.tao_cnn_sau().eval()
    tmp = Path(tempfile.mkdtemp()) / "sau.json"
    tmp.write_text(json.dumps({"phien_ban": "thu", "kien_truc": ocr.KIEN_TRUC_SAU, "tau": 0.9995, "delta": 0.99, "tau_khop": 0.5,
                               "thanh_vien": [{"seed": 1, "T": 1.0, **{k: X.lam_tron(v) for k, v in X.tham_so(net).items()}}]}), encoding="utf-8")
    sau = ocr.nap_mo_hinh_ocr(tmp)
    z_np, z_pt = ocr.logit_mot_thanh_vien(sau.thanh_vien[0], x), H.logits(net, x)
    kq = {"c": {"so_o": len(x), "cung_nhan": float((z_np.argmax(1) == z_pt.argmax(1)).mean()), "logit_lech_max": float(np.abs(z_np - z_pt).max()),
                "logit_std": float(z_pt.std())},
          "d": {"sau": ms_mot_o(sau, x), "hien_tai": ms_mot_o(ocr.nap_mo_hinh_ocr(), x)}}
    print(json.dumps(kq, indent=1))


if __name__ == "__main__":
    main()
