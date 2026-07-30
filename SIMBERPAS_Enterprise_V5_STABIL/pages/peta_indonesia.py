from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from components.layout import info_panel, page_header, section_header
from services.access_control import scope_news, scope_upt
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.geo_service import attach_news_counts, enrich_province_coordinates, province_map_data

user = current_user()
page_header("Peta Indonesia", "Drill-down wilayah dari provinsi dan Kanwil hingga UPT serta berita terkait.", "Geospatial Intelligence")
upt = scope_upt(fetch_upt_df(), user)
news = scope_news(fetch_news_df(), user, fetch_upt_df())

if upt.empty:
    st.warning("Data UPT pada cakupan akun Anda belum tersedia.")
    st.stop()

upt = enrich_province_coordinates(upt)
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    provinces = sorted([x for x in upt["provinsi"].dropna().astype(str).unique() if x])
    province = c1.selectbox("Provinsi", ["Semua Provinsi"] + provinces)
    filtered_upt = upt if province == "Semua Provinsi" else upt[upt["provinsi"] == province]
    kanwils = sorted([x for x in filtered_upt["kanwil"].dropna().astype(str).unique() if x])
    kanwil = c2.selectbox("Kanwil", ["Semua Kanwil"] + kanwils)
    if kanwil != "Semua Kanwil": filtered_upt = filtered_upt[filtered_upt["kanwil"] == kanwil]
    upt_names = sorted(filtered_upt["nama_upt"].dropna().astype(str).tolist())
    selected_upt = c3.selectbox("UPT", ["Semua UPT"] + upt_names)
    if selected_upt != "Semua UPT": filtered_upt = filtered_upt[filtered_upt["nama_upt"] == selected_upt]

filtered_upt = attach_news_counts(filtered_upt, news)

exact = filtered_upt[filtered_upt["coordinate_quality"].astype(str).str.casefold().isin(["exact", "tepat", "gps", "lokasi upt"])]
if not exact.empty:
    map_df = exact.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    layer_id = "upt-layer"
    layer = pdk.Layer(
        "ScatterplotLayer",
        id=layer_id,
        data=map_df,
        get_position="[longitude, latitude]",
        get_radius="1500 + jumlah_berita * 280",
        get_fill_color="[197, 58, 67, 190]",
        pickable=True,
        stroked=True,
        get_line_color="[255,255,255,220]",
        line_width_min_pixels=1,
    )
    tooltip = {"html": "<b>{nama_upt}</b><br>{provinsi}<br>{jumlah_berita} berita", "style": {"backgroundColor": "#06182C", "color": "white"}}
else:
    map_df = province_map_data(filtered_upt, news).reset_index(drop=True)
    layer_id = "province-layer"
    layer = pdk.Layer(
        "ScatterplotLayer",
        id=layer_id,
        data=map_df,
        get_position="[longitude, latitude]",
        get_radius="18000 + jumlah_berita * 1800",
        get_fill_color="[23,105,170,185]",
        pickable=True,
        stroked=True,
        get_line_color="[212,167,44,230]",
        line_width_min_pixels=2,
    )
    tooltip = {"html": "<b>{provinsi}</b><br>{jumlah_upt} UPT<br>{jumlah_berita} berita", "style": {"backgroundColor": "#06182C", "color": "white"}}
    st.caption("Peta menggunakan pusat provinsi karena koordinat tepat UPT belum lengkap. Impor latitude/longitude melalui menu Pengaturan untuk menampilkan titik UPT yang sebenarnya.")

if map_df.empty:
    info_panel("Data Geospasial", "Lokasi belum dapat dipetakan", "Lengkapi kolom provinsi atau koordinat pada data UPT melalui menu Pengaturan.")
else:
    center_lat = float(map_df["latitude"].mean())
    center_lon = float(map_df["longitude"].mean())
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=4.1 if province == "Semua Provinsi" else 7, pitch=0),
        tooltip=tooltip,
        map_style=None,
    )
    event = st.pydeck_chart(deck, width="stretch", height=520, on_select="rerun", selection_mode="single-object", key="simberpas_map")
    indices = event.selection.indices.get(layer_id, []) if event and hasattr(event, "selection") else []
    if indices:
        selected = map_df.iloc[indices[0]]
        if layer_id == "upt-layer":
            st.success(f'Dipilih: {selected["nama_upt"]} — {selected["jumlah_berita"]} berita.')
        else:
            st.success(f'Dipilih: {selected["provinsi"]} — {selected["jumlah_upt"]} UPT dan {selected["jumlah_berita"]} berita.')

section_header("Daftar UPT pada Wilayah Terpilih", f"{len(filtered_upt)} UPT ditampilkan.")
st.dataframe(filtered_upt[["nama_upt", "jenis_upt", "provinsi", "kanwil", "jumlah_berita", "coordinate_quality"]], width="stretch", hide_index=True)

if selected_upt != "Semua UPT":
    related = news[news["nama_upt"] == selected_upt]
    section_header("Berita UPT Terpilih", f"{len(related)} berita terkait.")
    st.dataframe(related[["created_at", "judul", "sentimen", "urgensi", "link"]], width="stretch", hide_index=True, column_config={"link": st.column_config.LinkColumn("Link", display_text="Buka")})
