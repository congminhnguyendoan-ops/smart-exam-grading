"""
config.py - Cấu hình backend đọc từ biến môi trường / file .env (smart_exam_db/.env, KHÔNG vào git).

Biến môi trường đã đặt sẵn luôn thắng giá trị trong .env. Không có mật khẩu mặc định trong code: thiếu DATABASE_URL thì báo lỗi rõ.
Mẫu: .env.example.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent            # smart_exam_db/
load_dotenv(ROOT / ".env", override=False)


class LoiCauHinh(Exception):
    """Thiếu / sai cấu hình (vd chưa có .env)."""


@dataclass(frozen=True)
class CauHinh:
    database_url: str
    storage_dir: Path          # ảnh phiếu lưu trên đĩa, CSDL chỉ giữ đường dẫn tương đối so với thư mục này
    mo_hinh_omr: Path
    mo_hinh_ocr: Path          # CNN chữ số viết tay (NumPy + JSON, Tuần 6)
    nguoi_dung_demo: str       # username tạm thay cho đăng nhập (nợ kỹ thuật: auth ở Tuần 7–8)
    gioi_han_anh_mb: int
    auth_mode: str = "on"      # "on" (mặc định, an toàn) | "demo" (hành vi cũ DEMO_USER / X-User, KHÔNG kiểm quyền – chỉ dev + test cũ)
    auth_secret: str = ""      # khoá ký phiên (HMAC); bắt buộc khi auth_mode = "on"; KHÔNG có giá trị mặc định trong code
    session_hours: float = 8.0
    cookie_secure: bool = False  # bật khi chạy sau https (COOKIE_SECURE=1)


def lay_cau_hinh() -> CauHinh:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise LoiCauHinh("Chưa đặt DATABASE_URL. Sao chép .env.example thành .env (trong smart_exam_db/) "
                         "rồi điền thông tin kết nối.")
    kho = Path(os.environ.get("STORAGE_DIR", "storage"))
    mo_hinh = Path(os.environ.get("OMR_MODEL", "models/omr_m1.json"))
    mo_hinh_ocr = Path(os.environ.get("OCR_MODEL", "models/ocr_cnn.json"))
    mode = os.environ.get("AUTH_MODE", "on").strip().lower()
    if mode not in ("on", "demo"):
        raise LoiCauHinh(f"AUTH_MODE phải là 'on' hoặc 'demo' (đang là '{mode}').")
    secret = os.environ.get("AUTH_SECRET", "").strip()
    if mode == "on" and len(secret) < 32:
        raise LoiCauHinh("Chưa đặt AUTH_SECRET (≥ 32 ký tự) trong .env – cần để ký phiên đăng nhập. Sinh khoá: "
                         "python -c \"import secrets; print(secrets.token_urlsafe(48))\"  (hoặc AUTH_MODE=demo chỉ để dev).")
    return CauHinh(
        database_url=url,
        storage_dir=kho if kho.is_absolute() else ROOT / kho,
        mo_hinh_omr=mo_hinh if mo_hinh.is_absolute() else ROOT / mo_hinh,
        mo_hinh_ocr=mo_hinh_ocr if mo_hinh_ocr.is_absolute() else ROOT / mo_hinh_ocr,
        nguoi_dung_demo=os.environ.get("DEMO_USER", "gv_an"),
        gioi_han_anh_mb=int(os.environ.get("MAX_UPLOAD_MB", "25")),
        auth_mode=mode, auth_secret=secret, session_hours=float(os.environ.get("SESSION_HOURS", "8")),
        cookie_secure=os.environ.get("COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes", "on"),
    )
