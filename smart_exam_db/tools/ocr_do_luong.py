"""
ocr_do_luong.py - Đo lường CNN chữ số: chọn cấu hình tinh chỉnh, hiệu chỉnh nhiệt độ, ngưỡng "cần xem", đối chiếu với bubble OMR,
bảng 3 cột (Tuần 6, docs/ke_hoach_tuan6.md Bước 5–6). Chỉ ĐO trên dữ liệu dev: trang D (OOF theo người viết) + phiếu 0001–0028.
KHÔNG đọc phiếu 0029–0040.

  omr    : chạy OMR (mô hình cuối, ĐÃ HUẤN LUYỆN trên 0001–0028 → kênh bubble hơi lạc quan) trên 56 ảnh phiếu dev -> data/_ocr/omr_dev.json
  bao-cao: chọn cấu hình + T + τ, δ trên OOF trang D; đo phiếu dev; ghi data/_eval/ocr/bao_cao_buoc5.md + .json
Chạy (từ smart_exam_db/):  python tools/ocr_do_luong.py omr | bao-cao
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402
from cv_engine import ocr  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_TRAIN, chan_test, ma_phieu  # noqa: E402

DATA, OCR, EVAL = H.DATA, H.OCR, H.EVAL
TAU_KHOP = 0.5          # đối chiếu: bubble chắc + CNN cùng chữ số + p ≥ 0,5 (chọn trước, không chỉnh theo dữ liệu)


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


# ------------------------------------------------------------------------------------------- OMR dev
def cmd_omr(a):
    from cv_engine.omr import doc_phieu, nap_mo_hinh
    from cv_engine.preprocessing import nap_layout, preprocess
    lay, mh = nap_layout("phieu"), nap_mo_hinh()
    anhs = sorted(p for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in PHIEU_TRAIN)
    chan_test(anhs, xac_nhan=False, viec="ocr_do_luong omr")
    out = {}
    for p in anhs:
        kq = preprocess(str(p), lay)
        if not kq.ok:
            out[p.stem] = {"tu_choi": kq.ly_do}
            continue
        o = doc_phieu(kq, lay, mh)
        out[p.stem] = {"sbd": [[c.chu_so, bool(c.can_xem)] for c in o.sbd_cot], "ma_de": [[c.chu_so, bool(c.can_xem)] for c in o.ma_de_cot]}
    (OCR / "omr_dev.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"OMR {len(out)} ảnh -> data/_ocr/omr_dev.json; từ chối: {sum('tu_choi' in v for v in out.values())}")


# ------------------------------------------------------------------------------------------- hiệu chỉnh + ngưỡng
def chon_nhiet(z, y):
    """Nhiệt độ T ∈ [0,5; 6] cực tiểu NLL của softmax(z / T) (tìm lưới mịn)."""
    best = None
    for T in np.arange(0.5, 6.01, 0.05):
        p = softmax(z / T)
        nll = -float(np.log(p[np.arange(len(y)), y] + 1e-12).mean())
        if best is None or nll < best[0]:
            best = (nll, float(T))
    return best[1]


def can_xem_cnn(p, tau, delta):
    s = np.sort(p, axis=1)
    return (s[:, -1] < tau) | (s[:, -1] - s[:, -2] < delta)


def chon_nguong(p, y):
    """τ, δ từ lưới: ít 'cần xem' nhất trong các cặp có LỖI IM LẶNG = 0 trên OOF (sai mà không gắn cần xem). Hoà: τ, δ lớn hơn."""
    sai = p.argmax(1) != y
    best = None
    for tau in [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999, 0.9995, 0.9999]:
        for delta in [0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.99]:
            cx = can_xem_cnn(p, tau, delta)
            im_lang = int((sai & ~cx).sum())
            if im_lang == 0 and (best is None or cx.mean() < best[0] - 1e-12 or (abs(cx.mean() - best[0]) < 1e-12 and (tau, delta) > best[1:])):
                best = (float(cx.mean()), tau, delta)
    return best                                        # None nếu không có cặp nào đạt 0 lỗi im lặng


def xem_sai_chac_chan(t, p, y, n=60):
    """Lưới ảnh các chữ số trang D bị đọc SAI với xác suất cao nhất (để người dùng xem nhãn / nét chữ): data/_eval/ocr/sai_chac_chan.png."""
    import cv2
    sai = np.where(p.argmax(1) != y)[0]
    sai = sai[np.argsort(-p[sai].max(1))][:n]
    tl = []
    for i in sai:
        im = cv2.cvtColor(cv2.resize(255 - t["trang"]["x"][i], (84, 84), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        r = t["trang"]["meta"][i]
        cv2.putText(im, f"{int(y[i])}>{int(p[i].argmax())} {p[i].max():.2f}", (1, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 255), 1)
        cv2.putText(im, f"{r['anh']}#{r['vi_tri']}", (1, 81), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (200, 0, 0), 1)
        tl.append(im)
    tl += [np.full_like(tl[0], 255)] * (-len(tl) % 10)
    cv2.imwrite(str(EVAL / "sai_chac_chan.png"), np.vstack([np.hstack(tl[i:i + 10]) for i in range(0, len(tl), 10)]))


# ------------------------------------------------------------------------------------------- báo cáo
def cmd_bao_cao(a):
    omr = json.loads((OCR / "omr_dev.json").read_text(encoding="utf-8"))
    m0 = json.loads((EVAL / "m0_buoc4.json").read_text(encoding="utf-8"))
    m1 = json.loads((EVAL / "m1_buoc5.json").read_text(encoding="utf-8"))
    cau_hinh, tong = {}, {}
    for kieu in H.CAU_HINH_M2:
        for nguon in H.NGUON:
            t = H.tap_do(nguon)
            z = np.load(OCR / f"oof_m2_{kieu}_{nguon}.npz")
            y_tr, meta_tr = t["trang"]["y"], t["trang"]["meta"]
            pred = z["trang"].argmax(1)
            theo = H.theo_nguoi(y_tr, pred, meta_tr)
            cau_hinh[f"{kieu}/{nguon}"] = {"acc_trang_oof": H.tom_tat(y_tr, pred)["acc"], "theo_nguoi": {k: v["acc"] for k, v in theo.items()},
                                           "min_nguoi": min(v["acc"] for v in theo.values())}
            tong[(kieu, nguon)] = (t, z)
    chon = max(cau_hinh, key=lambda k: (cau_hinh[k]["min_nguoi"], cau_hinh[k]["acc_trang_oof"]))
    kieu, nguon = chon.split("/")
    t, z = tong[(kieu, nguon)]
    ghi = {"cau_hinh_m2": cau_hinh, "chon": chon, "quy_tac_chon": "maximin accuracy trang D OOF theo 5 người viết; hoà → accuracy trung bình"}
    print("Cấu hình M2 (trang D OOF theo người viết):")
    for k, v in cau_hinh.items():
        print(f"  {k:24s} acc {v['acc_trang_oof']:.4f}  min người {v['min_nguoi']:.4f}  {v['theo_nguoi']}" + ("   <== CHỌN" if k == chon else ""))
    # hiệu chỉnh + ngưỡng trên OOF trang D
    y_tr, meta_tr = t["trang"]["y"], t["trang"]["meta"]
    T = chon_nhiet(z["trang"], y_tr)
    p_tr = softmax(z["trang"] / T)
    ng = chon_nguong(p_tr, y_tr)
    ghi["T"] = T
    print(f"Nhiệt độ T = {T:.2f}")
    if ng is None:
        print("KHÔNG có cặp (τ, δ) nào cho lỗi im lặng = 0 trên OOF trang D -> dùng τ = 0,9999, δ = 0,99 (chặt nhất) và báo cáo lỗi còn lại")
        tau, delta = 0.9999, 0.99
    else:
        _, tau, delta = ng
    ghi["tau"], ghi["delta"] = tau, delta
    xem_sai_chac_chan(t, p_tr, y_tr)
    # đo digit-level OOF trang D
    cx = can_xem_cnn(p_tr, tau, delta)
    sai = p_tr.argmax(1) != y_tr
    ghi["trang_oof"] = {"n": int(len(y_tr)), "acc": H.tom_tat(y_tr, p_tr.argmax(1)), "sai": int(sai.sum()), "im_lang": int((sai & ~cx).sum()),
                        "can_xem": round(float(cx.mean()), 4), "can_xem_thua": round(float((cx & ~sai).mean()), 4),
                        "theo_nguoi": H.theo_nguoi(y_tr, p_tr.argmax(1), meta_tr)}
    lo, hi = H.cp_ci(int((sai & ~cx).sum()), int(sai.sum()) or 1)
    print(f"τ = {tau}, δ = {delta}: trang D OOF {len(y_tr)} chữ số, sai {int(sai.sum())}, lỗi im lặng {int((sai & ~cx).sum())} "
          f"(trong số ô sai CP95% ≤ {hi:.3f}), cần xem {cx.mean():.1%}")
    # phiếu dev
    yp, meta_p = t["phieu"]["y"], t["phieu"]["meta"]
    p_ph = softmax(z["phieu"] / T)
    cx_p = can_xem_cnn(p_ph, tau, delta)
    sai_p = p_ph.argmax(1) != yp
    ghi["phieu_dev"] = {"n": int(len(yp)), "acc": H.tom_tat(yp, p_ph.argmax(1)), "sai": int(sai_p.sum()), "im_lang_chu_so": int((sai_p & ~cx_p).sum()),
                        "can_xem": round(float(cx_p.mean()), 4), "theo_nguoi": H.theo_nguoi(yp, p_ph.argmax(1), meta_p),
                        "theo_dieu_kien": H.theo_dieu_kien(yp, p_ph.argmax(1), meta_p)}
    print(f"Phiếu dev (người lạ, OOF): {len(yp)} chữ số, sai {int(sai_p.sum())}, im lặng (chỉ CNN) {int((sai_p & ~cx_p).sum())}, cần xem {cx_p.mean():.1%}")
    # đối chiếu với bubble, mức trường
    cot = {}
    for i, (r, pi, c) in enumerate(zip(meta_p, p_ph, cx_p)):
        cot[(r["anh"], r["loai"], int(r["vi_tri"]))] = (int(pi.argmax()), float(pi.max()), bool(c), r["trong"] == "1", int(r["nhan"]))
    truong = {}
    for (anh, lo, vt), (d, p, c, tr, nhan) in cot.items():
        o = omr[anh]
        b, bcx = (o[lo][vt] if "tu_choi" not in o else ["?", True])
        truong.setdefault((anh, lo), []).append((vt, ocr.doi_chieu_cot(b, bcx, str(d), p, not c, tr, TAU_KHOP), nhan))
    kq = {"sbd": [], "ma_de": []}
    for (anh, lo), v in truong.items():
        v.sort(key=lambda x: x[0])
        gia_tri, chac, ly = ocr.doi_chieu_truong([x[1] for x in v], True)       # dev: SBD / mã đề thật nằm trong danh sách
        dung = gia_tri == "".join(str(x[2]) for x in v)
        kq[lo].append({"anh": anh, "chac": chac, "dung": dung, "ly_do": list(ly)})
    ghi["doi_chieu_phieu_dev"] = {}
    for lo, ds in kq.items():
        n, chac = len(ds), [d for d in ds if d["chac"]]
        im_lang = [d["anh"] for d in chac if not d["dung"]]
        thua = [d for d in ds if not d["chac"] and d["dung"]]
        ly = {}
        for d in ds:
            for m in d["ly_do"]:
                ly[m] = ly.get(m, 0) + 1
        lo_, hi_ = H.cp_ci(len(im_lang), len(chac) or 1)
        ghi["doi_chieu_phieu_dev"][lo] = {"n": n, "chac": len(chac), "can_xem": n - len(chac), "im_lang": len(im_lang), "im_lang_anh": im_lang,
                                           "im_lang_ci95": [round(lo_, 4), round(hi_, 4)], "can_xem_thua": len(thua), "ly_do": ly}
        print(f"Mức trường {lo}: {n} ảnh, chắc {len(chac)}, cần xem {n - len(chac)}, LỖI IM LẶNG {len(im_lang)} {im_lang}, lý do {ly}")
    # độ nhạy τ_khop (CHỈ THAM KHẢO – không chốt; phiếu dev là tập ĐO): chữ số bubble được nhận nếu p_CNN(chữ số bubble) ≥ τ
    nhay = {}
    for tk in (0.5, 0.3, 0.2, 0.1):
        nc = sl = nthua = 0
        for (anh, lo), v in truong.items():
            cols = []
            for vt, _, nhan in sorted(v, key=lambda x: x[0]):
                o = omr[anh]
                b, bcx = (o[lo][vt] if "tu_choi" not in o else ["?", True])
                d, pp, c_, tr, _ = cot[(anh, lo, vt)]
                pb = float(p_ph[[i for i, r in enumerate(meta_p) if r["anh"] == anh and r["loai"] == lo and int(r["vi_tri"]) == vt][0]][int(b)]) if b != "?" else 0.0
                cols.append(ocr.doi_chieu_cot(b, bcx, b if pb >= tk else str((int(b) + 1) % 10 if b != "?" else "x"), pb, True, tr, tk))
            gt_, ch_, _ = ocr.doi_chieu_truong(cols, True)
            dung = gt_ == "".join(str(x[2]) for x in sorted(v, key=lambda x: x[0]))
            nc += ch_
            sl += ch_ and not dung
        nhay[str(tk)] = {"chac": nc, "im_lang": sl, "tong": len(truong)}
    ghi["do_nhay_tau_khop_tham_khao"] = nhay
    print("Độ nhạy τ_khop (tham khảo):", nhay)
    # T4: phiếu (ảnh) toàn đúng nhưng bị gắn cần xem ở SBD hoặc mã đề
    ds_anh = {}
    for lo, ds in kq.items():
        for d in ds:
            ds_anh.setdefault(d["anh"], []).append(d)
    n_anh = len(ds_anh)
    flag = [a_ for a_, v in ds_anh.items() if any(not d["chac"] for d in v)]
    thua = [a_ for a_ in flag if all(d["dung"] for d in ds_anh[a_])]
    ghi["T4"] = {"anh": n_anh, "can_xem": len(flag), "can_xem_thua_theo_dinh_nghia_T4": len(thua), "ti_le_can_xem": round(len(flag) / n_anh, 4)}
    print(f"T4: {n_anh} ảnh phiếu, cần xem {len(flag)} ({len(flag) / n_anh:.1%}); trong đó chữ số CUỐI vẫn đúng (cần xem thừa theo T4) {len(thua)}")
    # mức trường chỉ CNN argmax (không đối chiếu) cho 3 cột
    ghi["m0"], ghi["m1"] = {k: m0[k] for k in ("mnist_test", "anh_nan", "anh_chuan_hoa")}, {k: m1[k] for k in ("mnist_test", "anh_nan", "anh_chuan_hoa")}
    (EVAL / "bao_cao_buoc5.json").write_text(json.dumps(ghi, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Ghi {EVAL / 'bao_cao_buoc5.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["omr", "bao-cao"])
    a = ap.parse_args()
    {"omr": cmd_omr, "bao-cao": cmd_bao_cao}[a.lenh](a)
