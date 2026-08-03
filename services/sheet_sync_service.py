from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from services.config import get_secret
from services.database import fetch_all, table_exists


@dataclass(frozen=True)
class SyncFunctionResult:
    ok: bool
    message: str
    payload: dict[str, Any]


def fetch_sync_logs(limit: int = 100) -> pd.DataFrame:
    if not table_exists("sheet_sync_log"):
        return pd.DataFrame()
    try:
        rows = fetch_all("sheet_sync_log", "*", order_by="started_at", desc=True)
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(rows[:limit])
    for column in ["started_at", "finished_at"]:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", utc=True)
    return df


def latest_sync_log() -> dict[str, Any]:
    df = fetch_sync_logs(limit=1)
    return {} if df.empty else df.iloc[0].to_dict()


def _function_url() -> str:
    explicit = get_secret("SHEET_SYNC_FUNCTION_URL")
    if explicit:
        return explicit.rstrip("/")
    supabase_url = get_secret("SUPABASE_URL")
    if not supabase_url:
        return ""
    return f"{supabase_url.rstrip('/')}/functions/v1/sheet-sync"


def trigger_sheet_sync(timeout: int = 120) -> SyncFunctionResult:
    url = _function_url()
    token = get_secret("SHEET_SYNC_TOKEN")
    if not url:
        return SyncFunctionResult(False, "SUPABASE_URL atau SHEET_SYNC_FUNCTION_URL belum diisi pada Secrets.", {})
    if not token:
        return SyncFunctionResult(False, "SHEET_SYNC_TOKEN belum diisi pada Secrets.", {})
    try:
        supabase_key = get_secret("SUPABASE_KEY") or get_secret("SUPABASE_ANON_KEY")
        headers = {
            "Content-Type": "application/json",
            "x-sync-token": token,
            "x-trigger-type": "manual_streamlit",
        }
        if supabase_key:
            headers["Authorization"] = f"Bearer {supabase_key}"
            headers["apikey"] = supabase_key
        response = requests.post(
            url,
            headers=headers,
            json={"source": "cyberintelpas_manual_button"},
            timeout=timeout,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text[:1500]}
        message = str(payload.get("message") or f"HTTP {response.status_code}")
        if response.ok and bool(payload.get("ok", True)):
            return SyncFunctionResult(True, message, payload)
        return SyncFunctionResult(False, message, payload)
    except requests.RequestException as exc:
        return SyncFunctionResult(False, f"Edge Function tidak dapat dihubungi: {exc}", {})


def sync_health() -> dict[str, Any]:
    latest = latest_sync_log()
    if not latest:
        return {
            "status": "Belum pernah",
            "last_run": None,
            "rows_seen": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
        }
    return {
        "status": latest.get("status") or "Tidak diketahui",
        "last_run": latest.get("finished_at") or latest.get("started_at"),
        "rows_seen": int(latest.get("rows_seen") or 0),
        "inserted": int(latest.get("rows_inserted") or 0),
        "updated": int(latest.get("rows_updated") or 0),
        "skipped": int(latest.get("rows_skipped") or 0),
        "failed": int(latest.get("rows_failed") or 0),
    }
