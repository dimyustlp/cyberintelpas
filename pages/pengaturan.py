from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.layout import info_panel, page_header, section_header
from services.access_control import require_permission
from services.config import get_config
from services.database import fetch_news_df, fetch_upt_df, get_db, table_exists

admin = require_permission("manage_settings")
page_header(
    "Pengaturan Sistem",
    "Periksa koneksi, migration, storage, AI, kelengkapan data, dan kesiapan produksi.",
    "System Administration",
)
cfg = get_config()

required_tables = [
    "app_users", "audit_log", "berita_status_history", "berita_attachments", "sheet_sync_log",
]
status = {table: table_exists(table) for table in required_tables}

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Supabase", "Terhubung" if cfg.has_supabase else "Demo")
c2.metric("Workflow", "Aktif" if status["berita_status_history"] else "Belum")
c3.metric("Lampiran", "Aktif" if status["berita_attachments"] else "Belum")
c4.metric("AI Provider", "Aktif" if cfg.has_openai else "Fallback Lokal")
c5.metric("Audit", "Aktif" if status["audit_log"] else "Belum")
c6.metric("Sheet Sync", "Aktif" if status["sheet_sync_log"] else "Belum")

section_header("Migration Database", "Diperlukan satu kali untuk seluruh fitur V5.3.")
if all(status.values()):
    st.success("Migration SIMBERPAS V5.3 terdeteksi lengkap.")
else:
    missing = ", ".join([table for table, ok in status.items() if not ok])
    info_panel(
        "Tindakan Diperlukan",
        "Jalankan migration SQL terbaru",
        f"Tabel/fitur belum ditemukan: <b>{missing}</b>. Buka Supabase → SQL Editor, salin isi <b>sql/migration_v5_3_internal_pusat.sql</b>, lalu Run.",
    )

section_header("Kesehatan Data", "Ringkasan master UPT dan berita.")
upt = fetch_upt_df()
news = fetch_news_df()
verified_coords = int(upt["coordinate_quality"].astype(str).str.casefold().eq("terverifikasi").sum()) if not upt.empty else 0
health = pd.DataFrame([
    {"Komponen": "Master UPT", "Nilai": len(upt), "Catatan": "Termasuk master paket dan database"},
    {"Komponen": "UPT koordinat terverifikasi", "Nilai": verified_coords, "Catatan": "Sisanya masih kandidat/perlu pemeriksaan"},
    {"Komponen": "Total berita", "Nilai": len(news), "Catatan": "Semua status"},
    {"Komponen": "Berita terverifikasi", "Nilai": int(news["status_verifikasi"].eq("Terverifikasi").sum()) if not news.empty else 0, "Catatan": "Memengaruhi peta resmi"},
    {"Komponen": "Berita menunggu proses", "Nilai": int(news["status_verifikasi"].isin(["Belum Ditelaah", "Perlu Koreksi"]).sum()) if not news.empty else 0, "Catatan": "Perlu tindakan"},
])
st.dataframe(health, width="stretch", hide_index=True)

section_header("Supabase Storage", "Bucket berita-bukti menyimpan JPG, PNG, dan PDF.")
if cfg.has_supabase and status["berita_attachments"]:
    try:
        db = get_db()
        buckets = db.storage.list_buckets() if db is not None else []
        names = [getattr(bucket, "name", None) or (bucket.get("name") if isinstance(bucket, dict) else "") for bucket in buckets]
        if "berita-bukti" in names:
            st.success("Bucket `berita-bukti` tersedia.")
        else:
            st.warning("Bucket `berita-bukti` belum terdeteksi. Jalankan migration SQL atau buat bucket private dengan nama tersebut.")
    except Exception as exc:
        st.warning(f"Status Storage belum dapat diperiksa: {exc}")
else:
    st.info("Storage akan aktif setelah Supabase dan migration lengkap.")

section_header("Tema Terang / Gelap", "Tampilan mengikuti tema Streamlit.")
info_panel(
    "Appearance",
    "Cara mengganti tema",
    "Klik menu <b>⋮</b> di kanan atas → <b>Settings</b> → <b>Theme</b>, lalu pilih Light atau Dark.",
)

section_header("Berkas Penting Paket", "Berkas yang digunakan saat pemasangan.")
root = Path(__file__).resolve().parents[1]
files = [
    "sql/migration_v5_3_internal_pusat.sql",
    "data/master_upt_coordinates.csv",
    "data/master_upt_coordinates.xlsx",
    "PETUNJUK_UPDATE_V5_3_INTERNAL_PUSAT.txt",
    "sql/migration_v5_4_spreadsheet_sync.sql",
    "integrations/google_apps_script/CyberIntelPAS_Sync.gs",
]
for rel in files:
    path = root / rel
    st.write(("✅" if path.exists() else "❌") + f" `{rel}`")
