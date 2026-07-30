from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client
from supabase.client import ClientOptions

from services.config import get_config


@st.cache_resource
def get_db() -> Client | None:
    cfg = get_config()
    if not cfg.has_supabase:
        return None
    return create_client(
        cfg.supabase_url,
        cfg.supabase_key,
        options=ClientOptions(
            postgrest_client_timeout=25,
            storage_client_timeout=25,
            schema="public",
        ),
    )


def is_demo_mode() -> bool:
    return get_db() is None


@st.cache_data(ttl=60, show_spinner=False)
def table_exists(table: str) -> bool:
    db = get_db()
    if db is None:
        return False
    try:
        db.table(table).select("*").limit(1).execute()
        return True
    except Exception:
        return False


def fetch_all(table: str, columns: str = "*", order_by: str | None = None, desc: bool = False) -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        return []
    rows: list[dict[str, Any]] = []
    page_size = 1000
    start = 0
    while True:
        query = db.table(table).select(columns)
        if order_by:
            query = query.order(order_by, desc=desc)
        response = query.range(start, start + page_size - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def demo_news() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "data" / "demo_news.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def demo_upt() -> pd.DataFrame:
    path = Path(__file__).resolve().parents[1] / "data" / "demo_upt.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_news_df() -> pd.DataFrame:
    if is_demo_mode():
        df = demo_news()
    else:
        rows = fetch_all("berita", "*", order_by="created_at", desc=True)
        df = pd.DataFrame(rows)
    return ensure_news_columns(df)


@st.cache_data(ttl=120, show_spinner=False)
def fetch_upt_df() -> pd.DataFrame:
    if is_demo_mode():
        df = demo_upt()
    else:
        rows = fetch_all("upt", "*", order_by="nama_upt")
        df = pd.DataFrame(rows)
    return ensure_upt_columns(df)


def ensure_news_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults: dict[str, Any] = {
        "id": "",
        "created_at": pd.NaT,
        "updated_at": pd.NaT,
        "nama_upt": "Tidak diketahui",
        "nama_petugas": "Tidak diketahui",
        "link": "",
        "judul": "Tanpa judul",
        "media": "Tidak diketahui",
        "platform": "Tidak diketahui",
        "tanggal_publikasi": pd.NaT,
        "kategori": "Lainnya",
        "subkategori": "Umum",
        "sentimen": "Tidak diketahui",
        "urgensi": "Rendah",
        "ringkasan": "",
        "caption_manual": "",
        "status_baca": "",
        "catatan": "",
        "status_verifikasi": "Draft",
        "kata_kunci": None,
        "lokasi": "",
        "tingkat_perhatian": "Rendah",
        "ai_provider": "rules",
        "ai_confidence": None,
    }
    out = df.copy()
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
        else:
            out[col] = out[col].where(out[col].notna(), default)
    for col in ["created_at", "updated_at", "tanggal_publikasi"]:
        out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)
    return out


def ensure_upt_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults: dict[str, Any] = {
        "id": "",
        "nama_upt": "",
        "jenis_upt": "",
        "provinsi": "",
        "kanwil": "",
        "latitude": None,
        "longitude": None,
        "coordinate_quality": "",
        "aktif": True,
    }
    out = df.copy()
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
        else:
            out[col] = out[col].where(out[col].notna(), default)
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    return out


def clear_data_cache() -> None:
    fetch_news_df.clear()
    fetch_upt_df.clear()
    table_exists.clear()


def insert_row(table: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        raise RuntimeError("Mode demo bersifat baca-saja. Isi Supabase Secrets untuk menyimpan data.")
    response = db.table(table).insert(payload).select("*").execute()
    clear_data_cache()
    return response.data or []


def update_rows(table: str, payload: dict[str, Any], key: str, value: Any) -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        raise RuntimeError("Mode demo bersifat baca-saja.")
    response = db.table(table).update(payload).eq(key, value).select("*").execute()
    clear_data_cache()
    return response.data or []


def delete_rows(table: str, key: str, value: Any) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Mode demo bersifat baca-saja.")
    db.table(table).delete().eq(key, value).execute()
    clear_data_cache()


def upsert_rows(table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Mode demo bersifat baca-saja.")
    if not rows:
        return
    chunk_size = 250
    for start in range(0, len(rows), chunk_size):
        db.table(table).upsert(rows[start:start + chunk_size], on_conflict=on_conflict).execute()
    clear_data_cache()
