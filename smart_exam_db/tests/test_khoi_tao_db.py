"""Lệnh AU (T5): tools/khoi_tao_db_san_xuat.py. Phần cần CSDL chạy trong schema tạm + ROLLBACK (conn_thu: SKIP nếu không có CSDL)."""
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import khoi_tao_db_san_xuat as K  # noqa: E402


def test_chi_chay_ba_tep_nen_khong_seed_khong_demo():
    assert K.FILE_NEN == ["01_schema.sql", "02_functions_triggers.sql", "03_views.sql"]
    assert not any("seed" in f or "demo" in f for f in K.FILE_NEN)
    ma = (ROOT / "tools" / "khoi_tao_db_san_xuat.py").read_text(encoding="utf-8")
    assert "execute" in ma and ".read_text" in ma
    # 04_seed / 05_demo chỉ được NHẮC trong chú thích / chuỗi cảnh báo, không nằm trong danh sách tệp chạy
    assert "04_seed.sql\", " not in ma and "FILE_NEN = [" in ma


def test_tao_admin_can_ap_dung():
    with pytest.raises(SystemExit) as e:
        K.main(["--tao-admin", "ten_a"])
    assert e.value.code == 2


def test_thu_schema_tam_dat_va_rollback(conn_thu):
    r = K.thu_schema_tam()
    assert r["dat"], r
    assert r["trinh_tu"][:3] == K.FILE_NEN and [x for x in r["trinh_tu"][3:]] == [f.name for f in K.migrate.ds_file()]
    assert r["schema_con_lai_sau_rollback"] == 0


def test_tao_admin_khong_ghi_de_tai_khoan_co_san(conn_thu):
    conn_thu.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES ('ad_co_san_au', 'x@y.z', 'scrypt$hash-giu-nguyen', 'Cũ', 'admin')")
    with pytest.raises(SystemExit) as e:
        K.tao_admin(conn_thu, "AD_CO_SAN_AU", None, None)
    assert "đã có" in str(e.value)
    assert conn_thu.execute("SELECT password_hash FROM users WHERE username = 'ad_co_san_au'").fetchone()["password_hash"] == "scrypt$hash-giu-nguyen"


def test_tao_admin_moi_dung_vai_tro_va_mat_khau_ngau_nhien(conn_thu):
    from backend import auth
    mk1 = K.tao_admin(conn_thu, "ad_moi_au_1", None, None)
    mk2 = K.tao_admin(conn_thu, "ad_moi_au_2", "a@b.c", "Họ Tên")
    assert mk1 != mk2 and auth.mat_khau_hop_le(mk1) is None
    h = conn_thu.execute("SELECT password_hash, role::text AS r FROM users WHERE username = 'ad_moi_au_1'").fetchone()
    assert h["r"] == "admin" and auth.kiem_mat_khau(mk1, h["password_hash"]) and mk1 not in h["password_hash"]
    with pytest.raises(SystemExit):
        K.tao_admin(conn_thu, "co khoang trang", None, None)
