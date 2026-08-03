from __future__ import annotations

import uuid
from datetime import datetime, timezone

import bcrypt
import streamlit as st

from services.access_control import ROLE_LABELS, UserContext, normalize_role
from services.audit_service import log_action
from services.config import get_config
from services.database import clear_data_cache, get_db, table_exists

SESSION_KEY = "simberpas_user"


def init_auth_state() -> None:
    st.session_state.setdefault(SESSION_KEY, None)


def current_user() -> UserContext | None:
    value = st.session_state.get(SESSION_KEY)
    if isinstance(value, UserContext):
        normalized = normalize_role(value.role)
        if normalized == value.role:
            return value
        return UserContext(
            id=value.id,
            username=value.username,
            full_name=value.full_name,
            role=normalized,
            assigned_kanwil="",
            assigned_upt="",
            legacy=value.legacy,
        )
    if isinstance(value, dict):
        allowed = {
            "id", "username", "full_name", "role", "assigned_kanwil", "assigned_upt", "legacy"
        }
        clean = {key: value.get(key) for key in allowed if key in value}
        clean.setdefault("id", "session-user")
        clean.setdefault("username", "admin")
        clean.setdefault("full_name", clean["username"])
        clean.setdefault("role", "executive_viewer")
        clean["role"] = normalize_role(clean.get("role"))
        clean.setdefault("assigned_kanwil", "")
        clean.setdefault("assigned_upt", "")
        clean.setdefault("legacy", False)
        try:
            return UserContext(**clean)
        except (TypeError, ValueError):
            st.session_state[SESSION_KEY] = None
    return None


def logout() -> None:
    user = current_user()
    if user:
        log_action("logout", "session", actor_username=user.username, actor_role=user.role)
    st.session_state.clear()
    st.rerun()


def _hash_password(password: str) -> str:
    if len(password or "") < 8:
        raise ValueError("Kata sandi minimal 8 karakter.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _authenticate_database(username: str, password: str) -> UserContext | None:
    if not table_exists("app_users"):
        return None
    db = get_db()
    if db is None:
        return None
    try:
        response = (
            db.table("app_users")
            .select("id,username,full_name,role,password_hash,assigned_kanwil,assigned_upt,aktif,deleted_at")
            .eq("username", username.casefold())
            .eq("aktif", True)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return None
        db.table("app_users").update(
            {"last_login": datetime.now(timezone.utc).isoformat()}
        ).eq("id", row["id"]).execute()
        return UserContext(
            id=str(row["id"]),
            username=row["username"],
            full_name=row.get("full_name") or row["username"],
            role=normalize_role(row.get("role") or "executive_viewer"),
            assigned_kanwil=row.get("assigned_kanwil") or "",
            assigned_upt=row.get("assigned_upt") or "",
        )
    except Exception:
        return None


def _has_active_database_super_admin() -> bool:
    if not table_exists("app_users"):
        return False
    db = get_db()
    if db is None:
        return False
    try:
        response = (
            db.table("app_users")
            .select("id")
            .eq("role", "super_admin")
            .eq("aktif", True)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception:
        return False


def authenticate(username: str, password: str) -> UserContext | None:
    clean_username = (username or "admin").strip().casefold()
    user = _authenticate_database(clean_username, password)
    if user:
        return user
    cfg = get_config()
    bootstrap_allowed = clean_username == "admin" and not _has_active_database_super_admin()
    if cfg.access_code and password == cfg.access_code and bootstrap_allowed:
        return UserContext(
            id="legacy-super-admin",
            username="admin",
            full_name="Administrator SIMBERPAS",
            role="super_admin",
            legacy=True,
        )
    return None


def render_login() -> None:
    st.markdown(
        """
        <div class="sim-login-wrap">
            <div class="sim-login-logo">🏛️</div>
            <div class="sim-login-title">SIMBERPAS</div>
            <div class="sim-login-subtitle">
                Executive Dashboard Sistem Monitoring Berita Pemasyarakatan.
                Masuk menggunakan akun yang telah diberikan administrator.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 1.25, 1])
    with center:
        with st.form("login_form"):
            username = st.text_input("Nama pengguna", value="admin")
            password = st.text_input("Kata sandi / kode akses", type="password")
            submitted = st.form_submit_button("MASUK", type="primary", use_container_width=True)
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state[SESSION_KEY] = user
                log_action("login", "session", actor_username=user.username, actor_role=user.role)
                st.rerun()
            log_action(
                "login_failed",
                "session",
                actor_username=(username or "unknown").strip().casefold(),
                actor_role="unknown",
            )
            st.error("Nama pengguna atau kata sandi tidak sesuai.")
        if not table_exists("app_users"):
            st.caption(
                "Mode kompatibilitas aktif: gunakan ACCESS_CODE lama. Jalankan migration SQL terbaru untuk akun bertingkat."
            )


def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str,
    assigned_kanwil: str = "",
    assigned_upt: str = "",
) -> str:
    if not table_exists("app_users"):
        raise RuntimeError("Tabel app_users belum tersedia. Jalankan migration SQL terbaru.")
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    clean_username = username.strip().casefold()
    if len(clean_username) < 3:
        raise ValueError("Nama pengguna minimal 3 karakter.")
    role = normalize_role(role)
    if role not in ROLE_LABELS:
        raise ValueError("Peran pengguna tidak valid.")
    user_id = str(uuid.uuid4())
    payload = {
        "id": user_id,
        "username": clean_username,
        "password_hash": _hash_password(password),
        "full_name": full_name.strip() or clean_username,
        "role": role,
        "assigned_kanwil": None,
        "assigned_upt": None,
        "aktif": True,
        "deleted_at": None,
        "deleted_by": None,
    }
    db.table("app_users").insert(payload).execute()
    clear_data_cache()
    return user_id


def update_user_profile(
    user_id: str,
    full_name: str,
    role: str,
    assigned_kanwil: str = "",
    assigned_upt: str = "",
) -> None:
    role = normalize_role(role)
    if role not in ROLE_LABELS:
        raise ValueError("Peran pengguna tidak valid.")
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    payload = {
        "full_name": full_name.strip(),
        "role": role,
        "assigned_kanwil": None,
        "assigned_upt": None,
    }
    db.table("app_users").update(payload).eq("id", user_id).execute()
    clear_data_cache()


def reset_password(user_id: str, new_password: str) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    db.table("app_users").update(
        {
            "password_hash": _hash_password(new_password),
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", user_id).execute()
    clear_data_cache()


def set_user_active(user_id: str, active: bool) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    if not active:
        response = db.table("app_users").select("role").eq("id", user_id).limit(1).execute()
        rows = response.data or []
        target_role = normalize_role(rows[0].get("role")) if rows else ""
        if target_role == "super_admin" and active_super_admin_count() <= 1:
            raise ValueError("Administrator Utama Sistem terakhir tidak dapat dinonaktifkan.")
    db.table("app_users").update({"aktif": bool(active)}).eq("id", user_id).execute()
    clear_data_cache()


def active_super_admin_count() -> int:
    db = get_db()
    if db is None or not table_exists("app_users"):
        return 0
    response = (
        db.table("app_users")
        .select("id", count="exact")
        .eq("role", "super_admin")
        .eq("aktif", True)
        .is_("deleted_at", "null")
        .execute()
    )
    return int(response.count or len(response.data or []))


def archive_user(user_id: str, deleted_by: str, target_role: str = "") -> None:
    if target_role == "super_admin" and active_super_admin_count() <= 1:
        raise ValueError("Super Admin terakhir tidak dapat diarsipkan.")
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    db.table("app_users").update(
        {
            "aktif": False,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": deleted_by,
        }
    ).eq("id", user_id).execute()
    clear_data_cache()


def restore_user(user_id: str) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    db.table("app_users").update(
        {"aktif": True, "deleted_at": None, "deleted_by": None}
    ).eq("id", user_id).execute()
    clear_data_cache()
