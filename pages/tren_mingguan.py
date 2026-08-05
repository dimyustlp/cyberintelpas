from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.trend_service import build_weekly_snapshot, fetch_news_for_analysis

user = current_user()
if user is None or not has_permission(user, "view_weekly_trends"):
    st.error("Anda tidak memiliki akses ke Analisis Tren Mingguan.")
    st.stop()

st.title("Analisis Tren Pemberitaan Mingguan")
st.caption("Satu link unik dihitung sebagai satu publikasi. Kesamaan kasus tidak menghapus publikasi dari media berbeda.")

today = date.today()
default_start = today - timedelta(days=6)
col1, col2 = st.columns(2)
with col1:
    start = st.date_input("Tanggal awal", value=default_start)
with col2:
    end = st.date_input("Tanggal akhir", value=today)
if start > end:
    st.error("Tanggal awal tidak boleh melewati tanggal akhir.")
    st.stop()

with st.spinner("Menghitung link unik, media, UPT, isu, dan urgensi..."):
    snapshot = build_weekly_snapshot(fetch_news_for_analysis(), start, end)

metrics = snapshot["metrics"]
cols = st.columns(6)
for column, label, value in zip(cols, [
    "Publikasi unik", "Publikasi negatif", "UPT negatif", "Media unik", "Kelompok isu", "Tinggi/Kritis"
], [
    metrics["total_publications"], metrics["negative_publications"], metrics["negative_upt_count"],
    metrics["unique_media"], metrics["issue_count"], metrics["high_critical_count"],
]):
    column.metric(label, value)

unmapped_negative = int(metrics.get("unmapped_negative_publications") or 0)
if unmapped_negative:
    st.warning(f"{unmapped_negative} publikasi negatif belum dipetakan ke UPT. Data tersebut tetap tersimpan, tetapi tidak dihitung dalam peringkat UPT.")

change = metrics.get("negative_change_percent")
if change is None:
    st.info("Periode sebelumnya tidak memiliki publikasi negatif pembanding. Persentase perubahan tidak dihitung.")
elif change > 0:
    st.warning(f"Publikasi negatif naik {change:.1f}% dibanding periode sebelumnya.")
elif change < 0:
    st.success(f"Publikasi negatif turun {abs(change):.1f}% dibanding periode sebelumnya.")
else:
    st.info("Jumlah publikasi negatif tidak berubah dibanding periode sebelumnya.")

trend_df = pd.DataFrame(snapshot["daily_trend"])
trend_df["Tanggal"] = pd.to_datetime(trend_df["Tanggal"])
fig_trend = px.line(trend_df, x="Tanggal", y="Jumlah Publikasi", markers=True)
st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

upt_df = pd.DataFrame(snapshot["upt_table"])
if upt_df.empty:
    st.info("Belum ada publikasi negatif yang dapat dipetakan pada periode tersebut.")
else:
    st.subheader("Peringkat UPT berdasarkan publikasi negatif")
    st.dataframe(
        upt_df,
        use_container_width=True,
        hide_index=True,
        column_order=["UPT", "Jumlah Publikasi", "Jumlah Media", "Jumlah Isu", "Berita Negatif", "Urgensi Tertinggi", "Isu Utama"],
    )
    top = upt_df.head(10).sort_values("Berita Negatif")
    fig_upt = px.bar(top, x="Berita Negatif", y="UPT", orientation="h", hover_data=["Jumlah Media", "Jumlah Isu"])
    st.plotly_chart(fig_upt, use_container_width=True, config={"displayModeBar": False})

left, right = st.columns(2)
with left:
    sent_df = pd.DataFrame(snapshot["sentiment_distribution"])
    if not sent_df.empty:
        st.subheader("Komposisi sentimen")
        st.plotly_chart(px.pie(sent_df, names="sentimen", values="Jumlah"), use_container_width=True, config={"displayModeBar": False})
with right:
    urg_df = pd.DataFrame(snapshot["urgency_distribution"])
    if not urg_df.empty:
        st.subheader("Komposisi urgensi")
        st.plotly_chart(px.bar(urg_df, x="urgensi", y="Jumlah", text="Jumlah"), use_container_width=True, config={"displayModeBar": False})
