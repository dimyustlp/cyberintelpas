from __future__ import annotations

import pandas as pd
import streamlit as st

from components.layout import page_header, section_header
from services.access_control import ROLE_LABELS, require_permission, role_label
from services.audit_service import log_action
from services.auth_service import (
    archive_user,
    create_user,
    reset_password,
    restore_user,
    set_user_active,
    update_user_profile,
)
from services.database import fetch_all, table_exists

admin = require_permission("manage_users")
page_header(
    "Manajemen Pengguna",
    "Kelola empat peran internal pusat, kata sandi, status aktif, arsip, dan pemulihan akun.",
    "Identity & Access Management",
)

if not table_exists("app_users"):
    st.error("Tabel app_users belum tersedia. Jalankan migration SQL terbaru pada Supabase SQL Editor.")
    st.stop()

with st.expander("Empat peran resmi SIMBERPAS", expanded=True):
    st.markdown(
        """
        - **Administrator Utama Sistem:** seluruh sistem, pengguna, konfigurasi, koordinat, audit, input, analisis, dan verifikasi.
        - **Analis Pemberitaan Strategis:** input, analisis, koreksi, telaah, verifikasi, Warning News, peta, dan laporan.
        - **Operator Akuisisi Data Berita:** input sumber dan bukti, memperbaiki data yang dikembalikan, tanpa kewenangan analisis/verifikasi.
        - **Pimpinan Eksekutif:** dashboard, Warning News, peta, AI Assistant, data terverifikasi, dan laporan secara baca-saja.
        """
    )

section_header("Tambah Pengguna", "Buat akun baru sesuai fungsi kerja internal pusat.")
with st.form("create_user_form"):
    c1, c2 = st.columns(2)
    username = c1.text_input("Nama pengguna")
    full_name = c2.text_input("Nama lengkap")
    role = c1.selectbox("Peran", list(ROLE_LABELS), format_func=lambda x: ROLE_LABELS[x])
    password = c2.text_input("Kata sandi awal", type="password")
    submitted = st.form_submit_button("BUAT PENGGUNA", type="primary", use_container_width=True)

if submitted:
    try:
        new_id = create_user(username, password, full_name, role)
        log_action(
            "create", "app_users", new_id, admin.username, admin.role,
            {"username": username.strip().casefold(), "role": role},
        )
        st.success("Pengguna berhasil dibuat.")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

section_header("Daftar Pengguna", "Pilih akun untuk mengubah profil, reset kata sandi, menonaktifkan, atau mengarsipkan.")
show_archived = st.checkbox("Tampilkan akun yang sudah diarsipkan", value=False)
users = pd.DataFrame(
    fetch_all(
        "app_users",
        "id,username,full_name,role,aktif,last_login,created_at,updated_at,deleted_at,deleted_by,password_changed_at",
        order_by="created_at",
        desc=True,
    )
)
if users.empty:
    st.info("Belum ada pengguna.")
    st.stop()

if not show_archived and "deleted_at" in users.columns:
    users = users[users["deleted_at"].isna()]

users["Peran"] = users["role"].map(role_label)
users["Status"] = users.apply(
    lambda row: "Diarsipkan" if pd.notna(row.get("deleted_at")) else ("Aktif" if bool(row.get("aktif")) else "Nonaktif"),
    axis=1,
)
event = st.dataframe(
    users[["username", "full_name", "Peran", "Status", "last_login", "created_at"]],
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
)
selected = event.selection.rows if event and hasattr(event, "selection") else []
if not selected:
    st.caption("Pilih satu pengguna untuk membuka tindakan akun.")
    st.stop()

row = users.iloc[selected[0]]
user_id = str(row["id"])
is_self = user_id == str(admin.id) or str(row["username"]).casefold() == admin.username.casefold()
is_archived = pd.notna(row.get("deleted_at"))
st.write(f'Pengguna dipilih: **{row["full_name"]}** (`{row["username"]}`)')

if is_archived:
    st.warning(f'Akun diarsipkan oleh {row.get("deleted_by") or "administrator"}.')
    if st.button("Pulihkan Akun", type="primary"):
        restore_user(user_id)
        log_action("restore", "app_users", user_id, admin.username, admin.role, {"username": row["username"]})
        st.success("Akun dipulihkan.")
        st.rerun()
    st.stop()

with st.expander("Ubah Profil dan Peran", expanded=True):
    current_role = str(row.get("role") or "executive_viewer")
    if current_role not in ROLE_LABELS:
        legacy_map = {"admin_pusat": "news_analyst", "admin_kanwil": "news_analyst", "operator_upt": "news_intake", "viewer": "executive_viewer"}
        current_role = legacy_map.get(current_role, "executive_viewer")
    with st.form(f"edit_user_{user_id}"):
        e1, e2 = st.columns(2)
        new_full_name = e1.text_input("Nama lengkap", value=str(row.get("full_name") or ""))
        new_role = e2.selectbox(
            "Peran",
            list(ROLE_LABELS),
            index=list(ROLE_LABELS).index(current_role),
            format_func=lambda x: ROLE_LABELS[x],
            disabled=is_self and current_role == "super_admin",
        )
        save_profile = st.form_submit_button("SIMPAN PERUBAHAN", type="primary", use_container_width=True)
    if save_profile:
        try:
            update_user_profile(user_id, new_full_name, new_role)
            log_action("update_profile", "app_users", user_id, admin.username, admin.role, {"role": new_role})
            st.success("Profil pengguna diperbarui.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

with st.expander("Reset Kata Sandi"):
    with st.form(f"reset_password_{user_id}"):
        new_password = st.text_input("Kata sandi baru", type="password")
        repeat_password = st.text_input("Ulangi kata sandi baru", type="password")
        reset_submit = st.form_submit_button("RESET KATA SANDI")
    if reset_submit:
        if new_password != repeat_password:
            st.error("Pengulangan kata sandi tidak sama.")
        else:
            try:
                reset_password(user_id, new_password)
                log_action("reset_password", "app_users", user_id, admin.username, admin.role, {"username": row["username"]})
                st.success("Kata sandi berhasil direset.")
            except Exception as exc:
                st.error(str(exc))

with st.expander("Status Aktif"):
    new_status = not bool(row["aktif"])
    label = "Aktifkan Pengguna" if new_status else "Nonaktifkan Pengguna"
    disabled = is_self and not new_status
    if disabled:
        st.warning("Akun yang sedang digunakan tidak dapat dinonaktifkan.")
    if st.button(label, type="primary", disabled=disabled, key=f"toggle_{user_id}"):
        try:
            set_user_active(user_id, new_status)
            log_action("update_status", "app_users", user_id, admin.username, admin.role, {"aktif": new_status})
            st.success("Status akun diperbarui.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

with st.expander("Arsipkan Akun"):
    st.warning("Arsip bukan hapus permanen. Riwayat akun dan audit tetap dipertahankan serta dapat dipulihkan.")
    if is_self:
        st.info("Akun yang sedang digunakan tidak dapat diarsipkan.")
    confirm_name = st.text_input("Ketik nama pengguna untuk konfirmasi", key=f"confirm_archive_{user_id}")
    can_archive = not is_self and confirm_name.strip().casefold() == str(row["username"]).casefold()
    if st.button("ARSIPKAN AKUN", disabled=not can_archive, key=f"archive_{user_id}"):
        try:
            archive_user(user_id, admin.username, str(row.get("role") or ""))
            log_action("archive", "app_users", user_id, admin.username, admin.role, {"username": row["username"]})
            st.success("Akun berhasil diarsipkan.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
