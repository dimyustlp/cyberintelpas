from __future__ import annotations

from datetime import date, datetime
from typing import Any

from services.cyber_db import insert_row
from services.role_catalog import canonical_role


def _actor(user: Any) -> tuple[str, str]:
    if isinstance(user, dict):
        username = str(user.get("username") or user.get("full_name") or "system")
        role = canonical_role(user.get("role"))
    else:
        username = str(getattr(user, "username", None) or getattr(user, "full_name", None) or "system")
        role = canonical_role(getattr(user, "role", ""))
    return username, role or "system"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def record_audit(
    user: Any,
    action: str,
    entity: str,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    *,
    strict: bool = False,
) -> bool:
    """Mencatat tindakan V6. Secara default kegagalan audit tidak mematikan proses utama."""
    username, role = _actor(user)
    payload = {
        "actor_username": username,
        "actor_role": role,
        "action": str(action),
        "entity": str(entity),
        "entity_id": str(entity_id) if entity_id else None,
        "metadata": _json_safe(metadata or {}),
    }
    try:
        insert_row("audit_log", payload)
        return True
    except Exception:
        if strict:
            raise
        return False
