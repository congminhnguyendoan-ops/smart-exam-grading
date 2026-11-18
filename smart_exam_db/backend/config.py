import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


class LoiCauHinh(Exception):
    pass


@dataclass(frozen=True)
class CauHinh:
    database_url: str
    storage_dir: Path
    mo_hinh_omr: Path
    mo_hinh_ocr: Path
    nguoi_dung_demo: str
    gioi_han_anh_mb: int
    auth_mode: str = "on"
    auth_secret: str = ""
    session_hours: float = 8.0
    cookie_secure: bool = False
    anh_xoa_tu_dong: bool = False
    anh_giu_gio: float = 24.0
    anh_giu_demo: bool = True
    public_base_url: str = ""
    cham_dong_thoi: int = 4
    cham_cho_giay: float = 30.0
    health_chi_tiet: bool = False
    moi_truong: str = ""
    max_anh_moi_lo: int = 30
    max_diem_anh: int = 60_000_000


def lay_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise LoiCauHinh("Chưa đặt DATABASE_URL. Sao chép .env.example thành .env (trong smart_exam_db/) "
                         "rồi điền thông tin kết nối.")
    return url


def lay_cau_hinh() -> CauHinh:
    url = lay_database_url()
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
    moi_truong = os.environ.get("MOI_TRUONG", "").strip().lower()
    if moi_truong not in ("", "production"):
        raise LoiCauHinh(f"MOI_TRUONG chỉ nhận 'production' hoặc để trống (đang là '{moi_truong}').")
    if moi_truong == "production":
        kiem_san_xuat(mode, secret, os.environ.get("COOKIE_SECURE", "0"), os.environ.get("WEB_CONCURRENCY", "1"))
    return CauHinh(
        database_url=url,
        storage_dir=kho if kho.is_absolute() else ROOT / kho,
        mo_hinh_omr=mo_hinh if mo_hinh.is_absolute() else ROOT / mo_hinh,
        mo_hinh_ocr=mo_hinh_ocr if mo_hinh_ocr.is_absolute() else ROOT / mo_hinh_ocr,
        nguoi_dung_demo=os.environ.get("DEMO_USER", "gv_an"),
        gioi_han_anh_mb=int(os.environ.get("MAX_UPLOAD_MB", "25")),
        auth_mode=mode, auth_secret=secret, session_hours=float(os.environ.get("SESSION_HOURS", "8")),
        cookie_secure=_bat(os.environ.get("COOKIE_SECURE", "0")),
        anh_xoa_tu_dong=_bat(os.environ.get("ANH_XOA_TU_DONG", "0")),
        anh_giu_gio=float(os.environ.get("ANH_GIU_GIO", "24")),
        anh_giu_demo=_bat(os.environ.get("ANH_GIU_DEMO", "1")),
        public_base_url=dia_chi_goc_hop_le(os.environ.get("PUBLIC_BASE_URL", "")),
        cham_dong_thoi=_so_nguyen_duong("CHAM_DONG_THOI", "4"), cham_cho_giay=_so_thuc_duong("CHAM_CHO_GIAY", "30"),
        health_chi_tiet=_bat(os.environ.get("HEALTH_CHI_TIET", "0")),
        moi_truong=moi_truong,
        max_anh_moi_lo=_so_nguyen_duong("MAX_ANH_MOI_LO", "30"), max_diem_anh=_so_nguyen_duong("MAX_DIEM_ANH", "60000000"),
    )


def kiem_san_xuat(auth_mode: str, auth_secret: str, cookie_secure: str, web_concurrency: str) -> None:
    loi = []
    if auth_mode != "on":
        loi.append(f"AUTH_MODE phải là 'on' (đang là '{auth_mode}'): chế độ demo bỏ đăng nhập")
    if not _bat(cookie_secure):
        loi.append("COOKIE_SECURE phải là 1 (cookie đăng nhập chỉ đi qua HTTPS)")
    if len(auth_secret) < 32:
        loi.append("AUTH_SECRET phải dài ≥ 32 ký tự")
    elif auth_secret.startswith("DOI_"):
        loi.append("AUTH_SECRET vẫn là giá trị mẫu (bắt đầu bằng 'DOI_') – hãy sinh khoá thật")
    wc = web_concurrency.strip()
    if wc and (not wc.isdigit() or int(wc) != 1):
        loi.append(f"chỉ chạy 1 worker (WEB_CONCURRENCY='{wc}'): khoá đăng nhập và giới hạn chấm tính theo từng tiến trình")
    if loi:
        raise LoiCauHinh("MOI_TRUONG=production nhưng cấu hình chưa an toàn: " + "; ".join(loi) + ". Xem .env.production.example.")


def docs_bat() -> bool:
    return _bat(os.environ.get("DOCS_ENABLED", "0"))


def _so_nguyen_duong(ten: str, mac_dinh: str) -> int:
    v = os.environ.get(ten, mac_dinh).strip()
    if not v.isdigit() or int(v) < 1:
        raise LoiCauHinh(f"{ten} phải là số nguyên ≥ 1 (đang là '{v}').")
    return int(v)


def _so_thuc_duong(ten: str, mac_dinh: str) -> float:
    try:
        x = float(os.environ.get(ten, mac_dinh).strip())
    except ValueError:
        raise LoiCauHinh(f"{ten} phải là số giây > 0 (đang là '{os.environ.get(ten)}').") from None
    if not 0 < x <= 3600:
        raise LoiCauHinh(f"{ten} phải trong (0; 3600] giây (đang là {x}).")
    return x


def dia_chi_goc_hop_le(v: str) -> str:
    v = v.strip().rstrip("/")
    if v and not re.fullmatch(r"https?://[A-Za-z0-9.\-\[\]:]+(/[A-Za-z0-9._~\-/]*)?", v):
        raise LoiCauHinh(f"PUBLIC_BASE_URL phải dạng http(s)://tên-máy[:cổng][/đường-dẫn] (đang là '{v}').")
    return v


def _bat(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "on")
