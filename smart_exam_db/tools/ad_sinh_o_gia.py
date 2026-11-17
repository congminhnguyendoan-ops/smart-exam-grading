"""
ad_sinh_o_gia.py - Lệnh AD, Bước 2: biến chữ số EMNIST / MNIST thành "ô phiếu giả" giống ô viết tay cắt từ ảnh chụp thật.

Vẽ ở thang 300 DPI của ảnh đã nắn (ô 70,9 × 106,3 px, viền in sẵn, nền giấy, bóng, nhoè, nhiễu, JPEG…) rồi cho qua ĐÚNG đường chạy thật:
cv_engine.ocr.cat_o (cắt vào NUT_VIEN, bản đồ mực, bỏ hạt bẩn / mảnh viền, ve_mnist 20×20 + trọng tâm) và ocr._hop_ly_o (ô trống / ít mực /
không phải chữ số bị loại – lúc chạy thật những ô đó cũng KHÔNG qua CNN). Kết quả là ảnh 28×28 cùng phân phối đầu vào với CNN lúc chạy.

Chỉnh tham số CHỈ theo trang chữ số D001–D010 (dữ liệu huấn luyện); KHÔNG nhìn ô trên phiếu 0001–0034 (phiếu 0001–0028 dùng để đo).

  python tools/ad_sinh_o_gia.py that                 # cắt ô thật trang D -> data/_eval/ad/o_that_mau.npz + thống kê
  python tools/ad_sinh_o_gia.py so-sanh              # 8 ô thật | 8 ô giả -> data/_eval/ad/so_sanh_that_gia.png + bảng thống kê
  python tools/ad_sinh_o_gia.py sinh --n 60000       # sinh bộ ô giả -> data/_eval/ad/o_gia.npz (x 28×28, y, nguồn)
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine import ocr  # noqa: E402

EVAL = ROOT / "data" / "_eval" / "ad"
EMNIST = ROOT / "data" / "nguon_ngoai" / "emnist_digits.npz"
W_O, H_O = 70.9, 106.3          # ô danh nghĩa @300 DPI (sheet_layout.py)
LE = 22                         # lề quanh ô trên ảnh vẽ (đủ chứa viền ô bên cạnh)

# Tham số CUỐI (sau khi so với trang D – xem docs/lenh_ad.md mục Bước 2). Khoảng [lo, hi] = phân phối đều.
TS = {
    "nen": (195, 230),           # mức xám giấy TRƯỚC bóng / gamma (anh_nan) – trang D: p5–p95 183–217 sau cùng
    "nhieu_nen": (3.0, 6.0),     # độ lệch chuẩn nhiễu Gauss mịn (mức xám)
    "van_giay": (2.0, 5.0),      # vân giấy: nhiễu Gauss làm mờ σ 1,5 px, biên độ (mức xám)
    "vien_day": (3, 4),          # bề dày nét viền (px; cv2 vẽ nét chẵn rộng hơn) – 5–6 px lọt vào vùng cắt NUT_VIEN, khác ảnh thật
    "vien_dam": (0.78, 0.95),    # độ đậm viền: xám = nền × (1 − đậm) – trang D p5–p95 0,80–0,96
    "o_ben": 0.7,                # xác suất vẽ viền ô bên cạnh
    "khoang_o_ben": (12, 24),    # khe giữa 2 ô (phiếu 11,8 px, trang D 23,6 px)
    "cao_chu": (40, 86),         # chiều cao chữ TRƯỚC làm mảnh nét (px) – sau cùng trang D: p5–p95 37–74
    "gian_ngang": (0.7, 1.1),    # co giãn ngang riêng (EMNIST rộng hơn chữ trên phiếu)
    "nguong_mong": (0.5, 0.82),  # ngưỡng làm mảnh nét sau khi phóng to (cao = mảnh hơn)
    "net_dam": (0.45, 0.9),      # độ đậm mực: xám = nền × (1 − đậm × mực)
    "xoay": 8.0,                 # độ
    "nghieng": 0.2,              # shear
    "lech": 0.5,                 # dịch tâm chữ, tỉ lệ khoảng trống còn lại
    "p_lan_vien": 0.12,          # chữ lấn sát / chạm viền
    "p_net_dut": 0.15,           # nét đứt / nhạt từng đoạn
    "p_bong": 0.5, "bong": (0.03, 0.2),          # bóng đổ (dốc tuyến tính)
    "sang": (0.92, 1.05), "gamma": (0.9, 1.12),  # độ sáng / tương phản
    "p_nhoe": 0.35, "nhoe": (0.3, 1.0),          # Gauss σ (px) – ảnh trang D hầu như sắc nét
    "p_chuyen_dong": 0.08, "chuyen_dong": (3, 5),
    "cao_min": 28,               # chữ sau cùng thấp hơn -> bỏ mẫu (trang D: p1 của cao = 33)
    "p_jpeg": 0.6, "jpeg": (55, 95),
    "lech_khung": 1,             # khung đưa vào cat_o lệch ±1 px (mô phỏng tim_khung)
}


# ------------------------------------------------------------------------------------------- vẽ ô giả
def _u(rng, ab):
    return float(rng.uniform(*ab))


def ve_o(src: np.ndarray, rng: np.random.Generator, ts: dict = TS):
    """src: chữ số 28×28 uint8 (nền 0, nét 255, đúng chiều). Trả (ảnh xám uint8 vẽ ô, khung (x0,y0,x1,y1,True), rect danh nghĩa)."""
    Wc, Hc = int(round(W_O)) + 2 * LE, int(round(H_O)) + 2 * LE
    rect = (float(LE), float(LE), W_O, H_O)
    # --- mực của chữ số (0–1) trên toàn ảnh
    ys, xs = np.nonzero(src > 25)
    c = src[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32) / 255.0
    h0, w0 = c.shape
    cao = _u(rng, ts["cao_chu"])
    rong = max(cao * w0 / h0 * _u(rng, ts["gian_ngang"]), 4.0)
    rong = min(rong, W_O - 6)
    c = cv2.resize(np.pad(c, 2), (int(round(rong)) + 4, int(round(cao)) + 4), interpolation=cv2.INTER_CUBIC)
    t = _u(rng, ts["nguong_mong"])
    c = np.clip((c - t) / 0.2, 0, 1)                                   # làm mảnh nét (MNIST phóng to quá dày so với bút bi)
    # xoay + nghiêng quanh tâm
    hh, ww = c.shape
    P = 12
    c = np.pad(c, P)
    th, sh = np.deg2rad(_u(rng, (-ts["xoay"], ts["xoay"]))), _u(rng, (-ts["nghieng"], ts["nghieng"]))
    A = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]) @ np.array([[1, sh], [0, 1]])
    ctr = np.array([c.shape[1] / 2, c.shape[0] / 2])
    M = np.hstack([A, (ctr - A @ ctr)[:, None]])
    c = cv2.warpAffine(c, M, (c.shape[1], c.shape[0]), flags=cv2.INTER_LINEAR)
    if rng.random() < ts["p_net_dut"]:                                 # nét đứt / nhạt: nhân mặt nạ tần số thấp
        m = cv2.resize(rng.random((4, 4)).astype(np.float32), (c.shape[1], c.shape[0]), interpolation=cv2.INTER_CUBIC)
        c = c * np.clip((m - rng.uniform(0.1, 0.4)) * 3, 0.15, 1)
    yy, xx = np.nonzero(c > 0.3)
    if len(yy) == 0:
        return None
    c = c[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    hh, ww = c.shape
    if hh < ts["cao_min"]:
        return None
    # đặt vào ô: vùng trong viền = rect co vào ~3 px
    ix0, iy0, ix1, iy1 = LE + 3, LE + 3, LE + W_O - 3, LE + H_O - 3
    du_x, du_y = max(ix1 - ix0 - ww, 0), max(iy1 - iy0 - hh, 0)
    if rng.random() < ts["p_lan_vien"]:
        ox = ix0 + (rng.choice([0.0, 1.0]) * du_x) + rng.uniform(-3, 3)
        oy = iy0 + rng.uniform(0, 1) * du_y + rng.uniform(-3, 3)
    else:
        k = ts["lech"]
        ox = ix0 + du_x * (0.5 + rng.uniform(-k, k) / 2)
        oy = iy0 + du_y * (0.5 + rng.uniform(-k, k) / 2)
    ox, oy = int(round(ox)), int(round(oy))
    muc = np.zeros((Hc, Wc), np.float32)
    y0, x0 = max(oy, 0), max(ox, 0)
    y1, x1 = min(oy + hh, Hc), min(ox + ww, Wc)
    muc[y0:y1, x0:x1] = c[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    # --- viền ô (+ viền ô bên cạnh)
    vien = np.zeros((Hc, Wc), np.float32)
    d = int(rng.integers(ts["vien_day"][0], ts["vien_day"][1] + 1))
    a, b = (LE, LE), (int(round(LE + W_O)), int(round(LE + H_O)))
    cv2.rectangle(vien, a, b, 1.0, d)
    if rng.random() < ts["o_ben"]:
        kh = _u(rng, ts["khoang_o_ben"])                               # ô bên trái / phải cùng hàng (hình chữ nhật riêng, có khe)
        for xb in (LE - kh - W_O, LE + W_O + kh):
            cv2.rectangle(vien, (int(round(xb)), a[1]), (int(round(xb + W_O)), b[1]), 1.0, d)
    # --- ghép: giấy × (1 − mực) × (1 − viền)
    nen = _u(rng, ts["nen"])
    g = np.full((Hc, Wc), nen, np.float32)
    g *= 1 - _u(rng, ts["vien_dam"]) * vien
    g *= 1 - _u(rng, ts["net_dam"]) * muc
    if rng.random() < ts["p_bong"]:                                    # bóng: dốc tuyến tính hướng ngẫu nhiên
        phi = rng.uniform(0, 2 * np.pi)
        Y, X = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
        r = (X * np.cos(phi) + Y * np.sin(phi))
        r = (r - r.min()) / (np.ptp(r) + 1e-6)
        g *= 1 - _u(rng, ts["bong"]) * r
    g = 255.0 * ((g * _u(rng, ts["sang"])).clip(0, 255) / 255.0) ** _u(rng, ts["gamma"])
    if rng.random() < ts["p_nhoe"]:
        g = cv2.GaussianBlur(g, (0, 0), _u(rng, ts["nhoe"]))
    if rng.random() < ts["p_chuyen_dong"]:
        L = int(rng.integers(ts["chuyen_dong"][0], ts["chuyen_dong"][1] + 1))
        k = np.zeros((L, L), np.float32)
        k[L // 2, :] = 1
        k = cv2.warpAffine(k, cv2.getRotationMatrix2D((L / 2 - 0.5, L / 2 - 0.5), rng.uniform(0, 180), 1.0), (L, L))
        g = cv2.filter2D(g, -1, k / max(k.sum(), 1e-6))
    g = g + cv2.GaussianBlur(rng.normal(0, 1, g.shape).astype(np.float32), (0, 0), 1.5) * _u(rng, ts["van_giay"]) * 2.5
    g = g + rng.normal(0, _u(rng, ts["nhieu_nen"]), g.shape)
    g = np.clip(g + 0.5, 0, 255).astype(np.uint8)
    if rng.random() < ts["p_jpeg"]:
        g = cv2.imdecode(cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(*ts["jpeg"]))])[1], cv2.IMREAD_GRAYSCALE)
    # khung NGOÀI (như tim_khung trả) = mép ngoài nét viền, lệch ±1 px
    j = ts["lech_khung"]
    lk = lambda: int(rng.integers(-j, j + 1))
    khung = (a[0] - d // 2 + lk(), a[1] - d // 2 + lk(), b[0] + d // 2 + 1 + lk(), b[1] + d // 2 + 1 + lk(), True)
    return g, khung, rect


def qua_duong_that(g, khung, rect):
    """Cho ô vẽ qua đúng đường chạy thật. Trả (OChuSo, hợp lệ: bool)."""
    o = ocr.cat_o(g, khung, rect)
    return o, (ocr._hop_ly_o(o) == "" and o.anh28 is not None)


# ------------------------------------------------------------------------------------------- thống kê dùng chung thật / giả
def thong_ke(g: np.ndarray, khung) -> dict:
    """Số đo của 1 ô (ảnh xám + khung ngoài), giống nhau cho ô thật và ô giả."""
    x0, y0, x1, y1, _ = khung
    n = ocr.NUT_VIEN
    o = g[y0 + n:y1 - n, x0 + n:x1 - n].astype(np.float32)
    oc = ocr.cat_o(g, khung, (x0, y0, x1 - x0, y1 - y0))
    mk = oc.ink >= ocr.NGUONG_MUC
    nen = float(np.median(o))
    r = {"nen": nen, "ink_px": oc.ink_px, "cao": oc.cao, "rong": oc.rong, "cham_vien": oc.cham_vien}
    r["net_dam"] = float(np.percentile(1 - o[mk] / max(nen, 1), 90)) if mk.sum() > 5 else np.nan
    cn, _ = cv2.findContours(mk.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    chu_vi = sum(len(c) for c in cn)
    r["rong_net"] = float(2 * mk.sum() / chu_vi) if chu_vi else np.nan
    nn = cv2.dilate(mk.astype(np.uint8), np.ones((5, 5), np.uint8)) == 0
    r["nhieu_nen"] = float(np.std(o[nn] - cv2.GaussianBlur(o, (0, 0), 3)[nn])) if nn.sum() > 50 else np.nan
    gy, gx = np.gradient(cv2.GaussianBlur(o, (0, 0), 0.5))
    r["do_net"] = float(np.percentile(np.hypot(gx, gy)[mk], 90) / max(nen, 1)) if mk.sum() > 5 else np.nan
    bv = g[max(y0, 0):y1, max(x0, 0):x1].astype(np.float32)
    r["vien_dam"] = float(1 - np.percentile(np.concatenate([bv[:3].ravel(), bv[-3:].ravel(), bv[:, :3].ravel(), bv[:, -3:].ravel()]), 10) / max(nen, 1))
    return r


# ------------------------------------------------------------------------------------------- ô thật (trang D)
def khung_cua_anh(xam, nhom_rects):
    """Như ocr.cat_anh nhưng trả KHUNG (x0,y0,x1,y1,ok) của từng ô (để cắt ảnh xám hiển thị / đo)."""
    toi = ocr.ban_do_toi(xam)
    kh = [ocr.tim_khung(toi, rs) for rs in nhom_rects]
    tim = [(k[0] - round(r[0]), k[1] - round(r[1])) for ks, rs in zip(kh, nhom_rects) for k, r in zip(ks, rs) if k is not None]
    dx, dy = (int(np.median([d[0] for d in tim])), int(np.median([d[1] for d in tim]))) if tim else (0, 0)
    out = []
    for ks, rs in zip(kh, nhom_rects):
        for k, r in zip(ks, rs):
            out.append((k if k is not None else (*ocr.tinh_chinh_khung(toi, r, dx, dy), False), r))
    return out


def cmd_that(a):
    from cv_engine.preprocessing import nap_layout, preprocess
    from cv_engine.tap_du_lieu import nguoi_viet
    lay = nap_layout("chu_so")
    hang = {}
    for b in lay["boxes"]:
        hang.setdefault(b["row"], []).append((b["label"], b["rect"]))
    nhom = [v for _, v in sorted(hang.items())]
    rng = np.random.default_rng(1)
    crop, nhan, nguoi, tk = [], [], [], []
    for p in sorted((ROOT / "data" / "raw_digits").glob("D*.jpg")):
        kq = preprocess(str(p), lay)
        if not kq.ok:
            print(f"  {p.name}: từ chối {kq.ly_do}")
            continue
        xam = kq.anh_nan
        kh = khung_cua_anh(xam, [[r for _, r in h] for h in nhom])
        lab = [l for h in nhom for l, _ in h]
        chon = rng.choice(len(kh), 40, replace=False)              # 40 ô / trang để đo thống kê
        for i in chon:
            (x0, y0, x1, y1, ok), r = kh[i]
            if not ok:
                continue
            s = thong_ke(xam, (x0, y0, x1, y1, ok))
            if s["ink_px"] < ocr.NGUONG_IT_MUC:
                continue
            tk.append(s)
            xa, ya = x0 - LE + 2, y0 - LE + 2
            c = xam[ya:ya + int(round(H_O)) + 2 * LE, xa:xa + int(round(W_O)) + 2 * LE].copy()
            crop.append((c, (x0 - xa, y0 - ya, x1 - xa, y1 - ya, True)))
            nhan.append(int(lab[i]))
            nguoi.append(int(nguoi_viet(p.stem)))
        print(f"  {p.name}: xong")
    EVAL.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(EVAL / "o_that_mau.npz", anh=np.stack([c for c, _ in crop]), khung=np.array([k[:4] for _, k in crop]),
                        nhan=np.array(nhan), nguoi=np.array(nguoi))
    tom = tom_tat(tk)
    (EVAL / "thong_ke_o_that.json").write_text(json.dumps(tom, ensure_ascii=False, indent=1), encoding="utf-8")
    in_bang({"thật (trang D)": tom})


def tom_tat(tk: list[dict]) -> dict:
    out = {}
    for k in tk[0]:
        v = np.array([t[k] for t in tk], float)
        v = v[~np.isnan(v)]
        out[k] = [round(float(x), 3) for x in np.percentile(v, [5, 25, 50, 75, 95])]
    out["n"] = len(tk)
    return out


def in_bang(d: dict):
    ten = [k for k in next(iter(d.values())) if k != "n"]
    print(f"{'số đo (p5 / p25 / p50 / p75 / p95)':36s} " + " | ".join(f"{k} (n={v['n']})" for k, v in d.items()))
    for k in ten:
        print(f"  {k:34s} " + " | ".join(" / ".join(f"{x:g}" for x in v[k]) for v in d.values()))


# ------------------------------------------------------------------------------------------- nguồn chữ số
def nguon_chu_so():
    """(x, y, nguồn) chữ số gốc ĐÚNG CHIỀU (chưa chuẩn hoá) để vẽ: MNIST train (cùng 55 000 ảnh của huấn luyện trước, bỏ 5 000 val nội bộ)
    + EMNIST Digits train. nguồn 0 = MNIST, 1 = EMNIST."""
    import huan_luyen_ocr as H
    xtr, ytr, _, _ = H.doc_mnist()
    tr = np.random.default_rng(H.SEED).permutation(len(xtr))[5000:]
    e = np.load(EMNIST)
    x = np.concatenate([xtr[tr], e["x_train"]])
    y = np.concatenate([ytr[tr].astype(np.int64), e["y_train"]])
    return x, y, np.concatenate([np.zeros(len(tr), np.int8), np.ones(len(e["y_train"]), np.int8)])


def cmd_so_sanh(a):
    z = np.load(EVAL / "o_that_mau.npz")
    rng = np.random.default_rng(a.seed)
    x, y, ng = nguon_chu_so()
    # thống kê ô giả (n = 400) để so với thật
    tk, gia = [], []
    while len(tk) < 400:
        i = int(rng.integers(len(x)))
        r = ve_o(x[i], rng)
        if r is None:
            continue
        g, kh, rect = r
        o, ok = qua_duong_that(g, kh, rect)
        if not ok:
            continue
        tk.append(thong_ke(g, kh))
        gia.append((g, kh, o.anh28))
    that_tk = json.loads((EVAL / "thong_ke_o_that.json").read_text(encoding="utf-8"))
    tom = tom_tat(tk)
    in_bang({"thật (trang D)": that_tk, "giả": tom})
    (EVAL / "thong_ke_o_gia.json").write_text(json.dumps(tom, ensure_ascii=False, indent=1), encoding="utf-8")
    # lưới: hàng 1 = 8 ô thật (ảnh xám), hàng 2 = 28×28 của chúng; hàng 3 = 8 ô giả, hàng 4 = 28×28
    it = rng.choice(len(z["anh"]), 8, replace=False)
    H_, W_ = z["anh"].shape[1:]

    def o_xam(g):
        return cv2.copyMakeBorder(cv2.resize(g, (W_, H_)), 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=255)

    def o28(a28):
        nen = np.full((H_, W_), 255, np.uint8)                       # 28×28 phóng ×3, đặt giữa ô trắng cùng cỡ
        v = cv2.resize(255 - a28, (84, 84), interpolation=cv2.INTER_NEAREST)
        y0, x0 = (H_ - 84) // 2, (W_ - 84) // 2
        nen[y0:y0 + 84, x0:x0 + 84] = v
        return cv2.copyMakeBorder(nen, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=255)

    h1, h2 = [], []
    for i in it:
        g, kh = z["anh"][i], tuple(int(v) for v in z["khung"][i]) + (True,)
        o = ocr.cat_o(g, kh, (kh[0], kh[1], kh[2] - kh[0], kh[3] - kh[1]))
        h1.append(o_xam(g))
        h2.append(o28(o.anh28 if o.anh28 is not None else np.zeros((28, 28), np.uint8)))
    h3 = [o_xam(g) for g, _, _ in gia[:8]]
    h4 = [o28(a28) for _, _, a28 in gia[:8]]
    luoi = np.vstack([np.hstack(h) for h in (h1, h2, h3, h4)])
    luoi = cv2.resize(luoi, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    hd = np.full((40, luoi.shape[1]), 255, np.uint8)
    cv2.putText(hd, "Hang 1-2: O THAT (trang D) + 28x28   |   Hang 3-4: O GIA + 28x28", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 2)
    cv2.imencode(".png", np.vstack([hd, luoi]))[1].tofile(str(EVAL / "so_sanh_that_gia.png"))
    print(f"Ghi {EVAL / 'so_sanh_that_gia.png'}")


def cmd_sinh(a):
    x, y, ng = nguon_chu_so()
    rng = np.random.default_rng(a.seed)
    X, Y, N, bo = [], [], [], 0
    t0 = time.time()
    # lấy cân bằng theo nguồn: n/2 từ MNIST, n/2 từ EMNIST
    for nguon in (0, 1):
        idx = rng.permutation(np.nonzero(ng == nguon)[0])
        k = 0
        for i in idx:
            if k >= a.n // 2:
                break
            r = ve_o(x[i], rng)
            if r is None:
                bo += 1
                continue
            o, ok = qua_duong_that(*r)
            if not ok:
                bo += 1
                continue
            X.append(o.anh28)
            Y.append(int(y[i]))
            N.append(nguon)
            k += 1
    np.savez_compressed(EVAL / "o_gia.npz", x=np.stack(X), y=np.array(Y), nguon=np.array(N, np.int8),
                        tham_so=np.array(json.dumps(TS)), seed=np.array(a.seed))
    print(f"Ghi {EVAL / 'o_gia.npz'}: {len(X)} ô giả ({sum(N)} EMNIST, {len(N) - sum(N)} MNIST), loại {bo} ô "
          f"(trống / ít mực / không phải chữ số theo luật chạy thật); {time.time() - t0:.0f} s")
    print("  mỗi lớp:", np.bincount(Y, minlength=10).tolist())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["that", "so-sanh", "sinh"])
    ap.add_argument("--n", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    {"that": cmd_that, "so-sanh": cmd_so_sanh, "sinh": cmd_sinh}[a.lenh](a)
