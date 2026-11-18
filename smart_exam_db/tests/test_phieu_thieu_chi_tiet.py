import json
import uuid

import pytest

from backend import demo


def _ky_thi(client) -> tuple[int, int]:
    r = client.post("/exams", json={"exam_title": "Phiếu thiếu chi tiết (pytest)", "subject_code": "W" + uuid.uuid4().hex[:8].upper(), "subject_name": "Môn W2",
                                    "num_questions": 10, "codes": [{"code": "101", "answers": demo.khoa_demo("101", 10)}]})
    assert r.status_code == 201, r.text
    return r.json()["exam_id"], client.get(f"/exams/{r.json()['exam_id']}").json()["codes"][0]


@pytest.mark.parametrize("chi_tiet", [None, {}, {"sbd": {"can_xem": True, "ly_do": ["lech_bubble"], "cot": []}}], ids=["null", "rong", "thieu_ma_de"])
def test_phieu_khong_co_chi_tiet_khong_500(client, conn_thu, chi_tiet):
    eid, ma = _ky_thi(client)
    ma_id = conn_thu.execute("SELECT exam_code_id FROM exam_codes WHERE exam_id = %s", (eid,)).fetchone()["exam_code_id"]
    sid = conn_thu.execute("INSERT INTO answer_sheets (exam_id, image_path, status, detected_sbd, detected_exam_code, exam_code_id, original_filename, omr_detail) "
                           "VALUES (%s, 'w2/khong_co.jpg', 'graded', '220001', '101', %s, 'w2.jpg', %s::jsonb) RETURNING sheet_id",
                           (eid, ma_id, None if chi_tiet is None else json.dumps(chi_tiet))).fetchone()["sheet_id"]
    r = client.get(f"/sheets/{sid}")
    assert r.status_code == 200, r.text
    p = r.json()
    if chi_tiet and "sbd" in chi_tiet:
        assert p["sbd"]["co_chi_tiet"] is True and p["sbd"]["can_xem"] is True and p["sbd"]["reasons"] == ["lech_bubble"]
    else:
        assert p["sbd"] == {"detected": "220001", "can_xem": False, "reasons": [], "columns": [], "co_chi_tiet": False}
    assert p["exam_code"]["co_chi_tiet"] is False and p["exam_code"]["columns"] == [] and p["exam_code"]["detected"] == "101"
    assert p["exam_code"]["matched_code"] == "101"
    assert conn_thu.execute("SELECT omr_detail FROM answer_sheets WHERE sheet_id = %s", (sid,)).fetchone()["omr_detail"] == chi_tiet


def test_phieu_bi_tu_choi_van_khong_co_sbd(client, conn_thu):
    eid, _ = _ky_thi(client)
    sid = conn_thu.execute("INSERT INTO answer_sheets (exam_id, image_path, status, reject_code, original_filename) VALUES (%s, 'w2/x.jpg', 'rejected', 'anh_mo', 'x.jpg') "
                           "RETURNING sheet_id", (eid,)).fetchone()["sheet_id"]
    p = client.get(f"/sheets/{sid}").json()
    assert p["sbd"] is None and p["exam_code"] is None


def test_phieu_mau_so_1_cua_ky_thi_1(client, conn_thu):
    r0 = conn_thu.execute("SELECT omr_detail, detected_sbd, status::text AS s FROM answer_sheets WHERE sheet_id = 1 AND exam_id = 1").fetchone()
    if r0 is None or r0["omr_detail"] is not None:
        pytest.skip("CSDL này không có phiếu mẫu #1 thiếu chi tiết")
    r = client.get("/sheets/1")
    assert r.status_code == 200, r.text
    assert r.json()["sbd"]["detected"] == r0["detected_sbd"] and r.json()["sbd"]["co_chi_tiet"] is False
