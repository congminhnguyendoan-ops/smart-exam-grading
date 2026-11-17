"""Lệnh AF2 (01/11/2026): xác nhận hàng loạt CHỈ cho câu "nhiều ô" (nhieu_o) / "tô nhạt cả tờ" (to_nhat) – MÁY CHỦ quyết.
Lô có BẤT KỲ câu nào khác (mờ, vết nhỏ, lưng chừng, vị trí, câu không còn cờ) -> từ chối CẢ LÔ, KHÔNG ghi gì. CSDL thật trong giao dịch ROLLBACK."""
import pytest

from backend.duyet_nhanh import LY_DO_HANG_LOAT, hop_le_hang_loat
from conftest import can_file
from test_backend_api import ROOT, can_anh, dem_results, tai, tao_de, them_sv
from test_dang_nhap import bang_moi, client_on, the_gioi  # noqa: F401  (fixture)

BV07 = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia" / "BV07.jpg"      # 40 câu cần xem chỉ vì to_nhat
ANH_TRON = "0001_C1"                                                       # dev: 7 câu nhieu_o + 12 câu o_mo
ANH_MO = "0002_C2"                                                         # dev: chỉ câu o_mo


def rq(client, sid, **kw) -> list[dict]:
    return client.get(f"/sheets/{sid}/review-questions", **kw).json()


def hl(client, sid, ds, **kw):
    return client.post(f"/sheets/{sid}/questions/confirm-remaining", json={"question_nos": ds, "confirm": True}, **kw)


def chup(conn, sid) -> tuple:
    """Ảnh chụp mọi thứ có thể bị ghi: câu, trạng thái phiếu, điểm, nhật ký."""
    cau = conn.execute("SELECT question_no, selected_options, state::text, needs_review, manually_edited, reviewed_by FROM sheet_answers "
                       "WHERE sheet_id = %s ORDER BY question_no", (sid,)).fetchall()
    sh = conn.execute("SELECT status::text, raw_score FROM answer_sheets WHERE sheet_id = %s", (sid,)).fetchone()
    nk = conn.execute("SELECT count(*) AS n FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat'").fetchone()["n"]
    return [tuple(r.values()) for r in cau], tuple(sh.values()), dem_results(conn, sid), nk


@pytest.fixture
def phieu_tron(client):
    can_anh(ANH_TRON)
    sid = tai(client, tao_de(client), ANH_TRON).json()["sheet_id"]
    q = rq(client, sid)
    nhieu = [c["question_no"] for c in q if c["reasons"] == ["nhieu_o"]]
    mo = [c["question_no"] for c in q if "o_mo" in c["reasons"]]
    assert nhieu and mo, q
    return sid, nhieu, mo


# ------------------------------------------------------------------------------------------------ luật (thuần)
def test_hop_le_chi_nhieu_o_va_to_nhat():
    assert LY_DO_HANG_LOAT == {"nhieu_o", "to_nhat"}
    for ly in (["nhieu_o"], ["to_nhat"], ["nhieu_o", "to_nhat"]):
        assert hop_le_hang_loat(ly), ly
    for ly in ([], None, ["o_mo"], ["vet_nho"], ["tin_cay_thap"], ["vi_tri"], ["nhieu_o", "o_mo"], ["to_nhat", "vet_nho"],
               ["nhieu_o", "tin_cay_thap"], ["vi_tri", "nhieu_o"], ["o_mo", "to_nhat"]):
        assert not hop_le_hang_loat(ly), ly


# ------------------------------------------------------------------------------------------------ từ chối cả lô, không ghi gì
def test_lo_co_cau_mo_bi_tu_choi_toan_bo(client, conn_thu, phieu_tron):
    sid, nhieu, mo = phieu_tron
    truoc = chup(conn_thu, sid)
    r = hl(client, sid, nhieu + mo[:1])
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert "Từ chối cả lô: 1 câu" in d and str(mo[0]) in d and "nhiều ô" in d and "Chưa ghi câu nào" in d
    r = hl(client, sid, nhieu + mo)
    assert r.status_code == 422 and f"{len(mo)} câu" in r.json()["detail"]
    assert hl(client, sid, mo).status_code == 422                                              # chỉ câu mờ
    assert chup(conn_thu, sid) == truoc                                                        # KHÔNG ghi câu nào, không nhật ký


@pytest.mark.parametrize("ly", [["vet_nho"], ["tin_cay_thap"], ["vi_tri"], ["nhieu_o", "vet_nho"], ["to_nhat", "o_mo"]])
def test_lo_co_cau_vet_lung_chung_vi_tri_bi_tu_choi(client, conn_thu, phieu_tron, ly):
    sid, nhieu, _ = phieu_tron
    n = nhieu[0]                                                                               # giả lập lý do khác trên một câu "nhiều ô"
    conn_thu.execute("UPDATE sheet_answers SET review_reasons = %s WHERE sheet_id = %s AND question_no = %s", (ly, sid, n))
    truoc = chup(conn_thu, sid)
    assert hl(client, sid, nhieu).status_code == 422
    assert chup(conn_thu, sid) == truoc
    assert hl(client, sid, nhieu[1:]).status_code == (200 if len(nhieu) > 1 else 422)          # bỏ câu đó ra thì lô hợp lệ


def test_cau_khong_con_co_bi_tu_choi_khong_ghi_gi(client, conn_thu, phieu_tron):
    sid, nhieu, _ = phieu_tron
    assert client.post(f"/sheets/{sid}/questions/{nhieu[0]}/review", json={"action": "confirm"}).status_code == 200
    truoc = chup(conn_thu, sid)
    assert hl(client, sid, nhieu).status_code == 409                                           # nhieu[0] không còn cờ -> danh sách cũ
    khong_co = next(c for c in range(1, 41) if c not in [x["question_no"] for x in rq(client, sid)])
    assert hl(client, sid, nhieu[1:] + [khong_co]).status_code == 409
    assert chup(conn_thu, sid) == truoc


def test_phieu_chi_co_cau_mo_khong_hang_loat_duoc(client, conn_thu):
    can_anh(ANH_MO)
    sid = tai(client, tao_de(client), ANH_MO).json()["sheet_id"]
    q = rq(client, sid)
    assert q and all("o_mo" in c["reasons"] for c in q)
    truoc = chup(conn_thu, sid)
    assert hl(client, sid, [c["question_no"] for c in q]).status_code == 422
    assert chup(conn_thu, sid) == truoc


# ------------------------------------------------------------------------------------------------ chấp nhận
def test_lo_chi_nhieu_o_duoc_nhan_cau_mo_o_lai(client, conn_thu, phieu_tron):
    sid, nhieu, mo = phieu_tron
    r = hl(client, sid, nhieu)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["da_xac_nhan"] == nhieu and j["con_chon_tay"] == mo and j["status"] == "needs_review" and j["official"] is None
    con = rq(client, sid)
    assert [c["question_no"] for c in con] == mo                                               # câu mờ vẫn chờ giáo viên
    for n in nhieu:
        a = conn_thu.execute("SELECT selected_options, omr_selected_options, needs_review, manually_edited FROM sheet_answers "
                             "WHERE sheet_id = %s AND question_no = %s", (sid, n)).fetchone()
        assert a["selected_options"] == (a["omr_selected_options"] or "") and len(a["selected_options"]) >= 2 and not a["needs_review"] and not a["manually_edited"]
    nk = conn_thu.execute("SELECT details FROM admin_audit_log WHERE action = 'xac_nhan_hang_loat' ORDER BY log_id DESC LIMIT 1").fetchone()["details"]
    assert nk["so_cau"] == len(nhieu) and all(c["ly_do"] == ["nhieu_o"] for c in nk["cau"])


def test_lo_chi_to_nhat_chot_diem(client, conn_thu):
    can_file(BV07)
    them_sv(conn_thu, "220007")
    sid = tai(client, tao_de(client), "BV07", du_lieu=BV07.read_bytes()).json()["sheet_id"]
    q = rq(client, sid)
    assert len(q) == 40 and all(c["reasons"] == ["to_nhat"] for c in q)
    r = hl(client, sid, [c["question_no"] for c in q])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "graded" and r.json()["official"] is not None and r.json()["con_chon_tay"] == []
    assert dem_results(conn_thu, sid) == 1


# ------------------------------------------------------------------------------------------------ phân quyền + đã chốt: như cũ
def test_phan_quyen_va_da_chot_nhu_cu(the_gioi, conn_thu):
    can_file(BV07)
    w = the_gioi
    sid = w.c.post(f"/exams/{w.EA}/sheets", headers=w.hA, files={"file": ("BV07.jpg", BV07.read_bytes(), "image/jpeg")}).json()["sheet_id"]
    ds = [c["question_no"] for c in rq(w.c, sid, headers=w.hA)]
    assert ds
    truoc = chup(conn_thu, sid)
    assert hl(w.c, sid, ds).status_code == 401
    r = hl(w.c, sid, ds, headers=w.hB)
    assert r.status_code == 404 and r.json()["detail"].startswith("Không có ")
    assert hl(w.c, sid, ds, headers=w.hSv).status_code == 403
    assert chup(conn_thu, sid) == truoc
    assert hl(w.c, sid, ds, headers=w.hA).status_code == 200
    conn_thu.execute("UPDATE answer_sheets SET status = 'graded' WHERE sheet_id = %s", (sid,))  # giả lập phiếu đã chốt
    r = hl(w.c, sid, ds, headers=w.hA)
    assert r.status_code == 409 and "graded" in r.json()["detail"]
