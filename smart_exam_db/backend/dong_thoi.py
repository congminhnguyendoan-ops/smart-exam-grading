import hashlib
import threading
from contextlib import contextmanager

import psycopg

from . import service

RANG_BUOC_DUA = {"uq_results_exam_student", "uq_sheets_image_hash"}
SO_LAN_THU = 3


class QuaTai(Exception):

    def __init__(self, retry_after: int):
        super().__init__("Máy chủ đang bận chấm ảnh, hãy thử lại sau ít giây.")
        self.retry_after = retry_after


class CongCham:

    def __init__(self, toi_da: int, cho_giay: float):
        self.toi_da = max(1, int(toi_da))
        self.cho_giay = max(0.0, float(cho_giay))
        self._sem = threading.BoundedSemaphore(self.toi_da)

    @property
    def retry_after(self) -> int:
        return max(1, int(self.cho_giay // 2) or 1)

    @contextmanager
    def vao(self):
        if not self._sem.acquire(timeout=self.cho_giay):
            raise QuaTai(self.retry_after)
        try:
            yield
        finally:
            self._sem.release()


_khoi_tao = threading.Lock()


def cong_cham_cua(app_state, cfg) -> CongCham:
    c = getattr(app_state, "cong_cham", None)
    if c is None:
        with _khoi_tao:
            c = getattr(app_state, "cong_cham", None)
            if c is None:
                c = app_state.cong_cham = CongCham(cfg.cham_dong_thoi, cfg.cham_cho_giay)
    return c


def _khoa(conn, ten: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (ten,))


def khoa_anh(conn, exam_id: int, du_lieu: bytes) -> None:
    _khoa(conn, f"ar:anh:{exam_id}:{hashlib.sha256(du_lieu).hexdigest()}")


def khoa_ky_thi(conn, exam_id: int, loai: str) -> None:
    _khoa(conn, f"ar:{loai}:{exam_id}")


def _la_dua(e: psycopg.errors.UniqueViolation) -> bool:
    return (e.diag.constraint_name or "") in RANG_BUOC_DUA


def nhan_anh_an_toan(conn, cfg, mh, exam_id: int, du_lieu: bytes, ten_file, user_id: int, batch_id=None, *, khoa_theo_anh: bool = True, nhan=None):
    nhan = nhan or service.nhan_anh
    if khoa_theo_anh:
        khoa_anh(conn, exam_id, du_lieu)
    for lan in range(1, SO_LAN_THU + 1):
        try:
            with conn.transaction():
                return nhan(conn, cfg, mh, exam_id, du_lieu, ten_file, user_id, batch_id)
        except psycopg.errors.UniqueViolation as e:
            if not _la_dua(e) or lan == SO_LAN_THU:
                raise
        khoa_ky_thi(conn, exam_id, "thu-lai")
    raise AssertionError("không tới được")
