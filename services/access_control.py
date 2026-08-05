from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from services.role_catalog import canonical_role, role_name


class UserContext:
    """Konteks pengguna yang kompatibel dengan SIMBERPAS V4/V5 dan CYBER-INTELPAS V6.

    Urutan argumen posisi dipertahankan seperti versi lama:
    ``id, username, full_name, role, assigned_kanwil, assigned_upt, legacy``.
    Pemanggilan berbasis keyword dari versi baru tetap didukung.
    """

    def __init__(
        self,
        id: str = "",
        username: str = "",
        full_name: str = "",
        role: str = "",
        assigned_kanwil: str | None = "",
        assigned_upt: str | None = "",
        legacy: bool = False,
        source: str = "database",
        user_id: str = "",
        aktif: bool = True,
        **extra: Any,
    ) -> None:
        self.id = str(id or user_id or "")
        self.user_id = str(user_id or id or "")
        self.username = str(username or "")
        self.full_name = str(full_name or "")
        self.role = normalize_role(role)
        self.assigned_kanwil = str(assigned_kanwil or "")
        self.assigned_upt = str(assigned_upt or "")
        self.legacy = bool(legacy)
        self.source = str(source or "database")
        self.aktif = bool(aktif)

        for key, value in extra.items():
            setattr(self, key, value)

    @property
    def display_name(self) -> str:
        return self.full_name or self.username or "Pengguna"

    @property
    def name(self) -> str:
        return self.display_name

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


ROLE_LABELS: dict[str, str] = {
    "executive_decision_maker": "Pimpinan Pengambil Keputusan",
    "media_intelligence_analyst": "Analis Intelijen Pemberitaan",
    "news_data_operator": "Operator Akuisisi dan Validasi Data",
    "field_verification_officer": "Petugas Verifikasi Lapangan",
    "evaluation_recommendation_analyst": "Analis Evaluasi dan Rekomendasi",
    "super_admin": "Administrator Utama CYBER-INTELPAS",
}


ROLE_ALIASES: dict[str, str] = {
    "pimpinan": "executive_decision_maker",
    "executive_viewer": "executive_decision_maker",
    "pimpinan_eksekutif": "executive_decision_maker",
    "viewer": "executive_decision_maker",
    "analis": "media_intelligence_analyst",
    "news_analyst": "media_intelligence_analyst",
    "analis_pemberitaan_strategis": "media_intelligence_analyst",
    "admin_pusat": "media_intelligence_analyst",
    "admin_kanwil": "media_intelligence_analyst",
    "operator": "news_data_operator",
    "news_intake": "news_data_operator",
    "operator_akuisisi_data_berita": "news_data_operator",
    "operator_upt": "news_data_operator",
    "tim_lapangan": "field_verification_officer",
    "petugas_verifikasi_lapangan": "field_verification_officer",
    "tim_analisis": "evaluation_recommendation_analyst",
    "analis_evaluasi_dan_rekomendasi": "evaluation_recommendation_analyst",
    "administrator_utama_sistem": "super_admin",
    "admin": "super_admin",
}


def normalize_role(role: str | None) -> str:
    raw = str(role or "").strip().casefold()
    if not raw:
        return ""
    aliased = ROLE_ALIASES.get(raw, raw)
    try:
        return str(canonical_role(aliased) or aliased)
    except Exception:
        return aliased


def role_label(role: str | None) -> str:
    normalized = normalize_role(role)
    if normalized in ROLE_LABELS:
        return ROLE_LABELS[normalized]
    try:
        return str(role_name(normalized) or normalized or "Pengguna")
    except Exception:
        return normalized or "Pengguna"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "executive_decision_maker": {
        "view_dashboard",
        "view_executive_brief",
        "view_news",
        "view_verified_news",
        "view_map",
        "view_ai_assistant",
        "view_weekly_trends",
        "view_cases",
        "view_field_reports",
        "view_recommendations",
        "decide_cases",
        "download_reports",
        "view_reports",
        "approve_reports",
        "publish_reports",
        "view_alerts",
        "view_action_items",
        "manage_action_items",
    },
    "media_intelligence_analyst": {
        "view_dashboard",
        "view_executive_brief",
        "view_news",
        "create_news",
        "review_news",
        "verify_news",
        "map_upt",
        "view_map",
        "view_ai_assistant",
        "view_weekly_trends",
        "manage_cases",
        "link_news_to_cases",
        "generate_reports",
        "edit_report_drafts",
        "view_reports",
        "download_reports",
        "view_alerts",
        "view_action_items",
        "upload_attachments",
    },
    "news_data_operator": {
        "view_dashboard",
        "view_executive_brief",
        "view_news",
        "create_news",
        "edit_own_news",
        "validate_news_metadata",
        "view_sync",
        "run_sync",
        "view_duplicate_news",
        "upload_attachments",
    },
    "field_verification_officer": {
        "view_dashboard",
        "view_executive_brief",
        "view_assigned_cases",
        "view_field_assignments",
        "submit_field_reports",
        "upload_field_evidence",
        "update_field_assignment",
        "view_own_field_reports",
        "view_action_items",
        "update_action_items",
    },
    "evaluation_recommendation_analyst": {
        "view_dashboard",
        "view_executive_brief",
        "view_news",
        "view_cases",
        "view_field_reports",
        "analyze_cases",
        "manage_recommendations",
        "assess_follow_up",
        "generate_reports",
        "edit_report_drafts",
        "view_reports",
        "download_reports",
        "view_weekly_trends",
        "view_action_items",
        "manage_action_items",
        "update_action_items",
    },
    "super_admin": {"*"},
}


# Semua nama izin dari V4/V5 diarahkan ke izin semantik V6.
PERMISSION_ALIASES: dict[str, str] = {
    "view_warning": "view_alerts",
    "use_ai": "view_ai_assistant",
    "view_data": "view_news",
    "export_reports": "download_reports",
    "analyze_news": "review_news",
    "edit_news": "review_news",
    "delete_news": "verify_news",
    "archive_news": "verify_news",
    "manage_coordinates": "manage_settings",
    "manage_sync": "run_sync",
    "view_audit": "view_audit_logs",
    "manage_scoped_users": "manage_users",
    "view_analytics": "view_weekly_trends",
    "manage_follow_up": "manage_recommendations",
    "manage_master_data": "manage_settings",
    "manage_roles": "manage_users",
    "manage_watchlist": "view_alerts",
    "view_all": "view_news",
    "view_kanwil": "view_news",
    "view_upt": "view_news",
}


ADMIN_ONLY: set[str] = {
    "manage_users",
    "manage_settings",
    "view_audit_logs",
    "view_system_health",
    "manage_system_health",
    "manage_integrations",
    "manage_backups",
    "manage_roles",
}


def _role_of(user: Any) -> str:
    if user is None:
        return ""
    if isinstance(user, str):
        return normalize_role(user)
    if isinstance(user, dict):
        return normalize_role(user.get("role"))
    return normalize_role(getattr(user, "role", ""))


def _value_of(user: Any, name: str, default: Any = None) -> Any:
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(name, default)
    return getattr(user, name, default)


def permissions_for(user_or_role: Any) -> set[str]:
    role = _role_of(user_or_role)
    permissions = set(ROLE_PERMISSIONS.get(role, set()))
    if role == "super_admin":
        permissions |= ADMIN_ONLY
    return permissions


def has_permission(user: Any, permission: str) -> bool:
    role = _role_of(user)
    if not role:
        return False
    if role == "super_admin":
        return True
    requested = PERMISSION_ALIASES.get(str(permission or "").strip(), str(permission or "").strip())
    return requested in ROLE_PERMISSIONS.get(role, set())


def has_any_permission(user: Any, permissions: Iterable[str]) -> bool:
    return any(has_permission(user, permission) for permission in permissions)


def _current_user_from_runtime() -> Any:
    try:
        from services.auth_service import current_user

        user = current_user()
        if user is not None:
            return user
    except Exception:
        pass

    try:
        import streamlit as st

        for key in ("simberpas_user", "current_user", "user", "auth_user", "user_context", "logged_user"):
            user = st.session_state.get(key)
            if user is not None:
                return user
    except Exception:
        pass
    return None


def require_permission(user_or_permission: Any, permission: str | None = None) -> Any:
    """Mendukung ``require_permission('izin')`` dan ``require_permission(user, 'izin')``."""
    legacy_single_argument = permission is None
    if legacy_single_argument:
        requested_permission = str(user_or_permission or "").strip()
        user = _current_user_from_runtime()
    else:
        requested_permission = str(permission or "").strip()
        user = user_or_permission

    if not requested_permission:
        raise ValueError("Nama permission tidak boleh kosong.")

    if user is None:
        message = "Sesi pengguna tidak ditemukan. Silakan login kembali."
        if legacy_single_argument:
            try:
                import streamlit as st

                st.error(message)
                st.stop()
            except Exception:
                pass
        raise PermissionError(message)

    if not has_permission(user, requested_permission):
        message = f"Pengguna tidak memiliki izin: {requested_permission}"
        if legacy_single_argument:
            try:
                import streamlit as st

                st.error("Anda tidak memiliki hak akses ke halaman ini.")
                st.stop()
            except Exception:
                pass
        raise PermissionError(message)
    return user


def _row_value(row: Any, name: str, default: Any = "") -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(name, default)
    try:
        return row.get(name, default)
    except Exception:
        return getattr(row, name, default)


def can_edit_news(user: Any, row: Any) -> bool:
    """Menentukan apakah pengguna dapat mengubah satu berita tertentu."""
    role = _role_of(user)
    if role == "super_admin":
        return True
    if role == "media_intelligence_analyst":
        return has_permission(user, "review_news")
    if role != "news_data_operator" or not has_permission(user, "edit_own_news"):
        return False

    username = str(_value_of(user, "username", "") or "").strip().casefold()
    full_name = str(_value_of(user, "full_name", "") or "").strip().casefold()
    created_by = str(_row_value(row, "created_by", "") or "").strip().casefold()
    officer = str(_row_value(row, "nama_petugas", "") or "").strip().casefold()
    status = str(_row_value(row, "status_verifikasi", "Belum Ditelaah") or "Belum Ditelaah").strip()
    is_owner = bool(username and created_by == username) or bool(full_name and officer == full_name)
    return is_owner and status in {"Belum Ditelaah", "Perlu Koreksi", "Draft", "Diajukan", "Perlu Perbaikan"}


def _apply_assignment_scope(data: Any, user: Any, all_upt: Any = None) -> Any:
    scoped = data.copy()
    assigned_upt = str(_value_of(user, "assigned_upt", "") or "").strip()
    assigned_kanwil = str(_value_of(user, "assigned_kanwil", "") or "").strip()

    if assigned_upt and "nama_upt" in scoped.columns:
        return scoped[scoped["nama_upt"].astype(str).str.strip().str.casefold() == assigned_upt.casefold()].copy()

    if assigned_kanwil:
        if "kanwil" in scoped.columns:
            return scoped[scoped["kanwil"].astype(str).str.strip().str.casefold() == assigned_kanwil.casefold()].copy()
        if (
            all_upt is not None
            and hasattr(all_upt, "columns")
            and "nama_upt" in all_upt.columns
            and "kanwil" in all_upt.columns
            and "nama_upt" in scoped.columns
        ):
            allowed_upt = all_upt.loc[
                all_upt["kanwil"].astype(str).str.strip().str.casefold() == assigned_kanwil.casefold(),
                "nama_upt",
            ].astype(str).str.strip().str.casefold()
            return scoped[scoped["nama_upt"].astype(str).str.strip().str.casefold().isin(set(allowed_upt))].copy()
    return scoped


def scope_news(data: Any, user: Any, all_upt: Any = None, *_args: Any, **_kwargs: Any) -> Any:
    if data is None:
        return data
    try:
        if user is None or not has_permission(user, "view_news"):
            return data.iloc[0:0].copy()

        scoped = _apply_assignment_scope(data, user, all_upt)
        role = _role_of(user)
        if role == "news_data_operator":
            username = str(_value_of(user, "username", "") or "").strip().casefold()
            full_name = str(_value_of(user, "full_name", "") or "").strip().casefold()
            owner_mask = None
            if "created_by" in scoped.columns and username:
                owner_mask = scoped["created_by"].astype(str).str.strip().str.casefold().eq(username)
            if "nama_petugas" in scoped.columns and full_name:
                by_name = scoped["nama_petugas"].astype(str).str.strip().str.casefold().eq(full_name)
                owner_mask = by_name if owner_mask is None else owner_mask | by_name
            if owner_mask is None:
                return scoped.iloc[0:0].copy()
            scoped = scoped[owner_mask]
        return scoped.copy()
    except Exception:
        return data


def scope_upt(data: Any, user: Any) -> Any:
    if data is None:
        return data
    try:
        if user is None:
            return data.iloc[0:0].copy()
        return _apply_assignment_scope(data, user).copy()
    except Exception:
        return data
