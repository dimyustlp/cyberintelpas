from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from services.audit_service import log_action
from components.layout import page_header, section_header
from services.access_control import require_permission
from services.database import fetch_audit_df
from services.export_service import excel_bytes

user = require_permission("view_audit")
page_header(
    "Audit Aktivitas",
    "Telusuri login, perubahan berita, verifikasi, pengguna, lampiran, koordinat, dan ekspor data.",
    "Accountability & Audit",
)

audit = fetch_audit_df()
if audit.empty:
    st.info("Audit log belum tersedia atau belum memiliki data.")
    st.stop()

for col in ["actor_username", "actor_role", "action", "entity", "entity_id"]:
    if col not in audit.columns:
        audit[col] = ""
audit["created_at"] = pd.to_datetime(audit.get("created_at"), errors="coerce", utc=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total aktivitas", int(len(audit)))
k2.metric("Pengguna aktif di log", int(audit["actor_username"].nunique()))
k3.metric("Perubahan berita", int(audit["entity"].eq("berita").sum()))
k4.metric("Login gagal", int(audit["action"].eq("login_failed").sum()))

with st.container(border=True):
    f1, f2, f3, f4 = st.columns(4)
    actors = f1.multiselect("Pengguna", sorted(audit["actor_username"].dropna().astype(str).unique().tolist()))
    actions = f2.multiselect("Aksi", sorted(audit["action"].dropna().astype(str).unique().tolist()))
    entities = f3.multiselect("Objek", sorted(audit["entity"].dropna().astype(str).unique().tolist()))
    roles = f4.multiselect("Peran", sorted(audit["actor_role"].dropna().astype(str).unique().tolist()))
    q = st.text_input("Cari ID objek atau metadata")

filtered = audit.copy()
if actors:
    filtered = filtered[filtered["actor_username"].isin(actors)]
if actions:
    filtered = filtered[filtered["action"].isin(actions)]
if entities:
    filtered = filtered[filtered["entity"].isin(entities)]
if roles:
    filtered = filtered[filtered["actor_role"].isin(roles)]
if q:
    metadata_text = filtered.get("metadata", pd.Series(index=filtered.index, dtype=object)).map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x))
    mask = filtered["entity_id"].astype(str).str.contains(q, case=False, na=False) | metadata_text.str.contains(q, case=False, na=False)
    filtered = filtered[mask]

section_header("Riwayat Aktivitas", f"{len(filtered)} aktivitas ditemukan.")
st.download_button(
    "Unduh audit ke Excel",
    data=excel_bytes(filtered, "Audit"),
    file_name="SIMBERPAS_Audit_Aktivitas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    on_click=log_action,
    args=("export", "audit_log", "filter", user.username, user.role, {"rows": len(filtered), "format": "xlsx"}),
)

display = filtered.copy()
if "metadata" in display.columns:
    display["metadata"] = display["metadata"].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x))
st.dataframe(
    display[[c for c in ["created_at", "actor_username", "actor_role", "action", "entity", "entity_id", "metadata"] if c in display.columns]],
    width="stretch",
    hide_index=True,
    column_config={"created_at": st.column_config.DatetimeColumn("Waktu", format="DD-MM-YYYY HH:mm:ss")},
)
