"""Kiểm thử công cụ đánh giá độc lập tools/eval_ocr.py (Tuần 6 Phần C): chỉ dùng API công khai, khoá tập val, không đọc nhãn ngoài tập."""
import ast
import os
import subprocess
import sys

import pytest

from conftest import DATA, ROOT, can_file

sys.path.insert(0, str(ROOT / "tools"))
import eval_ocr as E  # noqa: E402


def test_eval_chi_dung_api_cong_khai():
    cay = ast.parse((ROOT / "tools" / "eval_ocr.py").read_text(encoding="utf-8"))
    dung = {"ocr": set(), "omr": set()}
    for n in ast.walk(cay):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in dung:
            dung[n.value.id].add(n.attr)
    assert dung["ocr"] <= {"doc_chu_so", "doi_chieu_dinh_danh", "nap_mo_hinh_ocr"}, dung
    assert dung["omr"] <= {"doc_phieu", "nap_mo_hinh"}, dung
    mod = {n.module for n in ast.walk(cay) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(cay) if isinstance(n, ast.Import) for a in n.names}
    assert not ({"huan_luyen_ocr", "ocr_du_lieu", "ocr_cai_tien", "ocr_do_luong", "xuat_ocr", "torch"} & mod)


def test_val_bi_khoa_neu_khong_xac_nhan():
    # Tiến trình con phải xuất UTF-8: thông báo có dấu "–"; mặc định cp1252 thì tiến trình cha giải mã UTF-8 lỗi, r.stderr = None
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "eval_ocr.py"), "run", "--tap", "val"], capture_output=True, text=True,
                       encoding="utf-8", cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode != 0 and "val" in (r.stderr + r.stdout) and "xac-nhan-val" in (r.stderr + r.stdout)


def test_chi_tap_dev_va_val_khong_co_test():
    assert set(E.TAP) == {"dev", "val"}
    assert max(E.TAP["val"]) == 34 and min(E.TAP["val"]) == 29 and max(E.TAP["dev"]) == 28


def test_nhan_chi_gom_phieu_cua_tap():
    can_file(DATA / "ground_truth.csv")
    n = E.doc_nhan(E.TAP["dev"])
    assert len(n) == 28 and all(1 <= int(k) <= 28 for k in n)


def test_cp_ci():
    lo, hi = E.cp_ci(0, 54)
    assert lo == 0.0 and 0.05 < hi < 0.07                     # 0 / 54 -> cận trên ≈ 6,6%
