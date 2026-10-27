"""Kiểm thử bộ demo bảo vệ [DEMO-BV]: công cụ kiểm kịch bản (không CSDL) và công cụ nạp (CSDL thật trong giao dịch ROLLBACK – không ghi gì)."""
import copy
import sys

import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import kiem_bo_demo as K  # noqa: E402


@pytest.fixture(scope="module")
def du_lieu():
    can_file(K.DAP_AN, K.KICH_BAN)
    return K.doc(K.DAP_AN), K.doc(K.KICH_BAN)


# ------------------------------------------------------------------------------------------------ kiểm kịch bản (không CSDL)
def test_kich_ban_goc_khop(du_lieu):
    loi, bang = K.kiem(*du_lieu)
    assert not loi and len(bang) == 10
    d = {b["phieu"]: b for b in bang}
    assert d["BV01"]["diem"] == 9.5 and d["BV09"]["diem"] == 3.25 and len(d["BV07"]["cau_mo"]) == 40      # BV07 tô nhạt cả tờ
    assert d["BV02"]["cau_nhieu_o"] == [6] and 39 in d["BV03"]["cau_trong"]


def test_luat_dung():
    assert K.dung("A", "A") and K.dung("a", "A") and not K.dung("AC", "A") and not K.dung("-", "A") and not K.dung("B", "A")


@pytest.mark.parametrize("hong,mong", [
    (lambda da, kb: kb[0].__setitem__("so_cau_dung", "37"), "so_cau_dung"),
    (lambda da, kb: kb[0].__setitem__("diem_mong_doi", "9.25"), "diem_mong_doi"),
    (lambda da, kb: kb[0].__setitem__("exam_code", "103"), "không thuộc kỳ thi"),
    (lambda da, kb: kb[0].__setitem__("sbd", "220007"), "SBD 220007"),
    (lambda da, kb: kb[0].__setitem__("q5", "X"), "ký hiệu"),
    (lambda da, kb: kb[0].pop("q40"), "thiếu câu"),
    (lambda da, kb: da[0].__setitem__("answers", da[0]["answers"][:39]), "đủ 40"),
    (lambda da, kb: da[1].__setitem__("class_code", "CNTT-K22B"), "khác tiêu đề"),
])
def test_phat_hien_kich_ban_sai(du_lieu, hong, mong):
    da, kb = copy.deepcopy(du_lieu[0]), copy.deepcopy(du_lieu[1])
    hong(da, kb)
    loi, _ = K.kiem(da, kb)
    assert any(mong in x for x in loi), loi


# ------------------------------------------------------------------------------------------------ nạp (CSDL thật, giao dịch ROLLBACK)
def _dem(conn) -> dict:
    return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in ("exams", "exam_codes", "answer_keys", "exam_students")}


def test_xem_truoc_khong_ghi_va_ap_dung_idempotent(conn_thu):
    import nap_bo_demo as N
    truoc = _dem(conn_thu)
    tom = N.nap(conn_thu, ap_dung=False)
    assert _dem(conn_thu) == truoc and {t["ma"] for t in tom} == {"E1", "E2"}
    lan1 = N.nap(conn_thu, ap_dung=True)
    sau1 = _dem(conn_thu)
    ky_vong = {k: sum(t["insert"][k] for t in tom) for k in tom[0]["insert"]}
    assert {k: sau1[k] - truoc[k] for k in sau1} == ky_vong                                      # đúng số dòng đã báo ở bản xem trước
    lan2 = N.nap(conn_thu, ap_dung=True)
    assert _dem(conn_thu) == sau1 and all(v == 0 for t in lan2 for v in t["insert"].values())  # chạy lại: không đổi
    for t in lan1:
        e = conn_thu.execute("SELECT e.exam_id, e.num_questions, e.max_score, e.pass_score, c.class_code, s.subject_code, u.username "
                             "FROM exams e JOIN classes c USING (class_id) JOIN subjects s USING (subject_id) JOIN users u ON u.user_id = e.created_by "
                             "WHERE e.exam_title = %s", (t["exam_title"],)).fetchall()
        assert len(e) == 1 and e[0]["num_questions"] == 40 and float(e[0]["max_score"]) == 10 and float(e[0]["pass_score"]) == 5
        assert (e[0]["class_code"], e[0]["subject_code"], e[0]["username"]) == ({"E1": ("CNTT-K22A", "IT3080", "gv_an"),
                                                                                "E2": ("CNTT-K22B", "IT4040", "gv_binh")}[t["ma"]])
        sv = [r["student_code"] for r in conn_thu.execute("SELECT s.student_code FROM exam_students x JOIN students s USING (student_id) "
                                                          "WHERE x.exam_id = %s ORDER BY 1", (e[0]["exam_id"],)).fetchall()]
        assert sv == N.DU_THI[t["ma"]] and "220010" not in sv


def test_ban_tap_giong_ban_demo_chi_khac_tieu_de(conn_thu):
    """--ban-tap: 2 kỳ thi [DEMO-BV-TẬP] cùng đáp án / môn / lớp / GV / dự thi; không đụng kỳ thi [DEMO-BV]; chạy lại không trùng."""
    import nap_bo_demo as N
    goc, tap = N.ke_hoach(), N.ke_hoach(ban_tap=True)
    for g, t in zip(goc, tap):
        assert t["exam_title"] == g["exam_title"].replace("[DEMO-BV]", "[DEMO-BV-TẬP]") and "[DEMO-BV-TẬP]" in t["exam_title"]
        assert {k: v for k, v in t.items() if k != "exam_title"} == {k: v for k, v in g.items() if k != "exam_title"}
    demo_truoc = conn_thu.execute("SELECT count(*) AS n FROM exams WHERE exam_title LIKE '%%[DEMO-BV]%%'").fetchone()["n"]
    truoc = _dem(conn_thu)
    lan1 = N.nap(conn_thu, ap_dung=True, ban_tap=True)
    assert {t["ma"] for t in lan1} == {"E1", "E2"} and all("TẬP" in t["exam_title"] for t in lan1)
    sau1 = _dem(conn_thu)
    assert N.nap(conn_thu, ap_dung=True, ban_tap=True) and _dem(conn_thu) == sau1                # chạy lại: không đổi
    assert conn_thu.execute("SELECT count(*) AS n FROM exams WHERE exam_title LIKE '%%[DEMO-BV]%%'").fetchone()["n"] == demo_truoc
    assert sau1["exams"] - truoc["exams"] == sum(t["insert"]["exams"] for t in lan1)              # chưa nạp: 2; đã nạp thật: 0
