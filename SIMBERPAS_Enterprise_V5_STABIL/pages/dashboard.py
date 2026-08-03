from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.charts import horizontal_bar, sentiment_donut, trend_chart, vertical_bar
from components.layout import format_number, info_panel, kpi_grid, page_header, section_header
from services.access_control import scope_news, scope_upt
from services.ai_service import executive_summary
from services.analytics_service import count_table, daily_trend, dashboard_metrics
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df

user = current_user()
page_header(
    "SIMBERPAS — Executive Dashboard",
    "Command center untuk membaca tren, sentimen, prioritas, dan aktivitas pemberitaan Pemasyarakatan secara cepat.",
)

news = scope_news(fetch_news_df(), user, fetch_upt_df())
upt = scope_upt(fetch_upt_df(), user)

if news.empty:
    info_panel("Status Sistem", "Database siap digunakan", "Belum ada berita pada cakupan akun Anda.")
    st.stop()

metrics = dashboard_metrics(news)
delta = metrics.today - metrics.yesterday
kpi_grid([
    {"icon": "📰", "title": "Total Berita", "value": format_number(metrics.total), "foot": f"{metrics.month} pada bulan berjalan", "accent": "#1769AA"},
    {"icon": "⏱️", "title": "Hari Ini", "value": format_number(metrics.today), "foot": f"{delta:+d} dibanding kemarin", "accent": "#D4A72C"},
    {"icon": "🔴", "title": "Negatif", "value": format_number(metrics.negative), "foot": f"{metrics.negative / max(metrics.total,1) * 100:.1f}% dari seluruh berita", "accent": "#C53A43"},
    {"icon": "🚨", "title": "Urgensi Tinggi", "value": format_number(metrics.high), "foot": "Prioritas telaah", "accent": "#9B2C35"},
    {"icon": "🏢", "title": "UPT Aktif", "value": format_number(metrics.active_upt), "foot": f"dari {len(upt)} UPT dalam cakupan", "accent": "#16845B"},
    {"icon": "📅", "title": "7 Hari", "value": format_number(metrics.week), "foot": "Volume satu minggu", "accent": "#6F52A2"},
])

summary, attention, recommendation, provider = executive_summary(news)
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
sentiment = count_table(news, "sentimen", 10)
section_header("Tren dan Sentimen", "Perubahan volume berita selama 14 hari terakhir.")
c1, c2 = st.columns([1.7, 1])
with c1:
    st.plotly_chart(trend_chart(trend), width="stretch", config={"displayModeBar": False})
with c2:
    st.plotly_chart(sentiment_donut(sentiment.rename(columns={"sentimen": "Sentimen"}), metrics.total), width="stretch", config={"displayModeBar": False})

section_header("Distribusi Pemberitaan", "Sumber dan kategori yang paling dominan.")
p1, p2 = st.columns(2)
with p1:
    platform = count_table(news, "platform", 8).rename(columns={"platform": "Platform"})
    st.plotly_chart(horizontal_bar(platform, "Platform", "Jumlah", "blue"), width="stretch", config={"displayModeBar": False})
with p2:
    category = count_table(news, "kategori", 8).rename(columns={"kategori": "Kategori"})
    st.plotly_chart(vertical_bar(category, "Kategori", "Jumlah", "gold"), width="stretch", config={"displayModeBar": False})

section_header("Prioritas dan Aktivitas UPT", "Berita yang perlu dibaca terlebih dahulu dan UPT paling aktif.")
priority = news[(news["urgensi"] == "Tinggi") | (news["sentimen"] == "Negatif")].sort_values("created_at", ascending=False).head(6)
top_upt = count_table(news, "nama_upt", 10).rename(columns={"nama_upt": "UPT"})
b1, b2 = st.columns([1.3, 1])
with b1:
    if priority.empty:
        st.success("Tidak ada berita negatif atau berurgensi tinggi.")
    else:
        rows = []
        for _, row in priority.iterrows():
            title = escape(str(row["judul"])[:105])
            meta = escape(f'{row["nama_upt"]} • {row["media"]} • {row["urgensi"]}')
            rows.append(f'<div class="sim-priority-row"><div class="sim-priority-badge">PRIORITAS</div><div><div class="sim-priority-title">{title}</div><div class="sim-priority-meta">{meta}</div></div></div>')
        st.markdown('<div class="sim-panel">' + ''.join(rows) + '</div>', unsafe_allow_html=True)
with b2:
    st.dataframe(
        top_upt,
        width="stretch",
        hide_index=True,
        column_config={
            "UPT": st.column_config.TextColumn("Nama UPT"),
            "Jumlah": st.column_config.ProgressColumn("Jumlah", min_value=0, max_value=max(int(top_upt["Jumlah"].max()), 1), format="%d"),
        },
    )
