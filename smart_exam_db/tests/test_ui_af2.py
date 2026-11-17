"""Lệnh AF2 (01/11/2026): logic JS (node:test) + kiểm tệp tĩnh – nút hàng loạt chỉ nhiều ô / tô nhạt, giải thích câu mờ / vết,
bẫy Tab + Esc trong hộp, trả tiêu điểm về nút mở hộp, role="dialog" + aria-modal. Không cần CSDL."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


@pytest.mark.skipif(shutil.which("node") is None, reason="không có node để chạy test JS")
def test_duyet_nhanh_af2_node():
    r = subprocess.run(["node", "--test", str(ROOT / "tests" / "js" / "duyet_nhanh_af2.test.js")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"(#|ℹ) pass 4\b", r.stdout), r.stdout


def _ham(js: str, ten: str, ket: str) -> str:
    i = js.index(ten)
    return js[i:js.index(ket, i)]


def test_nut_va_giai_thich():
    f = _ham((FRONTEND / "app.js").read_text(encoding="utf-8"), "function khungNhanh", "const cauConLai")
    assert "DuyetNhanh.nhanNutHangLoat(hl.duoc.length)" in f and "${nhan ? " in f                    # 0 câu hợp lệ -> không có nút
    assert "Câu mờ / vết cần quyết định bằng mắt" in f and 'aria-haspopup="dialog"' in f
    assert "Xác nhận tất cả" not in f                                                                 # nhãn cũ (AF) đã bỏ


def test_hop_bay_tab_esc_tra_tieu_diem_aria():
    f = _ham((FRONTEND / "app.js").read_text(encoding="utf-8"), "function moXacNhanHangLoat", "/* AF1: phím tắt")
    assert 'setAttribute("role", "dialog")' in f and 'setAttribute("aria-modal", "true")' in f
    assert 'setAttribute("aria-labelledby", "dlg-hl-h")' in f and 'setAttribute("aria-describedby", "dlg-hl-canh-bao")' in f
    assert 'document.addEventListener("keydown", phimHop, true)' in f and 'document.removeEventListener("keydown", phimHop, true)' in f
    assert "DuyetNhanh.phimHop(" in f
    assert "const moTu = document.activeElement" in f and "moTu.isConnected ? moTu" in f                # đóng -> tiêu điểm về nút mở hộp
    assert 'id="hl-ok" disabled' in f and '$("#hl-huy", dlg).focus()' in f                            # vẫn: khoá tới khi tích, Enter = Huỷ
