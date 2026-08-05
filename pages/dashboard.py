from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar, sentiment_donut, trend_chart, vertical_bar
from components.layout import format_number, info_panel, kpi_grid, page_header, section_header
from services.access_control import require_permission, scope_news, scope_upt
from services.ai_service import executive_summary
from services.analytics_service import count_table, daily_trend, dashboard_metrics
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.geo_service import build_upt_status
from services.news_service import normalize_status, warning_state
from services.sheet_sync_service import sync_health

user = require_permission("view_dashboard")
page_header(
    "SIMBERPAS — Executive Dashboard",
    "Command center untuk membaca tren, sentimen, verifikasi, dan peta prioritas pemberitaan Pemasyarakatan.",
)

all_upt = fetch_upt_df()
upt = scope_upt(all_upt, user)
news = scope_news(fetch_news_df(), user, all_upt)
if not news.empty:
    news = news.copy()
    news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
    news["warning_state"] = news.apply(warning_state, axis=1)
    if user.role == "executive_decision_maker":
        news = news[news["status_verifikasi"].eq("Terverifikasi") | news["warning_state"].eq("preliminary")].copy()
status_map = build_upt_status(upt, news)
sync = sync_health()
sheet_count = int(news.get("source_type", pd.Series("manual", index=news.index)).eq("google_sheet").sum()) if not news.empty else 0
manual_count = int(news.get("source_type", pd.Series("manual", index=news.index)).eq("manual").sum()) if not news.empty else 0

verified_news = news[news["status_verifikasi"].astype(str) == "Terverifikasi"].copy() if not news.empty else news
pending_count = int(news["status_verifikasi"].isin(["Belum Ditelaah", "Perlu Koreksi"]).sum()) if not news.empty else 0
preliminary_count = int((news.get("warning_state", pd.Series(dtype=str)) == "preliminary").sum()) if not news.empty else 0
critical_upt = int((status_map["marker_status"] == "critical").sum()) if not status_map.empty else 0
negative_upt = int((status_map["marker_status"] == "negative").sum()) if not status_map.empty else 0
no_news_upt = int((status_map["marker_status"] == "none").sum()) if not status_map.empty else 0

if news.empty:
    kpi_grid([
        {"icon": "🏢", "title": "Total UPT", "value": format_number(len(upt)), "foot": "Master lokasi tersedia", "accent": "#1769AA"},
        {"icon": "🔵", "title": "Belum Ada Berita", "value": format_number(no_news_upt), "foot": "Marker biru", "accent": "#2563EB"},
        {"icon": "🧭", "title": "Koordinat", "value": format_number(int(status_map["latitude"].notna().sum())), "foot": "Termasuk titik kandidat", "accent": "#16845B"},
    ])
    info_panel("Status Sistem", "Database berita siap digunakan", "Belum ada berita pada cakupan akun Anda. Peta UPT tetap dapat dibuka.")
    st.stop()

metrics = dashboard_metrics(news)
delta = metrics.today - metrics.yesterday
kpi_grid([
    {"icon": "📰", "title": "Total Berita", "value": format_number(metrics.total), "foot": f"{len(verified_news)} terverifikasi", "accent": "#1769AA"},
    {"icon": "⚠️", "title": "Peringatan Awal", "value": format_number(preliminary_count), "foot": "Tinggi/kritis belum ditelaah", "accent": "#9B1C1C"},
    {"icon": "🕓", "title": "Belum Ditelaah", "value": format_number(pending_count), "foot": "Termasuk perlu koreksi", "accent": "#808080"},
    {"icon": "🟥", "title": "UPT Merah Tua", "value": format_number(critical_upt), "foot": "Tinggi/kritis terverifikasi", "accent": "#650000"},
    {"icon": "🔴", "title": "UPT Merah", "value": format_number(negative_upt), "foot": "Negatif terverifikasi", "accent": "#D00000"},
    {"icon": "🏢", "title": "UPT Terpantau", "value": format_number(metrics.active_upt), "foot": f"dari {len(upt)} UPT", "accent": "#16845B"},
    {"icon": "☁️", "title": "Spreadsheet", "value": format_number(sheet_count), "foot": f"Sinkron terakhir: {sync['status']}", "accent": "#0F766E"},
    {"icon": "📝", "title": "Input Manual", "value": format_number(manual_count), "foot": "Tetap aktif", "accent": "#6B4F9B"},
    {"icon": "⏱️", "title": "Hari Ini", "value": format_number(metrics.today), "foot": f"{delta:+d} dibanding kemarin", "accent": "#D4A72C"},
])

summary_source = verified_news if not verified_news.empty else news
summary, attention, recommendation, provider = executive_summary(summary_source)
summary_html = summary if provider == "Analitik otomatis" else escape(summary).replace("\n", "<br>")
attention_class = {"TINGGI": "sim-attention-high", "SEDANG": "sim-attention-medium"}.get(attention, "sim-attention-low")
left, right = st.columns([1.65, 1])
with left:
    info_panel(provider, "Ringkasan Eksekutif", summary_html)
with right:
    info_panel(
        "Early Warning",
        f'Tingkat Perhatian: <span class="{attention_class}">{escape(attention)}</span>',
        escape(recommendation),
    )

trend = daily_trend(news, 14)
sentiment = count_table(verified_news if not verified_news.empty else news, "sentimen", 10)
section_header("Tren dan Sentimen", "Tren memakai seluruh input; sentimen resmi mengutamakan berita terverifikasi.")
c1, c2 = st.columns([1.7, 1])
with c1:
    st.plotly_chart(trend_chart(trend), width="stretch", config={"displayModeBar": False})
with c2:
    total_sentiment = int(sentiment["Jumlah"].sum()) if not sentiment.empty else 0
    st.plotly_chart(sentiment_donut(sentiment.rename(columns={"sentimen": "Sentimen"}), total_sentiment), width="stretch", config={"displayModeBar": False})

section_header("Distribusi Pemberitaan", "Platform dan kategori paling dominan.")
p1, p2 = st.columns(2)
with p1:
    platform = count_table(news, "platform", 8).rename(columns={"platform": "Platform"})
    st.plotly_chart(horizontal_bar(platform, "Platform", "Jumlah", "blue"), width="stretch", config={"displayModeBar": False})
with p2:
    category = count_table(news, "kategori", 8).rename(columns={"kategori": "Kategori"})
    st.plotly_chart(vertical_bar(category, "Kategori", "Jumlah", "gold"), width="stretch", config={"displayModeBar": False})

section_header("Prioritas Pemberitaan", "Peringatan awal ditampilkan dengan label jelas; hasil resmi tetap mengutamakan berita terverifikasi.")
verified_priority = verified_news[
    verified_news["urgensi"].isin(["Tinggi", "Kritis"]) | verified_news["sentimen"].eq("Negatif")
] if not verified_news.empty else verified_news
preliminary_priority = news[news.get("warning_state", pd.Series("", index=news.index)).eq("preliminary")] if not news.empty else news
priority = pd.concat([preliminary_priority, verified_priority], ignore_index=True).drop_duplicates(subset=["id"], keep="first") if not news.empty else news
priority = priority.sort_values("created_at", ascending=False).head(8) if not priority.empty else priority
p1, p2 = st.columns([1.3, 1])
with p1:
    if priority.empty:
        st.success("Belum ada berita yang masuk prioritas.")
    else:
        rows = []
        for _, row in priority.iterrows():
            title = escape(str(row["judul"])[:105])
            meta = escape(f'{row["nama_upt"]} • {row["media"]} • {row["urgensi"]}')
            rows.append(
                f'<div class="sim-priority-row"><div class="sim-priority-badge">' + ('AWAL' if row.get('warning_state') == 'preliminary' else 'RESMI') + '</div>'
                f'<div><div class="sim-priority-title">{title}</div><div class="sim-priority-meta">{meta}</div></div></div>'
            )
        st.markdown('<div class="sim-panel">' + ''.join(rows) + '</div>', unsafe_allow_html=True)
with p2:
    status_summary = status_map["marker_label"].value_counts().reset_index()
    status_summary.columns = ["Status Peta", "Jumlah UPT"]
    st.dataframe(status_summary, width="stretch", hide_index=True)
