import json
import os
import sys
import warnings
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["AUTH_MODE"] = "demo"
os.environ["HEALTH_CHI_TIET"] = "1"
os.environ["ANH_XOA_TU_DONG"] = "0"

ANSWER_SHEET_DIR = ROOT / "answer_sheet"
DATA = ROOT / "data"
EVAL = DATA / "_eval"
THAM_CHIEU = EVAL / "tham_chieu_kiem_thu"
GIA = EVAL / "_gia_v4"
DUNG_SAI_MUC_XAM = 2
DUNG_SAI_TI_LE = 0.999


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


BANG_KIEM = ("subjects", "exams", "exam_codes", "answer_keys", "students", "answer_sheets", "sheet_answers", "results",
             "review_queue", "scan_batches", "ml_models", "score_audit_logs", "ocr_digits", "users", "classes", "teacher_classes",
             "admin_audit_log")


def _dem_bang(conn) -> dict:
    return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in BANG_KIEM}


@pytest.fixture(scope="session")
def csdl_san_sang():
    try:
        from backend import migrate
        from backend.config import lay_database_url
        from backend.db import ket_noi
        lay_database_url()
        if os.environ.get("SMART_EXAM_TEST_MIGRATE") == "1":
            migrate.ap_dung()
        with ket_noi() as c:
            c.execute("SET TRANSACTION READ ONLY")
            chua = migrate.chua_ap(c)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"không nối được CSDL / thiếu .env / chưa có schema_migrations: {type(e).__name__}: {e}")
    if chua:
        pytest.skip(f"SKIP: migration chưa áp lên CSDL: {chua} – chạy `python -m backend.migrate` (hoặc SMART_EXAM_TEST_MIGRATE=1); test KHÔNG tự áp")
    return True


@pytest.fixture(scope="session")
def csdl_003(csdl_san_sang):
    from backend import migrate
    from backend.db import ket_noi
    with ket_noi() as c:
        c.execute("SET TRANSACTION READ ONLY")
        chua = migrate.chua_ap(c, ca_tuy_chon=True)
    if "003_xoa_anh_tam.sql" in chua:
        pytest.skip("SKIP: migration 003_xoa_anh_tam.sql chưa áp lên CSDL (chờ người dùng đồng ý) – chạy `python -m backend.migrate`; test KHÔNG tự áp")
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
        yield conn_thu

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_cau_hinh] = lambda: cau_hinh_thu
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
