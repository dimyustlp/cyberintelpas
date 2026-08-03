from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DashboardMetrics:
    total: int
    today: int
    yesterday: int
    week: int
    month: int
    positive: int
    neutral: int
    negative: int
    high: int
    active_upt: int


def prepare_news(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    created = pd.to_datetime(out["created_at"], errors="coerce", utc=True)
    out["_created_wib"] = created.dt.tz_convert("Asia/Jakarta")
    out["_date"] = out["_created_wib"].dt.date
    return out


def apply_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty or period == "Semua waktu":
        return df
    out = prepare_news(df) if "_date" not in df.columns else df.copy()
    now = pd.Timestamp.now(tz="Asia/Jakarta")
    days = {"Hari ini": 0, "7 hari": 6, "14 hari": 13, "30 hari": 29}.get(period)
    if days is None:
        return out
    start = (now - pd.Timedelta(days=days)).date()
    return out[out["_date"].between(start, now.date())]


def dashboard_metrics(df: pd.DataFrame) -> DashboardMetrics:
    out = prepare_news(df)
    now = pd.Timestamp.now(tz="Asia/Jakarta")
    today = now.date()
    yesterday = (now - pd.Timedelta(days=1)).date()
    week_start = (now - pd.Timedelta(days=6)).date()
    month_start = now.replace(day=1).date()
    return DashboardMetrics(
        total=len(out),
        today=int((out["_date"] == today).sum()),
        yesterday=int((out["_date"] == yesterday).sum()),
        week=int(out["_date"].between(week_start, today).sum()),
        month=int(out["_date"].between(month_start, today).sum()),
        positive=int((out["sentimen"] == "Positif").sum()),
        neutral=int((out["sentimen"] == "Netral").sum()),
        negative=int((out["sentimen"] == "Negatif").sum()),
        high=int(out["urgensi"].isin(["Tinggi", "Kritis"]).sum()),
        active_upt=int(out["nama_upt"].nunique()),
    )


def daily_trend(df: pd.DataFrame, days: int = 14) -> pd.DataFrame:
    out = prepare_news(df)
    today = pd.Timestamp.now(tz="Asia/Jakarta").date()
    start = today - pd.Timedelta(days=days - 1)
    dates = pd.date_range(start, today, freq="D")
    grouped = out[out["_date"].between(start, today)].groupby("_date").size()
    trend = grouped.reindex(dates.date, fill_value=0).rename("Jumlah").reset_index()
    trend.columns = ["Tanggal", "Jumlah"]
    trend["Tanggal"] = pd.to_datetime(trend["Tanggal"])
    return trend


def count_table(df: pd.DataFrame, column: str, limit: int = 10) -> pd.DataFrame:
    table = df[column].fillna("Tidak diketahui").astype(str).value_counts().head(limit).reset_index()
    table.columns = [column, "Jumlah"]
    return table


def deterministic_summary(df: pd.DataFrame) -> tuple[str, str, str]:
    if df.empty:
        return "Belum ada data yang dapat diringkas.", "RENDAH", "Tambahkan berita untuk memulai analisis."
    m = dashboard_metrics(df)
    top_platform = df["platform"].value_counts().index[0]
    top_upt = df["nama_upt"].value_counts().index[0]
    top_category = df["kategori"].value_counts().index[0]
    now = pd.Timestamp.now(tz="Asia/Jakarta")
    summary = (
        f"Hingga pukul {now.strftime('%H:%M')} WIB, sistem menghimpun <b>{m.total} berita</b>, "
        f"dengan <b>{m.today} berita hari ini</b>. Terdapat <b>{m.negative} berita negatif</b> "
        f"dan <b>{m.high} berita berurgensi tinggi</b>. Platform paling aktif adalah "
        f"<b>{top_platform}</b>, kategori terbanyak adalah <b>{top_category}</b>, dan UPT "
        f"dengan pemberitaan terbanyak adalah <b>{top_upt}</b>."
    )
    if m.high > 0 or m.negative >= 5:
        return summary, "TINGGI", "Lakukan telaah internal segera dan prioritaskan validasi sumber serta dampak pemberitaan."
    if m.negative > 0:
        return summary, "SEDANG", "Pantau perkembangan berita negatif dan pastikan data telah ditelaah oleh Analis Pemberitaan Strategis."
    return summary, "RENDAH", "Situasi pemberitaan relatif terkendali. Lanjutkan monitoring rutin."


def rule_based_answer(question: str, df: pd.DataFrame) -> str:
    q = question.casefold()
    if df.empty:
        return "Belum ada data berita pada cakupan akun Anda."
    work = prepare_news(df)
    now = pd.Timestamp.now(tz="Asia/Jakarta")
    if "minggu" in q or "7 hari" in q:
        work = work[work["_date"].between((now - pd.Timedelta(days=6)).date(), now.date())]
    elif "hari ini" in q:
        work = work[work["_date"] == now.date()]
    if "negatif" in q:
        neg = work[work["sentimen"] == "Negatif"]
        top = neg["nama_upt"].value_counts().head(5)
        detail = ", ".join(f"{idx} ({val})" for idx, val in top.items()) or "belum ada UPT dominan"
        return f"Terdapat {len(neg)} berita negatif. UPT terbanyak: {detail}."
    if "urgensi" in q or "prioritas" in q:
        high = work[work["urgensi"].isin(["Tinggi", "Kritis"])]
        titles = high["judul"].head(5).tolist()
        return f"Terdapat {len(high)} berita berurgensi tinggi. Contoh prioritas: " + ("; ".join(titles) if titles else "tidak ada.")
    if "upt" in q and ("terbanyak" in q or "paling" in q or "aktif" in q):
        top = work["nama_upt"].value_counts().head(10)
        return "UPT paling aktif: " + "; ".join(f"{idx} ({val} berita)" for idx, val in top.items()) + "."
    if "platform" in q:
        top = work["platform"].value_counts().head(8)
        return "Distribusi platform: " + "; ".join(f"{idx} ({val})" for idx, val in top.items()) + "."
    if "kategori" in q or "isu" in q:
        top = work["kategori"].value_counts().head(8)
        return "Kategori dominan: " + "; ".join(f"{idx} ({val})" for idx, val in top.items()) + "."
    summary, attention, recommendation = deterministic_summary(work)
    return f"{summary.replace('<b>', '').replace('</b>', '')} Tingkat perhatian: {attention}. {recommendation}"
