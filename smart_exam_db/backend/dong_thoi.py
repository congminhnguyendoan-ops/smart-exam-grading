"""
dong_thoi.py - Lệnh AR (16/11/2026): TẦNG ĐIỀU PHỐI ĐỒNG THỜI cho tải ảnh, sửa các rủi ro ghi nhận ở lệnh AH (docs/lenh_ah.md mục 4, docs/tieu_chi_sua_ah.md).

KHÔNG sửa backend/service.py (tệp đóng băng đợt 2): mọi khoá nằm ở đây, lấy TRƯỚC khi gọi service.nhan_anh, ở mức giao dịch CSDL (pg_advisory_xact_lock →
tự nhả khi giao dịch commit / rollback; nhiều tiến trình uvicorn vẫn đúng).

  - R1  hai phiếu CÙNG SBD gửi đồng thời: bên thua cuộc đua gặp UniqueViolation (uq_results_exam_student) -> trước đây 409 + MẤT phiếu. Nay: rollback về savepoint,
        lấy khoá mức kỳ thi, THỬ LẠI service.nhan_anh – lần thử lại thấy điểm chính thức của phiếu thắng đã commit nên đi đường duplicate_sbd sẵn có (giữ ở needs_review).
        (Khoá mức (kỳ thi, SBD) từ đầu không làm được: SBD chỉ biết SAU khi đọc ảnh, bên trong service.nhan_anh; còn khoá mức kỳ thi từ đầu sẽ xếp hàng cả phần xử lý ảnh.)
  - R2  cùng MỘT tệp gửi hai lần đồng thời: khoá theo (kỳ thi, SHA-256 ảnh) – yêu cầu thứ hai chờ yêu cầu đầu commit rồi thấy phiếu cũ (da_ton_tai = true).
        Chỉ áp cho đường tải MỘT ảnh. /sheets/batch KHÔNG khoá theo ảnh (khoá ảnh giữ tới hết cả lô + khoá duy nhất results của lô có thể tạo vòng chờ với yêu cầu đơn).
  - R3  /sheets/batch hai lô chéo: mỗi lô lấy khoá mức kỳ thi (không gian khoá riêng "lo") ngay đầu lô -> hai lô cùng kỳ chạy lần lượt, không chéo khoá chỉ mục duy nhất.
  - R5  giới hạn chấm đồng thời: BoundedSemaphore (CHAM_DONG_THOI, mặc định 4) lấy TRƯỚC mọi khoá CSDL; chờ tối đa CHAM_CHO_GIAY (mặc định 30) rồi 503 + Retry-After.
"""
import hashlib
import threading
from contextlib import contextmanager

import psycopg

from . import service

RANG_BUOC_DUA = {"uq_results_exam_student", "uq_sheets_image_hash"}      # UniqueViolation do đua – thử lại được; ràng buộc khác (lỗi dữ liệu thật) thì ném tiếp
SO_LAN_THU = 3


class QuaTai(Exception):
    """Hết thời hạn chờ trong hàng đợi chấm -> 503 + Retry-After (main.py)."""

    def __init__(self, retry_after: int):
        super().__init__("Máy chủ đang bận chấm ảnh, hãy thử lại sau ít giây.")
        self.retry_after = retry_after


class CongCham:
    """Cổng giới hạn số ảnh được chấm CÙNG LÚC trong một tiến trình (mỗi ảnh ~150 MB bộ nhớ, thông lượng bão hoà từ ~4 yêu cầu)."""

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
    """Một CongCham cho mỗi ứng dụng (tạo lười, an toàn đa luồng). Cấu hình lấy từ CauHinh (biến môi trường CHAM_DONG_THOI / CHAM_CHO_GIAY)."""
    c = getattr(app_state, "cong_cham", None)
    if c is None:
        with _khoi_tao:
            c = getattr(app_state, "cong_cham", None)
            if c is None:
                c = app_state.cong_cham = CongCham(cfg.cham_dong_thoi, cfg.cham_cho_giay)
    return c


# ------------------------------------------------------------------------------------------------ khoá CSDL
def _khoa(conn, ten: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (ten,))


def khoa_anh(conn, exam_id: int, du_lieu: bytes) -> None:
    _khoa(conn, f"ar:anh:{exam_id}:{hashlib.sha256(du_lieu).hexdigest()}")


def khoa_ky_thi(conn, exam_id: int, loai: str) -> None:
    _khoa(conn, f"ar:{loai}:{exam_id}")


def _la_dua(e: psycopg.errors.UniqueViolation) -> bool:
    return (e.diag.constraint_name or "") in RANG_BUOC_DUA


def nhan_anh_an_toan(conn, cfg, mh, exam_id: int, du_lieu: bytes, ten_file, user_id: int, batch_id=None, *, khoa_theo_anh: bool = False, nhan=None):
    """service.nhan_anh + R1 (thử lại sau cuộc đua cùng SBD) + R2 (khoá theo ảnh). Trả (sheet_id, da_ton_tai).
    Phải gọi khi connection ĐANG trong giao dịch (get_conn của main.py luôn vậy): conn.transaction() khi đó là SAVEPOINT, lỗi chỉ hoàn tác phần của ảnh này."""
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
        khoa_ky_thi(conn, exam_id, "thu-lai")                # ngoài savepoint đã hoàn tác -> khoá không bị nhả theo
    raise AssertionError("không tới được")
