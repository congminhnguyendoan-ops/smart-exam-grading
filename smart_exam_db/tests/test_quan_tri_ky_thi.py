import uuid
from datetime import date

import pytest

from backend import demo, quan_tri
from test_dang_nhap import bang_moi, client_on, dn, tai_trang, tao_lop, tao_user  # noqa: F401 – fixture dùng lại

MA_DE = [{"code": "101", "answers": demo.khoa_demo("101", 10)}, {"code": "102", "answers": demo.khoa_demo("102", 10)}]


def than(**them) -> dict:
    return {"exam_title": "Kỳ thi quản trị (pytest)", "subject_code": "QT" + uuid.uuid4().hex[:6].upper(), "subject_name": "Môn quản trị",
            "num_questions": 10, "codes": MA_DE, **them}


@pytest.fixture
def qt(client_on, bang_moi):
    c, conn = client_on, bang_moi
    ad, _ = tao_user(conn, "admin")
    gA, idA = tao_user(conn)
    gB, idB = tao_user(conn)
    sv, _ = tao_user(conn, "student")
    h = {"ad": dn(c, ad), "A": dn(c, gA), "B": dn(c, gB), "sv": dn(c, sv)}
    r = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA, exam_date="2026-11-05"))
    assert r.status_code == 201, r.text
    return c, conn, h, idA, idB, r.json()


def test_chi_admin_403_401(qt):
    c, _, h, idA, _, e = qt
    eid = e["exam_id"]
    goi = [("get", "/admin/exams", None), ("post", "/admin/exams", than(teacher_user_id=idA)), ("patch", f"/admin/exams/{eid}", {"exam_title": "Tên mới"}),
           ("post", f"/admin/exams/{eid}/status", {"closed": True}), ("delete", f"/admin/exams/{eid}", None), ("get", "/admin/users", None)]
    for vai in ("A", "B", "sv"):
        for m, url, body in goi:
            r = getattr(c, m)(url, headers=h[vai], **({"json": body} if body is not None else {}))
            assert r.status_code == 403, (vai, m, url, r.text)
    for m, url, body in goi:
        assert getattr(c, m)(url, **({"json": body} if body is not None else {})).status_code == 401
    assert c.get(f"/exams/{eid}", headers=h["ad"]).json()["exam_title"] == "Kỳ thi quản trị (pytest)"


def test_giao_vien_khong_tu_tao_ky_thi(qt):
    c, conn, h, _, _, _ = qt
    n = conn.execute("SELECT count(*) AS n FROM exams").fetchone()["n"]
    assert c.post("/exams", headers=h["A"], json=than()).status_code == 403
    assert c.post("/exams", headers=h["ad"], json=than()).status_code == 201
    assert conn.execute("SELECT count(*) AS n FROM exams").fetchone()["n"] == n + 1


def test_tao_gan_giao_vien_va_pham_vi(qt):
    c, _, h, idA, _, e = qt
    assert e["teacher_user_id"] == idA and e["status"] == "draft" and e["ma_de"] == "101, 102" and e["exam_date"] == "2026-11-05" and e["so_phieu"] == 0
    eid = e["exam_id"]
    assert eid in {x["exam_id"] for x in c.get("/exams", headers=h["A"]).json()}
    d = c.get(f"/exams/{eid}", headers=h["A"]).json()
    assert d["codes"] == MA_DE and d["status"] == "draft"
    rB = c.get(f"/exams/{eid}", headers=h["B"])
    assert rB.status_code == 404 and rB.json()["detail"] == f"Không có kỳ thi {eid}."
    assert eid not in {x["exam_id"] for x in c.get("/exams", headers=h["B"]).json()}
    assert eid in {x["exam_id"] for x in c.get("/admin/exams", headers=h["ad"]).json()}


def test_tao_khong_gan_thi_admin_phu_trach(qt):
    c, _, h, _, _, _ = qt
    r = c.post("/admin/exams", headers=h["ad"], json=than())
    me = c.get("/me", headers=h["ad"]).json()
    assert r.status_code == 201 and r.json()["teacher_user_id"] == me["user_id"]


def test_dung_lai_quy_tac_dap_an(qt):
    c, _, h, idA, _, _ = qt
    sai = [({"codes": [{"code": "101", "answers": "ABC"}]}, "có 3 đáp án, cần đúng 10"),
           ({"codes": [{"code": "101", "answers": "ABCDABCDAX"}]}, "Mã đề 101"),
           ({"codes": [{"code": "1x1", "answers": "A" * 10}]}, "1–6 chữ số"),
           ({"codes": [{"code": "101", "answers": "A" * 10}, {"code": "101", "answers": "B" * 10}]}, "trùng")]
    for them, mau in sai:
        r_qt = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA, **them))
        r_cu = c.post("/exams", headers=h["ad"], json=than(**them))
        assert r_qt.status_code == r_cu.status_code == 422 and mau in r_qt.json()["detail"], (them, r_qt.text)
        assert r_qt.json()["detail"] == r_cu.json()["detail"]


def test_giao_vien_phu_trach_phai_hop_le(qt):
    c, conn, h, _, _, _ = qt
    _, id_khoa = tao_user(conn, active=False)
    _, id_ad = tao_user(conn, "admin")
    _, id_sv = tao_user(conn, "student")
    for uid in (id_khoa, id_ad, id_sv, 10 ** 12):
        r = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=uid))
        assert r.status_code == 422 and "Giáo viên phụ trách" in r.json()["detail"], uid


def test_sua_ten_ngay(qt):
    c, _, h, _, _, e = qt
    eid = e["exam_id"]
    r = c.patch(f"/admin/exams/{eid}", headers=h["ad"], json={"exam_title": "  Giữa kỳ đổi tên  "})
    assert r.status_code == 200 and r.json()["exam_title"] == "Giữa kỳ đổi tên" and r.json()["exam_date"] == "2026-11-05"
    r = c.patch(f"/admin/exams/{eid}", headers=h["ad"], json={"exam_date": "2026-12-01"})
    assert r.json()["exam_date"] == "2026-12-01" and r.json()["exam_title"] == "Giữa kỳ đổi tên"
    assert c.patch(f"/admin/exams/{eid}", headers=h["ad"], json={"exam_date": None}).json()["exam_date"] is None
    assert c.patch(f"/admin/exams/{eid}", headers=h["ad"], json={"exam_title": "ab"}).status_code == 422
    assert c.patch(f"/admin/exams/{eid}", headers=h["ad"], json={"exam_title": "   x   "}).status_code == 422
    assert c.patch(f"/admin/exams/{eid}", headers=h["ad"], json={}).status_code == 422
    assert c.patch("/admin/exams/999999999999", headers=h["ad"], json={"exam_title": "Không có"}).status_code == 404
    assert c.get(f"/exams/{eid}", headers=h["A"]).json()["codes"] == MA_DE


def test_dong_khong_nhan_anh_mo_lai_nhan(qt):
    c, _, h, _, _, e = qt
    eid = e["exam_id"]
    assert tai_trang(c, h["A"], eid).status_code == 201
    r = c.post(f"/admin/exams/{eid}/status", headers=h["ad"], json={"closed": True})
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert c.get(f"/exams/{eid}", headers=h["A"]).json()["status"] == "closed"
    assert {x["exam_id"]: x for x in c.get("/exams", headers=h["A"]).json()}[eid]["status"] == "closed"
    r = tai_trang(c, h["A"], eid)
    assert r.status_code == 409 and r.json()["detail"] == quan_tri.THONG_BAO_DA_DONG
    rb = c.post(f"/exams/{eid}/sheets/batch", headers=h["A"], files=[("files", ("a.jpg", b"x", "image/jpeg"))])
    assert rb.status_code == 409
    for url in (f"/exams/{eid}/sheets", f"/exams/{eid}/results", f"/exams/{eid}/review-questions", f"/exams/{eid}/export.xlsx"):
        assert c.get(url, headers=h["A"]).status_code == 200, url
    assert tai_trang(c, h["B"], eid).status_code == 404
    assert c.post(f"/admin/exams/{eid}/status", headers=h["ad"], json={"closed": False}).json()["status"] == "draft"
    assert tai_trang(c, h["A"], eid).status_code == 201


def test_xoa_chi_khi_chua_co_phieu(qt):
    c, conn, h, idA, _, e = qt
    eid = e["exam_id"]
    assert tai_trang(c, h["A"], eid).status_code == 201
    r = c.delete(f"/admin/exams/{eid}", headers=h["ad"])
    assert r.status_code == 409 and "ĐÓNG" in r.json()["detail"]
    assert conn.execute("SELECT count(*) AS n FROM answer_sheets WHERE exam_id = %s", (eid,)).fetchone()["n"] == 1
    rong = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA)).json()["exam_id"]
    assert c.delete(f"/admin/exams/{rong}", headers=h["ad"]).status_code == 204
    assert c.get(f"/exams/{rong}", headers=h["ad"]).status_code == 404
    assert c.delete(f"/admin/exams/{rong}", headers=h["ad"]).status_code == 404


def test_khong_xoa_ky_thi_demo_hoac_co_danh_sach_du_thi(qt):
    c, conn, h, idA, _, _ = qt
    demo_id = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA, exam_title="Giữa kỳ [DEMO-BV] thử")).json()["exam_id"]
    r = c.delete(f"/admin/exams/{demo_id}", headers=h["ad"])
    assert r.status_code == 409 and "DEMO" in r.json()["detail"]
    co_ds = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA)).json()["exam_id"]
    sv = conn.execute("INSERT INTO students (student_code, full_name) VALUES (%s, 'SV dự thi') RETURNING student_id",
                      (str(uuid.uuid4().int)[:12],)).fetchone()["student_id"]
    conn.execute("INSERT INTO exam_students (exam_id, student_id) VALUES (%s, %s)", (co_ds, sv))
    r = c.delete(f"/admin/exams/{co_ds}", headers=h["ad"])
    assert r.status_code == 409 and "danh sách dự thi" in r.json()["detail"]
    assert c.get(f"/exams/{co_ds}", headers=h["ad"]).status_code == 200


def test_lop_khong_ton_tai_va_lop_co_san(qt):
    c, conn, h, idA, _, _ = qt
    lop = tao_lop(conn)
    r = c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA, class_code=lop["ma"]))
    assert r.status_code == 201 and r.json()["class_id"] == lop["id"]
    n = conn.execute("SELECT count(*) AS n FROM classes").fetchone()["n"]
    assert c.post("/admin/exams", headers=h["ad"], json=than(class_code="KHONG-CO-LOP-NAY")).status_code == 422
    assert conn.execute("SELECT count(*) AS n FROM classes").fetchone()["n"] == n


def test_ds_quan_tri_khong_lo_mat_khau(qt):
    c, _, h, _, _, _ = qt
    for url in ("/admin/exams", "/admin/users"):
        t = c.get(url, headers=h["ad"]).text
        assert "password" not in t and "scrypt$" not in t


def test_demo_x_user_khong_phai_admin_bi_403(client):
    assert client.get("/admin/exams").status_code == 403
    assert client.get("/admin/exams", headers={"X-User": "admin"}).status_code == 200


def test_quan_tri_js_goi_dung_endpoint_va_cu_phap(client):
    import re
    import shutil
    import subprocess
    from conftest import ROOT
    js = (ROOT / "frontend" / "quan_tri.js").read_text(encoding="utf-8")
    paths = __import__("backend.main", fromlist=["app"]).app.openapi()["paths"]
    goi = set(re.findall(r"`(/(?:admin|exams|sheets|meta)[^`?]*)", js)) | set(re.findall(r'"(/(?:admin|exams|sheets|meta)[^"?]*)"', js))
    assert goi
    for m in goi:
        chuan = re.sub(r"(?<!/)\$\{[^}]+\}", "", re.sub(r"(?<=/)\$\{[^}]+\}", "{x}", m))
        assert any(re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", p), chuan) for p in paths), f"quan_tri.js gọi {m} nhưng API không có"
    assert 'id="nav-admin"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", str(ROOT / "frontend" / "quan_tri.js")], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_ngay_hop_le_qua_schema(qt):
    c, _, h, idA, _, _ = qt
    assert c.post("/admin/exams", headers=h["ad"], json=than(teacher_user_id=idA, exam_date="khong-phai-ngay")).status_code == 422
    assert date.fromisoformat(c.post("/admin/exams", headers=h["ad"], json=than(exam_date="2027-01-02")).json()["exam_date"]) == date(2027, 1, 2)
