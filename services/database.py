from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

try:
    from supabase import Client, create_client
    from supabase.client import ClientOptions
except (ImportError, ModuleNotFoundError):
    Client = Any  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]
    ClientOptions = None  # type: ignore[assignment]

from services.config import get_config

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def get_db() -> Client | None:
    cfg = get_config()
    if not cfg.has_supabase or create_client is None or ClientOptions is None:
        return None
    return create_client(
        cfg.supabase_url,
        cfg.supabase_key,
        options=ClientOptions(
            postgrest_client_timeout=30,
            storage_client_timeout=40,
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


def _read_csv(name: str) -> pd.DataFrame:
    path = ROOT / "data" / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def demo_news() -> pd.DataFrame:
    return _read_csv("demo_news.csv")


def master_upt() -> pd.DataFrame:
    df = _read_csv("master_upt_coordinates.csv")
    if df.empty:
        df = _read_csv("demo_upt.csv")
    return ensure_upt_columns(df)


def _merge_upt_with_master(database_df: pd.DataFrame, master_df: pd.DataFrame) -> pd.DataFrame:
    if database_df.empty:
        out = master_df.copy()
        out["data_source"] = "master_paket"
        return out
    if master_df.empty:
        out = database_df.copy()
        out["data_source"] = "database"
        return out

    db = ensure_upt_columns(database_df).copy()
    master = ensure_upt_columns(master_df).copy()
    db["_key"] = db["nama_upt"].astype(str).str.strip().str.casefold()
    master["_key"] = master["nama_upt"].astype(str).str.strip().str.casefold()
    db = db.drop_duplicates("_key", keep="last").set_index("_key")
    master = master.drop_duplicates("_key", keep="last").set_index("_key")

    all_keys = master.index.union(db.index)
    rows: list[dict[str, Any]] = []
    for key in all_keys:
        base = master.loc[key].to_dict() if key in master.index else {}
        live = db.loc[key].to_dict() if key in db.index else {}
        merged = dict(base)
        for column, value in live.items():
            if pd.notna(value) and str(value).strip() not in {"", "nan", "None"}:
                merged[column] = value
        merged["data_source"] = "database" if key in db.index else "master_paket"
        rows.append(merged)
    return ensure_upt_columns(pd.DataFrame(rows))


@st.cache_data(ttl=60, show_spinner=False)
def fetch_news_df() -> pd.DataFrame:
    if is_demo_mode():
        df = demo_news()
    else:
        try:
            rows = fetch_all("berita", "*", order_by="created_at", desc=True)
            df = pd.DataFrame(rows)
        except Exception:
            df = pd.DataFrame()
    return ensure_news_columns(df)


@st.cache_data(ttl=120, show_spinner=False)
def fetch_upt_df() -> pd.DataFrame:
    packaged = master_upt()
    if is_demo_mode():
        return packaged
    try:
        rows = fetch_all("upt", "*", order_by="nama_upt")
        database_df = pd.DataFrame(rows)
    except Exception:
        database_df = pd.DataFrame()
    return _merge_upt_with_master(database_df, packaged)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_audit_df() -> pd.DataFrame:
    if not table_exists("audit_log"):
        return pd.DataFrame()
    return pd.DataFrame(fetch_all("audit_log", "*", order_by="created_at", desc=True))


def ensure_news_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults: dict[str, Any] = {
        "id": "", "created_at": pd.NaT, "updated_at": pd.NaT,
        "nama_upt": "Tidak diketahui", "nama_petugas": "Tidak diketahui",
        "created_by": "", "link": "", "link_normalized": "",
        "judul": "Tanpa judul", "media": "Tidak diketahui", "platform": "Tidak diketahui",
        "tanggal_publikasi": pd.NaT, "kategori": "Lainnya", "subkategori": "Umum",
        "sentimen": "Tidak diketahui", "urgensi": "Rendah", "dampak": "UPT",
        "ringkasan": "", "caption_manual": "", "status_baca": "", "catatan": "",
        "status_verifikasi": "Belum Ditelaah", "status_sebelumnya": "", "kata_kunci": None,
        "lokasi": "", "tingkat_perhatian": "Rendah", "ai_provider": "rules",
        "ai_confidence": None, "source_type": "manual", "source_external_id": "",
        "source_sheet_id": "", "source_sheet_name": "", "source_row_number": None,
        "source_updated_at": pd.NaT, "last_synced_at": pd.NaT, "sync_status": "",
        "sync_error": "", "detected_at": pd.NaT, "raw_analysis": "",
        "rekomendasi": "", "status_tindak_lanjut": "", "petugas_respon": "",
        "waktu_respon": pd.NaT, "content_hash": "", "submitted_by": "", "submitted_at": pd.NaT,
        "reviewed_by": "", "reviewed_at": pd.NaT, "verified_by": "", "verified_at": pd.NaT,
        "review_note": "", "rejection_reason": "", "archived_by": "", "archived_at": pd.NaT,
        "deleted_at": pd.NaT, "deleted_by": "",
    }
    out = df.copy()
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
        else:
            out[col] = out[col].where(out[col].notna(), default)
    for col in [
        "created_at", "updated_at", "tanggal_publikasi", "submitted_at", "reviewed_at",
        "verified_at", "archived_at", "deleted_at", "source_updated_at", "last_synced_at",
        "detected_at", "waktu_respon",
    ]:
        out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)
    status_aliases = {
        "Draft": "Belum Ditelaah",
        "Diajukan": "Belum Ditelaah",
        "Sedang Diperiksa": "Belum Ditelaah",
        "Perlu Perbaikan": "Perlu Koreksi",
        "Ditolak": "Tidak Valid",
    }
    out["status_verifikasi"] = out["status_verifikasi"].astype(str).replace(status_aliases)
    return out


def ensure_upt_columns(df: pd.DataFrame) -> pd.DataFrame:
    defaults: dict[str, Any] = {
        "id": "", "nama_upt": "", "jenis_upt": "", "kelas_upt": "",
        "subjenis_upt": "", "provinsi": "", "kanwil": "", "kabupaten_kota": "",
        "alamat": "", "latitude": None, "longitude": None, "coordinate_quality": "Belum tersedia",
        "coordinate_source": "", "coordinate_score": None, "coordinate_verified_at": pd.NaT,
        "coordinate_verified_by": "", "aktif": True, "catatan_verifikasi": "",
        "data_source": "database",
    }
    out = df.copy()
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
        else:
            out[col] = out[col].where(out[col].notna(), default)
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out["coordinate_score"] = pd.to_numeric(out["coordinate_score"], errors="coerce")
    out["coordinate_verified_at"] = pd.to_datetime(out["coordinate_verified_at"], errors="coerce", utc=True)
    active_text = out["aktif"].astype(str).str.strip().str.casefold()
    out["aktif"] = active_text.map({
        "true": True, "1": True, "ya": True, "aktif": True,
        "false": False, "0": False, "tidak": False, "nonaktif": False,
    }).fillna(True).astype(bool)
    return out


def clear_data_cache() -> None:
    fetch_news_df.clear()
    fetch_upt_df.clear()
    fetch_audit_df.clear()
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
    raise RuntimeError(
        "Penghapusan permanen dinonaktifkan. Gunakan status arsip/soft delete agar audit tetap terjaga."
    )


def upsert_rows(table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Mode demo bersifat baca-saja.")
    if not rows:
        return
    chunk_size = 200
    for start in range(0, len(rows), chunk_size):
        db.table(table).upsert(rows[start:start + chunk_size], on_conflict=on_conflict).execute()
    clear_data_cache()
