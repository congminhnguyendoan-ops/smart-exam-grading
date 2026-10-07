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


# ---------------------------------------------------------------------------------------------- backend (Tuần 5 demo, B4)
# Test API / dịch vụ chạy trên CSDL THẬT nhưng trong MỘT giao dịch luôn ROLLBACK (không để lại dòng nào) + thư mục ảnh tạm.
# Không nối được CSDL / thiếu .env -> SKIP. Fixture kiểm cuối: số dòng các bảng chính sau rollback = trước khi test.
BANG_KIEM = ("subjects", "exams", "exam_codes", "answer_keys", "students", "answer_sheets", "sheet_answers", "results",
             "review_queue", "scan_batches", "ml_models", "score_audit_logs")


def _dem_bang(conn) -> dict:
    return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in BANG_KIEM}


@pytest.fixture(scope="session")
def csdl_san_sang():
    """Áp migration (chỉ thêm cột, idempotent) một lần; skip nếu không nối được CSDL."""
    try:
        from backend import migrate
        from backend.config import lay_cau_hinh
        lay_cau_hinh()
        migrate.ap_dung()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"không nối được CSDL / thiếu .env: {type(e).__name__}: {e}")
    return True


@pytest.fixture
def conn_thu(csdl_san_sang):
    from backend.db import ket_noi
    truoc_conn = ket_noi()
    truoc = _dem_bang(truoc_conn)
    truoc_conn.rollback()
    conn = ket_noi()
    yield conn
    conn.rollback()
    conn.close()
    sau = _dem_bang(truoc_conn)
    truoc_conn.close()
    assert sau == truoc, f"test để lại dữ liệu trong CSDL thật: {truoc} -> {sau}"


@pytest.fixture
def cau_hinh_thu(tmp_path):
    from dataclasses import replace
    from backend.config import lay_cau_hinh
    return replace(lay_cau_hinh(), storage_dir=tmp_path / "kho")


@pytest.fixture
def client(conn_thu, cau_hinh_thu):
    from fastapi.testclient import TestClient
    from backend.main import app, get_cau_hinh, get_conn

    def _conn():
        yield conn_thu                                   # dùng chung một giao dịch, KHÔNG commit

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_cau_hinh] = lambda: cau_hinh_thu
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
