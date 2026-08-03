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
                "actor_username": actor_username,
                "actor_role": actor_role,
                "metadata": metadata or {},
            }
        ).execute()
    except Exception:
        pass
