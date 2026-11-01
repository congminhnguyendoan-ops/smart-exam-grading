"""Lệnh AG (01/11/2026): kịch bản thử giấy thật + phần so sánh của công cụ chấm – KHÔNG cần ảnh, KHÔNG cần CSDL.
Tiêu chí: docs/tieu_chi_thu_giay_that.md (commit 18fd340)."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ag_cham_that as C  # noqa: E402
import ag_tao_kich_ban as K  # noqa: E402


@pytest.fixture(scope="module")
def kb():
    return K.lap_kich_ban()


# ------------------------------------------------------------------------------------------------ kịch bản
def test_kich_ban_tat_dinh_va_dat_rang_buoc(kb):
    assert K.lap_kich_ban() == kb                                                   # cùng hạt giống -> cùng kịch bản
    assert K.lap_kich_ban(K.HAT_GIONG + 1) != kb
    assert K.kiem_kich_ban(kb) == []
    assert list(kb["to"]) == [f"T{i:02d}" for i in range(1, 11)]
    dem = {}
    for ma, t in kb["to"].items():
        assert len(t["cau"]) == 40 and t["sbd"] in K.DS_SBD and t["ma_de"] in K.DS_MA
        dac = [c["loai"] for c in t["cau"].values() if c["loai"] != "binh_thuong"]
        assert 8 <= len(dac) <= 10
        assert ("te" in dac) == (t["but"] == "chi")                                 # "te" CHỈ ở tờ bút chì
        for l in dac:
            dem[l] = dem.get(l, 0) + 1
    assert all(dem[l] >= 6 for l in K.LOAI_DAC_BIET), dem
    assert [t["but"] for t in kb["to"].values()] == ["bi"] * 8 + ["chi"] * 2
    assert {m for m, t in kb["to"].items() if t["thieu_bubble"]} == {"T03", "T06", "T10"}


def test_quy_uoc_chap_nhan_va_huong_dan(kb):
    for t in kb["to"].values():
        for n, c in t["cau"].items():
            if c["loai"] == "hai_o":
                assert c["chap_nhan"] == ["can_xem"] and len(c["dap_an"]) == 2 and "2 ô" in c["huong_dan"]
            else:
                assert c["chap_nhan"] == ["doc_dung", "can_xem"]
            if c["loai"] == "te":
                assert c["to_truoc"] != c["dap_an"] and "TẨY" in c["huong_dan"]
            if c["loai"] == "vet":
                assert c["cham"] != c["dap_an"] and "chấm" in c["huong_dan"]
            if c["loai"] == "bo_trong":
                assert c["dap_an"] == "" and "TRỐNG" in c["huong_dan"]
            assert c["huong_dan"].startswith(f"Câu {n}:")


def test_kiem_kich_ban_bat_loi(kb):
    x = copy.deepcopy(kb)
    n = next(k for k, c in x["to"]["T01"]["cau"].items() if c["loai"] == "binh_thuong")
    x["to"]["T01"]["cau"][n] = {"loai": "te", "dap_an": "A", "to_truoc": "B", "chap_nhan": ["doc_dung", "can_xem"], "huong_dan": ""}
    assert any("'te' trên tờ bút bi" in e for e in K.kiem_kich_ban(x))
    y = copy.deepcopy(kb)
    for t in y["to"].values():
        t["thieu_bubble"] = []
    assert any("thiếu bubble" in e for e in K.kiem_kich_ban(y))


# ------------------------------------------------------------------------------------------------ so sánh
@pytest.mark.parametrize("dap_an,doc,cx,mong", [
    ("B", "B", False, "doc_dung"), ("B", "C", False, "sai_am_tham"), ("B", "", False, "sai_am_tham"), ("B", "C", True, "can_xem"),
    ("", "", False, "doc_dung"), ("", "A", False, "sai_am_tham"), ("BC", "CB", False, "doc_dung"), ("BC", "B", False, "sai_am_tham"),
    ("BC", "BC", True, "can_xem")])
def test_phan_loai_cau(dap_an, doc, cx, mong):
    assert C.phan_loai_cau(dap_an, doc, cx) == mong


def test_phan_loai_cot():
    assert C.phan_loai_cot("3", "3", False) == "doc_dung"
    assert C.phan_loai_cot("3", "8", False) == "sai_am_tham"
    assert C.phan_loai_cot("?", "8", False) == "sai_am_tham"                         # thiếu bubble mà máy "thấy" một chữ số, không cờ
    assert C.phan_loai_cot("?", "?", True) == "can_xem"


def rec_dung(ma: str, to: dict, cx=(), sai=None, truong=None) -> dict:
    """Bản ghi đọc ảnh GIẢ (không ảnh): đọc đúng kịch bản; cx = câu gắn cần xem; sai = {câu: ô đọc}; truong = ghi đè trường."""
    cau = []
    for n, c in to["cau"].items():
        doc = (sai or {}).get(int(n), c["dap_an"])
        cau.append({"n": int(n), "doc_o": doc, "doc_tt": "nhieu" if len(doc) > 1 else ("trong" if not doc else "ro"),
                    "cx": int(n) in cx or c["loai"] == "hai_o", "ly_do": ["nhieu_o"] if c["loai"] == "hai_o" else [], "P": None})
    tb = {(x["truong"], x["vi_tri"]) for x in to["thieu_bubble"]}
    cot, tr = [], {}
    for ten in ("sbd", "ma_de"):
        co_thieu = False
        for i, d in enumerate(to[ten]):
            thieu = (ten, i + 1) in tb
            co_thieu |= thieu
            cot.append({"truong": ten, "i": i, "b": "?" if thieu else d, "cnn": d, "cnn_p": 0.99, "chac": not thieu,
                        "ly_do": ["thieu_bubble"] if thieu else []})
        tr[ten] = {"gia_tri": to[ten], "chac": not co_thieu, "ly_do": ["thieu_bubble"] if co_thieu else [], "trong_ds": True}
    tr.update(truong or {})
    return {"anh": f"{ma}.jpg", "to": ma, "dieu_kien": "thuong", "cau": cau, "cot": cot, "truong": tr}


def test_doc_dung_kich_ban_dat_c1_h3(kb):
    dg = [C.danh_gia_anh(rec_dung(m, t), t) for m, t in kb["to"].items()]
    k = C.tong_hop(dg, kb, [], [])
    assert k["C1"] == "ĐẠT" and k["H3"]["ket_luan"] == "ĐẠT" and k["H3"]["H3b_so_truong_kiem"] == 3
    assert k["theo_loai"]["hai_o"]["can_xem"] == k["theo_loai"]["hai_o"]["n"] and k["theo_loai"]["binh_thuong"]["sai_am_tham"] == 0
    assert k["to_chua_kiem"] == []


def test_bat_sai_am_tham_cau_va_hai_o_tu_chot(kb):
    t = kb["to"]["T01"]
    n = int(next(k for k, c in t["cau"].items() if c["loai"] == "binh_thuong"))
    sai = next(o for o in "ABCD" if o != t["cau"][str(n)]["dap_an"])
    r = rec_dung("T01", t, sai={n: sai})
    h = int(next(k for k, c in t["cau"].items() if c["loai"] == "hai_o"))
    for c in r["cau"]:
        if c["n"] == h:                                                             # máy TỰ CHỐT một ô cho câu tô 2 ô
            c.update(doc_o=t["cau"][str(h)]["dap_an"][0], cx=False, ly_do=[])
    k = C.tong_hop([C.danh_gia_anh(r, t)], kb, [], [])
    assert k["C1"] == "KHÔNG ĐẠT"
    assert sorted((x["n"], x["loai"]) for x in k["sai_am_tham"]["cau"]) == sorted([(n, "binh_thuong"), (h, "hai_o")])
    assert set(k["to_chua_kiem"]) == set(kb["to"]) - {"T01"}


def test_h3a_truong_nhan_sai_va_h3b_thieu_bubble_bi_nhan(kb):
    t3 = kb["to"]["T03"]                                                            # T03: SBD cột 2 thiếu bubble
    r = rec_dung("T03", t3, truong={"sbd": {"gia_tri": t3["sbd"], "chac": True, "ly_do": [], "trong_ds": True}})
    k = C.tong_hop([C.danh_gia_anh(r, t3)], kb, [], [])
    assert k["H3"]["H3b_vi_pham"] == 1 and k["H3"]["ket_luan"] == "KHÔNG ĐẠT"
    t1 = kb["to"]["T01"]
    sai = "9" + t1["sbd"][1:] if t1["sbd"][0] != "9" else "8" + t1["sbd"][1:]
    r = rec_dung("T01", t1, truong={"sbd": {"gia_tri": sai, "chac": True, "ly_do": [], "trong_ds": True}})
    k = C.tong_hop([C.danh_gia_anh(r, t1)], kb, [], [])
    assert k["H3"]["H3a_truong_nhan_ma_sai"] == 1 and k["C1"] == "KHÔNG ĐẠT"
    r = rec_dung("T01", t1, truong={"sbd": {"gia_tri": sai, "chac": True, "ly_do": [], "trong_ds": False}})   # ngoài danh sách -> backend giữ lại
    assert C.tong_hop([C.danh_gia_anh(r, t1)], kb, [], [])["H3"]["H3a_truong_nhan_ma_sai"] == 0


def test_anh_bi_tu_choi_va_to_chua_kiem_duoc_bao(kb, tmp_path):
    for ten in ("T01.jpg", "t02_KHO.JPG", "T03.heic", "anh_la.jpg", "T04.txt", "T1.jpg"):
        (tmp_path / ten).write_bytes(b"x")
    anh, bo = C.liet_ke(tmp_path)
    assert sorted((p.name, m, d) for p, m, d in anh) == sorted([("T01.jpg", "T01", "thuong"), ("T03.heic", "T03", "thuong"), ("t02_KHO.JPG", "T02", "kho")])
    assert sorted(bo) == ["T04.txt", "T1.jpg", "anh_la.jpg"]
    k = C.tong_hop([], kb, [{"anh": "T05.jpg", "to": "T05", "ly_do": "thieu_marker", "thong_bao": ""}], bo)
    assert k["C1"].startswith("chưa kiểm được") and k["H3"]["ket_luan"] == "chưa kết luận được" and "T05" in k["to_chua_kiem"]
    md = C.bao_cao_md(dict(k, thu_muc="x", ghi_chu="", chi_tiet_anh=[]))
    assert "T05.jpg (tờ T05): **bị tiền xử lý từ chối** – `thieu_marker`" in md and "**Tờ T05: chưa kiểm được**" in md and "anh_la.jpg: bỏ qua" in md
