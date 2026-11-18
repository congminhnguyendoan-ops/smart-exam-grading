"""Lệnh AP: tools/chay_demo.py (3 chế độ xla / ml / dacn) + các phần đi kèm: nap_bo_demo --ba-mon, dat_lai_demo --ky-thi, demo_ly_thuyet_mon,
phần bổ sung của demo_xu_ly_anh (chuẩn hoá, điểm tạm, CNN là gì). KHÔNG mở máy chủ thật, KHÔNG mở trình duyệt thật, KHÔNG ghi CSDL
(test CSDL chạy trong giao dịch ROLLBACK)."""
import re
import sys
import uuid

import pytest

from conftest import DATA, ROOT

sys.path.insert(0, str(ROOT / "tools"))
import chay_demo as C  # noqa: E402
import dat_lai_demo as DL  # noqa: E402
import demo_ly_thuyet_mon as T  # noqa: E402
import nap_bo_demo as NB  # noqa: E402

KIEM_GOC = C.kiem_truoc          # bản gốc: các test thay C.kiem_truoc bằng lambda gọi lại bản này
ANH_BV01 = DATA / "_eval" / "demo_bv" / "anh_gia" / "BV01.jpg"


# ------------------------------------------------------------------------------------------------ kiểm tra nhánh + mô hình
def test_kiem_truoc_dat_khi_dung_nhanh_va_sha():
    assert all(m.dat for m in C.kiem_truoc("cnn-sau", C.SHA_MO_HINH_OCR))
    assert all(m.dat for m in C.kiem_truoc("main", C.SHA_MO_HINH_OCR))      # sau gộp lệnh AS
    assert all(m.dat for m in C.kiem_truoc("trien-khai", C.SHA_MO_HINH_OCR))   # nhánh lệnh AU


def test_kiem_truoc_khong_dat_khi_sai_nhanh_hoac_sha():
    sai_nhanh = C.kiem_truoc("cai-tien-b", C.SHA_MO_HINH_OCR)
    assert [m.dat for m in sai_nhanh] == [False, True] and "cnn-sau" in sai_nhanh[0].chi_tiet
    assert [m.dat for m in C.kiem_truoc("main", "0" * 64)] == [True, False]     # main nhưng SHA sai vẫn bị chặn
    sai_sha = C.kiem_truoc("cnn-sau", "0" * 64)
    assert [m.dat for m in sai_sha] == [True, False]
    assert C.kiem_truoc("cnn-sau", "")[1].dat is False


def test_sha_mo_hinh_thuc_te_khop_hang_so():
    """Hằng SHA trong chay_demo phải đúng với tệp đang triển khai (nếu lệch: đã đổi mô hình mà quên đổi hằng)."""
    assert C.sha_mo_hinh() == C.SHA_MO_HINH_OCR


def test_main_dung_khi_kiem_tra_khong_dat(monkeypatch, capsys):
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("cai-tien-b", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda *a, **k: pytest.fail("không được đặt lại khi kiểm tra không đạt"))
    assert C.main(["xla"]) == 2
    assert "DỪNG" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ hướng dẫn 8–10 dòng
@pytest.mark.parametrize("che_do", C.CHE_DO)
def test_huong_dan_8_den_10_dong_co_url(che_do):
    d = C.huong_dan(che_do, "http://127.0.0.1:1234/")
    assert (6 if che_do == "xla" else 8) <= len(d) <= 10          # lệnh AY: hướng dẫn xla chỉ 6–7 dòng (đăng nhập, chọn kỳ, tải, BV01, điểm tạm, câu cần xem)
    assert any("http://127.0.0.1:1234/" in x for x in d)
    assert not any(re.search(r"mật khẩu *[:=] *\w{4,}", x, re.I) for x in d), "không được ghi mật khẩu thật"


@pytest.mark.parametrize("che_do", C.CHE_DO)
def test_chi_in_khong_lam_gi_ngoai_in(che_do, monkeypatch, capsys):
    """--chi-in: không đặt lại dữ liệu, không mở trình duyệt, không mở máy chủ / tiến trình."""
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("cnn-sau", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda *a, **k: pytest.fail("đặt lại"))
    monkeypatch.setattr(C.webbrowser, "open", lambda *a, **k: pytest.fail("mở trình duyệt"))
    monkeypatch.setattr(C.subprocess, "Popen", lambda *a, **k: pytest.fail("mở tiến trình"))
    monkeypatch.setattr(C, "ThreadingHTTPServer", lambda *a, **k: pytest.fail("mở máy chủ"))
    assert C.main([che_do, "--chi-in"]) == 0
    out = capsys.readouterr().out
    assert f"DEMO {che_do.upper()}" in out and len(re.findall(r"^\d\. ", out, re.M)) >= (6 if che_do == "xla" else 8)


# ------------------------------------------------------------------------------------------------ đặt lại đúng kỳ thi
@pytest.mark.parametrize("che_do", C.CHE_DO)
def test_main_dat_lai_dung_ky_thi_cua_che_do(che_do, monkeypatch):
    goi = []
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("cnn-sau", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda cd, *a, **k: goi.append(cd) or True)
    monkeypatch.setattr(C, "chay_xla", lambda *a, **k: 0)
    monkeypatch.setattr(C, "chay_ml", lambda *a, **k: 0)
    monkeypatch.setattr(C, "chay_dacn", lambda *a, **k: 0)
    assert C.main([che_do, "--khong-mo"]) == 0
    assert goi == [C.KY_THI_CUA[che_do]]


def test_dacn_dung_neu_khong_dat_lai_duoc_con_xla_ml_chay_tiep(monkeypatch, capsys):
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("cnn-sau", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda *a, **k: False)
    monkeypatch.setattr(C, "chay_xla", lambda *a, **k: 0)
    monkeypatch.setattr(C, "chay_dacn", lambda *a, **k: pytest.fail("dacn không được chạy khi chưa đặt lại được"))
    assert C.main(["xla-cong-cu", "--khong-mo"]) == 0
    assert C.main(["ml", "--khong-mo"]) == 0
    assert C.main(["dacn", "--khong-mo"]) == 1


def test_ky_thi_ba_mon_khop_giua_cac_cong_cu():
    assert DL.KY_THI_BA_MON == NB.TIEU_DE_BA_MON == {"xla": "[XLA] Xử lý ảnh", "ml": "[ML] Máy học", "dacn": "[ĐACN] Đồ án chuyên ngành"}


def test_ke_hoach_ba_mon_cau_truc():
    kh = NB.ke_hoach_ba_mon()
    assert [k["exam_title"] for k in kh] == ["[XLA] Xử lý ảnh", "[ML] Máy học", "[ĐACN] Đồ án chuyên ngành"]
    for k in kh:
        assert [c["code"] for c in k["codes"]] == ["101", "102", "103", "104"] and all(len(c["answers"]) == 40 for c in k["codes"])
        assert k["du_thi"] == [str(s) for s in range(220001, 220010)] and "220010" not in k["du_thi"]   # 220010 cố ý ngoài danh sách (BV10)
        assert k["teacher"] == "gv_an" and k["tao_mon"] is True


def test_lap_ke_hoach_ky_phamvi_dung_mot_ky(conn_thu):
    """Đặt lại 'xla' chỉ có thể chạm kỳ [XLA]; kế hoạch không bao giờ chứa phiếu của kỳ khác."""
    kh = DL.lap_ke_hoach_ky(conn_thu, "xla")
    e = conn_thu.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (DL.KY_THI_BA_MON["xla"],)).fetchone()["exam_id"]
    assert kh["pham_vi"] == [e] and {p["exam_id"] for p in kh["xoa"]} <= {e} and kh["co_tap"] is False
    assert not (set(kh["pham_vi"]) & {1380, 1381, 1632, 1633})


def test_lap_ke_hoach_ky_tu_choi_ma_la_va_tieu_de_trung(conn_thu):
    with pytest.raises(DL.LoiDatLai):
        DL.lap_ke_hoach_ky(conn_thu, "bv")
    uid = conn_thu.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1").fetchone()["user_id"]
    mon = conn_thu.execute("INSERT INTO subjects (subject_code, subject_name) VALUES (%s, 'Môn thử') RETURNING subject_id", ("T" + uuid.uuid4().hex[:8].upper(),)).fetchone()["subject_id"]
    mau = conn_thu.execute("SELECT template_id FROM sheet_templates ORDER BY template_id LIMIT 1").fetchone()["template_id"]
    conn_thu.execute("INSERT INTO exams (subject_id, template_id, exam_title, num_questions, max_score, created_by) VALUES (%s, %s, %s, 10, 10, %s)",
                     (mon, mau, DL.KY_THI_BA_MON["ml"], uid))                                   # kỳ thi thứ hai trùng tiêu đề (trong giao dịch ROLLBACK)
    with pytest.raises(DL.LoiDatLai, match="đúng 1"):
        DL.lap_ke_hoach_ky(conn_thu, "ml")


def test_lap_ke_hoach_van_tu_choi_ky_khong_co_demo_khi_khong_truyen_ten_hop_le(conn_thu):
    """Hành vi cũ không đổi: không có ten_hop_le thì kỳ thi không có '[DEMO' bị từ chối (kể cả kỳ [XLA])."""
    e = conn_thu.execute("SELECT exam_id FROM exams WHERE exam_title = %s", (DL.KY_THI_BA_MON["xla"],)).fetchone()["exam_id"]
    with pytest.raises(DL.LoiDatLai, match="DEMO"):
        DL.lap_ke_hoach(conn_thu, xoa_het=(e,), tap=None, nen={})


# ------------------------------------------------------------------------------------------------ xla: máy chủ ngoại tuyến (hàm thuần, không mở cổng)
def test_trang_chon_anh_co_du_nut_va_form_tai_len():
    h = C.trang_chon_anh([f"BV{i:02d}" for i in range(1, 11)], ["T05_thuong.JPG"])
    assert all(f'href="/bv/BV{i:02d}"' in h for i in range(1, 11)) and 'href="/them/T05_thuong.JPG"' in h
    assert 'enctype="multipart/form-data"' in h and 'action="/tai"' in h
    assert "http://" not in h.replace("http://127.0.0.1", "") and "https://" not in h, "trang phải chạy được khi không có mạng"


def test_xu_ly_yeu_cau_tu_choi_duong_dan_nguy_hiem_va_trang_khong_co():
    assert C.xu_ly_yeu_cau("GET", "/")[0] == 200
    assert C.xu_ly_yeu_cau("GET", "/bv/..%2Fx")[0] in (400, 404)
    assert C.xu_ly_yeu_cau("GET", "/bv/../../etc")[0] in (400, 404)
    assert C.xu_ly_yeu_cau("GET", "/them/models")[0] == 404
    assert C.xu_ly_yeu_cau("GET", "/bv/BV99")[0] == 404
    assert C.xu_ly_yeu_cau("GET", "/khong-co")[0] == 404
    assert C.xu_ly_yeu_cau("POST", "/tai", "multipart/form-data; boundary=x", b"")[0] == 400


def test_doc_tep_tai_len_multipart():
    bd = "XBOUNDX"
    body = (f"--{bd}\r\nContent-Disposition: form-data; name=\"anh\"; filename=\"p.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode() + b"\xff\xd8DATA\x00\x01" + f"\r\n--{bd}--\r\n".encode())
    ten, nd = C.doc_tep_tai_len(f"multipart/form-data; boundary={bd}", body)
    assert ten == "p.jpg" and nd == b"\xff\xd8DATA\x00\x01"
    khac = (f"--{bd}\r\nContent-Disposition: form-data; name=\"khac\"\r\n\r\nx\r\n--{bd}--\r\n").encode()
    assert C.doc_tep_tai_len(f"multipart/form-data; boundary={bd}", khac) is None


def test_xla_xu_ly_anh_bv01_co_du_cac_buoc_moi():
    if not ANH_BV01.exists():
        pytest.skip("thiếu data/_eval/demo_bv/anh_gia/BV01.jpg")
    ma, ct, nd = C.xu_ly_yeu_cau("GET", "/bv/BV01")
    h = nd.decode("utf-8")
    assert ma == 200 and ct.startswith("text/html")
    assert re.findall(r'<span class="so">([^<]+)</span>', h) == ["1", "2", "3", "4", "4b", "5", "6", "7", "8", "9", "10"]
    for k in ("Chuẩn hoá ánh sáng", "điểm TẠM", "KHÔNG phải điểm chính thức", "CNN là gì", "aria-label=\"Sơ đồ CNN", "Chọn ảnh khác"):
        assert k in h
    assert "http://" not in h and "https://" not in h


# ------------------------------------------------------------------------------------------------ xla: bổ sung trong demo_xu_ly_anh
def test_diem_tam_dung_ham_cham_he_thong():
    """buoc_diem_tam dùng grading.cham_diem; câu cần xem KHÔNG được tính vào điểm tạm."""
    import demo_xu_ly_anh as X
    from types import SimpleNamespace as NS
    keys = X.dap_an_theo_ma_de()
    assert set(keys) == {"101", "102", "103", "104"} and all(len(v) == 40 for v in keys.values())
    cau = [NS(cau=i + 1, dap_an=keys["101"][i], trang_thai="ro", can_xem=(i < 4)) for i in range(40)]    # đúng cả 40 nhưng 4 câu đầu 'cần xem'
    h = X.buoc_diem_tam(NS(cau=cau), {"ma_de": ("101", True, ())})
    assert "9.000" in h and "KHÔNG phải điểm chính thức" in h and "10.000" in h                        # 36 × 0,25 = 9; tối đa 40 × 0,25 = 10
    assert "chưa chấm được" in X.buoc_diem_tam(NS(cau=cau), {"ma_de": ("99?", False, ())}).lower()


def test_giai_thich_cnn_co_hinh_va_loi_khong_can_o_mau():
    import demo_xu_ly_anh as X
    h = X.giai_thich_cnn(None)
    assert "<svg" in h and "CNN là gì" in h and "10 con số" in h and "<img" not in h


# ------------------------------------------------------------------------------------------------ ml + dacn (giả lập, không chạy thật)
def test_chay_ml_dung_trang_va_mo_mot_tab(monkeypatch, tmp_path):
    import demo_may_hoc as M
    monkeypatch.setattr(C, "RA", tmp_path)
    monkeypatch.setattr(M, "chay_truc_tiep", lambda: {"dung": 485, "n": 504})
    monkeypatch.setattr(M, "chay_so_sanh_truc_tiep", lambda da: {"da": da})
    monkeypatch.setattr(M, "dung_trang", lambda tt, ss: "<html>trang may hoc</html>")
    mo = []
    assert C.chay_ml(True, False, mo_trinh_duyet=mo.append) == 0
    assert (tmp_path / "may_hoc_chay_demo.html").read_text(encoding="utf-8") == "<html>trang may hoc</html>"
    assert len(mo) == 1 and mo[0].startswith("file:///")


def test_chay_dacn_khoi_dong_may_chu_mo_hai_tab_va_dung(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "RA", tmp_path)

    class GiaTienTrinh:
        da_dung = False
        lenh = None

        def wait(self):
            raise KeyboardInterrupt

        def terminate(self):
            GiaTienTrinh.da_dung = True

    def gia_popen(lenh, **kw):
        GiaTienTrinh.lenh = lenh
        return GiaTienTrinh()

    san_sang = iter([False, True])
    monkeypatch.setattr(C, "may_chu_dang_chay", lambda *a, **k: next(san_sang))
    mo = []
    assert C.chay_dacn(8000, True, mo_trinh_duyet=mo.append, mo_tien_trinh=gia_popen, cho_s=1) == 0
    assert GiaTienTrinh.lenh[1].endswith("chay_server_lan.py") and GiaTienTrinh.lenh[-2:] == ["--cong", "8000"]
    assert mo[0] == "http://127.0.0.1:8000/" and mo[1].startswith("file:///") and mo[1].endswith("ly_thuyet_cac_mon.html")
    assert GiaTienTrinh.da_dung is True
    assert (tmp_path / "ly_thuyet_cac_mon.html").exists()


def test_chay_dacn_bao_loi_khi_may_chu_khong_len(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(C, "RA", tmp_path)
    monkeypatch.setattr(C, "may_chu_dang_chay", lambda *a, **k: False)

    class P:
        dung = False

        def terminate(self):
            P.dung = True
    mo = []
    assert C.chay_dacn(8000, True, mo_trinh_duyet=mo.append, mo_tien_trinh=lambda *a, **k: P(), cho_s=0) == 1
    assert mo == [] and P.dung is True and "LỖI" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ trang lý thuyết các môn
def test_ly_thuyet_cac_mon_co_giai_dinh_va_7_mon_va_khong_bia_so():
    h = T.dung_trang({"so_duong_dan_api": None, "so_bang": None, "so_view": None})
    assert "GIẢ ĐỊNH" in h and h.count("<h2>") == 7
    for mon in ("Cơ sở dữ liệu", "Lập trình web", "An toàn thông tin", "Kiểm thử", "Phân tích thiết kế", "Xử lý ảnh", "Học máy"):
        assert mon in h
    assert "chưa đếm được" in h, "không đếm được thì phải ghi rõ, không điền số bịa"
    assert "http://" not in h and "https://" not in h
    h2 = T.dung_trang({"so_duong_dan_api": 60, "so_bang": 23, "so_view": 8})
    assert "60 cặp" in h2 and "23 bảng" in h2


# ------------------------------------------------------------------------------------------------ lệnh AY: xla = hệ thống thật, xla-cong-cu = công cụ cũ
def test_ay_xla_chay_he_thong_that_khong_phai_cong_cu_8765(monkeypatch):
    goi = {}
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("main", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda cd, *a, **k: goi.setdefault("dat_lai", []).append(cd) or True)
    monkeypatch.setattr(C, "chay_xla", lambda *a, **k: pytest.fail("xla không được chạy công cụ ngoại tuyến"))
    monkeypatch.setattr(C, "chay_ml", lambda *a, **k: pytest.fail("không được chạy ml"))
    monkeypatch.setattr(C, "chay_dacn", lambda cong, mo, **k: goi.update(cong=cong, mo=mo, **k) or 0)
    assert C.main(["xla", "--khong-mo"]) == 0
    assert goi == {"dat_lai": ["xla"], "cong": 8000, "mo": False, "che_do": "xla"}            # chỉ đặt lại kỳ [XLA]; không [ĐACN] / [ML]
    goi.clear()
    assert C.main(["xla", "--khong-mo", "--cong", "8010"]) == 0 and goi["cong"] == 8010


def test_ay_xla_dung_neu_khong_dat_lai_duoc(monkeypatch, capsys):
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("main", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda *a, **k: False)
    monkeypatch.setattr(C, "chay_dacn", lambda *a, **k: pytest.fail("xla không được chạy khi chưa đặt lại được"))
    assert C.main(["xla", "--khong-mo"]) == 1
    assert "xla" in capsys.readouterr().out


def test_ay_xla_khong_dat_lai_khi_co_khong_dat_lai(monkeypatch):
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("main", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda *a, **k: pytest.fail("không được đặt lại"))
    monkeypatch.setattr(C, "chay_dacn", lambda *a, **k: 0)
    assert C.main(["xla", "--khong-dat-lai", "--khong-mo"]) == 0


def test_ay_chi_in_xla_chi_chua_6_viec_va_khong_nhac_dacn_ml(capsys, monkeypatch):
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("main", C.SHA_MO_HINH_OCR))
    assert C.main(["xla", "--chi-in"]) == 0
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8000/app/" in out and "8765" not in out
    for muc in ("ĐĂNG NHẬP", "[XLA] Xử lý ảnh", "Tải ảnh & chấm", "BV01", "ĐIỂM TẠM", "cần xem"):
        assert muc in out, muc
    assert "[ĐACN]" not in out and "[ML]" not in out


def test_ay_chay_dacn_che_do_xla_mo_app_mot_tab_khong_dung_ly_thuyet(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "RA", tmp_path)
    monkeypatch.setattr(C, "dung_ly_thuyet", lambda: pytest.fail("xla không dựng trang lý thuyết"))

    class P:
        def wait(self):
            raise KeyboardInterrupt

        def terminate(self):
            pass
    san_sang = iter([False, True])
    monkeypatch.setattr(C, "may_chu_dang_chay", lambda *a, **k: next(san_sang))
    mo = []
    assert C.chay_dacn(8000, True, mo_trinh_duyet=mo.append, mo_tien_trinh=lambda *a, **k: P(), cho_s=1, che_do="xla") == 0
    assert mo == ["http://127.0.0.1:8000/app/"]


def test_ay_xla_cong_cu_con_ton_tai_cong_8765(monkeypatch):
    assert "xla-cong-cu" in C.CHE_DO and C.CONG_XLA == 8765 and callable(C.chay_xla)
    goi = {}
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("main", C.SHA_MO_HINH_OCR))
    monkeypatch.setattr(C, "dat_lai", lambda cd, *a, **k: True)
    monkeypatch.setattr(C, "chay_xla", lambda cong, mo, *a, **k: goi.update(cong=cong) or 0)
    monkeypatch.setattr(C, "chay_dacn", lambda *a, **k: pytest.fail("xla-cong-cu không chạy hệ thống thật"))
    assert C.main(["xla-cong-cu", "--khong-mo"]) == 0 and goi == {"cong": 8765}


def test_ay_chi_in_xla_cong_cu_giu_huong_dan_cu(capsys, monkeypatch):
    monkeypatch.setattr(C, "kiem_truoc", lambda: KIEM_GOC("main", C.SHA_MO_HINH_OCR))
    assert C.main(["xla-cong-cu", "--chi-in"]) == 0
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8765/" in out and "ngoại tuyến" in out
