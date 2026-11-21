from typing import Literal

from pydantic import BaseModel, Field

from . import nhat_ky, service


class XemLaiCauTuCham(BaseModel):
    action: Literal["keep", "set"] = Field(description="keep = giữ như máy chấm (chỉ ghi đã xem); set = chọn lại đáp án thật")
    selected_options: str | None = Field(default=None, max_length=4, description="Khi action = set: 'B', 'AC'... ('' = bỏ trống)")
    note: str | None = Field(default=None, max_length=500)


class MucGiu(BaseModel):
    sheet_id: int
    question_no: int


class GiuTatCa(BaseModel):
    items: list[MucGiu] = Field(min_length=1, max_length=2000, description="ĐÚNG các câu đang hiển thị trong mục 'Đã chấm tự động – cần xem lại'")
    confirm: Literal[True]


class KetQuaGiu(BaseModel):
    da_giu: int
    bo_qua: int = Field(description="Số câu không còn ở trạng thái cần xem lại (đã có người xử lý / phiếu bị từ chối) – không ghi gì")


class CauTuCham(BaseModel):
    sheet_id: int
    question_no: int
    omr_reading: str | None
    selected_options: str
    original_filename: str | None
    detected_sbd: str | None
    student_name: str | None
    official_score: float | None
    result_status: str | None
    sheet_status: str


class KetQuaXemLai(BaseModel):
    sheet_id: int
    question_no: int
    da_sua: bool
    status: str


def giu_tat_ca(conn, exam_id: int, body: GiuTatCa, nd) -> dict:
    thuoc = {r["sheet_id"] for r in conn.execute("SELECT sheet_id FROM answer_sheets WHERE exam_id = %s", (exam_id,)).fetchall()}
    ngoai = sorted({m.sheet_id for m in body.items} - thuoc)
    if ngoai:
        raise service.DuLieuSai(f"Phiếu {', '.join(map(str, ngoai))} không thuộc kỳ thi {exam_id}. Chưa ghi câu nào.")
    da, bo = service.giu_nhu_may_cham(conn, [(m.sheet_id, m.question_no) for m in body.items], nd.user_id)
    if da:
        nhat_ky.ghi(conn, nd, "giu_nhu_may_cham", exam_id, {"so_cau": len(da), "bo_qua": len(bo),
                                                             "cau": [{"phieu": s, "cau": q} for s, q in da]})
    return {"da_giu": len(da), "bo_qua": len(bo)}
