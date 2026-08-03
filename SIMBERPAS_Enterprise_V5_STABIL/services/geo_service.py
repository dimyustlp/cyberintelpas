from __future__ import annotations

import pandas as pd

PROVINCE_CENTROIDS = {
    "Aceh": (4.6951, 96.7494),
    "Sumatera Utara": (2.1154, 99.5451),
    "Sumatera Barat": (-0.7399, 100.8000),
    "Riau": (0.2933, 101.7068),
    "Kepulauan Riau": (3.9457, 108.1429),
    "Jambi": (-1.4852, 102.4381),
    "Sumatera Selatan": (-3.3194, 103.9144),
    "Kepulauan Bangka Belitung": (-2.7411, 106.4406),
    "Bengkulu": (-3.5778, 102.3464),
    "Lampung": (-4.5586, 105.4068),
    "DKI Jakarta": (-6.2088, 106.8456),
    "Banten": (-6.4058, 106.0640),
    "Jawa Barat": (-6.9175, 107.6191),
    "Jawa Tengah": (-7.1510, 110.1403),
    "D.I. Yogyakarta": (-7.7956, 110.3695),
    "Jawa Timur": (-7.5361, 112.2384),
    "Bali": (-8.3405, 115.0920),
    "Nusa Tenggara Barat": (-8.6529, 117.3616),
    "Nusa Tenggara Timur": (-8.6574, 121.0794),
    "Kalimantan Barat": (-0.2788, 111.4753),
    "Kalimantan Tengah": (-1.6815, 113.3824),
    "Kalimantan Selatan": (-3.0926, 115.2838),
    "Kalimantan Timur": (0.5387, 116.4194),
    "Kalimantan Utara": (3.0731, 116.0414),
    "Sulawesi Utara": (0.6247, 123.9750),
    "Gorontalo": (0.6999, 122.4467),
    "Sulawesi Tengah": (-1.4300, 121.4456),
    "Sulawesi Barat": (-2.8441, 119.2321),
    "Sulawesi Selatan": (-3.6688, 119.9741),
    "Sulawesi Tenggara": (-4.1449, 122.1746),
    "Maluku": (-3.2385, 130.1453),
    "Maluku Utara": (1.5709, 127.8088),
    "Papua Barat": (-1.3361, 133.1747),
    "Papua Barat Daya": (-1.1325, 131.5637),
    "Papua": (-4.2699, 138.0804),
    "Papua Tengah": (-3.7786, 136.4710),
    "Papua Pegunungan": (-4.0000, 139.0000),
    "Papua Selatan": (-7.5000, 139.5000),
}

ALIASES = {
    "Bangka Belitung": "Kepulauan Bangka Belitung",
    "DI Yogyakarta": "D.I. Yogyakarta",
    "D.I Yogyakarta": "D.I. Yogyakarta",
    "DIY": "D.I. Yogyakarta",
    "Jakarta": "DKI Jakarta",
}


def normalize_province(value: str) -> str:
    clean = " ".join(str(value or "").split())
    return ALIASES.get(clean, clean)


def enrich_province_coordinates(upt: pd.DataFrame) -> pd.DataFrame:
    out = upt.copy()
    for column, default in {
        "provinsi": "",
        "latitude": None,
        "longitude": None,
        "coordinate_quality": "",
    }.items():
        if column not in out.columns:
            out[column] = default

    out["provinsi"] = out["provinsi"].map(normalize_province)
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")

    missing_lat = out["latitude"].isna()
    missing_lon = out["longitude"].isna()
    out.loc[missing_lat, "latitude"] = out.loc[missing_lat, "provinsi"].map(
        lambda p: PROVINCE_CENTROIDS.get(p, (None, None))[0]
    )
    out.loc[missing_lon, "longitude"] = out.loc[missing_lon, "provinsi"].map(
        lambda p: PROVINCE_CENTROIDS.get(p, (None, None))[1]
    )
    out.loc[
        (missing_lat | missing_lon) & out["latitude"].notna(),
        "coordinate_quality",
    ] = "Pusat provinsi"
    return out


def attach_news_counts(upt: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    enriched = upt.copy()

    # Hapus hasil merge lama agar tidak membentuk suffix _x dan _y.
    old_count_columns = [
        column for column in enriched.columns
        if column == "jumlah_berita" or column.startswith("jumlah_berita_")
    ]
    if old_count_columns:
        enriched = enriched.drop(columns=old_count_columns, errors="ignore")

    if news.empty or "nama_upt" not in news.columns:
        enriched["jumlah_berita"] = 0
        return enriched

    counts = (
        news["nama_upt"]
        .fillna("")
        .astype(str)
        .value_counts()
        .rename_axis("nama_upt")
        .reset_index(name="jumlah_berita")
    )
    enriched = enriched.merge(counts, on="nama_upt", how="left")
    enriched["jumlah_berita"] = (
        pd.to_numeric(enriched.get("jumlah_berita", 0), errors="coerce")
        .fillna(0)
        .astype(int)
    )
    return enriched


def province_map_data(upt: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    enriched = attach_news_counts(enrich_province_coordinates(upt), news)
    if enriched.empty:
        return pd.DataFrame(
            columns=["provinsi", "latitude", "longitude", "jumlah_upt", "jumlah_berita"]
        )

    grouped = (
        enriched.groupby("provinsi", dropna=False)
        .agg(
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
            jumlah_upt=("nama_upt", "nunique"),
            jumlah_berita=("jumlah_berita", "sum"),
        )
        .reset_index()
    )
    return grouped.dropna(subset=["latitude", "longitude"])
