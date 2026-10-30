"""Lệnh U: tools/kiem_truoc_demo.py – mục KHÔNG ĐẠT khi giả lập thiếu tệp / SHA lệch, mã thoát, và các kiểm CSDL KHÔNG ghi gì (kể cả phép đo tốc độ)."""
import json
import sys

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import kiem_truoc_demo as K  # noqa: E402


def test_thieu_tep_demo_la_khong_dat(tmp_path):
    co = tmp_path / "phieu_demo_in.pdf"
    co.write_bytes(b"%PDF")
    muc = K.kiem_tep_demo([co, tmp_path / "BV03.jpg"], tmp_path)
    assert [m.ket_qua for m in muc] == [K.KHONG_DAT] and "BV03.jpg" in muc[0].chi_tiet
    assert K.ma_thoat(muc) == 1
    assert K.kiem_tep_demo([co], tmp_path)[0].ket_qua == K.DAT


def test_tep_demo_that_cua_du_an_du():
    assert K.kiem_tep_demo()[0].ket_qua == K.DAT, K.kiem_tep_demo()[0].chi_tiet


def test_mo_hinh_thieu_hoac_sai_sha_la_khong_dat(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "models" / "b.json").write_text("{}", encoding="utf-8")
    sdk = tmp_path / "so.json"
    sdk.write_text(json.dumps({"sha256": {"models/a.json": K.sha_hoa(tmp_path / "models" / "a.json"), "models/b.json": "0" * 64}}), encoding="utf-8")
    muc = K.kiem_mo_hinh(tmp_path, ["models/a.json", "models/b.json", "models/thieu.json"], sdk)
    assert [m.ket_qua for m in muc[:3]] == [K.DAT, K.KHONG_DAT, K.KHONG_DAT]
    assert "KHÁC" in muc[1].chi_tiet and "THIẾU" in muc[2].chi_tiet


def test_ma_thoat_chi_khac_0_khi_co_khong_dat():
    M = K.Muc
    assert K.ma_thoat([M("a", "b", K.DAT), M("a", "c", K.CANH_BAO), M("a", "d", K.KHONG_KIEM)]) == 0
    assert K.ma_thoat([M("a", "b", K.DAT), M("a", "c", K.KHONG_DAT)]) == 1
    bang = K.in_bang([M("a", "b", K.DAT), M("a", "c", K.KHONG_DAT, "thiếu")])
    assert "KHÔNG ĐẠT: 1" in bang and "CÓ MỤC KHÔNG ĐẠT" in bang


def test_kiem_csdl_chay_trong_giao_dich_chi_doc(conn_thu):
    """read_only: nếu một kiểm nào đó ghi (vd migrate.da_ap tạo bảng) thì PostgreSQL ném lỗi – test này bắt lỗi đó."""
    conn_thu.read_only = True
    muc = K.kiem_csdl(conn_thu) + K.kiem_tai_khoan(conn_thu)
    assert muc[0].ket_qua == K.DAT and any("Migration" in m.ten for m in muc)


def test_do_toc_do_khong_de_lai_dong_nao(csdl_san_sang):
    from backend.db import ket_noi
    bang = ("exams", "exam_codes", "answer_keys", "answer_sheets", "sheet_answers", "ocr_digits", "review_queue", "results")
    dem = lambda c: {b: c.execute(f"SELECT count(*) AS n FROM {b}").fetchone()["n"] for b in bang}   # noqa: E731
    with ket_noi() as c:
        truoc = dem(c)
    muc = K.kiem_toc_do()
    with ket_noi() as c:
        assert dem(c) == truoc
    assert muc[0].ket_qua in (K.DAT, K.CANH_BAO, K.KHONG_KIEM), muc[0].chi_tiet
