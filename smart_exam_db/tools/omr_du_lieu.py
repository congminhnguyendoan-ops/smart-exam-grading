import csv
import hashlib
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine.tap_du_lieu import PHIEU_TEST, PHIEU_TRAIN, PHIEU_VAL, chan_test  # noqa: E402

DATA = ROOT / "data"
SPLIT = DATA / "split.csv"
RAW = DATA / "raw"
DEM = DATA / "_omr" / "anh"
VAN_TAY_V4 = DATA / "_eval" / "v4_verify" / "anh_nan_sha256.csv"


class ChamTapVal(Exception):
    pass


def ds_anh(tap: str = "train", cho_phep_val: bool = False) -> list[dict]:
    if tap not in ("train", "val"):
        raise ValueError("chỉ 'train' hoặc 'val' – tập test chỉ đọc qua eval_omr.py ở đánh giá cuối")
    if tap == "val" and not cho_phep_val:
        raise ChamTapVal("Phần A không dùng val 0029–0034 (docs/ke_hoach_tuan5.md ★Q3)")
    with SPLIT.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["tap"] == tap]
    chan_test([r["anh"] for r in rows], False, "omr_du_lieu")
    for r in rows:
        p = int(r["phieu"])
        if p in PHIEU_TEST or (p in PHIEU_VAL and not cho_phep_val) or (tap == "train" and p not in PHIEU_TRAIN):
            raise RuntimeError(f"split.csv sai: {r['anh']} thuộc tập {r['tap']}")
    return rows


def sha_anh(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def _doc_png(p: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_GRAYSCALE)


_VAN_TAY: dict = {}


def van_tay_v4() -> dict:
    if not _VAN_TAY:
        with VAN_TAY_V4.open(encoding="utf-8-sig", newline="") as f:
            _VAN_TAY.update({r["anh"]: r["sha256"] for r in csv.DictReader(f)})
    return _VAN_TAY


def anh_da_nan(ten: str, layout: dict) -> tuple[np.ndarray, np.ndarray]:
    chan_test([ten], False, "omr_du_lieu.anh_da_nan")
    p_nan, p_ch = DEM / f"{ten}_nan.png", DEM / f"{ten}_chuan.png"
    if p_nan.exists() and p_ch.exists():
        nan, ch = _doc_png(p_nan), _doc_png(p_ch)
    else:
        from cv_engine.preprocessing import preprocess
        kq = preprocess(RAW / f"{ten}.jpg", layout)
        if not kq.ok:
            raise RuntimeError(f"{ten}: preprocess từ chối ({kq.ly_do}) – ảnh dev phải ok (Tuần 4: 78/78)")
        nan, ch = kq.anh_nan, kq.anh_chuan_hoa
        DEM.mkdir(parents=True, exist_ok=True)
        cv2.imencode(".png", nan, [cv2.IMWRITE_PNG_COMPRESSION, 1])[1].tofile(p_nan)
        cv2.imencode(".png", ch, [cv2.IMWRITE_PNG_COMPRESSION, 1])[1].tofile(p_ch)
    vt = van_tay_v4().get(ten)
    if vt is not None and sha_anh(nan) != vt:
        raise RuntimeError(f"{ten}: anh_nan khác vân tay v4 – xoá {p_nan} để tạo lại, hoặc preprocess đã đổi hành vi")
    return nan, ch


def nhan_o(cho_phep_val: bool = False) -> dict:
    out = {}
    with (DATA / "cell_labels.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            p = int(r["sheet_id"])
            if p in PHIEU_TRAIN or (cho_phep_val and p in PHIEU_VAL):
                out[(r["sheet_id"], r["question"], r["option"])] = r["cell_label"]
    return out
