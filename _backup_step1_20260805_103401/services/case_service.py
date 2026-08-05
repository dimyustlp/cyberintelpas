from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.cyber_db import fetch_all, get_db, insert_row, response_data, update_rows
from services.role_catalog import canonical_role
from services.v6_audit_service import record_audit


CASE_STATUSES = [
    "Terdeteksi",
    "Dalam Telaah Media",
    "Menunggu Keputusan Tindak Lanjut",
    "Ditugaskan ke Tim Lapangan",
    "Verifikasi Lapangan Berlangsung",
    "Menunggu Laporan Lapangan",
    "Dalam Analisis",
    "Menunggu Keputusan Pimpinan",
    "Dalam Tindak Lanjut UPT",
    "Dalam Pemantauan",
    "Selesai",
    "Dibuka Kembali",
]

FIELD_STATUSES = [
    "Belum Ditugaskan",
    "Ditugaskan",
    "Diterima Tim",
    "Persiapan",
    "Perjalanan",
    "Pemeriksaan Berlangsung",
    "Menunggu Dokumen UPT",
    "Draf Laporan",
    "Laporan Dikirim",
    "Perlu Perbaikan",
    "Selesai",
    "Dibatalkan",
]

FINDING_CLASSIFICATIONS = [
    "Berita sesuai fakta",
    "Berita sebagian sesuai fakta",
    "Berita tidak sesuai fakta",
    "Kejadian benar tetapi konteks media keliru",
    "Kejadian lama kembali diberitakan",
    "Belum dapat disimpulkan",
    "Memerlukan pemeriksaan tambahan",
]

ACTUALITY_STATUSES = [
    "Kejadian Baru",
    "Perkembangan Kasus Lama",
    "Konten Lama Kembali Viral",
    "Tidak Dapat Dipastikan",
]


def actor_name(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("username") or user.get("full_name") or "system")
    return str(getattr(user, "username", None) or getattr(user, "full_name", None) or "system")


def fetch_cases(limit: int = 500) -> list[dict[str, Any]]:
    return fetch_all(
        "intelligence_cases",
        "*",
        order_by="updated_at",
        desc=True,
        max_rows=limit,
    )


def create_case(payload: dict[str, Any], user: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "title": str(payload.get("title") or "").strip(),
        "issue_type": str(payload.get("issue_type") or "Lainnya").strip(),
        "primary_upt": str(payload.get("primary_upt") or "Belum Teridentifikasi").strip(),
        "priority": str(payload.get("priority") or "Sedang").strip(),
        "actuality_status": str(payload.get("actuality_status") or "Tidak Dapat Dipastikan").strip(),
        "summary": str(payload.get("summary") or "").strip(),
        "status": "Dalam Telaah Media",
        "owner_username": actor_name(user),
        "created_by": actor_name(user),
        "first_detected_at": payload.get("first_detected_at") or now,
        "last_media_at": payload.get("last_media_at") or now,
    }
    if not data["title"]:
        raise ValueError("Judul kasus wajib diisi.")
    row = insert_row("intelligence_cases", data)
    record_audit(user, "case.create", "intelligence_case", str(row.get("id") or ""), {"title": data["title"], "primary_upt": data["primary_upt"]})
    return row


def update_case(case_id: str, payload: dict[str, Any], user: Any) -> dict[str, Any]:
    data = {**payload, "updated_by": actor_name(user)}
    rows = update_rows("intelligence_cases", data, filters=[("eq", "id", case_id)])
    record_audit(user, "case.update", "intelligence_case", case_id, payload)
    return rows[0] if rows else {}


def fetch_news_candidates(limit: int = 1000) -> list[dict[str, Any]]:
    return fetch_all(
        "berita",
        "id,judul,nama_upt,media,sentimen,urgensi,link_normalized,detected_at,tanggal_publikasi,case_id",
        order_by="created_at",
        desc=True,
        max_rows=limit,
    )


def link_news_to_case(case_id: str, berita_ids: list[str], user: Any) -> int:
    if not berita_ids:
        return 0
    rows = [
        {"case_id": case_id, "berita_id": str(news_id), "linked_by": actor_name(user)}
        for news_id in berita_ids
    ]
    get_db().table("case_news").upsert(rows, on_conflict="case_id,berita_id").execute()
    for news_id in berita_ids:
        get_db().table("berita").update({"case_id": case_id}).eq("id", news_id).execute()
    refresh_case_counters(case_id)
    record_audit(user, "case.link_news", "intelligence_case", case_id, {"berita_ids": berita_ids, "count": len(rows)})
    return len(rows)


def refresh_case_counters(case_id: str) -> None:
    links = fetch_all("case_news", "berita_id", filters=[("eq", "case_id", case_id)], max_rows=5000)
    ids = [str(row["berita_id"]) for row in links if row.get("berita_id")]
    if not ids:
        update_rows(
            "intelligence_cases",
            {"article_count": 0, "media_count": 0, "negative_count": 0},
            filters=[("eq", "id", case_id)],
        )
        return
    news_rows: list[dict[str, Any]] = []
    for start in range(0, len(ids), 100):
        chunk = ids[start:start + 100]
        response = get_db().table("berita").select("id,media,sentimen,urgensi").in_("id", chunk).execute()
        news_rows.extend(response_data(response))
    media_count = len({str(row.get("media") or "").casefold() for row in news_rows if row.get("media")})
    negative_count = sum(str(row.get("sentimen") or "").casefold() == "negatif" for row in news_rows)
    urgency_rank = {"Rendah": 1, "Sedang": 2, "Tinggi": 3, "Kritis": 4}
    highest = max(
        (str(row.get("urgensi") or "Rendah").title() for row in news_rows),
        key=lambda item: urgency_rank.get(item, 0),
        default="Rendah",
    )
    update_rows(
        "intelligence_cases",
        {
            "article_count": len(news_rows),
            "media_count": media_count,
            "negative_count": negative_count,
            "highest_urgency": highest,
        },
        filters=[("eq", "id", case_id)],
    )


def create_field_assignment(payload: dict[str, Any], user: Any) -> dict[str, Any]:
    case_id = str(payload.get("case_id") or "")
    if not case_id:
        raise ValueError("Kasus wajib dipilih.")
    data = {
        "case_id": case_id,
        "assigned_to": str(payload.get("assigned_to") or "").strip(),
        "assigned_team": str(payload.get("assigned_team") or "Tim Verifikasi Lapangan").strip(),
        "instruction": str(payload.get("instruction") or "").strip(),
        "verification_questions": payload.get("verification_questions") or [],
        "due_at": payload.get("due_at"),
        "priority": str(payload.get("priority") or "Sedang"),
        "status": "Ditugaskan",
        "assigned_by": actor_name(user),
    }
    assignment = insert_row("field_assignments", data)
    update_rows(
        "intelligence_cases",
        {"status": "Ditugaskan ke Tim Lapangan", "updated_by": actor_name(user)},
        filters=[("eq", "id", case_id)],
    )
    record_audit(user, "field_assignment.create", "field_assignment", str(assignment.get("id") or ""), {"case_id": case_id, "assigned_to": data["assigned_to"], "due_at": data.get("due_at")})
    return assignment


def fetch_field_assignments(user: Any | None = None, all_rows: bool = False) -> list[dict[str, Any]]:
    filters = []
    if user is not None and not all_rows:
        filters.append(("eq", "assigned_to", actor_name(user)))
    return fetch_all(
        "field_assignments",
        "*",
        filters=filters,
        order_by="created_at",
        desc=True,
        max_rows=3000,
    )


def update_assignment_status(assignment_id: str, status: str, user: Any) -> None:
    update_rows(
        "field_assignments",
        {"status": status, "updated_by": actor_name(user)},
        filters=[("eq", "id", assignment_id)],
    )
    record_audit(user, "field_assignment.status_update", "field_assignment", assignment_id, {"status": status})


def submit_field_report(payload: dict[str, Any], user: Any) -> dict[str, Any]:
    assignment_id = str(payload.get("assignment_id") or "")
    case_id = str(payload.get("case_id") or "")
    if not assignment_id or not case_id:
        raise ValueError("Penugasan dan kasus wajib tersedia.")
    data = {
        "assignment_id": assignment_id,
        "case_id": case_id,
        "report_type": str(payload.get("report_type") or "Laporan Lengkap"),
        "visit_started_at": payload.get("visit_started_at"),
        "visit_finished_at": payload.get("visit_finished_at"),
        "officers": payload.get("officers") or [],
        "parties_met": payload.get("parties_met") or [],
        "activity_summary": str(payload.get("activity_summary") or "").strip(),
        "facts_found": str(payload.get("facts_found") or "").strip(),
        "upt_explanation": str(payload.get("upt_explanation") or "").strip(),
        "documents_checked": payload.get("documents_checked") or [],
        "obstacles": str(payload.get("obstacles") or "").strip(),
        "immediate_actions": str(payload.get("immediate_actions") or "").strip(),
        "upt_commitments": str(payload.get("upt_commitments") or "").strip(),
        "commitment_due_at": payload.get("commitment_due_at"),
        "finding_classification": str(payload.get("finding_classification") or "Belum dapat disimpulkan"),
        "initial_conclusion": str(payload.get("initial_conclusion") or "").strip(),
        "submitted_by": actor_name(user),
        "status": "Dikirim",
    }
    report = insert_row("field_reports", data)
    update_rows(
        "field_assignments",
        {"status": "Laporan Dikirim", "updated_by": actor_name(user)},
        filters=[("eq", "id", assignment_id)],
    )
    update_rows(
        "intelligence_cases",
        {"status": "Dalam Analisis", "updated_by": actor_name(user)},
        filters=[("eq", "id", case_id)],
    )
    record_audit(user, "field_report.submit", "field_report", str(report.get("id") or ""), {"case_id": case_id, "assignment_id": assignment_id, "report_type": data["report_type"]})
    return report


def fetch_field_reports(case_id: str | None = None, limit: int = 3000) -> list[dict[str, Any]]:
    filters = [("eq", "case_id", case_id)] if case_id else []
    return fetch_all(
        "field_reports",
        "*",
        filters=filters,
        order_by="submitted_at",
        desc=True,
        max_rows=limit,
    )


def save_case_analysis(payload: dict[str, Any], user: Any) -> dict[str, Any]:
    case_id = str(payload.get("case_id") or "")
    if not case_id:
        raise ValueError("Kasus wajib dipilih.")
    data = {
        "case_id": case_id,
        "analysis_version": int(payload.get("analysis_version") or 1),
        "media_narrative": str(payload.get("media_narrative") or "").strip(),
        "field_facts": str(payload.get("field_facts") or "").strip(),
        "comparison_matrix": payload.get("comparison_matrix") or [],
        "information_validity": str(payload.get("information_validity") or "Belum terverifikasi"),
        "reputation_impact": str(payload.get("reputation_impact") or "Sedang"),
        "operational_impact": str(payload.get("operational_impact") or "Terbatas"),
        "compliance_impact": str(payload.get("compliance_impact") or "Perlu pemeriksaan"),
        "media_escalation_risk": str(payload.get("media_escalation_risk") or "Stabil"),
        "root_causes": payload.get("root_causes") or [],
        "final_analysis": str(payload.get("final_analysis") or "").strip(),
        "follow_up_assessment": str(payload.get("follow_up_assessment") or "Belum Dapat Dinilai"),
        "created_by": actor_name(user),
        "status": str(payload.get("status") or "Draf"),
    }
    row = insert_row("case_analyses", data)
    update_rows(
        "intelligence_cases",
        {"status": "Menunggu Keputusan Pimpinan", "updated_by": actor_name(user)},
        filters=[("eq", "id", case_id)],
    )
    record_audit(user, "case_analysis.create", "case_analysis", str(row.get("id") or ""), {"case_id": case_id, "analysis_version": data["analysis_version"]})
    return row


def fetch_case_analyses(case_id: str | None = None, limit: int = 2000) -> list[dict[str, Any]]:
    filters = [("eq", "case_id", case_id)] if case_id else []
    return fetch_all(
        "case_analyses",
        "*",
        filters=filters,
        order_by="created_at",
        desc=True,
        max_rows=limit,
    )


def save_recommendations(case_id: str, recommendations: list[dict[str, Any]], user: Any) -> int:
    rows = []
    for item in recommendations:
        text = str(item.get("recommendation") or "").strip()
        if not text:
            continue
        rows.append({
            "case_id": case_id,
            "recommendation_type": str(item.get("recommendation_type") or "Jangka Pendek"),
            "recommendation": text,
            "responsible_party": str(item.get("responsible_party") or "").strip(),
            "due_at": item.get("due_at"),
            "priority": str(item.get("priority") or "Sedang"),
            "status": "Diusulkan",
            "created_by": actor_name(user),
        })
    if rows:
        get_db().table("case_recommendations").insert(rows).execute()
        record_audit(user, "recommendation.create", "intelligence_case", case_id, {"count": len(rows)})
    return len(rows)


def fetch_recommendations(case_id: str | None = None, limit: int = 3000) -> list[dict[str, Any]]:
    filters = [("eq", "case_id", case_id)] if case_id else []
    return fetch_all(
        "case_recommendations",
        "*",
        filters=filters,
        order_by="created_at",
        desc=True,
        max_rows=limit,
    )


def create_action_item(payload: dict[str, Any], user: Any) -> dict[str, Any]:
    data = {
        "case_id": payload.get("case_id"),
        "title": str(payload.get("title") or "").strip(),
        "description": str(payload.get("description") or "").strip(),
        "assigned_role": str(payload.get("assigned_role") or "").strip(),
        "assigned_to": str(payload.get("assigned_to") or "").strip(),
        "priority": str(payload.get("priority") or "Sedang"),
        "due_at": payload.get("due_at"),
        "status": "Belum Dimulai",
        "created_by": actor_name(user),
    }
    row = insert_row("action_items", data)
    record_audit(user, "action_item.create", "action_item", str(row.get("id") or ""), {"case_id": data.get("case_id"), "assigned_to": data.get("assigned_to"), "assigned_role": data.get("assigned_role")})
    return row


def fetch_action_items(role: str | None = None, username: str | None = None, limit: int = 3000) -> list[dict[str, Any]]:
    # Filter OR lintas role/username dilakukan di Python agar kompatibel dengan seluruh versi supabase-py.
    rows = fetch_all("action_items", "*", order_by="due_at", desc=False, max_rows=limit)
    if not role and not username:
        return rows
    output = []
    for row in rows:
        if username and row.get("assigned_to") == username:
            output.append(row)
        elif role and row.get("assigned_role") == role:
            output.append(row)
    return output


def decide_case(
    case_id: str,
    decision: str,
    note: str,
    user: Any,
    recommendation_ids: list[str] | None = None,
) -> None:
    """Mencatat keputusan pimpinan dan mengubah status kasus/rekomendasi."""
    decision_map = {
        "Disetujui": ("Disetujui", "Dalam Tindak Lanjut UPT"),
        "Perlu Penyempurnaan": ("Perlu Penyempurnaan", "Dalam Analisis"),
        "Ditolak": ("Ditolak", "Dalam Analisis"),
        "Dipantau": ("Disetujui", "Dalam Pemantauan"),
        "Selesai": ("Selesai", "Selesai"),
    }
    if decision not in decision_map:
        raise ValueError("Keputusan tidak dikenali.")
    recommendation_status, case_status = decision_map[decision]
    now = datetime.now(timezone.utc).isoformat()
    recommendations = fetch_recommendations(case_id)
    selected = set(str(item) for item in recommendation_ids or [])
    for row in recommendations:
        recommendation_id = str(row.get("id") or "")
        if selected and recommendation_id not in selected:
            continue
        update_rows(
            "case_recommendations",
            {
                "status": recommendation_status,
                "decided_by": actor_name(user),
                "decided_at": now,
                "decision_note": str(note or "").strip(),
            },
            filters=[("eq", "id", recommendation_id)],
        )
    insert_row("case_decisions", {
        "case_id": case_id,
        "decision": decision,
        "decision_note": str(note or "").strip(),
        "recommendation_ids": list(selected),
        "decided_by": actor_name(user),
    })
    update_rows(
        "intelligence_cases",
        {"status": case_status, "updated_by": actor_name(user)},
        filters=[("eq", "id", case_id)],
    )
    record_audit(user, "case.decision", "intelligence_case", case_id, {"decision": decision, "note": note, "recommendation_ids": list(selected)})


def update_action_item(
    action_item_id: str,
    *,
    status: str,
    progress_percent: int,
    user: Any,
) -> None:
    progress = max(0, min(100, int(progress_percent)))
    payload: dict[str, Any] = {"status": status, "progress_percent": progress}
    if status == "Selesai" or progress >= 100:
        payload.update({"status": "Selesai", "progress_percent": 100, "completed_at": datetime.now(timezone.utc).isoformat()})
    update_rows("action_items", payload, filters=[("eq", "id", action_item_id)])
    record_audit(user, "action_item.update", "action_item", action_item_id, payload)


def action_items_for_user(user: Any, limit: int = 3000) -> list[dict[str, Any]]:
    role = canonical_role(user.get("role") if isinstance(user, dict) else getattr(user, "role", ""))
    username = actor_name(user)
    return fetch_action_items(role=role, username=username, limit=limit)
