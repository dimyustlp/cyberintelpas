from __future__ import annotations

from collections.abc import Iterable
import os
from typing import Any

import streamlit as st
from supabase import Client, create_client


@st.cache_resource(show_spinner=False)
def get_db() -> Client:
    """Membuat client Supabase server-side tanpa menaruh secret di source code."""
    try:
        secret_url = st.secrets.get("SUPABASE_URL", "")
        secret_key = st.secrets.get("SUPABASE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")
    except Exception:
        secret_url = ""
        secret_key = ""
    url = str(os.getenv("SUPABASE_URL") or secret_url or "").strip()
    key = str(
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or secret_key
        or ""
    ).strip()
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL dan SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY belum tersedia pada Streamlit Secrets."
        )
    return create_client(url, key)


def response_data(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return list(data or [])


def fetch_all(
    table: str,
    columns: str = "*",
    *,
    filters: Iterable[tuple[str, str, Any]] | None = None,
    order_by: str | None = None,
    desc: bool = False,
    page_size: int = 1000,
    max_rows: int = 20000,
) -> list[dict[str, Any]]:
    """Mengambil data bertahap karena Data API membatasi hasil per permintaan."""
    output: list[dict[str, Any]] = []
    start = 0
    while start < max_rows:
        query = get_db().table(table).select(columns)
        for method, column, value in filters or []:
            query = getattr(query, method)(column, value)
        if order_by:
            query = query.order(order_by, desc=desc)
        batch = response_data(query.range(start, start + page_size - 1).execute())
        output.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return output


def insert_row(table: str, payload: dict[str, Any], *, returning: str = "*") -> dict[str, Any]:
    # Supabase mengembalikan representasi baris secara default pada operasi insert.
    response = get_db().table(table).insert(payload).execute()
    rows = response_data(response)
    return rows[0] if rows else {}


def update_rows(
    table: str,
    payload: dict[str, Any],
    *,
    filters: Iterable[tuple[str, str, Any]],
    returning: str = "*",
) -> list[dict[str, Any]]:
    query = get_db().table(table).update(payload)
    for method, column, value in filters:
        query = getattr(query, method)(column, value)
    return response_data(query.execute())


def rpc(function_name: str, params: dict[str, Any] | None = None) -> Any:
    return get_db().rpc(function_name, params or {}).execute()
