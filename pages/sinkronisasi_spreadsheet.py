from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import info_panel, page_header, section_header
from services.access_control import require_permission
from services.config import get_secret
from services.database import table_exists
from services.sheet_sync_service import fetch_sync_logs, sync_health, trigger_sheet_sync

admin = require_permission("manage_sync")
page_header(
    "Sinkronisasi Google Spreadsheet",
    "Pantau layanan read-only yang menarik berita dari publikasi CSV Google Spreadsheet ke Supabase tanpa menyentuh crawler maupun isi Spreadsheet.",
    "Data Source Operations",
)

public_csv_url = get_secret("PUBLIC_SHEET_CSV_URL", "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft/pub?output=csv")
sheet_name = get_secret("GOOGLE_SHEET_NAME", "Sheet1")
function_url = get_secret("SHEET_SYNC_FUNCTION_URL")
sync_token = get_secret("SHEET_SYNC_TOKEN")

if not table_exists("sheet_sync_log"):
    st.error("Tabel `sheet_sync_log` belum tersedia. Jalankan migration V5.6 terlebih dahulu.")
    st.stop()

health = sync_health()
status = str(health["status"])
status_icon = "✅" if status.casefold() == "berhasil" else "⚠️" if status.casefold() in {"sebagian", "berjalan"} else "❌" if status.casefold() == "gagal" else "ℹ️"

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Status terakhir", f"{status_icon} {status}")
last = health["last_run"]
if last is not None and not pd.isna(last):
    stamp = pd.Timestamp(last)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    last_text = stamp.tz_convert("Asia/Jakarta").strftime("%d %b %Y %H:%M WIB")
else:
    last_text = "Belum ada"
c2.metric("Terakhir sinkron", last_text)
c3.metric("Baris diperiksa", health["rows_seen"])
c4.metric("Data baru", health["inserted"])
c5.metric("Diperbarui", health["updated"])
c6.metric("Gagal", health["failed"])

section_header("Arsitektur Aman", "Crawler lama tetap bekerja dan Spreadsheet hanya dibaca.")
source_rows = pd.DataFrame([
    {"Komponen": "Crawler lama", "Nilai": "Tetap aktif dan tidak diubah"},
    {"Komponen": "Sumber publik", "Nilai": "Google Spreadsheet — Publish to web (CSV)"},
    {"Komponen": "URL CSV", "Nilai": public_csv_url},
    {"Komponen": "Nama tab", "Nilai": sheet_name},
    {"Komponen": "Mesin sinkronisasi", "Nilai": "GitHub Actions → Supabase Edge Function: sheet-sync"},
    {"Komponen": "Jadwal", "Nilai": "Setiap 5 menit melalui GitHub Actions"},
    {"Komponen": "Akses Spreadsheet", "Nilai": "Read-only melalui URL CSV publik"},
    {"Komponen": "Arah data", "Nilai": "Google Spreadsheet → Supabase → CyberIntelPAS"},
    {"Komponen": "Input manual", "Nilai": "Tetap aktif sebagai source_type=manual"},
])
st.dataframe(source_rows, width="stretch", hide_index=True)

section_header("Sinkronisasi Manual", "Menjalankan Edge Function yang sama dengan jadwal otomatis.")
if sync_token:
    if st.button("SINKRONKAN SEKARANG", type="primary", width="stretch"):
        with st.spinner("Membaca publikasi CSV Spreadsheet secara read-only..."):
            result = trigger_sheet_sync()
        if result.ok:
            st.success(result.message)
            counters = result.payload.get("counters") or {}
            if counters:
                st.caption(
                    f"Diperiksa {counters.get('seen', 0)} · baru {counters.get('inserted', 0)} · "
                    f"diperbarui {counters.get('updated', 0)} · dilewati {counters.get('skipped', 0)} · gagal {counters.get('failed', 0)}"
                )
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(result.message)
else:
    info_panel(
        "Tombol belum aktif",
        "Jadwal GitHub Actions tetap dapat berjalan",
        "Isi <b>SHEET_SYNC_TOKEN</b> pada Streamlit Secrets. Nilainya harus sama dengan secret pada Supabase Edge Function dan GitHub Actions Secret.",
    )

if not function_url:
    st.caption("SHEET_SYNC_FUNCTION_URL bersifat opsional. Jika kosong, aplikasi membentuk URL fungsi dari SUPABASE_URL.")

section_header("Riwayat Sinkronisasi", "Log disimpan di Supabase untuk audit dan diagnosis.")
logs = fetch_sync_logs(limit=100)
if logs.empty:
    st.info("Belum ada riwayat sinkronisasi.")
else:
    display_cols = [
        c for c in [
            "started_at", "finished_at", "status", "trigger_type", "sheet_name", "rows_seen",
            "rows_inserted", "rows_updated", "rows_skipped", "rows_failed",
            "duration_ms", "message", "error_detail",
        ] if c in logs.columns
    ]
    shown = logs[display_cols].copy()
    for col in ["started_at", "finished_at"]:
        if col in shown.columns:
            shown[col] = shown[col].dt.tz_convert("Asia/Jakarta").dt.strftime("%d/%m/%Y %H:%M:%S")
    st.dataframe(shown, width="stretch", hide_index=True)

section_header("Pemetaan Kolom", "Header Spreadsheet dipetakan tanpa menulis balik ke Sheet.")
mapping = pd.DataFrame([
    ["Waktu Terdeteksi", "detected_at"],
    ["Judul Berita", "judul"],
    ["Sumber / Portal", "media"],
    ["Tingkat Risiko", "urgensi"],
    ["Hasil Analisis", "raw_analysis, ringkasan, rekomendasi"],
    ["URL / Link Artikel", "link, link_normalized"],
    ["Status Tindak Lanjut", "status_tindak_lanjut"],
    ["Petugas Respon", "petugas_respon"],
    ["Waktu Respon", "waktu_respon"],
], columns=["Google Spreadsheet", "CyberIntelPAS / Supabase"])
st.dataframe(mapping, width="stretch", hide_index=True)

st.caption(
    "Data hasil sinkronisasi masuk sebagai Belum Ditelaah. Risiko Tinggi/Kritis langsung mengaktifkan Peringatan Awal, tetapi status resmi tetap ditentukan Analis Pemberitaan Strategis."
)
