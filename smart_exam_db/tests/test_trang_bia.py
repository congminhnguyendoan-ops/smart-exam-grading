import shutil
import subprocess
import uuid
from dataclasses import replace

import cv2
import numpy as np
import pytest

from backend import demo
from backend.config import LoiCauHinh, dia_chi_goc_hop_le
from conftest import ROOT
from test_dang_nhap import bang_moi, client_on, dn, tao_user  # noqa: F401 – fixture dùng lại

DAP_AN = demo.khoa_demo("101", 40)


def doc_pdf(pdf: bytes) -> tuple[str, str]:
    import pymupdf
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    assert len(doc) == 1
    pix = doc[0].get_pixmap(dpi=150)
    anh = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
    return cv2.QRCodeDetector().detectAndDecode(anh)[0], doc[0].get_text()


@pytest.fixture
def bia(client_on, bang_moi):
    c, conn = client_on, bang_moi
    ad, _ = tao_user(conn, "admin")
    gA, idA = tao_user(conn)
    gB, _ = tao_user(conn)
    sv, _ = tao_user(conn, "student")
    h = {"ad": dn(c, ad), "A": dn(c, gA), "B": dn(c, gB), "sv": dn(c, sv)}
    ten = "Giữa kỳ trang bìa " + uuid.uuid4().hex[:6]
    e = c.post("/admin/exams", headers=h["ad"], json={"exam_title": ten, "subject_code": "TB" + uuid.uuid4().hex[:6].upper(), "subject_name": "Môn bìa",
                                                      "exam_date": "2026-11-20", "num_questions": 40, "teacher_user_id": idA,
                                                      "codes": [{"code": "101", "answers": DAP_AN}]})
    assert e.status_code == 201, e.text
    ho_ten = conn.execute("SELECT full_name FROM users WHERE user_id = %s", (idA,)).fetchone()["full_name"]
    return c, h, e.json()["exam_id"], ten, ho_ten


def test_trang_bia_qr_mac_dinh_lay_tu_yeu_cau(bia):
    c, h, eid, ten, ho_ten = bia
    r = c.get(f"/exams/{eid}/cover.pdf", headers=h["A"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    qr, chu = doc_pdf(r.content)
    assert qr == f"http://testserver/m?kythi={eid}"
    phang = " ".join(chu.split())
    assert ten in phang and f"Mã kỳ thi: {eid}" in phang and ho_ten in phang and "20/11/2026" in phang and "101" in phang
    assert DAP_AN not in chu.replace("\n", "") and "CẢNH BÁO" in phang
    assert c.get(f"/exams/{eid}/cover.pdf", headers=h["ad"]).status_code == 200


def test_trang_bia_dung_public_base_url(bia):
    from backend.main import app, get_cau_hinh
    c, h, eid, _, _ = bia
    app.dependency_overrides[get_cau_hinh] = lambda: replace(c.cfg, public_base_url="https://thi.example.edu.vn/smartexam")
    qr, chu = doc_pdf(c.get(f"/exams/{eid}/cover.pdf", headers=h["A"]).content)
    assert qr == f"https://thi.example.edu.vn/smartexam/m?kythi={eid}" and "CẢNH BÁO" not in chu


def test_trang_bia_ngoai_quyen(bia):
    c, h, eid, ten, _ = bia
    r = c.get(f"/exams/{eid}/cover.pdf", headers=h["B"])
    assert r.status_code == 404 and r.json()["detail"] == f"Không có kỳ thi {eid}." and ten not in r.text
    assert c.get(f"/exams/{eid}/cover.pdf", headers=h["sv"]).status_code == 403
    assert c.get(f"/exams/{eid}/cover.pdf").status_code == 401
    assert c.get("/exams/999999999999/cover.pdf", headers=h["ad"]).status_code == 404


def test_kythi_ngoai_quyen_khong_lo_ten(bia):
    c, h, eid, ten, _ = bia
    assert eid in {e["exam_id"] for e in c.get("/exams", headers=h["A"]).json()}
    assert eid not in {e["exam_id"] for e in c.get("/exams", headers=h["B"]).json()}
    for hd in (h["A"], {}):
        r = c.get(f"/m?kythi={eid}", headers=hd)
        assert r.status_code == 200 and ten not in r.text and "/app/m_kythi.js" in r.text
    assert c.get("/app/m_kythi.js").status_code == 200


def test_dia_chi_goc_cau_hinh():
    assert dia_chi_goc_hop_le("") == ""
    assert dia_chi_goc_hop_le(" https://thi.truong.edu.vn/ ") == "https://thi.truong.edu.vn"
    assert dia_chi_goc_hop_le("http://192.168.1.5:8000") == "http://192.168.1.5:8000"
    assert dia_chi_goc_hop_le("https://x.vn/se/") == "https://x.vn/se"
    for sai in ("thi.truong.edu.vn", "ftp://x.vn", "https://x.vn/a?b=1", "javascript:alert(1)", "https://x.vn/<s>"):
        with pytest.raises(LoiCauHinh):
            dia_chi_goc_hop_le(sai)


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để chạy test JS")
def test_m_kythi_node():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "m_kythi.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    for f in ("m.js", "m_kythi.js"):
        r = subprocess.run(["node", "--check", str(ROOT / "frontend" / f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_m_js_dung_m_kythi_va_bo_tham_so_sau_khi_chon():
    js = (ROOT / "frontend" / "m.js").read_text(encoding="utf-8")
    assert "MKyThi.docThamSo(location.search)" in js and "MKyThi.chonTuDanhSach" in js and "thongBaoLoi(404)" in js
    assert "history.replaceState" in js
    html = (ROOT / "frontend" / "m.html").read_text(encoding="utf-8")
    assert html.index("/app/m_kythi.js") < html.index("/app/m.js")
