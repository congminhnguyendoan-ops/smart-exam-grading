"""
duyet_nhanh.py - Lệnh AF: DUYỆT NHANH cho giáo viên. KHÔNG đổi cách chấm / ngưỡng / OMR / CNN / đối chiếu hai kênh.

1. xac_nhan_hang_loat: "Xác nhận tất cả câu còn lại như máy đọc" cho MỘT phiếu.
   - Chỉ CÂU TRẢ LỜI đang cần xem; KHÔNG BAO GIỜ đụng SBD / mã đề (không gọi sua_dinh_danh – hai trường đó giáo viên chốt riêng).
   - Câu cần xem vì vị trí (`vi_tri`) KHÔNG được xác nhận nhanh (service.xu_ly_cau cũng cấm) -> bỏ ra, để giáo viên chọn tay.
   - Client phải gửi ĐÚNG danh sách câu nó đã hiển thị trong hộp xác nhận: lệch với CSDL (ai đó vừa duyệt, phiếu đổi) -> 409, không xác nhận gì.
   - Mỗi câu đi qua ĐÚNG service.xu_ly_cau(..., 'confirm', ...) như nút xác nhận từng câu -> sheet_answers, đánh giá lại phiếu, điểm tạm /
     chính thức nhất quán với đường cũ. Cả lô một giao dịch (main.get_conn): lỗi ở câu nào thì không câu nào được ghi.
   - Một dòng admin_audit_log 'xac_nhan_hang_loat' (đối tượng = kỳ thi; chi tiết: sheet_id, số câu, câu + đáp án máy đọc). Không dữ liệu cá nhân.
   - KHÔNG có hoàn tác: hệ thống hiện tại không cho mở lại câu đã chốt (xu_ly_cau chỉ nhận câu đang cần xem), và mở lại sẽ phải đổi luồng tính
     điểm (lệnh AF cấm). Giao diện nói rõ điều này trong hộp xác nhận.
2. nhom_hang_doi: thông tin để LỌC / NHÓM hàng đợi theo lý do (chỉ đọc, không đổi trạng thái nào).
"""
from typing import Literal

from pydantic import BaseModel, Field

from . import nhat_ky, service

KHONG_XAC_NHAN_NHANH = {"vi_tri"}          # lý do câu bắt buộc chọn tay (giống service.xu_ly_cau)


class XacNhanHangLoat(BaseModel):
    question_nos: list[int] = Field(min_length=1, max_length=40,
                                    description="ĐÚNG các câu đã hiển thị trong hộp xác nhận (mọi câu cần xem trừ câu `vi_tri`); lệch -> 409")
    confirm: Literal[True] = Field(description="Phải là true (giáo viên đã bấm nút trong hộp xác nhận)")


class KetQuaHangLoat(BaseModel):
    sheet_id: int
    da_xac_nhan: list[int]
    con_chon_tay: list[int] = Field(description="Câu cần xem vì vị trí – vẫn chờ giáo viên chọn tay")
    status: str
    official: float | None
    provisional: float | None


class NhomPhieu(BaseModel):
    sheet_id: int
    original_filename: str | None
    detected_sbd: str | None
    so_cau: int
    ly_do_cau: dict[str, int] = Field(description="lý do -> số câu đang cần xem có lý do đó")
    co_vi_tri: bool
    sbd_can_xem: bool
    ma_de_can_xem: bool
    chua_ghep: bool = Field(description="Chưa ghép được thí sinh / chưa xác định mã đề")
    trung_sbd: bool
    provisional: float | None


def cau_hang_loat(conn, sheet_id: int) -> tuple[list[dict], list[int]]:
    """(câu được xác nhận nhanh [{question_no, omr, reasons}], câu phải chọn tay) – đọc CSDL, không khoá."""
    rows = conn.execute("SELECT question_no, omr_selected_options, review_reasons FROM sheet_answers "
                        "WHERE sheet_id = %s AND needs_review ORDER BY question_no", (sheet_id,)).fetchall()
    duoc = [{"question_no": r["question_no"], "omr": r["omr_selected_options"] or "", "reasons": list(r["review_reasons"] or [])}
            for r in rows if not (set(r["review_reasons"] or []) & KHONG_XAC_NHAN_NHANH)]
    tay = [r["question_no"] for r in rows if set(r["review_reasons"] or []) & KHONG_XAC_NHAN_NHANH]
    return duoc, tay


def xac_nhan_hang_loat(conn, sheet_id: int, question_nos: list[int], nd) -> dict:
    sh = conn.execute("SELECT sheet_id, status, exam_id FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise service.KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] != "needs_review":
        raise service.XungDot(f"Phiếu {sheet_id} đang ở trạng thái '{sh['status']}', không có câu nào chờ xem.")
    duoc, tay = cau_hang_loat(conn, sheet_id)
    if not duoc:
        raise service.XungDot("Phiếu không còn câu trả lời nào xác nhận nhanh được (chỉ còn SBD / mã đề hoặc câu phải chọn tay).")
    gui, that = sorted(set(question_nos)), [c["question_no"] for c in duoc]
    if len(gui) != len(question_nos) or gui != that:
        raise service.XungDot(f"Danh sách câu đã thay đổi (máy chủ: {that}, màn hình: {sorted(question_nos)}) – tải lại phiếu rồi xem lại hộp xác nhận.")
    for c in duoc:                                                             # ĐÚNG đường xác nhận từng câu
        service.xu_ly_cau(conn, sheet_id, c["question_no"], "confirm", None, nd.user_id)
    nhat_ky.ghi(conn, nd, "xac_nhan_hang_loat", sh["exam_id"],
                {"sheet_id": sheet_id, "so_cau": len(duoc), "cau": [{"cau": c["question_no"], "may_doc": c["omr"] or "bỏ trống",
                                                                      "ly_do": c["reasons"]} for c in duoc]})
    v = service.xem_phieu(conn, sheet_id)
    sc = v["score"] or {}
    return {"sheet_id": sheet_id, "da_xac_nhan": that, "con_chon_tay": tay, "status": v["status"], "official": sc.get("official"),
            "provisional": sc.get("provisional")}


def nhom_hang_doi(conn, exam_id: int) -> list[dict]:
    """Mỗi phiếu cần xem: lý do câu (đếm), SBD / mã đề cần xem, trùng SBD. Dùng service.xem_phieu (cùng logic màn duyệt) – chỉ đọc."""
    out = []
    for p in service.ds_phieu_ky_thi(conn, exam_id, "needs_review"):
        v = service.xem_phieu(conn, p["sheet_id"])
        cau = [q for q in v["questions"] if q["needs_review"]]
        dem: dict[str, int] = {}
        for q in cau:
            for r in q["reasons"]:
                dem[r] = dem.get(r, 0) + 1
        sbd, ma, rv = v.get("sbd") or {}, v.get("exam_code") or {}, v.get("review") or {}
        out.append({"sheet_id": p["sheet_id"], "original_filename": p["original_filename"], "detected_sbd": p["detected_sbd"], "so_cau": len(cau),
                    "ly_do_cau": dem, "co_vi_tri": dem.get("vi_tri", 0) > 0, "sbd_can_xem": bool(sbd.get("can_xem")),
                    "ma_de_can_xem": bool(ma.get("can_xem")), "chua_ghep": (not v.get("student")) or not ma.get("matched_code"),
                    "trung_sbd": "duplicate_sbd" in (rv.get("reasons") or []), "provisional": (v["score"] or {}).get("provisional")})
    return out
