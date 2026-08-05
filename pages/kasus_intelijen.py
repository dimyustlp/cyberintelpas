from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.case_service import (
    ACTUALITY_STATUSES,
    CASE_STATUSES,
    create_case,
    create_field_assignment,
    fetch_cases,
    fetch_news_candidates,
    link_news_to_case,
    update_case,
)
from services.cyber_db import fetch_all

user = current_user()
if user is None or not (has_permission(user, "view_cases") or has_permission(user, "manage_cases")):
    st.error("Anda tidak memiliki akses ke Kasus Intelijen.")
    st.stop()

st.title("Kasus Intelijen Pemberitaan")
st.caption("Satu kasus dapat memiliki banyak publikasi dari link dan media yang berbeda.")

cases = fetch_cases()
case_df = pd.DataFrame(cases)

if has_permission(user, "manage_cases"):
    with st.expander("Buat kasus baru", expanded=not cases):
        with st.form("create_case_form"):
            title = st.text_input("Judul kasus")
            c1, c2, c3 = st.columns(3)
            with c1:
                primary_upt = st.text_input("UPT utama", value="Belum Teridentifikasi")
            with c2:
                issue_type = st.selectbox("Jenis isu", ["Keamanan", "Narkotika", "Pelayanan", "Integritas", "Kapasitas", "Hak Warga Binaan", "Lainnya"])
            with c3:
                priority = st.selectbox("Prioritas", ["Rendah", "Sedang", "Tinggi", "Kritis"], index=1)
            actuality_status = st.selectbox("Aktualitas", ACTUALITY_STATUSES, index=3)
            summary = st.text_area("Ringkasan kasus", height=120)
            submitted = st.form_submit_button("Buat Kasus", type="primary")
        if submitted:
            try:
                created = create_case({
                    "title": title,
                    "primary_upt": primary_upt,
                    "issue_type": issue_type,
                    "priority": priority,
                    "actuality_status": actuality_status,
                    "summary": summary,
                }, user)
                st.success(f"Kasus {created.get('case_number', '')} berhasil dibuat.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

if case_df.empty:
    st.info("Belum ada kasus intelijen.")
    st.stop()

show_cols = [column for column in [
    "case_number", "title", "primary_upt", "status", "priority", "article_count",
    "media_count", "negative_count", "highest_urgency", "actuality_status", "updated_at"
] if column in case_df.columns]
st.dataframe(case_df[show_cols], use_container_width=True, hide_index=True)

labels = {
    f"{row.get('case_number', '-')}: {row.get('title', 'Tanpa judul')}": str(row.get("id"))
    for row in cases
}
selected_label = st.selectbox("Pilih kasus untuk dikelola", list(labels))
case_id = labels[selected_label]
selected = next(row for row in cases if str(row.get("id")) == case_id)

with st.container(border=True):
    st.markdown(f"### {selected.get('case_number', '')} · {selected.get('title', '')}")
    st.write(selected.get("summary") or "Belum ada ringkasan.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Publikasi", selected.get("article_count", 0))
    m2.metric("Media", selected.get("media_count", 0))
    m3.metric("Negatif", selected.get("negative_count", 0))
    m4.metric("Urgensi", selected.get("highest_urgency", "Rendah"))

if has_permission(user, "manage_cases"):
    tab1, tab2, tab3 = st.tabs(["Perbarui Kasus", "Hubungkan Berita", "Penugasan Lapangan"])

    with tab1:
        with st.form("update_case_form"):
            new_status = st.selectbox("Status kasus", CASE_STATUSES, index=CASE_STATUSES.index(selected.get("status")) if selected.get("status") in CASE_STATUSES else 0)
            new_priority = st.selectbox("Prioritas kasus", ["Rendah", "Sedang", "Tinggi", "Kritis"], index=["Rendah", "Sedang", "Tinggi", "Kritis"].index(selected.get("priority")) if selected.get("priority") in ["Rendah", "Sedang", "Tinggi", "Kritis"] else 1)
            new_actuality = st.selectbox("Aktualitas", ACTUALITY_STATUSES, index=ACTUALITY_STATUSES.index(selected.get("actuality_status")) if selected.get("actuality_status") in ACTUALITY_STATUSES else 3)
            new_summary = st.text_area("Ringkasan", value=selected.get("summary") or "", height=140)
            save_case = st.form_submit_button("Simpan Perubahan", type="primary")
        if save_case:
            update_case(case_id, {
                "status": new_status,
                "priority": new_priority,
                "actuality_status": new_actuality,
                "summary": new_summary,
            }, user)
            st.success("Kasus diperbarui.")
            st.rerun()

    with tab2:
        news = fetch_news_candidates()
        linked_rows = fetch_all("case_news", "berita_id", filters=[("eq", "case_id", case_id)], max_rows=5000)
        linked_ids = {str(row.get("berita_id")) for row in linked_rows}
        news_options = {}
        for row in news:
            news_id = str(row.get("id"))
            if news_id in linked_ids:
                continue
            label = f"{row.get('nama_upt', 'Belum Teridentifikasi')} · {row.get('media', 'Tidak diketahui')} · {row.get('judul', 'Tanpa judul')}"
            news_options[label[:220]] = news_id
        selected_news = st.multiselect("Pilih publikasi yang membahas kasus yang sama", list(news_options))
        if st.button("Hubungkan Publikasi", type="primary", disabled=not selected_news):
            count = link_news_to_case(case_id, [news_options[label] for label in selected_news], user)
            st.success(f"{count} publikasi berhasil dihubungkan.")
            st.rerun()

        if linked_ids:
            linked_news = [row for row in news if str(row.get("id")) in linked_ids]
            st.caption(f"Publikasi terhubung: {len(linked_news)}")
            st.dataframe(pd.DataFrame(linked_news), use_container_width=True, hide_index=True)

    with tab3:
        field_users = fetch_all("app_users", "username,full_name,role,aktif", filters=[("eq", "aktif", True)], max_rows=1000)
        officers = {
            f"{row.get('full_name') or row.get('username')} ({row.get('username')})": row.get("username")
            for row in field_users if row.get("role") in {"field_verification_officer", "petugas_verifikasi_lapangan"}
        }
        if not officers:
            st.warning("Belum ada akun Petugas Verifikasi Lapangan. Administrator perlu menetapkan peran pengguna terlebih dahulu.")
        with st.form("field_assignment_form"):
            officer_label = st.selectbox("Petugas yang ditugaskan", list(officers) if officers else ["Belum tersedia"])
            instruction = st.text_area("Instruksi dan ruang lingkup verifikasi", height=120)
            questions_text = st.text_area("Pertanyaan verifikasi, satu baris satu pertanyaan", height=120)
            due_date = st.date_input("Batas waktu", value=date.today())
            due_time = st.time_input("Jam batas waktu", value=time(17, 0))
            assignment_priority = st.selectbox("Prioritas penugasan", ["Rendah", "Sedang", "Tinggi", "Kritis"], index=2)
            assign = st.form_submit_button("Kirim Penugasan", type="primary", disabled=not officers)
        if assign:
            due_at = datetime.combine(due_date, due_time, tzinfo=WIB).isoformat()
            created = create_field_assignment({
                "case_id": case_id,
                "assigned_to": officers[officer_label],
                "instruction": instruction,
                "verification_questions": [line.strip() for line in questions_text.splitlines() if line.strip()],
                "due_at": due_at,
                "priority": assignment_priority,
            }, user)
            st.success(f"Penugasan {created.get('assignment_number', '')} berhasil dibuat.")
            st.rerun()
