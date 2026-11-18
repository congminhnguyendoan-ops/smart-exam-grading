import sys
import uuid

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import don_du_lieu_test as D  # noqa: E402


def _dem(conn):
    return {b: conn.execute(f"SELECT count(*) AS n FROM {b}").fetchone()["n"] for b in D.BANG_XOA}


@pytest.fixture
def the_gioi(conn_thu, tmp_path):
    c = conn_thu
    uid = c.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()["user_id"]
    mon = c.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, 'Môn dọn') RETURNING subject_id", ("D" + uuid.uuid4().hex[:8].upper(),)).fetchone()["subject_id"]
    mau = c.execute("SELECT template_id FROM sheet_templates ORDER BY template_id LIMIT 1").fetchone()["template_id"]
    ky = lambda ten: c.execute("INSERT INTO exams (subject_id, template_id, exam_title, num_questions, max_score, created_by) VALUES (%s, %s, %s, 10, 10, %s) RETURNING exam_id",   # noqa: E731
                               (mon, mau, ten, uid)).fetchone()["exam_id"]
    e1, e2, e3 = ky("[DEMO-BV-TẬP] thử dọn E1"), ky("[DEMO] kỳ thi khác E2"), ky("Kỳ thi THẬT E3")
    sv = c.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV dọn') RETURNING student_id", (str(uuid.uuid4().int)[:12],)).fetchone()["student_id"]
    kho = tmp_path / "kho"
    kho.mkdir()

    def phieu(exam, status, sbd="123456", ten="att.pc5ziEjVdDSu9zNPSpp9.jpeg", sv_id=None, anh=True):
        n = uuid.uuid4().hex[:8]
        rel = f"{exam}/{n}.jpg"
        if anh:
            (kho / str(exam)).mkdir(exist_ok=True)
            (kho / rel).write_bytes(b"x")
        return c.execute("INSERT INTO answer_sheets (exam_id, image_path, aligned_image_path, status, detected_sbd, original_filename, matched_student_id) "
                         "VALUES (%s, %s, %s, %s::sheet_status, %s, %s, %s) RETURNING sheet_id", (exam, rel, rel + ".nan.png" if anh else None, status, sbd, ten, sv_id)).fetchone()["sheet_id"]

    def con(sid, kho_anh=True):
        for q in (1, 2):
            c.execute("INSERT INTO sheet_answers (sheet_id, question_no, state, selected_options) VALUES (%s, %s, 'filled', 'A')", (sid, q))
        c.execute("INSERT INTO review_queue (sheet_id, reasons, details, priority) VALUES (%s, ARRAY['low_omr_confidence']::review_reason[], '{}', 2)", (sid,))
        for pos in (0, 1):
            rel = f"ocr/{sid}_{pos}.png"
            if kho_anh:
                (kho / "ocr").mkdir(exist_ok=True)
                (kho / rel).write_bytes(b"x")
            c.execute("INSERT INTO ocr_digits (sheet_id, field, position, predicted_digit, confidence, top_k, crop_image_path) VALUES (%s, 'sbd', %s, 1, 0.9, '[]', %s)", (sid, pos, rel))

    ids = {"A": phieu(e1, "graded", sv_id=sv), "B": phieu(e1, "needs_review"), "C": phieu(e1, "rejected"), "V": phieu(e1, "needs_review", sv_id=sv),
           "X2": phieu(e2, "needs_review"), "X3": phieu(e3, "needs_review"), "KHONG_ANH": phieu(e1, "rejected", anh=False)}
    for k in ("A", "B", "X2", "X3"):
        con(ids[k])
    c.execute("INSERT INTO results (exam_id, student_id, sheet_id, num_correct, score, status) VALUES (%s, %s, %s, 5, 5, 'confirmed')", (e1, sv, ids["A"]))
    c.execute("INSERT INTO results (exam_id, student_id, sheet_id, num_correct, score, status) VALUES (%s, %s, %s, 3, 3, 'void')", (e1, sv, ids["V"]))
    return {"conn": c, "e1": e1, "e2": e2, "e3": e3, "ids": ids, "kho": kho, "sv": sv}


def test_xem_truoc_khong_ghi_gi(the_gioi):
    c, g = the_gioi["conn"], the_gioi
    truoc = _dem(c)
    kh = D.lap_ke_hoach(c, (g["e1"],))
    txt = D.in_xem_truoc(kh)
    assert _dem(c) == truoc
    assert [p["sheet_id"] for p in kh["giu"]] == [g["ids"]["A"]]
    assert sorted(kh["ids"]) == sorted(g["ids"][k] for k in ("B", "C", "V", "KHONG_ANH"))
    assert kh["dem"] == {"score_audit_logs": 1, "results": 1, "ocr_digits": 2, "sheet_answers": 2, "review_queue": 1, "answer_sheets": 4}
    assert "GIỮ (1 phiếu)" in txt and "XOÁ (4 phiếu)" in txt and "att.pc5ziE….jpeg" in txt and "NGOÀI PHẠM VI" in txt
    assert any(p["sheet_id"] == g["ids"]["X2"] for p in kh["ngoai_pham_vi"])
    assert not any(p["sheet_id"] == g["ids"]["X3"] for p in kh["ngoai_pham_vi"])


def test_thuc_hien_dung_pham_vi_va_dem_dung_so_dong(the_gioi):
    c, g = the_gioi["conn"], the_gioi
    truoc = _dem(c)
    kh = D.lap_ke_hoach(c, (g["e1"],))
    da = D.thuc_hien(c, kh)
    assert da == kh["dem"]
    sau = _dem(c)
    assert {b: truoc[b] - sau[b] for b in D.BANG_XOA} == kh["dem"]
    ton_tai = lambda k: c.execute("SELECT 1 FROM answer_sheets WHERE sheet_id = %s", (g["ids"][k],)).fetchone() is not None   # noqa: E731
    assert ton_tai("A") and ton_tai("X2") and ton_tai("X3")
    assert not any(ton_tai(k) for k in ("B", "C", "V", "KHONG_ANH"))
    assert c.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s", (g["ids"]["A"],)).fetchone()["n"] == 1
    for k in ("X2", "X3"):
        assert c.execute("SELECT count(*) AS n FROM sheet_answers WHERE sheet_id = %s", (g["ids"][k],)).fetchone()["n"] == 2
        assert c.execute("SELECT count(*) AS n FROM review_queue WHERE sheet_id = %s", (g["ids"][k],)).fetchone()["n"] == 1
    for k in ("exams", "students", "subjects", "exam_codes", "answer_keys", "users", "classes"):
        assert c.execute(f"SELECT count(*) AS n FROM {k}").fetchone()["n"] >= 0
    assert c.execute("SELECT 1 FROM exams WHERE exam_id = ANY(%s)", ([g["e1"], g["e2"], g["e3"]],)).fetchall().__len__() == 3
    ks = D.kiem_sau(c, (g["e1"],))
    assert not any(ks["mo_coi"].values()) and ks["thong_ke"][g["e1"]]["tong"] == 1


def test_lech_so_dong_thi_hoan_tac(the_gioi):
    c, g = the_gioi["conn"], the_gioi
    truoc = _dem(c)
    kh = D.lap_ke_hoach(c, (g["e1"],))
    kh["dem"] = {**kh["dem"], "sheet_answers": kh["dem"]["sheet_answers"] + 1}
    with pytest.raises(D.LoiDon, match="sheet_answers"):
        D.thuc_hien(c, kh)
    assert _dem(c) == truoc
    kh2 = D.lap_ke_hoach(c, (g["e1"],))
    kh2["dem"] = {**kh2["dem"], "answer_sheets": 99}
    with pytest.raises(D.LoiDon):
        D.thuc_hien(c, kh2)
    assert _dem(c) == truoc


def test_ids_va_giu(the_gioi):
    c, g = the_gioi["conn"], the_gioi
    kh = D.lap_ke_hoach(c, (g["e1"],), ids_them=[g["ids"]["X2"]], giu_them=[g["ids"]["B"]])
    assert g["ids"]["X2"] in kh["ids"] and g["ids"]["B"] not in kh["ids"]
    assert {p["sheet_id"] for p in kh["giu"]} == {g["ids"]["A"], g["ids"]["B"]}
    with pytest.raises(D.LoiDon, match="kỳ thi thật|không có dấu"):
        D.lap_ke_hoach(c, (g["e1"],), ids_them=[g["ids"]["X3"]])
    with pytest.raises(D.LoiDon, match="Không có|không có phiếu"):
        D.lap_ke_hoach(c, (g["e1"],), ids_them=[2_000_000_000])
    ks = D.lap_ke_hoach(c, (g["e1"],))
    assert g["ids"]["X3"] not in ks["ids"] and g["ids"]["X2"] not in ks["ids"]


def test_ids_khong_xoa_phieu_co_diem_chinh_thuc_hop_le(the_gioi):
    c, g = the_gioi["conn"], the_gioi
    sv = c.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV 2') RETURNING student_id", (str(uuid.uuid4().int)[:12],)).fetchone()["student_id"]
    sid = c.execute("INSERT INTO answer_sheets (exam_id, image_path, status, matched_student_id) VALUES (%s, 'x.jpg', 'graded', %s) RETURNING sheet_id", (g["e2"], sv)).fetchone()["sheet_id"]
    c.execute("INSERT INTO results (exam_id, student_id, sheet_id, num_correct, score, status) VALUES (%s, %s, %s, 1, 1, 'confirmed')", (g["e2"], sv, sid))
    with pytest.raises(D.LoiDon, match="điểm chính thức"):
        D.lap_ke_hoach(c, (g["e1"],), ids_them=[sid])


def test_sao_luu_va_xoa_tep(the_gioi, tmp_path):
    c, g = the_gioi["conn"], the_gioi
    kh = D.lap_ke_hoach(c, (g["e1"],))
    tep = D.sao_luu(c, kh, tmp_path / "sl", g["kho"])
    ten = {p.name for p in tep}
    assert {"answer_sheets.csv", "sheet_answers.csv", "review_queue.csv", "ocr_digits.csv", "results.csv", "score_audit_logs.csv", "ke_hoach.json"} <= ten
    assert (tmp_path / "sl" / "answer_sheets.csv").read_text(encoding="utf-8").count("\n") >= 5
    kho_ngoai = tmp_path / "ngoai.txt"
    kho_ngoai.write_text("không được xoá", encoding="utf-8")
    ket = D.xoa_tep(g["kho"], kh["tep"] + ["../ngoai.txt", "khong/co/tep.jpg"])
    assert ket["bo_qua_ngoai_kho"] == 1 and ket["khong_ton_tai"] >= 1 and ket["da_xoa"] >= 3
    assert kho_ngoai.exists()
    assert (g["kho"] / "ocr" / f"{g['ids']['A']}_0.png").exists()
    assert not any((g["kho"] / rel).exists() for rel in kh["tep"])


def test_rut_gon_ten():
    assert D.rut_gon_ten("image.jpg") == "image.jpg" and D.rut_gon_ten(None) == "" and D.rut_gon_ten("") == ""
    assert D.rut_gon_ten("att.pc5ziEjVdDSu9zNPSpp9Llr1udeCi1EQjzdpGAIhgWQ.jpeg") == "att.pc5ziE….jpeg"
    assert D.rut_gon_ten("a" * 40) == "a" * 10 + "…"


def test_mac_dinh_pham_vi_chi_hai_ky_thi_demo():
    assert D.PHAM_VI == (1632, 1633)
    src = (ROOT / "tools" / "don_du_lieu_test.py").read_text(encoding="utf-8")
    assert 'if not a.thuc_hien:\n            conn.read_only = True' in src
    assert '"XOA"' in src and "conn.commit()" in src and src.count("conn.commit()") == 1
