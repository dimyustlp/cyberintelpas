from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import kpi_grid, page_header, section_header
from services.access_control import require_permission, scope_news
from services.database import fetch_all, fetch_news_df, fetch_upt_df, table_exists
from services.news_service import change_news_status, normalize_status, update_news, warning_state

user = require_permission("review_news")
page_header(
    "Pusat Telaah Pemberitaan",
    "Validasi internal pusat untuk memastikan klasifikasi, urgensi, sentimen, UPT, dan sumber berita dapat dipertanggungjawabkan.",
    "Central Editorial Review",
)

upt_df = fetch_upt_df()
news = scope_news(fetch_news_df(), user, upt_df)
if news.empty:
    st.info("Belum ada berita yang perlu ditelaah.")
    st.stop()

news = news.copy()
news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
news["warning_state"] = news.apply(warning_state, axis=1)

counts = news["status_verifikasi"].value_counts()
preliminary = int((news["warning_state"] == "preliminary").sum())
verified_warning = int((news["warning_state"] == "verified").sum())
kpi_grid([
    {"icon": "⚠️", "title": "Peringatan Awal", "value": preliminary, "foot": "Tinggi/kritis belum ditelaah", "accent": "#9B1C1C"},
    {"icon": "🕓", "title": "Belum Ditelaah", "value": int(counts.get("Belum Ditelaah", 0)), "foot": "Menunggu validasi", "accent": "#808080"},
    {"icon": "↩️", "title": "Perlu Koreksi", "value": int(counts.get("Perlu Koreksi", 0)), "foot": "Dikembalikan ke penginput", "accent": "#D97706"},
    {"icon": "✅", "title": "Terverifikasi", "value": int(counts.get("Terverifikasi", 0)), "foot": f"{verified_warning} warning resmi", "accent": "#16845B"},
    {"icon": "⛔", "title": "Tidak Valid", "value": int(counts.get("Tidak Valid", 0)), "foot": "Tidak digunakan", "accent": "#6B7280"},
])

with st.expander("Alur telaah yang berlaku", expanded=False):
    st.markdown(
        """
        **Belum Ditelaah → Terverifikasi / Perlu Koreksi / Tidak Valid → Diarsipkan.**

        Berita berurgensi **Tinggi/Kritis** langsung tampil sebagai **Peringatan Awal** sebelum telaah.
        Setelah diverifikasi, statusnya berubah menjadi **Peringatan Terverifikasi** dan memengaruhi marker resmi peta.
        """
    )

view_options = [
    "Prioritas Tinggi/Kritis",
    "Belum Ditelaah",
    "Perlu Koreksi",
    "Terverifikasi",
    "Tidak Valid",
    "Diarsipkan",
    "Semua Berita",
]
with st.container(border=True):
    c1, c2, c3 = st.columns([1.2, 1.8, 1])
    selected_view = c1.selectbox("Antrean", view_options)
    query = c2.text_input("Cari judul, UPT, media, atau kata kunci")
    source_filter = c3.multiselect("Sumber", sorted(news["source_type"].dropna().astype(str).unique().tolist()))

filtered = news.copy()
if selected_view == "Prioritas Tinggi/Kritis":
    filtered = filtered[
        filtered["urgensi"].astype(str).isin(["Tinggi", "Kritis"])
        & ~filtered["status_verifikasi"].isin(["Tidak Valid", "Diarsipkan"])
    ]
elif selected_view != "Semua Berita":
    filtered = filtered[filtered["status_verifikasi"] == selected_view]
if source_filter:
    filtered = filtered[filtered["source_type"].isin(source_filter)]
if query:
    search_cols = [c for c in ["judul", "nama_upt", "media", "kategori", "ringkasan", "link"] if c in filtered.columns]
    mask = filtered[search_cols].astype(str).apply(
        lambda col: col.str.contains(query, case=False, na=False)
    ).any(axis=1)
    filtered = filtered[mask]

# Prioritaskan kritis, tinggi, lalu data terbaru.
urgency_rank = {"Kritis": 0, "Tinggi": 1, "Sedang": 2, "Rendah": 3}
filtered = filtered.assign(
    _urgency_rank=filtered["urgensi"].map(urgency_rank).fillna(4),
    _created_sort=pd.to_datetime(filtered["created_at"], errors="coerce", utc=True),
).sort_values(["_urgency_rank", "_created_sort"], ascending=[True, False])

section_header("Antrean Berita", f"{len(filtered)} berita sesuai filter.")
if filtered.empty:
    st.success("Tidak ada berita pada antrean ini.")
    st.stop()

options = filtered["id"].astype(str).tolist()
lookup = filtered.set_index(filtered["id"].astype(str), drop=False)

def _format_option(news_id: str) -> str:
    row = lookup.loc[news_id]
    warning = "⚠️ " if row.get("warning_state") == "preliminary" else "🚨 " if row.get("warning_state") == "verified" else ""
    return f"{warning}{row.get('urgensi', '-')} | {str(row.get('judul') or 'Tanpa judul')[:95]} | {row.get('nama_upt', '-')}"

selected_id = st.selectbox("Pilih berita untuk ditelaah", options, format_func=_format_option)
row = lookup.loc[selected_id]
news_id = str(row.get("id") or "")
current_status = normalize_status(str(row.get("status_verifikasi") or "Belum Ditelaah"))

left, right = st.columns([1.65, 1])
with left:
    st.subheader(str(row.get("judul") or "Tanpa judul"))
    st.markdown(f"**UPT:** {row.get('nama_upt', '-')}  ")
    st.markdown(f"**Media/Platform:** {row.get('media', '-')} / {row.get('platform', '-')}  ")
    st.markdown(f"**Kategori:** {row.get('kategori', '-')} — {row.get('subkategori', '-')}  ")
    st.markdown(f"**Sentimen/Urgensi:** {row.get('sentimen', '-')} / **{row.get('urgensi', '-')}**  ")
    st.markdown(f"**Ringkasan:** {row.get('ringkasan', '-')}")
with right:
    if row.get("warning_state") == "preliminary":
        st.error("⚠️ PERINGATAN AWAL\n\nBelum ditelaah analis")
    elif row.get("warning_state") == "verified":
        st.error("🚨 PERINGATAN TERVERIFIKASI")
    else:
        st.info(f"Status: **{current_status}**")
    st.caption(f"Penginput: {row.get('nama_petugas') or row.get('created_by') or '-'}")
    st.caption(f"Sumber input: {row.get('source_type', 'manual')}")
    if row.get("link"):
        st.link_button("Buka sumber asli", str(row.get("link")), use_container_width=True)

section_header("Koreksi Analisis", "Simpan perubahan sebelum menetapkan hasil telaah.")
with st.form(f"analysis_edit_{news_id}"):
    e1, e2 = st.columns(2)
    title = e1.text_input("Judul", value=str(row.get("judul") or ""))
    media = e2.text_input("Media/Akun", value=str(row.get("media") or ""))
    category = e1.text_input("Kategori", value=str(row.get("kategori") or ""))
    subcategory = e2.text_input("Subkategori", value=str(row.get("subkategori") or ""))
    sentiment_options = ["Positif", "Netral", "Negatif", "Campuran"]
    current_sentiment = str(row.get("sentimen") or "Netral")
    sentiment = e1.selectbox(
        "Sentimen",
        sentiment_options,
        index=sentiment_options.index(current_sentiment) if current_sentiment in sentiment_options else 1,
    )
    urgency_options = ["Rendah", "Sedang", "Tinggi", "Kritis"]
    current_urgency = str(row.get("urgensi") or "Rendah")
    urgency = e2.selectbox(
        "Urgensi",
        urgency_options,
        index=urgency_options.index(current_urgency) if current_urgency in urgency_options else 0,
    )
    impact_options = ["UPT", "Kanwil", "Nasional", "Lintas Instansi", "Perhatian Publik Luas"]
    current_impact = str(row.get("dampak") or "UPT")
    impact = e1.selectbox(
        "Dampak",
        impact_options,
        index=impact_options.index(current_impact) if current_impact in impact_options else 0,
    )
    location = e2.text_input("Lokasi kejadian", value=str(row.get("lokasi") or ""))
    summary = st.text_area("Ringkasan", value=str(row.get("ringkasan") or ""), height=140)
    analyst_note = st.text_area("Catatan analisis internal", value=str(row.get("catatan") or ""), height=90)
    save_edit = st.form_submit_button("SIMPAN KOREKSI ANALISIS", type="primary", use_container_width=True)

if save_edit:
    try:
        update_news(
            news_id,
            {
                "judul": title,
                "media": media,
                "kategori": category,
                "subkategori": subcategory,
                "sentimen": sentiment,
                "urgensi": urgency,
                "dampak": impact,
                "lokasi": location,
                "ringkasan": summary,
                "catatan": analyst_note,
            },
            user.username,
            user.role,
        )
        st.success("Analisis berita berhasil diperbarui.")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

section_header("Keputusan Telaah", "Pilih satu keputusan. Tidak ada lagi tahapan 'Mulai Pemeriksaan'.")
review_note = st.text_area(
    "Catatan keputusan",
    value=str(row.get("review_note") or ""),
    key=f"review_note_{news_id}",
    placeholder="Tuliskan dasar verifikasi atau koreksi yang diperlukan.",
)
reason = st.text_input(
    "Alasan koreksi/tidak valid",
    value=str(row.get("rejection_reason") or ""),
    key=f"review_reason_{news_id}",
)

buttons: list[tuple[str, str, str]] = []
if current_status in {"Belum Ditelaah", "Perlu Koreksi"}:
    buttons = [
        ("✅ Verifikasi", "Terverifikasi", "primary"),
        ("↩️ Perlu Koreksi", "Perlu Koreksi", "secondary"),
        ("⛔ Tidak Valid", "Tidak Valid", "secondary"),
        ("🗄️ Arsipkan", "Diarsipkan", "secondary"),
    ]
elif current_status == "Terverifikasi":
    buttons = [
        ("↩️ Buka untuk Koreksi", "Perlu Koreksi", "secondary"),
        ("⛔ Nyatakan Tidak Valid", "Tidak Valid", "secondary"),
        ("🗄️ Arsipkan", "Diarsipkan", "secondary"),
    ]
elif current_status == "Tidak Valid":
    buttons = [
        ("♻️ Kembalikan ke Belum Ditelaah", "Belum Ditelaah", "primary"),
        ("🗄️ Arsipkan", "Diarsipkan", "secondary"),
    ]
elif current_status == "Diarsipkan":
    buttons = [("♻️ Pulihkan ke Belum Ditelaah", "Belum Ditelaah", "primary")]

if buttons:
    cols = st.columns(len(buttons))
    for col, (label, target, kind) in zip(cols, buttons):
        if col.button(label, type=kind, use_container_width=True, key=f"review_{target}_{news_id}"):
            if target in {"Perlu Koreksi", "Tidak Valid"} and not (reason.strip() or review_note.strip()):
                st.error("Catatan/alasan wajib diisi untuk keputusan ini.")
                st.stop()
            try:
                change_news_status(
                    news_id,
                    target,
                    review_note,
                    user.username,
                    user.role,
                    reason,
                )
                st.success(f"Status berita berubah menjadi {target}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

if table_exists("berita_status_history") and news_id:
    with st.expander("Riwayat Telaah dan Status"):
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
            st.caption("Belum ada riwayat perubahan status.")
        else:
            st.dataframe(
                history[["created_at", "status_from", "status_to", "changed_by", "note", "reason"]],
                width="stretch",
                hide_index=True,
            )
