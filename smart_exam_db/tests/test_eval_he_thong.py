import ast
import json
import subprocess
import sys

import pytest

from conftest import DATA, ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import eval_he_thong as E  # noqa: E402


def test_doc_lap_khong_import_luat_cham():
    cay = ast.parse((ROOT / "tools" / "eval_he_thong.py").read_text(encoding="utf-8"))
    cap_tren = [n for n in cay.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    mod_tren = {n.module for n in cap_tren if isinstance(n, ast.ImportFrom)} | {a.name for n in cap_tren if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and (m.startswith("cv_engine.omr") or m.startswith("cv_engine.ocr") or m.startswith("backend")) for m in mod_tren), mod_tren
    moi = {n.module for n in ast.walk(cay) if isinstance(n, ast.ImportFrom)}
    assert not {"cv_engine.omr", "cv_engine.ocr", "backend.service", "backend.grading", "cv_engine"} & moi
    dung = {n.attr for n in ast.walk(cay) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in ("omr", "ocr", "grading", "service")}
    assert not dung
    ham = next(n for n in cay.body if isinstance(n, ast.FunctionDef) and n.name == "nhat_quan_tuan4")
    assert any(isinstance(n, ast.ImportFrom) and n.module == "cv_engine.preprocessing" for n in ast.walk(ham))
    assert "cv_engine.preprocessing" not in mod_tren


def test_thuoc_do_dung_that():
    assert E.dung_that("B", "B") and E.dung_that("b", "B") and not E.dung_that("A", "B")
    assert not E.dung_that("-", "B") and not E.dung_that("AB", "B")
    assert E.tap_chon("-") == "" and E.tap_chon("c") == "C" and E.tap_chon("CA") == "AC"
    assert [E.trang_thai_that(x) for x in ("-", "B", "b", "AC")] == ["trong", "ro", "mo", "nhieu"]
    rows = [{"that": "mo", "doc": "faint"}, {"that": "mo", "doc": "filled"}, {"that": "ro", "doc": "faint"}, {"that": "ro", "doc": "filled"}]
    assert E.f1_mo(rows) == pytest.approx(0.5)


def test_cp_tren_khong_loi():
    assert 0.05 < E.cp_tren(0, 54) < 0.07 and E.cp_tren(0, 0) == 1.0


def test_nhan_chi_gom_phieu_cua_tap():
    can_file(DATA / "ground_truth.csv")
    n = E.doc_nhan(range(1, 4))
    assert set(n) == {"0001", "0002", "0003"}
    assert set(E.doc_nhan(E.TAP["dev"])) == {f"{i:04d}" for i in range(1, 29)}
    assert set(E.TAP) == {"dev", "test"} and min(E.TAP["test"]) == 35


def test_test_can_xac_nhan(monkeypatch, tmp_path):
    from cv_engine.tap_du_lieu import ChamTapTest
    can_file(DATA / "raw" / "0035_C3.jpg")
    monkeypatch.setattr(sys, "argv", ["eval_he_thong.py", "run", "--tap", "test"])
    with pytest.raises(ChamTapTest):
        E.main()


def test_khoa_chay_mot_lan(monkeypatch, tmp_path):
    can_file(DATA / "raw" / "0035_C3.jpg")
    khoa = tmp_path / "da_chay_test.lock"
    khoa.write_text("đã chạy", encoding="utf-8")
    monkeypatch.setattr(E, "KHOA", khoa)
    monkeypatch.setattr(E, "OUT", tmp_path)
    monkeypatch.setattr(E, "kiem_dang_ky", lambda *a, **k: pytest.fail("không được tới bước đăng ký khi đã có khoá"))
    monkeypatch.setattr(E, "chay", lambda *a, **k: pytest.fail("không được chạy khi đã có khoá"))
    monkeypatch.setattr(sys, "argv", ["eval_he_thong.py", "run", "--tap", "test", "--xac-nhan-test"])
    with pytest.raises(SystemExit) as e:
        E.main()
    assert "TỪ CHỐI" in str(e.value)


def test_dang_ky_thieu_hoac_sai_bi_tu_choi(tmp_path):
    with pytest.raises(SystemExit):
        E.kiem_dang_ky(tmp_path / "khong_co.json")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, capture_output=True, text=True).stdout.strip()
    sai = tmp_path / "dk.json"
    sai.write_text(json.dumps({"ma_commit": head, "sha256": {E.FILE_SHA[0]: "0" * 64}}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        E.kiem_dang_ky(sai)
    assert "SHA" in str(e.value) or "khác" in str(e.value)
    sai.write_text(json.dumps({"ma_commit": "0" * 40, "sha256": {}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        E.kiem_dang_ky(sai)


def test_dang_ky_khop_duoc_chap_nhan(tmp_path):
    ban = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", *E.DUONG_DAN_MA], cwd=ROOT.parent, capture_output=True, text=True).stdout
    if ban.strip():
        pytest.skip("mã đang có thay đổi chưa commit")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, capture_output=True, text=True).stdout.strip()
    dk = tmp_path / "dk.json"
    dk.write_text(json.dumps({"ma_commit": head, "sha256": {f: E.sha_file(ROOT.parent / f) for f in E.FILE_SHA if (ROOT.parent / f).exists()}}), encoding="utf-8")
    assert E.kiem_dang_ky(dk)["ma_commit"] == head


def test_chay_nho_tren_dev_hai_anh(csdl_san_sang):
    ten = ["0002_C2", "0014_C2"]
    can_file(*[DATA / "raw" / f"{t}.jpg" for t in ten], DATA / "ground_truth.csv", DATA / "_eval" / "v6_api" / "diem_dev.csv")
    kq = E.chay("dev", xem=True, tien_do=lambda *_: None, danh_sach=ten)
    s = E.tom_tat(kq["rows"])
    assert s["anh"] == 2 and s["tu_choi"] == 0
    assert s["H2_nang"] == 0 and s["H3_sbd"] == 0 and s["H3_ma"] == 0 and s["H4_cham_sai_khong_co"] == 0 and s["H4_vi_pham_can"] == 0 and s["H4_tu_chot_sai"] == 0
    assert s["H5_dung"] == 2
    assert kq["nhat_quan"]["khop"] == 2 and not kq["nhat_quan"]["lech"]
    mu, may = E.html_trang(kq["rows"], False), E.html_trang(kq["rows"], True)
    assert "chưa có kết luận của máy" in mu and "máy:" not in mu and "ô tô" not in mu and "cần xem" not in mu.lower()
    assert "KẾT QUẢ MÁY" in may and "máy:" in may and "ô tô" in may
    assert E.dat_bat_buoc(s)["H2"] is True
