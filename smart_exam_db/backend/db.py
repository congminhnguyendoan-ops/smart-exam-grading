"""
db.py - Kết nối PostgreSQL (psycopg 3). Mỗi yêu cầu API một kết nối + một giao dịch: thành công thì commit, lỗi thì rollback.
Các hàm dịch vụ (service.py) KHÔNG tự commit – để API quyết định, và để pytest chạy trong giao dịch rồi rollback.
"""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import lay_database_url


def ket_noi(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or lay_database_url(), row_factory=dict_row, connect_timeout=5)


@contextmanager
def giao_dich(url: str | None = None):
    """Một kết nối, một giao dịch: commit khi thoát bình thường, rollback khi có lỗi."""
    with ket_noi(url) as conn:           # psycopg: thoát khối with = commit / rollback rồi đóng
        yield conn
