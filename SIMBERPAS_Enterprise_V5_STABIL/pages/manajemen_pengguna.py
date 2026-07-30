from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import page_header, section_header
from services.access_control import ROLE_LABELS, has_permission
from services.audit_service import log_action
from services.auth_service import create_user, current_user, set_user_active
from services.database import fetch_all, fetch_upt_df, table_exists

admin = current_user()
if admin is None or not (has_permission(admin, "manage_users") or has_permission(admin, "manage_scoped_users")):
    st.error("Anda tidak memiliki hak akses untuk mengelola pengguna.")
    st.stop()
page_header("Manajemen Pengguna", "Kelola akun, peran, dan cakupan akses tanpa membagikan satu kode kepada semua petugas.", "Identity & Access Management")

if not table_exists("app_users"):
    st.error("Tabel app_users belum tersedia. Jalankan sql/migration_v4_enterprise.sql pada Supabase SQL Editor.")
    st.stop()

upt_df = fetch_upt_df()
kanwils = sorted([x for x in upt_df["kanwil"].dropna().astype(str).unique() if x])
upt_names = sorted([x for x in upt_df["nama_upt"].dropna().astype(str).unique() if x])
if has_permission(admin, "manage_scoped_users") and not has_permission(admin, "manage_users"):
    kanwils = [admin.assigned_kanwil] if admin.assigned_kanwil else []
    scoped_upt = upt_df[upt_df["kanwil"] == admin.assigned_kanwil] if admin.assigned_kanwil else upt_df.iloc[0:0]
    upt_names = sorted(scoped_upt["nama_upt"].dropna().astype(str).tolist())

section_header("Tambah Pengguna", "Buat akun baru dengan hak akses sesuai tugas.")
with st.form("create_user_form"):
    c1, c2 = st.columns(2)
    username = c1.text_input("Nama pengguna")
    full_name = c2.text_input("Nama lengkap")
    allowed_roles = list(ROLE_LABELS) if has_permission(admin, "manage_users") else ["operator_upt", "viewer"]
    role = c1.selectbox("Peran", allowed_roles, format_func=lambda x: ROLE_LABELS[x])
    password = c2.text_input("Kata sandi awal", type="password")
    assigned_kanwil = c1.selectbox("Cakupan Kanwil", ([""] + kanwils) if has_permission(admin, "manage_users") else kanwils, index=0 if kanwils or has_permission(admin, "manage_users") else None)
    assigned_upt = c2.selectbox("Cakupan UPT", [""] + upt_names)
    submitted = st.form_submit_button("BUAT PENGGUNA", type="primary", use_container_width=True)
if submitted:
    try:
        create_user(username, password, full_name, role, assigned_kanwil, assigned_upt)
        log_action("create", "app_users", actor_username=admin.username, actor_role=admin.role, metadata={"username": username, "role": role})
        st.success("Pengguna berhasil dibuat.")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

section_header("Daftar Pengguna", "Aktifkan atau nonaktifkan akses akun.")
users = pd.DataFrame(fetch_all("app_users", "id,username,full_name,role,assigned_kanwil,assigned_upt,aktif,last_login,created_at", order_by="created_at", desc=True))
if not users.empty and has_permission(admin, "manage_scoped_users") and not has_permission(admin, "manage_users"):
    users = users[users["assigned_kanwil"].fillna("") == admin.assigned_kanwil]
if users.empty:
    st.info("Belum ada pengguna database. Anda sedang masuk melalui ACCESS_CODE lama.")
else:
    users["Peran"] = users["role"].map(ROLE_LABELS).fillna(users["role"])
    event = st.dataframe(users[["username", "full_name", "Peran", "assigned_kanwil", "assigned_upt", "aktif", "last_login"]], width="stretch", hide_index=True, on_select="rerun", selection_mode="single-row")
    selected = event.selection.rows if event and hasattr(event, "selection") else []
    if selected:
        row = users.iloc[selected[0]]
        st.write(f'Pengguna dipilih: **{row["full_name"]}** ({row["username"]})')
        new_status = not bool(row["aktif"])
        label = "Aktifkan Pengguna" if new_status else "Nonaktifkan Pengguna"
        if st.button(label, type="primary"):
            set_user_active(str(row["id"]), new_status)
            log_action("update_status", "app_users", str(row["id"]), admin.username, admin.role, {"aktif": new_status})
            st.success("Status pengguna diperbarui.")
            st.rerun()
