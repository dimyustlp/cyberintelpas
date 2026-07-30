from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.layout import info_panel, page_header, section_header
from services.access_control import require_permission
from services.config import get_config
from services.database import fetch_all, get_db, table_exists, upsert_rows

admin = require_permission("manage_settings")
page_header("Pengaturan Sistem", "Periksa koneksi, migration, AI, tema, dan kelengkapan data UPT.", "System Administration")
cfg = get_config()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Supabase", "Terhubung" if cfg.has_supabase else "Demo")
c2.metric("Database Enterprise", "Aktif" if table_exists("app_users") else "Belum Migration")
c3.metric("AI Provider", "Aktif" if cfg.has_openai else "Fallback Lokal")
c4.metric("Audit Log", "Aktif" if table_exists("audit_log") else "Belum Aktif")

section_header("Migration Database", "Diperlukan satu kali untuk akun bertingkat, audit log, peta, dan metadata AI.")
if table_exists("app_users") and table_exists("audit_log"):
    st.success("Migration enterprise telah terdeteksi.")
else:
    info_panel("Tindakan Diperlukan", "Jalankan migration SQL", "Buka Supabase → SQL Editor, salin seluruh isi <b>sql/migration_v4_enterprise.sql</b>, lalu klik Run.")

section_header("Impor dan Perkaya Daftar UPT", "Tambahkan provinsi, Kanwil, dan koordinat untuk mengaktifkan peta drill-down.")
template_path = Path(__file__).resolve().parents[1] / "data" / "upt_enterprise_template.csv"
st.download_button("Unduh Template UPT Enterprise", template_path.read_bytes(), "upt_enterprise_template.csv", "text/csv")
uploaded = st.file_uploader("Unggah CSV atau Excel UPT", type=["csv", "xlsx", "xls"])
if uploaded:
    try:
        df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
        required = {"nama_upt"}
        if not required.issubset(df.columns):
            st.error("File harus memiliki kolom nama_upt.")
        else:
            allowed = ["nama_upt", "jenis_upt", "provinsi", "kanwil", "latitude", "longitude", "coordinate_quality", "aktif"]
            for col in allowed:
                if col not in df.columns: df[col] = None
            preview = df[allowed].copy()
            st.dataframe(preview.head(30), width="stretch", hide_index=True)
            if st.button("IMPOR / PERBARUI UPT", type="primary"):
                rows = []
                for record in preview.to_dict("records"):
                    clean = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                    clean["nama_upt"] = str(clean["nama_upt"]).strip()
                    if clean["nama_upt"]:
                        rows.append(clean)
                upsert_rows("upt", rows, "nama_upt")
                st.success(f"{len(rows)} data UPT berhasil diproses.")
                st.rerun()
    except Exception as exc:
        st.error(f"File tidak dapat diproses: {exc}")

section_header("Tema Terang / Gelap", "Tampilan mengikuti tema aktif Streamlit.")
info_panel("Appearance", "Cara mengganti tema", "Klik menu <b>⋮</b> di kanan atas → <b>Settings</b> → <b>Theme</b>, lalu pilih Light atau Dark. Seluruh kartu, grafik, sidebar, dan peta menyesuaikan otomatis.")

if table_exists("audit_log"):
    section_header("Aktivitas Terbaru", "Jejak login, input, perubahan, dan penghapusan data.")
    audit = pd.DataFrame(fetch_all("audit_log", "created_at,actor_username,actor_role,action,entity,entity_id,metadata", order_by="created_at", desc=True)[:200])
    st.dataframe(audit, width="stretch", hide_index=True)
