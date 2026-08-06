from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import page_header, section_header
from services.access_control import has_permission, require_permission, scope_news, scope_upt
from services.attachment_service import upload_attachment
from services.database import fetch_news_df, fetch_upt_df
from services.news_service import (
    analyze_news,
    clean_text,
    find_duplicate_news,
    normalize_url,
    save_news,
)

# --- 1. VERIFIKASI HAK AKSES & INISIALISASI ---
user = require_permission("create_news")
can_analyze = has_permission(user, "analyze_news")

page_header(
    "Input & Analisis Berita (Hybrid System)" if can_analyze else "Input Berita",
    (
        "Masukkan tautan, koreksi hasil analisis AI/Bot, deteksi duplikat real-time, lalu kirim ke Pusat Telaah."
        if can_analyze
        else "Masukkan sumber berita dan bukti pendukung. Analisis otomatis dicatat untuk ditelaah oleh Analis Pemberitaan Strategis."
    ),
    "Central News Intake",
)

all_upt = fetch_upt_df()
upt_df = scope_upt(all_upt, user)
upt_names = sorted(upt_df.loc[upt_df["aktif"] == True, "nama_upt"].dropna().astype(str).unique().tolist())
if not upt_names:
    st.warning("Daftar UPT belum tersedia. Hubungi Administrator Utama Sistem.")
    st.stop()

st.session_state.setdefault("analysis_result", None)
st.session_state.setdefault("duplicate_info", None)

# --- 2. PENJELASAN ALUR KERJA HYBRID ---
with st.expander("ℹ️ Alur Kerja Hybrid & Anti-Duplikasi Cyber-Intelpas", expanded=False):
    st.markdown(
        """
        **Input Manual/Bot Otomatis → Belum Ditelaah → Telaah Analis → Terverifikasi / Perlu Koreksi / Tidak Valid.**
        
        * **Anti-Duplikasi Lapis 1 (Normalisasi):** Tautan berita otomatis dibersihkan dari parameter pelacak iklan (`?utm_source=...`).
        * **Anti-Duplikasi Lapis 2 (Live Warning):** Jika berita sudah pernah ditarik oleh Bot Scraper atau petugas lain, sistem langsung memberi peringatan kuning.
        * **Smart Upsert Lapis 3:** Input manual dari manusia memiliki prioritas lebih tinggi untuk melengkapi/memperbarui data hasil tarikan bot otomatis.
        """
    )

# --- 3. TAHAP 1: FORM PENGAMBILAN & ANALISIS SUMBER ---
with st.form("process_news"):
    c1, c2 = st.columns(2)
    nama_upt = c1.selectbox("Nama UPT", upt_names, index=None, placeholder="Pilih UPT")
    nama_petugas = c2.text_input("Nama penginput", value=user.full_name or user.username, disabled=True)
    link = st.text_input("Link berita *", placeholder="https://...")
    manual_text = st.text_area(
        "Caption, transkrip, atau keterangan sumber",
        placeholder="Tempel teks unggahan media sosial atau informasi penting dari sumber.",
        height=130,
    )
    process = st.form_submit_button("🔍 PROSES SUMBER & CEK DUPLIKASI", type="primary", use_container_width=True)

if process:
    # Lapis 1: Normalisasi URL
    url = normalize_url(link)
    if not nama_upt or not url:
        st.warning("Nama UPT dan link berita wajib diisi.")
    else:
        with st.spinner("Membaca sumber, mendeteksi duplikasi, dan menjalankan klasifikasi awal..."):
            result = analyze_news(url, manual_text)
            
            # Cek Duplikasi Real-time terhadap database eksisting (Lapis 2)
            visible_news = scope_news(fetch_news_df(), user, all_upt)
            existing_dups = find_duplicate_news(
                url, 
                str(result.get("judul", "")), 
                str(result.get("media", "")), 
                nama_upt, 
                "", 
                visible_news
            )
            
            st.session_state.duplicate_info = existing_dups if not existing_dups.empty else None
            st.session_state.analysis_result = {
                **result,
                "nama_upt": nama_upt,
                "nama_petugas": clean_text(nama_petugas),
                "link": url,
                "caption_manual": clean_text(manual_text),
            }

result = st.session_state.analysis_result
if not result:
    st.info("💡 Masukkan tautan berita di atas lalu klik 'PROSES SUMBER & CEK DUPLIKASI' untuk memulai.")
    st.stop()

# --- 4. ANTI-DUPLIKASI LAPIS 2: LIVE WARNING ALERT ---
existing_dups = st.session_state.duplicate_info
if existing_dups is not None and not existing_dups.empty:
    first_dup = existing_dups.iloc[0]
    st.warning(
        f"⚠️ **LINK/BERITA SERUPA SUDAH TERDATA DI SISTEM! (Anti-Duplikasi Lapis 2)**\n\n"
        f"• **Judul Terdaftar:** {first_dup.get('judul', '-')}\n"
        f"• **Media:** {first_dup.get('media', '-')} | **UPT:** {first_dup.get('nama_upt', '-')}\n"
        f"• **Status:** {first_dup.get('status_verifikasi', '-')}\n\n"
        f"💡 *Catatan Smart Upsert (Lapis 3): Anda tetap bisa menyimpan data di bawah sebagai **koreksi/perkembangan baru** atau **sumber tambahan** tanpa membuat duplikat sampah.*"
    )

urgency_auto = str(result.get("urgensi", "Rendah"))
if urgency_auto in {"Tinggi", "Kritis"}:
    st.error(
        f"⚠️ **PERINGATAN AWAL** — sistem mendeteksi urgensi **{urgency_auto}**. "
        "Berita akan langsung tampil pada Warning News dengan label Belum Ditelaah setelah disimpan."
    )

# --- 5. TAHAP 2: FORM DETAIL & SMART UPSERT ---
section_header(
    "Data yang Akan Disimpan",
    "Analis dapat mengoreksi klasifikasi. Operator Akuisisi hanya mengelola data sumber dan tidak menetapkan analisis final.",
)

with st.form("save_news_form", clear_on_submit=False):
    a, b = st.columns(2)
    with a:
        title = st.text_input("Judul", value=str(result.get("judul", "")))
        media = st.text_input("Media/Akun", value=str(result.get("media", "")))
        platform_options = ["Portal Berita", "Instagram", "Facebook", "TikTok", "YouTube", "Google News", "Lainnya"]
        platform_value = str(result.get("platform", "Portal Berita"))
        platform = st.selectbox(
            "Platform",
            platform_options,
            index=platform_options.index(platform_value) if platform_value in platform_options else 0,
        )
        published = st.text_input("Tanggal publikasi", value=str(result.get("tanggal_publikasi", "")))
        location = st.text_input("Lokasi kejadian", value=str(result.get("lokasi", "")))
    
    with b:
        if can_analyze:
            categories = [
                "Keamanan dan Ketertiban", "Pelarian", "Peredaran Narkotika", "Barang Terlarang",
                "Pungutan Liar", "Kekerasan", "Kesehatan", "Kematian", "Kebakaran dan Bencana",
                "Pelayanan", "Hak Asasi Manusia", "Kunjungan", "Pembinaan", "Overkapasitas",
                "Sarana dan Prasarana", "Integritas Petugas", "Prestasi dan Inovasi", "Kerja Sama", "Lainnya",
            ]
            category_value = str(result.get("kategori", "Lainnya"))
            category = st.selectbox(
                "Kategori",
                categories,
                index=categories.index(category_value) if category_value in categories else len(categories) - 1,
            )
            subcategory = st.text_input("Subkategori", value=str(result.get("subkategori", "Umum")))
            sentiment_options = ["Positif", "Netral", "Negatif", "Campuran"]
            sentiment_value = str(result.get("sentimen", "Netral"))
            sentiment = st.selectbox(
                "Sentimen",
                sentiment_options,
                index=sentiment_options.index(sentiment_value) if sentiment_value in sentiment_options else 1,
            )
            urgency_options = ["Rendah", "Sedang", "Tinggi", "Kritis"]
            urgency_value = str(result.get("urgensi", "Rendah"))
            urgency = st.selectbox(
                "Urgensi",
                urgency_options,
                index=urgency_options.index(urgency_value) if urgency_value in urgency_options else 0,
            )
            impact = st.selectbox("Dampak", ["UPT", "Kanwil", "Nasional", "Lintas Instansi", "Perhatian Publik Luas"])
        else:
            category = str(result.get("kategori", "Lainnya"))
            subcategory = str(result.get("subkategori", "Umum"))
            sentiment = str(result.get("sentimen", "Netral"))
            urgency = str(result.get("urgensi", "Rendah"))
            impact = str(result.get("dampak", "UPT"))
            st.info(
                "Klasifikasi otomatis (tidak dapat diubah oleh peran Anda):\n\n"
                f"**Kategori:** {category}  \n**Sentimen:** {sentiment}  \n**Urgensi:** {urgency}"
            )

    summary_default = str(result.get("ringkasan", ""))
    if can_analyze:
        summary = st.text_area("Ringkasan analisis (Wajib untuk Isu Negatif)", value=summary_default, height=150)
        keywords = st.text_input("Kata kunci", value=", ".join(result.get("kata_kunci", []) or []))
    else:
        st.text_area("Ringkasan otomatis", value=summary_default, height=130, disabled=True)
        summary = summary_default
        keywords = ", ".join(result.get("kata_kunci", []) or [])

    notes = st.text_area("Catatan penginput / Koreksi atas Bot", height=80)
    files = st.file_uploader(
        "Bukti pendukung (opsional)",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
        help="Maksimal 5 file, masing-masing maksimal 10 MB.",
    )
    
    # Pilihan penanganan duplikasi (Smart Upsert Logic)
    default_dup_idx = 1 if (existing_dups is not None and not existing_dups.empty) else 0
    duplicate_action = st.radio(
        "Tindakan jika terdeteksi berita serupa (Smart Upsert Lapis 3):",
        ["Batalkan jika duplikat", "Simpan sebagai sumber tambahan", "Simpan sebagai perkembangan baru"],
        index=default_dup_idx,
        horizontal=True,
    )
    
    submitted = st.form_submit_button("💾 SIMPAN DAN KIRIM KE PUSAT TELAAH", type="primary", use_container_width=True)

if submitted:
    parsed = pd.to_datetime(published, errors="coerce") if published else None
    published_value = None if parsed is None or pd.isna(parsed) else parsed.isoformat()
    visible_news = scope_news(fetch_news_df(), user, all_upt)
    duplicates = find_duplicate_news(
        result["link"], title, media, result["nama_upt"], published_value or "", visible_news
    )
    
    # Jika memilih "Batalkan jika duplikat" dan memang ada duplikat
    if not duplicates.empty and duplicate_action == "Batalkan jika duplikat":
        st.error("❌ Penyimpanan dibatalkan karena ditemukan berita yang sama atau sangat mirip.")
        st.dataframe(
            duplicates[[c for c in ["judul", "nama_upt", "media", "status_verifikasi", "duplicate_reason", "similarity", "link"] if c in duplicates.columns]],
            use_container_width=True,
            hide_index=True,
            column_config={"link": st.column_config.LinkColumn("Link", display_text="Buka")},
        )
        st.stop()

    if len(files or []) > 5:
        st.error("❌ Maksimal 5 lampiran per berita.")
        st.stop()

    payload = {
        "nama_upt": result["nama_upt"],
        "nama_petugas": result["nama_petugas"],
        "created_by": user.username,
        "link": result["link"],
        "judul": clean_text(title),
        "media": clean_text(media),
        "platform": platform,
        "tanggal_publikasi": published_value,
        "kategori": category,
        "subkategori": clean_text(subcategory) or "Umum",
        "sentimen": sentiment,
        "urgensi": urgency,
        "dampak": impact,
        "ringkasan": clean_text(summary),
        "caption_manual": result.get("caption_manual", ""),
        "status_baca": result.get("status_baca", ""),
        "catatan": clean_text(notes),
        "status_verifikasi": "Belum Ditelaah",
        "kata_kunci": [x.strip() for x in str(keywords).split(",") if x.strip()],
        "lokasi": clean_text(location),
        "tingkat_perhatian": result.get("tingkat_perhatian", "Rendah"),
        "ai_provider": result.get("ai_provider", "rules"),
        "ai_confidence": result.get("ai_confidence"),
        "source_type": "manual",
        "duplicate_relation": (
            "sumber_tambahan" if duplicate_action == "Simpan sebagai sumber tambahan"
            else "perkembangan_baru" if duplicate_action == "Simpan sebagai perkembangan baru"
            else ""
        ),
        "duplicate_of": str(duplicates.iloc[0].get("id") or "") if not duplicates.empty else None,
    }
    
    ok, message, news_id = save_news(payload, user.username, user.role)
    if not ok:
        st.error(f"❌ {message}")
        st.stop()

    attachment_errors: list[str] = []
    for file in files or []:
        try:
            upload_attachment(
                news_id,
                file.name,
                file.getvalue(),
                user.username,
                user.role,
                description="Bukti saat input berita",
            )
        except Exception as exc:
            attachment_errors.append(f"{file.name}: {exc}")

    st.success(f"✅ {message}")
    if urgency in {"Tinggi", "Kritis"}:
        st.warning("⚠️ Peringatan Awal telah diaktifkan dan masuk antrean prioritas Pusat Telaah.")
    if attachment_errors:
        st.warning("Sebagian lampiran gagal diunggah: " + "; ".join(attachment_errors))
        
    st.session_state.analysis_result = None
    st.session_state.duplicate_info = None
    st.rerun()

# --- 6. PREVIEW BERITA TERAKHIR ---
with st.expander("📊 Lihat 5 Berita Terakhir di Database", expanded=False):
    df_recent = scope_news(fetch_news_df(), user, all_upt)
    if not df_recent.empty:
        cols_to_show = [c for c in ["tanggal_publikasi", "media", "judul", "sentimen", "nama_upt", "status_verifikasi"] if c in df_recent.columns]
        st.dataframe(df_recent.tail(5)[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data berita yang tersedia.")