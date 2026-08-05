from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from services.role_catalog import canonical_role, role_name


class UserContext:
    """Konteks pengguna yang kompatibel dengan SIMBERPAS V4/V5 dan V6.

    Konstruktor dibuat longgar agar auth_service lama tetap dapat mengirim
    parameter umum maupun metadata tambahan tanpa memutus proses login.
    """

    def __init__(
        self,
        username: str = "",
        full_name: str = "",
        role: str = "",
        assigned_kanwil: str | None = None,
        assigned_upt: str | None = None,
        source: str = "database",
        id: str = "",
        user_id: str = "",
        aktif: bool = True,
        **extra: Any,
    ) -> None:
        self.username = str(username or "")
        self.full_name = str(full_name or "")
        self.role = normalize_role(role)
        self.assigned_kanwil = assigned_kanwil
        self.assigned_upt = assigned_upt
        self.source = str(source or "database")
        self.id = str(id or user_id or "")
        self.user_id = str(user_id or id or "")
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


# Nama peran V6 dan alias peran lama.
ROLE_LABELS: dict[str, str] = {
    "executive_decision_maker": "Pimpinan Pengambil Keputusan",
    "media_intelligence_analyst": "Analis Intelijen Pemberitaan",
    "news_data_operator": "Operator Akuisisi dan Validasi Data",
    "field_verification_officer": "Petugas Verifikasi Lapangan",
    "evaluation_recommendation_analyst": "Analis Evaluasi dan Rekomendasi",
    "super_admin": "Administrator Utama CYBER-INTELPAS",

    # Alias lama untuk menjaga kompatibilitas akun dan halaman terdahulu.
    "pimpinan": "Pimpinan Pengambil Keputusan",
    "executive_viewer": "Pimpinan Pengambil Keputusan",
    "pimpinan_eksekutif": "Pimpinan Pengambil Keputusan",
    "viewer": "Pimpinan Pengambil Keputusan",

    "analis": "Analis Intelijen Pemberitaan",
    "news_analyst": "Analis Intelijen Pemberitaan",
    "analis_pemberitaan_strategis": "Analis Intelijen Pemberitaan",
    "admin_pusat": "Analis Intelijen Pemberitaan",
    "admin_kanwil": "Analis Intelijen Pemberitaan",

    "operator": "Operator Akuisisi dan Validasi Data",
    "news_intake": "Operator Akuisisi dan Validasi Data",
    "operator_akuisisi_data_berita": "Operator Akuisisi dan Validasi Data",
    "operator_upt": "Operator Akuisisi dan Validasi Data",

    "tim_lapangan": "Petugas Verifikasi Lapangan",
    "petugas_verifikasi_lapangan": "Petugas Verifikasi Lapangan",

    "tim_analisis": "Analis Evaluasi dan Rekomendasi",
    "analis_evaluasi_dan_rekomendasi": "Analis Evaluasi dan Rekomendasi",

    "administrator_utama_sistem": "Administrator Utama CYBER-INTELPAS",
    "admin": "Administrator Utama CYBER-INTELPAS",
}


# Alias eksplisit sebagai lapisan pengaman apabila role_catalog versi lama
# belum mengenali seluruh nama peran V6.
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
    """Menormalkan nama peran lama menjadi kode peran CYBER-INTELPAS V6."""
    raw = str(role or "").strip().lower()
    if not raw:
        return ""

    aliased = ROLE_ALIASES.get(raw, raw)

    try:
        normalized = canonical_role(aliased)
        return str(normalized or aliased)
    except Exception:
        return aliased


def role_label(role: str | None) -> str:
    """Menghasilkan nama tampilan peran untuk komponen lama dan baru."""
    normalized = normalize_role(role)

    if normalized in ROLE_LABELS:
        return ROLE_LABELS[normalized]

    raw = str(role or "").strip().lower()
    if raw in ROLE_LABELS:
        return ROLE_LABELS[raw]

    try:
        label = role_name(normalized)
        return str(label or normalized or "Pengguna")
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
    },
    "news_data_operator": {
        "view_dashboard",
        "view_news",
        "create_news",
        "edit_own_news",
        "validate_news_metadata",
        "view_sync",
        "run_sync",
        "view_duplicate_news",
        "view_reports",
    },
    "field_verification_officer": {
        "view_dashboard",
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


# Nama izin lama tetap diterima oleh halaman SIMBERPAS V4/V5.
LEGACY_PERMISSION_ALIASES: dict[str, str] = {
    "manage_users": "manage_users",
    "manage_scoped_users": "manage_users",
    "manage_settings": "manage_settings",
    "view_analytics": "view_weekly_trends",
    "manage_follow_up": "manage_recommendations",
    "manage_master_data": "manage_settings",
    "view_audit_logs": "view_audit_logs",
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

    if role == "super_admin":
        return True

    requested = LEGACY_PERMISSION_ALIASES.get(permission, permission)
    permissions = ROLE_PERMISSIONS.get(role, set())

    return "*" in permissions or requested in permissions


def has_any_permission(user: Any, permissions: Iterable[str]) -> bool:
    return any(has_permission(user, permission) for permission in permissions)


def _current_user_from_runtime() -> Any:
    """Mengambil pengguna aktif tanpa membuat ketergantungan import permanen.

    Fungsi ini mendukung halaman lama yang memanggil:
        user = require_permission("view_dashboard")

    Import auth_service dilakukan saat fungsi dipanggil agar tidak memicu
    circular import ketika auth_service sedang mengimpor access_control.
    """
    try:
        from services.auth_service import current_user

        user = current_user()
        if user is not None:
            return user
    except Exception:
        pass

    try:
        import streamlit as st

        for key in (
            "current_user",
            "user",
            "auth_user",
            "user_context",
            "logged_user",
        ):
            user = st.session_state.get(key)
            if user is not None:
                return user
    except Exception:
        pass

    return None


def require_permission(
    user_or_permission: Any,
    permission: str | None = None,
) -> Any:
    """Memeriksa izin dengan dukungan dua pola pemanggilan.

    Pola halaman lama:
        user = require_permission("view_dashboard")

    Pola service atau halaman baru:
        user = require_permission(current_user, "view_dashboard")

    Fungsi mengembalikan objek pengguna setelah akses dinyatakan sah.
    """
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


def scope_news(
    data: Any,
    user: Any,
    all_upt: Any = None,
    *_args: Any,
    **_kwargs: Any,
) -> Any:
    """Menyaring DataFrame berita secara kompatibel dengan halaman lama dan V6.

    Mendukung kedua pola:
        scope_news(news_df, user)
        scope_news(news_df, user, all_upt)

    Parameter ``all_upt`` diterima untuk kompatibilitas halaman lama. Bila
    tersedia, data master tersebut dapat dipakai untuk menentukan lingkup
    Kanwil ketika DataFrame berita belum memiliki kolom ``kanwil``.
    """
    if data is None:
        return data

    try:
        if user is None:
            return data.iloc[0:0].copy()

        role = _role_of(user)

        if role == "field_verification_officer" and not has_permission(user, "view_news"):
            return data.iloc[0:0].copy()

        if not has_permission(user, "view_news"):
            return data.iloc[0:0].copy()

        scoped = data.copy()
        assigned_upt = _value_of(user, "assigned_upt")
        assigned_kanwil = _value_of(user, "assigned_kanwil")

        if assigned_upt and "nama_upt" in scoped.columns:
            scoped = scoped[
                scoped["nama_upt"].astype(str).str.strip()
                == str(assigned_upt).strip()
            ]
        elif assigned_kanwil:
            if "kanwil" in scoped.columns:
                scoped = scoped[
                    scoped["kanwil"].astype(str).str.strip()
                    == str(assigned_kanwil).strip()
                ]
            elif (
                all_upt is not None
                and hasattr(all_upt, "columns")
                and "nama_upt" in getattr(all_upt, "columns", [])
                and "kanwil" in getattr(all_upt, "columns", [])
                and "nama_upt" in scoped.columns
            ):
                allowed_upt = (
                    all_upt[
                        all_upt["kanwil"].astype(str).str.strip()
                        == str(assigned_kanwil).strip()
                    ]["nama_upt"]
                    .astype(str)
                    .str.strip()
                    .tolist()
                )
                scoped = scoped[
                    scoped["nama_upt"].astype(str).str.strip().isin(allowed_upt)
                ]

        return scoped.copy()
    except Exception:
        # Jangan merusak halaman jika objek bukan DataFrame.
        return data


def scope_upt(data: Any, user: Any) -> Any:
    """Menyaring master UPT untuk kompatibilitas halaman peta versi lama."""
    if data is None:
        return data

    try:
        if user is None:
            return data.iloc[0:0].copy()

        scoped = data.copy()
        assigned_upt = _value_of(user, "assigned_upt")
        assigned_kanwil = _value_of(user, "assigned_kanwil")

        if assigned_upt and "nama_upt" in scoped.columns:
            scoped = scoped[
                scoped["nama_upt"].astype(str).str.strip()
                == str(assigned_upt).strip()
            ]
        elif assigned_kanwil and "kanwil" in scoped.columns:
            scoped = scoped[
                scoped["kanwil"].astype(str).str.strip()
                == str(assigned_kanwil).strip()
            ]

        return scoped.copy()
    except Exception:
        return data