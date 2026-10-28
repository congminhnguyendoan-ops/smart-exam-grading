"""
bang_diem.py - Bảng điểm của kỳ thi + xuất Excel (demo 13/10/2026).

Quy tắc cốt lõi (như service.danh_gia_phieu): cột `score` (điểm chính thức) CHỈ lấy từ bảng `results` (status <> 'void').
Phiếu chưa duyệt xong (needs_review) chỉ có điểm tạm -> cột riêng `provisional_score`, KHÔNG BAO GIỜ vào `score`.

Mỗi thí sinh một dòng (danh sách dự thi `exam_students`; kỳ thi không có danh sách thì lấy các sinh viên đã ghép được phiếu).
Phiếu của thí sinh được chọn: phiếu có điểm chính thức > phiếu cần xem mới nhất. Phiếu KHÔNG ghép được thí sinh (ảnh bị từ chối
không đọc được SBD; SBD không có trong danh sách) không thuộc dòng nào -> trả riêng ở `unmatched` và tính vào tổng "bị từ chối".
"""
import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import phieu_trung
from .service import KhongTimThay

NHAN = {"official": "Chính thức", "pending": "Chưa duyệt xong – điểm tạm", "rejected": "Bị từ chối", "no_sheet": "Chưa có phiếu"}
GHI_CHU_TAM = "Điểm tạm chưa phải điểm chính thức: chỉ tính các câu máy đọc chắc chắn, phiếu còn mục giáo viên chưa duyệt."


def _f(x):
    return None if x is None else float(x)


def bang_diem(conn, exam_id: int) -> dict:
    ex = conn.execute("SELECT e.exam_id, e.exam_title, e.max_score, e.num_questions, sj.subject_code, sj.subject_name, e.class_id, c.class_code, c.class_name "
                      "FROM exams e JOIN subjects sj ON sj.subject_id = e.subject_id LEFT JOIN classes c ON c.class_id = e.class_id "
                      "WHERE e.exam_id = %s", (exam_id,)).fetchone()
    if not ex:
        raise KhongTimThay(f"Không có kỳ thi {exam_id}.")
    # Mọi phiếu CÓ ghép thí sinh (graded / needs_review), kèm kết quả chính thức nếu có.
    phieu = conn.execute(
        "SELECT a.sheet_id, a.status::text AS status, a.matched_student_id AS sid, a.raw_score, a.num_correct AS dung_tam, "
        "a.detected_exam_code, c.code AS ma_de, r.score AS diem, r.num_correct AS dung, "
        "(SELECT count(*) FROM sheet_answers q WHERE q.sheet_id = a.sheet_id AND q.needs_review) AS cho "
        "FROM answer_sheets a LEFT JOIN results r ON r.sheet_id = a.sheet_id AND r.status <> 'void' "
        "LEFT JOIN exam_codes c ON c.exam_code_id = a.exam_code_id "
        "WHERE a.exam_id = %s AND a.matched_student_id IS NOT NULL AND a.status IN ('graded', 'needs_review') "
        "ORDER BY a.sheet_id", (exam_id,)).fetchall()
    tot_nhat: dict[int, dict] = {}
    so_phieu: dict[int, int] = {}
    for p in phieu:                                         # chính thức thắng; cùng loại thì phiếu mới hơn (sheet_id lớn) thắng
        so_phieu[p["sid"]] = so_phieu.get(p["sid"], 0) + 1
        cu = tot_nhat.get(p["sid"])
        if cu is None or (p["diem"] is not None, p["sheet_id"]) > (cu["diem"] is not None, cu["sheet_id"]):
            tot_nhat[p["sid"]] = p
    sv = conn.execute(
        "SELECT s.student_id, s.student_code, s.full_name, es.is_absent FROM students s JOIN exam_students es USING (student_id) "
        "WHERE es.exam_id = %(e)s UNION "
        "SELECT s.student_id, s.student_code, s.full_name, FALSE FROM students s WHERE s.student_id = ANY(%(ids)s::bigint[]) "
        "ORDER BY student_code", {"e": exam_id, "ids": list(tot_nhat)}).fetchall()
    cho_trung = phieu_trung.dem_cho(conn, exam_id)
    dong = []
    for i, s in enumerate(sv, 1):
        p = tot_nhat.get(s["student_id"])
        d = {"stt": i, "student_id": s["student_id"], "sbd": s["student_code"], "full_name": s["full_name"], "exam_code": None,
             "num_correct": None, "score": None, "provisional_score": None, "provisional_correct": None, "pending_questions": 0,
             "sheet_id": None, "sheets": so_phieu.get(s["student_id"], 0),
             "duplicate_pending": len(cho_trung.get(s["student_id"], [])), "duplicate_sheet_ids": cho_trung.get(s["student_id"], [])}
        if p is None:
            d["status"] = "no_sheet"
        else:
            d.update(sheet_id=p["sheet_id"], exam_code=p["ma_de"] or p["detected_exam_code"])
            if p["diem"] is not None:                       # có dòng results = chính thức
                d.update(status="official", score=_f(p["diem"]), num_correct=p["dung"])
            else:
                d.update(status="pending", provisional_score=_f(p["raw_score"]), provisional_correct=p["dung_tam"],
                         pending_questions=p["cho"])
        d["status_label"] = NHAN[d["status"]]
        dong.append(d)
    roi = conn.execute(
        "SELECT a.sheet_id, a.status::text AS status, a.original_filename, a.detected_sbd, a.reject_code, a.error_message AS reject_message "
        "FROM answer_sheets a WHERE a.exam_id = %s AND a.matched_student_id IS NULL AND a.status IN ('rejected', 'needs_review') "
        "ORDER BY a.sheet_id", (exam_id,)).fetchall()
    dem = {k: sum(d["status"] == k for d in dong) for k in ("official", "pending", "no_sheet")}
    dem["rejected"] = sum(p["status"] == "rejected" for p in roi)
    dem["unmatched_review"] = sum(p["status"] == "needs_review" for p in roi)
    dem["students_duplicate_pending"] = sum(d["duplicate_pending"] > 0 for d in dong)
    return {"exam_id": exam_id, "exam_title": ex["exam_title"], "subject_code": ex["subject_code"], "subject_name": ex["subject_name"],
            "class_id": ex["class_id"], "class_code": ex["class_code"], "class_name": ex["class_name"], "max_score": _f(ex["max_score"]), "num_questions": ex["num_questions"],
            "exported_on": date.today().isoformat(), "counts": {**dem, "students": len(dong)}, "rows": dong, "unmatched": roi}


def chi_tiet_chinh_thuc(conn, exam_id: int) -> list[dict]:
    """Mỗi (phiếu chính thức, câu): bài làm, đáp án đúng, đúng/sai."""
    return conn.execute(
        "SELECT s.student_code AS sbd, s.full_name, c.code AS ma_de, r.sheet_id, r.score, q.question_no, q.selected_options AS chon, "
        "k.correct_option AS dap_an, q.is_correct "
        "FROM results r JOIN students s USING (student_id) JOIN exam_codes c ON c.exam_code_id = r.exam_code_id "
        "JOIN sheet_answers q ON q.sheet_id = r.sheet_id "
        "JOIN answer_keys k ON k.exam_code_id = r.exam_code_id AND k.question_no = q.question_no "
        "WHERE r.exam_id = %s AND r.status <> 'void' ORDER BY s.student_code, r.sheet_id, q.question_no", (exam_id,)).fetchall()


def ten_file(tieu_de: str, ngay: str) -> str:
    """Tên file có tên kỳ thi: chỉ giữ chữ / số / dấu cách (kể cả tiếng Việt) -> gạch dưới."""
    sach = "".join(ch if (ch.isalnum() or ch in " -") else " " for ch in tieu_de)
    return "_".join(sach.split())[:80] + f"_{ngay}.xlsx"


def xuat_excel(conn, exam_id: int) -> tuple[bytes, str]:
    b = bang_diem(conn, exam_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "Bảng điểm"
    dam = Font(bold=True)
    ws["A1"] = f"BẢNG ĐIỂM – {b['exam_title']}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Ngày xuất: {b['exported_on']} · Điểm tối đa: {b['max_score']:g} · {b['num_questions']} câu"
    ws["A3"] = "Ghi chú: " + GHI_CHU_TAM + " Cột 'Điểm' chỉ có giá trị khi trạng thái là Chính thức."
    ws["A3"].font = Font(italic=True, color="9C5700")
    ws["A4"] = f"Môn: {b['subject_code']} – {b['subject_name']}"          # hàng 4 đang trống: KHÔNG chèn dòng (hàng 5 = tiêu đề cột, dữ liệu từ hàng 6)
    ws["F4"] = "Lớp: " + (f"{b['class_code']} – {b['class_name']}" if b["class_code"] else "(không gắn lớp)")
    ws["A4"].font = ws["F4"].font = Font(bold=True)
    n_trung = b["counts"]["students_duplicate_pending"]
    if n_trung:                                          # cảnh báo nổi bật ở đầu bảng (không chèn dòng: dữ liệu vẫn từ hàng 6)
        ws["A2"] = ws["A2"].value + f" · CẢNH BÁO: {n_trung} thí sinh còn phiếu TRÙNG SBD đang chờ duyệt – xem cột 'Cảnh báo'"
        ws["A2"].font = Font(bold=True, color="C00000")
    dau = ["STT", "SBD", "Họ tên", "Mã đề", "Số câu đúng", "Điểm", "Điểm tạm (chưa chính thức)", "Trạng thái", "Mã phiếu", "Cảnh báo"]
    for j, t in enumerate(dau, 1):
        c = ws.cell(row=5, column=j, value=t)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    mau = {"official": "E2EFDA", "pending": "FFF2CC", "no_sheet": "EDEDED"}
    for i, d in enumerate(b["rows"], 6):
        ws.append([d["stt"], d["sbd"], d["full_name"], d["exam_code"], d["num_correct"], d["score"], d["provisional_score"],
                   d["status_label"], d["sheet_id"],
                   (f"Còn {d['duplicate_pending']} phiếu trùng SBD chờ duyệt (mã phiếu " + ", ".join(map(str, d["duplicate_sheet_ids"])) + ")")
                   if d["duplicate_pending"] else None])
        if d["duplicate_pending"]:
            ws.cell(row=i, column=10).font = Font(bold=True, color="C00000")
        ws.cell(row=i, column=2).number_format = "@"        # SBD là chuỗi (giữ số 0 đầu)
        ws.cell(row=i, column=8).fill = PatternFill("solid", fgColor=mau[d["status"]])
        for j in (6, 7):
            ws.cell(row=i, column=j).number_format = "0.00"
    cuoi = 6 + len(b["rows"]) + 1
    ws.cell(row=cuoi, column=1, value="Tổng hợp").font = dam
    k = b["counts"]
    ws.cell(row=cuoi + 1, column=1, value=f"Chính thức: {k['official']} · Chưa duyệt xong: {k['pending']} · "
                                          f"Chưa có phiếu: {k['no_sheet']} · Phiếu bị từ chối (không ghép được thí sinh): {k['rejected']}")
    ws.cell(row=cuoi + 2, column=1, value=f"Thí sinh có phiếu TRÙNG SBD đang chờ duyệt: {k['students_duplicate_pending']}")
    if k["students_duplicate_pending"]:
        ws.cell(row=cuoi + 2, column=1).font = Font(bold=True, color="C00000")
    for j, w in enumerate([6, 12, 30, 8, 12, 9, 16, 28, 11, 46], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[5].height = 32
    ws.freeze_panes = "A6"

    ct = wb.create_sheet("Chi tiết")
    ct.append(["SBD", "Họ tên", "Mã đề", "Mã phiếu", "Câu", "Bài làm", "Đáp án đúng", "Kết quả"])
    for c in ct[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
    xanh, do = PatternFill("solid", fgColor="E2EFDA"), PatternFill("solid", fgColor="F8CBAD")
    for r in chi_tiet_chinh_thuc(conn, exam_id):
        ct.append([r["sbd"], r["full_name"], r["ma_de"], r["sheet_id"], r["question_no"], r["chon"] or "(trống)", r["dap_an"],
                   "Đúng" if r["is_correct"] else "Sai"])
        n = ct.max_row
        ct.cell(row=n, column=1).number_format = "@"
        ct.cell(row=n, column=8).fill = xanh if r["is_correct"] else do
    for j, w in enumerate([12, 30, 8, 10, 6, 10, 12, 9], 1):
        ct.column_dimensions[get_column_letter(j)].width = w
    ct.freeze_panes = "A2"
    ct.auto_filter.ref = ct.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), ten_file(b["exam_title"], b["exported_on"])
