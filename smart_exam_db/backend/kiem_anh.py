"""
kiem_anh.py - Lệnh AU (T3): giới hạn tải lên ở tầng ứng dụng, chạy TRƯỚC khi ảnh vào logic chấm (service.py không đổi).

  1. GioiHanThanMiddleware : từ chối 413 theo Content-Length ngay khi nhận tiêu đề; thân chunked (không Content-Length) bị đếm byte và dừng khi vượt.
  2. doc_tep_gioi_han      : đọc từng đoạn, dừng + 413 ngay khi vượt MAX_UPLOAD_MB (không bao giờ nạp cả tệp quá lớn vào RAM).
  3. kiem_noi_dung_anh     : nội dung THẬT phải là JPEG / PNG / HEIC (đọc chữ ký đầu tệp, không tin đuôi); kích thước (rộng × cao) đọc từ TIÊU ĐỀ
                              ảnh, không giải mã; vượt MAX_DIEM_ANH -> 422 tiếng Việt.
Thứ tự kiểm: Content-Length -> đọc có giới hạn -> chữ ký -> số điểm ảnh -> (mới tới) preprocess / OMR / CNN.
"""
import io
import json
import re

from PIL import Image

from .service import LoiDichVu

CHU_KY_JPEG = b"\xff\xd8\xff"
CHU_KY_PNG = b"\x89PNG\r\n\x1a\n"
THUONG_HIEU_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1", b"heif"}
DOAN_DOC = 1024 * 1024
_DUONG_DAN_TAI = re.compile(r"^/exams/\d+/sheets(/batch)?$")
PHI_MULTIPART = 256 * 1024            # tiêu đề / ranh giới multipart + tên tệp: dư cho mỗi yêu cầu


class TepQuaLon(LoiDichVu):
    ma_http = 413


class AnhKhongHopLe(LoiDichVu):
    ma_http = 422


class QuaNhieuAnh(LoiDichVu):
    ma_http = 413


def ap_dung_gioi_han_diem_anh(max_diem: int) -> None:
    """Image.MAX_IMAGE_PIXELS = max_diem: Pillow cảnh báo > max, báo lỗi (DecompressionBombError) > 2 × max khi mở / giải mã (kể cả đường HEIC của cv_engine)."""
    Image.MAX_IMAGE_PIXELS = int(max_diem)


# ------------------------------------------------------------------------------------------------ 1. giới hạn thân yêu cầu (ASGI)
def gioi_han_than(duong_dan: str, max_mb: int, max_anh_moi_lo: int) -> int | None:
    """Số byte tối đa của THÂN yêu cầu cho đường dẫn tải ảnh; None = không phải đường dẫn tải ảnh (không giới hạn ở đây)."""
    m = _DUONG_DAN_TAI.match(duong_dan)
    if not m:
        return None
    so_tep = max_anh_moi_lo if m.group(1) else 1
    return so_tep * max_mb * 1024 * 1024 + (so_tep + 1) * PHI_MULTIPART


class _VuotGioiHan(Exception):
    pass


class GioiHanThanMiddleware:
    """Pure ASGI. Chỉ áp cho POST /exams/{id}/sheets và /sheets/batch. Cấu hình lấy lúc có yêu cầu (đọc `app.state.cfg`) để test đổi được."""

    def __init__(self, app, lay_gioi_han):
        self.app = app
        self.lay_gioi_han = lay_gioi_han              # () -> (max_mb, max_anh_moi_lo)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        max_mb, max_lo = self.lay_gioi_han()
        gioi_han = gioi_han_than(scope["path"], max_mb, max_lo)
        if gioi_han is None:
            return await self.app(scope, receive, send)
        for ten, gia_tri in scope["headers"]:
            if ten == b"content-length":
                try:
                    if int(gia_tri) > gioi_han:
                        return await _tra_413(send, max_mb, scope["path"].endswith("/batch"), max_lo)
                except ValueError:
                    pass
        da_nhan = 0
        vuot = False

        async def nhan():
            nonlocal da_nhan, vuot
            msg = await receive()
            if msg["type"] == "http.request":
                da_nhan += len(msg.get("body", b""))
                if da_nhan > gioi_han:
                    vuot = True
                    raise _VuotGioiHan()                    # FastAPI có thể nuốt ngoại lệ này thành 400 -> `gui` đổi phản hồi sang 413 nhờ cờ `vuot`
            return msg

        da_tra = False

        async def gui(msg):
            nonlocal da_tra
            if vuot:
                if not da_tra:
                    da_tra = True
                    await _tra_413(send, max_mb, scope["path"].endswith("/batch"), max_lo)
                return                                       # bỏ phản hồi gốc (400 do nuốt ngoại lệ)
            if msg["type"] == "http.response.start":
                da_tra = True
            await send(msg)

        try:
            await self.app(scope, nhan, gui)
        except _VuotGioiHan:
            pass
        if vuot and not da_tra:
            await _tra_413(send, max_mb, scope["path"].endswith("/batch"), max_lo)


async def _tra_413(send, max_mb: int, la_lo: bool, max_lo: int) -> None:
    noi_dung = (f"Lô ảnh quá lớn (tối đa {max_lo} ảnh, mỗi ảnh {max_mb} MB)." if la_lo else f"Ảnh lớn hơn {max_mb} MB.")
    body = json.dumps({"detail": noi_dung}, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"connection", b"close")]})
    await send({"type": "http.response.body", "body": body})


# ------------------------------------------------------------------------------------------------ 2. đọc tệp có giới hạn
def doc_tep_gioi_han(tep, max_mb: int) -> bytes:
    """Đọc `tep` (đối tượng có .read(n), vd UploadFile.file) từng đoạn; > max_mb MB -> TepQuaLon NGAY (không đọc tiếp)."""
    gioi_han = max_mb * 1024 * 1024
    phan, tong = [], 0
    while True:
        doan = tep.read(DOAN_DOC)
        if not doan:
            break
        tong += len(doan)
        if tong > gioi_han:
            raise TepQuaLon(f"Ảnh lớn hơn {max_mb} MB.")
        phan.append(doan)
    return b"".join(phan)


# ------------------------------------------------------------------------------------------------ 3. nội dung thật + số điểm ảnh
def loai_anh(du_lieu: bytes) -> str | None:
    """'jpeg' | 'png' | 'heic' theo CHỮ KÝ đầu tệp; None nếu không phải ba loại cho phép."""
    if du_lieu.startswith(CHU_KY_JPEG):
        return "jpeg"
    if du_lieu.startswith(CHU_KY_PNG):
        return "png"
    if len(du_lieu) >= 12 and du_lieu[4:8] == b"ftyp" and du_lieu[8:12] in THUONG_HIEU_HEIC:
        return "heic"
    return None


def kiem_noi_dung_anh(du_lieu: bytes, max_diem: int) -> tuple[str, int, int]:
    """Trả (loại, rộng, cao). Không giải mã điểm ảnh: Pillow chỉ đọc tiêu đề. Sai nội dung / vượt số điểm ảnh -> AnhKhongHopLe (422)."""
    loai = loai_anh(du_lieu)
    if loai is None:
        raise AnhKhongHopLe("Tệp không phải ảnh JPEG, PNG hoặc HEIC (nội dung không đúng định dạng ảnh).")
    if loai == "heic":
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:                          # pragma: no cover – pillow_heif có trong requirements
            raise AnhKhongHopLe("Máy chủ chưa hỗ trợ ảnh HEIC.") from None
    try:
        with Image.open(io.BytesIO(du_lieu)) as im:  # đọc tiêu đề; lazy – chưa giải mã
            rong, cao = im.size
    except Image.DecompressionBombError:
        raise AnhKhongHopLe(f"Ảnh có quá nhiều điểm ảnh (tối đa {max_diem // 1_000_000} triệu).") from None
    except Exception:  # noqa: BLE001 – mọi lỗi mở tệp = tiêu đề ảnh hỏng
        raise AnhKhongHopLe("Không đọc được tiêu đề ảnh – tệp bị hỏng hoặc không phải ảnh hợp lệ.") from None
    if rong <= 0 or cao <= 0 or rong * cao > max_diem:
        raise AnhKhongHopLe(f"Ảnh có {rong}×{cao} = {rong * cao / 1e6:.0f} triệu điểm ảnh, vượt giới hạn {max_diem // 1_000_000} triệu. "
                            "Hãy chụp ở độ phân giải thấp hơn (phiếu chỉ cần khoảng 12 MP).")
    return loai, rong, cao


def nhan_tep_an_toan(tep, max_mb: int, max_diem: int) -> bytes:
    """Đọc có giới hạn rồi kiểm nội dung. Trả byte ảnh đã được kiểm (đưa tiếp cho dong_thoi.nhan_anh_an_toan)."""
    du_lieu = doc_tep_gioi_han(tep, max_mb)
    if not du_lieu:
        raise AnhKhongHopLe("File ảnh rỗng.")
    kiem_noi_dung_anh(du_lieu, max_diem)
    return du_lieu
