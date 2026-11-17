"""Lệnh AU – kiểm thử chuẩn bị bản công khai (tiêu chí docs/tieu_chi_trien_khai.md). Phần lớn KHÔNG cần CSDL."""
import json
import subprocess
import sys

import pytest

from conftest import ROOT


def chay_py(ma: str, env_them: dict | None = None) -> subprocess.CompletedProcess:
    """Chạy một đoạn Python trong tiến trình mới (app đọc biến môi trường lúc import) với môi trường sạch của các biến AU."""
    import os
    from pathlib import Path
    env = {k: v for k, v in os.environ.items() if k not in ("DOCS_ENABLED", "MOI_TRUONG", "FORWARDED_ALLOW_IPS")}
    env.update(env_them or {})
    return subprocess.run([sys.executable, "-c", ma], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)


MA_DOCS = ("from fastapi.testclient import TestClient\nfrom backend.main import app\nc = TestClient(app)\n"
           "import json\nprint(json.dumps([c.get(p).status_code for p in ('/docs', '/redoc', '/openapi.json')]))")


# ------------------------------------------------------------------------------------------------ T1
@pytest.mark.parametrize("env,mong", [({}, [404, 404, 404]), ({"DOCS_ENABLED": "0"}, [404, 404, 404]), ({"DOCS_ENABLED": "1"}, [200, 200, 200])])
def test_t1_docs_theo_bien(env, mong):
    r = chay_py(MA_DOCS, env)
    assert r.returncode == 0, r.stderr[-400:]
    assert json.loads(r.stdout.strip().splitlines()[-1]) == mong


def test_t1_health_cong_khai_chi_trang_thai(client, monkeypatch):
    r = client.get("/health")                                     # conftest đặt HEALTH_CHI_TIET=1 (test cũ) -> có chi tiết
    assert r.status_code == 200 and r.json()["omr_model"].startswith("omr_m1-")
    from backend import main
    cfg = main.app.state.cfg
    monkeypatch.setattr(main.app.state, "cfg", type(cfg)(**{**cfg.__dict__, "health_chi_tiet": False}))
    j = client.get("/health").json()
    assert j == {"status": "ok", "db": "ok"}                      # không phiên bản, không SHA / tên mô hình


# ------------------------------------------------------------------------------------------------ T2
MA_PROXY = '''
import json
from fastapi.testclient import TestClient
from backend import main
from backend.main import app, get_cau_hinh, get_conn


class _Kq:
    def fetchone(self): return None          # không có người dùng -> mỗi lần là "sai" (không cần CSDL)


class _Conn:
    def execute(self, *a, **k): return _Kq()


app.dependency_overrides[get_conn] = lambda: _Conn()
from types import SimpleNamespace
app.dependency_overrides[get_cau_hinh] = lambda: SimpleNamespace(auth_mode="on", auth_secret="k" * 40, session_hours=8.0, cookie_secure=True)


def thu(client_ip, xff_list):
    """Gửi lần lượt các yêu cầu đăng nhập sai; trả danh sách mã HTTP."""
    c = TestClient(app, client=(client_ip, 5000))
    return [c.post("/auth/login", json={"username": "nguoi_la", "password": "sai-mat-khau"},
                   headers={"X-Forwarded-For": x} if x else {}).status_code for x in xff_list]


kq = {}
kq["tin_cay_A_5_sai_roi_khoa"] = thu("10.0.0.1", ["203.0.113.1"] * 6)                    # proxy tin cậy, cùng người dùng thật A -> lần 6 bị 429
kq["tin_cay_B_khong_bi_khoa_theo_A"] = thu("10.0.0.1", ["203.0.113.2"])                  # người dùng thật B qua cùng proxy -> 401 (không dồn khoá)
kq["khong_tin_gia_mao_khong_ne_khoa"] = thu("10.9.9.9", [f"198.51.100.{i}" for i in range(1, 8)])   # nơi KHÔNG tin: đổi X-Forwarded-For liên tục vẫn bị khoá theo IP kết nối
print(json.dumps(kq))
'''


def test_t2_proxy_tin_cay_khoa_theo_ip_that_va_bo_qua_nguon_la():
    r = chay_py(MA_PROXY, {"FORWARDED_ALLOW_IPS": "10.0.0.1"})
    assert r.returncode == 0, r.stderr[-600:]
    kq = json.loads(r.stdout.strip().splitlines()[-1])
    assert kq["tin_cay_A_5_sai_roi_khoa"] == [401] * 5 + [429]
    assert kq["tin_cay_B_khong_bi_khoa_theo_A"] == [401]
    assert kq["khong_tin_gia_mao_khong_ne_khoa"] == [401] * 5 + [429, 429]


def test_t2_khong_dat_bien_thi_bo_qua_header_hoan_toan():
    r = chay_py(MA_PROXY, {"FORWARDED_ALLOW_IPS": ""})
    kq = json.loads(r.stdout.strip().splitlines()[-1])
    assert kq["tin_cay_A_5_sai_roi_khoa"] == [401] * 5 + [429]        # khoá theo IP kết nối 10.0.0.1
    assert kq["tin_cay_B_khong_bi_khoa_theo_A"] == [429]              # B bị chung khoá với A (mặc định không tin header) – đúng hành vi LAN cũ


# ------------------------------------------------------------------------------------------------ T3
import io
import struct
import zlib
from dataclasses import replace

from backend import kiem_anh
from test_backend_api import anh_trang, tai, tao_de


def png_tieu_de(rong: int, cao: int) -> bytes:
    """PNG chỉ có chữ ký + IHDR + IEND (Pillow đọc được kích thước từ tiêu đề; không có dữ liệu điểm ảnh)."""
    def chunk(loai, d):
        return struct.pack(">I", len(d)) + loai + d + struct.pack(">I", zlib.crc32(loai + d) & 0xFFFFFFFF)
    return kiem_anh.CHU_KY_PNG + chunk(b"IHDR", struct.pack(">IIBBBBB", rong, cao, 8, 0, 0, 0, 0)) + chunk(b"IEND", b"")


class _DocDem(io.BytesIO):
    """Đếm tổng byte đã bị đọc ra – để chứng minh dừng sớm."""
    da_doc = 0

    def read(self, n=-1):
        d = super().read(n)
        self.da_doc += len(d)
        return d


def test_t3_doc_tep_dung_som_khi_vuot_gioi_han():
    tep = _DocDem(b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024))
    with pytest.raises(kiem_anh.TepQuaLon) as e:
        kiem_anh.doc_tep_gioi_han(tep, 1)
    assert e.value.ma_http == 413 and "1 MB" in str(e.value)
    assert tep.da_doc <= 2 * 1024 * 1024 + 10                       # KHÔNG đọc hết 5 MB: dừng ở đoạn đầu tiên vượt 1 MB


def test_t3_tep_qua_lon_413_theo_content_length(client, monkeypatch):
    from backend import main
    monkeypatch.setattr(main.app.state, "cfg", replace(main.app.state.cfg, gioi_han_anh_mb=1))
    eid = tao_de(client)
    r = tai(client, eid, "to", b"\xff\xd8\xff" + b"0" * (3 * 1024 * 1024))
    assert r.status_code == 413 and "1 MB" in r.json()["detail"]


def test_t3_than_chunked_khong_content_length_cung_bi_chan(client, monkeypatch):
    from backend import main
    monkeypatch.setattr(main.app.state, "cfg", replace(main.app.state.cfg, gioi_han_anh_mb=1))
    eid = tao_de(client)
    boundary = "bb"
    dau = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode()

    def sinh():
        yield dau
        for _ in range(4):
            yield b"\xff\xd8\xff" + b"0" * (1024 * 1024)
        yield f"\r\n--{boundary}--\r\n".encode()

    r = client.post(f"/exams/{eid}/sheets", content=sinh(), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert r.status_code == 413


def test_t3_lo_qua_nhieu_anh_413(client, cau_hinh_thu):
    from backend.main import app, get_cau_hinh
    app.dependency_overrides[get_cau_hinh] = lambda: replace(cau_hinh_thu, max_anh_moi_lo=2)
    eid = tao_de(client)
    files = [("files", (f"{i}.jpg", anh_trang(), "image/jpeg")) for i in range(3)]
    r = client.post(f"/exams/{eid}/sheets/batch", files=files)
    assert r.status_code == 413 and "tối đa 2 ảnh" in r.json()["detail"]
    r2 = client.post(f"/exams/{eid}/sheets/batch", files=files[:2])          # đúng giới hạn thì qua
    assert r2.status_code == 201 and r2.json()["tong"] == 2


def test_t3_anh_qua_nhieu_diem_anh_422(client):
    eid = tao_de(client)
    r = tai(client, eid, "bom", png_tieu_de(10000, 10000))                    # 100 triệu điểm ảnh > 60 triệu
    assert r.status_code == 422 and "điểm ảnh" in r.json()["detail"] and "100" in r.json()["detail"]
    assert tai(client, eid, "ok", png_tieu_de(1000, 1000)).status_code != 422  # 1 triệu điểm: qua kiểm (sau đó bị từ chối vì không có nội dung phiếu / hỏng)


@pytest.mark.parametrize("du_lieu", [b"day khong phai anh", b"<html>" + b"x" * 100, b"PK\x03\x04" + b"0" * 50, b"\x89PNG", b""])
def test_t3_duoi_jpg_nhung_noi_dung_khong_phai_anh_422(client, du_lieu):
    eid = tao_de(client)
    r = tai(client, eid, "gia", du_lieu)                                       # tên tệp "gia.jpg", Content-Type image/jpeg
    assert r.status_code == 422, r.text
    assert "ảnh" in r.json()["detail"]


def test_t3_ba_loai_anh_duoc_nhan_dang_theo_chu_ky():
    import cv2
    import numpy as np
    a = np.full((50, 40), 200, np.uint8)
    assert kiem_anh.kiem_noi_dung_anh(cv2.imencode(".jpg", a)[1].tobytes(), 60_000_000)[0] == "jpeg"
    assert kiem_anh.kiem_noi_dung_anh(cv2.imencode(".png", a)[1].tobytes(), 60_000_000) == ("png", 40, 50)
    heic = pytest.importorskip("pillow_heif")
    from PIL import Image
    heic.register_heif_opener()
    b = io.BytesIO()
    Image.fromarray(a).save(b, format="HEIF")
    assert kiem_anh.kiem_noi_dung_anh(b.getvalue(), 60_000_000)[0] == "heic"


def test_t3_dat_image_max_image_pixels():
    from PIL import Image
    cu = Image.MAX_IMAGE_PIXELS
    try:
        kiem_anh.ap_dung_gioi_han_diem_anh(12_345_678)
        assert Image.MAX_IMAGE_PIXELS == 12_345_678
    finally:
        Image.MAX_IMAGE_PIXELS = cu


# ------------------------------------------------------------------------------------------------ T4 / T4b
from backend.config import LoiCauHinh, lay_cau_hinh

GOC_ENV = {"DATABASE_URL": "postgresql://x:y@localhost/z", "AUTH_MODE": "on", "AUTH_SECRET": "s" * 40, "COOKIE_SECURE": "1"}


def _dat_env(monkeypatch, **bien):
    for k in ("MOI_TRUONG", "WEB_CONCURRENCY", "COOKIE_SECURE", "AUTH_SECRET", "AUTH_MODE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in {**GOC_ENV, **bien}.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_t4_production_hop_le_khoi_dong_duoc(monkeypatch):
    _dat_env(monkeypatch, MOI_TRUONG="production")
    c = lay_cau_hinh()
    assert c.moi_truong == "production" and c.cookie_secure and c.auth_mode == "on"


@pytest.mark.parametrize("sai,noi_dung", [({"AUTH_MODE": "demo"}, "AUTH_MODE"), ({"COOKIE_SECURE": "0"}, "COOKIE_SECURE"), ({"COOKIE_SECURE": None}, "COOKIE_SECURE"),
                                          ({"AUTH_SECRET": "ngan" * 5}, "AUTH_SECRET"), ({"WEB_CONCURRENCY": "2"}, "1 worker")])
def test_t4_production_tu_choi_cau_hinh_khong_an_toan(monkeypatch, sai, noi_dung):
    _dat_env(monkeypatch, MOI_TRUONG="production", **sai)
    with pytest.raises(LoiCauHinh) as e:
        lay_cau_hinh()
    assert noi_dung in str(e.value) and "s" * 40 not in str(e.value)          # không lộ giá trị bí mật


def test_t4_production_gom_het_loi_mot_lan(monkeypatch):
    _dat_env(monkeypatch, MOI_TRUONG="production", AUTH_MODE="demo", COOKIE_SECURE="0", AUTH_SECRET="x")
    with pytest.raises(LoiCauHinh) as e:
        lay_cau_hinh()
    assert all(k in str(e.value) for k in ("AUTH_MODE", "COOKIE_SECURE", "AUTH_SECRET"))


@pytest.mark.parametrize("env", [{}, {"AUTH_MODE": "demo", "COOKIE_SECURE": "0", "WEB_CONCURRENCY": "4"}])
def test_t4_mac_dinh_khong_doi_hanh_vi_lan(monkeypatch, env):
    _dat_env(monkeypatch, **env)                     # không đặt MOI_TRUONG -> mọi kiểm tra production KHÔNG chạy
    assert lay_cau_hinh().moi_truong == ""


def test_t4_moi_truong_sai_gia_tri(monkeypatch):
    _dat_env(monkeypatch, MOI_TRUONG="prod")
    with pytest.raises(LoiCauHinh):
        lay_cau_hinh()


def test_t4_tep_mau_production_du_bien_bat_buoc_va_vuot_kiem_tra(monkeypatch):
    mau = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    bien = dict(l.split("=", 1) for l in mau.splitlines() if l and not l.startswith("#") and "=" in l)
    for k in ("MOI_TRUONG", "DATABASE_URL", "AUTH_SECRET", "AUTH_MODE", "COOKIE_SECURE", "PUBLIC_BASE_URL", "CHAM_DONG_THOI", "DOCS_ENABLED"):
        assert k in bien, k
    assert bien["MOI_TRUONG"] == "production" and bien["COOKIE_SECURE"] == "1" and bien["DOCS_ENABLED"] == "0" and bien["PUBLIC_BASE_URL"].startswith("https://")
    for k in ("MOI_TRUONG", "WEB_CONCURRENCY", "COOKIE_SECURE", "AUTH_SECRET", "AUTH_MODE", "PUBLIC_BASE_URL", "FORWARDED_ALLOW_IPS", "STORAGE_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k, v in bien.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(LoiCauHinh) as e:             # sao chép nguyên mẫu mà không đổi khoá -> bị từ chối (giá trị giữ chỗ "DOI_…" dài > 32 ký tự)
        lay_cau_hinh()
    assert "giá trị mẫu" in str(e.value)
    monkeypatch.setenv("AUTH_SECRET", "k" * 48)      # đổi khoá thật -> mẫu còn lại hợp lệ
    assert lay_cau_hinh().moi_truong == "production"


# ------------------------------------------------------------------------------------------------ T6 / T7 (kiểm TĨNH: máy có thể không chạy được Docker)
import ast
import fnmatch
import hashlib
import re as _re


def _khop_dockerignore(duong_dan: str, mau: list[str]) -> bool:
    """True nếu `duong_dan` (tương đối, dùng '/') BỊ LOẠI theo .dockerignore (mẫu sau thắng; '!' = giữ lại). Đủ cho các dạng dùng trong repo này."""
    bi_loai = False
    for dong in mau:
        dong = dong.strip()
        if not dong or dong.startswith("#"):
            continue
        phu_dinh = dong.startswith("!")
        m = dong[1:] if phu_dinh else dong
        if m.endswith("/"):
            m = m + "**"
        ok = False
        for g in (m, m[3:] if m.startswith("**/") else None):
            if g is None:
                continue
            re_ = "^" + _re.escape(g).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "(?:/.*)?$"
            if _re.match(re_, duong_dan):
                ok = True
        if ok:
            bi_loai = not phu_dinh
    return bi_loai


MAU_DI = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines() if (ROOT / ".dockerignore").exists() else []


@pytest.mark.parametrize("p", ["data/raw/0001_C1.jpg", "data/ground_truth.csv", "storage/uploads/1/ab/x.jpg", ".env", ".env.local", ".venv/Scripts/python.exe",
                               ".git/config", "tests/test_backend_api.py", "docs/ERD.png", "backend/__pycache__/main.cpython-314.pyc", "tools/ah_thu_dong_thoi.py",
                               "answer_sheet/demo_bv/phieu_demo_in.pdf", "Dockerfile", "backups/smart_exam_x.dump",
                               ".claude/settings.local.json", "answer_sheet/output/synthetic_photo.jpg", "answer_sheet/output/preview_phieu.png"])
def test_t6_dockerignore_loai_du_lieu_bi_mat_va_nang(p):
    assert _khop_dockerignore(p, MAU_DI), f"{p} KHÔNG bị loại khỏi image"


@pytest.mark.parametrize("p", ["backend/main.py", "backend/migrations/006_thu_hoi_token.sql", "cv_engine/omr.py", "frontend/index.html", "frontend/m.html",
                               "models/ocr_cnn.json", "models/omr_m1.json", "answer_sheet/output/layout.json", "answer_sheet/output/phieu_trang_300dpi.png",
                               "answer_sheet/output/phieu_trang_300dpi.json", "answer_sheet/fonts/DejaVuSans.ttf", "database/01_schema.sql",
                               "database/02_functions_triggers.sql", "database/03_views.sql", "tools/khoi_tao_db_san_xuat.py", "requirements-prod.txt",
                               ".env.production.example"])
def test_t6_dockerignore_giu_du_tep_can_de_chay(p):
    assert (ROOT / p).exists(), f"{p} không tồn tại trong repo"
    assert not _khop_dockerignore(p, MAU_DI), f"{p} bị loại nhầm khỏi image"


def test_t6_dockerfile_lenh_khoi_dong_va_an_toan():
    d = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "1"]' in d
    assert "USER app" in d and "MOI_TRUONG=production" in d and "HEALTHCHECK" in d and "requirements-prod.txt" in d
    assert "COPY . ." in d and ".env" not in d.replace("MOI_TRUONG", "").split("COPY . .")[1].split("RUN")[0]


def test_t6_compose_chi_caddy_mo_cong_va_db_khong_publish():
    c = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:17" in c and "pgdata:" in c and "storage:" in c and "caddy:2" in c
    assert len(_re.findall(r"^\s+ports:", c, _re.M)) == 1 and '"443:443"' in c and "5432:5432" not in c and "8000:8000" not in c


def test_t6_caddyfile_co_tls_gioi_han_than_va_proxy():
    c = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "reverse_proxy app:8000" in c and c.count("request_body") >= 3 and "max_size 26MB" in c and "{$PUBLIC_HOST" in c


def test_t6_requirements_prod_du_goi_cho_moi_import_cua_backend():
    """Mọi gói ngoài thư viện chuẩn mà backend/, cv_engine/, tools/khoi_tao_db_san_xuat.py import đều có trong requirements-prod.txt."""
    ten_goi = {"cv2": "opencv-python-headless", "PIL": "pillow", "dotenv": "python-dotenv", "multipart": "python-multipart", "pillow_heif": "pillow-heif"}
    chuan = {l.split("==")[0].strip().lower().replace("_", "-") for l in (ROOT / "requirements-prod.txt").read_text(encoding="utf-8").splitlines()
             if "==" in l and not l.startswith("#")}
    noi_bo = {"backend", "cv_engine", "tools", "answer_sheet"}
    can = set()
    for tep in [*(ROOT / "backend").glob("*.py"), *(ROOT / "cv_engine").glob("*.py"), ROOT / "tools" / "khoi_tao_db_san_xuat.py"]:
        for nut in ast.walk(ast.parse(tep.read_text(encoding="utf-8"))):
            mods = [a.name for a in nut.names] if isinstance(nut, ast.Import) else [nut.module] if isinstance(nut, ast.ImportFrom) and nut.level == 0 and nut.module else []
            for m in mods:
                goc = m.split(".")[0]
                if goc not in sys.stdlib_module_names and goc not in noi_bo and goc != "khoi_tao_db_san_xuat":
                    can.add(ten_goi.get(goc, goc).lower().replace("_", "-"))
    thieu = sorted(g for g in can if g not in chuan)
    assert not thieu, f"requirements-prod.txt thiếu: {thieu}"
    assert {"fastapi", "uvicorn", "numpy", "opencv-python-headless", "pillow", "pillow-heif", "psycopg", "python-multipart"} <= chuan


def test_t6_requirements_prod_khop_phien_ban_voi_freeze():
    freeze = {l.split("==")[0].lower().replace("_", "-"): l.split("==")[1].strip() for l in
              (ROOT / "requirements-freeze.txt").read_text(encoding="utf-8-sig").splitlines() if "==" in l}
    for l in (ROOT / "requirements-prod.txt").read_text(encoding="utf-8").splitlines():
        if "==" in l and not l.startswith("#"):
            ten, ver = l.split("==")
            ten = ten.lower().replace("_", "-")
            goc = "opencv-python" if ten == "opencv-python-headless" else ten
            assert freeze.get(goc) == ver.strip(), f"{ten}: prod {ver} ≠ freeze {freeze.get(goc)}"


def test_t7_mo_hinh_co_san_va_sha_dung():
    sha = hashlib.sha256((ROOT / "models" / "ocr_cnn.json").read_bytes()).hexdigest()
    assert sha.startswith("a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8"[:8]) and sha == "a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8"
    assert (ROOT / "models" / "omr_m1.json").stat().st_size > 0


def test_t7_health_chi_tiet_bao_dung_sha_mo_hinh(client):
    j = client.get("/health").json()                  # conftest đặt HEALTH_CHI_TIET=1 (chế độ nội bộ)
    assert j["ocr_model"] == "ocr_cnn-a151c078" and j["omr_model"].startswith("omr_m1-")


def test_t2_dai_mang_cidr_nhu_trong_docker_compose():
    r = chay_py(MA_PROXY.replace('"10.0.0.1"', '"172.28.0.5"'), {"FORWARDED_ALLOW_IPS": "172.28.0.0/24"})
    kq = json.loads(r.stdout.strip().splitlines()[-1])
    assert kq["tin_cay_A_5_sai_roi_khoa"] == [401] * 5 + [429] and kq["tin_cay_B_khong_bi_khoa_theo_A"] == [401]    # proxy trong dải được tin
    r2 = chay_py(MA_PROXY.replace('"10.0.0.1"', '"172.29.0.5"'), {"FORWARDED_ALLOW_IPS": "172.28.0.0/24"})
    kq2 = json.loads(r2.stdout.strip().splitlines()[-1])
    assert kq2["tin_cay_B_khong_bi_khoa_theo_A"] == [429]            # nguồn NGOÀI dải: bỏ qua header -> B dùng chung khoá theo IP kết nối


# ------------------------------------------------------------------------------------------------ V7 (lệnh AV): liên kết Swagger ở giao diện
import shutil


def test_v7_lien_ket_swagger_an_san_va_chi_hien_khi_co_openapi():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<span id="lk-docs-wrap" class="hidden"><br><a href="/docs" target="_blank">API (Swagger)</a></span>' in html      # ẩn mặc định
    assert '<script src="lien_ket_docs.js"></script>' in html
    js = (ROOT / "frontend" / "lien_ket_docs.js").read_text(encoding="utf-8")
    assert '"/openapi.json"' in js and 'classList.remove("hidden")' in js


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node")
def test_v7_js_logic_va_cu_phap():
    r = subprocess.run(["node", "--check", str(ROOT / "frontend" / "lien_ket_docs.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "lien_ket_docs.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-400:]


def test_v7_may_chu_phuc_vu_script_va_docs_404_mac_dinh(client):
    assert client.get("/app/lien_ket_docs.js").status_code == 200
    assert client.get("/app/").status_code == 200


def test_v2_ngu_canh_build_thuc_te_khong_con_du_lieu_rieng_tu():
    """Duyệt THẬT thư mục smart_exam_db/ (bỏ qua nhánh đã bị loại cả thư mục): tệp còn lại KHÔNG có ảnh / dump / .env / cấu hình cục bộ."""
    import os
    from pathlib import Path
    con_lai = []
    for goc, thu_muc, tep in os.walk(ROOT):
        rel_goc = Path(goc).relative_to(ROOT).as_posix()
        thu_muc[:] = [d for d in thu_muc if not _khop_dockerignore(f"{rel_goc}/{d}".lstrip("./") + "/x", MAU_DI) or d in ("storage",)]
        for f in tep:
            rel = (Path(goc) / f).relative_to(ROOT).as_posix()
            if not _khop_dockerignore(rel, MAU_DI):
                con_lai.append(rel)
    xau = [r for r in con_lai if r.lower().endswith((".jpg", ".jpeg", ".heic", ".dump", ".pdf", ".csv")) or Path(r).name.startswith(".env") and r != ".env.production.example"
           or r.endswith(".local.json") or r.startswith((".claude/", "data/", ".git/", ".venv/", "tests/", "docs/"))]
    assert not xau, f"còn vào image: {xau}"
    assert "models/ocr_cnn.json" in con_lai and "answer_sheet/output/phieu_trang_300dpi.png" in con_lai
