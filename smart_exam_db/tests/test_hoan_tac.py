import inspect
import subprocess
from pathlib import Path

import pytest

from backend import service
from test_backend_api import anh_trang, tai, tao_de
from test_dang_nhap import bang_moi, client_on, the_gioi  # noqa: F401  (fixture)
from test_tu_cham_nhieu_o import Q, diem_cau, duyet, tai_phieu

M = 12


def dem_results(conn, sid):
    return conn.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s AND status <> 'void'", (sid,)).fetchone()["n"]


def undo(client, sid, n):
    return client.post(f"/sheets/{sid}/questions/{n}/review/undo")


def xac_nhan(client, sid, n=M):
    return client.post(f"/sheets/{sid}/questions/{n}/review", json={"action": "confirm"})


def nhat_ky(conn, sid):
    return conn.execute("SELECT action, old_status::text AS os, new_status::text AS ns, new_score, reason FROM score_audit_logs l "
                        "JOIN results r USING (result_id) WHERE r.sheet_id = %s ORDER BY audit_id", (sid,)).fetchall()


def test_confirm_undo_confirm_lai_diem_dung(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(), mo=(M,))
    sid = t["sheet_id"]
    assert t["status"] == "needs_review"
    v = xac_nhan(client, sid).json()
    assert v["status"] == "graded" and v["score"]["official"] == pytest.approx(10.0)
    assert diem_cau(v, M)["da_xem"] is True
    r = undo(client, sid, M)
    assert r.status_code == 200, r.text
    v = r.json()
    q = diem_cau(v, M)
    assert v["status"] == "needs_review" and q["needs_review"] is True and q["da_xem"] is False and q["is_correct"] is None
    assert q["manually_edited"] is False and q["selected_options"] == q["omr_selected_options"]
    assert v["score"]["official"] is None and v["score"]["pending_questions"] == 1
    assert dem_results(conn_thu, sid) == 0
    v = xac_nhan(client, sid).json()
    assert v["status"] == "graded" and v["score"]["official"] == pytest.approx(10.0)
    assert dem_results(conn_thu, sid) == 1
    assert conn_thu.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s", (sid,)).fetchone()["n"] == 1


def test_set_roi_undo_ve_may_doc(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch, nhieu=(), mo=(M,))
    sid = t["sheet_id"]
    may = key[M - 1]
    khac = next(o for o in "ABCD" if o != may)
    v = client.post(f"/sheets/{sid}/questions/{M}/review", json={"action": "set", "selected_options": khac}).json()
    q = diem_cau(v, M)
    assert q["selected_options"] == khac and q["manually_edited"] is True and q["is_correct"] is False
    q = diem_cau(undo(client, sid, M).json(), M)
    assert q["selected_options"] == may and q["manually_edited"] is False and q["needs_review"] is True and q["da_xem"] is False
    row = conn_thu.execute("SELECT reviewed_by, reviewed_at, state::text AS s, omr_state::text AS o FROM sheet_answers "
                           "WHERE sheet_id = %s AND question_no = %s", (sid, M)).fetchone()
    assert row["reviewed_by"] is None and row["reviewed_at"] is None and row["s"] == row["o"]


def test_phieu_graded_loai_cho_undo_void_audit_roi_chot_lai(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(), mo=(M,))
    sid = t["sheet_id"]
    xac_nhan(client, sid)
    undo(client, sid, M)
    res = conn_thu.execute("SELECT status::text AS s FROM results WHERE sheet_id = %s", (sid,)).fetchall()
    assert [x["s"] for x in res] == ["void"]
    assert conn_thu.execute("SELECT status::text AS s FROM answer_sheets WHERE sheet_id = %s", (sid,)).fetchone()["s"] == "needs_review"
    log = nhat_ky(conn_thu, sid)
    assert [x["action"] for x in log] == ["INSERT", "UPDATE"] and log[1]["ns"] == "void"
    assert log[1]["reason"] == f"Giáo viên hoàn tác xác nhận câu {M}"
    pend = conn_thu.execute("SELECT count(*) AS n FROM review_queue WHERE sheet_id = %s AND status = 'pending'", (sid,)).fetchone()["n"]
    daxong = conn_thu.execute("SELECT count(*) AS n FROM review_queue WHERE sheet_id = %s AND status = 'resolved'", (sid,)).fetchone()["n"]
    assert pend == 1 and daxong == 1
    v = xac_nhan(client, sid).json()
    assert v["status"] == "graded" and v["score"]["official"] == pytest.approx(10.0)
    assert dem_results(conn_thu, sid) == 1
    assert conn_thu.execute("SELECT count(*) AS n FROM results WHERE sheet_id = %s", (sid,)).fetchone()["n"] == 1


def test_tu_cham_giu_roi_undo_diem_khong_doi(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    duyet(client, sid, action="keep")
    truoc = conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs").fetchone()["n"]
    r = undo(client, sid, Q)
    assert r.status_code == 200, r.text
    v = r.json()
    q = diem_cau(v)
    assert v["status"] == "graded" and q["needs_review"] is False and q["tu_cham_can_xem"] is True and q["da_xem"] is False
    assert q["state"] == "multiple" and q["selected_options"] == "AB" and q["is_correct"] is False
    assert v["score"]["official"] == pytest.approx(9.75) and v["score"]["result_status"] == "auto"
    assert conn_thu.execute("SELECT count(*) AS n FROM review_queue WHERE sheet_id = %s", (sid,)).fetchone()["n"] == 0
    assert conn_thu.execute("SELECT count(*) AS n FROM score_audit_logs").fetchone()["n"] == truoc


def test_tu_cham_chon_lai_roi_undo_diem_ve_cu_va_status_auto(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch)
    sid = t["sheet_id"]
    duyet(client, sid, action="set", selected_options=key[Q - 1])
    assert dem_results(conn_thu, sid) == 1
    v = undo(client, sid, Q).json()
    q = diem_cau(v)
    assert v["score"]["official"] == pytest.approx(9.75) and v["score"]["result_status"] == "auto" and v["score"]["num_correct"] == 39
    assert q["selected_options"] == "AB" and q["manually_edited"] is False and q["is_correct"] is False and q["tu_cham_can_xem"] is True
    log = nhat_ky(conn_thu, sid)
    assert [x["action"] for x in log] == ["INSERT", "UPDATE", "UPDATE"]
    assert log[2]["reason"] == f"Giáo viên hoàn tác xem lại câu {Q}" and (log[2]["os"], log[2]["ns"]) == ("manual_edited", "auto")
    assert float(log[2]["new_score"]) == pytest.approx(9.75)


def test_tu_cham_undo_giu_manual_edited_neu_con_cau_sua_tay(client, conn_thu, monkeypatch):
    _, t, key = tai_phieu(client, conn_thu, monkeypatch, nhieu=(3, Q))
    sid = t["sheet_id"]
    duyet(client, sid, n=3, action="set", selected_options=key[2])
    duyet(client, sid, n=Q, action="set", selected_options=key[Q - 1])
    v = undo(client, sid, Q).json()
    assert v["score"]["result_status"] == "manual_edited" and v["score"]["official"] == pytest.approx(9.75)


def test_phan_quyen_undo(the_gioi):
    w = the_gioi
    url = f"/sheets/{w.SA}/questions/1/review/undo"
    assert w.c.post(url).status_code == 401
    assert w.c.post(url, headers=w.hSv).status_code == 403
    r = w.c.post(url, headers=w.hB)
    assert r.status_code == 404 and r.json()["detail"].startswith("Không có ")
    r = w.c.post(url, headers=w.hA)
    assert r.status_code == 409 and "rejected" in r.json()["detail"]


def test_cau_chua_xem_409_va_phieu_rejected(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(), mo=(M,))
    sid = t["sheet_id"]
    assert undo(client, sid, M).status_code == 409
    assert undo(client, sid, 1).status_code == 409
    assert undo(client, 99999999, 1).status_code == 404
    eid = tao_de(client)
    rej = tai(client, eid, "trang", anh_trang()).json()["sheet_id"]
    r = undo(client, rej, 1)
    assert r.status_code == 409 and "rejected" in r.json()["detail"]


def test_hai_undo_lien_tiep_mot_thanh_cong_va_co_khoa_hang(client, conn_thu, monkeypatch):
    _, t, _ = tai_phieu(client, conn_thu, monkeypatch, nhieu=(), mo=(M,))
    sid = t["sheet_id"]
    xac_nhan(client, sid)
    assert [undo(client, sid, M).status_code, undo(client, sid, M).status_code] == [200, 409]
    assert inspect.getsource(service.hoan_tac_cau).count("FOR UPDATE") == 3


def test_ma_hoan_tac_khong_chu_thich_va_ui_co_nut():
    nguon = inspect.getsource(service.hoan_tac_cau)
    assert "#" not in nguon and '"""' not in nguon
    goc = Path(__file__).resolve().parents[1] / "frontend"
    assert "hoan_tac.js" in (goc / "index.html").read_text(encoding="utf-8")
    app = (goc / "app.js").read_text(encoding="utf-8")
    assert "review/undo" in app and "HoanTac.nutHtml" in app


def test_node_hoan_tac():
    goc = Path(__file__).resolve().parents[1]
    kq = subprocess.run(["node", "--test", "tests/js/hoan_tac.test.js"], cwd=goc, capture_output=True, text=True, encoding="utf-8")
    assert kq.returncode == 0, kq.stdout + kq.stderr
