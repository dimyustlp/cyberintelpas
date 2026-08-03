from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services.audit_service import log_action
from components.layout import kpi_grid, page_header, section_header
from services.access_control import require_permission, scope_news
from services.analytics_service import dashboard_metrics
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.export_service import excel_bytes
from services.news_service import normalize_status, warning_state

user = require_permission("export_reports")
page_header(
    "Laporan Eksekutif",
    "Siapkan rekap harian, mingguan, bulanan, atau bahan pimpinan dengan status verifikasi yang jelas.",
    "Reporting Center",
)
all_upt = fetch_upt_df()
news = scope_news(fetch_news_df(), user, all_upt)
if not news.empty:
    news = news.copy()
    news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
    news["warning_state"] = news.apply(warning_state, axis=1)
    if user.role == "executive_viewer":
        news = news[news["status_verifikasi"].eq("Terverifikasi") | news["warning_state"].eq("preliminary")].copy()
if news.empty:
    st.info("Belum ada data untuk dilaporkan.")
    st.stop()

created = pd.to_datetime(news["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Jakarta")
news = news.assign(_date=created.dt.date)
min_date = news["_date"].dropna().min() or date.today()
max_date = news["_date"].dropna().max() or date.today()

with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    date_range = c1.date_input("Rentang tanggal", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    sentiment = c2.multiselect("Sentimen", sorted(news["sentimen"].dropna().astype(str).unique().tolist()))
    category = c3.multiselect("Kategori", sorted(news["kategori"].dropna().astype(str).unique().tolist()))
    status = c4.multiselect(
        "Status verifikasi",
        sorted(news["status_verifikasi"].dropna().astype(str).unique().tolist()),
        default=["Terverifikasi"] if "Terverifikasi" in news["status_verifikasi"].astype(str).unique() else [],
    )
    d1, d2, d3 = st.columns(3)
    urgency = d1.multiselect("Urgensi", sorted(news["urgensi"].dropna().astype(str).unique().tolist()))
    platform = d2.multiselect("Platform", sorted(news["platform"].dropna().astype(str).unique().tolist()))
    upt_names = d3.multiselect("UPT", sorted(news["nama_upt"].dropna().astype(str).unique().tolist()))

filtered = news.copy()
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    filtered = filtered[filtered["_date"].between(date_range[0], date_range[1])]
if sentiment:
    filtered = filtered[filtered["sentimen"].isin(sentiment)]
if category:
    filtered = filtered[filtered["kategori"].isin(category)]
if status:
    filtered = filtered[filtered["status_verifikasi"].isin(status)]
if urgency:
    filtered = filtered[filtered["urgensi"].isin(urgency)]
if platform:
    filtered = filtered[filtered["platform"].isin(platform)]
if upt_names:
    filtered = filtered[filtered["nama_upt"].isin(upt_names)]

m = dashboard_metrics(filtered) if not filtered.empty else dashboard_metrics(news.iloc[0:0])
kpi_grid([
    {"icon": "📰", "title": "Total", "value": m.total, "foot": "Dalam filter laporan", "accent": "#1769AA"},
    {"icon": "🔴", "title": "Negatif", "value": m.negative, "foot": "Memerlukan telaah", "accent": "#C53A43"},
    {"icon": "🚨", "title": "Tinggi/Kritis", "value": m.high, "foot": "Prioritas", "accent": "#650000"},
    {"icon": "🏢", "title": "UPT Aktif", "value": m.active_upt, "foot": "Kontributor berita", "accent": "#16845B"},
    {"icon": "📊", "title": "Positif", "value": m.positive, "foot": "Pemberitaan positif", "accent": "#16845B"},
    {"icon": "➖", "title": "Netral", "value": m.neutral, "foot": "Pemberitaan netral", "accent": "#D4A72C"},
])

section_header("Data Laporan", f"{len(filtered)} berita sesuai filter.")
columns = [
    "created_at", "tanggal_publikasi", "nama_upt", "judul", "media", "platform", "kategori",
    "subkategori", "sentimen", "urgensi", "dampak", "status_verifikasi", "source_type",
    "reviewed_by", "verified_by", "link", "ringkasan",
]
columns = [c for c in columns if c in filtered.columns]
st.dataframe(
    filtered[columns],
    width="stretch",
    height=450,
    hide_index=True,
    column_config={"link": st.column_config.LinkColumn("Link", display_text="Buka")},
)

c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "Unduh Laporan Excel",
        excel_bytes(filtered[columns], "Laporan Berita"),
        f"laporan_simberpas_{date.today().isoformat()}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        on_click=log_action,
        args=("export", "laporan", "berita", user.username, user.role, {"rows": len(filtered), "format": "xlsx"}),
    )
with c2:
    st.download_button(
        "Unduh Data CSV",
        filtered[columns].to_csv(index=False).encode("utf-8-sig"),
        f"laporan_simberpas_{date.today().isoformat()}.csv",
        "text/csv",
        use_container_width=True,
        on_click=log_action,
        args=("export", "laporan", "berita", user.username, user.role, {"rows": len(filtered), "format": "csv"}),
    )
