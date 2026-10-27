"""schemas.py - Hợp đồng dữ liệu của API (pydantic). Tên trường tiếng Anh theo cột CSDL; thông báo / mô tả tiếng Việt."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------------------------------------ đề thi
class MaDeMoi(BaseModel):
    code: str = Field(description="Mã đề, 1–6 chữ số (vd '101')", examples=["101"])
    answers: str = Field(description="Đáp án chuẩn theo thứ tự câu, mỗi câu một chữ cái A–D (độ dài = num_questions)",
                         examples=["ABCDABCDAB"])


class KyThiMoi(BaseModel):
    exam_title: str = Field(min_length=3, max_length=200)
    subject_code: str = Field(min_length=1, max_length=20, description="Mã môn; chưa có thì tạo mới")
    subject_name: str | None = Field(default=None, max_length=150)
    exam_date: date | None = None
    duration_min: int | None = Field(default=None, gt=0, le=1000)
    num_questions: int = Field(gt=0, le=40, description="Tối đa 40 (mẫu phiếu chuẩn)")
    max_score: Decimal = Field(default=Decimal(10), gt=0, le=999)
    pass_score: Decimal = Field(default=Decimal(5), ge=0, le=999)
    class_id: int | None = Field(default=None, description="Lớp của kỳ thi (tuỳ chọn): phải TỒN TẠI và thuộc lớp bạn phụ trách (admin: bất kỳ)")
    class_code: str | None = Field(default=None, max_length=30, description="Hoặc mã lớp (vd 'CNTT-K22A'); không tự tạo lớp mới")
    template_name: str | None = Field(default=None, description="Mẫu phiếu; bỏ trống = mẫu đầu tiên ('Phiếu chuẩn 40 câu A4')")
    codes: list[MaDeMoi] = Field(min_length=1, max_length=20)


class MaDeOut(BaseModel):
    code: str
    answers: str


class SoPhieu(BaseModel):
    tong: int
    da_cham: int = Field(description="status = graded")
    can_xem: int = Field(description="status = needs_review")
    bi_tu_choi: int = Field(description="status = rejected")


class KyThiOut(BaseModel):
    exam_id: int
    exam_title: str
    subject_code: str
    subject_name: str
    class_id: int | None = None
    class_code: str | None = None
    class_name: str | None = None
    exam_date: date | None
    num_questions: int
    max_score: float
    pass_score: float
    codes: list[MaDeOut]
    sheets: SoPhieu


class KyThiTomTat(BaseModel):
    exam_id: int
    exam_title: str
    subject_code: str
    subject_name: str
    class_id: int | None = None
    class_code: str | None = None
    class_name: str | None = None
    num_questions: int
    max_score: float
    exam_date: date | None
    so_phieu: int


class KyThiTao(BaseModel):
    exam_id: int


# ------------------------------------------------------------------------------------------------ phiếu
class ChuVietTay(BaseModel):
    """Chữ số CNN đọc từ ô VIẾT TAY của cột (kênh thứ hai, độc lập với bubble)."""
    pos: int = Field(description="Vị trí ô viết tay (tính từ 0, khoá của ảnh /digits/{field}/{pos}/image và của ocr_digits)")
    chu_so: str = Field(description="'0'–'9' hoặc '?' (ô trống / không đọc được)")
    p: float = Field(description="Độ tin cậy (xác suất đã hiệu chỉnh) của chữ số đọc được; 0 khi '?'")
    top_k: list[dict] = Field(description="[{d, p}] 3 chữ số khả dĩ nhất")
    o_trong: bool
    loi_o: str = Field(description="'' | o_it_muc | khong_phai_chu_so")
    ok_vien: bool = Field(description="False: không dò được khung ô, vị trí ước lượng")
    corrected: str | None = Field(default=None, description="Chữ số giáo viên đã chốt (nếu có sửa)")
    has_crop: bool = Field(default=False, description="Có ảnh cắt: GET /sheets/{id}/digits/{field}/{pos}/image")


class CotChuSo(BaseModel):
    vi_tri: int
    chu_so: str = Field(description="Chữ số chốt: bubble khi bubble đọc được, '?' nếu không đọc được")
    can_xem: bool
    ly_do: list[str] = Field(description="Mã lý do cần xem của cột (OMR + đối chiếu hai kênh, xem MA_LY_DO_OCR)")
    do_tin_cay: float = Field(description="min(độ tin cậy bubble, xác suất CNN) của cột")
    bubble: str | None = Field(default=None, description="Chữ số đọc từ ô tô (bubble); '?' nếu không đọc được")
    handwriting: ChuVietTay | None = Field(default=None, description="Chữ số đọc từ chữ viết tay; None ở phiếu cũ (trước Tuần 6)")


class TruongDinhDanh(BaseModel):
    detected: str | None
    can_xem: bool
    columns: list[CotChuSo]
    reasons: list[str] = Field(default_factory=list, description="Lý do cần xem của cả trường (gộp các cột + danh sách thi)")


class MaDeDoc(TruongDinhDanh):
    matched_code: str | None = Field(description="Mã đề tìm thấy trong kỳ thi (None nếu chưa chắc / không có)")


class SinhVien(BaseModel):
    student_id: int
    student_code: str
    full_name: str


class Diem(BaseModel):
    official: float | None = Field(description="Điểm chính thức (bảng results). None khi phiếu chưa chốt")
    result_status: str | None = Field(description="auto (máy tự chốt) | confirmed (đã qua giáo viên)")
    provisional: float | None = Field(description="Điểm TẠM: chỉ tính các câu chắc chắn")
    max_possible: float | None = Field(description="Điểm tối đa nếu mọi câu cần xem đều đúng")
    num_correct: int | None
    pending_questions: int = Field(description="Số câu OMR còn cần xem")
    max_score: float


class MucReview(BaseModel):
    model_config = ConfigDict(extra="allow")
    review_id: int
    reasons: list[str]
    status: str
    priority: int


class CauOut(BaseModel):
    question_no: int
    selected_options: str
    state: Literal["blank", "filled", "faint", "multiple"]
    needs_review: bool
    reasons: list[str] = Field(description="o_mo | nhieu_o | tin_cay_thap | vi_tri | vet_nho | to_nhat (rỗng nếu chắc chắn)")
    is_correct: bool | None = Field(description="None = chưa chấm (cần xem hoặc chưa biết mã đề)")
    manually_edited: bool
    omr_selected_options: str | None = Field(description="Cách máy đọc ban đầu")
    confidence: float | None


class PhieuOut(BaseModel):
    sheet_id: int
    exam_id: int
    status: Literal["uploaded", "processing", "processed", "graded", "needs_review", "rejected", "error"]
    original_filename: str | None
    uploaded_at: datetime
    reject_code: str | None = Field(description="Mã từ chối của preprocess() (anh_mo, thieu_marker, ...)")
    reject_message: str | None = Field(description="Thông báo cho giáo viên")
    sbd: TruongDinhDanh | None
    exam_code: MaDeDoc | None
    student: SinhVien | None
    score: Diem | None
    review: MucReview | None
    questions: list[CauOut]
    image_deleted_at: datetime | None = Field(default=None, description="Ảnh đã được xoá (chính sách ảnh tạm) lúc này – API ảnh trả 410")


class PhieuTomTat(BaseModel):
    sheet_id: int
    status: str
    original_filename: str | None
    detected_sbd: str | None
    detected_exam_code: str | None = None
    reject_code: str | None
    reject_message: str | None = None
    raw_score: float | None = Field(description="Điểm tạm (câu chắc chắn)")
    official_score: float | None
    result_status: str | None = Field(default=None, description="auto | confirmed (khi đã có điểm chính thức)")
    student_name: str | None = None
    pending_questions: int


class CauCanXem(BaseModel):
    sheet_id: int
    question_no: int
    omr_reading: str | None = Field(description="Máy đọc: '' = bỏ trống, 'B', 'AC'...")
    omr_state: str | None
    reasons: list[str]
    confidence: float | None
    option_probs: dict | None = Field(description="{A: {blank, faint, filled}, ...}")


class TaiAnhOut(BaseModel):
    sheet_id: int
    da_ton_tai: bool = Field(description="True: ảnh này đã tải trước đó cho kỳ thi, trả phiếu cũ")
    status: str
    reject_code: str | None
    reject_message: str | None
    pending_questions: int
    provisional_score: float | None
    official_score: float | None


class MucTaiNhieu(BaseModel):
    filename: str | None
    sheet_id: int | None = None
    da_ton_tai: bool = False
    status: str | None = None
    reject_code: str | None = None
    reject_message: str | None = None
    pending_questions: int | None = None
    error: str | None = Field(default=None, description="Lỗi xử lý ảnh này (các ảnh khác vẫn được xử lý)")


class TaiNhieuOut(BaseModel):
    batch_id: int
    tong: int
    results: list[MucTaiNhieu]


# ------------------------------------------------------------------------------------------------ giáo viên
class XuLyCau(BaseModel):
    action: Literal["confirm", "set"] = Field(
        description="confirm = nhận cách máy đọc (không dùng cho câu cần xem vì vị trí); set = giáo viên chốt lựa chọn")
    selected_options: str | None = Field(default=None, description="Với action = set: 'B', 'AC', hoặc '' = bỏ trống")
    note: str | None = Field(default=None, max_length=500)


class DinhDanh(BaseModel):
    sbd: str | None = Field(default=None, description="Số báo danh đúng (chữ số)")
    exam_code: str | None = Field(default=None, description="Mã đề đúng (chữ số)")
    note: str | None = Field(default=None, max_length=500)


class LyDoTuChoi(BaseModel):
    message: str = Field(description="Thông báo cho giáo viên (MA_LY_DO của preprocess)")
    advice: str = Field(description="Lời khuyên chụp lại")


class UngVienIp(BaseModel):
    ip: str
    card: str
    ao: bool = Field(description="Card ảo (WSL / Docker / VPN …) – điện thoại thường không tới được")
    mac_dinh: bool = Field(description="IP của tuyến mặc định")
    hotspot: bool = Field(description="192.168.137.x – điểm phát sóng của Windows")
    url: str


class KetNoi(BaseModel):
    lan_bat: bool = Field(description="Server khởi động cho mạng nội bộ (--host 0.0.0.0, tools/chay_server_lan.py)")
    cong: int
    url: str | None = Field(description="Địa chỉ trang điện thoại /m theo IP được chọn")
    qr_svg: str = Field(description="Mã QR của url (SVG); rỗng nếu thiếu segno")
    ung_vien: list[UngVienIp]
    gioi_han_anh_mb: int


# ------------------------------------------------------------------------------------------------ bảng điểm
class DongBangDiem(BaseModel):
    stt: int
    student_id: int
    sbd: str
    full_name: str
    exam_code: str | None
    num_correct: int | None = Field(description="Số câu đúng – CHỈ khi điểm đã chính thức")
    score: float | None = Field(description="Điểm CHÍNH THỨC (bảng results). Phiếu chưa duyệt xong luôn là null")
    provisional_score: float | None = Field(description="Điểm tạm (chỉ phiếu chưa duyệt xong) – không phải điểm chính thức")
    provisional_correct: int | None
    pending_questions: int = Field(description="Số câu còn chờ giáo viên (phiếu chưa duyệt xong)")
    status: Literal["official", "pending", "rejected", "no_sheet"]
    status_label: str
    sheet_id: int | None
    sheets: int = Field(description="Số phiếu đã ghép thí sinh này (>1: tải nhiều lần / trùng SBD)")


class PhieuKhongGhep(BaseModel):
    sheet_id: int
    status: str
    original_filename: str | None
    detected_sbd: str | None
    reject_code: str | None
    reject_message: str | None


class TongBangDiem(BaseModel):
    official: int
    pending: int
    no_sheet: int
    rejected: int = Field(description="Phiếu bị từ chối (ảnh không dùng được – không biết của thí sinh nào)")
    unmatched_review: int = Field(description="Phiếu cần xem nhưng chưa ghép được thí sinh")
    students: int


class BangDiemOut(BaseModel):
    exam_id: int
    exam_title: str
    subject_code: str
    subject_name: str
    class_id: int | None = None
    class_code: str | None = None
    class_name: str | None = None
    max_score: float
    num_questions: int
    exported_on: str
    counts: TongBangDiem
    rows: list[DongBangDiem]
    unmatched: list[PhieuKhongGhep]


# ------------------------------------------------------------------------------------------------ tài khoản / lớp
class DangNhap(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class HoSo(BaseModel):
    user_id: int
    username: str
    full_name: str
    email: str
    role: Literal["admin", "teacher", "student"]
    last_login_at: datetime | None = Field(default=None, description="Lần đăng nhập gần nhất (None nếu chưa từng)")
    created_at: datetime | None = None


class SuaHoSo(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)


class DoiMatKhau(BaseModel):
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200, description="Tối thiểu 8 ký tự, khác mật khẩu cũ")


class LopCuaToi(BaseModel):
    class_id: int
    class_code: str
    class_name: str
    academic_year: str | None
    subject_id: int | None = Field(description="Môn bạn dạy ở lớp này (None nếu chưa gán / admin)")
    subject_code: str | None
    subject_name: str | None
    so_sinh_vien: int


class SinhVienLop(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    date_of_birth: date | None
    gender: str | None
    email: str | None


class LopThongTin(BaseModel):
    class_id: int
    class_code: str
    class_name: str
    academic_year: str | None


class DsSinhVienLop(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    lop: LopThongTin
    tong: int
    trang: int
    co_trang: int
    sinh_vien: list[SinhVienLop]

