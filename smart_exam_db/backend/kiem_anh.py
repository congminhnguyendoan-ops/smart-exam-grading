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
PHI_MULTIPART = 256 * 1024


class TepQuaLon(LoiDichVu):
    ma_http = 413


class AnhKhongHopLe(LoiDichVu):
    ma_http = 422


class QuaNhieuAnh(LoiDichVu):
    ma_http = 413


def ap_dung_gioi_han_diem_anh(max_diem: int) -> None:
    Image.MAX_IMAGE_PIXELS = int(max_diem)


def gioi_han_than(duong_dan: str, max_mb: int, max_anh_moi_lo: int) -> int | None:
    m = _DUONG_DAN_TAI.match(duong_dan)
    if not m:
        return None
    so_tep = max_anh_moi_lo if m.group(1) else 1
    return so_tep * max_mb * 1024 * 1024 + (so_tep + 1) * PHI_MULTIPART


class _VuotGioiHan(Exception):
    pass


class GioiHanThanMiddleware:

    def __init__(self, app, lay_gioi_han):
        self.app = app
        self.lay_gioi_han = lay_gioi_han

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
                    raise _VuotGioiHan()
            return msg

        da_tra = False

        async def gui(msg):
            nonlocal da_tra
            if vuot:
                if not da_tra:
                    da_tra = True
                    await _tra_413(send, max_mb, scope["path"].endswith("/batch"), max_lo)
                return
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


def doc_tep_gioi_han(tep, max_mb: int) -> bytes:
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


def loai_anh(du_lieu: bytes) -> str | None:
    if du_lieu.startswith(CHU_KY_JPEG):
        return "jpeg"
    if du_lieu.startswith(CHU_KY_PNG):
        return "png"
    if len(du_lieu) >= 12 and du_lieu[4:8] == b"ftyp" and du_lieu[8:12] in THUONG_HIEU_HEIC:
        return "heic"
    return None


def kiem_noi_dung_anh(du_lieu: bytes, max_diem: int) -> tuple[str, int, int]:
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
        with Image.open(io.BytesIO(du_lieu)) as im:
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
    du_lieu = doc_tep_gioi_han(tep, max_mb)
    if not du_lieu:
        raise AnhKhongHopLe("File ảnh rỗng.")
    kiem_noi_dung_anh(du_lieu, max_diem)
    return du_lieu
