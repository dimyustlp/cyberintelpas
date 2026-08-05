from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd



TRACKING_PARAMS = {
    "fbclid", "gclid", "igsh", "igshid", "mc_cid", "mc_eid", "ref", "source"
}
STOPWORDS = {
    "dan", "yang", "di", "ke", "dari", "untuk", "dengan", "pada", "dalam", "atas",
    "oleh", "ini", "itu", "sebagai", "terkait", "soal", "kasus", "berita", "kembali",
    "lapas", "rutan", "lembaga", "pemasyarakatan", "rumah", "tahanan", "kelas", "negara",
}
URGENCY_ORDER = {"Rendah": 1, "Sedang": 2, "Tinggi": 3, "Kritis": 4}
UNMAPPED_UPT_VALUES = {"", "belum teridentifikasi", "tidak diketahui", "null", "none"}


@dataclass(frozen=True)
class TrendPeriod:
    start: date
    end: date

    @property
    def previous(self) -> "TrendPeriod":
        days = (self.end - self.start).days + 1
        previous_end = self.start - timedelta(days=1)
        return TrendPeriod(previous_end - timedelta(days=days - 1), previous_end)


def normalize_url(url: Any) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    try:
        parts = urlsplit(value)
        filtered = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            low = key.lower()
            if low.startswith("utm_") or low in TRACKING_PARAMS:
                continue
            filtered.append((key, val))
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), path, urlencode(filtered), ""))
    except Exception:
        return value.rstrip("/")


def _clean_title(value: Any) -> str:
    text = re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())
    tokens = [token for token in text.split() if len(token) > 2 and token not in STOPWORDS]
    return " ".join(tokens)


def _pick_date_column(df: pd.DataFrame) -> pd.Series:
    candidates = ["detected_at", "tanggal_publikasi", "created_at"]
    parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    for column in candidates:
        if column not in df.columns:
            continue
        candidate = pd.to_datetime(df[column], errors="coerce", utc=True)
        parsed = parsed.fillna(candidate)
    return parsed


def normalize_news_frame(rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    df = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "judul", "nama_upt", "media", "sentimen", "urgensi", "link_normalized",
            "_event_at", "_event_date", "_issue_key",
        ])
    defaults = {
        "id": "", "judul": "Tanpa judul", "nama_upt": "Belum Teridentifikasi",
        "media": "Tidak diketahui", "sentimen": "Tidak diketahui", "urgensi": "Rendah",
        "link": "", "link_normalized": "", "kategori": "Lainnya", "ringkasan": "",
        "raw_analysis": "", "case_id": "", "issue_group_key": "", "status_verifikasi": "",
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default
        df[column] = df[column].fillna(default)
    df["link_normalized"] = df.apply(
        lambda row: normalize_url(row.get("link_normalized") or row.get("link")), axis=1
    )
    df["_event_at"] = _pick_date_column(df)
    df["_event_date"] = df["_event_at"].dt.tz_convert("Asia/Jakarta").dt.date
    df["nama_upt"] = df["nama_upt"].replace("", "Belum Teridentifikasi")
    df["_title_key"] = df["judul"].map(_clean_title)
    return df



def mapped_upt_mask(df: pd.DataFrame) -> pd.Series:
    """Menandai berita yang sudah dipetakan kepada UPT nyata."""
    if df.empty or "nama_upt" not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    normalized = df["nama_upt"].fillna("").astype(str).str.strip().str.casefold()
    return ~normalized.isin(UNMAPPED_UPT_VALUES)

def _cluster_issue_keys(df: pd.DataFrame) -> pd.Series:
    output = pd.Series(index=df.index, dtype="object")
    for upt, group in df.groupby("nama_upt", dropna=False):
        representatives: list[tuple[str, str]] = []
        for index, row in group.sort_values("_event_at").iterrows():
            explicit = str(row.get("case_id") or row.get("issue_group_key") or "").strip()
            if explicit:
                output.at[index] = f"explicit:{explicit}"
                continue
            key = str(row.get("_title_key") or "").strip()
            if not key:
                output.at[index] = f"article:{row.get('id') or index}"
                continue
            matched = ""
            for representative, cluster_id in representatives:
                ratio = SequenceMatcher(None, representative, key).ratio()
                token_a, token_b = set(representative.split()), set(key.split())
                overlap = len(token_a & token_b) / max(1, min(len(token_a), len(token_b)))
                if ratio >= 0.58 or overlap >= 0.62:
                    matched = cluster_id
                    break
            if not matched:
                matched = f"auto:{str(upt)}:{len(representatives) + 1}"
                representatives.append((key, matched))
            output.at[index] = matched
    return output


def _highest_urgency(values: pd.Series) -> str:
    normalized = [str(value or "Rendah").title() for value in values]
    return max(normalized, key=lambda value: URGENCY_ORDER.get(value, 0), default="Rendah")


def filter_period(df: pd.DataFrame, period: TrendPeriod) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return df[df["_event_date"].between(period.start, period.end)].copy()


def deduplicate_publications(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    with_link = df[df["link_normalized"].astype(str).str.len() > 0].drop_duplicates("link_normalized", keep="first")
    without_link = df[df["link_normalized"].astype(str).str.len() == 0].drop_duplicates(
        ["judul", "media", "_event_date"], keep="first"
    )
    return pd.concat([with_link, without_link], ignore_index=True)


def aggregate_upt(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "UPT", "Jumlah Publikasi", "Jumlah Media", "Jumlah Isu", "Berita Negatif",
            "Urgensi Tertinggi", "Isu Utama",
        ])
    working = df.copy()
    working["_issue_key"] = _cluster_issue_keys(working)
    negative = working["sentimen"].astype(str).str.casefold().eq("negatif")
    working["_is_negative"] = negative.astype(int)

    rows: list[dict[str, Any]] = []
    for upt, group in working.groupby("nama_upt", dropna=False):
        issue_counts = group.groupby("_issue_key").size().sort_values(ascending=False)
        main_issue_key = issue_counts.index[0] if not issue_counts.empty else ""
        issue_group = group[group["_issue_key"] == main_issue_key]
        main_issue = str(issue_group.iloc[0]["judul"]) if not issue_group.empty else "Tidak diketahui"
        rows.append({
            "UPT": str(upt or "Belum Teridentifikasi"),
            "Jumlah Publikasi": int(len(group)),
            "Jumlah Media": int(group["media"].astype(str).str.casefold().nunique()),
            "Jumlah Isu": int(group["_issue_key"].nunique()),
            "Berita Negatif": int(group["_is_negative"].sum()),
            "Urgensi Tertinggi": _highest_urgency(group["urgensi"]),
            "Isu Utama": main_issue,
        })
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["Berita Negatif", "Jumlah Publikasi", "Jumlah Media"], ascending=[False, False, False]
    ).reset_index(drop=True)


def daily_trend(df: pd.DataFrame, period: TrendPeriod) -> pd.DataFrame:
    dates = pd.date_range(period.start, period.end, freq="D").date
    if df.empty:
        return pd.DataFrame({"Tanggal": list(dates), "Jumlah Publikasi": [0] * len(dates)})
    counts = df.groupby("_event_date").size().reindex(dates, fill_value=0)
    return pd.DataFrame({"Tanggal": list(dates), "Jumlah Publikasi": counts.values})


def distribution(df: pd.DataFrame, column: str, order: list[str] | None = None) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "Jumlah"])
    counts = df[column].fillna("Tidak diketahui").astype(str).value_counts()
    if order:
        counts = counts.reindex(order, fill_value=0)
    result = counts.rename("Jumlah").reset_index()
    result.columns = [column, "Jumlah"]
    return result


def _percentage_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return None if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


def build_weekly_snapshot(
    rows: list[dict[str, Any]] | pd.DataFrame,
    start: date,
    end: date,
) -> dict[str, Any]:
    period = TrendPeriod(start, end)
    all_df = normalize_news_frame(rows)
    current = deduplicate_publications(filter_period(all_df, period))
    previous = deduplicate_publications(filter_period(all_df, period.previous))
    current["_issue_key"] = _cluster_issue_keys(current) if not current.empty else pd.Series(dtype="object")

    negative_mask = current["sentimen"].astype(str).str.casefold().eq("negatif") if not current.empty else pd.Series(dtype=bool)
    current_negative = current[negative_mask].copy() if not current.empty else current.copy()
    previous_negative_count = int(
        previous["sentimen"].astype(str).str.casefold().eq("negatif").sum()
    ) if not previous.empty else 0

    mapped_negative = current_negative[mapped_upt_mask(current_negative)].copy() if not current_negative.empty else current_negative.copy()
    unmapped_negative = current_negative[~mapped_upt_mask(current_negative)].copy() if not current_negative.empty else current_negative.copy()
    upt_table = aggregate_upt(mapped_negative)
    total = int(len(current))
    negative_count = int(len(current_negative))
    mapped_negative_count = int(len(mapped_negative))
    unmapped_negative_count = int(len(unmapped_negative))
    media_count = int(current["media"].astype(str).str.casefold().nunique()) if not current.empty else 0
    upt_count = int(mapped_negative["nama_upt"].nunique()) if not mapped_negative.empty else 0
    issue_count = int(current_negative["_issue_key"].nunique()) if not current_negative.empty else 0
    high_count = int(current["urgensi"].astype(str).str.casefold().isin({"tinggi", "kritis"}).sum()) if not current.empty else 0
    top_upt = upt_table.iloc[0].to_dict() if not upt_table.empty else {}

    concentration = 0.0
    if mapped_negative_count and not upt_table.empty:
        concentration = round(float(upt_table.head(2)["Berita Negatif"].sum()) / mapped_negative_count * 100, 1)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "previous_period": {"start": period.previous.start.isoformat(), "end": period.previous.end.isoformat()},
        "metrics": {
            "total_publications": total,
            "negative_publications": negative_count,
            "mapped_negative_publications": mapped_negative_count,
            "unmapped_negative_publications": unmapped_negative_count,
            "unique_media": media_count,
            "negative_upt_count": upt_count,
            "issue_count": issue_count,
            "high_critical_count": high_count,
            "previous_negative_publications": previous_negative_count,
            "negative_change_percent": _percentage_change(negative_count, previous_negative_count),
            "top_two_concentration_percent": concentration,
        },
        "top_upt": top_upt,
        "upt_table": upt_table.to_dict("records"),
        "daily_trend": daily_trend(current, period).assign(Tanggal=lambda x: x["Tanggal"].astype(str)).to_dict("records"),
        "sentiment_distribution": distribution(current, "sentimen").to_dict("records"),
        "urgency_distribution": distribution(current, "urgensi", ["Kritis", "Tinggi", "Sedang", "Rendah"]).to_dict("records"),
        "top_news": current_negative.sort_values("_event_at", ascending=False).head(20)[[
            "id", "judul", "nama_upt", "media", "urgensi", "ringkasan", "raw_analysis",
            "link_normalized", "_event_date",
        ]].assign(_event_date=lambda x: x["_event_date"].astype(str)).to_dict("records") if not current_negative.empty else [],
    }


def fetch_news_for_analysis(max_rows: int = 20000) -> list[dict[str, Any]]:
    from services.cyber_db import fetch_all

    return fetch_all(
        "berita",
        "id,created_at,detected_at,tanggal_publikasi,judul,nama_upt,media,sentimen,urgensi,"
        "link,link_normalized,kategori,ringkasan,raw_analysis,status_verifikasi,case_id,issue_group_key",
        order_by="created_at",
        desc=True,
        max_rows=max_rows,
    )
