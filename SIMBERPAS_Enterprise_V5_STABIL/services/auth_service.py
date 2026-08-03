from __future__ import annotations

import uuid
from datetime import datetime, timezone

import bcrypt
import streamlit as st

from services.access_control import UserContext
from services.audit_service import log_action
from services.config import get_config
from services.database import get_db, table_exists

SESSION_KEY = "simberpas_user"


def init_auth_state() -> None:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = None


def current_user() -> UserContext | None:
    value = st.session_state.get(SESSION_KEY)
    if isinstance(value, UserContext):
        return value
    if isinstance(value, dict):
        allowed = {
            "id", "username", "full_name", "role",
            "assigned_kanwil", "assigned_upt", "legacy"
        }
        clean = {key: value.get(key) for key in allowed if key in value}
        clean.setdefault("id", "session-user")
        clean.setdefault("username", "admin")
        clean.setdefault("full_name", clean["username"])
        clean.setdefault("role", "viewer")
        clean.setdefault("assigned_kanwil", "")
        clean.setdefault("assigned_upt", "")
        clean.setdefault("legacy", False)
        try:
            return UserContext(**clean)
        except (TypeError, ValueError):
            st.session_state[SESSION_KEY] = None
            return None
    return None


def logout() -> None:
    user = current_user()
    if user:
        log_action("logout", "session", actor_username=user.username, actor_role=user.role)
    st.session_state.clear()
    st.rerun()


def _authenticate_database(username: str, password: str) -> UserContext | None:
    if not table_exists("app_users"):
        return None
    db = get_db()
    if db is None:
        return None
    try:
        response = (
            db.table("app_users")
            .select("id,username,full_name,role,password_hash,assigned_kanwil,assigned_upt,aktif")
            .eq("username", username.casefold())
            .eq("aktif", True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return None
        db.table("app_users").update({"last_login": datetime.now(timezone.utc).isoformat()}).eq("id", row["id"]).execute()
        return UserContext(
            id=str(row["id"]),
            username=row["username"],
            full_name=row.get("full_name") or row["username"],
            role=row.get("role") or "viewer",
            assigned_kanwil=row.get("assigned_kanwil") or "",
            assigned_upt=row.get("assigned_upt") or "",
        )
    except Exception:
        return None


def authenticate(username: str, password: str) -> UserContext | None:
    clean_username = (username or "admin").strip().casefold()
    user = _authenticate_database(clean_username, password)
    if user:
        return user
    cfg = get_config()
    if cfg.access_code and password == cfg.access_code:
        return UserContext(
            id="legacy-super-admin",
            username=clean_username or "admin",
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
    left, center, right = st.columns([1, 1.25, 1])
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
            st.error("Nama pengguna atau kata sandi tidak sesuai.")
        if not table_exists("app_users"):
            st.caption("Mode kompatibilitas aktif: gunakan kode ACCESS_CODE lama. Setelah migration SQL dijalankan, akun bertingkat dapat dibuat.")


def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str,
    assigned_kanwil: str = "",
    assigned_upt: str = "",
) -> None:
    if not table_exists("app_users"):
        raise RuntimeError("Tabel app_users belum tersedia. Jalankan migration_v4_enterprise.sql terlebih dahulu.")
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    clean_username = username.strip().casefold()
    if len(clean_username) < 3:
        raise ValueError("Nama pengguna minimal 3 karakter.")
    if len(password) < 8:
        raise ValueError("Kata sandi minimal 8 karakter.")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    payload = {
        "id": str(uuid.uuid4()),
        "username": clean_username,
        "password_hash": password_hash,
        "full_name": full_name.strip() or clean_username,
        "role": role,
        "assigned_kanwil": assigned_kanwil.strip() or None,
        "assigned_upt": assigned_upt.strip() or None,
        "aktif": True,
    }
    db.table("app_users").insert(payload).execute()


def set_user_active(user_id: str, active: bool) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    db.table("app_users").update({"aktif": active}).eq("id", user_id).execute()
