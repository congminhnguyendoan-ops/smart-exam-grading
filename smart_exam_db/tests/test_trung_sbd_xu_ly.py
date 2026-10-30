"""Lệnh F2 (28/10/2026): xử lý phiếu TRÙNG SBD – cảnh báo ở Bảng điểm / Excel, "Bỏ phiếu chụp lại", "Dùng phiếu này thay phiếu cũ",
chốt đồng thời (409), phân quyền. CSDL thật trong giao dịch ROLLBACK (conftest.py). Bất biến kiểm ở mọi test: không bao giờ có 2 điểm chính thức / thí sinh."""
import io

import pytest
from openpyxl import load_workbook

from test_backend_api import can_anh, giai_quyet_het, tai, tao_de, them_sv
from test_dang_nhap import bang_moi, client_on, ky_thi, the_gioi, tai_trang  # noqa: F401  (fixture)
from test_trung_sbd import SBD_0002, hai_phieu  # noqa: F401  (hai_phieu: fixture)


def so_diem_chinh_thuc(conn, eid):
    return conn.execute("SELECT count(*) AS n FROM results r JOIN students s USING (student_id) WHERE r.exam_id = %s AND s.student_code = %s "
                        "AND r.status <> 'void'", (eid, SBD_0002)).fetchone()["n"]


def giu_b(client, b):
    vb = giai_quyet_het(client, b)
    assert vb["status"] == "needs_review" and "duplicate_sbd" in vb["review"]["reasons"]
    assert vb["review"]["details"]["duplicate_with_sheet_id"]
    return vb


# ------------------------------------------------------------------------------------------------ a) hiển thị cảnh báo
def test_bang_diem_va_excel_canh_bao_phieu_trung_cho(client, hai_phieu):
    eid, a, b, va = hai_phieu
    giu_b(client, b)
    bd = client.get(f"/exams/{eid}/results").json()
    d = next(r for r in bd["rows"] if r["sbd"] == SBD_0002)
    assert d["status"] == "official" and d["sheet_id"] == a and d["score"] == float(va["score"]["official"])   # điểm vẫn của phiếu cũ
    assert d["duplicate_pending"] == 1 and d["duplicate_sheet_ids"] == [b]
    assert bd["counts"]["students_duplicate_pending"] == 1
    wb = load_workbook(io.BytesIO(client.get(f"/exams/{eid}/export.xlsx").content))
    ws = wb["Bảng điểm"]
    assert "CẢNH BÁO" in ws["A2"].value and "1 thí sinh" in ws["A2"].value
    hang = next(r for r in ws.iter_rows(min_row=6) if r[1].value == SBD_0002)
    assert ws.cell(row=5, column=10).value == "Cảnh báo" and f"{b}" in str(hang[9].value) and "trùng SBD" in hang[9].value
    chu = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
    assert "Thí sinh có phiếu TRÙNG SBD đang chờ duyệt: 1" in chu


def test_khong_canh_bao_khi_phieu_trung_da_xu_ly(client, hai_phieu):
    eid, a, b, _ = hai_phieu
    giu_b(client, b)
    assert client.get(f"/exams/{eid}/results").json()["counts"]["students_duplicate_pending"] == 1
    assert client.post(f"/sheets/{b}/duplicate/discard", json={}).status_code == 200
    bd = client.get(f"/exams/{eid}/results").json()
    assert bd["counts"]["students_duplicate_pending"] == 0
    assert all(r["duplicate_pending"] == 0 for r in bd["rows"])
    ws = load_workbook(io.BytesIO(client.get(f"/exams/{eid}/export.xlsx").content))["Bảng điểm"]
    assert "CẢNH BÁO" not in (ws["A2"].value or "")


# ------------------------------------------------------------------------------------------------ b) bỏ phiếu mới
def test_bo_phieu_chup_lai_giu_phieu_cu(client, conn_thu, hai_phieu):
    eid, a, b, va = hai_phieu
    giu_b(client, b)
    r = client.post(f"/sheets/{b}/duplicate/discard", json={})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["hanh_dong"] == "bo_phieu_moi" and j["phieu_cu"] == a and j["phieu"]["status"] == "rejected"
    assert j["phieu"]["reject_code"] == "chup_lai_bi_bo" and "giữ phiếu cũ" in j["phieu"]["reject_message"]
    assert client.get(f"/sheets/{a}").json()["score"]["official"] == va["score"]["official"]                # phiếu cũ KHÔNG đổi
    assert so_diem_chinh_thuc(conn_thu, eid) == 1
    rq = conn_thu.execute("SELECT status::text AS s, resolution_note FROM review_queue WHERE sheet_id = %s ORDER BY review_id DESC", (b,)).fetchone()
    assert rq["s"] == "rejected" and f"#{b}" in rq["resolution_note"] and f"#{a}" in rq["resolution_note"]
    bd = client.get(f"/exams/{eid}/results").json()
    assert bd["counts"]["students_duplicate_pending"] == 0
    assert client.post(f"/sheets/{b}/duplicate/discard", json={}).status_code == 409                           # làm lại lần hai: không còn bị giữ


# ------------------------------------------------------------------------------------------------ c) thay phiếu cũ
def test_thay_phieu_cu_mot_giao_dich_ghi_nhat_ky(client, conn_thu, hai_phieu):
    eid, a, b, va = hai_phieu
    giu_b(client, b)
    assert client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a}).status_code == 422          # thiếu confirm
    assert client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a, "confirm": False}).status_code == 422
    assert so_diem_chinh_thuc(conn_thu, eid) == 1 and client.get(f"/sheets/{a}").json()["score"]["official"] is not None   # chưa xác nhận: chưa đổi gì
    r = client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a, "confirm": True})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["hanh_dong"] == "thay_phieu_cu" and j["phieu_cu"] == a and j["diem_cu_da_rut"] == float(va["score"]["official"])
    assert j["phieu"]["status"] == "graded" and j["phieu"]["score"]["official"] is not None                    # phiếu mới được chốt qua đường quyết định cũ
    assert so_diem_chinh_thuc(conn_thu, eid) == 1                                                              # vẫn đúng MỘT điểm chính thức
    cu = conn_thu.execute("SELECT status::text AS s FROM results WHERE sheet_id = %s", (a,)).fetchone()
    assert cu["s"] == "void"
    moi = conn_thu.execute("SELECT status::text AS s FROM results WHERE sheet_id = %s", (b,)).fetchone()
    assert moi["s"] == "confirmed"
    pa = client.get(f"/sheets/{a}").json()
    assert pa["status"] == "rejected" and pa["reject_code"] == "bi_thay_the" and f"#{b}" in pa["reject_message"]
    nk = conn_thu.execute("SELECT l.action, l.old_status::text AS o, l.new_status::text AS n, l.changed_by, l.reason, l.changed_at "
                          "FROM score_audit_logs l JOIN results r USING (result_id) WHERE r.sheet_id = %s ORDER BY audit_id DESC", (a,)).fetchall()
    ghi = next(x for x in nk if x["n"] == "void")                                                              # ai / lúc nào / phiếu nào thay phiếu nào
    assert ghi["o"] in ("auto", "confirmed") and ghi["changed_by"] is not None and ghi["changed_at"] is not None
    assert f"#{a}" in ghi["reason"] and f"#{b}" in ghi["reason"] and SBD_0002 in ghi["reason"]
    ghi_b = conn_thu.execute("SELECT reason FROM score_audit_logs l JOIN results r USING (result_id) WHERE r.sheet_id = %s", (b,)).fetchone()
    assert f"#{a}" in ghi_b["reason"]
    bd = client.get(f"/exams/{eid}/results").json()
    d = next(x for x in bd["rows"] if x["sbd"] == SBD_0002)
    assert d["status"] == "official" and d["sheet_id"] == b and d["duplicate_pending"] == 0 and bd["counts"]["students_duplicate_pending"] == 0


def test_thay_phieu_khong_dung_phieu_cu_bi_tu_choi(client, conn_thu, hai_phieu):
    eid, a, b, _ = hai_phieu
    giu_b(client, b)
    assert client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": b, "confirm": True}).status_code == 422     # phiếu cũ ≠ phiếu mới
    r = client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a + 100000, "confirm": True})      # phiếu cũ người dùng thấy đã đổi
    assert r.status_code == 409                                  # phiếu cũ người dùng thấy không còn là phiếu đang giữ điểm
    r2 = client.post(f"/sheets/{a}/duplicate/replace", json={"old_sheet_id": b, "confirm": True})
    assert r2.status_code == 409                                 # sai vai: A không bị giữ vì trùng
    assert so_diem_chinh_thuc(conn_thu, eid) == 1 and conn_thu.execute("SELECT status::text AS s FROM results WHERE sheet_id = %s", (a,)).fetchone()["s"] != "void"


# ------------------------------------------------------------------------------------------------ d) chốt đồng thời
def test_thay_phieu_lan_hai_khi_phieu_cu_da_doi_la_409(client, conn_thu, hai_phieu):
    """Hai giáo viên cùng bấm: người thứ hai gửi old_sheet_id = phiếu A nhưng A đã bị thay -> 409, không rút thêm điểm nào."""
    eid, a, b, _ = hai_phieu
    giu_b(client, b)
    assert client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a, "confirm": True}).status_code == 200
    r = client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a, "confirm": True})
    assert r.status_code == 409, r.text
    assert so_diem_chinh_thuc(conn_thu, eid) == 1


def test_thua_cuoc_dua_chot_dong_thoi_tra_409_khong_co_hai_diem(client, conn_thu, hai_phieu):
    """Giả lập: SAU khi service đã kiểm "không còn phiếu trùng" và TRƯỚC khi ghi điểm (đúng lúc gọi fn_grade_sheet), một giáo viên khác chốt xong
    một phiếu C cho cùng thí sinh. Chỉ mục duy nhất uq_results_exam_student chặn dòng thứ hai -> API trả 409 (không có hai điểm chính thức)."""
    from backend.main import app, get_conn
    eid, a, b, _ = hai_phieu
    giu_b(client, b)
    sid = conn_thu.execute("SELECT matched_student_id FROM answer_sheets WHERE sheet_id = %s", (b,)).fetchone()["matched_student_id"]
    c = conn_thu.execute("INSERT INTO answer_sheets (exam_id, image_path, status, matched_student_id) VALUES (%s, 'x.jpg', 'graded', %s) RETURNING sheet_id",
                         (eid, sid)).fetchone()["sheet_id"]

    class DoiThu:
        """Bọc kết nối: ngay trước SELECT fn_grade_sheet (bước cuối trước khi ghi điểm) chèn kết quả của "giáo viên kia"."""
        def __init__(self, goc):
            self._goc, self._xong = goc, False

        def __getattr__(self, ten):
            return getattr(self._goc, ten)

        def execute(self, q, *a_, **k_):
            if not self._xong and isinstance(q, str) and q.lstrip().startswith("SELECT fn_grade_sheet"):
                self._xong = True
                self._goc.execute("INSERT INTO results (exam_id, student_id, sheet_id, num_correct, score, status) VALUES (%s, %s, %s, 0, 0, 'confirmed')",
                                  (eid, sid, c))
            return self._goc.execute(q, *a_, **k_)

    def _conn():
        yield DoiThu(conn_thu)
    cu = app.dependency_overrides[get_conn]
    app.dependency_overrides[get_conn] = _conn
    try:
        r = client.post(f"/sheets/{b}/duplicate/replace", json={"old_sheet_id": a, "confirm": True})
    finally:
        app.dependency_overrides[get_conn] = cu
    assert r.status_code == 409 and "ràng buộc" in r.json()["detail"], r.text


# ------------------------------------------------------------------------------------------------ e) phân quyền
def test_giao_vien_lop_khac_khong_xu_ly_duoc_phieu_trung(the_gioi):
    g = the_gioi
    SA = g.SA
    for ch, body in (("discard", {}), ("replace", {"old_sheet_id": SA, "confirm": True})):
        assert g.c.post(f"/sheets/{SA}/duplicate/{ch}", headers=g.hB, json=body).status_code == 404        # giáo viên lớp B: như không tồn tại
        assert g.c.post(f"/sheets/{SA}/duplicate/{ch}", headers=g.hSv, json=body).status_code == 403       # sinh viên
        assert g.c.post(f"/sheets/{SA}/duplicate/{ch}", json=body).status_code == 401                      # chưa đăng nhập
    # chủ kỳ thi vào được tới nghiệp vụ (phiếu này không bị giữ vì trùng -> 409, không phải 404)
    assert g.c.post(f"/sheets/{SA}/duplicate/discard", headers=g.hA, json={}).status_code == 409
    sb = tai_trang(g.c, g.hB, g.EB).json()["sheet_id"]
    # giáo viên A dùng phiếu cũ của kỳ thi người khác làm old_sheet_id -> 404 (không dò được phiếu của lớp khác)
    assert g.c.post(f"/sheets/{SA}/duplicate/replace", headers=g.hA, json={"old_sheet_id": sb, "confirm": True}).status_code == 404
