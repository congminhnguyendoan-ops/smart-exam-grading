"""Kiểm thử giao diện demo (HTML + JS thuần) và các endpoint thêm cho nó. Chạy trên CSDL thật trong giao dịch ROLLBACK."""
import re
import shutil
import subprocess

import pytest

from backend import loi_khuyen
from cv_engine.preprocessing import MA_LY_DO
from conftest import ROOT
from test_backend_api import anh_trang, can_anh, tai, tao_de, them_sv

FRONTEND = ROOT / "frontend"


def test_goc_chuyen_sang_giao_dien(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/app/"


def test_phuc_vu_trang_tinh(client):
    r = client.get("/app/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "Smart Exam" in r.text
    for f in ("app.js", "style.css"):
        assert client.get(f"/app/{f}").status_code == 200
    assert client.get("/app/khong_co.js").status_code == 404
    assert client.get("/health").status_code == 200                       # API vẫn chạy cạnh thư mục tĩnh


def test_trang_tinh_tham_chieu_dung_file_va_dung_endpoint(client):
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for ref in re.findall(r'(?:src|href)="([a-z.]+\.(?:js|css))"', html):
        assert (FRONTEND / ref).exists(), ref
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    paths = client.get("/openapi.json").json()["paths"]
    # mọi đường dẫn API mà JS gọi phải có trong OpenAPI (đổi ${...} thành {tham_so})
    for m in set(re.findall(r"`(/(?:exams|sheets|meta)[^`?]*)", js)) | set(re.findall(r'"(/(?:exams|sheets|meta)[^"?]*)"', js)):
        chuan = re.sub(r"(?<!/)\$\{[^}]+\}", "", re.sub(r"(?<=/)\$\{[^}]+\}", "{x}", m))   # ${..} đầu đoạn = tham số, còn lại = query
        assert any(re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", p), chuan) for p in paths), f"JS gọi {m} nhưng API không có"


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để kiểm cú pháp JS")
def test_js_dung_cu_phap():
    r = subprocess.run(["node", "--check", str(FRONTEND / "app.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_ly_do_tu_choi_day_du_co_loi_khuyen(client):
    r = client.get("/meta/reject-reasons")
    assert r.status_code == 200
    d = r.json()
    assert set(d) == set(MA_LY_DO) and set(loi_khuyen.LOI_KHUYEN) == set(MA_LY_DO)
    for ma, v in d.items():
        assert v["message"] == MA_LY_DO[ma] and len(v["advice"]) > 10


def test_danh_sach_phieu_co_them_truong(client, conn_thu):
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    ok = tai(client, eid, "0002_C2").json()["sheet_id"]
    bi_tu_choi = tai(client, eid, "trang", du_lieu=anh_trang()).json()
    assert bi_tu_choi["status"] == "rejected"
    ds = {p["sheet_id"]: p for p in client.get(f"/exams/{eid}/sheets").json()}
    a, b = ds[ok], ds[bi_tu_choi["sheet_id"]]
    assert a["status"] == "needs_review" and a["student_name"] and a["detected_exam_code"] and a["official_score"] is None
    assert a["raw_score"] is not None and a["result_status"] is None
    assert b["status"] == "rejected" and b["reject_message"] == MA_LY_DO[b["reject_code"]] and b["raw_score"] is None


def test_luong_f1_den_f4_qua_api(client, conn_thu):
    """Đúng chuỗi lời gọi mà giao diện thực hiện: tải → danh sách → chi tiết → câu cần xem → ảnh cắt → duyệt → chính thức."""
    can_anh("0002_C2")
    them_sv(conn_thu, "795125")
    eid = tao_de(client)
    sid = tai(client, eid, "0002_C2").json()["sheet_id"]
    assert client.get(f"/exams/{eid}/sheets?status=needs_review").json()[0]["sheet_id"] == sid
    assert client.get(f"/sheets/{sid}/image?kind=aligned").status_code == 200
    for c in client.get(f"/sheets/{sid}/review-questions").json():
        img = client.get(f"/sheets/{sid}/questions/{c['question_no']}/image")
        assert img.status_code == 200 and img.headers["content-type"] == "image/png"
        r = client.post(f"/sheets/{sid}/questions/{c['question_no']}/review", json={"action": "set", "selected_options": "A"})
        assert r.status_code == 200
    v = client.get(f"/sheets/{sid}").json()
    assert v["status"] == "graded" and v["score"]["official"] is not None and v["score"]["result_status"] == "confirmed"
    assert client.get(f"/exams/{eid}").json()["sheets"]["da_cham"] == 1
