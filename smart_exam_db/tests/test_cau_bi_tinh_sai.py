import shutil
import subprocess
from pathlib import Path

import pytest

from backend import service
from test_dang_nhap import bang_moi, client_on, the_gioi  # noqa: F401  (fixture)
from test_tu_cham_nhieu_o import Q, diem_cau, tai_phieu

GOC = Path(__file__).resolve().parents[1]


def dap_an_db(conn, sid):
    return {r["question_no"]: r["correct_option"] for r in conn.execute(
        "SELECT k.question_no, k.correct_option FROM answer_keys k JOIN answer_sheets a ON a.exam_code_id = k.exam_code_id "
        "WHERE a.sheet_id = %s", (sid,)).fetchall()}


def test_correct_option_dung_ma_de_va_khong_doi_diem(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    db = dap_an_db(conn_thu, sid)
    assert len(v["questions"]) == 40
    assert all(q["correct_option"] == db[q["question_no"]] for q in v["questions"])
    assert [q["correct_option"] for q in v["questions"]] == list(key)
    assert v["score"]["official"] == pytest.approx(0.25 * 39) and v["score"]["num_correct"] == 39
    assert diem_cau(v, Q)["is_correct"] is False and diem_cau(v, Q)["correct_option"] == key[Q - 1]


def test_correct_option_khong_doi_cach_tinh_diem(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    truoc = conn_thu.execute("SELECT score, num_correct FROM results WHERE sheet_id = %s", (sid,)).fetchone()
    client.get(f"/sheets/{sid}")
    client.get(f"/sheets/{sid}")
    sau = conn_thu.execute("SELECT score, num_correct FROM results WHERE sheet_id = %s", (sid,)).fetchone()
    assert truoc == sau
    assert conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs l JOIN results r USING (result_id) WHERE r.sheet_id = %s",
                            (sid,)).fetchone()["n"] == 1


def test_correct_option_none_khi_chua_biet_ma_de(conn_thu):
    ex = conn_thu.execute("SELECT exam_id FROM exams LIMIT 1").fetchone()
    if not ex:
        pytest.skip("không có kỳ thi nào để dựng phiếu thử")
    sid = conn_thu.execute(
        "SELECT sheet_id FROM answer_sheets a WHERE exam_code_id IS NULL AND EXISTS (SELECT 1 FROM sheet_answers s WHERE s.sheet_id = a.sheet_id) LIMIT 1"
    ).fetchone()
    if not sid:
        pytest.skip("không có phiếu chưa biết mã đề")
    v = service.xem_phieu(conn_thu, sid["sheet_id"])
    assert all(q["correct_option"] is None for q in v["questions"])


def test_correct_option_khong_lo_cho_nguoi_khong_co_quyen(the_gioi):
    g = the_gioi
    own = g.c.get(f"/sheets/{g.SA}", headers=g.hA)
    ngoai = g.c.get(f"/sheets/{g.SA}", headers=g.hB)
    assert own.status_code == 200
    assert ngoai.status_code == 404 and "correct_option" not in ngoai.text
    assert g.c.get(f"/sheets/{g.SA}", headers=g.hSv).status_code == 403
    assert g.c.get(f"/sheets/{g.SA}").status_code == 401


def test_node_cau_sai_va_ly_do():
    node = shutil.which("node")
    if not node:
        pytest.skip("không có node")
    for ten in ("cau_sai.test.js", "ly_do_cau.test.js"):
        r = subprocess.run([node, "--test", str(GOC / "tests" / "js" / ten)], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout + r.stderr
