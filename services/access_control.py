from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

# Kode peran baru untuk penggunaan internal pusat.
ROLE_LABELS = {
    "super_admin": "Administrator Utama Sistem",
    "news_analyst": "Analis Pemberitaan Strategis",
    "news_intake": "Operator Akuisisi Data Berita",
    "executive_viewer": "Pimpinan Eksekutif",
}

# Kompatibilitas akun lama. Migrasi SQL akan mengganti nilai di database,
# tetapi kode ini mencegah akun lama langsung kehilangan akses sebelum migrasi.
ROLE_ALIASES = {
    "admin_pusat": "news_analyst",
    "admin_kanwil": "news_analyst",
    "operator_upt": "news_intake",
    "viewer": "executive_viewer",
}

PERMISSIONS = {
    "super_admin": {
        "view_dashboard", "view_all", "view_data", "view_map", "view_warning",
        "create_news", "analyze_news", "edit_news", "review_news", "verify_news",
        "archive_news", "upload_attachments", "use_ai", "export_reports",
        "manage_users", "manage_settings", "manage_coordinates", "view_audit",
        "view_sensitive",
    },
    "news_analyst": {
        "view_dashboard", "view_all", "view_data", "view_map", "view_warning",
        "create_news", "analyze_news", "edit_news", "review_news", "verify_news",
        "archive_news", "upload_attachments", "use_ai", "export_reports",
    },
    "news_intake": {
        "view_dashboard", "view_data", "create_news", "edit_own_news",
        "upload_attachments", "view_own_news",
    },
    "executive_viewer": {
        "view_dashboard", "view_all", "view_data", "view_map", "view_warning",
        "use_ai", "export_reports",
    },
}


@dataclass(frozen=True)
class UserContext:
    id: str
    username: str
    full_name: str
    role: str
    # Dipertahankan untuk kompatibilitas database lama. Pada model internal pusat
    # kedua nilai ini tidak lagi digunakan sebagai pembatas akses.
    assigned_kanwil: str = ""
    assigned_upt: str = ""
    legacy: bool = False


def normalize_role(role: str | None) -> str:
    clean = str(role or "executive_viewer").strip()
    return ROLE_ALIASES.get(clean, clean)


def role_label(role: str | None) -> str:
    normalized = normalize_role(role)
    return ROLE_LABELS.get(normalized, normalized)


def has_permission(user: UserContext | None, permission: str) -> bool:
    return bool(user and permission in PERMISSIONS.get(normalize_role(user.role), set()))


def require_permission(permission: str) -> UserContext:
    from services.auth_service import current_user

    user = current_user()
    if user is None:
        st.error("Sesi pengguna berakhir. Silakan masuk kembali.")
        st.stop()
    if not has_permission(user, permission):
        st.error("Anda tidak memiliki hak akses untuk membuka fitur ini.")
        st.stop()
    return user


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def scope_upt(df: pd.DataFrame, user: UserContext | None) -> pd.DataFrame:
    """Seluruh peran internal pusat dapat melihat daftar UPT sebagai objek data."""
    if df.empty:
        return df
    if user is None:
        return df.iloc[0:0].copy()
    return df.copy()


def scope_news(news: pd.DataFrame, user: UserContext | None, upt: pd.DataFrame | None = None) -> pd.DataFrame:
    """Batasi Operator Akuisisi pada berita miliknya; peran lain melihat data nasional."""
    if news.empty:
        return news
    if user is None:
        return news.iloc[0:0].copy()
    role = normalize_role(user.role)
    if role in {"super_admin", "news_analyst", "executive_viewer"}:
        return news.copy()
    if role == "news_intake":
        owner_values = {_clean(user.username), _clean(user.full_name)}
        created = news.get("created_by", pd.Series("", index=news.index)).map(_clean)
        named = news.get("nama_petugas", pd.Series("", index=news.index)).map(_clean)
        return news[created.isin(owner_values) | named.isin(owner_values)].copy()
    return news.iloc[0:0].copy()


def can_access_upt(user: UserContext | None, nama_upt: str, upt: pd.DataFrame | None = None) -> bool:
    return user is not None


def can_edit_news(user: UserContext | None, row: pd.Series | dict[str, Any]) -> bool:
    if user is None:
        return False
    if has_permission(user, "edit_news"):
        return True
    if not has_permission(user, "edit_own_news"):
        return False
    owner = _clean(row.get("created_by") or row.get("nama_petugas"))
    is_owner = owner in {_clean(user.username), _clean(user.full_name)}
    status = str(row.get("status_verifikasi") or "Belum Ditelaah")
    return is_owner and status in {"Belum Ditelaah", "Perlu Koreksi", "Draft", "Perlu Perbaikan"}


def can_review_news(user: UserContext | None) -> bool:
    return has_permission(user, "review_news")
