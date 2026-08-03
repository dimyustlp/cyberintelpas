from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from components.layout import page_header, section_header
from services.access_control import require_permission, scope_news, scope_upt
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.geo_service import MARKER_META, build_upt_status, marker_css, marker_icon_html, popup_html

user = require_permission("view_map")
page_header(
    "Peta Indonesia",
    "Peta situasi seluruh UPT berdasarkan hasil telaah, sentimen terverifikasi, dan peringatan awal urgensi tinggi/kritis.",
    "Geospatial Intelligence",
)

all_upt = fetch_upt_df()
upt = scope_upt(all_upt, user)
news = scope_news(fetch_news_df(), user, all_upt)
if upt.empty:
    st.warning("Data UPT pada cakupan akun Anda belum tersedia.")
    st.stop()

status_df = build_upt_status(upt, news)
status_df = status_df.dropna(subset=["latitude", "longitude"]).copy()
if status_df.empty:
    st.warning("Belum ada UPT yang mempunyai koordinat atau titik wilayah sementara.")
    st.stop()

with st.container(border=True):
    f1, f2, f3, f4 = st.columns(4)
    provinces = sorted([x for x in status_df["provinsi"].dropna().astype(str).unique() if x])
    province = f1.selectbox("Provinsi", ["Semua Provinsi"] + provinces)
    filtered = status_df if province == "Semua Provinsi" else status_df[status_df["provinsi"] == province]

    kanwils = sorted([x for x in filtered["kanwil"].dropna().astype(str).unique() if x])
    kanwil = f2.selectbox("Kanwil", ["Semua Kanwil"] + kanwils)
    if kanwil != "Semua Kanwil":
        filtered = filtered[filtered["kanwil"] == kanwil]

    marker_options = {
        "Merah tua — urgensi tinggi/kritis": "critical",
        "Merah — negatif terverifikasi": "negative",
        "Abu-abu — belum ditelaah/koreksi": "draft",
        "Krem/beige — netral": "neutral",
        "Hijau — positif": "positive",
        "Biru — belum ada berita": "none",
    }
    marker_filter_labels = f3.multiselect("Status marker", list(marker_options))
    if marker_filter_labels:
        filtered = filtered[filtered["marker_status"].isin([marker_options[x] for x in marker_filter_labels])]

    quality_values = sorted([x for x in filtered["coordinate_quality"].dropna().astype(str).unique() if x])
    quality_filter = f4.multiselect("Kualitas koordinat", quality_values)
    if quality_filter:
        filtered = filtered[filtered["coordinate_quality"].isin(quality_filter)]

    r2c1, r2c2, r2c3 = st.columns([2, 1, 1])
    search_upt = r2c1.text_input("Cari UPT", placeholder="Contoh: Sukamiskin, Cipinang, Nusakambangan")
    if search_upt:
        filtered = filtered[filtered["nama_upt"].astype(str).str.contains(search_upt, case=False, na=False)]
    only_news = r2c2.checkbox("Hanya UPT memiliki berita", value=False)
    if only_news:
        filtered = filtered[filtered["jumlah_berita"] > 0]
    disable_animation = r2c3.checkbox("Nonaktifkan animasi", value=False)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("UPT tampil", int(len(filtered)))
k2.metric("Merah tua", int((filtered["marker_status"] == "critical").sum()))
k3.metric("Merah", int((filtered["marker_status"] == "negative").sum()))
k4.metric("Abu-abu", int((filtered["marker_status"] == "draft").sum()))
k5.metric("Terverifikasi", int(filtered["jumlah_terverifikasi"].sum()))
k6.metric("Peringatan awal", int(filtered["jumlah_peringatan_awal"].sum()))

with st.expander("Legenda marker", expanded=True):
    legend_cols = st.columns(7)
    order = ["critical", "negative", "draft", "neutral", "positive", "none"]
    for col, key in zip(legend_cols[:6], order):
        meta = MARKER_META[key]
        col.markdown(
            f'<div style="display:flex;align-items:center;gap:7px;font-size:12px">'
            f'<span style="width:13px;height:13px;border-radius:50%;background:{meta["color"]};display:inline-block"></span>'
            f'<span>{meta["label"]}</span></div>',
            unsafe_allow_html=True,
        )
    legend_cols[6].markdown(
        '<div style="display:flex;align-items:center;gap:7px;font-size:12px">'
        '<span style="width:15px;height:15px;border-radius:50%;background:#650000;color:white;display:inline-block;text-align:center;font:bold 11px/15px Arial">!</span>'
        '<span>Peringatan awal tinggi/kritis</span></div>',
        unsafe_allow_html=True,
    )

if filtered.empty:
    st.info("Tidak ada UPT yang sesuai dengan filter.")
    st.stop()

center_lat = float(filtered["latitude"].mean())
center_lon = float(filtered["longitude"].mean())
zoom = 4.3 if province == "Semua Provinsi" else 7.0
if len(filtered) == 1:
    zoom = 12.0

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=zoom,
    tiles="CartoDB positron",
    control_scale=True,
    prefer_canvas=False,
)
m.get_root().header.add_child(folium.Element(marker_css(disable_animation)))
cluster = MarkerCluster(name="UPT reguler", disableClusteringAtZoom=11, showCoverageOnHover=False).add_to(m)
priority_layer = folium.FeatureGroup(name="UPT prioritas dan peringatan awal", show=True).add_to(m)

for _, row in filtered.iterrows():
    icon = folium.DivIcon(
        html=marker_icon_html(
            str(row["marker_color"]),
            "" if disable_animation else str(row["marker_animation"]),
            bool(row.get("preliminary_warning")),
        ),
        icon_size=(26, 26),
        icon_anchor=(13, 13),
        class_name="simberpas-div-icon",
    )
    tooltip = f"{row['nama_upt']} | {row['marker_label']}" + (" | Peringatan awal" if bool(row.get("preliminary_warning")) else "")
    target_layer = priority_layer if str(row.get("marker_status")) in {"critical", "negative"} or bool(row.get("preliminary_warning")) else cluster
    folium.Marker(
        location=[float(row["latitude"]), float(row["longitude"])],
        icon=icon,
        tooltip=tooltip,
        popup=folium.Popup(popup_html(row), max_width=390),
    ).add_to(target_layer)

folium.LayerControl(collapsed=True).add_to(m)
map_result = st_folium(
    m,
    width=None,
    height=610,
    use_container_width=True,
    returned_objects=["last_object_clicked_tooltip"],
    key="simberpas_map_v53",
)

clicked_tooltip = (map_result or {}).get("last_object_clicked_tooltip")
if clicked_tooltip:
    clicked_name = str(clicked_tooltip).split(" | ", 1)[0]
    selected = filtered[filtered["nama_upt"].astype(str) == clicked_name]
    if not selected.empty:
        row = selected.iloc[0]
        st.success(f"Dipilih: {row['nama_upt']} — {row['marker_label']}")
        related = news[news["nama_upt"].astype(str) == str(row["nama_upt"])].copy()
        if not related.empty:
            section_header("Berita UPT Terpilih", f"{len(related)} berita ditemukan.")
            columns = [c for c in ["created_at", "judul", "sentimen", "urgensi", "status_verifikasi", "link"] if c in related.columns]
            st.dataframe(
                related[columns],
                width="stretch",
                hide_index=True,
                column_config={"link": st.column_config.LinkColumn("Link", display_text="Buka")},
            )

section_header("Daftar UPT pada Peta", f"{len(filtered)} UPT ditampilkan.")
columns = [
    "nama_upt", "jenis_upt", "provinsi", "kanwil", "kabupaten_kota", "marker_label",
    "jumlah_berita", "jumlah_terverifikasi", "jumlah_draft", "jumlah_peringatan_awal", "coordinate_quality",
]
st.dataframe(filtered[columns], width="stretch", hide_index=True)
