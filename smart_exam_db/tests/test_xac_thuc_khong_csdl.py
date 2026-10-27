"""Kiểm thử xác thực / phân quyền KHÔNG cần CSDL: băm mật khẩu, token, giới hạn thử sai, cấu hình, kiểm toán route (mọi endpoint
có xác thực; mọi endpoint theo id có kiểm quyền), giao diện tĩnh. Các test cần CSDL nằm ở test_dang_nhap.py."""
import inspect
import re

import pytest
from fastapi.routing import APIRoute

from backend import auth, main, nguoi_dung
from backend.config import LoiCauHinh, lay_cau_hinh
from conftest import ROOT

KHOA = "k" * 40


# ------------------------------------------------------------------------------------------------ mật khẩu
def test_bam_va_kiem_mat_khau():
    h = auth.bam_mat_khau("Mat-khau-dung-1")
    assert h.startswith("scrypt$16384$8$1$") and "Mat-khau" not in h
    assert auth.kiem_mat_khau("Mat-khau-dung-1", h) and not auth.kiem_mat_khau("Mat-khau-dung-2", h) and not auth.kiem_mat_khau("", h)
    assert auth.bam_mat_khau("Mat-khau-dung-1") != h                          # muối ngẫu nhiên mỗi lần
    assert auth.kiem_mat_khau("Mật khẩu có dấu", auth.bam_mat_khau("Mật khẩu có dấu"))


@pytest.mark.parametrize("hash_la", [None, "", "abc", "$2b$12$KIXQJ6vY0nZ0r8bB1rj3NuQm5YfV1N3x7n0gM1W6xFvX4v2Q9m3yS",    # chuỗi giả của 04_seed.sql
                                     "scrypt$x$8$1$AA$AA", "scrypt$16384$8$1$!!!$!!!", "scrypt$16384$8$1$AA"])
def test_hash_la_khong_nem_loi_va_khong_dang_nhap_duoc(hash_la):
    assert auth.kiem_mat_khau("bat-ky", hash_la) is False


def test_dung_so_sanh_hang_thoi_gian():
    src = inspect.getsource(auth.kiem_mat_khau)
    assert "hmac.compare_digest" in src and "==" not in src.replace("!=", "")


def test_luat_mat_khau_hop_le():
    assert auth.mat_khau_hop_le("abc") and auth.mat_khau_hop_le("x" * 201) and auth.mat_khau_hop_le("12345678") is None
    mk = {auth.mat_khau_ngau_nhien() for _ in range(20)}
    assert len(mk) == 20 and all(len(m) == 14 for m in mk)


# ------------------------------------------------------------------------------------------------ token
def test_token_dung_sai_het_han_va_bi_sua():
    h = auth.bam_mat_khau("mk-12345678")
    t = auth.tao_token(KHOA, 7, h, 8, bay_gio=1000.0)
    d = auth.doc_token(KHOA, t, bay_gio=1000.0 + 3600)
    assert d["u"] == 7 and d["e"] == 1000 + 8 * 3600
    assert auth.doc_token(KHOA, t, bay_gio=1000.0 + 8 * 3600 + 1) is None          # hết hạn
    assert auth.doc_token("khoa-khac-" + "z" * 30, t, bay_gio=1000.0) is None      # sai khoá
    ver, payload, ky = t.split(".")
    gia = auth._b64(b'{"u":1,"e":99999999999,"f":"x"}')
    assert auth.doc_token(KHOA, f"{ver}.{gia}.{ky}", bay_gio=1000.0) is None        # sửa payload, giữ chữ ký
    assert auth.doc_token(KHOA, f"{ver}.{payload}.{ky[:-2]}AA", bay_gio=1000.0) is None
    for rac in ("", "abc", "v1..", "v1.a.b", "v2." + payload + "." + ky, None):
        assert auth.doc_token(KHOA, rac or "", bay_gio=1000.0) is None


def test_doi_mat_khau_doi_dau_van_tay_token():
    h1, h2 = auth.bam_mat_khau("mk-cu-12345"), auth.bam_mat_khau("mk-moi-12345")
    assert auth.doc_token(KHOA, auth.tao_token(KHOA, 1, h1, 8))["f"] != auth.doc_token(KHOA, auth.tao_token(KHOA, 1, h2, 8))["f"]


# ------------------------------------------------------------------------------------------------ giới hạn thử sai
def test_gioi_han_5_lan_15_phut():
    g = auth.GioiHanDangNhap()
    k = ("gv", "1.2.3.4")
    for i in range(5):
        assert not g.bi_chan(k, bay_gio=100.0 + i)
        g.ghi_sai(k, bay_gio=100.0 + i)
    assert g.bi_chan(k, bay_gio=105.0)
    assert not g.bi_chan(("gv", "5.6.7.8"), bay_gio=105.0) and not g.bi_chan(("khac", "1.2.3.4"), bay_gio=105.0)     # theo (username, IP)
    assert not g.bi_chan(k, bay_gio=100.0 + 15 * 60 + 10)                                                          # hết cửa sổ 15 phút
    g.ghi_sai(k, bay_gio=2000.0)
    g.xoa(k)
    assert not g.bi_chan(k, bay_gio=2000.0)


def test_thong_bao_sai_duy_nhat():
    assert auth.THONG_BAO_SAI == "Sai tên đăng nhập hoặc mật khẩu."
    src = inspect.getsource(nguoi_dung.dang_nhap)
    assert src.count("ChuaDangNhap(") == 1 and "auth.kiem_gia()" in src            # một thông báo; tên không tồn tại vẫn tốn một phép scrypt


# ------------------------------------------------------------------------------------------------ cấu hình
def test_cau_hinh_thieu_auth_secret_bao_loi_ro(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost/z")
    monkeypatch.setenv("AUTH_MODE", "on")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(LoiCauHinh) as e:
        lay_cau_hinh()
    assert "AUTH_SECRET" in str(e.value)
    monkeypatch.setenv("AUTH_SECRET", "ngan")
    with pytest.raises(LoiCauHinh):
        lay_cau_hinh()
    monkeypatch.setenv("AUTH_SECRET", "s" * 40)
    c = lay_cau_hinh()
    assert c.auth_mode == "on" and c.session_hours == 8 and c.cookie_secure is False
    monkeypatch.setenv("COOKIE_SECURE", "1")
    monkeypatch.setenv("SESSION_HOURS", "2")
    assert lay_cau_hinh().cookie_secure is True and lay_cau_hinh().session_hours == 2
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.delenv("AUTH_SECRET")
    assert lay_cau_hinh().auth_mode == "demo"                                       # demo không cần khoá
    monkeypatch.setenv("AUTH_MODE", "tuy-tien")
    with pytest.raises(LoiCauHinh):
        lay_cau_hinh()


def test_mac_dinh_la_on_va_khong_co_khoa_mac_dinh_trong_code():
    import backend.config as cf
    src = inspect.getsource(cf)
    assert 'os.environ.get("AUTH_MODE", "on")' in src
    assert 'AUTH_SECRET", ""' in src and not re.search(r'AUTH_SECRET",\s*"[^"]{3,}"', src)
    assert "AUTH_SECRET" in (ROOT / ".env.example").read_text(encoding="utf-8") and "AUTH_MODE=on" in (ROOT / ".env.example").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ kiểm toán route
CONG_KHAI = {"/", "/health", "/meta/reject-reasons", "/auth/login", "/auth/logout"}      # "/" chỉ chuyển hướng tới /app/ (HTML + JS + CSS tĩnh, không dữ liệu)


def _phu_thuoc(dependant):
    for d in dependant.dependencies:
        yield d.call
        yield from _phu_thuoc(d)


def _routes_api():
    return [r for r in main.app.routes if isinstance(r, APIRoute)]


def test_moi_endpoint_tru_cong_khai_deu_co_xac_thuc():
    thieu = [f"{sorted(r.methods)} {r.path}" for r in _routes_api() if r.path not in CONG_KHAI and main.get_nguoi_dung not in set(_phu_thuoc(r.dependant))]
    assert not thieu, f"endpoint chưa yêu cầu đăng nhập: {thieu}"


def test_moi_endpoint_chi_danh_cho_giao_vien_tru_tai_khoan_ca_nhan():
    """/me, /me (PATCH), /me/password dùng được cho mọi vai trò đã đăng nhập; còn lại: admin / teacher (sinh viên 403)."""
    ca_nhan = {"/me", "/me/password"}
    sai = [r.path for r in _routes_api() if r.path not in CONG_KHAI | ca_nhan and main.giao_vien not in set(_phu_thuoc(r.dependant))]
    assert not sai, f"endpoint chưa chặn sinh viên: {sai}"


def test_moi_endpoint_theo_id_co_kiem_quyen_doi_tuong():
    """Mọi route có {exam_id} / {sheet_id} / {class_id} phải gọi phan_quyen.kiem_* trong thân hàm (chống IDOR)."""
    thieu = []
    for r in _routes_api():
        for tham, ham in (("{exam_id}", "kiem_ky_thi"), ("{sheet_id}", "kiem_phieu"), ("{class_id}", "kiem_lop")):
            if tham in r.path and f"phan_quyen.{ham}(" not in inspect.getsource(r.endpoint):
                thieu.append(f"{r.path} thiếu phan_quyen.{ham}")
    assert not thieu, thieu
    assert any("{exam_id}" in r.path for r in _routes_api()) and any("{sheet_id}" in r.path for r in _routes_api())
    # danh sách / tạo kỳ thi không theo id nhưng phải lọc / kiểm quyền lớp
    src = {r.path + "|" + ",".join(sorted(r.methods)): inspect.getsource(r.endpoint) for r in _routes_api()}
    assert "dieu_kien_ky_thi" in src["/exams|GET"] and "giai_lop_cho_ky_thi" in src["/exams|POST"]


def test_x_user_chi_co_hieu_luc_trong_demo():
    src = inspect.getsource(nguoi_dung.xac_thuc)
    phan_demo, phan_on = src.split('if cfg.auth_mode == "demo":')[1].split("if not token:")
    assert "x_user" in phan_demo and "x_user" not in phan_on


def test_truy_van_sql_dung_tham_so_khong_noi_chuoi():
    """Không có f-string / % / + nối dữ liệu người dùng vào conn.execute trong các module mới (chỉ nối hằng nội bộ có chú thích)."""
    for ten in ("auth", "nguoi_dung", "phan_quyen"):
        txt = (ROOT / "backend" / f"{ten}.py").read_text(encoding="utf-8")
        for m in re.finditer(r"execute\(\s*f[\"']", txt):
            dong = txt[m.start(): txt.index("\n", m.start() + 200)]
            assert "_LOP_CUA_TOI" in dong or "{dk}" in dong, f"{ten}: SQL f-string đáng ngờ: {dong[:120]}"
    for m in re.finditer(r"execute\([^)]*%\s*\(", (ROOT / "backend" / "nguoi_dung.py").read_text(encoding="utf-8")):
        pytest.fail("nối chuỗi bằng % trong SQL")


def test_khong_log_mat_khau_hay_token():
    for ten in ("auth", "nguoi_dung", "phan_quyen", "tai_khoan", "main"):
        txt = (ROOT / "backend" / f"{ten}.py").read_text(encoding="utf-8")
        for m in re.finditer(r"(log\.\w+|logging\.\w+|print)\(([^\n]*)", txt):
            if ten == "tai_khoan":
                continue                                                           # tài khoản mẫu --mau in mật khẩu MỘT lần (đã nêu trong tài liệu)
            assert not re.search(r"mat_khau|password|token|secret", m.group(2), re.I), f"{ten}: log có thể lộ bí mật: {m.group(0)}"


def test_cookie_phien_httponly_samesite_lax():
    src = inspect.getsource(main.dang_nhap)
    assert "httponly=True" in src and 'samesite="lax"' in src and "secure=cfg.cookie_secure" in src


# ------------------------------------------------------------------------------------------------ giao diện tĩnh
def test_giao_dien_co_trang_dang_nhap_ho_so_lop():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    for dau_hieu in ('id="userbox"', 'id="logout"', 'href="#/classes"', 'href="#/profile"'):
        assert dau_hieu in html, dau_hieu
    for dau_hieu in ("function manDangNhap", "function manHoSo", "function manLop", "function manSinhVienLop", "/auth/login", "/auth/logout", "/me/classes",
                     "/me/password", "r.status === 401", "e.dangNhap", "subject_name", "class_code"):
        assert dau_hieu in js, dau_hieu
    assert 'method: "PATCH"' in js


def test_giao_dien_khong_luu_token_o_trinh_duyet():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"(localStorage|sessionStorage)\.setItem\(\s*[\"'](token|jwt|session|se_session|auth)", js, re.I)
    assert not re.search(r"document\.cookie", js) and not re.search(r"Authorization", js)       # cookie HttpOnly: JS không đụng tới token
    assert js.count("localStorage.setItem(") == 1 and 'localStorage.setItem("examId"' in js        # chỉ nhớ kỳ thi đang chọn


def test_duong_dan_api_moi_trong_js_co_trong_openapi():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    paths = main.app.openapi()["paths"]
    for m in set(re.findall(r"[`\"](/(?:auth|me|classes)[^`\"?]*)", js)):
        chuan = re.sub(r"\$\{[^}]+\}", "{x}", m)
        assert any(re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", p), chuan) for p in paths), f"JS gọi {m} nhưng API không có"
    for p in ("/auth/login", "/auth/logout", "/me", "/me/password", "/me/classes", "/classes/{class_id}/students"):
        assert p in paths
