from __future__ import annotations

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.cyber_db import fetch_all, update_rows
from services.role_catalog import ROLE_DEFINITIONS, ROLE_OPTIONS, role_name
from services.v6_audit_service import record_audit

user = current_user()
if user is None or not has_permission(user, "manage_users"):
    st.error("Anda tidak memiliki akses ke Manajemen Peran.")
    st.stop()

st.title("Manajemen Peran Pengguna")
st.caption("Enam peran CYBER-INTELPAS dipisahkan berdasarkan tugas pokok dan fungsi.")

role_df = pd.DataFrame([
    {
        "Kode": role.code,
        "Nama Peran": role.name,
        "Tupoksi Singkat": role.short_description,
        "Fokus Utama": role.main_focus,
    }
    for role in ROLE_DEFINITIONS
])
st.dataframe(role_df, use_container_width=True, hide_index=True)

users = fetch_all("app_users", "id,username,full_name,role,aktif,last_login", order_by="full_name", max_rows=2000)
if not users:
    st.info("Belum ada pengguna pada tabel app_users.")
    st.stop()

for row in users:
    row["role_name"] = role_name(row.get("role"))
user_df = pd.DataFrame(users)
st.subheader("Pengguna Aktif")
st.dataframe(user_df[["username", "full_name", "role_name", "aktif", "last_login"]], use_container_width=True, hide_index=True)

labels = {f"{row.get('full_name')} ({row.get('username')}) · {row.get('role_name')}": str(row.get("id")) for row in users}
selected_label = st.selectbox("Pilih pengguna", list(labels))
selected_id = labels[selected_label]
selected_user = next(row for row in users if str(row.get("id")) == selected_id)
role_names = list(ROLE_OPTIONS)
current_name = role_name(selected_user.get("role"))
new_role_name = st.selectbox("Peran baru", role_names, index=role_names.index(current_name) if current_name in role_names else 0)
old_role = str(selected_user.get("role") or "")
new_role = ROLE_OPTIONS[new_role_name]
active_admins = [row for row in users if row.get("aktif") and role_name(row.get("role")) == "Administrator Utama CYBER-INTELPAS"]
last_admin_blocked = old_role == "super_admin" and new_role != "super_admin" and len(active_admins) <= 1
if last_admin_blocked:
    st.error("Peran Administrator Utama terakhir tidak dapat diubah. Tetapkan Administrator Utama lain terlebih dahulu.")
if st.button("Simpan Peran", type="primary", disabled=last_admin_blocked or old_role == new_role):
    update_rows("app_users", {"role": new_role}, filters=[("eq", "id", selected_id)])
    record_audit(user, "user.role_update", "app_user", selected_id, {"username": selected_user.get("username"), "role_from": old_role, "role_to": new_role})
    st.success("Peran pengguna berhasil diperbarui.")
    st.rerun()
