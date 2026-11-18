import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import dat_lai_demo as DL  # noqa: E402

MOC = datetime(2026, 10, 28, 9, 18, 32, tzinfo=timezone(timedelta(hours=7)))


def _dem(conn):
    return {b: conn.execute(f"SELECT count(*) AS n FROM {b}").fetchone()["n"] for b in ("answer_sheets", "results", "sheet_answers", "review_queue", "ocr_digits",
                                                                                      "score_audit_logs", "exam_students", "exams", "users", "classes")}


@pytest.fixture
def the_gioi(conn_thu, tmp_path):
    c = conn_thu
    uid = c.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()["user_id"]
    mon = c.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, 'Môn đặt lại') RETURNING subject_id", ("U" + uuid.uuid4().hex[:8].upper(),)).fetchone()["subject_id"]
    mau = c.execute("SELECT template_id FROM sheet_templates ORDER BY template_id LIMIT 1").fetchone()["template_id"]
    ky = lambda ten: c.execute("INSERT INTO exams (subject_id, template_id, exam_title, num_questions, max_score, created_by) VALUES (%s, %s, %s, 10, 10, %s) "   # noqa: E731
                               "RETURNING exam_id", (mon, mau, ten, uid)).fetchone()["exam_id"]
    chinh, tap, khac, that = ky("[DEMO-BV] thử đặt lại chính"), ky("[DEMO-BV-TẬP] thử đặt lại tập"), ky("[DEMO] kỳ thi khác"), ky("Kỳ thi THẬT")
    sv = c.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV đặt lại') RETURNING student_id", (str(uuid.uuid4().int)[:12],)).fetchone()["student_id"]
    for e in (chinh, tap):
        c.execute("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s)", (e, sv))
    kho = tmp_path / "kho"
    kho.mkdir()

    def phieu(exam, status, luc=None, rel=None):
        rel = rel or f"{exam}/{uuid.uuid4().hex[:8]}.jpg"
        (kho / rel).parent.mkdir(parents=True, exist_ok=True)
        (kho / rel).write_bytes(b"x")
        return c.execute("INSERT INTO answer_sheets (exam_id, image_path, status, detected_sbd, original_filename, uploaded_at) "
                         "VALUES (%s, %s, %s::sheet_status, '220001', 'a.jpg', %s) RETURNING sheet_id", (exam, rel, status, luc or datetime.now(timezone.utc))).fetchone()["sheet_id"]

    ids = {"C_CT": phieu(chinh, "graded"), "C_CX": phieu(chinh, "needs_review"), "C_TC": phieu(chinh, "rejected", rel="chung/anh.jpg"),
           "NEN_CT": phieu(tap, "graded", MOC - timedelta(days=1)), "NEN_CX": phieu(tap, "needs_review", MOC),
           "TAP_MOI": phieu(tap, "needs_review", MOC + timedelta(hours=2)), "TAP_LA_CU": phieu(tap, "rejected", MOC - timedelta(hours=1)),
           "KHAC": phieu(khac, "needs_review"), "KHAC_CHUNG": phieu(khac, "rejected", rel="chung/anh.jpg")}
    for k in ("C_CT", "NEN_CT"):
        c.execute("INSERT INTO results (exam_id, student_id, sheet_id, num_correct, score, status) VALUES (%s, %s, %s, 8, 8, 'confirmed')",
                  (chinh if k == "C_CT" else tap, sv, ids[k]))
    c.execute("INSERT INTO sheet_answers (sheet_id, question_no, state, selected_options) VALUES (%s, 1, 'filled', 'A')", (ids["C_CX"],))
    c.execute("INSERT INTO review_queue (sheet_id, reasons, details, priority) VALUES (%s, ARRAY['low_omr_confidence']::review_reason[], '{}', 2)", (ids["C_CX"],))
    kw = {"xoa_het": (chinh,), "tap": tap, "nen": {ids["NEN_CT"]: "graded", ids["NEN_CX"]: "needs_review"}, "moc": MOC}
    return {"c": c, "ids": ids, "kw": kw, "kho": kho, "chinh": chinh, "tap": tap, "khac": khac, "that": that}


def test_xem_truoc_khong_ghi_va_chon_dung(the_gioi):
    c, g = the_gioi["c"], the_gioi
    truoc = _dem(c)
    kh = DL.lap_ke_hoach(c, **g["kw"])
    txt = DL.in_xem_truoc(kh)
    assert _dem(c) == truoc
    i = g["ids"]
    assert kh["ids"] == sorted([i["C_CT"], i["C_CX"], i["C_TC"], i["TAP_MOI"]])
    assert [p["sheet_id"] for p in kh["bat_thuong"]] == [i["TAP_LA_CU"]] and kh["nen_doi"] == []
    assert kh["tep_dung_chung"] == ["chung/anh.jpg"] and "chung/anh.jpg" not in kh["tep"] and len(kh["tep"]) == 3
    assert kh["dem"]["answer_sheets"] == 4 and kh["dem"]["results"] == 1 and kh["dem"]["sheet_answers"] == 1 and kh["dem"]["review_queue"] == 1
    assert "SẼ XOÁ 4 phiếu" in txt and "[CÓ ĐIỂM CHÍNH THỨC]" in txt and "BẤT THƯỜNG" in txt and "Tệp GIỮ vì phiếu khác cũng dùng" in txt


def test_thuc_hien_chi_xoa_phieu_muc_tieu(the_gioi):
    c, g = the_gioi["c"], the_gioi
    i = g["ids"]
    kh = DL.lap_ke_hoach(c, **g["kw"])
    du_thi = c.execute("SELECT count(*) AS n FROM exam_students WHERE exam_id = ANY(%s)", ([g["chinh"], g["tap"]],)).fetchone()["n"]
    da = DL.thuc_hien(c, kh)
    assert da["answer_sheets"] == 4 and da["results"] == 1
    con = {r["sheet_id"] for r in c.execute("SELECT sheet_id FROM answer_sheets WHERE sheet_id = ANY(%s)", (list(i.values()),)).fetchall()}
    assert con == {i["NEN_CT"], i["NEN_CX"], i["TAP_LA_CU"], i["KHAC"], i["KHAC_CHUNG"]}
    assert DL.dem_ky_thi(c, [g["chinh"]])[g["chinh"]]["tong"] == 0
    assert c.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s AND status = 'confirmed'", (i["NEN_CT"],)).fetchone()["n"] == 1
    assert c.execute("SELECT count(*) AS n FROM exam_students WHERE exam_id = ANY(%s)", ([g["chinh"], g["tap"]],)).fetchone()["n"] == du_thi
    kq = DL.D.xoa_tep(g["kho"], kh["tep"])
    assert kq["da_xoa"] == 3 and (g["kho"] / "chung" / "anh.jpg").exists()


def test_nen_bi_doi_thi_canh_bao(the_gioi):
    c, g = the_gioi["c"], the_gioi
    c.execute("UPDATE answer_sheets SET status = 'graded' WHERE sheet_id = %s", (g["ids"]["NEN_CX"],))
    kh = DL.lap_ke_hoach(c, **g["kw"])
    assert len(kh["nen_doi"]) == 1 and "CẢNH BÁO" in DL.in_xem_truoc(kh)


def test_tu_choi_ky_thi_khong_co_dau_demo(the_gioi):
    g = the_gioi
    with pytest.raises(DL.LoiDatLai, match="DEMO"):
        DL.lap_ke_hoach(g["c"], **(g["kw"] | {"xoa_het": (g["chinh"], g["that"])}))


def test_mac_dinh_dung_ky_thi_demo_va_nen_da_chot():
    assert DL.KY_THI_XOA_HET == (1380, 1381, 1633) and DL.KY_THI_TAP == 1632
    assert sorted(DL.NEN_TAP) == [3878, 3880, 4270, 4271, 4272, 6028] and DL.XAC_NHAN == "DAT_LAI"
    assert DL.KY_THI_DUOC_PHEP == {1380, 1381, 1632, 1633}


NGOAI_PHAM_VI = (6, 115, 178, 509)


def test_id_that_khong_dung_ky_thi_khac_du_co_dau_demo(conn_thu):
    c = conn_thu
    ten = {r["exam_id"]: r["exam_title"] for r in c.execute("SELECT exam_id, exam_title FROM exams WHERE exam_id = ANY(%s)",
                                                            (list(NGOAI_PHAM_VI) + sorted(DL.KY_THI_DUOC_PHEP),)).fetchall()}
    if len(ten) < len(NGOAI_PHAM_VI) + 4:
        pytest.skip(f"CSDL này không có đủ kỳ thi {NGOAI_PHAM_VI} + {sorted(DL.KY_THI_DUOC_PHEP)} (máy khác)")
    assert "[DEMO" in ten[6] and "[DEMO" in ten[178]
    them = lambda e: c.execute("INSERT INTO answer_sheets (exam_id, image_path, status, original_filename, uploaded_at) VALUES (%s, %s, 'needs_review', 'v.jpg', now()) "  # noqa: E731
                               "RETURNING sheet_id", (e, f"v_test/{uuid.uuid4().hex}.jpg")).fetchone()["sheet_id"]
    moi = {e: them(e) for e in NGOAI_PHAM_VI}
    moi_1633 = them(1633)
    truoc = {e: DL.dem_ky_thi(c, [e])[e] for e in NGOAI_PHAM_VI}
    assert all(truoc[e]["tong"] >= 1 for e in NGOAI_PHAM_VI)
    kh = DL.lap_ke_hoach(c)
    assert {p["exam_id"] for p in kh["xoa"]} <= DL.KY_THI_DUOC_PHEP and moi_1633 in kh["ids"]
    assert not set(moi.values()) & set(kh["ids"])
    ngoai_ids = {r["sheet_id"] for r in c.execute("SELECT sheet_id FROM answer_sheets WHERE exam_id = ANY(%s)", (list(NGOAI_PHAM_VI),)).fetchall()}
    assert not ngoai_ids & set(kh["ids"])
    DL.thuc_hien(c, kh)
    assert {e: DL.dem_ky_thi(c, [e])[e] for e in NGOAI_PHAM_VI} == truoc
    assert DL.dem_ky_thi(c, [1633])[1633]["tong"] == 0


def test_hau_kiem_tu_choi_phieu_ngoai_pham_vi(the_gioi, monkeypatch):
    g = the_gioi
    goc = g["c"].execute

    def execute(sql, *a, **k):
        if isinstance(sql, str) and sql.lstrip().startswith("SELECT a.sheet_id") and "a.exam_id = ANY(%s) ORDER BY" in sql:
            return goc(sql, ([*a[0][0], g["khac"]],), **k)
        return goc(sql, *a, **k)
    monkeypatch.setattr(g["c"], "execute", execute)
    with pytest.raises(DL.LoiDatLai, match="ngoài phạm vi"):
        DL.lap_ke_hoach(g["c"], **g["kw"])
