"""Lệnh AU – kiểm thử chuẩn bị bản công khai (tiêu chí docs/tieu_chi_trien_khai.md). Phần lớn KHÔNG cần CSDL."""
import json
import subprocess
import sys

import pytest

from conftest import ROOT


def chay_py(ma: str, env_them: dict | None = None) -> subprocess.CompletedProcess:
    """Chạy một đoạn Python trong tiến trình mới (app đọc biến môi trường lúc import) với môi trường sạch của các biến AU."""
    import os
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
