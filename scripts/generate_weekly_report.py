from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.cyber_db import fetch_all, update_rows
from services.report_service import build_report_package, save_weekly_report
from services.v6_audit_service import record_audit

WIB = ZoneInfo("Asia/Jakarta")
SYSTEM_USER = {
    "username": "weekly-report-scheduler",
    "full_name": "Penjadwal Laporan Mingguan",
    "role": "super_admin",
}


def main() -> int:
    today_wib = datetime.now(WIB).date()
    period_end = today_wib - timedelta(days=1)
    period_start = period_end - timedelta(days=6)

    snapshot, narrative = build_report_package(period_start, period_end, use_ai=True)
    existing = fetch_all(
        "weekly_reports",
        "id,report_number,status",
        filters=[
            ("eq", "period_start", period_start.isoformat()),
            ("eq", "period_end", period_end.isoformat()),
        ],
        order_by="created_at",
        desc=True,
        max_rows=20,
    )

    narrative_payload = {
        "executive_summary": narrative.executive_summary,
        "trend_analysis": narrative.trend_analysis,
        "priority_analysis": narrative.priority_analysis,
        "recommendations": narrative.recommendations,
        "limitations": narrative.limitations,
        "source": narrative.source,
    }

    if existing and existing[0].get("status") in {"Draf Sistem", "Ditelaah Analis"}:
        report_id = str(existing[0]["id"])
        update_rows(
            "weekly_reports",
            {
                "snapshot_data": snapshot,
                "ai_narrative": narrative_payload,
                "ai_provider": narrative.source,
                "updated_by": SYSTEM_USER["username"],
            },
            filters=[("eq", "id", report_id)],
        )
        record_audit(
            SYSTEM_USER,
            "weekly_report.scheduled_refresh",
            "weekly_report",
            report_id,
            {"period_start": period_start.isoformat(), "period_end": period_end.isoformat()},
        )
        print(f"Draf laporan {existing[0].get('report_number', report_id)} diperbarui.")
    elif existing:
        print(
            "Laporan periode yang sama sudah melewati tahap draf. "
            "Scheduler tidak mengubah laporan yang telah diverifikasi atau dipublikasikan."
        )
    else:
        row = save_weekly_report(snapshot, narrative, SYSTEM_USER, "Draf Sistem")
        print(f"Draf laporan {row.get('report_number', row.get('id', ''))} berhasil dibuat.")

    metrics = snapshot.get("metrics", {})
    print(
        "Ringkasan: "
        f"{metrics.get('total_publications', 0)} publikasi, "
        f"{metrics.get('negative_publications', 0)} negatif, "
        f"{metrics.get('negative_upt_count', 0)} UPT terpetakan."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
