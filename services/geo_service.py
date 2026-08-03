from __future__ import annotations

import html
from typing import Any

import pandas as pd

PROVINCE_CENTROIDS = {
    "Aceh": (4.6951, 96.7494), "Sumatera Utara": (2.1154, 99.5451),
    "Sumatera Barat": (-0.7399, 100.8000), "Riau": (0.2933, 101.7068),
    "Kepulauan Riau": (3.9457, 108.1429), "Jambi": (-1.4852, 102.4381),
    "Sumatera Selatan": (-3.3194, 103.9144), "Kepulauan Bangka Belitung": (-2.7411, 106.4406),
    "Bengkulu": (-3.5778, 102.3464), "Lampung": (-4.5586, 105.4068),
    "DKI Jakarta": (-6.2088, 106.8456), "Banten": (-6.4058, 106.0640),
    "Jawa Barat": (-6.9175, 107.6191), "Jawa Tengah": (-7.1510, 110.1403),
    "D.I. Yogyakarta": (-7.7956, 110.3695), "Jawa Timur": (-7.5361, 112.2384),
    "Bali": (-8.3405, 115.0920), "Nusa Tenggara Barat": (-8.6529, 117.3616),
    "Nusa Tenggara Timur": (-8.6574, 121.0794), "Kalimantan Barat": (-0.2788, 111.4753),
    "Kalimantan Tengah": (-1.6815, 113.3824), "Kalimantan Selatan": (-3.0926, 115.2838),
    "Kalimantan Timur": (0.5387, 116.4194), "Kalimantan Utara": (3.0731, 116.0414),
    "Sulawesi Utara": (0.6247, 123.9750), "Gorontalo": (0.6999, 122.4467),
    "Sulawesi Tengah": (-1.4300, 121.4456), "Sulawesi Barat": (-2.8441, 119.2321),
    "Sulawesi Selatan": (-3.6688, 119.9741), "Sulawesi Tenggara": (-4.1449, 122.1746),
    "Maluku": (-3.2385, 130.1453), "Maluku Utara": (1.5709, 127.8088),
    "Papua Barat": (-1.3361, 133.1747), "Papua Barat Daya": (-1.1325, 131.5637),
    "Papua": (-2.5337, 140.7181), "Papua Tengah": (-3.7786, 136.4710),
    "Papua Pegunungan": (-4.0000, 139.0000), "Papua Selatan": (-7.5000, 139.5000),
}

ALIASES = {
    "Bangka Belitung": "Kepulauan Bangka Belitung", "DI Yogyakarta": "D.I. Yogyakarta",
    "D.I Yogyakarta": "D.I. Yogyakarta", "DIY": "D.I. Yogyakarta", "Jakarta": "DKI Jakarta",
}

MARKER_META = {
    "critical": {"label": "Urgensi tinggi/kritis terverifikasi", "color": "#650000", "animation": "pulse-critical"},
    "negative": {"label": "Negatif terverifikasi", "color": "#D00000", "animation": "pulse-negative"},
    "draft": {"label": "Belum Ditelaah/Perlu Koreksi", "color": "#808080", "animation": "pulse-draft"},
    "neutral": {"label": "Netral terverifikasi", "color": "#D8C3A5", "animation": ""},
    "positive": {"label": "Positif terverifikasi", "color": "#16A34A", "animation": ""},
    "none": {"label": "Belum memiliki berita", "color": "#2563EB", "animation": ""},
}

VERIFIED = "Terverifikasi"
STATUS_ALIASES = {
    "Draft": "Belum Ditelaah",
    "Diajukan": "Belum Ditelaah",
    "Sedang Diperiksa": "Belum Ditelaah",
    "Perlu Perbaikan": "Perlu Koreksi",
    "Ditolak": "Tidak Valid",
}
PENDING = {"Belum Ditelaah", "Perlu Koreksi"}
EXCLUDED = {"Tidak Valid", "Diarsipkan"}


def normalize_province(value: str) -> str:
    clean = " ".join(str(value or "").split())
    return ALIASES.get(clean, clean)


def enrich_province_coordinates(upt: pd.DataFrame) -> pd.DataFrame:
    out = upt.copy()
    for column, default in {
        "provinsi": "", "latitude": None, "longitude": None, "coordinate_quality": "Belum tersedia",
    }.items():
        if column not in out.columns:
            out[column] = default
    out["provinsi"] = out["provinsi"].map(normalize_province)
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    missing = out["latitude"].isna() | out["longitude"].isna()
    if bool(missing.any()):
        lat_fallback = out.loc[missing, "provinsi"].map(
            lambda p: PROVINCE_CENTROIDS.get(p, (None, None))[0]
        ).astype(float)
        lon_fallback = out.loc[missing, "provinsi"].map(
            lambda p: PROVINCE_CENTROIDS.get(p, (None, None))[1]
        ).astype(float)
        out.loc[missing, "latitude"] = lat_fallback
        out.loc[missing, "longitude"] = lon_fallback
        out.loc[missing & out["latitude"].notna(), "coordinate_quality"] = "Pusat provinsi—perlu verifikasi"
    return out


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def build_upt_status(upt: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    out = enrich_province_coordinates(upt).copy()
    count_columns = [
        "jumlah_berita", "jumlah_terverifikasi", "jumlah_draft", "jumlah_positif", "jumlah_netral",
        "jumlah_negatif", "jumlah_tinggi", "jumlah_kritis", "jumlah_tidak_valid", "jumlah_diarsipkan",
        "jumlah_peringatan_awal",
    ]
    for col in count_columns:
        out[col] = 0
    out["marker_status"] = "none"
    out["marker_label"] = MARKER_META["none"]["label"]
    out["marker_color"] = MARKER_META["none"]["color"]
    out["marker_animation"] = ""
    out["preliminary_warning"] = False
    out["berita_terakhir"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")

    if news.empty or "nama_upt" not in news.columns:
        return out

    work = news.copy()
    for col, default in {
        "status_verifikasi": "Belum Ditelaah", "sentimen": "Tidak diketahui", "urgensi": "Rendah",
        "created_at": pd.NaT, "tanggal_publikasi": pd.NaT,
    }.items():
        if col not in work.columns:
            work[col] = default
    work["_key"] = work["nama_upt"].map(_norm)
    work["status_verifikasi"] = work["status_verifikasi"].fillna("Belum Ditelaah").astype(str).replace(STATUS_ALIASES)
    work["sentimen"] = work["sentimen"].fillna("Tidak diketahui").astype(str)
    work["urgensi"] = work["urgensi"].fillna("Rendah").astype(str)
    work["_event_date"] = pd.to_datetime(work["tanggal_publikasi"], errors="coerce", utc=True)
    created = pd.to_datetime(work["created_at"], errors="coerce", utc=True)
    work["_event_date"] = work["_event_date"].fillna(created)

    summaries: dict[str, dict[str, Any]] = {}
    for key, group in work.groupby("_key", dropna=False):
        active = group[~group["status_verifikasi"].isin(EXCLUDED)]
        verified = group[group["status_verifikasi"] == VERIFIED]
        pending = group[group["status_verifikasi"].isin(PENDING)]
        pending_urg = pending["urgensi"].str.casefold()
        preliminary_warning = bool(pending_urg.isin(["tinggi", "kritis"]).any())
        urg = verified["urgensi"].str.casefold()
        sent = verified["sentimen"].str.casefold()
        is_critical = urg.isin(["tinggi", "kritis"]).any()
        if is_critical:
            marker = "critical"
        elif sent.eq("negatif").any():
            marker = "negative"
        elif sent.eq("netral").any():
            marker = "neutral"
        elif sent.eq("positif").any():
            marker = "positive"
        elif not pending.empty:
            marker = "draft"
        else:
            marker = "none"
        summaries[key] = {
            "jumlah_berita": int(len(active)),
            "jumlah_terverifikasi": int(len(verified)),
            "jumlah_draft": int(len(pending)),
            "jumlah_positif": int(sent.eq("positif").sum()),
            "jumlah_netral": int(sent.eq("netral").sum()),
            "jumlah_negatif": int(sent.eq("negatif").sum()),
            "jumlah_tinggi": int(urg.eq("tinggi").sum()),
            "jumlah_kritis": int(urg.eq("kritis").sum()),
            "jumlah_tidak_valid": int(group["status_verifikasi"].eq("Tidak Valid").sum()),
            "jumlah_diarsipkan": int(group["status_verifikasi"].eq("Diarsipkan").sum()),
            "jumlah_peringatan_awal": int(pending_urg.isin(["tinggi", "kritis"]).sum()),
            "preliminary_warning": preliminary_warning,
            "marker_status": marker,
            "marker_label": MARKER_META[marker]["label"],
            "marker_color": MARKER_META[marker]["color"],
            "marker_animation": MARKER_META[marker]["animation"],
            "berita_terakhir": group["_event_date"].max(),
        }

    out["_key"] = out["nama_upt"].map(_norm)
    for idx, row in out.iterrows():
        summary = summaries.get(row["_key"])
        if summary:
            for key, value in summary.items():
                out.at[idx, key] = value
    return out.drop(columns=["_key"], errors="ignore")


def attach_news_counts(upt: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    return build_upt_status(upt, news)


def province_map_data(upt: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    enriched = build_upt_status(upt, news)
    if enriched.empty:
        return pd.DataFrame(columns=["provinsi", "latitude", "longitude", "jumlah_upt", "jumlah_berita"])
    return (
        enriched.groupby("provinsi", dropna=False)
        .agg(
            latitude=("latitude", "mean"), longitude=("longitude", "mean"),
            jumlah_upt=("nama_upt", "nunique"), jumlah_berita=("jumlah_berita", "sum"),
            jumlah_merah_tua=("marker_status", lambda s: int((s == "critical").sum())),
            jumlah_merah=("marker_status", lambda s: int((s == "negative").sum())),
        )
        .reset_index()
        .dropna(subset=["latitude", "longitude"])
    )


def popup_html(row: pd.Series | dict[str, Any]) -> str:
    get = row.get
    latest = get("berita_terakhir")
    latest_text = "Belum ada"
    if pd.notna(latest):
        try:
            latest_text = pd.Timestamp(latest).tz_convert("Asia/Jakarta").strftime("%d-%m-%Y %H:%M WIB")
        except Exception:
            latest_text = str(latest)
    def esc(value: Any) -> str:
        return html.escape(str(value or "-"))
    status_key = str(get("marker_status") or "none")
    badge_text = "#111827" if status_key == "neutral" else "#FFFFFF"
    return f"""
    <div style="font-family:Arial,sans-serif;min-width:280px;max-width:360px;color:#111827">
      <div style="font-weight:800;font-size:15px;margin-bottom:4px">{esc(get('nama_upt'))}</div>
      <div style="font-size:12px;color:#6B7280;margin-bottom:8px">{esc(get('kabupaten_kota'))} • {esc(get('provinsi'))}</div>
      <div style="padding:7px 9px;border-radius:8px;background:{esc(get('marker_color'))};color:{badge_text};font-weight:700;font-size:12px;margin-bottom:8px">{esc(get('marker_label'))}</div>
      <table style="width:100%;font-size:12px;border-collapse:collapse">
        <tr><td>Total aktif</td><td style="text-align:right;font-weight:700">{int(get('jumlah_berita') or 0)}</td></tr>
        <tr><td>Terverifikasi</td><td style="text-align:right;font-weight:700">{int(get('jumlah_terverifikasi') or 0)}</td></tr>
        <tr><td>Belum ditelaah/koreksi</td><td style="text-align:right;font-weight:700">{int(get('jumlah_draft') or 0)}</td></tr>
        <tr><td>Peringatan awal</td><td style="text-align:right;font-weight:700;color:#650000">{int(get('jumlah_peringatan_awal') or 0)}</td></tr>
        <tr><td>Positif</td><td style="text-align:right">{int(get('jumlah_positif') or 0)}</td></tr>
        <tr><td>Netral</td><td style="text-align:right">{int(get('jumlah_netral') or 0)}</td></tr>
        <tr><td>Negatif</td><td style="text-align:right">{int(get('jumlah_negatif') or 0)}</td></tr>
        <tr><td>Tinggi/kritis</td><td style="text-align:right">{int(get('jumlah_tinggi') or 0) + int(get('jumlah_kritis') or 0)}</td></tr>
      </table>
      <div style="margin-top:8px;font-size:11px;color:#6B7280">Koordinat: {esc(get('coordinate_quality'))}<br>Berita terakhir: {esc(latest_text)}</div>
    </div>
    """


def marker_css(disable_animation: bool = False) -> str:
    animation_override = "animation:none!important;" if disable_animation else ""
    return f"""
    <style>
      .sim-marker-wrap{{position:relative;width:26px;height:26px;}}
      .sim-marker{{position:absolute;left:6px;top:6px;width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 1px 5px rgba(0,0,0,.45);{animation_override}}}
      .sim-marker::after{{content:'';position:absolute;inset:-5px;border-radius:50%;border:2px solid currentColor;opacity:.65;{animation_override}}}
      .sim-warning-badge{{position:absolute;right:-3px;top:-5px;width:14px;height:14px;border-radius:50%;background:#650000;color:white;border:1.5px solid white;font:bold 10px/12px Arial;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.45);}}
      .pulse-critical::after{{animation:simPulse .55s infinite ease-out;}}
      .pulse-negative::after{{animation:simPulse .9s infinite ease-out;}}
      .pulse-draft::after{{animation:simPulse 2.4s infinite ease-out;}}
      .sim-warning-badge{{animation:simBadge .65s infinite alternate ease-in-out;{animation_override}}}
      @keyframes simPulse{{0%{{transform:scale(.65);opacity:.85}}100%{{transform:scale(1.9);opacity:0}}}}
      @keyframes simBadge{{0%{{transform:scale(.9)}}100%{{transform:scale(1.18)}}}}
      @media (prefers-reduced-motion: reduce){{.sim-marker::after,.sim-warning-badge{{animation:none!important;}}}}
    </style>
    """


def marker_icon_html(color: str, animation: str = "", preliminary_warning: bool = False) -> str:
    badge = '<div class="sim-warning-badge">!</div>' if preliminary_warning else ''
    return (
        f'<div class="sim-marker-wrap"><div class="sim-marker {html.escape(animation)}" '
        f'style="background:{html.escape(color)};color:{html.escape(color)}"></div>{badge}</div>'
    )
