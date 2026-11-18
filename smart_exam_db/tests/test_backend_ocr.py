import numpy as np
import pytest

from backend import demo, service
from backend.config import LoiCauHinh
from cv_engine.ocr import CotOCR, KetQuaOCR
from test_backend_api import anh_trang, can_anh, omr_gia, tai, tao_de, them_sv


def ocr_tay(sbd: str, ma_de: str, p: float = 0.99, trong: bool = False):
    def cot(so):
        return [CotOCR(i, "?" if trong else d, [] if trong else [(int(d), p)], 0.0 if trong else p, trong, "", True, not trong, None,
                       np.full((20, 12), 255, np.uint8)) for i, d in enumerate(so)]
    return KetQuaOCR(cot(sbd), cot(ma_de), 1.0)


def dat(monkeypatch, omr_kq, ocr_kq):
    monkeypatch.setattr("backend.service.omr.doc_phieu", lambda kq, layout, mh: omr_kq)
    monkeypatch.setattr("backend.service.ocr_cnn.doc_chu_so", lambda kq, layout, mh: ocr_kq)


def sach(client, eid, monkeypatch, omr_kq, ocr_kq):
    dat(monkeypatch, omr_kq, ocr_kq)
    return client.get(f"/sheets/{tai(client, eid, '0002_C2').json()['sheet_id']}").json()


KEY = demo.khoa_demo("101")
CHON = {q: KEY[q - 1] for q in range(1, 41)}


def test_thieu_mo_hinh_chu_so_thi_khong_khoi_dong(cau_hinh_thu, tmp_path):
    from dataclasses import replace
    with pytest.raises(LoiCauHinh):
        service.nap_mo_hinh(replace(cau_hinh_thu, mo_hinh_ocr=tmp_path / "khong_co.json"))


def test_hai_kenh_khop_va_trong_danh_sach_tu_chot(client, conn_thu, monkeypatch):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    v = sach(client, eid, monkeypatch, omr_gia(chon=CHON), ocr_tay("795125", "101"))
    assert v["status"] == "graded" and not v["sbd"]["can_xem"] and not v["exam_code"]["can_xem"]
    c = v["sbd"]["columns"][0]
    assert c["bubble"] == "7" and c["handwriting"]["chu_so"] == "7" and c["handwriting"]["p"] == pytest.approx(0.99)


def test_hai_kenh_lech_la_can_xem_khong_tu_chot(client, conn_thu, monkeypatch):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    v = sach(client, eid, monkeypatch, omr_gia(chon=CHON), ocr_tay("795126", "101"))
    assert v["status"] == "needs_review" and v["sbd"]["can_xem"] and not v["exam_code"]["can_xem"]
    assert v["score"]["official"] is None
    cot = v["sbd"]["columns"]
    assert [c["can_xem"] for c in cot] == [False] * 5 + [True] and cot[5]["ly_do"] == ["lech_bubble"]
    assert cot[5]["bubble"] == "5" and cot[5]["handwriting"]["chu_so"] == "6"
    assert "lech_bubble" in v["sbd"]["reasons"] and "low_ocr_confidence" in v["review"]["reasons"]
    assert v["review"]["details"]["sbd_ly_do"] == ["lech_bubble"]
    r = client.put(f"/sheets/{v['sheet_id']}/identity", json={"sbd": "795125"}).json()
    assert r["status"] == "graded" and r["student"]["student_code"] == "795125" and r["score"]["result_status"] == "confirmed"
    assert [c["handwriting"]["corrected"] for c in r["sbd"]["columns"]] == list("795125")
    d = conn_thu.execute("SELECT position, predicted_digit, corrected_digit FROM ocr_digits WHERE sheet_id = %s AND field = 'sbd' "
                         "ORDER BY position", (v["sheet_id"],)).fetchall()
    assert [(x["predicted_digit"], x["corrected_digit"]) for x in d] == list(zip("795126", "795125"))


def test_cnn_khong_chac_p_thap_van_can_xem(client, conn_thu, monkeypatch):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    v = sach(client, eid, monkeypatch, omr_gia(chon=CHON), ocr_tay("795125", "101", p=0.4))
    assert v["sbd"]["can_xem"] and v["exam_code"]["can_xem"] and v["status"] == "needs_review"
    assert v["sbd"]["columns"][0]["ly_do"] == ["tin_cay_thap"]


def test_o_viet_tay_trong_q3_chap_nhan_bubble_chi_khi_co_trong_danh_sach(client, conn_thu, monkeypatch):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    ok = sach(client, eid, monkeypatch, omr_gia(chon=CHON), ocr_tay("795125", "101", trong=True))
    assert ok["status"] == "graded" and not ok["sbd"]["can_xem"]
    assert all(c["handwriting"]["o_trong"] for c in ok["sbd"]["columns"])
    eid2 = tao_de(client)
    ngoai = sach(client, eid2, monkeypatch, omr_gia(sbd="999999", chon=CHON), ocr_tay("999999", "101", trong=True))
    assert ngoai["status"] == "needs_review" and ngoai["sbd"]["can_xem"] and "o_trong_ngoai_ds" in ngoai["sbd"]["reasons"]


def test_o_viet_tay_trong_ma_de_ngoai_ky_thi_can_xem(client, conn_thu, monkeypatch):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client, ma_de=("101", "102"))
    v = sach(client, eid, monkeypatch, omr_gia(ma_de="104", chon=CHON), ocr_tay("795125", "104", trong=True))
    assert v["exam_code"]["can_xem"] and "o_trong_ngoai_ds" in v["exam_code"]["reasons"]


def test_anh_that_cnn_that_ocr_digits_va_anh_cat(client, conn_thu):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    v = client.get(f"/sheets/{sid}").json()
    assert len(v["sbd"]["columns"]) == 6 and len(v["exam_code"]["columns"]) == 3
    for t_ in (v["sbd"], v["exam_code"]):
        for c in t_["columns"]:
            assert c["bubble"] is not None and c["handwriting"] is not None and c["handwriting"]["has_crop"]
            assert len(c["handwriting"]["top_k"]) == 3 or c["handwriting"]["chu_so"] == "?"
    n = conn_thu.execute("SELECT count(*) AS n FROM ocr_digits WHERE sheet_id = %s", (sid,)).fetchone()["n"]
    assert n == 9
    for truong, vt in (("sbd", 0), ("sbd", 5), ("exam_code", 2)):
        r = client.get(f"/sheets/{sid}/digits/{truong}/{vt}/image")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert client.get(f"/sheets/{sid}/digits/sbd/8/image").status_code == 404
    assert client.get(f"/sheets/{sid}/digits/khac/0/image").status_code == 422
    m = conn_thu.execute("SELECT m.model_type::text AS t FROM answer_sheets a JOIN ml_models m ON m.model_id = a.ocr_model_id "
                         "WHERE a.sheet_id = %s", (sid,)).fetchone()
    assert m["t"] == "ocr_digit"
    assert client.get("/health").json()["ocr_model"].startswith("ocr_cnn-")


def test_anh_bi_tu_choi_khong_co_ocr_digits(client, conn_thu):
    eid = tao_de(client)
    j = tai(client, eid, "trang", anh_trang()).json()
    assert j["status"] == "rejected"
    assert conn_thu.execute("SELECT count(*) AS n FROM ocr_digits WHERE sheet_id = %s", (j["sheet_id"],)).fetchone()["n"] == 0
    assert client.get(f"/sheets/{j['sheet_id']}/digits/sbd/0/image").status_code == 404
