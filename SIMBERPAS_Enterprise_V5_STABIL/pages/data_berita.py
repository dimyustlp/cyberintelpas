from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import page_header, section_header
from services.access_control import has_permission, scope_news
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.export_service import excel_bytes
from services.news_service import delete_news, update_news

user = current_user()
page_header("Pusat Data Berita", "Telusuri, filter, verifikasi, edit, dan ekspor data pemberitaan dalam satu tempat.", "Monitoring Database")
news = scope_news(fetch_news_df(), user, fetch_upt_df())
if news.empty:
    st.info("Belum ada data berita pada cakupan akun Anda.")
    st.stop()

with st.container(border=True):
    f1, f2, f3, f4 = st.columns(4)
    upt_filter = f1.multiselect("UPT", sorted(news["nama_upt"].unique().tolist()))
    sentiment_filter = f2.multiselect("Sentimen", sorted(news["sentimen"].unique().tolist()))
    platform_filter = f3.multiselect("Platform", sorted(news["platform"].unique().tolist()))
    urgency_filter = f4.multiselect("Urgensi", sorted(news["urgensi"].unique().tolist()))
    q = st.text_input("Cari judul, media, kategori, atau link", placeholder="Ketik kata pencarian...")

filtered = news.copy()
if upt_filter: filtered = filtered[filtered["nama_upt"].isin(upt_filter)]
if sentiment_filter: filtered = filtered[filtered["sentimen"].isin(sentiment_filter)]
if platform_filter: filtered = filtered[filtered["platform"].isin(platform_filter)]
if urgency_filter: filtered = filtered[filtered["urgensi"].isin(urgency_filter)]
if q:
    mask = filtered[["judul", "media", "kategori", "subkategori", "link"]].astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
    filtered = filtered[mask]

section_header("Hasil Pencarian", f"{len(filtered)} berita ditemukan.")
display_cols = ["created_at", "nama_upt", "judul", "media", "platform", "kategori", "sentimen", "urgensi", "status_verifikasi", "link"]
event = st.dataframe(
    filtered[display_cols],
    width="stretch",
    height=460,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "created_at": st.column_config.DatetimeColumn("Tanggal Input", format="DD MMM YYYY, HH:mm"),
        "link": st.column_config.LinkColumn("Link", display_text="Buka"),
    },
)

c1, c2 = st.columns(2)
with c1:
    st.download_button("Unduh Excel", excel_bytes(filtered[display_cols]), "rekap_berita_simberpas.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
with c2:
    st.download_button("Unduh CSV", filtered[display_cols].to_csv(index=False).encode("utf-8-sig"), "rekap_berita_simberpas.csv", "text/csv", use_container_width=True)

selected_rows = event.selection.rows if event and hasattr(event, "selection") else []
if selected_rows:
    row = filtered.iloc[selected_rows[0]]
    section_header("Detail Berita", "Data yang dipilih dari tabel.")
    with st.container(border=True):
        st.subheader(str(row["judul"]))
        st.caption(f'{row["nama_upt"]} • {row["media"]} • {row["platform"]}')
        st.write(row["ringkasan"] or "Ringkasan belum tersedia.")
        if row["link"]:
            st.link_button("Buka sumber berita", row["link"])

    can_edit = has_permission(user, "edit_news") or (has_permission(user, "edit_own_news") and row["nama_petugas"] == user.full_name)
    if can_edit and row["id"]:
        with st.expander("Edit dan Verifikasi"):
            with st.form("edit_news_form"):
                title = st.text_input("Judul", value=str(row["judul"]))
                summary = st.text_area("Ringkasan", value=str(row["ringkasan"]), height=130)
                sentiment = st.selectbox("Sentimen", ["Positif", "Netral", "Negatif"], index=["Positif", "Netral", "Negatif"].index(row["sentimen"]) if row["sentimen"] in ["Positif", "Netral", "Negatif"] else 1)
                urgency = st.selectbox("Urgensi", ["Rendah", "Sedang", "Tinggi"], index=["Rendah", "Sedang", "Tinggi"].index(row["urgensi"]) if row["urgensi"] in ["Rendah", "Sedang", "Tinggi"] else 0)
                status = st.selectbox("Status verifikasi", ["Draft", "Terverifikasi", "Ditolak"], index=["Draft", "Terverifikasi", "Ditolak"].index(row["status_verifikasi"]) if row["status_verifikasi"] in ["Draft", "Terverifikasi", "Ditolak"] else 0)
                if st.form_submit_button("Simpan Perubahan", type="primary"):
                    update_news(str(row["id"]), {"judul": title, "ringkasan": summary, "sentimen": sentiment, "urgensi": urgency, "status_verifikasi": status}, user.username, user.role)
                    st.success("Perubahan disimpan.")
                    st.rerun()
        if has_permission(user, "delete_news"):
            with st.expander("Zona Berbahaya"):
                confirm = st.checkbox("Saya memahami bahwa data akan dihapus permanen.")
                if st.button("Hapus Berita", type="primary", disabled=not confirm):
                    delete_news(str(row["id"]), user.username, user.role)
                    st.success("Berita dihapus.")
                    st.rerun()
