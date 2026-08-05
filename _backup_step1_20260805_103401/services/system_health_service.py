from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from services.cyber_db import fetch_all, get_db, response_data, rpc


def _component(component: str, status: str, message: str, detail: str = "") -> dict[str, str]:
    return {"component": component, "status": status, "message": message, "detail": detail}



def _check_application_runtime() -> dict[str, str]:
    return _component("Aplikasi Streamlit", "Normal", "Runtime aplikasi aktif dan halaman System Operations Center dapat dimuat.")


def _check_authentication() -> dict[str, str]:
    try:
        users = fetch_all("app_users", "id,aktif,last_login", max_rows=5000)
        active = sum(bool(row.get("aktif")) for row in users)
        if active == 0:
            return _component("Autentikasi Pengguna", "Kritis", "Tidak ditemukan akun aktif pada app_users.")
        last_login_values = [pd.to_datetime(row.get("last_login"), errors="coerce", utc=True) for row in users]
        valid = [value for value in last_login_values if pd.notna(value)]
        latest = max(valid).tz_convert("Asia/Jakarta").strftime("%d-%m-%Y %H:%M WIB") if valid else "belum tercatat"
        return _component("Autentikasi Pengguna", "Normal", f"Terdapat {active} akun aktif. Login terakhir: {latest}.")
    except Exception as exc:
        return _component("Autentikasi Pengguna", "Kritis", "Status akun dan autentikasi tidak dapat diperiksa.", str(exc))


def _check_audit_log() -> dict[str, str]:
    try:
        rows = fetch_all("audit_log", "id,created_at,action", order_by="created_at", desc=True, max_rows=1)
        if not rows:
            return _component("Audit Aktivitas", "Peringatan", "Tabel audit tersedia, tetapi belum ada aktivitas yang tercatat.")
        created = pd.to_datetime(rows[0].get("created_at"), errors="coerce", utc=True)
        when = created.tz_convert("Asia/Jakarta").strftime("%d-%m-%Y %H:%M WIB") if pd.notna(created) else "waktu tidak diketahui"
        return _component("Audit Aktivitas", "Normal", f"Audit terakhir tercatat pada {when} dengan aksi {rows[0].get('action') or '-'}.")
    except Exception as exc:
        return _component("Audit Aktivitas", "Kritis", "Audit aktivitas tidak dapat dibaca.", str(exc))


def _check_storage_buckets() -> dict[str, str]:
    required = {"berita-bukti", "field-evidence", "intel-reports"}
    try:
        response = get_db().storage.list_buckets()
        buckets = response if isinstance(response, list) else getattr(response, "data", response) or []
        names = set()
        for item in buckets:
            if isinstance(item, dict):
                names.add(str(item.get("name") or item.get("id") or ""))
            else:
                names.add(str(getattr(item, "name", None) or getattr(item, "id", "")))
        missing = sorted(required - names)
        if missing:
            return _component("Storage Bukti dan Laporan", "Kritis", "Bucket belum tersedia: " + ", ".join(missing) + ".")
        return _component("Storage Bukti dan Laporan", "Normal", "Bucket berita-bukti, field-evidence, dan intel-reports tersedia.")
    except Exception as exc:
        return _component("Storage Bukti dan Laporan", "Peringatan", "Status bucket Storage belum dapat diperiksa.", str(exc))

def _check_database() -> dict[str, str]:
    try:
        response = get_db().table("berita").select("id", count="exact").limit(1).execute()
        count = getattr(response, "count", None)
        return _component("Database Supabase", "Normal", f"Database dapat diakses. Total berita terbaca: {count if count is not None else 'tersedia'}.")
    except Exception as exc:
        return _component("Database Supabase", "Kritis", "Database tidak dapat diakses.", str(exc))


def _check_sheet_sync() -> dict[str, str]:
    try:
        rows = fetch_all("sheet_sync_log", "*", order_by="started_at", desc=True, max_rows=5)
        if not rows:
            return _component("Sinkronisasi Spreadsheet", "Peringatan", "Belum ada riwayat sinkronisasi.")
        latest = rows[0]
        started = pd.to_datetime(latest.get("started_at"), errors="coerce", utc=True)
        age_minutes = None
        if pd.notna(started):
            age_minutes = int((datetime.now(timezone.utc) - started.to_pydatetime()).total_seconds() / 60)
        status_text = str(latest.get("status") or "").casefold()
        if status_text in {"gagal", "failed"}:
            return _component("Sinkronisasi Spreadsheet", "Kritis", "Sinkronisasi terakhir gagal.", str(latest.get("error_detail") or latest.get("message") or ""))
        if age_minutes is not None and age_minutes > 20:
            return _component("Sinkronisasi Spreadsheet", "Peringatan", f"Sinkronisasi terakhir sudah {age_minutes} menit yang lalu.")
        return _component("Sinkronisasi Spreadsheet", "Normal", f"Sinkronisasi terakhir berhasil{f' {age_minutes} menit lalu' if age_minutes is not None else ''}.")
    except Exception as exc:
        return _component("Sinkronisasi Spreadsheet", "Peringatan", "Riwayat sinkronisasi belum dapat diperiksa.", str(exc))


def _check_cron() -> dict[str, str]:
    try:
        response = rpc("cyberintelpas_system_health")
        data = getattr(response, "data", None) or {}
        if isinstance(data, list) and data:
            data = data[0]
        installed = bool(data.get("cron_installed")) if isinstance(data, dict) else False
        active = bool(data.get("sheet_sync_cron_active")) if isinstance(data, dict) else False
        if not installed:
            return _component("Cron Otomatis", "Kritis", "Ekstensi pg_cron belum terdeteksi.")
        if not active:
            return _component("Cron Otomatis", "Kritis", "Job sheet-sync-auto belum aktif.")
        return _component("Cron Otomatis", "Normal", "Job sheet-sync-auto aktif.")
    except Exception as exc:
        return _component("Cron Otomatis", "Peringatan", "Status Cron belum dapat dibaca melalui RPC.", str(exc))


def _check_ai() -> dict[str, str]:
    configured = bool(str(st.secrets.get("OPENAI_API_KEY", "")).strip())
    if configured:
        return _component("AI Laporan", "Normal", "OPENAI_API_KEY tersedia. Generator AI siap digunakan.")
    return _component("AI Laporan", "Peringatan", "OPENAI_API_KEY belum tersedia. Sistem memakai narasi lokal sebagai fallback.")


def _check_report_dependencies() -> dict[str, str]:
    modules = {"reportlab": "PDF", "docx": "Word", "pptx": "PowerPoint"}
    missing = [label for module, label in modules.items() if importlib.util.find_spec(module) is None]
    if missing:
        return _component("Generator Laporan", "Peringatan", "Dependensi belum lengkap: " + ", ".join(missing) + ".")
    return _component("Generator Laporan", "Normal", "Generator PDF, Word, dan PowerPoint tersedia.")


def _check_core_tables() -> list[dict[str, str]]:
    checks = [
        ("Kasus Intelijen", "intelligence_cases"),
        ("Relasi Berita dan Kasus", "case_news"),
        ("Penugasan Lapangan", "field_assignments"),
        ("Laporan Lapangan", "field_reports"),
        ("Bukti Lapangan", "field_evidence"),
        ("Analisis Evaluasi", "case_analyses"),
        ("Rekomendasi", "case_recommendations"),
        ("Keputusan Pimpinan", "case_decisions"),
        ("Tindak Lanjut", "action_items"),
        ("Laporan Mingguan", "weekly_reports"),
        ("Arsip Ekspor", "report_exports"),
    ]
    output = []
    for label, table in checks:
        try:
            get_db().table(table).select("*", count="exact").limit(1).execute()
            output.append(_component(label, "Normal", f"Table {table} tersedia."))
        except Exception as exc:
            output.append(_component(label, "Kritis", f"Table {table} belum tersedia atau tidak dapat diakses.", str(exc)))
    return output


def collect_system_health() -> list[dict[str, str]]:
    return [
        _check_application_runtime(),
        _check_database(),
        _check_authentication(),
        _check_sheet_sync(),
        _check_cron(),
        _check_audit_log(),
        _check_storage_buckets(),
        _check_ai(),
        _check_report_dependencies(),
        *_check_core_tables(),
    ]
