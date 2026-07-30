from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from components.layout import kpi_grid, page_header, section_header
from services.access_control import scope_news
from services.analytics_service import dashboard_metrics
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.export_service import excel_bytes

user = current_user()
page_header("Laporan Eksekutif", "Siapkan rekap terfilter untuk kebutuhan harian, mingguan, bulanan, dan bahan pimpinan.", "Reporting Center")
news = scope_news(fetch_news_df(), user, fetch_upt_df())
if news.empty:
    st.info("Belum ada data untuk dilaporkan.")
    st.stop()

created = pd.to_datetime(news["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Jakarta")
news = news.assign(_date=created.dt.date)
min_date = news["_date"].dropna().min() or date.today()
max_date = news["_date"].dropna().max() or date.today()
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    date_range = c1.date_input("Rentang tanggal", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    sentiment = c2.multiselect("Sentimen", sorted(news["sentimen"].unique().tolist()))
    category = c3.multiselect("Kategori", sorted(news["kategori"].unique().tolist()))

filtered = news.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    filtered = filtered[filtered["_date"].between(date_range[0], date_range[1])]
if sentiment: filtered = filtered[filtered["sentimen"].isin(sentiment)]
if category: filtered = filtered[filtered["kategori"].isin(category)]

m = dashboard_metrics(filtered)
kpi_grid([
    {"icon": "📰", "title": "Total", "value": m.total, "foot": "Dalam filter laporan", "accent": "#1769AA"},
    {"icon": "🔴", "title": "Negatif", "value": m.negative, "foot": "Memerlukan telaah", "accent": "#C53A43"},
    {"icon": "🚨", "title": "Urgensi Tinggi", "value": m.high, "foot": "Prioritas", "accent": "#9B2C35"},
    {"icon": "🏢", "title": "UPT Aktif", "value": m.active_upt, "foot": "Kontributor berita", "accent": "#16845B"},
    {"icon": "📊", "title": "Positif", "value": m.positive, "foot": "Pemberitaan positif", "accent": "#16845B"},
    {"icon": "➖", "title": "Netral", "value": m.neutral, "foot": "Pemberitaan netral", "accent": "#D4A72C"},
])

section_header("Data Laporan", f"{len(filtered)} berita sesuai filter.")
columns = ["created_at", "nama_upt", "judul", "media", "platform", "kategori", "subkategori", "sentimen", "urgensi", "status_verifikasi", "link", "ringkasan"]
st.dataframe(filtered[columns], width="stretch", height=430, hide_index=True, column_config={"link": st.column_config.LinkColumn("Link", display_text="Buka")})

c1, c2 = st.columns(2)
with c1:
    st.download_button("Unduh Laporan Excel", excel_bytes(filtered[columns], "Laporan Berita"), f"laporan_simberpas_{date.today().isoformat()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
with c2:
    st.download_button("Unduh Data CSV", filtered[columns].to_csv(index=False).encode("utf-8-sig"), f"laporan_simberpas_{date.today().isoformat()}.csv", "text/csv", use_container_width=True)
