from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def _psycopg2():
    import psycopg2

    return psycopg2


def _real_dict_cursor():
    from psycopg2.extras import RealDictCursor

    return RealDictCursor


def accounting_sql_enabled() -> bool:
    return bool(os.environ.get("ODOO_POSTGRES_DSN"))


def get_accounting_connection():
    dsn = os.environ.get("ODOO_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError(
            "ODOO_POSTGRES_DSN is not configured. "
            "Set it to the Odoo PostgreSQL database DSN for direct financial SQL."
        )
    return _psycopg2().connect(dsn)


@contextmanager
def accounting_cursor() -> Iterator[Any]:
    conn = get_accounting_connection()
    try:
        with conn.cursor(cursor_factory=_real_dict_cursor()) as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
