"""
config.py - Cấu hình backend đọc từ biến môi trường / file .env (smart_exam_db/.env, KHÔNG vào git).

Biến môi trường đã đặt sẵn luôn thắng giá trị trong .env. Không có mật khẩu mặc định trong code: thiếu DATABASE_URL thì báo lỗi rõ.
Mẫu: .env.example.
"""
import os
import re
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
    # Ảnh tạm (docs/thiet_ke_chup_dien_thoai.md mục 7): xoá ảnh của phiếu đã chốt sau anh_giu_gio giờ. Luồng dọn CHỈ chạy khi anh_xoa_tu_dong
    # (chỉ tools/chay_server_lan.py --bat-don-anh bật – lệnh Z); pytest / tools/* dùng TestClient trên CSDL thật nên mặc định TẮT – không bao giờ xoá ảnh thật khi kiểm thử.
    anh_xoa_tu_dong: bool = False
    anh_giu_gio: float = 24.0
    anh_giu_demo: bool = True    # không xoá ảnh của kỳ thi có "[DEMO" trong tên (demo / báo cáo cần ảnh)
    # Địa chỉ gốc in trong mã QR trang bìa kỳ thi (vd https://thi.truong.edu.vn hoặc http://192.168.1.5:8000). Rỗng = lấy từ yêu cầu (request.base_url).
    public_base_url: str = ""
    # Lệnh AR – R5: giới hạn số ảnh được chấm CÙNG LÚC trong một tiến trình (mỗi ảnh ~150 MB bộ nhớ; thông lượng bão hoà từ ~4 yêu cầu – docs/lenh_ah.md).
    # Mặc định 4 (≥ 2 để không chạm hàng đợi tải 2 lượt của giao diện). Vượt giới hạn: yêu cầu CHỜ tối đa cham_cho_giay rồi 503 + Retry-After.
    cham_dong_thoi: int = 4
    cham_cho_giay: float = 30.0
    # Lệnh AU – T1: /health công khai chỉ trả trạng thái; HEALTH_CHI_TIET=1 mới thêm phiên bản + SHA mô hình (nội bộ / kiểm thử).
    health_chi_tiet: bool = False
    # Lệnh AU – T3: giới hạn tải lên ở tầng ứng dụng (backend/kiem_anh.py). gioi_han_anh_mb (MAX_UPLOAD_MB) = tối đa MỘT ảnh.
    moi_truong: str = ""             # "" (mặc định: hành vi LAN / dev như cũ) | "production" (lệnh AU – T4: từ chối khởi động nếu cấu hình không an toàn)
    max_anh_moi_lo: int = 30
    max_diem_anh: int = 60_000_000


def lay_database_url() -> str:
    """Chỉ cần DATABASE_URL (công cụ CSDL như backend.migrate không được đòi AUTH_SECRET)."""
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
    """Lệnh AU – T4 / T4b. MOI_TRUONG=production: gom MỌI lỗi cấu hình rồi từ chối khởi động một lần (không lộ giá trị bí mật).
    1 worker: bộ đếm khoá đăng nhập (auth.gioi_han) và giới hạn chấm đồng thời (CHAM_DONG_THOI) nằm trong BỘ NHỚ TỪNG TIẾN TRÌNH –
    N worker nhân giới hạn lên N lần. Ở đây chỉ phát hiện được WEB_CONCURRENCY; cờ `--workers` trên dòng lệnh do Dockerfile / docs cố định là 1."""
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
    """DOCS_ENABLED (mặc định 0). Đọc lúc tạo app (trước lifespan) nên tách khỏi CauHinh. 0 -> /docs, /redoc, /openapi.json trả 404."""
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
    """'' hoặc http(s)://máy[:cổng][/đường-dẫn] (bỏ '/' cuối). Sai dạng -> LoiCauHinh (không âm thầm in QR hỏng)."""
    v = v.strip().rstrip("/")
    if v and not re.fullmatch(r"https?://[A-Za-z0-9.\-\[\]:]+(/[A-Za-z0-9._~\-/]*)?", v):
        raise LoiCauHinh(f"PUBLIC_BASE_URL phải dạng http(s)://tên-máy[:cổng][/đường-dẫn] (đang là '{v}').")
    return v


def _bat(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "on")
