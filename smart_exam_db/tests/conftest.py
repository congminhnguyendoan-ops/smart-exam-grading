"""Cấu hình chung cho bộ kiểm thử (Tuần 4, Bước 6). Chạy từ thư mục smart_exam_db/:  python -m pytest tests

Test cần dữ liệu (data/ không có trong git) tự SKIP nếu thiếu file – không báo lỗi trên máy chỉ có code.
Chỉ dùng ảnh dev và ảnh giả tạo từ ảnh dev (data/_eval/_gia_v4); không đọc ảnh test 0035–0040.
"""
import json
import sys
import warnings
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent           # smart_exam_db/
sys.path.insert(0, str(ROOT))

ANSWER_SHEET_DIR = ROOT / "answer_sheet"
DATA = ROOT / "data"
EVAL = DATA / "_eval"
THAM_CHIEU = EVAL / "tham_chieu_kiem_thu"               # tools/tao_tham_chieu.py
GIA = EVAL / "_gia_v4"                                  # tools/kiem_verify.py tao-gia
DUNG_SAI_MUC_XAM = 2                                    # khác phiên bản OpenCV/numpy: |Δ| ≤ 2 mức xám …
DUNG_SAI_TI_LE = 0.999                                  # … ở ≥ 99,9% điểm ảnh


def can_file(*paths: Path) -> None:
    thieu = [str(p) for p in paths if not p.exists()]
    if thieu:
        pytest.skip(f"thiếu dữ liệu (data/ không có trong git): {', '.join(thieu)}")


@pytest.fixture(scope="session")
def tham_chieu() -> dict:
    can_file(THAM_CHIEU / "tham_chieu.json")
    tc = json.loads((THAM_CHIEU / "tham_chieu.json").read_text(encoding="utf-8"))
    mt = tc["moi_truong"]
    tc["cung_phien_ban"] = (mt["cv2"], mt["numpy"]) == (cv2.__version__, np.__version__)
    return tc


def doc_png(p: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_UNCHANGED)


def so_voi_tham_chieu(moi: np.ndarray, ten_png: str, sha_ref: str, cung_phien_ban: bool) -> None:
    """Cùng phiên bản cv2/numpy lúc ghi tham chiếu -> giống từng byte (SHA). Khác phiên bản -> dung sai
    (|Δ| ≤ 2 mức xám ở ≥ 99,9% điểm ảnh) + cảnh báo, không fail vì khác biệt làm tròn của thư viện."""
    import hashlib
    assert moi is not None and moi.dtype == np.uint8
    if cung_phien_ban:
        assert hashlib.sha256(np.ascontiguousarray(moi).tobytes()).hexdigest() == sha_ref, \
            f"{ten_png}: khác tham chiếu từng byte (cùng phiên bản cv2/numpy) – hành vi preprocess đã đổi"
        return
    ref = doc_png(THAM_CHIEU / ten_png)
    assert moi.shape == ref.shape
    khop = float(np.mean(np.abs(moi.astype(np.int16) - ref.astype(np.int16)) <= DUNG_SAI_MUC_XAM))
    warnings.warn(f"{ten_png}: phiên bản cv2/numpy khác lúc ghi tham chiếu – so có dung sai, khớp {khop:.4%}")
    assert khop >= DUNG_SAI_TI_LE, f"{ten_png}: chỉ {khop:.4%} điểm ảnh lệch ≤ {DUNG_SAI_MUC_XAM} mức xám"
