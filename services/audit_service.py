from __future__ import annotations

from typing import Any

from services.database import get_db, table_exists


def log_action(
    action: str,
    entity: str,
    entity_id: str = "",
    actor_username: str = "system",
    actor_role: str = "system",
    metadata: dict[str, Any] | None = None,
) -> None:
    if not table_exists("audit_log"):
        return
    db = get_db()
    if db is None:
        return
    try:
        db.table("audit_log").insert(
            {
                "action": action,
                "entity": entity,
                "entity_id": entity_id or None,
                "actor_username": actor_username or "system",
                "actor_role": actor_role or "system",
                "metadata": metadata or {},
            }
        ).execute()
    except Exception:
        # Audit tidak boleh menjatuhkan proses utama. Kesalahan tetap terlihat pada health check.
        pass
