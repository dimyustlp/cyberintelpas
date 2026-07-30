from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import page_header, section_header
from services.access_control import require_permission, scope_upt
from services.auth_service import current_user
from services.database import fetch_upt_df
from services.news_service import analyze_news, clean_text, normalize_url, save_news

user = require_permission("create_news")
page_header(
    "Input & Analisis Berita",
    "Masukkan tautan, periksa hasil analisis otomatis, koreksi bila diperlukan, lalu simpan ke database nasional.",
    "Monitoring Operations",
)

upt_df = scope_upt(fetch_upt_df(), user)
upt_names = sorted(upt_df.loc[upt_df["aktif"] == True, "nama_upt"].dropna().astype(str).tolist())
if not upt_names:
    st.warning("Daftar UPT pada cakupan akun ini belum tersedia. Hubungi administrator.")
    st.stop()

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

with st.form("process_news"):
    c1, c2 = st.columns(2)
    with c1:
        default_upt = user.assigned_upt if user.assigned_upt in upt_names else None
        nama_upt = st.selectbox("Nama UPT", upt_names, index=upt_names.index(default_upt) if default_upt else None, placeholder="Pilih UPT")
    with c2:
        nama_petugas = st.text_input("Nama petugas/penginput", value=user.full_name or user.username)
    link = st.text_input("Link berita", placeholder="https://...")
    manual_text = st.text_area("Caption/teks tambahan", placeholder="Tempel caption media sosial atau isi penting agar analisis lebih akurat.", height=130)
    process = st.form_submit_button("PROSES & ANALISIS", type="primary", use_container_width=True)

if process:
    url = normalize_url(link)
    if not nama_upt or not url:
        st.warning("Nama UPT dan link berita wajib diisi.")
    else:
        with st.spinner("Membaca dan menganalisis berita..."):
            result = analyze_news(url, manual_text)
        st.session_state.analysis_result = {
            **result,
            "nama_upt": nama_upt,
            "nama_petugas": clean_text(nama_petugas),
            "link": url,
            "caption_manual": clean_text(manual_text),
        }

result = st.session_state.analysis_result
if result:
    section_header("Hasil Analisis dan Koreksi", "Periksa seluruh isian sebelum data disimpan.")
    with st.form("save_news"):
        a, b = st.columns(2)
        with a:
            title = st.text_input("Judul", value=str(result.get("judul", "")))
            media = st.text_input("Media/Akun", value=str(result.get("media", "")))
            platform_options = ["Portal Berita", "Instagram", "Facebook", "TikTok", "YouTube", "Google News", "Lainnya"]
            platform_value = result.get("platform", "Portal Berita")
            platform = st.selectbox("Platform", platform_options, index=platform_options.index(platform_value) if platform_value in platform_options else 0)
            published = st.text_input("Tanggal publikasi", value=str(result.get("tanggal_publikasi", "")))
        with b:
            categories = ["Keamanan dan Ketertiban", "Pembinaan", "Pelayanan", "SDM", "Sarana dan Prasarana", "Kehumasan", "Lainnya"]
            category_value = result.get("kategori", "Lainnya")
            category = st.selectbox("Kategori", categories, index=categories.index(category_value) if category_value in categories else len(categories)-1)
            subcategory = st.text_input("Subkategori", value=str(result.get("subkategori", "Umum")))
            sentiment_options = ["Positif", "Netral", "Negatif"]
            sentiment_value = result.get("sentimen", "Netral")
            sentiment = st.selectbox("Sentimen", sentiment_options, index=sentiment_options.index(sentiment_value) if sentiment_value in sentiment_options else 1)
            urgency_options = ["Rendah", "Sedang", "Tinggi"]
            urgency_value = result.get("urgensi", "Rendah")
            urgency = st.selectbox("Urgensi", urgency_options, index=urgency_options.index(urgency_value) if urgency_value in urgency_options else 0)
        summary = st.text_area("Ringkasan", value=str(result.get("ringkasan", "")), height=150)
        keywords = st.text_input("Kata kunci", value=", ".join(result.get("kata_kunci", []) or []))
        notes = st.text_area("Catatan", height=90)
        submitted = st.form_submit_button("SIMPAN KE DATABASE", type="primary", use_container_width=True)

    if submitted:
        published_value = None
        parsed = pd.to_datetime(published, errors="coerce") if published else None
        if parsed is not None and not pd.isna(parsed):
            published_value = parsed.isoformat()
        payload = {
            "nama_upt": result["nama_upt"],
            "nama_petugas": result["nama_petugas"],
            "link": result["link"],
            "judul": clean_text(title),
            "media": clean_text(media),
            "platform": platform,
            "tanggal_publikasi": published_value,
            "kategori": category,
            "subkategori": clean_text(subcategory),
            "sentimen": sentiment,
            "urgensi": urgency,
            "ringkasan": clean_text(summary),
            "caption_manual": result.get("caption_manual", ""),
            "status_baca": result.get("status_baca", ""),
            "catatan": clean_text(notes),
            "status_verifikasi": "Draft",
            "kata_kunci": [clean_text(x) for x in keywords.split(",") if clean_text(x)],
            "lokasi": result.get("lokasi", ""),
            "tingkat_perhatian": result.get("tingkat_perhatian", urgency),
            "ai_provider": result.get("ai_provider", "rules"),
            "ai_confidence": result.get("ai_confidence"),
        }
        ok, message = save_news(payload, user.username, user.role)
        if ok:
            st.success(message)
            st.session_state.analysis_result = None
        else:
            st.error(message)
