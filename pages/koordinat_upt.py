from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from services.audit_service import log_action
from components.layout import page_header, section_header
from services.access_control import require_permission
from services.auth_service import current_user
from services.coordinate_service import import_coordinates, normalize_coordinate_import, save_coordinate
from services.database import fetch_upt_df
from services.export_service import excel_bytes

admin = require_permission("manage_coordinates")
page_header(
    "Koordinat UPT",
    "Kelola master lokasi UPT, impor koordinat, verifikasi titik, dan perbaiki kualitas data peta.",
    "Geospatial Administration",
)

upt = fetch_upt_df().copy()
if upt.empty:
    st.warning("Master UPT belum tersedia.")
    st.stop()

has_coords = upt["latitude"].notna() & upt["longitude"].notna()
verified = upt["coordinate_quality"].astype(str).str.casefold().eq("terverifikasi")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total UPT", int(len(upt)))
k2.metric("Memiliki titik", int(has_coords.sum()))
k3.metric("Terverifikasi", int(verified.sum()))
k4.metric("Perlu pemeriksaan", int((~verified).sum()))

st.warning(
    "Koordinat dalam master awal adalah kandidat pusat kota/kabupaten atau pusat provinsi, bukan otomatis alamat gedung UPT. "
    "Gunakan tombol Verifikasi setelah titik diperiksa."
)

section_header("Impor Koordinat", "Mendukung CSV atau Excel dan tidak menghapus data lama.")
upload = st.file_uploader("Pilih file koordinat", type=["csv", "xlsx"])
if upload is not None:
    try:
        if upload.name.casefold().endswith(".csv"):
            imported = pd.read_csv(upload)
        else:
            imported = pd.read_excel(upload)
        normalized = normalize_coordinate_import(imported)
        st.dataframe(normalized.head(50), width="stretch", hide_index=True)
        if st.button("IMPOR / PERBARUI KE SUPABASE", type="primary"):
            count = import_coordinates(normalized, admin.username, admin.role)
            st.success(f"{count} baris berhasil diproses.")
            st.rerun()
    except Exception as exc:
        st.error(f"File tidak dapat diproses: {exc}")

export_cols = [
    "nama_upt", "jenis_upt", "kelas_upt", "subjenis_upt", "provinsi", "kanwil",
    "kabupaten_kota", "alamat", "latitude", "longitude", "coordinate_quality",
    "coordinate_source", "coordinate_score", "coordinate_verified_at", "coordinate_verified_by",
    "aktif", "catatan_verifikasi",
]
st.download_button(
    "Unduh master koordinat",
    data=excel_bytes(upt[[c for c in export_cols if c in upt.columns]], "Koordinat UPT"),
    file_name="SIMBERPAS_Master_Koordinat_UPT.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    on_click=log_action,
    args=("export", "upt", "coordinates", admin.username, admin.role, {"rows": len(upt), "format": "xlsx"}),
)

section_header("Periksa dan Edit Titik UPT", "Pilih satu UPT, perbaiki lokasi, lalu simpan atau verifikasi.")
filters = st.columns(3)
province_filter = filters[0].selectbox("Provinsi", ["Semua"] + sorted(upt["provinsi"].dropna().astype(str).unique().tolist()))
quality_filter = filters[1].selectbox("Kualitas", ["Semua"] + sorted(upt["coordinate_quality"].dropna().astype(str).unique().tolist()))
search = filters[2].text_input("Cari nama UPT")

filtered = upt.copy()
if province_filter != "Semua":
    filtered = filtered[filtered["provinsi"] == province_filter]
if quality_filter != "Semua":
    filtered = filtered[filtered["coordinate_quality"] == quality_filter]
if search:
    filtered = filtered[filtered["nama_upt"].astype(str).str.contains(search, case=False, na=False)]

st.dataframe(
    filtered[[
        "nama_upt", "provinsi", "kabupaten_kota", "latitude", "longitude",
        "coordinate_quality", "coordinate_verified_by", "data_source",
    ]],
    width="stretch",
    hide_index=True,
)

names = sorted(filtered["nama_upt"].astype(str).tolist())
if not names:
    st.info("Tidak ada UPT yang sesuai dengan filter.")
    st.stop()
selected_name = st.selectbox("Pilih UPT untuk diedit", names)
row = filtered[filtered["nama_upt"] == selected_name].iloc[0]

with st.form(f"coordinate_edit_{selected_name}"):
    c1, c2 = st.columns(2)
    jenis = c1.text_input("Jenis UPT", value=str(row.get("jenis_upt") or ""))
    kelas = c2.text_input("Kelas UPT", value=str(row.get("kelas_upt") or ""))
    province = c1.text_input("Provinsi", value=str(row.get("provinsi") or ""))
    kanwil = c2.text_input("Kanwil", value=str(row.get("kanwil") or ""))
    city = c1.text_input("Kabupaten/Kota", value=str(row.get("kabupaten_kota") or ""))
    address = c2.text_input("Alamat", value=str(row.get("alamat") or ""))
    lat = c1.number_input("Latitude", value=float(row.get("latitude") or 0.0), format="%.8f")
    lon = c2.number_input("Longitude", value=float(row.get("longitude") or 0.0), format="%.8f")
    quality_options = [
        "Terverifikasi", "Hasil pencarian otomatis", "Pusat kota/kabupaten—kandidat",
        "Pusat provinsi—perlu verifikasi", "Perlu pemeriksaan", "Belum tersedia",
    ]
    current_quality = str(row.get("coordinate_quality") or "Perlu pemeriksaan")
    quality = c1.selectbox(
        "Kualitas koordinat",
        quality_options,
        index=quality_options.index(current_quality) if current_quality in quality_options else 4,
    )
    source = c2.text_input("Sumber koordinat", value=str(row.get("coordinate_source") or ""))
    note = st.text_area("Catatan verifikasi", value=str(row.get("catatan_verifikasi") or ""), height=90)
    save_col, verify_col = st.columns(2)
    save_button = save_col.form_submit_button("SIMPAN PERUBAHAN", use_container_width=True)
    verify_button = verify_col.form_submit_button("SIMPAN & VERIFIKASI TITIK", type="primary", use_container_width=True)

if save_button or verify_button:
    payload = {
        "jenis_upt": jenis,
        "kelas_upt": kelas,
        "provinsi": province,
        "kanwil": kanwil,
        "kabupaten_kota": city,
        "alamat": address,
        "latitude": lat,
        "longitude": lon,
        "coordinate_quality": quality,
        "coordinate_source": source,
        "catatan_verifikasi": note,
        "aktif": True,
    }
    save_coordinate(selected_name, payload, admin.username, admin.role, verify=bool(verify_button))
    st.success("Koordinat UPT berhasil diperbarui.")
    st.rerun()
