from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.case_service import action_items_for_user, actor_name, fetch_action_items, update_action_item
from services.role_catalog import canonical_role

user = current_user()
if user is None or not has_permission(user, "view_action_items"):
    st.error("Anda tidak memiliki akses ke Tindak Lanjut.")
    st.stop()

st.title("Tindak Lanjut dan Reminder")
st.caption("Menampilkan tugas yang menjadi tanggung jawab pengguna atau perannya, lengkap dengan tenggat dan progres.")

role = canonical_role(user.get("role") if isinstance(user, dict) else getattr(user, "role", ""))
username = actor_name(user)
all_rows = has_permission(user, "manage_action_items")
items = fetch_action_items() if all_rows else action_items_for_user(user)

if not items:
    st.info("Belum ada tugas tindak lanjut.")
    st.stop()

now = datetime.now(timezone.utc)
for row in items:
    due = pd.to_datetime(row.get("due_at"), errors="coerce", utc=True)
    row["Tenggat"] = due.tz_convert("Asia/Jakarta").strftime("%d-%m-%Y %H:%M WIB") if pd.notna(due) else "Tidak ditetapkan"
    row["Kondisi"] = (
        "Selesai" if row.get("status") == "Selesai"
        else "Terlambat" if pd.notna(due) and due.to_pydatetime() < now
        else "Aktif"
    )

item_df = pd.DataFrame(items)
show_cols = [column for column in [
    "title", "assigned_role", "assigned_to", "priority", "status", "progress_percent", "Tenggat", "Kondisi"
] if column in item_df.columns]
st.dataframe(item_df[show_cols], use_container_width=True, hide_index=True)

active = sum(row.get("status") not in {"Selesai", "Dibatalkan"} for row in items)
overdue = sum(row.get("Kondisi") == "Terlambat" for row in items)
completed = sum(row.get("status") == "Selesai" for row in items)
c1, c2, c3 = st.columns(3)
c1.metric("Tugas aktif", active)
c2.metric("Terlambat", overdue)
c3.metric("Selesai", completed)

labels = {
    f"{row.get('priority', 'Sedang')} · {row.get('title', 'Tugas')} · {row.get('Tenggat')}": str(row.get("id"))
    for row in items
}
selected_label = st.selectbox("Pilih tugas", list(labels))
item_id = labels[selected_label]
item = next(row for row in items if str(row.get("id")) == item_id)

with st.container(border=True):
    st.markdown(f"### {item.get('title', 'Tugas')}")
    st.write(item.get("description") or "Tidak ada uraian tambahan.")
    st.caption(
        f"Penanggung jawab: {item.get('assigned_to') or item.get('assigned_role') or 'Belum ditetapkan'} | "
        f"Prioritas: {item.get('priority', 'Sedang')} | Tenggat: {item.get('Tenggat')}"
    )

can_update = has_permission(user, "update_action_items") or has_permission(user, "manage_action_items")
assigned_to_user = item.get("assigned_to") == username or item.get("assigned_role") == role
if can_update and (all_rows or assigned_to_user):
    status_options = ["Belum Dimulai", "Dalam Proses", "Menunggu Pihak Lain", "Tertunda", "Selesai", "Dibatalkan"]
    current_status = item.get("status") if item.get("status") in status_options else "Belum Dimulai"
    new_status = st.selectbox("Status terbaru", status_options, index=status_options.index(current_status))
    progress = st.slider("Progres", 0, 100, int(item.get("progress_percent") or 0), step=5)
    if st.button("Simpan Progres", type="primary"):
        update_action_item(item_id, status=new_status, progress_percent=progress, user=user)
        st.success("Progres tindak lanjut diperbarui.")
        st.rerun()
else:
    st.info("Tugas ini ditampilkan sebagai informasi. Perubahan hanya dapat dilakukan oleh penanggung jawab atau pengelola tindak lanjut.")
