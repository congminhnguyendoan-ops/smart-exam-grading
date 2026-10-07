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
    exam_date: date | None
    num_questions: int
    max_score: float
    pass_score: float
    codes: list[MaDeOut]
    sheets: SoPhieu


class KyThiTomTat(BaseModel):
    exam_id: int
    exam_title: str
    num_questions: int
    max_score: float
    exam_date: date | None
    so_phieu: int


class KyThiTao(BaseModel):
    exam_id: int


# ------------------------------------------------------------------------------------------------ phiếu
class CotChuSo(BaseModel):
    vi_tri: int
    chu_so: str = Field(description="'0'–'9' hoặc '?' (không ô nào / nhiều ô)")
    can_xem: bool
    ly_do: list[str]
    do_tin_cay: float


class TruongDinhDanh(BaseModel):
    detected: str | None
    can_xem: bool
    columns: list[CotChuSo]


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
    reasons: list[str] = Field(description="o_mo | nhieu_o | tin_cay_thap | vi_tri (rỗng nếu chắc chắn)")
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


class PhieuTomTat(BaseModel):
    sheet_id: int
    status: str
    original_filename: str | None
    detected_sbd: str | None
    reject_code: str | None
    raw_score: float | None = Field(description="Điểm tạm (câu chắc chắn)")
    official_score: float | None
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
