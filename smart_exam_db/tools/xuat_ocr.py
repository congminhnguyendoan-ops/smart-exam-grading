"""
xuat_ocr.py - Xuất CNN chữ số viết tay ra models/ocr_cnn.json (NumPy + JSON, không cần PyTorch lúc chạy) – Tuần 6 Phần C, Bước 3.
CẦN torch (chỉ để huấn luyện / xuất). Chạy TỪ COMMIT SẠCH: file tracked không được có thay đổi chưa commit (ghi SHA commit vào siêu dữ liệu).

  1. tiền huấn luyện (cache data/_ocr/cap/) -> tinh chỉnh trên TOÀN BỘ trang chữ số D001–D010 (ô dò được khung) cho từng seed
  2. nhiệt độ T mỗi thành viên + (τ, δ) lấy từ OOF 5-fold theo người viết của CÙNG cấu hình (python tools/ocr_cai_tien.py chay trước)
  3. ghi JSON (trọng số làm tròn 8 chữ số có nghĩa) + siêu dữ liệu (ngày, commit, seed, cấu hình, SHA dữ liệu, số đo OOF)
  4. kiểm: NumPy (cv_engine.ocr, đọc lại từ JSON) khớp PyTorch (trọng số gốc) trên MỌI chữ số dev: cùng nhãn 100%, chênh xác suất < 1e-4

Chạy (từ smart_exam_db/):  python tools/xuat_ocr.py --cau-hinh g0_goc --seeds 2026
"""
import argparse
import copy
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import huan_luyen_ocr as H  # noqa: E402
import ocr_cai_tien as C  # noqa: E402
import ocr_do_luong as L  # noqa: E402
from cv_engine import ocr  # noqa: E402

DICH = ROOT / "models" / "ocr_cnn.json"
SAI_SO_TOI_DA = 1e-4


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, encoding="utf-8").stdout.strip()


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tham_so(m) -> dict:
    """Trọng số torch -> dict mảng (float32) đúng tên mà cv_engine.ocr dùng."""
    sd = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in m.state_dict().items()}
    if "a1.weight" in sd:                                      # CNN sâu "sau_2x2" (lệnh AM): 4 conv a1 a2 b1 b2 + d1 d2, ghi kien_truc = ocr.KIEN_TRUC_SAU
        return {f"{t}{u}": sd[f"{t}.{'weight' if u == 'w' else 'bias'}"] for t in ("a1", "a2", "b1", "b2", "d1", "d2") for u in ("w", "b")}
    return {"c1w": sd["c1.weight"], "c1b": sd["c1.bias"], "c2w": sd["c2.weight"], "c2b": sd["c2.bias"],
            "d1w": sd["d1.weight"], "d1b": sd["d1.bias"], "d2w": sd["d2.weight"], "d2b": sd["d2.bias"]}


def lam_tron(a: np.ndarray) -> list:
    return np.array([float(f"{v:.8g}") for v in a.ravel()], dtype=np.float64).reshape(a.shape).tolist()


def xuat_tu_tep(a):
    """Lệnh AN: ghi models/ocr_cnn.json từ MỘT TỆP ỨNG VIÊN ĐÃ ĐO (không huấn luyện lại – huấn luyện không tất định, mô hình huấn luyện lại là mô hình chưa đo).
    Trọng số giữ giống từng giá trị; chỉ thêm siêu dữ liệu + kiểm NumPy ↔ PyTorch (trọng số gốc .pt) trên mọi chữ số dev. Từ commit sạch."""
    ban = git("status", "--porcelain", "--untracked-files=no")
    if ban and not a.cho_phep_ban:
        sys.exit("DỪNG: có thay đổi chưa commit ở file tracked (xuất mô hình phải từ commit sạch):\n" + ban)
    tep, pt_goc = Path(a.tu_tep), Path(a.trong_so_pytorch)
    if a.sha_mong_doi and sha_file(tep).lower() != a.sha_mong_doi.lower():
        sys.exit(f"DỪNG: SHA tệp ứng viên {sha_file(tep)} khác SHA đã đăng ký {a.sha_mong_doi}")
    cand = json.loads(tep.read_text(encoding="utf-8"))
    assert cand["kien_truc"] == ocr.KIEN_TRUC_SAU and len(cand["thanh_vien"]) == 1
    torch, _, _ = H._torch()
    import ak_so_sanh_mo_rong as K
    net = K.tao_cnn_sau()
    net.load_state_dict(torch.load(pt_goc))
    net.eval()
    t = H.tap_do(C.NGUON)
    xs = np.concatenate([t["trang"]["x"], t["phieu"]["x"]])
    mh_tmp = ocr.nap_mo_hinh_ocr(tep)
    p_np = ocr.du_doan_xac_suat(mh_tmp, xs)
    z = H.logits(net, xs).astype(np.float64) / cand["thanh_vien"][0]["T"]
    z -= z.max(1, keepdims=True)
    p_t = np.exp(z) / np.exp(z).sum(1, keepdims=True)
    chenh, cung_nhan = float(np.abs(p_np - p_t).max()), float((p_np.argmax(1) == p_t.argmax(1)).mean())
    print(f"Kiểm NumPy ↔ PyTorch trên {len(xs)} chữ số dev: cùng nhãn {cung_nhan:.4%}, chênh xác suất lớn nhất {chenh:.2e}")
    if cung_nhan < 1.0 or chenh >= SAI_SO_TOI_DA:
        sys.exit("KHÔNG ĐẠT: NumPy khác PyTorch")
    am = json.loads((ROOT / "data" / "_eval" / "am" / "ket_qua.json").read_text(encoding="utf-8"))
    an = json.loads((ROOT / "data" / "_eval" / "an" / "ket_qua.json").read_text(encoding="utf-8"))
    sha = {"cat_anh_nan_npz": sha_file(H.OCR / "cat" / "anh_nan.npz"), "cat_anh_nan_csv": sha_file(H.OCR / "cat" / "anh_nan.csv"),
           "mnist": (H.OCR / "nguon" / "SHA.txt").read_text(encoding="utf-8").strip().splitlines()}
    out = dict(cand, phien_ban="ocr_cnn_v2_sau")
    out["sieu_du_lieu"] = {
        "ngay": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "git_head": git("rev-parse", "HEAD"), "git_sach": not ban,
        "cau_hinh": "sau_2x2_seed2026", "tien_huan_luyen": "mnist", "tang_cuong_tien": "co_ban", "tang_cuong_tinh_chinh": "co_ban", "seeds": [2026],
        "tinh_chinh": C.FT, "pre": C.PRE, "torch": torch.__version__, "numpy": np.__version__,
        "tap_huan_luyen": f"mnist + tinh chỉnh D001–D010 ({len(t['trang']['x'])} ô, 5 người viết)", "nguon_anh": C.NGUON,
        "fold": "5-fold theo người viết (OOF) để chọn nhiệt độ T và đo; mô hình xuất tinh chỉnh trên cả 5 người; τ, δ giữ nguyên CNN cũ (không chỉnh theo dev)",
        "sha256_du_lieu": sha, "nhiet_do_T": [cand["thanh_vien"][0]["T"]],
        "nguon_ung_vien": {"tep": "data/_eval/am/ocr_cnn_sau_seed2026.json", "sha256": sha_file(tep), "dang_ky": "docs/tieu_chi_thay_mo_hinh_an.md", "trong_so_giong_tung_gia_tri": True},
        "do_luong": {"IL": 0, "ghi_chu": "IL = lỗi im lặng mức trường: 0 trên dev (OOF + 13 ảnh AG, lệnh AM) và 0 trên val+test (lệnh AN)",
                     "oof_dung_ca_chuoi_seed2026": am["a"]["hw_gop_tung_seed"][0], "oof_dung_ca_chuoi_tb3": am["a"]["hw_gop_tb"], "oof_dung_ca_chuoi_cnn_cu": am["a"]["hw_gop_baseline"],
                     "val_test_ung_vien": an["gop"]["ung_vien"], "val_test_cnn_cu": an["gop"]["hien_tai"]},
        "tuong_duong_numpy_torch": {"n": int(len(xs)), "cung_nhan": cung_nhan, "chenh_xac_suat_max": chenh}}
    dich = Path(a.dich)
    dich.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kiem = json.loads(dich.read_text(encoding="utf-8"))
    assert kiem["thanh_vien"] == cand["thanh_vien"], "trọng số phải giống tệp ứng viên"
    print(f"Ghi {dich} ({dich.stat().st_size / 1024:.0f} KB), sạch = {not ban}; trọng số giống tệp ứng viên")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cau-hinh", choices=list(C.CAU_HINH))
    ap.add_argument("--tu-tep", help="Lệnh AN: tệp ứng viên đã đo (kiến trúc sau_2x2) – ghi lại với siêu dữ liệu, KHÔNG huấn luyện lại")
    ap.add_argument("--trong-so-pytorch", default=str(ROOT / "data" / "_eval" / "am" / "tam" / "final_sau_2026.pt"))
    ap.add_argument("--sha-mong-doi", default="")
    ap.add_argument("--seeds", type=int, nargs="+", default=[2026])
    ap.add_argument("--cho-phep-ban", action="store_true", help="CHỈ để thử: bỏ kiểm commit sạch (file ra có git_sach = false)")
    ap.add_argument("--dich", default=str(DICH))
    a = ap.parse_args()
    if a.tu_tep:
        return xuat_tu_tep(a)
    if not a.cau_hinh:
        ap.error("cần --cau-hinh (huấn luyện lại) hoặc --tu-tep (ghi từ tệp đã đo)")

    ban = git("status", "--porcelain", "--untracked-files=no")
    if ban and not a.cho_phep_ban:
        sys.exit("DỪNG: có thay đổi chưa commit ở file tracked (xuất mô hình phải từ commit sạch):\n" + ban)
    head = git("rev-parse", "HEAD")
    torch, _, _ = H._torch()
    nt, a_pre, a_ft = C.CAU_HINH[a.cau_hinh]
    t = H.tap_do(C.NGUON)
    x, y = t["trang"]["x"], t["trang"]["y"]
    thanh_vien, models_torch, T_list = [], [], []
    for sd in a.seeds:
        z = np.load(C.CAP / f"oof_{a.cau_hinh}_{sd}.npz")
        T = L.chon_nhiet(z["trang"], y)
        pre = C.tien_huan_luyen(nt, a_pre, sd)
        m = H.huan_luyen_cnn(x, y, C.FT["epochs"], C.FT["lr"], sd, mo_hinh=copy.deepcopy(pre), batch=C.FT["batch"],
                             aug_fn=C.tang_cuong_v2 if a_ft == "v2" else None)
        models_torch.append((m, T))
        T_list.append(round(T, 4))
        thanh_vien.append({"seed": sd, "T": round(T, 4), **{k: lam_tron(v) for k, v in tham_so(m).items()}})
        print(f"seed {sd}: tinh chỉnh trên {len(x)} ô trang D, T = {T:.3f}")

    # số đo OOF của đúng cấu hình này (ensemble các seed đã chọn) + τ, δ
    omr = json.loads((H.OCR / "omr_dev.json").read_text(encoding="utf-8"))
    pt, pp, _ = C.xac_suat_hieu_chinh(a.cau_hinh, tuple(a.seeds), t)
    do_luong = C.danh_gia(pt, pp, t, omr)
    do_luong.pop("gan_theo_anh", None)
    ng = L.chon_nguong(pt, y)
    tau, delta = (ng[1], ng[2]) if ng else (0.9999, 0.99)

    sha = {"cat_anh_nan_npz": sha_file(H.OCR / "cat" / "anh_nan.npz"), "cat_anh_nan_csv": sha_file(H.OCR / "cat" / "anh_nan.csv"),
           "mnist": (H.OCR / "nguon" / "SHA.txt").read_text(encoding="utf-8").strip().splitlines()}
    if nt.startswith("emnist"):
        sha["emnist"] = {f.name: sha_file(f) for f in sorted((H.OCR / "nguon_emnist_hf").glob("*.gz"))}
    out = {"phien_ban": "ocr_cnn_v1", "kien_truc": "Conv16(3x3)-pool-Conv32(3x3)-pool-Dense64-Dense10, ReLU, padding 1",
           "thanh_vien": thanh_vien, "tau": tau, "delta": delta, "tau_khop": L.TAU_KHOP,
           "sieu_du_lieu": {
               "ngay": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "git_head": head, "git_sach": not ban,
               "cau_hinh": a.cau_hinh, "tien_huan_luyen": nt, "tang_cuong_tien": a_pre, "tang_cuong_tinh_chinh": a_ft, "seeds": a.seeds,
               "tinh_chinh": C.FT, "pre": C.PRE, "torch": torch.__version__, "numpy": np.__version__,
               "tap_huan_luyen": f"{nt} + tinh chỉnh D001–D010 ({len(x)} ô, 5 người viết)", "nguon_anh": C.NGUON,
               "fold": "5-fold theo người viết (OOF) để chọn nhiệt độ T, τ, δ và đo; mô hình xuất tinh chỉnh trên cả 5 người",
               "sha256_du_lieu": sha, "nhiet_do_T": T_list, "do_luong": do_luong}}
    dich = Path(a.dich)
    dich.parent.mkdir(parents=True, exist_ok=True)
    dich.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Ghi {dich} ({dich.stat().st_size / 1024:.0f} KB), commit {head[:8]}, sạch = {not ban}")

    # kiểm tương đương: NumPy từ JSON ↔ PyTorch (trọng số gốc) trên MỌI chữ số dev (anh_nan, cả 2 tập đo + trang D bỏ ô không dò được khung)
    mh = ocr.nap_mo_hinh_ocr(dich)
    xs = np.concatenate([t["trang"]["x"], t["phieu"]["x"]])
    p_np = ocr.du_doan_xac_suat(mh, xs)
    ps = []
    for m, T in models_torch:
        z = H.logits(m, xs).astype(np.float64) / T
        z -= z.max(1, keepdims=True)
        e = np.exp(z)
        ps.append(e / e.sum(1, keepdims=True))
    p_t = np.mean(ps, axis=0)
    chenh = float(np.abs(p_np - p_t).max())
    cung_nhan = float((p_np.argmax(1) == p_t.argmax(1)).mean())
    print(f"Kiểm NumPy ↔ PyTorch trên {len(xs)} chữ số: cùng nhãn {cung_nhan:.4%}, chênh xác suất lớn nhất {chenh:.2e}")
    out["sieu_du_lieu"]["tuong_duong_numpy_torch"] = {"n": int(len(xs)), "cung_nhan": cung_nhan, "chenh_xac_suat_max": chenh}
    dich.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if cung_nhan < 1.0 or chenh >= SAI_SO_TOI_DA:
        sys.exit(f"KHÔNG ĐẠT: NumPy khác PyTorch (nhãn {cung_nhan:.4%}, chênh {chenh:.2e} ≥ {SAI_SO_TOI_DA})")
    print("ĐẠT: NumPy khớp PyTorch.")


if __name__ == "__main__":
    main()
