"""Lệnh AR (docs/tieu_chi_sua_ah.md): tầng điều phối đồng thời backend/dong_thoi.py + sửa R1–R5. Test đơn vị / tích hợp chạy trên CSDL thật trong giao dịch ROLLBACK
(`conn_thu`); các cuộc đua THẬT giữa nhiều yêu cầu nằm ở tools/ah_thu_dong_thoi.py (máy chủ thử cổng 8010, ≥ 50 / 60 / 100 lần lặp)."""
import psycopg
import pytest

from backend import dong_thoi


def _gia_dua(conn, so_lan_hong: int, ten_rb: str = "bang_ar_tam_pkey"):
    """Hàm thay cho service.nhan_anh: `so_lan_hong` lần đầu vi phạm một ràng buộc duy nhất THẬT (bảng tạm), sau đó trả (7, False)."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS bang_ar_tam (x int PRIMARY KEY)")
    goi = []

    def nhan(c, cfg, mh, exam_id, du_lieu, ten, user_id, batch_id):
        goi.append(1)
        if len(goi) <= so_lan_hong:
            c.execute("INSERT INTO bang_ar_tam VALUES (1)")
            c.execute("INSERT INTO bang_ar_tam VALUES (1)")                       # UniqueViolation
        return 7, False
    return nhan, goi


@pytest.fixture
def rb_dua(monkeypatch):
    monkeypatch.setattr(dong_thoi, "RANG_BUOC_DUA", {"bang_ar_tam_pkey"})        # coi ràng buộc của bảng tạm như uq_results_exam_student


# ------------------------------------------------------------------------------------------------ R1: thử lại sau cuộc đua cùng SBD
def test_r1_thu_lai_sau_unique_violation_do_dua(conn_thu, rb_dua):
    nhan, goi = _gia_dua(conn_thu, 1)
    kq = dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan)
    assert kq == (7, False) and len(goi) == 2, "lần 1 thua cuộc đua -> lần 2 phải thấy phiếu thắng và thành công"
    assert conn_thu.execute("SELECT count(*) AS n FROM bang_ar_tam").fetchone()["n"] == 0, "phần ghi dở của lần thua phải bị hoàn tác (savepoint)"
    assert conn_thu.info.transaction_status.name == "INTRANS", "giao dịch ngoài vẫn sống (không rollback cả yêu cầu)"


def test_r1_khoa_muc_ky_thi_lay_khi_thu_lai_va_giu_den_het_giao_dich(conn_thu, rb_dua):
    from backend.db import ket_noi
    nhan, _ = _gia_dua(conn_thu, 1)
    dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 424242, b"x", "a.jpg", 1, nhan=nhan)
    with ket_noi() as c2:
        c2.execute("SET TRANSACTION READ ONLY")
        giu = c2.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS ok", ("ar:thu-lai:424242",)).fetchone()["ok"]
        c2.rollback()
    assert giu is False, "khoá mức kỳ thi 'thu-lai' phải đang được giữ bởi giao dịch này"


def test_r1_rang_buoc_khac_khong_bi_nuot(conn_thu):
    """UniqueViolation không phải do đua (ràng buộc lạ) -> ném ngay, KHÔNG thử lại (không che lỗi dữ liệu thật)."""
    nhan, goi = _gia_dua(conn_thu, 5)
    with pytest.raises(psycopg.errors.UniqueViolation):
        dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan)
    assert len(goi) == 1


def test_r1_het_so_lan_thu_thi_nem_loi_that(conn_thu, rb_dua):
    nhan, goi = _gia_dua(conn_thu, 99)
    with pytest.raises(psycopg.errors.UniqueViolation):
        dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan)
    assert len(goi) == dong_thoi.SO_LAN_THU


def test_r1_khong_dua_thi_goi_dung_mot_lan(conn_thu):
    nhan, goi = _gia_dua(conn_thu, 0)
    assert dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 1, b"x", "a.jpg", 1, nhan=nhan) == (7, False) and len(goi) == 1


def test_r1_main_dung_tang_dieu_phoi_va_khong_goi_thang_service_nhan_anh():
    """Cả hai đường tải ảnh (đơn + lô) phải đi qua dong_thoi.nhan_anh_an_toan; không còn lời gọi thẳng service.nhan_anh trong main.py."""
    import inspect

    from backend import main
    nguon = inspect.getsource(main)
    assert "service.nhan_anh(" not in nguon and nguon.count("dong_thoi.nhan_anh_an_toan(") == 2


def test_r1_tep_dong_bang_khong_bi_cham():
    """service.py / schemas.py / cv_engine / models nằm trong danh sách đóng băng: lệnh AR không được đổi (băm đầu lệnh ghi trong docs/tieu_chi_sua_ah.md)."""
    import hashlib

    from conftest import ROOT
    mong = {"backend/service.py": "2537b4f51a00a167c1c2d9d45e9ff29fcd9e149d8a3e6260b4ce6dd875847f8e", "backend/schemas.py": "05310795f5646007320a3dd1795ffb971eea5e45cd4bf882115e7dcb84cd231d",
            "models/ocr_cnn.json": "a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8", "models/omr_m1.json": "507ecc7b4f885e148c1a896884f8a285ea4e308de4477e47f870bebf7c059797",
            "cv_engine/ocr.py": "e9b3e00fc0917341756441d5aecc39abc14a85861b35844e6506cae33a26b4be", "cv_engine/omr.py": "e0111fc1909af598f7df882b40bda9bb8d509e2c25c2423ea0e15963786c1912",
            "cv_engine/preprocessing.py": "0d35c26ae716778d11ec69382da5c1dff70e5a88b455ae8946091393d618f237",
            "cv_engine/tap_du_lieu.py": "3f030b71ece0b3117db0465c2ebbe3cf1948911140deb002f20a333d37fd9f01"}      # băm sau khi đổi CRLF -> LF (autocrlf của Windows không làm test lệch)
    for tep, sha in mong.items():
        du_lieu = (ROOT / tep).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(du_lieu).hexdigest() == sha, f"{tep} đã bị đổi – tệp đóng băng (docs/tieu_chi_sua_ah.md mục 0)"


# ------------------------------------------------------------------------------------------------ R2: cùng một tệp ảnh gửi hai lần đồng thời
def _khoa_dang_giu(ten: str) -> bool:
    """True nếu MỘT KẾT NỐI KHÁC không lấy được khoá advisory `ten` (tức giao dịch của test đang giữ)."""
    from backend.db import ket_noi
    with ket_noi() as c2:
        c2.execute("SET TRANSACTION READ ONLY")
        ok = c2.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS ok", (ten,)).fetchone()["ok"]
        c2.rollback()
    return not ok


def test_r2_khoa_theo_ky_thi_va_bam_anh(conn_thu):
    import hashlib
    nhan, _ = _gia_dua(conn_thu, 0)
    anh = b"noi dung anh r2"
    dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 31337, anh, "a.jpg", 1, nhan=nhan)
    sha = hashlib.sha256(anh).hexdigest()
    assert _khoa_dang_giu(f"ar:anh:31337:{sha}"), "yêu cầu thứ hai CÙNG ảnh, CÙNG kỳ thi phải bị chặn tới khi giao dịch này kết thúc"
    assert not _khoa_dang_giu(f"ar:anh:31338:{sha}"), "kỳ thi khác: không chặn"
    assert not _khoa_dang_giu(f"ar:anh:31337:{hashlib.sha256(b'anh khac').hexdigest()}"), "ảnh khác: không chặn"


def test_r2_lo_khong_khoa_theo_anh(conn_thu):
    import hashlib
    nhan, _ = _gia_dua(conn_thu, 0)
    anh = b"anh trong lo r2"
    dong_thoi.nhan_anh_an_toan(conn_thu, None, None, 31339, anh, "a.jpg", 1, nhan=nhan, khoa_theo_anh=False)
    assert not _khoa_dang_giu(f"ar:anh:31339:{hashlib.sha256(anh).hexdigest()}")


def test_r2_main_lo_tai_nhieu_anh_tat_khoa_theo_anh():
    import inspect

    from backend import main
    nguon = inspect.getsource(main.tai_nhieu_anh)
    assert "khoa_theo_anh=False" in nguon and "khoa_theo_anh" not in inspect.getsource(main.tai_mot_anh)
