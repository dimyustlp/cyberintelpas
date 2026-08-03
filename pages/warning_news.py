from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.layout import kpi_grid, page_header, section_header
from services.access_control import require_permission, scope_news
from services.database import fetch_news_df, fetch_upt_df
from services.news_service import normalize_status, warning_state

user = require_permission("view_warning")
page_header(
    "Warning News",
    "Peringatan awal muncul segera saat urgensi tinggi/kritis terdeteksi. Status terverifikasi membedakan informasi resmi dari hasil deteksi awal.",
    "Early Warning Center",
)

upt_df = fetch_upt_df()
news = scope_news(fetch_news_df(), user, upt_df)
if news.empty:
    st.success("Belum ada berita pada sistem.")
    st.stop()

news = news.copy()
news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
news["warning_state"] = news.apply(warning_state, axis=1)
warning = news[news["warning_state"].isin(["preliminary", "verified"])].copy()

preliminary = warning[warning["warning_state"] == "preliminary"]
verified = warning[warning["warning_state"] == "verified"]
critical = warning[warning["urgensi"].astype(str) == "Kritis"]
high = warning[warning["urgensi"].astype(str) == "Tinggi"]

kpi_grid([
    {"icon": "⚠️", "title": "Peringatan Awal", "value": len(preliminary), "foot": "Belum ditelaah", "accent": "#9B1C1C"},
    {"icon": "🚨", "title": "Terverifikasi", "value": len(verified), "foot": "Peringatan resmi", "accent": "#650000"},
    {"icon": "🟥", "title": "Kritis", "value": len(critical), "foot": "Prioritas tertinggi", "accent": "#4A0000"},
    {"icon": "🔴", "title": "Tinggi", "value": len(high), "foot": "Perlu perhatian", "accent": "#D00000"},
])

with st.expander("Makna dua tingkat peringatan", expanded=True):
    st.markdown(
        """
        - **⚠️ Peringatan Awal — Belum Ditelaah:** muncul otomatis segera setelah sistem mendeteksi urgensi Tinggi/Kritis. Belum menjadi kesimpulan resmi.
        - **🚨 Peringatan Terverifikasi:** sudah ditelaah oleh Analis Pemberitaan Strategis atau Administrator Utama Sistem dan dapat digunakan dalam laporan resmi.
        """
    )

with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    type_filter = c1.multiselect(
        "Jenis peringatan",
        ["Peringatan Awal", "Peringatan Terverifikasi"],
        default=["Peringatan Awal", "Peringatan Terverifikasi"],
    )
    urgency_filter = c2.multiselect("Urgensi", ["Kritis", "Tinggi"], default=["Kritis", "Tinggi"])
    upt_filter = c3.multiselect("UPT", sorted(warning["nama_upt"].dropna().astype(str).unique().tolist()))
    query = c4.text_input("Cari judul/media")

filtered = warning.copy()
allowed_states = []
if "Peringatan Awal" in type_filter:
    allowed_states.append("preliminary")
if "Peringatan Terverifikasi" in type_filter:
    allowed_states.append("verified")
filtered = filtered[filtered["warning_state"].isin(allowed_states)] if allowed_states else filtered.iloc[0:0]
if urgency_filter:
    filtered = filtered[filtered["urgensi"].isin(urgency_filter)]
if upt_filter:
    filtered = filtered[filtered["nama_upt"].isin(upt_filter)]
if query:
    filtered = filtered[
        filtered[["judul", "media", "nama_upt"]].astype(str).apply(
            lambda col: col.str.contains(query, case=False, na=False)
        ).any(axis=1)
    ]

rank = {"Kritis": 0, "Tinggi": 1}
filtered = filtered.assign(
    _rank=filtered["urgensi"].map(rank).fillna(9),
    _created=pd.to_datetime(filtered["created_at"], errors="coerce", utc=True),
).sort_values(["_rank", "_created"], ascending=[True, False])

section_header("Daftar Peringatan", f"{len(filtered)} peringatan sesuai filter.")
if filtered.empty:
    st.success("Tidak ada peringatan yang sesuai dengan filter.")
    st.stop()

for _, row in filtered.head(50).iterrows():
    is_preliminary = row["warning_state"] == "preliminary"
    label = "⚠️ PERINGATAN AWAL — BELUM DITELAAH" if is_preliminary else "🚨 PERINGATAN TERVERIFIKASI"
    color = "#9B1C1C" if is_preliminary else "#650000"
    title = escape(str(row.get("judul") or "Tanpa judul"))
    meta = escape(f"{row.get('nama_upt', '-')} • {row.get('media', '-')} • Urgensi {row.get('urgensi', '-')}")
    summary = escape(str(row.get("ringkasan") or "-")[:420])
    st.markdown(
        f"""
        <div class="sim-panel" style="border-left:6px solid {color};margin-bottom:12px">
          <div class="sim-panel-kicker" style="color:{color}">{label}</div>
          <div class="sim-panel-title">{title}</div>
          <div class="sim-panel-body"><b>{meta}</b><br>{summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 3])
    c1.caption(f"Status: {row.get('status_verifikasi', '-')}")
    c2.caption(f"Input: {row.get('created_by') or row.get('nama_petugas') or '-'}")
    if row.get("link"):
        c3.link_button("Buka sumber", str(row.get("link")))
