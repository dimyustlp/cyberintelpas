from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from components.layout import page_header, section_header
from services.access_control import can_edit_news, has_permission, require_permission, scope_news
from services.attachment_service import archive_attachment, list_attachments, signed_url, upload_attachment
from services.audit_service import log_action
from services.database import fetch_all, fetch_news_df, fetch_upt_df, table_exists
from services.export_service import excel_bytes
from services.news_service import WORKFLOW_STATUSES, change_news_status, normalize_status, update_news, warning_state

user = require_permission("view_data")
page_header(
    "Pusat Data Berita",
    "Telusuri data, status telaah, sumber, lampiran, dan riwayat perubahan berita.",
    "Central News Database",
)

upt_df = fetch_upt_df()
news = scope_news(fetch_news_df(), user, upt_df)
if news.empty:
    st.info("Belum ada data berita yang dapat ditampilkan untuk akun Anda.")
    st.stop()

news = news.copy()
news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
news["warning_state"] = news.apply(warning_state, axis=1)

# Pimpinan melihat hasil terverifikasi dan peringatan awal tinggi/kritis, bukan seluruh antrean kerja biasa.
if user.role == "executive_viewer":
    news = news[
        news["status_verifikasi"].eq("Terverifikasi")
        | news["warning_state"].eq("preliminary")
    ].copy()

status_counts = news["status_verifikasi"].value_counts()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Belum Ditelaah", int(status_counts.get("Belum Ditelaah", 0)))
k2.metric("Perlu Koreksi", int(status_counts.get("Perlu Koreksi", 0)))
k3.metric("Terverifikasi", int(status_counts.get("Terverifikasi", 0)))
k4.metric("Tidak Valid", int(status_counts.get("Tidak Valid", 0)))
k5.metric("Diarsipkan", int(status_counts.get("Diarsipkan", 0)))

with st.expander("Makna status", expanded=False):
    st.markdown(
        """
        **Belum Ditelaah → Terverifikasi / Perlu Koreksi / Tidak Valid → Diarsipkan.**

        Berita Tinggi/Kritis yang belum ditelaah tetap dapat tampil sebagai **Peringatan Awal**, tetapi belum menjadi hasil resmi.
        """
    )

with st.container(border=True):
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    upt_filter = r1c1.multiselect("UPT", sorted(news["nama_upt"].dropna().astype(str).unique().tolist()))
    sentiment_filter = r1c2.multiselect("Sentimen", sorted(news["sentimen"].dropna().astype(str).unique().tolist()))
    urgency_filter = r1c3.multiselect("Urgensi", sorted(news["urgensi"].dropna().astype(str).unique().tolist()))
    status_filter = r1c4.multiselect("Status telaah", WORKFLOW_STATUSES)

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    platform_filter = r2c1.multiselect("Platform", sorted(news["platform"].dropna().astype(str).unique().tolist()))
    category_filter = r2c2.multiselect("Kategori", sorted(news["kategori"].dropna().astype(str).unique().tolist()))
    source_filter = r2c3.multiselect("Sumber input", sorted(news["source_type"].dropna().astype(str).unique().tolist()))
    warning_filter = r2c4.multiselect(
        "Jenis peringatan",
        ["Peringatan Awal", "Peringatan Terverifikasi", "Bukan Warning"],
    )

    min_dt = pd.to_datetime(news["created_at"], errors="coerce", utc=True).min()
    max_dt = pd.to_datetime(news["created_at"], errors="coerce", utc=True).max()
    default_start = min_dt.date() if pd.notna(min_dt) else date.today()
    default_end = max_dt.date() if pd.notna(max_dt) else date.today()
    d1, d2, qcol = st.columns([1, 1, 2])
    start_date = d1.date_input("Dari tanggal", value=default_start)
    end_date = d2.date_input("Sampai tanggal", value=default_end)
    q = qcol.text_input("Cari judul, media, kategori, UPT, petugas, atau link")

filtered = news.copy()
if upt_filter:
    filtered = filtered[filtered["nama_upt"].isin(upt_filter)]
if sentiment_filter:
    filtered = filtered[filtered["sentimen"].isin(sentiment_filter)]
if urgency_filter:
    filtered = filtered[filtered["urgensi"].isin(urgency_filter)]
if status_filter:
    filtered = filtered[filtered["status_verifikasi"].isin(status_filter)]
if platform_filter:
    filtered = filtered[filtered["platform"].isin(platform_filter)]
if category_filter:
    filtered = filtered[filtered["kategori"].isin(category_filter)]
if source_filter:
    filtered = filtered[filtered["source_type"].isin(source_filter)]
if warning_filter:
    states = []
    if "Peringatan Awal" in warning_filter:
        states.append("preliminary")
    if "Peringatan Terverifikasi" in warning_filter:
        states.append("verified")
    if "Bukan Warning" in warning_filter:
        states.append("none")
    filtered = filtered[filtered["warning_state"].isin(states)]

created_local = pd.to_datetime(filtered["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Jakarta")
filtered = filtered[(created_local.dt.date >= start_date) & (created_local.dt.date <= end_date)]
if q:
    search_cols = [c for c in ["judul", "media", "kategori", "subkategori", "link", "nama_upt", "nama_petugas", "ringkasan"] if c in filtered.columns]
    mask = filtered[search_cols].astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)
    filtered = filtered[mask]

filtered = filtered.sort_values("created_at", ascending=False)
section_header("Hasil Pencarian", f"{len(filtered)} berita ditemukan.")
if filtered.empty:
    st.info("Tidak ada berita yang sesuai dengan filter.")
    st.stop()

if has_permission(user, "export_reports"):
    st.download_button(
        "Unduh hasil ke Excel",
        data=excel_bytes(filtered, "Berita"),
        file_name="SIMBERPAS_Data_Berita.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click=log_action,
        args=("export", "berita", "filter", user.username, user.role, {"rows": len(filtered), "format": "xlsx"}),
    )

options = filtered["id"].astype(str).tolist()
lookup = filtered.set_index(filtered["id"].astype(str), drop=False)

def _label(news_id: str) -> str:
    row = lookup.loc[news_id]
    prefix = "⚠️ " if row.get("warning_state") == "preliminary" else "🚨 " if row.get("warning_state") == "verified" else ""
    return f"{prefix}{row.get('status_verifikasi', '-')} | {str(row.get('judul') or 'Tanpa judul')[:95]} | {row.get('nama_upt', '-')}"

selected_id = st.selectbox("Pilih berita untuk melihat detail", options, format_func=_label)
row = lookup.loc[selected_id]
news_id = str(row.get("id") or "")
current_status = normalize_status(str(row.get("status_verifikasi") or "Belum Ditelaah"))

section_header("Detail Berita", str(row.get("judul") or "Tanpa judul"))
left, right = st.columns([2, 1])
with left:
    st.markdown(f"**UPT:** {row.get('nama_upt', '-')}  ")
    st.markdown(f"**Media/Platform:** {row.get('media', '-')} / {row.get('platform', '-')}  ")
    st.markdown(f"**Kategori:** {row.get('kategori', '-')} — {row.get('subkategori', '-')}  ")
    st.markdown(f"**Sentimen/Urgensi:** {row.get('sentimen', '-')} / {row.get('urgensi', '-')}  ")
    st.markdown(f"**Ringkasan:** {row.get('ringkasan', '-')}")
with right:
    if row.get("warning_state") == "preliminary":
        st.error("⚠️ PERINGATAN AWAL\n\nBelum Ditelaah")
    elif row.get("warning_state") == "verified":
        st.error("🚨 PERINGATAN TERVERIFIKASI")
    else:
        st.info(f"Status: **{current_status}**")
    st.caption(f"Penginput: {row.get('nama_petugas') or row.get('created_by') or '-'}")
    st.caption(f"Sumber input: {row.get('source_type', 'manual')}")
    if row.get("link"):
        st.link_button("Buka sumber berita", str(row.get("link")), use_container_width=True)

if can_edit_news(user, row) and current_status not in {"Diarsipkan", "Tidak Valid"}:
    full_analysis_edit = has_permission(user, "analyze_news")
    with st.expander("Koreksi Data Berita", expanded=current_status == "Perlu Koreksi"):
        with st.form(f"edit_news_{news_id}"):
            e1, e2 = st.columns(2)
            title = e1.text_input("Judul", value=str(row.get("judul") or ""))
            media = e2.text_input("Media/Akun", value=str(row.get("media") or ""))
            link = st.text_input("Link", value=str(row.get("link") or ""))
            caption = st.text_area("Caption/transkrip/keterangan sumber", value=str(row.get("caption_manual") or ""), height=100)
            note = st.text_area("Catatan penginput", value=str(row.get("catatan") or ""), height=80)
            payload = {"judul": title, "media": media, "link": link, "caption_manual": caption, "catatan": note}
            if full_analysis_edit:
                category = e1.text_input("Kategori", value=str(row.get("kategori") or ""))
                subcategory = e2.text_input("Subkategori", value=str(row.get("subkategori") or ""))
                sentiments = ["Positif", "Netral", "Negatif", "Campuran"]
                current_sentiment = str(row.get("sentimen") or "Netral")
                sentiment = e1.selectbox("Sentimen", sentiments, index=sentiments.index(current_sentiment) if current_sentiment in sentiments else 1)
                urgencies = ["Rendah", "Sedang", "Tinggi", "Kritis"]
                current_urgency = str(row.get("urgensi") or "Rendah")
                urgency = e2.selectbox("Urgensi", urgencies, index=urgencies.index(current_urgency) if current_urgency in urgencies else 0)
                summary = st.text_area("Ringkasan", value=str(row.get("ringkasan") or ""), height=120)
                payload.update({"kategori": category, "subkategori": subcategory, "sentimen": sentiment, "urgensi": urgency, "ringkasan": summary})
            save_edit = st.form_submit_button("SIMPAN KOREKSI", type="primary", use_container_width=True)
        if save_edit:
            try:
                update_news(news_id, payload, user.username, user.role)
                if current_status == "Perlu Koreksi" and not full_analysis_edit:
                    change_news_status(news_id, "Belum Ditelaah", "Koreksi telah disimpan oleh penginput", user.username, user.role)
                    st.success("Koreksi disimpan dan dikirim kembali ke antrean Belum Ditelaah.")
                else:
                    st.success("Koreksi berhasil disimpan.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

if has_permission(user, "review_news"):
    st.info("Keputusan verifikasi dilakukan melalui menu **Pusat Telaah** agar antrean dan prioritas tetap terpusat.")

section_header("Bukti dan Lampiran", "JPG, PNG, dan PDF; maksimal 10 MB per file.")
attachments = list_attachments(news_id) if news_id else []
if attachments:
    for attachment in attachments:
        cols = st.columns([4, 2, 1])
        cols[0].write(f"📎 **{attachment.get('file_name', 'Lampiran')}**")
        cols[1].caption(f"{int(attachment.get('size_bytes') or 0) / 1024:.1f} KB • {attachment.get('uploaded_by') or '-'}")
        url = signed_url(str(attachment.get("storage_path") or ""))
        if url:
            cols[2].link_button("Buka", url, use_container_width=True)
        if has_permission(user, "archive_news"):
            with st.expander(f"Kelola {attachment.get('file_name', 'lampiran')}"):
                if st.button("Arsipkan lampiran", key=f"archive_attachment_{attachment.get('id')}"):
                    archive_attachment(str(attachment.get("id")), user.username, user.role)
                    st.success("Lampiran diarsipkan.")
                    st.rerun()
else:
    st.caption("Belum ada lampiran.")

if has_permission(user, "upload_attachments") and news_id and current_status != "Diarsipkan":
    with st.form(f"upload_attachment_{news_id}"):
        new_files = st.file_uploader("Tambah lampiran", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)
        attachment_note = st.text_input("Keterangan lampiran")
        upload_submit = st.form_submit_button("UNGGAH LAMPIRAN")
    if upload_submit:
        if not new_files:
            st.warning("Pilih setidaknya satu file.")
        elif len(new_files) > 5:
            st.error("Maksimal 5 file dalam satu kali unggah.")
        else:
            errors = []
            for file in new_files:
                try:
                    upload_attachment(news_id, file.name, file.getvalue(), user.username, user.role, attachment_note)
                except Exception as exc:
                    errors.append(f"{file.name}: {exc}")
            if errors:
                st.warning("Sebagian file gagal: " + "; ".join(errors))
            else:
                st.success("Lampiran berhasil diunggah.")
            st.rerun()

if table_exists("berita_status_history") and news_id:
    with st.expander("Riwayat Status"):
        history = pd.DataFrame(
            fetch_all(
                "berita_status_history",
                "created_at,status_from,status_to,changed_by,changed_by_role,note,reason,berita_id",
                order_by="created_at",
                desc=True,
            )
        )
        if not history.empty:
            history = history[history["berita_id"].astype(str) == news_id]
        if history.empty:
            st.caption("Belum ada riwayat status.")
        else:
            st.dataframe(history[["created_at", "status_from", "status_to", "changed_by", "note", "reason"]], width="stretch", hide_index=True)
