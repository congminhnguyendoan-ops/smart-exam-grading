from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import lay_database_url


def ket_noi(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or lay_database_url(), row_factory=dict_row, connect_timeout=5)


@contextmanager
def giao_dich(url: str | None = None):
    with ket_noi(url) as conn:
        yield conn
