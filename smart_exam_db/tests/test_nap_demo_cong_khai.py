"""Lệnh AW (W1–W5): tools/nap_demo_cong_khai.py. Phần cần CSDL chạy trong MỘT schema tạm (CSDL trống như bản công khai vừa khởi tạo) + ROLLBACK:
không đụng dữ liệu thật (conn_thu kiểm số dòng trước / sau)."""
import sys
from dataclasses import replace

import pytest

from conftest import ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import khoi_tao_db_san_xuat as KT  # noqa: E402
import nap_demo_cong_khai as N  # noqa: E402

TEN = ("qt_demo_aw", "gv_x_aw", "gv_y_aw")
BANG = ("users", "classes", "teacher_classes", "students", "subjects", "exams", "exam_codes", "answer_keys", "exam_students", "answer_sheets", "results")


@pytest.fixture
def db_trong(conn_thu):
    """Schema tạm giống hệt CSDL công khai sau khoi_tao_db_san_xuat (01–03 + migration + mẫu phiếu; không seed). Cuối test conn_thu ROLLBACK."""
    conn_thu.execute("CREATE SCHEMA tmp_nap_aw")
    conn_thu.execute("SET LOCAL search_path = tmp_nap_aw")
    KT.ap_nen(conn_thu)
    KT.ap_migration_trong_giao_dich(conn_thu)
    KT.ap_mau_phieu(conn_thu)
    return conn_thu


def dem(conn) -> dict:
    return {b: conn.execute(f"SELECT count(*) AS n FROM {b}").fetchone()["n"] for b in BANG}


# ------------------------------------------------------------------------------------------------ không cần CSDL
def test_w1_che_mat_khau_va_nguoi_dung():
    m = N.muc_tieu("postgresql://smart_exam_app:MAT-KHAU-BI-MAT@db.noi-bo:5432/smart_exam")
    assert "db.noi-bo" in m and "smart_exam" in m
    for kieng in ("MAT-KHAU-BI-MAT", "smart_exam_app", "5432", "@"):
        assert kieng not in m.replace("smart_exam", "")
    assert "MAT-KHAU" not in N.muc_tieu("postgres://u:MAT-KHAU@h/d")
    assert "tmp_x" in N.muc_tieu("postgresql://u:p@h/d?options=-csearch_path%3Dtmp_x")
    assert "MAT-KHAU" not in N.muc_tieu("host=h dbname=d user=u password=MAT-KHAU")


def test_w3_tu_choi_ten_mau_va_trung():
    assert N.kiem_tham_so("quan_tri_1", ["giang_vien_1", "giang_vien_2"]) == []
    for mau in ("admin", "GV_AN", "gv_binh", "Sv220001"):
        assert any("mẫu" in x for x in N.kiem_tham_so(mau, ["giang_vien_1", "giang_vien_2"]))
        assert any("mẫu" in x for x in N.kiem_tham_so("quan_tri_1", [mau, "giang_vien_2"]))
    assert any("khác nhau" in x for x in N.kiem_tham_so("abc", ["abc", "def"]))
    assert any("không hợp lệ" in x for x in N.kiem_tham_so("a b", ["giang_vien_1", "giang_vien_2"]))


def test_w1_mac_dinh_xem_truoc_va_xac_nhan_sai_khong_ghi(capsys, monkeypatch):
    monkeypatch.setattr(N, "kiem_tham_so", lambda *a: [])
    assert N.main(["--admin", "aaa", "--giao-vien", "bbb", "ccc", "--xac-nhan", "nap"]) == 1       # sai xác nhận: thoát trước khi nối CSDL
    assert "KHÔNG ghi" in capsys.readouterr().out
    ma = (ROOT / "tools" / "nap_demo_cong_khai.py").read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in ma and "ghi = a.xac_nhan == XAC_NHAN" in ma


def test_w2_du_lieu_nhat_quan_voi_cong_cu_khac():
    import dat_lai_demo as D
    import nap_bo_demo as B
    assert {ma: td for ma, td, _, _ in N.BA_MON} == D.KY_THI_BA_MON == B.TIEU_DE_BA_MON
    assert [(ma, td, mm, tm) for ma, td, mm, tm in N.BA_MON] == [tuple(x) for x in B.BA_MON]
    assert N.DU_THI == tuple(str(s) for s in range(220001, 220010)) and len(N.SINH_VIEN) == 10
    assert all(len(a) == 40 for a in N.DAP_AN.values()) and list(N.DAP_AN) == ["101", "102", "103", "104"]


def test_w2_dap_an_trung_bo_demo_bv():
    can_file(ROOT / "answer_sheet" / "demo_bv" / "demo_bv_dap_an.csv")
    import kiem_bo_demo as K
    goc = {r["exam_code"]: r["answers"] for r in K.doc(K.DAP_AN)}
    assert goc == N.DAP_AN


def test_w2_sinh_vien_trung_seed_va_khong_co_ten_ngoai_seed():
    """Mọi (MSSV, họ tên) phải có trong database/04_seed.sql (dữ liệu mẫu của dự án) – không có bản ghi nào do ta tự thêm từ nguồn khác."""
    seed = (ROOT / "database" / "04_seed.sql").read_text(encoding="utf-8")
    for ma, ten, _ in N.SINH_VIEN:
        assert f"fn_upsert_student('{ma}','{ten}'" in " ".join(seed.split()).replace("', '", "','"), (ma, ten)


def test_w6_dockerignore_cho_phep_cong_cu_nap_va_dat_lai():
    di = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for t in ("nap_demo_cong_khai.py", "dat_lai_demo.py", "don_du_lieu_test.py"):
        assert f"!tools/{t}" in di, t


# ------------------------------------------------------------------------------------------------ CSDL trống (schema tạm, ROLLBACK)
def test_w1_xem_truoc_khong_ghi(db_trong):
    truoc = dem(db_trong)
    kq = N.nap(db_trong, *TEN[:1], list(TEN[1:]), ap_dung=False)
    assert dem(db_trong) == truoc and kq["mat_khau"] == {}
    assert kq["dong"]["users"] == 3 and kq["dong"]["exams"] == 3 and kq["dong"]["students"] == 10 and kq["dong"]["exam_students"] == 27
    assert kq["dong"]["exam_codes"] == 12 and kq["dong"]["answer_keys"] == 480 and kq["dong"]["subjects"] == 3 and kq["dong"]["classes"] == 2


def test_w2_w3_nap_dung_noi_dung(db_trong):
    from backend import auth
    kq = N.nap(db_trong, TEN[0], list(TEN[1:]), ap_dung=True)
    d = dem(db_trong)
    assert (d["users"], d["classes"], d["students"], d["exams"], d["exam_codes"], d["answer_keys"], d["exam_students"], d["teacher_classes"]) == (3, 2, 10, 3, 12, 480, 27, 2)
    assert d["answer_sheets"] == 0 and d["results"] == 0                         # W4: kỳ thi trống phiếu
    assert db_trong.execute("SELECT count(*) AS n FROM users WHERE role = 'student'").fetchone()["n"] == 0
    assert {r["username"] for r in db_trong.execute("SELECT username FROM users")} == set(TEN)
    assert db_trong.execute("SELECT role::text AS r FROM users WHERE username = %s", (TEN[0],)).fetchone()["r"] == "admin"
    assert {t["exam_title"] for t in db_trong.execute("SELECT exam_title FROM exams")} == {td for _, td, _, _ in N.BA_MON}
    assert set(kq["mat_khau"]) == set(TEN)
    for ten, mk in kq["mat_khau"].items():
        assert len(mk) >= 16 and auth.mat_khau_hop_le(mk) is None
        h = db_trong.execute("SELECT password_hash FROM users WHERE username = %s", (ten,)).fetchone()["password_hash"]
        assert auth.kiem_mat_khau(mk, h) and mk not in h
    assert len(set(kq["mat_khau"].values())) == 3
    gv1 = db_trong.execute("SELECT user_id FROM users WHERE username = %s", (TEN[1],)).fetchone()["user_id"]
    assert {r["created_by"] for r in db_trong.execute("SELECT created_by FROM exams")} == {gv1}
    assert db_trong.execute("SELECT count(*) AS n FROM students WHERE student_code = '220010' AND student_id NOT IN (SELECT student_id FROM exam_students)").fetchone()["n"] == 1


def test_w5_chay_lan_hai_khong_nhan_doi(db_trong):
    N.nap(db_trong, TEN[0], list(TEN[1:]), ap_dung=True)
    sau1 = dem(db_trong)
    kq2 = N.nap(db_trong, TEN[0], list(TEN[1:]), ap_dung=True)
    assert dem(db_trong) == sau1 and kq2["mat_khau"] == {} and not any(v for v in kq2["dong"].values())
    assert not any(t[2] for t in kq2["tai_khoan"])


def test_w3_tai_khoan_co_san_giu_nguyen_mat_khau(db_trong):
    db_trong.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, 'cu@x.invalid', 'scrypt$giu-nguyen', 'Cũ', 'admin')", (TEN[0],))
    kq = N.nap(db_trong, TEN[0].upper(), list(TEN[1:]), ap_dung=True)
    assert TEN[0].upper() not in kq["mat_khau"] and TEN[0] not in kq["mat_khau"] and set(kq["mat_khau"]) == set(TEN[1:])
    assert db_trong.execute("SELECT password_hash FROM users WHERE username = %s", (TEN[0],)).fetchone()["password_hash"] == "scrypt$giu-nguyen"


def test_w3_sai_vai_tro_thi_dung(db_trong):
    db_trong.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, 'cu@x.invalid', 'h', 'Cũ', 'student')", (TEN[1],))
    with pytest.raises(SystemExit) as e:
        N.nap(db_trong, TEN[0], list(TEN[1:]), ap_dung=True)
    assert "vai trò" in str(e.value)


def test_w2_sinh_vien_co_san_khac_ten_thi_dung_khong_ghi_de(db_trong):
    db_trong.execute("INSERT INTO students (student_code, full_name) VALUES ('220003', 'Người Khác Hẳn')")
    with pytest.raises(SystemExit) as e:
        N.nap(db_trong, TEN[0], list(TEN[1:]), ap_dung=True)
    assert "220003" in str(e.value) and "KHÔNG ghi đè" in str(e.value)
    assert db_trong.execute("SELECT full_name FROM students WHERE student_code = '220003'").fetchone()["full_name"] == "Người Khác Hẳn"


def test_chua_khoi_tao_thi_dung(conn_thu):
    conn_thu.execute("CREATE SCHEMA tmp_nap_aw_trong")
    conn_thu.execute("SET LOCAL search_path = tmp_nap_aw_trong")
    with pytest.raises(SystemExit) as e:
        N.nap(conn_thu, TEN[0], list(TEN[1:]), ap_dung=False)
    assert "chưa khởi tạo" in str(e.value)


# ------------------------------------------------------------------------------------------------ W5: đăng nhập + tải BV01 -> ghép đúng SBD, 9,5
def test_w5_dang_nhap_tai_bv01_ghep_sbd_va_ra_9_5(db_trong, cau_hinh_thu, monkeypatch):
    anh = ROOT / "data" / "_eval" / "demo_bv" / "anh_gia" / "BV01.jpg"
    can_file(anh, ROOT / "answer_sheet" / "demo_bv" / "demo_bv_kich_ban.csv")
    from fastapi.testclient import TestClient
    from backend import auth
    from backend.main import app, get_cau_hinh, get_conn
    kq = N.nap(db_trong, TEN[0], list(TEN[1:]), ap_dung=True)
    cfg = replace(cau_hinh_thu, auth_mode="on", auth_secret="t" * 48)
    monkeypatch.setattr(auth, "gioi_han", auth.GioiHanDangNhap())
    def _conn():
        yield db_trong
    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_cau_hinh] = lambda: cfg
    try:
        with TestClient(app) as cl:
            assert cl.post("/auth/login", json={"username": TEN[1], "password": "sai-mat-khau-0000"}).status_code in (401, 429)
            r = cl.post("/auth/login", json={"username": TEN[1], "password": kq["mat_khau"][TEN[1]]})
            assert r.status_code == 200, r.text
            ds = cl.get("/exams").json()
            kt = next(e for e in (ds if isinstance(ds, list) else ds.get("exams", ds.get("items", []))) if e["exam_title"] == "[XLA] Xử lý ảnh")
            r = cl.post(f"/exams/{kt['exam_id']}/sheets", files={"file": ("BV01.jpg", anh.read_bytes(), "image/jpeg")})
            assert r.status_code in (200, 201), r.text
            sid = r.json()["sheet_id"]
            v = cl.get(f"/sheets/{sid}").json()
            assert v["sbd"]["detected"] == "220001" and v["exam_code"]["detected"] == "101"          # ghép đúng SBD / mã đề (ảnh giả hoá: ô viết tay trống, bubble đúng)
            assert v["status"] == "needs_review" and float(v["score"]["provisional"]) == 9.0        # điểm TẠM: còn câu mờ chờ giáo viên
            # giáo viên duyệt ĐÚNG NHƯ GIẤY (kịch bản BV01) -> điểm chính thức 9,5 (38/40, đúng kiem_bo_demo)
            import kiem_bo_demo as K
            nhan = next(x for x in K.doc(K.KICH_BAN) if x["sheet_id"] == "BV01")
            for q in cl.get(f"/sheets/{sid}/review-questions").json():
                lab = nhan[f"q{q['question_no']}"]
                rr = cl.post(f"/sheets/{sid}/questions/{q['question_no']}/review",
                             json={"action": "set", "selected_options": "" if lab == "-" else "".join(sorted(lab.upper()))})
                assert rr.status_code == 200, rr.text
            sc = cl.get(f"/sheets/{sid}").json()["score"]
            assert sc["result_status"] == "confirmed" and float(sc["official"]) == 9.5, sc
            bd = cl.get(f"/exams/{kt['exam_id']}/results").json()
            assert any(x["sbd"] == "220001" and float(x["score"]) == 9.5 for x in bd["rows"]), bd
            r2 = TestClient(app).get("/exams")                                  # không đăng nhập
            assert r2.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_w6_sao_luu_dir_ghi_de_duoc_va_mac_dinh_khong_doi():
    import subprocess
    lay = lambda env: subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'tools'); import don_du_lieu_test as D; print(D.THU_MUC_SAO_LUU)"],
                                     cwd=ROOT, capture_output=True, text=True, env=env).stdout.strip()
    import os
    sach = {k: v for k, v in os.environ.items() if k != "SAO_LUU_DIR"}
    assert lay(sach).replace("\\", "/").endswith("data/_eval/sao_luu_don_du_lieu")
    assert lay({**sach, "SAO_LUU_DIR": "/app/storage/sao_luu"}).replace("\\", "/").endswith("/app/storage/sao_luu")
