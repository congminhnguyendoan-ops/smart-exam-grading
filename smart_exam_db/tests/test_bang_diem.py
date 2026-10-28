"""Kiểm thử bảng điểm + xuất Excel (demo 13/10). CSDL thật trong giao dịch ROLLBACK; chỉ ảnh dev 0001–0028 (không đụng 0029–0040)."""
import io
from urllib.parse import unquote

import pytest
from openpyxl import load_workbook

from backend import demo
from test_backend_api import ocr_khop, anh_trang, can_anh, giai_quyet_het, omr_gia, tai, tao_de, them_sv


def dang_ky(conn, eid, *sbd):
    for s in sbd:
        them_sv(conn, s)
        conn.execute("INSERT INTO exam_students (exam_id, student_id) SELECT %s, student_id FROM students WHERE student_code = %s", (eid, s))


def diem_doc_lap(conn, sheet_id, eid) -> float:
    """Điểm tính lại từ bài làm + đáp án (không dùng is_correct / results): câu 'filled' và trùng đáp án, 10/40 điểm mỗi câu."""
    r = conn.execute(
        "SELECT count(*) AS n FROM sheet_answers q JOIN answer_sheets a USING (sheet_id) "
        "JOIN answer_keys k ON k.exam_code_id = a.exam_code_id AND k.question_no = q.question_no "
        "WHERE q.sheet_id = %s AND q.state = 'filled' AND q.selected_options = k.correct_option", (sheet_id,)).fetchone()
    return r["n"] * 10 / 40


def test_bang_diem_du_bon_trang_thai(client, conn_thu):
    """Chính thức / chưa duyệt xong / bị từ chối / chưa có phiếu; phiếu chưa duyệt KHÔNG có điểm trong cột điểm chính thức."""
    can_anh("0002_C2", "0001_C1")
    eid = tao_de(client)
    dang_ky(conn_thu, eid, "795125", "062384", "111111")
    s2 = tai(client, eid, "0002_C2").json()["sheet_id"]           # SBD 795125, cần xem
    tai(client, eid, "0001_C1")                                   # SBD 06238? -> chưa ghép được
    tai(client, eid, "trang", anh_trang())                        # bị từ chối
    b = client.get(f"/exams/{eid}/results").json()
    d = {r["sbd"]: r for r in b["rows"]}
    assert [r["stt"] for r in b["rows"]] == [1, 2, 3] and b["max_score"] == 10
    assert d["795125"]["status"] == "pending" and d["795125"]["score"] is None and d["795125"]["num_correct"] is None
    assert d["795125"]["provisional_score"] is not None and d["795125"]["pending_questions"] > 0 and d["795125"]["sheet_id"] == s2
    assert d["111111"]["status"] == "no_sheet" and d["062384"]["status"] == "no_sheet"       # 0001 chưa chốt SBD nên chưa ghép
    assert b["counts"] == {"official": 0, "pending": 1, "no_sheet": 2, "rejected": 1, "unmatched_review": 1, "students": 3, "students_duplicate_pending": 0}
    kh = {p["status"]: p for p in b["unmatched"]}
    assert set(kh) == {"needs_review", "rejected"} and kh["needs_review"]["detected_sbd"] == "06238?" and kh["rejected"]["reject_code"] == "thieu_marker"
    # giáo viên duyệt hết -> chính thức, điểm = điểm tính độc lập
    giai_quyet_het(client, s2)
    d2 = {r["sbd"]: r for r in client.get(f"/exams/{eid}/results").json()["rows"]}["795125"]
    assert d2["status"] == "official" and d2["provisional_score"] is None and d2["pending_questions"] == 0
    assert d2["score"] == pytest.approx(diem_doc_lap(conn_thu, s2, eid)) and d2["exam_code"] == "102"
    # giáo viên chốt SBD của 0001 -> thí sinh 062384 hiện phiếu chưa duyệt xong
    s1 = next(p["sheet_id"] for p in b["unmatched"] if p["status"] == "needs_review")
    assert client.put(f"/sheets/{s1}/identity", json={"sbd": "062384"}).status_code == 200
    d1 = {r["sbd"]: r for r in client.get(f"/exams/{eid}/results").json()["rows"]}["062384"]
    assert d1["status"] == "pending" and d1["score"] is None and d1["sheet_id"] == s1


def test_khong_co_phieu_chua_duyet_trong_cot_diem_chinh_thuc(client, conn_thu, monkeypatch):
    """Một phiếu tự chốt đủ 40 câu + một phiếu còn 1 câu mờ: chỉ phiếu thứ nhất có `score`; phiếu thứ hai chỉ có điểm tạm 9,75."""
    can_anh("0002_C2", "0003_C3")
    eid = tao_de(client)
    dang_ky(conn_thu, eid, "795125", "222222")
    key = demo.khoa_demo("101")
    chon = {q: (key[q - 1] if q % 3 else "A" if key[q - 1] != "A" else "B") for q in range(1, 41)}
    dung = sum(q % 3 != 0 for q in range(1, 41))
    ds = iter([omr_gia(sbd="795125", chon=chon), omr_gia(sbd="222222", chon={q: key[q - 1] for q in range(1, 41)}, mo=(7,))])
    monkeypatch.setattr("backend.service.omr.doc_phieu", lambda kq, layout, mh: next(ds))
    ocr_khop(monkeypatch, ("795125", "101"), ("222222", "101"))
    a = tai(client, eid, "0002_C2").json()
    p = tai(client, eid, "0003_C3").json()
    assert a["status"] == "graded" and p["status"] == "needs_review"
    d = {r["sbd"]: r for r in client.get(f"/exams/{eid}/results").json()["rows"]}
    assert d["795125"]["status"] == "official" and d["795125"]["score"] == pytest.approx(0.25 * dung) and d["795125"]["num_correct"] == dung
    assert d["795125"]["score"] == pytest.approx(diem_doc_lap(conn_thu, a["sheet_id"], eid))
    assert d["222222"]["status"] == "pending" and d["222222"]["score"] is None and d["222222"]["num_correct"] is None
    assert d["222222"]["provisional_score"] == pytest.approx(9.75) and d["222222"]["pending_questions"] == 1
    n_chinh_thuc = conn_thu.execute("SELECT count(*) AS n FROM results WHERE exam_id = %s", (eid,)).fetchone()["n"]
    assert n_chinh_thuc == sum(r["score"] is not None for r in d.values()) == 1
    # Excel khớp API
    r = client.get(f"/exams/{eid}/export.xlsx")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Bảng điểm", "Chi tiết"]
    ws = wb["Bảng điểm"]
    assert "Đề thử (pytest)" in ws["A1"].value and "Ngày xuất" in ws["A2"].value and "điểm tạm chưa phải điểm chính thức" in ws["A3"].value.lower()
    api = client.get(f"/exams/{eid}/results").json()["rows"]
    xl = [[c.value for c in row] for row in ws.iter_rows(min_row=6, max_row=5 + len(api))]
    for dong, row in zip(api, xl):
        assert row == [dong["stt"], dong["sbd"], dong["full_name"], dong["exam_code"], dong["num_correct"], dong["score"],
                       dong["provisional_score"], dong["status_label"], dong["sheet_id"], None]    # cột J "Cảnh báo" trống khi không có phiếu trùng
    assert next(r for r in xl if r[1] == "222222")[5] is None and next(r for r in xl if r[1] == "222222")[6] == pytest.approx(9.75)
    ct = list(wb["Chi tiết"].iter_rows(min_row=2, values_only=True))
    assert len(ct) == 40 and {x[0] for x in ct} == {"795125"} and sum(x[7] == "Đúng" for x in ct) == dung     # chỉ phiếu chính thức
    assert all(x[6] == key[x[4] - 1] for x in ct)
    cd = r.headers["content-disposition"]
    assert "attachment" in cd and "filename*=UTF-8''" in cd and "Đề_thử_(pytest)" not in cd
    assert unquote(cd.split("filename*=UTF-8''")[1]).startswith("Đề_thử_pytest_") and cd.isascii()


def test_ky_thi_khong_ton_tai_va_trong(client):
    assert client.get("/exams/999999/results").status_code == 404
    assert client.get("/exams/999999/export.xlsx").status_code == 404
    eid = tao_de(client)
    b = client.get(f"/exams/{eid}/results").json()
    assert b["rows"] == [] and b["counts"]["students"] == 0
    wb = load_workbook(io.BytesIO(client.get(f"/exams/{eid}/export.xlsx").content))
    assert wb["Chi tiết"].max_row == 1


def test_giao_dien_f5_co_trong_html_va_js():
    from conftest import ROOT
    assert 'href="#/results"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "manBangDiem" in js and "export.xlsx" in js


# ------------------------------------------------------------------------------------------------ [DEMO-2] đáp án = bài làm 0005
def test_demo2_khoa_tu_bai_lam_0005_va_diem_mong_doi(client, conn_thu):
    """Nạp [DEMO-2] (trong ROLLBACK, chạy 2 lần không nhân đôi) -> tải 0005_C1 -> duyệt theo ground_truth -> điểm = điểm tính độc lập."""
    can_anh("0005_C1")
    uid = conn_thu.execute("SELECT user_id FROM users LIMIT 1").fetchone()["user_id"]
    tieu_de = demo.TIEU_DE_2 + " (pytest)"          # tên khác kỳ thi thật -> nhánh 'tạo mới' luôn chạy trong ROLLBACK
    k1 = demo.nap_demo_khop(conn_thu, uid, tieu_de=tieu_de)
    k2 = demo.nap_demo_khop(conn_thu, uid, tieu_de=tieu_de)
    assert k1["ky_thi_moi"] and not k2["ky_thi_moi"] and k2["exam_id"] == k1["exam_id"] and k2["thi_sinh_moi"] == 0
    eid, bl = k1["exam_id"], demo.doc_bai_lam()
    assert (k1["ma_de"], k1["sbd"]) == ("101", "823451") and len(k1["khoa"]) == 40
    assert k1["dac_biet"] == {"bo_trong": [6, 11], "nhieu_o": [8, 20, 26, 35]} and (k1["dung_mong_doi"], k1["diem_mong_doi"]) == (34, 8.5)
    ex = client.get(f"/exams/{eid}").json()
    ma = {c["code"]: c["answers"] for c in ex["codes"]}
    assert ma["101"] == k1["khoa"] and all(ma[m] == demo.khoa_demo(m) for m in ("102", "103", "104"))
    for q, v in enumerate(bl["nhan"], 1):                      # câu 1 ô (kể cả ô mờ): đáp án = chữ trong nhãn
        if len(v) == 1 and v != "-":
            assert ma["101"][q - 1] == v.upper()
    n = conn_thu.execute("SELECT count(*) AS n FROM exam_students WHERE exam_id = %s", (eid,)).fetchone()["n"]
    assert n == 28
    sid = tai(client, eid, "0005_C1").json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    if v["sbd"]["can_xem"] or v["exam_code"]["can_xem"]:
        assert client.put(f"/sheets/{sid}/identity", json={"sbd": bl["sbd"], "exam_code": bl["exam_code"]}).status_code == 200
    for c in client.get(f"/sheets/{sid}/review-questions").json():          # giáo viên "oracle": chốt đúng như trên giấy
        gt = bl["nhan"][c["question_no"] - 1]
        body = {"action": "set", "selected_options": "" if gt == "-" else gt.upper()}
        assert client.post(f"/sheets/{sid}/questions/{c['question_no']}/review", json=body).status_code == 200
    fin = client.get(f"/sheets/{sid}").json()
    assert fin["status"] == "graded" and fin["student"]["student_code"] == "823451" and fin["exam_code"]["matched_code"] == "101"
    assert fin["score"]["official"] == pytest.approx(8.5) == pytest.approx(diem_doc_lap(conn_thu, sid, eid)) and fin["score"]["num_correct"] == 34
    row = next(r for r in client.get(f"/exams/{eid}/results").json()["rows"] if r["sbd"] == "823451")
    assert row["status"] == "official" and row["score"] == pytest.approx(8.5) and row["num_correct"] == 34
