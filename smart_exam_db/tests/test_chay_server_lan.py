"""Lệnh Z – mặc định dọn ảnh tạm của tools/chay_server_lan.py. KHÔNG chạy máy chủ thật: uvicorn.run bị thay bằng hàm ghi lại tham số."""
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import chay_server_lan as CS  # noqa: E402


@pytest.fixture
def chay(monkeypatch, capsys):
    """Gọi CS.main() với argv cho trước; trả (giá trị ANH_XOA_TU_DONG lúc uvicorn được gọi, stdout)."""
    import uvicorn
    goi = {}

    def gia(*a, **k):
        goi["anh"] = os.environ.get("ANH_XOA_TU_DONG")
        goi["k"] = k
    monkeypatch.setattr(uvicorn, "run", gia)
    monkeypatch.chdir(ROOT)

    def _chay(*argv):
        monkeypatch.setenv("ANH_XOA_TU_DONG", "khong_dat")                   # giá trị lạ: phải bị ghi đè rõ ràng
        monkeypatch.setattr(sys, "argv", ["chay_server_lan.py", *argv])
        assert CS.main() == 0
        return goi.get("anh"), capsys.readouterr().out
    return _chay


# Trước lệnh Z: không cờ -> ANH_XOA_TU_DONG=1. Một test ghi lại hành vi đó (assert == "1") đã chạy ĐẠT trên mã cũ ngay trước khi sửa
# (30/10/2026, chưa commit – ghi trong data/_eval/bao_cao_gan_nhat.md của lệnh Z). Từ lệnh Z: mặc định TẮT.

def test_khong_co_co_thi_TAT_don_anh_va_in_trang_thai(chay):
    anh, out = chay()
    assert anh == "0"
    assert "Dọn ảnh tạm: TẮT (mặc định)" in out and "CẢNH BÁO" not in out


def test_khong_xoa_anh_van_chay_nhu_cu(chay):
    anh, out = chay("--khong-xoa-anh")
    assert anh == "0" and "Dọn ảnh tạm: TẮT" in out


def test_chi_bat_khi_co_co_bat_don_anh_va_canh_bao_ro(chay):
    anh, out = chay("--bat-don-anh")
    assert anh == "1"
    assert "CẢNH BÁO: DỌN ẢNH TẠM ĐANG BẬT (--bat-don-anh)" in out and "kỳ thi thật" in out


def test_hai_co_trai_nghia_bi_tu_choi(chay):
    with pytest.raises(SystemExit) as e:
        chay("--bat-don-anh", "--khong-xoa-anh")
    assert e.value.code == 2


def test_chi_in_khong_chay_may_chu_van_in_trang_thai(monkeypatch, capsys):
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: pytest.fail("không được chạy máy chủ"))
    monkeypatch.setattr(sys, "argv", ["chay_server_lan.py", "--chi-in"])
    assert CS.main() == 0
    assert "Dọn ảnh tạm: TẮT (mặc định)" in capsys.readouterr().out


def test_tai_lieu_chay_server_khong_bat_don_anh():
    """Kịch bản demo (nơi có lệnh để chạy): mọi dòng nhắc tới --bat-don-anh phải CẢNH BÁO (chủ ý / cảnh báo) hoặc CẤM dùng.
    CLAUDE.md (mô tả dài): phải có câu cảnh báo "chỉ thêm --bat-don-anh khi chủ ý"."""
    for p in (ROOT / "docs" / "kich_ban_demo_bao_ve.md", ROOT / "docs" / "kich_ban_demo.md"):
        for dong in p.read_text(encoding="utf-8").splitlines():
            if "--bat-don-anh" in dong:
                d = dong.lower()
                assert any(m in d for m in ("chủ ý", "cảnh báo", "không thêm", "không dùng", "không bao giờ dùng")), f"{p.name}: {dong.strip()[:120]}"
    assert "chỉ thêm `--bat-don-anh` khi chủ ý" in (ROOT.parent / "CLAUDE.md").read_text(encoding="utf-8")
