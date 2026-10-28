"""Lệnh D – việc phụ: HAI phiếu cùng SBD trong CÙNG kỳ thi – CSDL thật trong giao dịch ROLLBACK. (Lệnh F2 28/10: Bảng điểm / Excel đã có cảnh báo, màn duyệt có
hai lựa chọn xử lý – xem test_trung_sbd_xu_ly.py; các test dưới đây vẫn là bất biến "đúng MỘT điểm chính thức".)

Kết luận (docs/so_sanh_ocr_cnn.md mục "Việc phụ"): không bao giờ có 2 điểm chính thức cho một thí sinh (service gắn duplicate_sbd + chỉ mục
uq_results_exam_student); phiếu sau kẹt ở "cần xem"; Bảng điểm / Excel lấy phiếu chính thức."""
import io

import psycopg
import pytest
from openpyxl import load_workbook

from test_backend_api import can_anh, giai_quyet_het, tai, tao_de, them_sv

SBD_0002 = "795125"


@pytest.fixture
def hai_phieu(client, conn_thu):
    """Kỳ thi + 2 ảnh KHÁC NHAU (SHA khác) của cùng phiếu 0002 (cùng SBD): phiếu A chốt chính thức trước, phiếu B tải sau."""
    can_anh("0002_C2", "0002_C3")
    them_sv(conn_thu, SBD_0002)
    eid = tao_de(client)
    a = tai(client, eid, "0002_C2").json()["sheet_id"]
    va = giai_quyet_het(client, a)
    if va["status"] != "graded":
        va = client.put(f"/sheets/{a}/identity", json={"sbd": SBD_0002}).json()
    assert va["status"] == "graded" and va["score"]["official"] is not None
    b = tai(client, eid, "0002_C3").json()["sheet_id"]
    assert b != a
    return eid, a, b, va


def test_phieu_sau_bi_giu_o_can_xem_khong_co_diem_chinh_thuc_thu_hai(client, conn_thu, hai_phieu):
    eid, a, b, va = hai_phieu
    vb = giai_quyet_het(client, b)                                         # giáo viên duyệt hết câu của phiếu B
    assert vb["status"] == "needs_review" and "duplicate_sbd" in vb["review"]["reasons"]
    assert vb["score"]["official"] is None and vb["student"]["student_code"] == SBD_0002      # B vẫn ghép đúng thí sinh
    vb2 = client.put(f"/sheets/{b}/identity", json={"sbd": SBD_0002}).json()                 # xác nhận lại đúng SBD: vẫn kẹt
    assert vb2["status"] == "needs_review" and "duplicate_sbd" in vb2["review"]["reasons"]
    n = conn_thu.execute("SELECT count(*) AS n FROM results r JOIN students s USING (student_id) WHERE r.exam_id = %s AND s.student_code = %s "
                         "AND r.status <> 'void'", (eid, SBD_0002)).fetchone()["n"]
    assert n == 1                                                          # đúng MỘT điểm chính thức
    assert client.get(f"/sheets/{a}").json()["score"]["official"] == va["score"]["official"]   # phiếu A không đổi


def test_csdl_chan_diem_chinh_thuc_thu_hai(conn_thu, hai_phieu):
    """Kể cả khi bỏ qua service (vd hai giáo viên chốt cùng lúc): chỉ mục duy nhất uq_results_exam_student chặn dòng results thứ hai."""
    eid, a, b, _ = hai_phieu
    sid = conn_thu.execute("SELECT matched_student_id FROM answer_sheets WHERE sheet_id = %s", (b,)).fetchone()["matched_student_id"]
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn_thu.transaction():
            conn_thu.execute("INSERT INTO results (exam_id, student_id, sheet_id, num_correct, score, status) VALUES (%s, %s, %s, 0, 0, 'confirmed')",
                             (eid, sid, b))


def test_bang_diem_va_excel_lay_phieu_chinh_thuc_va_canh_bao_phieu_trung(client, hai_phieu):
    """Điểm ở Bảng điểm / Excel vẫn là của phiếu chính thức (A); từ lệnh F2 có CẢNH BÁO phiếu trùng chờ duyệt (chi tiết: test_trung_sbd_xu_ly.py)."""
    eid, a, b, va = hai_phieu
    giai_quyet_het(client, b)
    bd = client.get(f"/exams/{eid}/results").json()
    d = next(r for r in bd["rows"] if r["sbd"] == SBD_0002)
    assert d["status"] == "official" and d["sheet_id"] == a and d["score"] == float(va["score"]["official"])
    assert d["sheets"] == 2 and d["duplicate_pending"] == 1 and d["duplicate_sheet_ids"] == [b]
    assert all(p["sheet_id"] != b for p in bd["unmatched"])                # phiếu B vẫn không nằm ở "chưa ghép được"
    wb = load_workbook(io.BytesIO(client.get(f"/exams/{eid}/export.xlsx").content))
    chu = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None).lower()
    assert "trùng sbd" in chu
    from conftest import ROOT
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "duplicate_pending" in js and "/duplicate/replace" in js and "/duplicate/discard" in js     # màn Bảng điểm + màn duyệt có xử lý phiếu trùng
