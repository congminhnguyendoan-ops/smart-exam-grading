"""
ad_nap_emnist.py - Lệnh AD, Bước 1: nạp EMNIST Digits từ zip Kaggle (crawford/emnist) -> data/nguon_ngoai/emnist_digits.npz.

KHÔNG giải nén cả zip: chỉ đọc 4 tệp idx của phần "digits" (emnist_source_files/emnist-digits-*-ubyte) bằng zipfile, phân tích bằng NumPy.
EMNIST lưu ảnh CHUYỂN VỊ so với MNIST (hàng <-> cột) -> chuyển vị lại. EMNIST còn chuẩn hoá KHÁC MNIST (chữ số chiếm ~24 px, căn theo bbox),
trong khi lúc chạy thật ô viết tay đi qua cv_engine.ocr.ve_mnist (bbox mực -> 20×20, trọng tâm -> (14, 14)). Vì vậy lưu thêm bản
`*_chuan` = ảnh đã cho qua ĐÚNG ve_mnist (cùng đường với ô thật).

Lưu: x_train, y_train, x_test, y_test (đúng chiều, chuẩn hoá gốc EMNIST), x_train_chuan, x_test_chuan (qua ve_mnist), sha256 tệp zip.
Ảnh kiểm bằng mắt: data/_eval/ad/emnist_mau.png (lưới 10×10: mỗi hàng 1 chữ số 0–9; nửa trái gốc, nửa phải đã chuẩn hoá).

Chạy (từ smart_exam_db/):  python tools/ad_nap_emnist.py
"""
import hashlib
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine import ocr  # noqa: E402

ZIP = ROOT / "data" / "nguon_ngoai" / "emnist" / "emnist_archive.zip"
RA = ROOT / "data" / "nguon_ngoai" / "emnist_digits.npz"
EVAL = ROOT / "data" / "_eval" / "ad"
TEN = {"x_train": "emnist_source_files/emnist-digits-train-images-idx3-ubyte",
       "y_train": "emnist_source_files/emnist-digits-train-labels-idx1-ubyte",
       "x_test": "emnist_source_files/emnist-digits-test-images-idx3-ubyte",
       "y_test": "emnist_source_files/emnist-digits-test-labels-idx1-ubyte"}


def doc_idx(b: bytes) -> np.ndarray:
    """Định dạng idx (magic 0x0803 ảnh / 0x0801 nhãn), big-endian."""
    magic = int.from_bytes(b[:4], "big")
    if magic == 0x0803:
        n, h, w = (int.from_bytes(b[4 + 4 * i:8 + 4 * i], "big") for i in range(3))
        return np.frombuffer(b, np.uint8, offset=16).reshape(n, h, w)
    if magic == 0x0801:
        return np.frombuffer(b, np.uint8, offset=8)
    raise ValueError(f"magic idx lạ: {magic:#x}")


def chuan_hoa(x: np.ndarray) -> np.ndarray:
    """Cho từng ảnh qua ocr.ve_mnist (giống ô thật). Ảnh rỗng (không có) -> giữ nguyên."""
    ra = np.empty_like(x)
    for i, im in enumerate(x):
        v = ocr.ve_mnist(im.astype(np.float32) / 255.0)
        ra[i] = im if v is None else v
    return ra


def luoi(anh: list[np.ndarray], cot: int) -> np.ndarray:
    hang = [np.hstack(anh[i:i + cot]) for i in range(0, len(anh), cot)]
    return np.vstack(hang)


def main():
    if not ZIP.exists():
        sys.exit(f"DỪNG: không thấy {ZIP}")
    with zipfile.ZipFile(ZIP) as z:
        co = set(z.namelist())
        thieu = [t for t in TEN.values() if t not in co]
        if thieu:
            sys.exit(f"DỪNG: zip không có phần digits: thiếu {thieu}")
        d = {k: doc_idx(z.read(t)) for k, t in TEN.items()}
    sha = hashlib.sha256()
    with ZIP.open("rb") as f:
        for khoi in iter(lambda: f.read(1 << 24), b""):
            sha.update(khoi)
    for k in ("x_train", "x_test"):
        d[k] = np.ascontiguousarray(d[k].transpose(0, 2, 1))          # EMNIST chuyển vị -> đúng chiều MNIST
    for k in ("y_train", "y_test"):
        d[k] = d[k].astype(np.int64)
        assert d[k].min() == 0 and d[k].max() == 9
    print("Chuẩn hoá qua ocr.ve_mnist (giống ô thật)…")
    d["x_train_chuan"] = chuan_hoa(d["x_train"])
    d["x_test_chuan"] = chuan_hoa(d["x_test"])
    RA.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(RA, **d, sha256_zip=np.array(sha.hexdigest()))
    print(f"Ghi {RA} ({RA.stat().st_size / 1e6:.1f} MB); SHA-256 zip {sha.hexdigest()}")
    for tap in ("train", "test"):
        dem = np.bincount(d[f"y_{tap}"], minlength=10)
        print(f"  {tap}: {len(d[f'y_{tap}'])} mẫu; mỗi lớp: " + ", ".join(f"{c}:{n}" for c, n in enumerate(dem)))

    # đối chiếu với bản Hugging Face đã dùng ở Tuần 6 Phần C (nếu còn): cùng dữ liệu NIST?
    hf = ROOT / "data" / "_ocr" / "nguon_emnist_hf" / "emnist-digits-train-images-idx3-ubyte.gz"
    if hf.exists():
        import gzip
        with gzip.open(hf, "rb") as f:
            xh = np.ascontiguousarray(doc_idx(f.read()).transpose(0, 2, 1))
        print(f"  Đối chiếu bản HF Tuần 6: cùng kích thước {xh.shape == d['x_train'].shape}, "
              f"trùng từng byte {bool(xh.shape == d['x_train'].shape and np.array_equal(xh, d['x_train']))}")

    # lưới 10×10 kiểm bằng mắt: hàng = chữ số; 5 ảnh gốc (đã chuyển vị) | 5 ảnh đã chuẩn hoá
    rng = np.random.default_rng(0)
    o = []
    for c in range(10):
        ix = rng.choice(np.nonzero(d["y_train"] == c)[0], 5, replace=False)
        o += [d["x_train"][i] for i in ix] + [d["x_train_chuan"][i] for i in ix]
    g = luoi([255 - cv2.copyMakeBorder(a, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=128) for a in o], 10)
    g = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    EVAL.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", g)[1].tofile(str(EVAL / "emnist_mau.png"))
    print(f"Ghi {EVAL / 'emnist_mau.png'} (hàng = chữ số 0..9; 5 cột trái gốc EMNIST đã chuyển vị, 5 cột phải qua ve_mnist)")


if __name__ == "__main__":
    main()
