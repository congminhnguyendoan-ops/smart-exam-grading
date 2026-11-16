"""
(Ghi chú lệnh AO, 16/11/2026: từ lệnh AN, models/ocr_cnn.json là CNN SÂU sau_2x2 (467 818 tham số). Chữ "CNN hiện tại" / số liệu "CNN" trong công cụ và kết quả này là CNN CŨ (105 866 tham số, SHA 6d87205c…) – mô hình lúc đó; bản sao lưu data/_eval/an/ocr_cnn_hien_tai_sao_luu.json. Chạy lại công cụ này sẽ đo mô hình đang triển khai, KHÔNG tái tạo số liệu cũ.)
ak_so_sanh_mo_rong.py - Lệnh AK: so sánh MỞ RỘNG CNN với 11 thuật toán khác, mức ô (R3) và mức hệ thống (R4), chi phí (R5).
Tiêu chí ĐĂNG KÝ TRƯỚC: docs/tieu_chi_so_sanh_mo_rong.md (commit 2e549da – trước công cụ này). CHỈ ĐO: không sửa models/*, mã hệ thống, CSDL.
Tái dùng giao thức lệnh AI (tools/ai_so_sanh_thuat_toan.py): cùng ảnh 28×28, 5 người viết, seed, mẫu con, hiệu chỉnh nhiệt độ.
Chỉ dev (MNIST, trang D001–D010, phiếu dev 0001–0028) + 13 ảnh giấy thật AG (chỉ ĐỌC để cắt ô, không gọi ag_cham_that.cham). Cần torch + scikit-learn.

  python tools/ak_so_sanh_mo_rong.py chay [--thuat-toan ...]  # E1 + E2b (mỗi đơn vị lưu ở data/_eval/ak/tam/, chạy tiếp được)
  python tools/ak_so_sanh_mo_rong.py ag-cat                   # cắt 117 ô của 13 ảnh AG -> data/_eval/ak/ag_o.npz + ag_o.json
  python tools/ak_so_sanh_mo_rong.py ag-doc                   # huấn luyện lại trên MNIST + 5 người, đọc ô AG -> tam/AG_*.npz
  python tools/ak_so_sanh_mo_rong.py bang                     # R3 / R4 / R5 -> ket_qua.json, ket_qua.md
  python tools/ak_so_sanh_mo_rong.py truc-tiep [--da-tinh-san] # chạy trực tiếp mô hình (người 1 giữ ra) -> truc_tiep.json (dùng cho demo_may_hoc.py)
  --thu <thư mục>: chạy thử mã trên dữ liệu tí hon vào thư mục nháp (KHÔNG phải kết quả)
"""
import argparse
import copy
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import ai_so_sanh_thuat_toan as A  # noqa: E402
import huan_luyen_ocr as H  # noqa: E402
import ocr_cai_tien as C  # noqa: E402
import ocr_do_luong as L  # noqa: E402

AK = ROOT / "data" / "_eval" / "ak"
TIEU_CHI = "docs/tieu_chi_so_sanh_mo_rong.md (commit 2e549da)"
A.AI, A.TAM = AK, AK / "tam"                               # mọi hàm cũ ghi vào thư mục AK, không đụng data/_eval/ai
SEED0, SEEDS, NGUOI, TAU, EPS = A.SEED0, A.SEEDS, A.NGUOI, A.TAU, A.EPS

CU = ("lr", "knn", "svm", "rf", "mlp", "cnn")
MOI_SK = ("dt", "nb", "hgb", "hogsvm")
MOI_NET = ("lenet", "cnnsau")
TAT_CA = CU + MOI_SK + MOI_NET
NET = ("cnn", "mlp") + MOI_NET
A.THUAT_TOAN.update({
    "dt": ("Decision Tree", [{"max_depth": d} for d in (10, 20, None)], True),
    "nb": ("Naive Bayes Gaussian", [{"var_smoothing": v} for v in (1e-9, 1e-3, 1e-1)], False),
    "hgb": ("HistGradientBoosting (100 vòng)", [{}], False),
    "hogsvm": ("HOG + SVM RBF", [{"C": c} for c in (1.0, 10.0)], False),
    "lenet": ("LeNet-5", [{}], True),
    "cnnsau": ("CNN sâu (2 khối × 2 conv)", [{}], True),
})
NHAN = {t: A.THUAT_TOAN[t][0] for t in TAT_CA}
NHAN["cnn"] = "CNN hiện tại (Conv16–Conv32–Dense64)"


# ------------------------------------------------------------------------------------------- mô hình scikit-learn mới
def tao_sk(ten, g, seed):
    if ten == "dt":
        from sklearn.tree import DecisionTreeClassifier
        return DecisionTreeClassifier(criterion="gini", max_depth=g["max_depth"], random_state=seed)
    if ten == "nb":
        from sklearn.naive_bayes import GaussianNB
        return GaussianNB(var_smoothing=g["var_smoothing"])
    if ten == "hgb":
        from sklearn.ensemble import HistGradientBoostingClassifier
        return HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, early_stopping=False, random_state=seed)
    if ten == "hogsvm":
        from ak_hog import HogSVM
        return HogSVM(g["C"])
    return _tao_cu(ten, g, seed)


def diem_sk(ten, m, X):
    if ten in ("dt", "hgb"):
        return np.log(m.predict_proba(X) + EPS)
    if ten == "nb":
        return m.predict_log_proba(X)
    if ten == "hogsvm":
        return m.decision_function(X)
    return _diem_cu(ten, m, X)


_tao_cu, _diem_cu = A.tao_sk, A.diem_sk
A.tao_sk, A.diem_sk = tao_sk, diem_sk


# ------------------------------------------------------------------------------------------- mạng nơ-ron
def tao_lenet():
    torch, nn, F = H._torch()

    class LeNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.c1, self.c2 = nn.Conv2d(1, 6, 5, padding=2), nn.Conv2d(6, 16, 5)
            self.f1, self.f2, self.f3 = nn.Linear(400, 120), nn.Linear(120, 84), nn.Linear(84, 10)

        def forward(self, x):
            x = F.max_pool2d(F.relu(self.c1(x)), 2)
            x = F.max_pool2d(F.relu(self.c2(x)), 2)
            return self.f3(F.relu(self.f2(F.relu(self.f1(x.flatten(1))))))
    return LeNet()


def tao_cnn_sau():
    torch, nn, F = H._torch()

    class CNNSau(nn.Module):
        def __init__(self):
            super().__init__()
            self.a1, self.a2 = nn.Conv2d(1, 32, 3, padding=1), nn.Conv2d(32, 32, 3, padding=1)
            self.b1, self.b2 = nn.Conv2d(32, 64, 3, padding=1), nn.Conv2d(64, 64, 3, padding=1)
            self.d1, self.d2, self.drop = nn.Linear(3136, 128), nn.Linear(128, 10), nn.Dropout(0.3)

        def forward(self, x):
            x = F.max_pool2d(F.relu(self.a2(F.relu(self.a1(x)))), 2)
            x = F.max_pool2d(F.relu(self.b2(F.relu(self.b1(x)))), 2)
            return self.d2(self.drop(F.relu(self.d1(x.flatten(1)))))
    return CNNSau()


def tao_mang(ten):
    return {"cnn": H.tao_cnn, "mlp": A.tao_mlp, "lenet": tao_lenet, "cnnsau": tao_cnn_sau}[ten]()


def pre_net(ten, seed, ghi):
    """Tiền huấn luyện MNIST 55 000 (10 epoch, Adam 2e-3 + cosine, lô 128 mặc định) – đúng quy trình CNN; CNN dùng bộ đệm Tuần 6."""
    torch, _, _ = H._torch()
    if ten == "cnn":
        m = H.tao_cnn()
        m.load_state_dict(torch.load(C.CAP / f"pre_mnist_co_ban_{seed}.pt"))
        ghi["pre"] = f"bộ đệm {C.CAP.name}/pre_mnist_co_ban_{seed}.pt"
        return m.eval()
    f = A.TAM / f"pre_{ten}_{seed}.pt"
    if f.exists():
        m = tao_mang(ten)
        m.load_state_dict(torch.load(f))
        return m.eval()
    x, y = C.du_lieu_truoc("mnist")
    if A.THU:
        x, y = x[:3000], y[:3000]
    t0 = time.time()
    m = H.huan_luyen_cnn(x, y, C.PRE["epochs"], C.PRE["lr"], seed, mo_hinh=tao_mang(ten))
    ghi["pre_giay"] = round(time.time() - t0, 1)
    A.TAM.mkdir(parents=True, exist_ok=True)
    torch.save(m.state_dict(), f)
    return m


def net_e1(ten, seed, D):
    ghi = {"thi_nghiem": "E1", "thuat_toan": ten, "seed": seed}
    m = pre_net(ten, seed, ghi)
    ghi["so_tham_so"], ghi["n_huan_luyen"] = A.so_tham_so(m), len(D["mnist_tr"][1])
    return {b: H.logits(m, D[b][0]) for b in ("mnist_va", "mnist_te", "emnist_chuan", "emnist_tho")}, ghi


def net_e2b(ten, seed, D):
    torch, _, _ = H._torch()
    xt, yt, nt = D["trang"]
    ghi = {"thi_nghiem": "E2b", "thuat_toan": ten, "seed": seed, "theo_fold": {}}
    pre = pre_net(ten, seed, ghi)
    lt, lp = C.oof(pre, "co_ban", seed)                                  # tinh chỉnh 5 fold theo người – GIỐNG HỆT quy trình cũ
    if ten == "cnn":
        z0 = np.load(C.CAP / f"oof_g0_goc_{seed}.npz")
        ch = max(float(np.abs(z0["trang"] - lt).max()), float(np.abs(z0["phieu"] - lp).max()))
        ghi["chenh_logit_so_voi_bo_dem_g0_goc"] = ch
        if ch > 1e-4 and not A.THU:
            sys.exit(f"DỪNG: CNN E2b seed {seed} khác bộ đệm oof_g0_goc ({ch:.3g}) – tiêu chí mục 1")
    if seed == SEED0:                                                    # mô hình "người 1 giữ ra" – chỉ để trình diễn trực tiếp + đo kích thước
        m1 = H.huan_luyen_cnn(xt[nt != 1], yt[nt != 1], C.FT["epochs"], C.FT["lr"], seed, mo_hinh=copy.deepcopy(pre), batch=C.FT["batch"])
        ghi["so_tham_so"] = A.so_tham_so(m1)
        torch.save(m1.state_dict(), A.TAM / f"mo_hinh_E2b_{ten}_nguoi1.pt")
    return {"trang": lt[D["idx_trang"]], "phieu": lp[D["idx_phieu"]]}, ghi


_e1_cu, _e2_cu = A.e1, A.e2


def e1(ten, seed, D):
    if ten in NET:
        return net_e1(ten, seed, D)
    if ten == "hogsvm":                                                  # như SVM: mẫu con 20 000 (tiêu chí mục 1 + AI mục 2)
        x, y = D["mnist_tr"]
        i = A.mau_con(y, A.N_SVM_E1, SEED0)
        z, ghi = _e1_cu(ten, seed, dict(D, mnist_tr=(x[i], y[i])))
        ghi["mau_con"] = f"{len(i)} / {len(y)} (phân tầng, seed {SEED0})"
        return z, ghi
    return _e1_cu(ten, seed, D)


def e2(bien_the, ten, seed, D):
    assert bien_the == "b", "AK chỉ chạy E2b"
    return net_e2b(ten, seed, D) if ten in NET else _e2_cu(bien_the, ten, seed, D)


A.e1, A.e2 = e1, e2


# Thuật toán KHÔNG chạy E2b vì quá giới hạn 30 phút/thuật toán của tiêu chí (đo thật: một lần fit trên 13,9 nghìn mẫu ≈ 40 s khi máy rảnh; E2b cần 5 × (3 × 4 + 1) = 65 lần fit ≈ 44 phút).
# Không cắt giảm âm thầm (không đổi lưới w, không bỏ kiểm định lồng): ghi rõ trong báo cáo.
KHONG_CHAY_E2B = {"hgb": "ước tính ≈ 44 phút (65 lần fit × ≈ 40 s trên 13,9 nghìn mẫu × 784 chiều, đo trước khi chạy) > giới hạn 30 phút của tiêu chí; "
                         "không cắt giảm lưới w / kiểm định lồng nên không chạy; chỉ có E1"}


def cmd_chay(a):
    A.THU = bool(a.thu)
    A.TAM.mkdir(parents=True, exist_ok=True)
    A.cmd_chay(argparse.Namespace(thi_nghiem=["E1"], thuat_toan=a.thuat_toan))
    A.cmd_chay(argparse.Namespace(thi_nghiem=["E2b"], thuat_toan=[t for t in a.thuat_toan if t not in KHONG_CHAY_E2B]))
    (A.TAM / "khong_chay.json").write_text(json.dumps({t: r for t, r in KHONG_CHAY_E2B.items() if t in a.thuat_toan}, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------------------------------- R4(b): cắt 117 ô giấy thật AG
AG_ANH = ROOT / "data" / "anh_that_ag"
AG_KB = ROOT / "data" / "_eval" / "ag" / "kich_ban.json"


def cmd_ag_cat(a):
    """Chỉ ĐỌC 13 ảnh AG + kịch bản (nhãn SBD / mã đề): preprocess -> doc_phieu -> doc_chu_so. KHÔNG gọi ag_cham_that.cham, không ghi gì ngoài data/_eval/ak/."""
    import ag_cham_that as G
    from cv_engine import ocr
    from cv_engine.omr import doc_phieu, nap_mo_hinh
    from cv_engine.preprocessing import nap_layout, preprocess
    kb = json.loads(AG_KB.read_text(encoding="utf-8"))
    ds_sbd, ds_ma = set(kb["ky_thi_danh_sach"]["sbd"]), set(kb["ky_thi_danh_sach"]["ma_de"])
    lay, mh, mho = nap_layout("phieu"), nap_mo_hinh(), ocr.nap_mo_hinh_ocr()
    anh, o, xs = [], [], []
    for p, ma, dk in G.liet_ke(AG_ANH)[0]:
        kq = preprocess(str(p), lay)
        rec = {"anh": p.name, "to": ma, "dieu_kien": dk, "tu_choi": "" if kq.ok else kq.ly_do}
        if not kq.ok:
            anh.append(rec)
            continue
        om, hv = doc_phieu(kq, lay, mh), ocr.doc_chu_so(kq, lay, mho)
        rec["sbd_trong"] = None if "?" in om.sbd else om.sbd in ds_sbd
        rec["ma_trong"] = None if "?" in om.ma_de else om.ma_de in ds_ma
        for ten, oc, hc in (("sbd", om.sbd_cot, hv.sbd), ("ma_de", om.ma_de_cot, hv.ma_de)):
            for i, (b, h) in enumerate(zip(oc, hc)):
                doc = h.chu_so != "?"
                o.append({"anh_idx": len(anh), "truong": ten, "i": i, "truth": kb["to"][ma][ten][i], "b": b.chu_so, "bcx": bool(b.can_xem),
                          "cnn_he_thong": h.chu_so, "o_trong": bool(h.o_trong), "loi_o": h.loi_o, "doc": doc, "x": len(xs) if doc else -1})
                if doc:
                    xs.append(h.anh28)
        anh.append(rec)
    AK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(AK / "ag_o.npz", x=np.stack(xs).astype(np.uint8))
    (AK / "ag_o.json").write_text(json.dumps({"anh": anh, "o": o}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"AG: {len(anh)} ảnh ({sum(1 for r in anh if r['tu_choi'])} bị từ chối), {len(o)} ô, {len(xs)} ô qua bộ đọc chữ số")


def sieu_tham_so_day_du(ten):
    """g từ E1; w = giá trị chọn nhiều nhất qua 5 fold E2b, hoà -> nhỏ hơn (tiêu chí mục 3b)."""
    g = A.chon_e1(ten, SEEDS[0] if A.THUAT_TOAN[ten][2] else SEED0)
    ws = [r["chon"]["w"] for r in json.loads((A.TAM / f"E2b_{ten}_{SEED0}.json").read_text(encoding="utf-8"))["theo_fold"].values()]
    dem = {w: ws.count(w) for w in set(ws)}
    return g, min(dem, key=lambda w: (-dem[w], w)), dem


def cmd_ag_doc(a):
    from cv_engine import ocr
    D = A.du_lieu()
    x_ag = np.load(AK / "ag_o.npz")["x"]
    X_ag = A.vec(x_ag)
    xm, ym = D["mnist_tr"]
    xt, yt, _ = D["trang"]                                            # trang D của CẢ 5 người
    ghi = {}
    p = ocr.du_doan_xac_suat(ocr.nap_mo_hinh_ocr(), x_ag)             # CNN triển khai: xác suất đã hiệu chỉnh -> lưu log p (T = 1)
    A.TAM.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(A.TAM / "AG_cnn_trien_khai_2026.npz", z=np.log(p + EPS))
    for ten in TAT_CA:
        if ten in KHONG_CHAY_E2B:
            continue
        for sd in (SEEDS if A.THUAT_TOAN[ten][2] else (SEED0,)):
            f = A.TAM / f"AG_{ten}_{sd}.npz"
            if f.exists():
                continue
            t0 = time.time()
            if ten in NET:
                pre = pre_net(ten, sd, {})
                m = H.huan_luyen_cnn(xt, yt, C.FT["epochs"], C.FT["lr"], sd, mo_hinh=copy.deepcopy(pre), batch=C.FT["batch"])
                z = H.logits(m, x_ag)
                ghi[f"{ten}_{sd}"] = "mạng: tiền huấn luyện MNIST + tinh chỉnh trang D (5 người)"
            else:
                g, w, dem = sieu_tham_so_day_du(ten)
                im = A.mau_con(ym, A.N_MNIST_E2B, SEED0)
                X = np.concatenate([A.vec(xm[im]), A.vec(xt)])
                y = np.concatenate([ym[im], yt])
                wt = np.concatenate([np.ones(len(im)), np.full(len(yt), float(w))])
                m = A.fit_sk(ten, g, sd, X, y, wt, {})
                z = A.diem_sk(ten, m, X_ag)
                ghi[f"{ten}_{sd}"] = {"g": g, "w": w, "w_qua_5_fold": dem}
            np.savez_compressed(f, z=z)
            print(f"  AG {ten} seed {sd}: {time.time() - t0:.0f} s")
    (A.TAM / "AG_ghi.json").write_text(json.dumps(ghi, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


# ------------------------------------------------------------------------------------------- R4: đối chiếu hai kênh với bộ đọc thay thế (THUẦN)
def he_thong(o: list, truong: dict, P: np.ndarray) -> dict:
    """o: danh sách ô {f, i, truth, b, bcx, doc, o_trong, loi_o}; truong[f] = {loai, trong_ds}; P [N,10] xác suất của thuật toán.
    Mỗi trường: viết tay đúng cả chuỗi (argmax mọi ô; ô không qua bộ đọc = '?'), rồi doi_chieu_cot / doi_chieu_truong của hệ thống (τ_khop 0,5)."""
    from cv_engine import ocr
    theo = {}
    for k, c in enumerate(o):
        theo.setdefault(c["f"], []).append((c["i"], k))
    r = {"sbd": {"n": 0, "hw_dung": 0}, "ma_de": {"n": 0, "hw_dung": 0}, "nhan": 0, "sai_khong_co": 0, "can_xem": 0, "co_thua": 0, "ca_sai_khong_co": []}
    for f, ks in theo.items():
        ks = [k for _, k in sorted(ks)]
        tr = "".join(o[k]["truth"] for k in ks)
        hw = "".join(str(int(P[k].argmax())) if o[k]["doc"] else "?" for k in ks)
        loai = truong[f]["loai"]
        r[loai]["n"] += 1
        r[loai]["hw_dung"] += int(hw == tr)
        cot = [ocr.doi_chieu_cot(o[k]["b"], o[k]["bcx"], str(int(P[k].argmax())) if o[k]["doc"] else "?", float(P[k].max()) if o[k]["doc"] else 0.0,
                                 True, o[k]["o_trong"], 0.5, o[k]["loi_o"]) for k in ks]
        gia, chac, _ = ocr.doi_chieu_truong(cot, truong[f]["trong_ds"])
        nhan = bool(chac) and truong[f]["trong_ds"] is True
        r["nhan"] += int(nhan)
        r["can_xem"] += int(not nhan)
        if nhan and gia != tr:
            r["sai_khong_co"] += 1
            r["ca_sai_khong_co"].append({"truong": str(f), "doc": gia, "dung": tr, "viet_tay": hw})
        if not nhan and gia == tr:
            r["co_thua"] += 1
    return r


def gop_he_thong(rs: list[dict]) -> dict:
    """Gộp seed: tỉ lệ TB; đếm 'sai không cờ' CỘNG các seed (như lệnh AI)."""
    n = {k: rs[0][k]["n"] for k in ("sbd", "ma_de")}
    hw = {k: float(np.mean([r[k]["hw_dung"] for r in rs])) for k in n}
    return {"n_seed": len(rs), "n_sbd": n["sbd"], "n_ma_de": n["ma_de"], "hw_sbd": hw["sbd"] / n["sbd"], "hw_ma_de": hw["ma_de"] / n["ma_de"],
            "hw_gop": (hw["sbd"] + hw["ma_de"]) / (n["sbd"] + n["ma_de"]),
            "nhan": float(np.mean([r["nhan"] for r in rs])), "can_xem": float(np.mean([r["can_xem"] for r in rs])),
            "co_thua": float(np.mean([r["co_thua"] for r in rs])), "sai_khong_co_cong": int(sum(r["sai_khong_co"] for r in rs)),
            "ca_sai_khong_co": [c for r in rs for c in r["ca_sai_khong_co"]]}


def r4a(nap_e2b, yt):
    """(a) 504 ô phiếu dev: OOF E2b + kênh bubble data/_ocr/omr_dev.json (như ocr_do_luong.cmd_bao_cao). Trả {tên: gop_he_thong}."""
    meta = H.tap_do("anh_nan")["phieu"]["meta"]
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    o, truong = [], {}
    for r in meta:
        anh, lo, vt = r["anh"], r["loai"], int(r["vi_tri"])
        b, bcx = (omr[anh][lo][vt] if "tu_choi" not in omr[anh] else ["?", True])
        o.append({"f": (anh, lo), "i": vt, "truth": str(int(r["nhan"])), "b": b, "bcx": bool(bcx), "doc": True, "o_trong": False, "loi_o": ""})
        truong[(anh, lo)] = {"loai": lo, "trong_ds": True}
    out = {}
    for ten, lan in nap_e2b.items():
        rs = []
        for sd, z, _ in lan:
            T = L.chon_nhiet(z["trang"], yt)
            rs.append(he_thong(o, truong, L.softmax(z["phieu"] / T)))
        out[ten] = gop_he_thong(rs)
    return out


def r4b(nap_ag, yt):
    """(b) 13 ảnh giấy thật AG; nap_ag[tên] = [(seed, z_ag, T)]. T = nhiệt độ OOF trang D cùng thuật toán / seed (CNN triển khai: T = 1, đã trong mô hình)."""
    j = json.loads((AK / "ag_o.json").read_text(encoding="utf-8"))
    anh = j["anh"]
    o, truong = [], {}
    for c in j["o"]:
        a = anh[c["anh_idx"]]
        f = (c["anh_idx"], c["truong"])
        o.append({"f": f, "i": c["i"], "truth": c["truth"], "b": c["b"], "bcx": c["bcx"], "doc": c["doc"], "o_trong": c["o_trong"], "loi_o": c["loi_o"], "x": c["x"]})
        truong[f] = {"loai": c["truong"], "trong_ds": a["sbd_trong"] if c["truong"] == "sbd" else a["ma_trong"]}
    out = {}
    for ten, lan in nap_ag.items():
        rs = []
        for sd, z, T in lan:
            Pz = L.softmax(z / T)
            P = np.stack([Pz[c["x"]] if c["doc"] else np.full(10, 0.1) for c in o])
            rs.append(he_thong(o, truong, P))
        out[ten] = gop_he_thong(rs)
    return out, {"n_anh": len(anh), "n_tu_choi": sum(1 for a_ in anh if a_["tu_choi"]), "n_o": len(o), "n_o_doc": sum(c["doc"] for c in o)}


# ------------------------------------------------------------------------------------------- R5: kích thước + thời gian
def mo_hinh_nguoi1(ten):
    """Nạp mô hình 'người 1 giữ ra' (seed 2026) -> (hàm dự đoán z cho ảnh uint8 [N,28,28], số byte, số tham số)."""
    if ten in NET:
        torch, _, _ = H._torch()
        f = A.TAM / f"mo_hinh_E2b_{ten}_nguoi1.pt"
        m = tao_mang(ten)
        m.load_state_dict(torch.load(f))
        m.eval()
        return (lambda x: H.logits(m, x)), f.stat().st_size, A.so_tham_so(m)
    f = A.TAM / f"mo_hinh_E2b_{ten}_nguoi1.pkl"
    m = pickle.loads(f.read_bytes())
    if ten == "rf":
        m.n_jobs = 1
    if ten == "knn":
        m.nn.n_jobs = 1
    return (lambda x: A.diem_sk(ten, m, A.vec(x))), f.stat().st_size, None


def r5(D, co: list) -> dict:
    from cv_engine import ocr
    torch, _, _ = H._torch()
    torch.set_num_threads(1)
    xt = D["trang"][0][:300]
    out = {}
    for ten in co:
        f, byte, n_tp = mo_hinh_nguoi1(ten)
        out[ten] = {"byte": byte, "so_tham_so": n_tp, "ms_moi_o": A.do_tg(f, xt),
                    "do_bang": "PyTorch CPU 1 luồng" if ten in NET else "scikit-learn predict, 1 luồng (kể cả HOG cho HOG+SVM)"}
        if ten in NET:
            out[ten]["byte"] = 4 * n_tp                                              # trọng số float32
    mh = ocr.nap_mo_hinh_ocr()
    out["cnn"]["ms_moi_o_numpy_trien_khai"] = A.do_tg(lambda v: ocr.du_doan_xac_suat(mh, v), xt)
    out["cnn"]["byte_json_trien_khai"] = (ROOT / "models" / "ocr_cnn.json").stat().st_size
    return out


# ------------------------------------------------------------------------------------------- bảng
def pt(v):
    return f"{100 * v:.2f}%"


def cmd_bang(a):
    from scipy.stats import binomtest
    D = A.du_lieu()
    _, yt, nt = D["trang"]
    _, yp, npp = D["phieu"]
    khong = json.loads((A.TAM / "khong_chay.json").read_text(encoding="utf-8")) if (A.TAM / "khong_chay.json").exists() else {}
    co = [t for t in TAT_CA if t not in khong and (A.TAM / f"E2b_{t}_{SEED0}.npz").exists()]
    lan = {t: A.nap("E2b", t) for t in co}
    # ---- R3
    rs = {t: [A.chi_so_e2(z["trang"], z["phieu"], yt, nt, yp, npp) for _, z, _ in lan[t]] for t in co}
    e2b = {t: A.gop_seed(rs[t]) for t in co}
    cu = json.loads((ROOT / "data" / "_eval" / "ai" / "ket_qua.json").read_text(encoding="utf-8"))["E2b"]
    doi_chieu = {t: {"cu": cu[t]["macro"], "moi": e2b[t]["macro"], "chenh_diem": round(100 * (e2b[t]["macro"] - cu[t]["macro"]), 3)} for t in CU if t in e2b}
    khac = [t for t, v in doi_chieu.items() if abs(v["chenh_diem"]) > 0.05]
    tot = max(e2b, key=lambda t: e2b[t]["macro"])
    chenh = 100 * (e2b[tot]["macro"] - e2b["cnn"]["macro"])
    r3 = {"tot_nhat": tot, "macro_tot_nhat": e2b[tot]["macro"], "macro_cnn": e2b["cnn"]["macro"], "chenh_diem": round(chenh, 3), "dat": bool(chenh <= 1.0 + 1e-9),
          "dung_hon_cnn": sorted([(t, round(100 * (v["macro"] - e2b["cnn"]["macro"]), 3)) for t, v in e2b.items() if t != "cnn" and v["macro"] > e2b["cnn"]["macro"]], key=lambda x: -x[1]),
          "khong_trung_ket_qua_cu": khac}
    dung_cnn = rs["cnn"][0]["dung_tung_o"]
    khac_nhat = max((t for t in co if t != "cnn"), key=lambda t: e2b[t]["macro"])
    dung_k = rs[khac_nhat][0]["dung_tung_o"]
    b, c = int((dung_cnn & ~dung_k).sum()), int((~dung_cnn & dung_k).sum())
    r3["dau_cap_theo_o"] = {"so_sanh_voi": khac_nhat, "cnn_dung_kia_sai": b, "cnn_sai_kia_dung": c,
                            "p": float(binomtest(b, b + c, 0.5).pvalue) if b + c else 1.0, "ghi_chu": "seed 2026, trang D, phụ – không quyết định"}
    # ---- R4(a)
    nap_a = {t: lan[t] for t in co}
    ra = r4a(nap_a, yt)
    # ---- R4(b)
    kq_b, meta_b = {}, None
    if (AK / "ag_o.json").exists() and (A.TAM / "AG_cnn_trien_khai_2026.npz").exists():
        nap_b = {"cnn_trien_khai": [(SEED0, np.load(A.TAM / "AG_cnn_trien_khai_2026.npz")["z"], 1.0)]}
        for t in co:
            ls = []
            for sd, z, _ in lan[t]:
                f = A.TAM / f"AG_{t}_{sd}.npz"
                if f.exists():
                    ls.append((sd, np.load(f)["z"], L.chon_nhiet(z["trang"], yt)))
            if ls:
                nap_b[t] = ls
        kq_b, meta_b = r4b(nap_b, yt)
    # ---- kết luận R4
    def ket_luan(bang, tham_chieu):
        khac_ = {t: v for t, v in bang.items() if t not in ("cnn", "cnn_trien_khai")}
        t_ = max(khac_, key=lambda k: khac_[k]["hw_gop"])
        ch = 100 * (khac_[t_]["hw_gop"] - bang[tham_chieu]["hw_gop"])
        return {"tham_chieu": tham_chieu, "tot_nhat_khac": t_, "hw_tot_nhat": khac_[t_]["hw_gop"], "hw_cnn": bang[tham_chieu]["hw_gop"], "chenh_diem": round(ch, 3),
                "dat": bool(ch <= 1.0 + 1e-9), "dung_hon_cnn": sorted([(k, round(100 * (v["hw_gop"] - bang[tham_chieu]["hw_gop"]), 3)) for k, v in khac_.items()
                                                                       if v["hw_gop"] > bang[tham_chieu]["hw_gop"]], key=lambda x: -x[1])}
    r4 = {"a": ket_luan(ra, "cnn"), "b": ket_luan(kq_b, "cnn_trien_khai") if kq_b else None}
    r5_ = r5(D, co)
    ktd = AK / "kiem_tat_dinh.json"
    kq = {"kiem_tat_dinh_ghi_chu": (lambda r: f"Nguyên nhân MLP lệch: huấn luyện KHÔNG tất định trên máy này – tiền huấn luyện MLP seed 2026 hai lần giống hệt cho logit lệch tối đa {r['max_chenh_logit']:.1f}, {r['so_nhan_khac_tren_2000']}/2000 nhãn khác (`ak_so_sanh_mo_rong.py kiem-tat-dinh`). Độ lệch 0,17 điểm là nhiễu chạy lại, không phải lỗi quy trình; MLP cách top > 5 điểm nên không đổi kết luận. Mọi mạng huấn luyện lại (MLP, LeNet-5, CNN sâu) chịu cùng nhiễu; CNN hiện tại dùng bộ đệm tiền huấn luyện của Tuần 6 nên trùng tuyệt đối.")(json.loads(ktd.read_text(encoding="utf-8"))) if ktd.exists() else "", "tieu_chi": TIEU_CHI, "ngay": time.strftime("%Y-%m-%d %H:%M"), "khong_chay_E2b": khong, "E2b": e2b, "doi_chieu_ket_qua_ai": doi_chieu, "R3": r3,
          "R4a": ra, "R4b": kq_b, "R4b_meta": meta_b, "R4": r4, "R5": r5_, "nhan": NHAN,
          "E1": {t: {k: v for k, v in json.loads((A.TAM / f"E1_{t}_{SEEDS[0] if A.THUAT_TOAN[t][2] else SEED0}.json").read_text(encoding="utf-8")).items()
                     if k in ("chon", "giay", "mau_con", "so_tham_so")} for t in TAT_CA},
          "chon_sieu_tham_so": {t: {sd: ghi.get("sieu_tham_so_tu_E1") for sd, _, ghi in lan[t]} for t in co}}
    for t in co:
        kq["E2b"][t].pop("confusion_cong", None)
    AK.mkdir(parents=True, exist_ok=True)
    (AK / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (AK / "ket_qua.md").write_text(bao_cao(kq), encoding="utf-8")
    print(f"Ghi {AK / 'ket_qua.md'}  |  R3 {'ĐẠT' if r3['dat'] else 'KHÔNG ĐẠT'} ({r3['chenh_diem']:+.2f})  |  R4a {'ĐẠT' if r4['a']['dat'] else 'KHÔNG ĐẠT'} ({r4['a']['chenh_diem']:+.2f})"
          + (f"  |  R4b {'ĐẠT' if r4['b']['dat'] else 'KHÔNG ĐẠT'} ({r4['b']['chenh_diem']:+.2f})" if r4["b"] else "  |  R4b: không có dữ liệu"))


def bao_cao(kq: dict) -> str:
    E, N = kq["E2b"], kq["nhan"]
    thu_tu = sorted(E, key=lambda t: -E[t]["macro"])
    L_ = [f"# So sánh mở rộng CNN với các thuật toán khác (lệnh AK)", "", f"Tiêu chí đăng ký trước: `{kq['tieu_chi']}`. Chạy: `python tools/ak_so_sanh_mo_rong.py chay` → `ag-cat` → `ag-doc` → `bang`.", "",
          "## R3 – mức ô (E2b: MNIST + ô thật, học 4 người, đo người thứ 5; trang D; TB 5 người ± SD giữa người; TB 3 seed với thuật toán ngẫu nhiên)", "",
          "| Thuật toán | E2b macro | Người 1 | Người 2 | Người 3 | Người 4 | Người 5 | Ô phiếu dev (504 ô) | Sai mà tự tin (p ≥ 0,5) | Sai tổng | Trùng kết quả lệnh AI |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in thu_tu:
        e = E[t]
        dc = kq["doi_chieu_ket_qua_ai"].get(t)
        L_.append(f"| {'**' + N[t] + '**' if t == 'cnn' else N[t]} | **{pt(e['macro'])}** ± {100 * e['sd_nguoi']:.2f} | " + " | ".join(pt(e["theo_nguoi"][str(k)]) for k in NGUOI)
                  + f" | {pt(e['phieu'])} | {e['sai_tu_tin_trang_cong']} ({e['n_seed']} seed) | {e['sai_trang_cong']} | " + (f"chênh {dc['chenh_diem']:+.3f} điểm" if dc else "(mới)") + " |")
    for t, ly in kq["khong_chay_E2b"].items():
        L_.append(f"| {N[t]} | **KHÔNG CHẠY E2b** | – | – | – | – | – | – | – | – | {ly} |")
    r3 = kq["R3"]
    L_ += ["", f"**R3 {'ĐẠT' if r3['dat'] else 'KHÔNG ĐẠT'}**: tốt nhất = **{N[r3['tot_nhat']]}** ({pt(r3['macro_tot_nhat'])}); CNN {pt(r3['macro_cnn'])}; CNN thấp hơn tốt nhất **{r3['chenh_diem']:.2f} điểm** (ngưỡng 1,0).",
           (f"Đúng hơn CNN: " + ", ".join(f"{N[t]} (+{d} điểm)" for t, d in r3["dung_hon_cnn"]) + ".") if r3["dung_hon_cnn"] else "Không thuật toán nào đúng hơn CNN.",
           f"Phụ (không quyết định): kiểm định dấu cặp theo ô, seed 2026, CNN so với {N[r3['dau_cap_theo_o']['so_sanh_voi']]}: CNN đúng / kia sai {r3['dau_cap_theo_o']['cnn_dung_kia_sai']}, "
           f"CNN sai / kia đúng {r3['dau_cap_theo_o']['cnn_sai_kia_dung']}, p = {r3['dau_cap_theo_o']['p']:.3g}.",
           ("**Cảnh báo**: kết quả chạy lại KHÔNG trùng lệnh AI ở: " + ", ".join(r3["khong_trung_ket_qua_cu"])) if r3["khong_trung_ket_qua_cu"]
           else "Chạy lại 6 thuật toán cũ **trùng** kết quả lệnh AI (|chênh macro| ≤ 0,05 điểm mọi thuật toán).",
           kq.get("kiem_tat_dinh_ghi_chu", ""), ""]

    def bang4(b, tieu_de, don_vi):
        o = [tieu_de, "", f"| Thuật toán | Viết tay đúng cả SBD (6) | Đúng cả mã đề (3) | **Đúng cả chuỗi (gộp)** | Trường nhận | Cần xem | Cờ thừa | **Sai mà không cờ** (cộng seed) |", "|---|---|---|---|---|---|---|---|"]
        for t in sorted(b, key=lambda k: -b[k]["hw_gop"]):
            v = b[t]
            ten = N.get(t, "CNN triển khai (`models/ocr_cnn.json`)" if t == "cnn_trien_khai" else t)
            o.append(f"| {ten} | {pt(v['hw_sbd'])} | {pt(v['hw_ma_de'])} | **{pt(v['hw_gop'])}** | {v['nhan']:.1f} / {v['n_sbd'] + v['n_ma_de']} | {v['can_xem']:.1f} | {v['co_thua']:.1f} | **{v['sai_khong_co_cong']}** |")
        return o
    L_ += bang4(kq["R4a"], "## R4(a) – 504 ô SBD / mã đề phiếu dev (56 SBD + 56 mã đề = 112 trường; OOF E2b; kênh bubble = OMR dev)", "")
    r4a_ = kq["R4"]["a"]
    L_ += ["", f"**R4(a) {'ĐẠT' if r4a_['dat'] else 'KHÔNG ĐẠT'}**: tốt nhất (ngoài CNN) = {N[r4a_['tot_nhat_khac']]} {pt(r4a_['hw_tot_nhat'])}; CNN {pt(r4a_['hw_cnn'])}; chênh {r4a_['chenh_diem']:+.2f} điểm (ngưỡng 1,0; 1 trường = 0,89 điểm).",
           "Ca sai mà không cờ (mọi thuật toán): " + (", ".join(f"{N[t]}: {len(v['ca_sai_khong_co'])}" for t, v in kq["R4a"].items() if v["ca_sai_khong_co"]) or "không có") + ".", ""]
    if kq["R4b"]:
        m = kq["R4b_meta"]
        L_ += bang4(kq["R4b"], f"## R4(b) – ảnh giấy thật AG ({m['n_anh']} ảnh, {m['n_tu_choi']} bị từ chối, {m['n_o']} ô, {m['n_o_doc']} ô qua bộ đọc; trường = {m['n_anh'] * 2 - 2 * m['n_tu_choi']})", "")
        r4b_ = kq["R4"]["b"]
        L_ += ["", f"**R4(b) {'ĐẠT' if r4b_['dat'] else 'KHÔNG ĐẠT'}**: tốt nhất (ngoài CNN) = {N[r4b_['tot_nhat_khac']]} {pt(r4b_['hw_tot_nhat'])}; CNN triển khai {pt(r4b_['hw_cnn'])}; chênh {r4b_['chenh_diem']:+.2f} điểm "
               f"(ngưỡng 1,0; 1 trường = 3,8 điểm → rất thô).",
               "Ca sai mà không cờ: " + (", ".join(f"{N.get(t, t)}: {len(v['ca_sai_khong_co'])}" for t, v in kq["R4b"].items() if v["ca_sai_khong_co"]) or "không có") + ".", ""]
    else:
        L_ += ["## R4(b)", "", "**Không có dữ liệu** (chưa chạy `ag-cat` / `ag-doc`).", ""]
    L_ += ["## R5 – chi phí (chỉ báo cáo, không dùng để loại)", "", "| Thuật toán | Kích thước | Số tham số | ms / ô (lô 1, CPU) | Đo bằng |", "|---|---|---|---|---|"]
    for t in sorted(kq["R5"], key=lambda k: kq["R5"][k]["byte"]):
        v = kq["R5"][t]
        mb = v["byte"] / 1e6
        extra = f" (NumPy triển khai: {v['ms_moi_o_numpy_trien_khai']:.2f})" if "ms_moi_o_numpy_trien_khai" in v else ""
        L_.append(f"| {N[t]} | {mb:.2f} MB | {v['so_tham_so'] if v['so_tham_so'] else '–'} | {v['ms_moi_o']:.2f}{extra} | {v['do_bang']} |")
    L_ += ["", "Siêu tham số đã chọn (E1, kiểm định MNIST nội bộ): " + "; ".join(f"{N[t]} → {kq['E1'][t].get('chon')}" for t in TAT_CA if kq['E1'][t].get("chon")), ""]
    return "\n".join(L_)


# ------------------------------------------------------------------------------------------- chạy trực tiếp (dùng cho demo_may_hoc.py --so-sanh-truc-tiep)
def cmd_truc_tiep(a):
    """Nạp từng mô hình 'người 1 giữ ra' (không thấy người 1 lúc huấn luyện) và dự đoán TRƯỚC MẮT người xem trên ô trang D của người 1.
    --da-tinh-san: không chạy, đọc kết quả đã đệm (truc_tiep.json). Trả dict (cũng ghi truc_tiep.json + truc_tiep.npz)."""
    return truc_tiep(da_tinh_san=a.da_tinh_san)


def truc_tiep(da_tinh_san: bool = False, in_ra=print) -> dict:
    f_json = AK / "truc_tiep.json"
    if da_tinh_san:
        if not f_json.exists():
            sys.exit("Chưa có kết quả đã tính sẵn: chạy `python tools/ak_so_sanh_mo_rong.py truc-tiep` một lần trước.")
        r = json.loads(f_json.read_text(encoding="utf-8"))
        r["da_tinh_san"] = True
        return r
    D = A.du_lieu()
    xt, yt, nt = D["trang"]
    x, y = xt[nt == 1], yt[nt == 1]
    in_ra(f"Ô trang D của NGƯỜI VIẾT 1 (mô hình KHÔNG thấy người này lúc huấn luyện): {len(y)} ô")
    torch, _, _ = H._torch()
    torch.set_num_threads(1)
    ket = json.loads((AK / "ket_qua.json").read_text(encoding="utf-8")) if (AK / "ket_qua.json").exists() else {}
    khong = set(ket.get("khong_chay_E2b", {}))
    r = {"n": int(len(y)), "nguoi": 1, "da_tinh_san": False, "ngay": time.strftime("%Y-%m-%d %H:%M"), "algos": {}}
    preds = {}
    for ten in TAT_CA:
        if ten in khong or not ((A.TAM / f"mo_hinh_E2b_{ten}_nguoi1.pkl").exists() or (A.TAM / f"mo_hinh_E2b_{ten}_nguoi1.pt").exists()):
            continue
        f, byte, n_tp = mo_hinh_nguoi1(ten)
        t0 = time.perf_counter()
        z = f(x)
        dt = time.perf_counter() - t0
        p = np.asarray(z).argmax(1)
        preds[ten] = p.astype(np.int8)
        r["algos"][ten] = {"nhan": NHAN[ten], "dung": float((p == y).mean()), "sai": int((p != y).sum()), "giay_tong": round(dt, 3), "ms_moi_o_lo": round(1000 * dt / len(y), 3),
                           "byte": byte if ten not in NET else 4 * n_tp, "so_tham_so": n_tp}
        in_ra(f"  {NHAN[ten]:44s} đúng {100 * r['algos'][ten]['dung']:.2f}%  sai {r['algos'][ten]['sai']:4d}/{len(y)}  {dt:6.2f} s")
    r["y"] = y.tolist()
    AK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(AK / "truc_tiep.npz", x=x, y=y.astype(np.int8), **{f"p_{t}": v for t, v in preds.items()})
    f_json.write_text(json.dumps({k: v for k, v in r.items() if k != "y"}, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def cmd_kiem_tat_dinh(a):
    """Huấn luyện MLP tiền huấn luyện (seed 2026) HAI lần giống hệt nhau, so logit: máy này có tất định không? -> kiem_tat_dinh.json (giải thích MLP không trùng lệnh AI)."""
    x, y = C.du_lieu_truoc("mnist")
    xte = x[:2000]
    zs = [H.logits(H.huan_luyen_cnn(x, y, C.PRE["epochs"], C.PRE["lr"], SEED0, mo_hinh=A.tao_mlp()), xte) for _ in range(2)]
    r = {"thuat_toan": "mlp (tiền huấn luyện MNIST, seed 2026, 2 lần giống hệt)", "max_chenh_logit": float(np.abs(zs[0] - zs[1]).max()),
         "so_nhan_khac_tren_2000": int((zs[0].argmax(1) != zs[1].argmax(1)).sum())}
    AK.mkdir(parents=True, exist_ok=True)
    (AK / "kiem_tat_dinh.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(r)

def cmd_don(a):
    import shutil
    shutil.rmtree(A.TAM, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thu", default="", help="thư mục nháp: chạy thử mã trên dữ liệu tí hon")
    sp = ap.add_subparsers(dest="lenh", required=True)
    c = sp.add_parser("chay")
    c.add_argument("--thuat-toan", nargs="+", default=list(TAT_CA), choices=TAT_CA)
    c.set_defaults(f=cmd_chay)
    sp.add_parser("don").set_defaults(f=cmd_don)
    for ten in ("ag-cat", "ag-doc", "bang", "truc-tiep", "kiem-tat-dinh"):
        p = sp.add_parser(ten)
        if ten == "truc-tiep":
            p.add_argument("--da-tinh-san", action="store_true")
        p.set_defaults(f=globals().get("cmd_" + ten.replace("-", "_")))
    a = ap.parse_args()
    if a.thu:
        global AK
        AK = Path(a.thu).resolve()
        A.AI, A.TAM = AK, AK / "tam"
        A.THU = True
    a.f(a)


if __name__ == "__main__":
    main()
