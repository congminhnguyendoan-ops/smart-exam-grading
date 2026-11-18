import sys
from pathlib import Path

import pytest

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import sao_luu_demo as S  # noqa: E402


def test_tach_url_va_lenh_khong_chua_mat_khau():
    k = S.tach_url("postgresql://smart_exam_app:Bi%40Mat-123@localhost:5433/smart_exam")
    assert k == {"host": "localhost", "port": "5433", "user": "smart_exam_app", "db": "smart_exam", "mat_khau": "Bi@Mat-123"}
    lenh = S.lenh_dump("pg_dump", k, Path("x.dump"))
    assert lenh[:2] == ["pg_dump", "-Fc"] and "Bi@Mat-123" not in " ".join(lenh) and "Bi%40Mat-123" not in " ".join(lenh)
    kp = S.lenh_khoi_phuc(k, "x.dump")
    assert "Bi@Mat" not in kp and "--clean" in kp and "-d smart_exam" in kp


def test_url_sai_dang_bi_tu_choi_khong_in_gia_tri():
    with pytest.raises(SystemExit) as e:
        S.tach_url("mysql://u:BiMat@h/db")
    assert "BiMat" not in str(e.value)
