from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

ROLE_LABELS = {
    "super_admin": "Super Admin",
    "admin_pusat": "Admin Pusat",
    "admin_kanwil": "Admin Kanwil",
    "operator_upt": "Operator UPT",
    "viewer": "Viewer",
}

PERMISSIONS = {
    "super_admin": {"view_all", "create_news", "edit_news", "delete_news", "verify_news", "manage_users", "manage_settings", "view_audit"},
    "admin_pusat": {"view_all", "create_news", "edit_news", "delete_news", "verify_news", "manage_users", "manage_settings", "view_audit"},
    "admin_kanwil": {"create_news", "edit_news", "verify_news", "manage_scoped_users"},
    "operator_upt": {"create_news", "edit_own_news"},
    "viewer": set(),
}


@dataclass(frozen=True)
class UserContext:
    id: str
    username: str
    full_name: str
    role: str
    assigned_kanwil: str = ""
    assigned_upt: str = ""
    legacy: bool = False


def has_permission(user: UserContext | None, permission: str) -> bool:
    if user is None:
        return False
    return permission in PERMISSIONS.get(user.role, set())


def require_permission(permission: str) -> UserContext:
    from services.auth_service import current_user
    user = current_user()
    if user is None:
        st.error("Sesi pengguna berakhir. Silakan keluar lalu masuk kembali.")
        st.stop()
    if not has_permission(user, permission):
        st.error("Anda tidak memiliki hak akses untuk membuka fitur ini.")
        st.stop()
    return user


def scope_upt(df: pd.DataFrame, user: UserContext | None) -> pd.DataFrame:
    if df.empty:
        return df
    if user is None:
        return df.iloc[0:0].copy()
    if has_permission(user, "view_all"):
        return df
    scoped = df.copy()
    if user.assigned_upt:
        return scoped[scoped["nama_upt"].astype(str).str.casefold() == user.assigned_upt.casefold()]
    if user.assigned_kanwil:
        return scoped[scoped["kanwil"].astype(str).str.casefold() == user.assigned_kanwil.casefold()]
    return scoped.iloc[0:0]


def scope_news(news: pd.DataFrame, user: UserContext | None, upt: pd.DataFrame | None = None) -> pd.DataFrame:
    if news.empty:
        return news
    if user is None:
        return news.iloc[0:0].copy()
    if has_permission(user, "view_all"):
        return news
    scoped = news.copy()
    if user.assigned_upt:
        return scoped[scoped["nama_upt"].astype(str).str.casefold() == user.assigned_upt.casefold()]
    if user.assigned_kanwil and upt is not None and not upt.empty:
        allowed = upt.loc[
            upt["kanwil"].astype(str).str.casefold() == user.assigned_kanwil.casefold(),
            "nama_upt",
        ].astype(str).tolist()
        return scoped[scoped["nama_upt"].isin(allowed)]
    return scoped.iloc[0:0]
