from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from components.layout import kpi_grid, page_header, section_header
from services.access_control import require_permission, scope_news
from services.analytics_service import dashboard_metrics
from services.audit_service import log_action
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.export_service import excel_bytes
from services.news_service import normalize_status, warning_state
# --- IMPOR MESIN CETAK PDF DITJENPAS & TELEGRAM ---
from services.pdf_report_service import create_daily_pdf_bytes
from services.telegram_service import send_telegram_document

# --- 1. VERIFIKASI HAK AKSES ---
user = require_permission("export_reports")
page_header(
    "Laporan Eksekutif & Operasional",
    "Siapkan rekap harian taktis, mingguan eksekutif, bulanan, atau bahan pimpinan dengan status verifikasi dan cetakan PDF resmi.",
    "Reporting Center",
)

# --- 2. AMBIL DATA & NORMALIZE STATUS ---
all_upt = fetch_upt_df()
news = scope_news(fetch_news_df(), user, all_upt)
if not news.empty:
    news = news.copy()
    news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
    news["warning_state"] = news.apply(warning_state, axis=1)
    if user.role == "executive_decision_maker":
        news = news[news["status_verifikasi"].eq("Terverifikasi") | news["warning_state"].eq("preliminary")].copy()

if news.empty:
    st.info("💡 Belum ada data untuk dilaporkan.")
    st.stop()

created = pd.to_datetime(news["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Jakarta")
news = news.assign(_date=created.dt.date)
min_date = news["_date"].dropna().min() or date.today()
max_date = news["_date"].dropna().max() or date.today()

# --- 3. PANEL FILTER DATA GLOBAL ---
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

# Terapkan filter
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

columns = [
    "created_at", "tanggal_publikasi", "nama_upt", "judul", "media", "platform", "kategori",
    "subkategori", "sentimen", "urgensi", "dampak", "status_verifikasi", "source_type",
    "reviewed_by", "verified_by", "link", "ringkasan",
]
columns = [c for c in columns if c in filtered.columns]

# --- 4. STRUKTUR 2 TAB: HARIAN (TAKTIS) & MINGGUAN (EKSEKUTIF RAPIM) ---
tab_harian, tab_mingguan = st.tabs([
    "📄 Laporan Harian (Taktis Operasional)", 
    "📊 Laporan Mingguan (Eksekutif Rapim)"
])

# =====================================================================
# TAB 1: LAPORAN HARIAN (TAKTIS OPERASIONAL)
# =====================================================================
with tab_harian:
    m = dashboard_metrics(filtered) if not filtered.empty else dashboard_metrics(news.iloc[0:0])
    kpi_grid([
        {"icon": "📰", "title": "Total", "value": m.total, "foot": "Dalam filter laporan", "accent": "#1769AA"},
        {"icon": "🔴", "title": "Negatif", "value": m.negative, "foot": "Memerlukan telaah", "accent": "#C53A43"},
        {"icon": "🚨", "title": "Tinggi/Kritis", "value": m.high, "foot": "Prioritas", "accent": "#650000"},
        {"icon": "🏢", "title": "UPT Aktif", "value": m.active_upt, "foot": "Kontributor berita", "accent": "#16845B"},
        {"icon": "📊", "title": "Positif", "value": m.positive, "foot": "Pemberitaan positif", "accent": "#16845B"},
        {"icon": "➖", "title": "Netral", "value": m.neutral, "foot": "Pemberitaan netral", "accent": "#D4A72C"},
    ])

    section_header("Data Laporan Harian", f"{len(filtered)} berita taktis sesuai filter.")
    st.dataframe(
        filtered[columns],
        width="stretch",
        height=400,
        hide_index=True,
        column_config={"link": st.column_config.LinkColumn("Link", display_text="Buka")},
    )

    st.markdown("---")

    # Pengaturan Kop Periode PDF Harian
    with st.expander("⚙️ Pengaturan Kop Laporan PDF Resmi Ditjenpas", expanded=False):
        default_periode_label = (
            f"{date_range[0].strftime('%d %B %Y')} - {date_range[1].strftime('%d %B %Y')}"
            if isinstance(date_range, (tuple, list)) and len(date_range) == 2
            else date.today().strftime('%d %B %Y')
        )
        periode_label = st.text_input(
            "Label Periode pada Halaman Judul PDF Harian",
            value=f"{default_periode_label} (07.00 WIB - Selesai)",
            help="Label ini akan dicetak tepat di bawah judul Laporan Harian Pemasyarakatan pada berkas PDF.",
        )

    # Tombol Ekspor Harian (3 Format: PDF, Excel, CSV)
    c1, c2, c3 = st.columns(3)

    # A. EXPORT PDF RESMI DITJENPAS (+ QR CODE)
    with c1:
        if not filtered.empty:
            with st.spinner("Merender PDF Resmi Ditjenpas & QR Code Kliping..."):
                pdf_bytes = create_daily_pdf_bytes(filtered, periode_label)

            st.download_button(
                label="📄 Unduh Laporan PDF Resmi",
                data=pdf_bytes,
                file_name=f"Laporan_Harian_CyberIntelpas_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                on_click=log_action,
                args=("export", "laporan", "pdf", user.username, user.role, {"rows": len(filtered), "format": "pdf"}),
            )
        else:
            st.button("📄 Unduh Laporan PDF Resmi", disabled=True, use_container_width=True)

    # B. EXPORT EXCEL
    with c2:
        st.download_button(
            label="📊 Unduh Laporan Excel",
            data=excel_bytes(filtered[columns], "Laporan Berita"),
            file_name=f"laporan_simberpas_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            on_click=log_action,
            args=("export", "laporan", "berita", user.username, user.role, {"rows": len(filtered), "format": "xlsx"}),
        )

    # C. EXPORT CSV
    with c3:
        st.download_button(
            label="📋 Unduh Data CSV",
            data=filtered[columns].to_csv(index=False).encode("utf-8-sig"),
            file_name=f"laporan_simberpas_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
            on_click=log_action,
            args=("export", "laporan", "berita", user.username, user.role, {"rows": len(filtered), "format": "csv"}),
        )

    # D. KURIR TELEGRAM LANGSUNG
    with st.expander("📲 Distribusi Laporan Harian ke Telegram Pimpinan", expanded=False):
        st.write("Kirimkan berkas PDF Laporan Harian yang sedang aktif langsung ke Grup Telegram Monitoring.")
        if st.button("🚀 Kirim PDF Laporan Harian Sekarang ke Telegram", type="primary", use_container_width=True):
            if not filtered.empty:
                with st.spinner("Mengirim dokumen PDF resmi ke Telegram..."):
                    pdf_bytes_send = create_daily_pdf_bytes(filtered, periode_label)
                    nama_file_tg = f"Laporan_Harian_CyberIntelpas_{date.today().isoformat()}.pdf"
                    caption_tg = (
                        f"🔴 <b>[LAPORAN HARIAN MONITORING PEMBERITAAN]</b>\n"
                        f"📅 <b>Periode:</b> {periode_label}\n"
                        f"🏛️ <b>Instansi:</b> Ditjen Pemasyarakatan\n\n"
                        f"📊 <b>STATISTIK:</b>\n"
                        f"🔹 Total: <b>{len(filtered)} Berita</b> | "
                        f"✅ Positif: <b>{len(filtered[filtered['sentimen']=='Positif'])}</b> | "
                        f"🔻 Negatif: <b>{len(filtered[filtered['sentimen']=='Negatif'])}</b>\n\n"
                        f"<i>Dikirim oleh Command Center Cyber-Intelpas</i>"
                    )
                    berhasil = send_telegram_document(pdf_bytes_send, nama_file_tg, caption_tg)
                if berhasil:
                    st.success("✅ Laporan PDF resmi berhasil dikirim ke Grup Telegram Pimpinan!")
                else:
                    st.error("❌ Gagal mengirim ke Telegram. Periksa koneksi atau token di .streamlit/secrets.toml.")
            else:
                st.warning("Tidak ada data laporan untuk dikirim.")

# =====================================================================
# TAB 2: LAPORAN MINGGUAN (EKSEKUTIF RAPIM - LANSKAP 16:9)
# =====================================================================
with tab_mingguan:
    section_header(
        "Laporan Mingguan Eksekutif Ditjen Pemasyarakatan", 
        "Didesain berorientasi Lanskap (16:9) & analitis untuk bahan presentasi Rapat Pimpinan (Rapim)."
    )

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        minggu_label = st.text_input(
            "Periode Laporan Mingguan", 
            value=f"Periode Mingguan ({date_range[0].strftime('%d/%m/%Y')} - {date_range[1].strftime('%d/%m/%Y')})",
            help="Label periode ini akan tercantum pada slide cover presentasi mingguan pimpinan."
        )
    with col_w2:
        opsi_fokus = st.multiselect(
            "Fokus Isu Strategis Mingguan",
            ["Peredaran Narkotika", "Keamanan & Ketertiban", "Overkapasitas", "Integritas Petugas", "Prestasi & Inovasi"],
            default=["Peredaran Narkotika", "Keamanan & Ketertiban"]
        )

    st.markdown("### 📈 Ringkasan Strategis Mingguan")
    if not filtered.empty:
        total_m = len(filtered)
        pos_m = len(filtered[filtered["sentimen"] == "Positif"])
        neg_m = len(filtered[filtered["sentimen"] == "Negatif"])

        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        c_kpi1.metric("Total Berita Mingguan", f"{total_m} Berita", delta="Data Terpilih")
        c_kpi2.metric("Dominasi Positif", f"{pos_m} Berita", delta=f"{round((pos_m/total_m*100), 1)}% dari total" if total_m>0 else "0%")
        c_kpi3.metric("Isu Negatif Prioritas", f"{neg_m} Kasus", delta="Memerlukan mitigasi", delta_color="inverse")

        # RISK HEATMAP: Peta Wilayah/UPT Rawan Isu Negatif
        st.markdown("#### 📍 Risk Heatmap — Wilayah & UPT Berisiko Tinggi")
        df_neg_week = filtered[filtered["sentimen"] == "Negatif"]
        if not df_neg_week.empty:
            cols_neg = [c for c in ["tanggal_publikasi", "nama_upt", "judul", "media", "urgensi"] if c in df_neg_week.columns]
            st.dataframe(
                df_neg_week[cols_neg],
                use_container_width=True,
                height=250,
                hide_index=True
            )
        else:
            st.success("🟢 Nihil isu negatif berisiko tinggi pada periode minggu ini.")

        st.markdown("---")

        # Tombol Ekspor Laporan Mingguan
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            st.download_button(
                label="📽️ Unduh Slide Presentasi Mingguan (PDF Lanskap)",
                data=b"",  # Siap dihubungkan dengan template WeasyPrint A4 landscape Anda
                file_name=f"Laporan_Mingguan_Eksekutif_{date.today().isoformat()}.pdf",
                use_container_width=True,
                disabled=True,
                help="Template PDF Lanskap 16:9 siap dilampirkan untuk presentasi Rapat Pimpinan."
            )
        with c_exp2:
            st.download_button(
                label="📑 Unduh Rekap Data Mingguan (Excel)",
                data=excel_bytes(filtered[columns], "Rekap Mingguan"),
                file_name=f"Rekap_Mingguan_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                on_click=log_action,
                args=("export", "laporan", "mingguan", user.username, user.role, {"rows": len(filtered), "format": "xlsx"}),
            )
    else:
        st.info("💡 Belum ada data pada rentang minggu terpilih.")