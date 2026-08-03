from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import kpi_grid, page_header, section_header
from services.access_control import require_permission, scope_news
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.upt_mapping_service import apply_mapping, news_text, suggest_upt

user = require_permission("review_news")
page_header(
    "Pemetaan UPT",
    "Petakan berita otomatis yang belum mengenali UPT. Sistem memberikan kandidat lokal, sedangkan keputusan akhir tetap berada pada analis.",
    "UPT Mapping Center",
)

upt = fetch_upt_df()
news = scope_news(fetch_news_df(), user, upt)
if news.empty:
    st.info("Belum ada berita untuk dipetakan.")
    st.stop()

unmapped = news[news["nama_upt"].fillna("").astype(str).str.strip().isin(["", "Tidak diketahui", "None", "nan"])].copy()
auto_source = news[news.get("source_type", pd.Series("manual", index=news.index)).eq("google_sheet")]

kpi_grid([
    {"icon": "🧭", "title": "Belum Terpetakan", "value": len(unmapped), "foot": "Memerlukan keputusan analis", "accent": "#808080"},
    {"icon": "☁️", "title": "Berita Spreadsheet", "value": len(auto_source), "foot": "Sumber otomatis", "accent": "#1769AA"},
    {"icon": "✅", "title": "Sudah Terpetakan", "value": max(len(news) - len(unmapped), 0), "foot": "Memengaruhi peta UPT", "accent": "#16845B"},
])

if unmapped.empty:
    st.success("Semua berita sudah memiliki UPT.")
    st.stop()

with st.container(border=True):
    q = st.text_input("Cari judul, media, atau isi analisis")
    source_filter = st.multiselect("Sumber", ["google_sheet", "manual"], default=["google_sheet", "manual"])

filtered = unmapped.copy()
if source_filter:
    filtered = filtered[filtered["source_type"].isin(source_filter)]
if q:
    filtered = filtered[
        filtered[["judul", "media", "ringkasan", "raw_analysis"]].astype(str).apply(
            lambda col: col.str.contains(q, case=False, na=False)
        ).any(axis=1)
    ]

section_header("Antrean Pemetaan", f"{len(filtered)} berita belum memiliki UPT.")
for _, row in filtered.sort_values("created_at", ascending=False).head(50).iterrows():
    news_id = str(row["id"])
    title = str(row.get("judul") or "Tanpa judul")
    source = str(row.get("source_type") or "manual")
    with st.expander(f"{title[:115]} · {source}"):
        st.caption(f"Media: {row.get('media') or '-'} · Urgensi: {row.get('urgensi') or '-'}")
        st.write(str(row.get("ringkasan") or row.get("raw_analysis") or "-")[:1200])
        suggestions = suggest_upt(news_text(row), upt, limit=5)
        option_labels = [f"{item.nama_upt} — {item.confidence:.0%}" for item in suggestions]
        all_names = sorted(upt["nama_upt"].dropna().astype(str).unique().tolist())
        default_name = suggestions[0].nama_upt if suggestions else None
        c1, c2 = st.columns([1.4, 1])
        with c1:
            selected = st.selectbox(
                "Pilih UPT",
                [""] + all_names,
                index=(all_names.index(default_name) + 1) if default_name in all_names else 0,
                key=f"map_upt_{news_id}",
            )
        with c2:
            if suggestions:
                st.markdown("**Kandidat teratas**")
                for item in suggestions:
                    st.caption(f"{item.nama_upt} · {item.confidence:.0%} · {item.reason}")
            else:
                st.caption("Belum ada kandidat yang cukup kuat.")
        if st.button("Simpan Pemetaan", type="primary", disabled=not selected, key=f"save_map_{news_id}"):
            chosen = next((item for item in suggestions if item.nama_upt == selected), None)
            apply_mapping(
                news_id,
                selected,
                user.username,
                user.role,
                method="saran_lokal" if chosen else "manual",
                confidence=chosen.confidence if chosen else None,
            )
            st.success("UPT berhasil dipetakan.")
            st.cache_data.clear()
            st.rerun()
