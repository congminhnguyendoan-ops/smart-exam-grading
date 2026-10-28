"""Lệnh F3 (số phiếu ở ô chọn kỳ thi được làm mới) và F4 (khôi phục danh sách tờ ở /m sau khi tải lại). Logic hàng đợi: tests/js/hang_doi.test.js (F4);
giao diện thật: tools/thu_lenh_f.py (Playwright, chỉ ROLLBACK). CSDL thật trong giao dịch ROLLBACK."""
import re

from conftest import ROOT
from test_backend_api import anh_trang, tai, tao_de


def test_f3_so_phieu_o_chon_ky_thi_khop_so_phieu_sau_khi_tai(client):
    """Ô chọn kỳ thi lấy số từ GET /exams (so_phieu); giao diện làm mới nó bằng GET /exams/{id} (sheets.tong) sau mỗi lần tải / duyệt. Hai nguồn phải khớp."""
    eid = tao_de(client, n=10, ma_de=("101",))
    ds = lambda: next(e for e in client.get("/exams").json() if e["exam_id"] == eid)       # noqa: E731
    assert ds()["so_phieu"] == 0 and client.get(f"/exams/{eid}").json()["sheets"]["tong"] == 0
    assert tai(client, eid, "trang", du_lieu=anh_trang()).status_code == 201               # ảnh trắng: bị từ chối nhưng vẫn là một phiếu
    assert ds()["so_phieu"] == 1 and client.get(f"/exams/{eid}").json()["sheets"]["tong"] == 1


def test_f3_giao_dien_lam_moi_nhan_ky_thi_moi_lan_nap_chi_tiet():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "function lamMoiNhanKyThi" in js and "const nhanKyThi" in js
    nap = js[js.index("async function napChiTietKyThi"):]
    nap = nap[:nap.index("\n}\n")]
    assert "lamMoiNhanKyThi(e)" in nap                                    # mọi chỗ gọi napChiTietKyThi (tải xong, duyệt, thăm dò 4 s) đều làm mới nhãn
    assert js.count("await napChiTietKyThi()") >= 4                        # tải xong · đổi kỳ thi · duyệt · thăm dò


def test_f4_m_js_luu_sieu_du_lieu_o_session_storage_khong_token_khong_anh():
    bo_cmt = lambda p: re.sub(r"/\*.*?\*/|^\s*//.*$", "", (ROOT / "frontend" / p).read_text(encoding="utf-8"), flags=re.S | re.M)   # noqa: E731
    js = bo_cmt("m.js")
    assert 'KHOA_PHIEN = "m_hang_doi"' in js and "sessionStorage.setItem(KHOA_PHIEN" in js and "khoiPhucPhien" in js
    luu = js[js.index("function luuPhien"):js.index("async function traCuuPhieu")]
    assert "xuatSieuDuLieu()" in luu and "token" not in luu.lower() and ".file" not in luu          # chỉ siêu dữ liệu
    assert "localStorage" not in js
    assert "removeItem(KHOA_PHIEN)" in js                                  # đăng xuất / người khác đăng nhập: xoá
    assert "/sheets/${id}" in js                                           # hỏi lại trạng thái qua API sẵn có
