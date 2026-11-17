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
