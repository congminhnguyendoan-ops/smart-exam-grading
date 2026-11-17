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
