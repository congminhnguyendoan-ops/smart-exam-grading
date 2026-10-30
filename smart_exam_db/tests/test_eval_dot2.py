"""Kiểm thử công cụ đợt 2 tools/eval_dot2.py: độc lập, nhãn (gồm chấm nhỏ), đối chiếu chéo nhãn, khoá chạy một lần, đăng ký, sửa nhãn theo giấy,
xem mù không rò kết luận máy, chạy nhỏ trên ảnh giả hoá. Không đọc ảnh / nhãn val / test; không cần ảnh đợt 2 thật."""
import ast
import csv
import json
import subprocess
import sys

import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import eval_dot2 as E  # noqa: E402


def test_doc_lap_khong_import_luat_cham():
    cay = ast.parse((ROOT / "tools" / "eval_dot2.py").read_text(encoding="utf-8"))
    moi = {n.module for n in ast.walk(cay) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(cay) if isinstance(n, ast.Import) for a in n.names}
    assert not {"cv_engine.omr", "cv_engine.ocr", "backend.service", "backend.grading", "backend", "cv_engine", "cv_engine.preprocessing"} & moi, moi
    dung = {n.attr for n in ast.walk(cay) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in ("omr", "ocr", "grading", "service")}
    assert not dung


def test_nhan_cham_nho_la_trong():
    assert E.tap_chon("*B") == "" and E.tap_chon("-") == "" and E.tap_chon("bD") == "BD"
    assert E.trang_thai_that("*B") == "vet" and E.trang_thai_that("-") == "trong" and E.trang_thai_that("b") == "mo" and E.trang_thai_that("AC") == "nhieu"
    assert not E.H.dung_that("*B", "B")                                   # chấm nhỏ không phải đáp án
    ds = {"B": "dam", "b": "mo", "AB": "hai_dam", "Ab": "dam_mo", "bd": "hai_mo", "ABD": "ba_dam", "abd": "ba_mo", "*B": "cham_nho", "-": "trong"}
    assert {k: E.loai_cau(k) for k in ds} == ds
    assert [E.nhan_o("*B", o) for o in "ABCD"] == ["blank", "vet", "blank", "blank"]
    assert [E.nhan_o("aD", o) for o in "ABCD"] == ["faint", "blank", "blank", "filled"]


def test_nhan_goc_khop_cheo_va_phat_hien_sua_tay(tmp_path):
    can_file(E.GT, E.CELL)
    nhan = E.doc_nhan(E.GT, E.CELL)
    assert sorted(nhan) == [f"{p:04d}" for p in E.PHIEU_DOT2] and all(len(t["q"]) == 40 for t in nhan.values())
    assert sum(loai == "cham_nho" for t in nhan.values() for loai in t["loai"].values()) == 30
    assert nhan["0107"]["sbd_bubble"] == "37-273"
    assert len(E.ten_anh(nhan)) == 20
    rows = E.doc_csv(E.CELL)                                              # sửa tay 1 ô cell_labels -> phải DỪNG
    rows[0]["cell_label"] = "filled"
    xau = tmp_path / "cell.csv"
    with xau.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit) as e:
        E.doc_nhan(E.GT, xau)
    assert "lệch" in str(e.value)


def test_chi_hai_che_do_va_khoa_chay_mot_lan(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["eval_dot2.py", "run"])
    with pytest.raises(SystemExit) as e:
        E.main()
    assert "TỪ CHỐI" in str(e.value)
    khoa = tmp_path / "da_chay_dot2.lock"
    khoa.write_text("đã chạy", encoding="utf-8")
    monkeypatch.setattr(E, "KHOA", khoa)
    monkeypatch.setattr(E, "OUT", tmp_path)
    monkeypatch.setattr(E, "kiem_dang_ky", lambda *a, **k: pytest.fail("không được tới bước đăng ký khi đã có khoá"))
    monkeypatch.setattr(E, "chay", lambda *a, **k: pytest.fail("không được chạy khi đã có khoá"))
    monkeypatch.setattr(sys, "argv", ["eval_dot2.py", "run", "--xac-nhan-dot2"])
    with pytest.raises(SystemExit) as e:
        E.main()
    assert "TỪ CHỐI" in str(e.value)


def test_thu_gia_khong_tao_khoa_va_khong_can_dang_ky(monkeypatch, tmp_path):
    class Dung(Exception):
        pass

    def dung(*a, **k):
        raise Dung()
    monkeypatch.setattr(E, "KHOA", tmp_path / "da_chay_dot2.lock")
    monkeypatch.setattr(E, "OUT", tmp_path)
    monkeypatch.setattr(E, "kiem_dang_ky", lambda *a, **k: pytest.fail("--thu-gia không được đòi đăng ký"))
    monkeypatch.setattr(E, "chay", dung)
    monkeypatch.setattr(sys, "argv", ["eval_dot2.py", "run", "--thu-gia"])
    with pytest.raises(Dung):
        E.main()
    assert not (tmp_path / "da_chay_dot2.lock").exists()


@pytest.fixture
def ma_khoa_on_dinh(monkeypatch):
    """Trỏ 'mã khoá' sang thư mục dữ liệu đợt 2 (không đổi trong lúc phát triển) để test không phụ thuộc cây git đang sạch hay dơ."""
    monkeypatch.setattr(E, "DUONG_DAN_MA", ["smart_exam_db/answer_sheet/dot2"])


def test_dang_ky_thieu_hoac_sai_bi_tu_choi(tmp_path, ma_khoa_on_dinh):
    with pytest.raises(SystemExit):
        E.kiem_dang_ky(tmp_path / "khong_co.json")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, capture_output=True, text=True).stdout.strip()
    sai = tmp_path / "dk.json"
    sai.write_text(json.dumps({"ma_commit": head, "sha256": {E.FILE_SHA_GOC[0]: "0" * 64}}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        E.kiem_dang_ky(sai)
    assert "SHA" in str(e.value) or "khác" in str(e.value)
    sai.write_text(json.dumps({"ma_commit": "0" * 40, "sha256": {}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        E.kiem_dang_ky(sai)


def test_dang_ky_khop_va_nhan_sua_phai_co_bo_sung(monkeypatch, tmp_path, ma_khoa_on_dinh):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, capture_output=True, text=True).stdout.strip()
    sha = {f: E.H.sha_file(ROOT.parent / f) for f in E.FILE_SHA_GOC if (ROOT.parent / f).exists()}
    dk = tmp_path / "dk.json"
    dk.write_text(json.dumps({"ma_commit": head, "sha256": sha}), encoding="utf-8")
    monkeypatch.setattr(E, "GT_SUA", tmp_path / "ground_truth_dot2_da_sua.csv")
    monkeypatch.setattr(E, "CELL_SUA", tmp_path / "cell_labels_dot2_da_sua.csv")
    monkeypatch.setattr(E, "SUA_NHAN", tmp_path / "sua_nhan.csv")
    assert E.kiem_dang_ky(dk)["ma_commit"] == head                        # chưa có nhãn sửa -> chấp nhận
    for p in (E.GT_SUA, E.CELL_SUA, E.SUA_NHAN):
        p.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as e:                                  # có nhãn sửa mà chưa đăng ký bổ sung
        E.kiem_dang_ky(dk)
    assert "bổ sung" in str(e.value)
    bs = {p.name: E.H.sha_file(p) for p in (E.GT_SUA, E.CELL_SUA, E.SUA_NHAN)}
    dk.write_text(json.dumps({"ma_commit": head, "sha256": sha, "bo_sung": bs}), encoding="utf-8")
    assert E.kiem_dang_ky(dk)["ma_commit"] == head


def test_ap_dung_sua_nhan(monkeypatch, tmp_path):
    can_file(E.GT, E.CELL)
    monkeypatch.setattr(E, "DOT2_DATA", tmp_path)
    monkeypatch.setattr(E, "GT_SUA", tmp_path / "gt_sua.csv")
    monkeypatch.setattr(E, "CELL_SUA", tmp_path / "cell_sua.csv")
    monkeypatch.setattr(E, "SUA_NHAN", tmp_path / "sua_nhan.csv")
    cu = E.doc_nhan(E.GT, E.CELL)["0101"]["q"][2]

    def ghi(rows):
        with E.SUA_NHAN.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["phieu", "muc", "nhan_cu", "nhan_moi", "ly_do", "ngay"])
            w.writeheader()
            w.writerows(rows)
    ghi([dict(phieu="0101", muc="q2", nhan_cu="SAI", nhan_moi="A", ly_do="x", ngay="2026-10-30")])
    with pytest.raises(SystemExit):                                       # nhãn cũ không khớp
        E.ap_dung_sua()
    ghi([dict(phieu="0101", muc="q2", nhan_cu=cu, nhan_moi="A", ly_do="", ngay="2026-10-30")])
    with pytest.raises(SystemExit):                                       # thiếu lý do
        E.ap_dung_sua()
    ghi([dict(phieu="0101", muc="q2", nhan_cu=cu, nhan_moi="A", ly_do="so giấy thật", ngay="2026-10-30")])
    E.ap_dung_sua()
    moi = E.doc_nhan(E.GT_SUA, E.CELL_SUA)["0101"]
    assert moi["q"][2] == "A" and moi["loai"][2] == "dam" and E.doc_nhan(E.GT, E.CELL)["0101"]["q"][2] == cu
    assert E.nguon_nhan()[0] == E.GT_SUA                                  # có bản sửa thì dùng bản sửa


def test_chay_nho_tren_anh_gia_hoa(csdl_san_sang, monkeypatch, tmp_path):
    can_file(E.LAYOUT, E.MAU_PNG, E.GT, E.CELL)
    monkeypatch.setattr(E, "THU_GIA", tmp_path)
    E.tao_gia()
    ten = ["0107_C3", "0105_C1"]
    kq = E.chay(tmp_path, xem=True, co_chu_so=False, tien_do=lambda *_: None, danh_sach=ten)
    s = E.H.tom_tat(kq["rows"])
    h = E.dat_bat_buoc(s, kq["rows"])
    assert s["anh"] == 2 and s["tu_choi"] == 0 and h["H2"] is True and h["H3"] is True and h["H4"] is True and h["H5"] is True
    pt = E.phan_tich(kq["rows"])
    assert pt["vet"]["n"] == 6 and pt["vet"]["gan_co"] == 6 and pt["vet"]["doc_thanh_dap_an_chac_LOI_NANG"] == 0
    assert pt["phieu_0107_sbd_can_xem"] == {"0107_C3": True}
    r105 = next(r for r in kq["rows"] if r["phieu"] == 105)                # tô nhạt cả tờ: mọi câu có ô được chọn đều có cờ
    assert all(c["cx"] for c in r105["cau"] if c["that"] != "trong")
    mu, may = E.H.html_trang(kq["rows"], False), E.H.html_trang(kq["rows"], True)
    assert "chưa có kết luận của máy" in mu and "máy:" not in mu and "ô tô" not in mu and "cần xem" not in mu.lower()
    assert "KẾT QUẢ MÁY" in may and "máy:" in may


def test_dang_ky_that_khop_voi_cay_lam_viec():
    """Bản đăng ký thật (docs/dang_ky_test_dot2.json) phải khớp SHA các file đang có – bắt lỗi ghi sai (vd chữ HOA / thường) hoặc file trôi sau đăng ký."""
    if not E.DANG_KY.exists():
        pytest.skip("chưa có bản đăng ký")
    d = json.loads(E.DANG_KY.read_text(encoding="utf-8"))
    assert d["sha256"] and all(h == h.lower() for h in d["sha256"].values())
    khac = subprocess.run(["git", "diff", "--stat", d["ma_commit"], "HEAD", "--", *E.DUONG_DAN_MA], cwd=ROOT.parent, capture_output=True, text=True)
    if khac.returncode != 0 or khac.stdout.strip():
        pytest.skip("SKIP có chủ đích: mã khoá (cv_engine / models / backend / answer_sheet/output) khác commit đăng ký – đang ở nhánh phát triển; "
                    "kiểm đăng ký chỉ có nghĩa trên bản đóng băng (tag dang-ky-dot2), nơi test này chạy thật")
    sai = [f for f, h in d["sha256"].items() if E.H.sha_file(ROOT.parent / f) != h]
    assert not sai, f"SHA khác đăng ký: {sai}"
