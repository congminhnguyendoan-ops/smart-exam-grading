import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend import demo, don_anh, service, tu_cham
from test_backend_api import anh_trang, can_anh, dem_results, ocr_khop, omr_gia, tai, tao_de, them_sv
from test_dang_nhap import bang_moi, client_on, the_gioi  # noqa: F401  (fixture)

ANH = "0002_C2"
Q = 7


def dung_het():
    key = demo.khoa_demo("101")
    return key, {q: key[q - 1] for q in range(1, 41)}


def doi_ly_do(omr, theo_cau):
    cau = tuple(dataclasses.replace(c, ly_do=theo_cau[c.cau]) if c.cau in theo_cau else c for c in omr.cau)
    return dataclasses.replace(omr, cau=cau)


def tai_phieu(client, conn_thu, monkeypatch, *, nhieu=(Q,), ly_do=None, mo=()):
    can_anh(ANH)
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    key, chon = dung_het()
    omr = omr_gia(chon=chon, nhieu=nhieu, mo=mo)
    if ly_do:
        omr = doi_ly_do(omr, ly_do)
    monkeypatch.setattr("backend.service.omr.doc_phieu", lambda kq, layout, mh: omr)
    ocr_khop(monkeypatch)
    t = tai(client, eid, ANH).json()
    return eid, t, key


def duyet(client, sid, n=Q, **body):
    return client.post(f"/sheets/{sid}/questions/{n}/auto-review", json=body)


def diem_cau(v, n=Q):
    return next(q for q in v["questions"] if q["question_no"] == n)


def test_nhieu_o_thuan_tu_cham_sai_phieu_graded_ngay(client, conn_thu, monkeypatch):
    eid, t, _ = tai_phieu(client, conn_thu, monkeypatch)
    assert t["status"] == "graded" and t["pending_questions"] == 0 and t["auto_graded_pending"] == 1
    assert t["official_score"] == pytest.approx(0.25 * 39)
    v = client.get(f"/sheets/{t['sheet_id']}").json()
    q = diem_cau(v)
    assert q["is_correct"] is False and q["needs_review"] is False and q["tu_cham_can_xem"] is True and q["state"] == "multiple"
    assert q["selected_options"] == "AB" and q["omr_selected_options"] == "AB" and q["reasons"] == ["nhieu_o"]
    assert v["score"]["result_status"] == "auto" and v["score"]["auto_graded_pending"] == 1 and v["score"]["pending_questions"] == 0
    assert v["review"] is None
    assert dem_results(conn_thu, t["sheet_id"]) == 1
    diem_db = conn_thu.execute("SELECT fn_grade_sheet(%s) AS s", (t["sheet_id"],)).fetchone()["s"]
    assert Decimal(diem_db) == Decimal("9.75")
    sh = conn_thu.execute("SELECT status::text AS s, raw_score, num_correct FROM answer_sheets WHERE sheet_id = %s", (t["sheet_id"],)).fetchone()
    assert sh["s"] == "graded" and sh["raw_score"] == Decimal("9.75") and sh["num_correct"] == 39
    assert conn_thu.execute("SELECT count(*) AS n FROM review_queue WHERE sheet_id = %s", (t["sheet_id"],)).fetchone()["n"] == 0


def test_danh_gia_phieu_khong_sinh_multiple_marks_cho_nhieu_o_thuan(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(3, 9, 20))
    assert t["status"] == "graded" and t["auto_graded_pending"] == 3
    r = service.danh_gia_phieu(conn_thu, t["sheet_id"], 1)
    assert r["status"] == "graded" and "multiple_marks" not in r["ly_do"] and r["ly_do"] == []
    assert conn_thu.execute("SELECT count(*) AS n FROM review_queue WHERE sheet_id = %s", (t["sheet_id"],)).fetchone()["n"] == 0


@pytest.mark.parametrize("them", ["o_mo", "vet_nho", "to_nhat", "tin_cay_thap", "vi_tri"])
def test_nhieu_o_kem_ly_do_khac_van_la_cau_cho(client, conn_thu, monkeypatch, them):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch, ly_do={Q: ("nhieu_o", them)})
    assert t["status"] == "needs_review" and t["official_score"] is None and t["pending_questions"] == 1 and t["auto_graded_pending"] == 0
    v = client.get(f"/sheets/{t['sheet_id']}").json()
    q = diem_cau(v)
    assert q["needs_review"] is True and q["is_correct"] is None and q["tu_cham_can_xem"] is False
    assert "multiple_marks" in "".join(v["review"]["reasons"])


def test_giu_nhu_may_cham_khong_doi_diem(client, conn_thu, monkeypatch):
    eid, t, _ = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    nhat_ky_truoc = conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs").fetchone()["n"]
    r = duyet(client, sid, action="keep")
    assert r.status_code == 200, r.text
    v = r.json()
    q = diem_cau(v)
    assert q["tu_cham_can_xem"] is False and q["is_correct"] is False and q["selected_options"] == "AB" and q["manually_edited"] is False
    assert v["score"]["official"] == pytest.approx(9.75) and v["score"]["result_status"] == "auto" and v["score"]["auto_graded_pending"] == 0
    a = conn_thu.execute("SELECT reviewed_at, reviewed_by FROM sheet_answers WHERE sheet_id = %s AND question_no = %s", (sid, Q)).fetchone()
    assert a["reviewed_at"] is not None
    assert conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs").fetchone()["n"] == nhat_ky_truoc
    assert client.get(f"/exams/{eid}/auto-graded-review").json() == []
    assert duyet(client, sid, action="keep").status_code == 409


def test_chon_lai_mot_o_tinh_lai_diem_va_ghi_vet(client, conn_thu, monkeypatch):
    eid, t, key = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    r = duyet(client, sid, action="set", selected_options=key[Q - 1])
    assert r.status_code == 200, r.text
    v = r.json()
    q = diem_cau(v)
    assert q["is_correct"] is True and q["selected_options"] == key[Q - 1] and q["manually_edited"] is True and q["tu_cham_can_xem"] is False
    assert v["score"]["official"] == pytest.approx(10.0) and v["score"]["result_status"] == "manual_edited" and v["score"]["num_correct"] == 40
    res = conn_thu.execute("SELECT status::text AS s, score, num_correct, confirmed_by FROM results WHERE sheet_id = %s", (sid,)).fetchone()
    assert res["s"] == "manual_edited" and res["score"] == Decimal("10.000") and res["num_correct"] == 40
    log = conn_thu.execute("SELECT action, old_score, new_score, old_status::text AS os, new_status::text AS ns, reason FROM score_audit_logs l "
                           "JOIN results r USING (result_id) WHERE r.sheet_id = %s ORDER BY audit_id", (sid,)).fetchall()
    assert [x["action"] for x in log] == ["INSERT", "UPDATE"]
    assert log[1]["old_score"] == Decimal("9.750") and log[1]["new_score"] == Decimal("10.000") and (log[1]["os"], log[1]["ns"]) == ("auto", "manual_edited")
    assert log[1]["reason"] == f"Giáo viên sửa câu {Q}: AB → {key[Q - 1]}"
    sh = conn_thu.execute("SELECT raw_score, num_correct FROM answer_sheets WHERE sheet_id = %s", (sid,)).fetchone()
    assert sh["raw_score"] == Decimal("10.000") and sh["num_correct"] == 40
    assert Decimal(conn_thu.execute("SELECT fn_grade_sheet(%s) AS s", (sid,)).fetchone()["s"]) == Decimal("10.000")
    assert duyet(client, sid, action="set", selected_options="A").status_code == 409


def test_chon_lai_sai_van_giu_diem_nhung_ghi_vet(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch)
    sai = next(o for o in "ABCD" if o != key[Q - 1])
    v = duyet(client, t["sheet_id"], action="set", selected_options=sai).json()
    assert v["score"]["official"] == pytest.approx(9.75) and v["score"]["result_status"] == "manual_edited" and diem_cau(v)["is_correct"] is False


def test_hanh_dong_khong_hop_le_va_cau_khong_cho_xem_lai(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    assert duyet(client, sid, action="set").status_code == 422 or duyet(client, sid, action="set").status_code == 400
    assert duyet(client, sid, action="set", selected_options="X").status_code in (400, 422)
    assert duyet(client, sid, n=1, action="keep").status_code == 409
    assert client.post(f"/sheets/{sid}/questions/{Q}/review", json={"action": "confirm"}).status_code == 409


def test_hai_thao_tac_lien_tiep_tren_cung_cau_chi_mot_thanh_cong(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    ma = [duyet(client, sid, action="set", selected_options=key[Q - 1]).status_code, duyet(client, sid, action="keep").status_code]
    assert ma == [200, 409]
    v = client.get(f"/sheets/{sid}").json()
    assert v["score"]["official"] == pytest.approx(10.0) and diem_cau(v)["selected_options"] == key[Q - 1]
    import inspect
    nguon = inspect.getsource(service.xem_lai_cau_tu_cham) + inspect.getsource(service.giu_nhu_may_cham)
    assert nguon.count("FOR UPDATE") == 4


def test_phieu_cho_van_xem_lai_duoc_va_khong_co_diem_chinh_thuc(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch, nhieu=(Q,), mo=(12,))
    sid = t["sheet_id"]
    assert t["status"] == "needs_review" and t["auto_graded_pending"] == 1 and t["pending_questions"] == 1
    v = duyet(client, sid, action="set", selected_options=key[Q - 1]).json()
    assert v["status"] == "needs_review" and v["score"]["official"] is None and v["score"]["provisional"] == pytest.approx(0.25 * 39)
    assert dem_results(conn_thu, sid) == 0 and diem_cau(v)["is_correct"] is True


def test_phieu_rejected_bi_tu_choi(client, conn_thu):
    eid = tao_de(client)
    sid = tai(client, eid, "trang", anh_trang()).json()["sheet_id"]
    r = duyet(client, sid, action="keep")
    assert r.status_code == 409 and "rejected" in r.json()["detail"]


def test_danh_sach_hang_cho_va_giu_tat_ca(client, conn_thu, monkeypatch):
    eid, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(3, 7))
    sid = t["sheet_id"]
    ds = client.get(f"/exams/{eid}/auto-graded-review").json()
    assert [(c["sheet_id"], c["question_no"], c["omr_reading"]) for c in ds] == [(sid, 3, "AB"), (sid, 7, "AB")]
    assert ds[0]["official_score"] == pytest.approx(9.5) and ds[0]["student_name"]
    assert client.get(f"/exams/{eid}/sheets").json()[0]["auto_graded_pending"] == 2
    muc = [{"sheet_id": sid, "question_no": 3}, {"sheet_id": sid, "question_no": 7}]
    assert client.post(f"/exams/{eid}/auto-graded-review/keep-all", json={"items": muc, "confirm": False}).status_code == 422
    assert client.post(f"/exams/{eid}/auto-graded-review/keep-all", json={"items": [{"sheet_id": sid + 999999, "question_no": 3}], "confirm": True}).status_code == 400 \
        or client.post(f"/exams/{eid}/auto-graded-review/keep-all", json={"items": [{"sheet_id": sid + 999999, "question_no": 3}], "confirm": True}).status_code == 422
    truoc = conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs").fetchone()["n"]
    r = client.post(f"/exams/{eid}/auto-graded-review/keep-all", json={"items": muc, "confirm": True})
    assert r.status_code == 200 and r.json() == {"da_giu": 2, "bo_qua": 0}
    assert client.get(f"/exams/{eid}/auto-graded-review").json() == []
    v = client.get(f"/sheets/{sid}").json()
    assert v["score"]["official"] == pytest.approx(9.5) and v["score"]["result_status"] == "auto"
    assert conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs").fetchone()["n"] == truoc
    r2 = client.post(f"/exams/{eid}/auto-graded-review/keep-all", json={"items": muc, "confirm": True})
    assert r2.json() == {"da_giu": 0, "bo_qua": 2}
    nk = conn_thu.execute("SELECT details FROM admin_audit_log WHERE action = 'giu_nhu_may_cham' ORDER BY log_id DESC LIMIT 1").fetchone()["details"]
    assert nk["so_cau"] == 2


def test_cac_bo_loc_ket_qua_coi_manual_edited_la_chinh_thuc(client, conn_thu, monkeypatch):
    eid, t, key = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    conn_thu.execute("INSERT INTO exam_students (exam_id, student_id) SELECT %s, student_id FROM students WHERE student_code = '795125'", (eid,))
    duyet(client, sid, action="set", selected_options=key[Q - 1])
    b = client.get(f"/exams/{eid}/results").json()
    d = next(r for r in b["rows"] if r["sbd"] == "795125")
    assert d["status"] == "official" and d["score"] == pytest.approx(10.0) and d["provisional_score"] is None and d["auto_graded_pending"] == 0
    assert b["counts"]["official"] == 1 and b["counts"]["pending"] == 0 and b["counts"]["auto_graded_pending_questions"] == 0
    ds = client.get(f"/exams/{eid}/sheets").json()
    assert ds[0]["official_score"] == pytest.approx(10.0) and ds[0]["result_status"] == "manual_edited"
    xlsx = client.get(f"/exams/{eid}/export.xlsx")
    assert xlsx.status_code == 200
    from io import BytesIO
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(xlsx.content))
    chi_tiet = [r for r in wb["Chi tiết"].iter_rows(min_row=2, values_only=True) if r[3] == sid]
    assert len(chi_tiet) == 40 and all(r[7] == "Đúng" for r in chi_tiet)
    dong = next(r for r in wb["Bảng điểm"].iter_rows(min_row=6, values_only=True) if r[1] == "795125")
    assert dong[5] == 10 and dong[7] == "Chính thức" and not dong[9]


def test_bang_diem_va_excel_canh_bao_khi_con_cau_tu_cham(client, conn_thu, monkeypatch):
    eid, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(3, 7))
    conn_thu.execute("INSERT INTO exam_students (exam_id, student_id) SELECT %s, student_id FROM students WHERE student_code = '795125'", (eid,))
    b = client.get(f"/exams/{eid}/results").json()
    d = next(r for r in b["rows"] if r["sbd"] == "795125")
    assert d["status"] == "official" and d["score"] == pytest.approx(9.5) and d["auto_graded_pending"] == 2
    assert b["counts"]["auto_graded_pending_questions"] == 2 and b["counts"]["students_auto_graded_pending"] == 1 and b["counts"]["official"] == 1
    from io import BytesIO
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(client.get(f"/exams/{eid}/export.xlsx").content))
    dong = next(r for r in wb["Bảng điểm"].iter_rows(min_row=6, values_only=True) if r[1] == "795125")
    assert dong[5] == 9.5 and "2 câu tô nhiều ô đã chấm sai, chờ xem lại" in dong[9]
    sheet_ct = [r for r in wb["Chi tiết"].iter_rows(min_row=2, values_only=True) if r[3] == t["sheet_id"]]
    assert len(sheet_ct) == 40 and sum(r[7] == "Sai" for r in sheet_ct) == 2


def test_don_anh_khong_xoa_phieu_con_cau_tu_cham(client, conn_thu, monkeypatch, cau_hinh_thu, csdl_003):
    eid, t, _ = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    sau = datetime.now(timezone.utc) + timedelta(hours=25)
    assert sid not in {p["sheet_id"] for p in don_anh.phieu_can_xoa(conn_thu, cau_hinh_thu, sau, ky_thi=[eid])}
    assert duyet(client, sid, action="keep").status_code == 200
    assert sid in {p["sheet_id"] for p in don_anh.phieu_can_xoa(conn_thu, cau_hinh_thu, sau, ky_thi=[eid])}


def test_m_hien_canh_bao_va_bo_dem_rieng():
    import json
    import shutil
    import subprocess
    from conftest import ROOT
    m = (ROOT / "frontend" / "m.js").read_text(encoding="utf-8")
    assert "câu tô nhiều ô đã chấm sai – xem lại trên máy tính" in m and "tu_cham_can_xem" in m and "hd.demTuCham()" in m
    if shutil.which("node") is None:
        pytest.skip("không có node")
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "hang_doi_tu_cham.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    json.dumps(r.returncode)


def test_phan_quyen_hang_cho_va_xem_lai(the_gioi):
    w = the_gioi
    url = f"/sheets/{w.SA}/questions/1/auto-review"
    ds = f"/exams/{w.EA}/auto-graded-review"
    giu = f"/exams/{w.EA}/auto-graded-review/keep-all"
    muc = {"items": [{"sheet_id": w.SA, "question_no": 1}], "confirm": True}
    for goi in (lambda h: w.c.post(url, headers=h, json={"action": "keep"}), lambda h: w.c.get(ds, headers=h), lambda h: w.c.post(giu, headers=h, json=muc)):
        assert goi({}).status_code == 401
        assert goi(w.hSv).status_code == 403
        r = goi(w.hB)
        assert r.status_code == 404 and r.json()["detail"].startswith("Không có "), r.text
    r = w.c.post(url, headers=w.hA, json={"action": "keep"})
    assert r.status_code == 409 and "rejected" in r.json()["detail"]
    assert w.c.get(ds, headers=w.hA).json() == [] and w.c.post(giu, headers=w.hA, json=muc).json() == {"da_giu": 0, "bo_qua": 1}


def test_ma_thuan_tuy_khong_chu_thich():
    assert tu_cham.giu_tat_ca and service.la_nhieu_o_thuan(["nhieu_o"]) and not service.la_nhieu_o_thuan(["nhieu_o", "o_mo"]) and not service.la_nhieu_o_thuan([])
