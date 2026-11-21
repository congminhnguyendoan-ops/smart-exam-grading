from typing import Literal

from pydantic import BaseModel, Field

from . import nhat_ky, service

LY_DO_HANG_LOAT = frozenset({"nhieu_o", "to_nhat"})


def hop_le_hang_loat(reasons) -> bool:
    r = set(reasons or [])
    return "to_nhat" in r and r <= LY_DO_HANG_LOAT


class XacNhanHangLoat(BaseModel):
    question_nos: list[int] = Field(min_length=1, max_length=40,
                                    description="ĐÚNG các câu đã hiển thị trong hộp xác nhận = mọi câu cần xem có lý do thuộc `nhieu_o` / `to_nhat` và có `to_nhat` (câu nhiều ô thuần đã tự chấm sai, không còn ở đây). "
                                                "Có câu loại khác (mờ, vết, lưng chừng, vị trí) -> 422 cả lô; danh sách cũ / lệch -> 409")
    confirm: Literal[True] = Field(description="Phải là true (giáo viên đã bấm nút trong hộp xác nhận)")


class KetQuaHangLoat(BaseModel):
    sheet_id: int
    da_xac_nhan: list[int]
    con_chon_tay: list[int] = Field(description="Câu cần xem KHÔNG thuộc loại hàng loạt (mờ, vết, lưng chừng, vị trí) – vẫn chờ giáo viên chọn từng câu")
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
    rows = conn.execute("SELECT question_no, omr_selected_options, review_reasons FROM sheet_answers "
                        "WHERE sheet_id = %s AND needs_review ORDER BY question_no", (sheet_id,)).fetchall()
    duoc = [{"question_no": r["question_no"], "omr": r["omr_selected_options"] or "", "reasons": list(r["review_reasons"] or [])}
            for r in rows if hop_le_hang_loat(r["review_reasons"])]
    tay = [r["question_no"] for r in rows if not hop_le_hang_loat(r["review_reasons"])]
    return duoc, tay


def xac_nhan_hang_loat(conn, sheet_id: int, question_nos: list[int], nd) -> dict:
    sh = conn.execute("SELECT sheet_id, status, exam_id FROM answer_sheets WHERE sheet_id = %s FOR UPDATE", (sheet_id,)).fetchone()
    if not sh:
        raise service.KhongTimThay(f"Không có phiếu {sheet_id}.")
    if sh["status"] != "needs_review":
        raise service.XungDot(f"Phiếu {sheet_id} đang ở trạng thái '{sh['status']}', không có câu nào chờ xem.")
    duoc, tay = cau_hang_loat(conn, sheet_id)
    bi_loai = sorted({n for n in question_nos if n in tay})
    if bi_loai:
        raise service.DuLieuSai(f"Từ chối cả lô: {len(bi_loai)} câu không xác nhận hàng loạt được (câu {', '.join(map(str, bi_loai))}) – chỉ nhận câu "
                                "'tô nhạt cả tờ'. Câu mờ / vết / lưng chừng / vị trí phải chọn từng câu bằng mắt. Chưa ghi câu nào.")
    if not duoc:
        raise service.XungDot("Phiếu không còn câu 'tô nhạt cả tờ' nào chờ xem – các câu còn lại phải chọn từng câu.")
    gui, that = sorted(set(question_nos)), [c["question_no"] for c in duoc]
    if len(gui) != len(question_nos) or gui != that:
        raise service.XungDot(f"Danh sách câu đã thay đổi (máy chủ: {that}, màn hình: {sorted(question_nos)}) – tải lại phiếu rồi xem lại hộp xác nhận.")
    for c in duoc:
        service.xu_ly_cau(conn, sheet_id, c["question_no"], "confirm", None, nd.user_id)
    nhat_ky.ghi(conn, nd, "xac_nhan_hang_loat", sh["exam_id"],
                {"sheet_id": sheet_id, "so_cau": len(duoc), "cau": [{"cau": c["question_no"], "may_doc": c["omr"] or "bỏ trống",
                                                                      "ly_do": c["reasons"]} for c in duoc]})
    v = service.xem_phieu(conn, sheet_id)
    sc = v["score"] or {}
    return {"sheet_id": sheet_id, "da_xac_nhan": that, "con_chon_tay": tay, "status": v["status"], "official": sc.get("official"),
            "provisional": sc.get("provisional")}


def nhom_hang_doi(conn, exam_id: int) -> list[dict]:
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
