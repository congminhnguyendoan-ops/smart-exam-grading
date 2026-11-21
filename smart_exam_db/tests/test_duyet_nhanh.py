import pytest

from conftest import can_file
from test_backend_api import ROOT, can_anh, dem_results, giai_quyet_het, tai, tao_de, them_sv
from test_dang_nhap import bang_moi, client_on, the_gioi  # noqa: F401  (fixture)

ANH_OK = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia" / "BV07.jpg"
ANH_SBD = "0001_C1"
SBD_0002 = "220007"
HL = {"nhieu_o", "to_nhat"}


def can_xem(client, sid) -> list[int]:
    return [c["question_no"] for c in client.get(f"/sheets/{sid}/review-questions").json()]


def can_xem_hl(client, sid) -> list[int]:
    return [c["question_no"] for c in client.get(f"/sheets/{sid}/review-questions").json() if c["reasons"] and set(c["reasons"]) <= HL]


def hang_loat(client, sid, ds=None, **kw):
    return client.post(f"/sheets/{sid}/questions/confirm-remaining", json={"question_nos": can_xem_hl(client, sid) if ds is None else ds, "confirm": True}, **kw)


def tai_ok(client, eid):
    return tai(client, eid, "BV07", du_lieu=ANH_OK.read_bytes())


def cau_db(conn, sid) -> list[tuple]:
    return [tuple(r.values()) for r in conn.execute(
        "SELECT question_no, selected_options, state::text, needs_review, manually_edited, is_correct, (reviewed_by IS NOT NULL) AS da_duyet "
        "FROM sheet_answers WHERE sheet_id = %s ORDER BY question_no", (sid,)).fetchall()]


@pytest.fixture
def phieu_ok(client, conn_thu):
    can_file(ANH_OK)
    them_sv(conn_thu, SBD_0002)
    eid = tao_de(client)
    r = tai_ok(client, eid)
    assert r.status_code == 201, r.text
    sid = r.json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    assert v["status"] == "needs_review" and not v["sbd"]["can_xem"] and not v["exam_code"]["can_xem"] and len(can_xem(client, sid)) >= 2
    return eid, sid


def test_hang_loat_trung_khit_xac_nhan_tung_cau(client, conn_thu, phieu_ok):
    eid, sid = phieu_ok
    eid2 = tao_de(client)
    sid2 = tai_ok(client, eid2).json()["sheet_id"]
    ds = can_xem(client, sid)
    r = hang_loat(client, sid)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["da_xac_nhan"] == ds and j["con_chon_tay"] == [] and j["status"] == "graded" and j["official"] is not None
    v2 = giai_quyet_het(client, sid2)
    assert cau_db(conn_thu, sid) == cau_db(conn_thu, sid2)
    v = client.get(f"/sheets/{sid}").json()
    assert v["status"] == v2["status"] == "graded" and v["score"]["official"] == v2["score"]["official"]
    assert v["score"]["result_status"] == v2["score"]["result_status"] == "confirmed"
    assert dem_results(conn_thu, sid) == dem_results(conn_thu, sid2) == 1
    assert can_xem(client, sid) == []


def test_ghi_mot_dong_nhat_ky_khong_du_lieu_ca_nhan(client, conn_thu, phieu_ok):
    eid, sid = phieu_ok
    ds = can_xem(client, sid)
    trc = conn_thu.execute("SELECT count(*) AS n FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat'").fetchone()["n"]
    assert hang_loat(client, sid).status_code == 200
    rows = conn_thu.execute("SELECT object_type, object_id, details FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat' ORDER BY log_id").fetchall()
    assert len(rows) == trc + 1
    d = rows[-1]
    assert d["object_type"] == "exam" and d["object_id"] == eid
    assert d["details"]["sheet_id"] == sid and d["details"]["so_cau"] == len(ds) and [c["cau"] for c in d["details"]["cau"]] == ds
    chu = str(d["details"]).lower()
    assert SBD_0002 not in chu and "full_name" not in chu and "sv thử" not in chu and "password" not in chu


def test_thieu_hoac_sai_confirm_422_khong_ghi_gi(client, conn_thu, phieu_ok):
    _, sid = phieu_ok
    truoc = cau_db(conn_thu, sid)
    ds = can_xem(client, sid)
    assert client.post(f"/sheets/{sid}/questions/confirm-remaining", json={"question_nos": ds}).status_code == 422
    assert client.post(f"/sheets/{sid}/questions/confirm-remaining", json={"question_nos": ds, "confirm": False}).status_code == 422
    assert client.post(f"/sheets/{sid}/questions/confirm-remaining", json={"question_nos": [], "confirm": True}).status_code == 422
    assert cau_db(conn_thu, sid) == truoc


def test_danh_sach_lech_409_khong_ghi_gi(client, conn_thu, phieu_ok):
    _, sid = phieu_ok
    ds = can_xem(client, sid)
    truoc = cau_db(conn_thu, sid)
    assert hang_loat(client, sid, ds[:-1]).status_code == 409
    thua = next((n for n in range(1, 41) if n not in ds), 41)
    assert hang_loat(client, sid, ds[1:] + [thua]).status_code == 409
    assert hang_loat(client, sid, ds[:-1] + ds[:1]).status_code == 409
    assert cau_db(conn_thu, sid) == truoc
    assert client.post(f"/sheets/{sid}/questions/{ds[0]}/review", json={"action": "confirm"}).status_code == 200
    assert hang_loat(client, sid, ds).status_code == 409
    assert hang_loat(client, sid).status_code == 200


def test_phieu_da_chot_409(client, phieu_ok):
    _, sid = phieu_ok
    ds = can_xem(client, sid)
    assert hang_loat(client, sid).status_code == 200
    r = hang_loat(client, sid, ds)
    assert r.status_code == 409 and "graded" in r.json()["detail"]


def test_cau_vi_tri_khong_xac_nhan_nhanh(client, conn_thu, phieu_ok):
    _, sid = phieu_ok
    ds = can_xem(client, sid)
    n_tay = ds[0]
    conn_thu.execute("UPDATE sheet_answers SET review_reasons = array_append(review_reasons, 'vi_tri') WHERE sheet_id = %s AND question_no = %s",
                     (sid, n_tay))
    assert hang_loat(client, sid, ds).status_code == 422
    r = hang_loat(client, sid, ds[1:])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["da_xac_nhan"] == ds[1:] and j["con_chon_tay"] == [n_tay] and j["status"] == "needs_review" and j["official"] is None
    assert can_xem(client, sid) == [n_tay]
    assert hang_loat(client, sid, [n_tay]).status_code == 422


def test_khong_bao_gio_dung_sbd_ma_de(client, conn_thu):
    can_anh(ANH_SBD)
    eid = tao_de(client)
    sid = tai(client, eid, ANH_SBD).json()["sheet_id"]
    v0 = client.get(f"/sheets/{sid}").json()
    assert v0["status"] == "needs_review" and v0["sbd"]["can_xem"]
    od0 = conn_thu.execute("SELECT detected_sbd, detected_exam_code, omr_detail FROM answer_sheets WHERE sheet_id = %s", (sid,)).fetchone()
    dg0 = conn_thu.execute("SELECT field, position, corrected_digit FROM ocr_digits WHERE sheet_id = %s ORDER BY field, position", (sid,)).fetchall()
    cho = can_xem(client, sid)
    n_hl = cho[0] if cho else conn_thu.execute("SELECT question_no FROM sheet_answers WHERE sheet_id = %s ORDER BY question_no LIMIT 1", (sid,)).fetchone()["question_no"]
    conn_thu.execute("UPDATE sheet_answers SET needs_review = TRUE, is_correct = NULL, review_reasons = ARRAY['to_nhat'] WHERE sheet_id = %s AND question_no = %s", (sid, n_hl))
    con_tay = [n for n in can_xem(client, sid) if n != n_hl]
    assert can_xem_hl(client, sid) == [n_hl]
    r = hang_loat(client, sid)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "needs_review" and r.json()["official"] is None
    v = client.get(f"/sheets/{sid}").json()
    assert v["sbd"] == v0["sbd"] and v["exam_code"] == v0["exam_code"] and v["student"] == v0["student"]
    assert conn_thu.execute("SELECT detected_sbd, detected_exam_code, omr_detail FROM answer_sheets WHERE sheet_id = %s", (sid,)).fetchone() == od0
    assert conn_thu.execute("SELECT field, position, corrected_digit FROM ocr_digits WHERE sheet_id = %s ORDER BY field, position", (sid,)).fetchall() == dg0
    assert dem_results(conn_thu, sid) == 0
    assert can_xem(client, sid) == con_tay


def test_ky_thi_dong_giong_xac_nhan_tung_cau(client, conn_thu, phieu_ok):
    eid, sid = phieu_ok
    conn_thu.execute("UPDATE exams SET status = 'closed' WHERE exam_id = %s", (eid,))
    ds = can_xem(client, sid)
    assert client.post(f"/sheets/{sid}/questions/{ds[0]}/review", json={"action": "confirm"}).status_code == 200
    assert hang_loat(client, sid).status_code == 200


def test_review_groups_chi_doc(client, conn_thu, phieu_ok):
    eid, sid = phieu_ok
    truoc = cau_db(conn_thu, sid)
    g = client.get(f"/exams/{eid}/review-groups")
    assert g.status_code == 200, g.text
    d = next(x for x in g.json() if x["sheet_id"] == sid)
    assert d["so_cau"] == len(can_xem(client, sid)) and sum(d["ly_do_cau"].values()) >= d["so_cau"]
    assert not d["sbd_can_xem"] and not d["ma_de_can_xem"] and not d["co_vi_tri"] and not d["trung_sbd"]
    assert cau_db(conn_thu, sid) == truoc
    assert client.get("/exams/99999999/review-groups").status_code == 404


def test_phan_quyen_hang_loat_va_nhom(the_gioi, conn_thu):
    can_file(ANH_OK)
    w = the_gioi
    r = w.c.post(f"/exams/{w.EA}/sheets", headers=w.hA, files={"file": ("BV07.jpg", ANH_OK.read_bytes(), "image/jpeg")})
    assert r.status_code == 201, r.text
    sid = r.json()["sheet_id"]
    ds = [c["question_no"] for c in w.c.get(f"/sheets/{sid}/review-questions", headers=w.hA).json()]
    assert ds, "phiếu thử phải có câu cần xem"
    body = {"question_nos": ds, "confirm": True}
    assert w.c.post(f"/sheets/{sid}/questions/confirm-remaining", json=body).status_code == 401
    r = w.c.post(f"/sheets/{sid}/questions/confirm-remaining", headers=w.hB, json=body)
    assert r.status_code == 404 and r.json()["detail"].startswith("Không có ")
    assert w.c.post(f"/sheets/{sid}/questions/confirm-remaining", headers=w.hSv, json=body).status_code == 403
    assert w.c.get(f"/exams/{w.EA}/review-groups", headers=w.hB).status_code == 404
    assert w.c.get(f"/exams/{w.EA}/review-groups", headers=w.hSv).status_code == 403
    assert [c["question_no"] for c in w.c.get(f"/sheets/{sid}/review-questions", headers=w.hA).json()] == ds
    assert w.c.get(f"/exams/{w.EA}/review-groups", headers=w.hA).status_code == 200
    r = w.c.post(f"/sheets/{sid}/questions/confirm-remaining", headers=w.hA, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["da_xac_nhan"] == ds
    nk = conn_thu.execute("SELECT actor_user_id FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat' ORDER BY log_id DESC LIMIT 1").fetchone()
    assert nk["actor_user_id"] == w.idA
