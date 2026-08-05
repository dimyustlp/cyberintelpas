from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from services.case_service import actor_name, fetch_action_items, fetch_cases, fetch_field_assignments, fetch_field_reports
from services.cyber_db import fetch_all
from services.role_catalog import canonical_role, role_name
from services.system_health_service import collect_system_health
from services.trend_service import build_weekly_snapshot, fetch_news_for_analysis, normalize_news_frame

WIB = ZoneInfo("Asia/Jakarta")


@dataclass
class BriefingCard:
    label: str
    value: int | str
    help_text: str = ""


@dataclass
class RoleBriefing:
    role_code: str
    role_name: str
    title: str
    punchline: str
    cards: list[BriefingCard] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    priorities: list[dict[str, str]] = field(default_factory=list)
    status: str = "Normal"


def _safe(callable_, default):
    try:
        return callable_()
    except Exception:
        return default


def _today_news() -> pd.DataFrame:
    rows = _safe(lambda: fetch_news_for_analysis(10000), [])
    df = normalize_news_frame(rows)
    if df.empty:
        return df
    today = datetime.now(timezone.utc).astimezone(WIB).date()
    return df[df["_event_date"] == today].copy()


def _role_and_username(user: Any) -> tuple[str, str]:
    role = canonical_role(user.get("role") if isinstance(user, dict) else getattr(user, "role", ""))
    username = actor_name(user)
    return role, username


def _priority_news(df: pd.DataFrame, limit: int = 3) -> list[dict[str, str]]:
    if df.empty:
        return []
    rank = {"Rendah": 1, "Sedang": 2, "Tinggi": 3, "Kritis": 4}
    working = df.copy()
    working["_urgency_rank"] = working["urgensi"].astype(str).str.title().map(rank).fillna(0)
    working["_negative"] = working["sentimen"].astype(str).str.casefold().eq("negatif").astype(int)
    working = working.sort_values(["_urgency_rank", "_negative", "_event_at"], ascending=[False, False, False])
    rows = []
    for _, row in working.head(limit).iterrows():
        rows.append({
            "title": str(row.get("judul") or "Tanpa judul"),
            "meta": f"{row.get('nama_upt') or 'Belum Teridentifikasi'} · {row.get('urgensi') or 'Rendah'}",
            "analysis": str(row.get("ringkasan") or row.get("raw_analysis") or "Belum ada ringkasan."),
        })
    return rows


def _executive_briefing(user: Any) -> RoleBriefing:
    today_df = _today_news()
    negative = int(today_df["sentimen"].astype(str).str.casefold().eq("negatif").sum()) if not today_df.empty else 0
    high = int(today_df["urgensi"].astype(str).str.casefold().isin({"tinggi", "kritis"}).sum()) if not today_df.empty else 0
    cases = _safe(fetch_cases, [])
    awaiting_decision = sum(row.get("status") == "Menunggu Keputusan Pimpinan" for row in cases)
    overdue = _safe(lambda: fetch_action_items(), [])
    now = datetime.now(timezone.utc)
    overdue_count = 0
    for item in overdue:
        due = pd.to_datetime(item.get("due_at"), errors="coerce", utc=True)
        if pd.notna(due) and due.to_pydatetime() < now and item.get("status") not in {"Selesai", "Dibatalkan"}:
            overdue_count += 1
    if high:
        punchline = f"Terdapat {high} pemberitaan berurgensi tinggi atau kritis hari ini. Fokus pimpinan diarahkan pada isu yang belum memiliki keputusan dan tindak lanjut melewati tenggat."
        status = "Perhatian Tinggi"
    elif negative:
        punchline = f"Terdapat {negative} pemberitaan negatif hari ini. Situasi perlu dipantau, terutama pada UPT dengan eksposur media berulang."
        status = "Perlu Perhatian"
    else:
        punchline = "Situasi pemberitaan hari ini relatif terkendali. Tidak ada lonjakan negatif yang menonjol pada data yang telah masuk."
        status = "Normal"
    return RoleBriefing(
        "executive_decision_maker", role_name("executive_decision_maker"),
        "Ringkasan Eksekutif Hari Ini", punchline,
        cards=[
            BriefingCard("Total berita hari ini", len(today_df)),
            BriefingCard("Berita negatif", negative),
            BriefingCard("Urgensi tinggi/kritis", high),
            BriefingCard("Menunggu keputusan", awaiting_decision),
            BriefingCard("Tindak lanjut terlambat", overdue_count),
        ],
        todos=[
            f"Berikan keputusan pada {awaiting_decision} kasus yang menunggu arahan." if awaiting_decision else "Tidak ada kasus yang menunggu keputusan pimpinan.",
            f"Periksa {overdue_count} tindak lanjut yang melewati tenggat." if overdue_count else "Tidak ada tindak lanjut yang melewati tenggat.",
            f"Baca {high} berita prioritas tinggi atau kritis." if high else "Lanjutkan pemantauan rutin.",
        ],
        priorities=_priority_news(today_df),
        status=status,
    )


def _media_analyst_briefing(user: Any) -> RoleBriefing:
    rows = _safe(lambda: fetch_news_for_analysis(10000), [])
    df = normalize_news_frame(rows)
    unreviewed = int(df["status_verifikasi"].astype(str).isin({"Belum Ditelaah", "Perlu Koreksi", ""}).sum()) if not df.empty else 0
    unmapped = int(df["nama_upt"].astype(str).str.casefold().isin({"", "belum teridentifikasi", "tidak diketahui"}).sum()) if not df.empty else 0
    high_unreviewed = int((df["urgensi"].astype(str).str.casefold().isin({"tinggi", "kritis"}) & df["status_verifikasi"].astype(str).ne("Terverifikasi")).sum()) if not df.empty else 0
    cases = _safe(fetch_cases, [])
    media_review_cases = sum(row.get("status") in {"Terdeteksi", "Dalam Telaah Media"} for row in cases)
    todos = [
        f"Telaah {unreviewed} berita berstatus Belum Ditelaah atau Perlu Koreksi.",
        f"Petakan UPT pada {unmapped} berita yang belum teridentifikasi.",
        f"Dahulukan {high_unreviewed} berita tinggi atau kritis yang belum terverifikasi.",
        f"Kelompokkan publikasi pada {media_review_cases} kasus yang masih dalam telaah media.",
    ]
    return RoleBriefing(
        "media_intelligence_analyst", role_name("media_intelligence_analyst"),
        "Briefing Analis Intelijen Pemberitaan",
        "Prioritas hari ini adalah memastikan berita berisiko tinggi memiliki UPT, klasifikasi, dan kelompok isu yang benar sebelum naik menjadi bahan pimpinan.",
        cards=[
            BriefingCard("Belum ditelaah", unreviewed),
            BriefingCard("UPT belum terpetakan", unmapped),
            BriefingCard("Tinggi/kritis belum valid", high_unreviewed),
            BriefingCard("Kasus dalam telaah media", media_review_cases),
        ],
        todos=todos,
        priorities=_priority_news(df[df["status_verifikasi"].astype(str).ne("Terverifikasi")]),
        status="Perlu Tindakan" if high_unreviewed else "Normal",
    )


def _operator_briefing(user: Any) -> RoleBriefing:
    today_df = _today_news()
    sync_logs = _safe(lambda: fetch_all("sheet_sync_log", "*", order_by="started_at", desc=True, max_rows=50), [])
    latest = sync_logs[0] if sync_logs else {}
    failed_sync = sum(str(row.get("status") or "").casefold() in {"gagal", "failed"} for row in sync_logs)
    if not today_df.empty:
        non_empty_links = today_df["link_normalized"].astype(str).str.strip()
        duplicate_count = int(non_empty_links[non_empty_links.ne("")].duplicated().sum())
    else:
        duplicate_count = 0
    incomplete = 0
    if not today_df.empty:
        incomplete = int(
            (today_df["judul"].astype(str).str.strip().eq("") |
             today_df["media"].astype(str).str.strip().isin({"", "Tidak diketahui"}) |
             today_df["link_normalized"].astype(str).str.strip().eq("")).sum()
        )
    latest_status = str(latest.get("status") or "Belum ada log")
    return RoleBriefing(
        "news_data_operator", role_name("news_data_operator"),
        "Briefing Akuisisi dan Validasi Data",
        f"Aliran data terakhir berstatus {latest_status}. Pekerjaan utama operator adalah memastikan tidak ada link rusak, metadata kosong, atau publikasi identik yang masuk dua kali.",
        cards=[
            BriefingCard("Data masuk hari ini", len(today_df)),
            BriefingCard("Metadata belum lengkap", incomplete),
            BriefingCard("Duplikat dalam tampilan", duplicate_count),
            BriefingCard("Sinkronisasi gagal terakhir", failed_sync),
        ],
        todos=[
            f"Lengkapi metadata pada {incomplete} berita." if incomplete else "Metadata berita hari ini lengkap.",
            f"Periksa {failed_sync} log sinkronisasi gagal." if failed_sync else "Tidak ada log sinkronisasi gagal pada pemeriksaan terakhir.",
            f"Tinjau {duplicate_count} kandidat duplikat." if duplicate_count else "Tidak ada kandidat link identik pada data hari ini.",
        ],
        priorities=[],
        status="Perlu Tindakan" if failed_sync or incomplete else "Normal",
    )


def _field_briefing(user: Any) -> RoleBriefing:
    assignments = _safe(lambda: fetch_field_assignments(user, all_rows=False), [])
    active = [row for row in assignments if row.get("status") not in {"Selesai", "Dibatalkan"}]
    now = datetime.now(timezone.utc)
    due_24h = 0
    overdue = 0
    for row in active:
        due = pd.to_datetime(row.get("due_at"), errors="coerce", utc=True)
        if pd.isna(due):
            continue
        delta = due.to_pydatetime() - now
        if delta.total_seconds() < 0:
            overdue += 1
        elif delta <= timedelta(hours=24):
            due_24h += 1
    reports = _safe(fetch_field_reports, [])
    own_reports = [row for row in reports if row.get("submitted_by") == actor_name(user)]
    draft_or_revision = sum(row.get("status") in {"Draf", "Perlu Perbaikan"} for row in own_reports)
    return RoleBriefing(
        "field_verification_officer", role_name("field_verification_officer"),
        "Briefing Petugas Verifikasi Lapangan",
        "Fokus lapangan adalah ketepatan fakta, kelengkapan bukti, dan kecepatan pembaruan kondisi UPT. Laporan cepat didahulukan untuk kasus mendesak.",
        cards=[
            BriefingCard("Tugas aktif", len(active)),
            BriefingCard("Jatuh tempo 24 jam", due_24h),
            BriefingCard("Melewati tenggat", overdue),
            BriefingCard("Laporan perlu dilengkapi", draft_or_revision),
        ],
        todos=[
            f"Selesaikan {overdue} penugasan yang melewati tenggat." if overdue else "Tidak ada penugasan yang terlambat.",
            f"Persiapkan {due_24h} tugas yang jatuh tempo dalam 24 jam." if due_24h else "Tidak ada tenggat dalam 24 jam.",
            f"Lengkapi {draft_or_revision} laporan atau bukti." if draft_or_revision else "Tidak ada laporan yang perlu diperbaiki.",
        ],
        status="Perhatian Tinggi" if overdue else ("Perlu Tindakan" if due_24h else "Normal"),
    )


def _evaluation_briefing(user: Any) -> RoleBriefing:
    reports = _safe(fetch_field_reports, [])
    analyses = _safe(lambda: fetch_all("case_analyses", "*", order_by="created_at", desc=True, max_rows=3000), [])
    analyzed_cases = {str(row.get("case_id")) for row in analyses if row.get("case_id")}
    new_reports = [row for row in reports if str(row.get("case_id")) not in analyzed_cases]
    draft_analyses = sum(row.get("status") == "Draf" for row in analyses)
    recommendations = _safe(lambda: fetch_all("case_recommendations", "*", max_rows=3000), [])
    pending_rec = sum(row.get("status") in {"Diusulkan", "Menunggu Keputusan"} for row in recommendations)
    escalation = sum(str(row.get("media_escalation_risk") or "").casefold() in {"sedang meningkat", "viral"} for row in analyses)
    return RoleBriefing(
        "evaluation_recommendation_analyst", role_name("evaluation_recommendation_analyst"),
        "Briefing Analis Evaluasi dan Rekomendasi",
        "Prioritas analisis adalah menyatukan bukti media dan temuan lapangan menjadi kesimpulan yang dapat dipertanggungjawabkan, lalu mengubahnya menjadi rekomendasi terukur.",
        cards=[
            BriefingCard("Laporan lapangan baru", len(new_reports)),
            BriefingCard("Analisis masih draf", draft_analyses),
            BriefingCard("Rekomendasi menunggu", pending_rec),
            BriefingCard("Risiko eskalasi", escalation),
        ],
        todos=[
            f"Analisis {len(new_reports)} laporan lapangan baru." if new_reports else "Tidak ada laporan lapangan baru.",
            f"Selesaikan {draft_analyses} analisis yang masih draf." if draft_analyses else "Tidak ada analisis draf.",
            f"Lengkapi penanggung jawab dan tenggat pada {pending_rec} rekomendasi." if pending_rec else "Tidak ada rekomendasi tertunda.",
        ],
        status="Perhatian Tinggi" if escalation else ("Perlu Tindakan" if new_reports or draft_analyses else "Normal"),
    )


def _admin_briefing(user: Any) -> RoleBriefing:
    health = collect_system_health()
    critical = [row for row in health if row["status"] == "Kritis"]
    warnings = [row for row in health if row["status"] == "Peringatan"]
    normal = [row for row in health if row["status"] == "Normal"]
    todo = [f"Periksa {row['component']}: {row['message']}" for row in critical + warnings]
    if not todo:
        todo = ["Seluruh komponen yang dapat diperiksa berada dalam kondisi normal."]
    return RoleBriefing(
        "super_admin", role_name("super_admin"),
        "System Operations Brief",
        f"Sebanyak {len(normal)} komponen normal, {len(warnings)} memerlukan perhatian, dan {len(critical)} berada pada kondisi kritis. Administrator perlu mendahulukan kegagalan sinkronisasi, database, autentikasi, dan generator laporan.",
        cards=[
            BriefingCard("Komponen normal", len(normal)),
            BriefingCard("Peringatan", len(warnings)),
            BriefingCard("Kritis", len(critical)),
            BriefingCard("Total diperiksa", len(health)),
        ],
        todos=todo,
        priorities=[{"title": row["component"], "meta": row["status"], "analysis": row["message"]} for row in critical + warnings][:5],
        status="Perhatian Tinggi" if critical else ("Perlu Tindakan" if warnings else "Normal"),
    )


def build_role_briefing(user: Any) -> RoleBriefing:
    role, _ = _role_and_username(user)
    builders = {
        "executive_decision_maker": _executive_briefing,
        "media_intelligence_analyst": _media_analyst_briefing,
        "news_data_operator": _operator_briefing,
        "field_verification_officer": _field_briefing,
        "evaluation_recommendation_analyst": _evaluation_briefing,
        "super_admin": _admin_briefing,
    }
    builder = builders.get(role, _operator_briefing)
    return builder(user)
