from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.case_service import (
    create_action_item,
    decide_case,
    fetch_case_analyses,
    fetch_cases,
    fetch_recommendations,
)
from services.cyber_db import fetch_all
from services.role_catalog import ROLE_DEFINITIONS

WIB = ZoneInfo("Asia/Jakarta")

user = current_user()
if user is None or not has_permission(user, "decide_cases"):
    st.error("Halaman ini hanya tersedia untuk Pimpinan Pengambil Keputusan.")
    st.stop()

st.title("Keputusan dan Disposisi Pimpinan")
st.caption("Membaca fakta, menetapkan keputusan, lalu mengubah rekomendasi menjadi tugas yang terukur.")

cases = fetch_cases()
if not cases:
    st.info("Belum ada kasus intelijen.")
    st.stop()

priority_cases = [row for row in cases if row.get("status") in {
    "Menunggu Keputusan Tindak Lanjut", "Menunggu Keputusan Pimpinan", "Dalam Tindak Lanjut UPT", "Dalam Pemantauan"
}]
working_cases = priority_cases or cases
labels = {
    f"{row.get('case_number', '-')} · {row.get('priority', 'Sedang')} · {row.get('primary_upt', 'UPT')} · {row.get('title', 'Kasus')}": str(row.get("id"))
    for row in working_cases
}
selected_label = st.selectbox("Pilih kasus", list(labels))
case_id = labels[selected_label]
case = next(row for row in working_cases if str(row.get("id")) == case_id)
analyses = fetch_case_analyses(case_id)
recommendations = fetch_recommendations(case_id)
latest_analysis = analyses[0] if analyses else {}

with st.container(border=True):
    st.markdown(f"### {case.get('case_number', '')} · {case.get('title', '')}")
    st.write(case.get("summary") or "Belum ada ringkasan kasus.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Publikasi", case.get("article_count", 0))
    c2.metric("Media", case.get("media_count", 0))
    c3.metric("Negatif", case.get("negative_count", 0))
    c4.metric("Urgensi", case.get("highest_urgency", "Rendah"))
    c5.metric("Status", case.get("status", "Terdeteksi"))

left, right = st.columns(2)
with left:
    st.subheader("Analisis akhir")
    st.write(latest_analysis.get("final_analysis") or "Analisis akhir belum tersedia.")
    st.caption(
        f"Validitas: {latest_analysis.get('information_validity', 'Belum dinilai')} | "
        f"Dampak reputasi: {latest_analysis.get('reputation_impact', 'Belum dinilai')} | "
        f"Risiko eskalasi: {latest_analysis.get('media_escalation_risk', 'Belum dinilai')}"
    )
with right:
    st.subheader("Fakta lapangan")
    st.write(latest_analysis.get("field_facts") or "Fakta lapangan belum dirangkum dalam analisis.")
    st.caption(f"Penilaian tindak lanjut UPT: {latest_analysis.get('follow_up_assessment', 'Belum Dapat Dinilai')}")

st.subheader("Rekomendasi yang diajukan")
if not recommendations:
    st.info("Belum ada rekomendasi untuk kasus ini.")
    recommendation_options: dict[str, str] = {}
else:
    rec_df = pd.DataFrame(recommendations)
    show_cols = [column for column in [
        "recommendation_type", "recommendation", "responsible_party", "priority", "due_at", "status"
    ] if column in rec_df.columns]
    st.dataframe(rec_df[show_cols], use_container_width=True, hide_index=True)
    recommendation_options = {
        f"{row.get('recommendation_type', 'Rekomendasi')} · {row.get('recommendation', '')[:140]}": str(row.get("id"))
        for row in recommendations
    }

selected_recommendations = st.multiselect(
    "Rekomendasi yang diputuskan",
    list(recommendation_options),
    default=list(recommendation_options),
    help="Kosong berarti seluruh rekomendasi pada kasus ini mengikuti keputusan.",
)
decision = st.selectbox("Keputusan", ["Disetujui", "Perlu Penyempurnaan", "Ditolak", "Dipantau", "Selesai"])
decision_note = st.text_area("Arahan atau catatan keputusan", height=130)
confirm = st.checkbox("Saya telah membaca ringkasan kasus, analisis, dan rekomendasi.")
if st.button("Simpan Keputusan", type="primary", disabled=not confirm):
    try:
        decide_case(
            case_id,
            decision,
            decision_note,
            user,
            [recommendation_options[label] for label in selected_recommendations],
        )
        st.success("Keputusan pimpinan berhasil dicatat.")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

decision_history = fetch_all("case_decisions", "decision,decision_note,decided_by,decided_at", filters=[("eq", "case_id", case_id)], order_by="decided_at", desc=True, max_rows=100)
if decision_history:
    with st.expander("Riwayat keputusan kasus"):
        st.dataframe(pd.DataFrame(decision_history), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Buat Disposisi atau Tugas Tindak Lanjut")
active_users = fetch_all("app_users", "username,full_name,role,aktif", filters=[("eq", "aktif", True)], order_by="full_name", max_rows=2000)
user_options = {
    f"{row.get('full_name') or row.get('username')} · {row.get('username')}": str(row.get("username"))
    for row in active_users
}
role_options = {role.name: role.code for role in ROLE_DEFINITIONS if role.code != "executive_decision_maker"}

with st.form("executive_action_item_form"):
    task_title = st.text_input("Judul tugas")
    task_description = st.text_area("Uraian tugas", height=120)
    c1, c2 = st.columns(2)
    with c1:
        assigned_role_name = st.selectbox("Peran penanggung jawab", list(role_options))
        assigned_user_label = st.selectbox("Pengguna penanggung jawab", ["Tidak ditetapkan"] + list(user_options))
    with c2:
        task_priority = st.selectbox("Prioritas", ["Rendah", "Sedang", "Tinggi", "Kritis"], index=2)
        due_date = st.date_input("Tenggat tanggal", value=date.today())
        due_time = st.time_input("Tenggat waktu", value=time(17, 0))
    create_task = st.form_submit_button("Buat Tugas", type="primary")

if create_task:
    if not task_title.strip():
        st.warning("Judul tugas wajib diisi.")
    else:
        due_at = datetime.combine(due_date, due_time, tzinfo=WIB).isoformat()
        row = create_action_item({
            "case_id": case_id,
            "title": task_title,
            "description": task_description,
            "assigned_role": role_options[assigned_role_name],
            "assigned_to": "" if assigned_user_label == "Tidak ditetapkan" else user_options[assigned_user_label],
            "priority": task_priority,
            "due_at": due_at,
        }, user)
        st.success(f"Tugas tindak lanjut berhasil dibuat dengan ID {row.get('id', '')}.")
