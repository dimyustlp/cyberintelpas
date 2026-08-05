from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path
from uuid import uuid4

WIB = ZoneInfo("Asia/Jakarta")

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.case_service import (
    FIELD_STATUSES,
    FINDING_CLASSIFICATIONS,
    actor_name,
    fetch_cases,
    fetch_field_assignments,
    submit_field_report,
    update_assignment_status,
)
from services.cyber_db import get_db, insert_row
from services.v6_audit_service import record_audit

user = current_user()
if user is None or not has_permission(user, "view_field_assignments"):
    st.error("Anda tidak memiliki akses ke Verifikasi Lapangan.")
    st.stop()

st.title("Verifikasi dan Tindak Lanjut Lapangan")
st.caption("Catat fakta secara objektif, unggah bukti pendukung, dan hindari kesimpulan yang belum dapat dibuktikan.")

all_rows = has_permission(user, "manage_cases") or has_permission(user, "view_system_health")
assignments = fetch_field_assignments(user, all_rows=all_rows)
cases = {str(row.get("id")): row for row in fetch_cases()}

if not assignments:
    st.info("Belum ada penugasan lapangan untuk akun ini.")
    st.stop()

assignment_df = pd.DataFrame(assignments)
show_cols = [column for column in ["assignment_number", "assigned_to", "priority", "status", "due_at", "created_at"] if column in assignment_df.columns]
st.dataframe(assignment_df[show_cols], use_container_width=True, hide_index=True)

labels = {}
for row in assignments:
    case = cases.get(str(row.get("case_id")), {})
    labels[f"{row.get('assignment_number', '-')} · {case.get('primary_upt', 'UPT')} · {case.get('title', 'Kasus')}"] = str(row.get("id"))
selected_label = st.selectbox("Pilih penugasan", list(labels))
assignment_id = labels[selected_label]
assignment = next(row for row in assignments if str(row.get("id")) == assignment_id)
case = cases.get(str(assignment.get("case_id")), {})

with st.container(border=True):
    st.markdown(f"### {case.get('case_number', '')} · {case.get('title', '')}")
    st.write(case.get("summary") or "Belum ada ringkasan kasus.")
    st.markdown("**Instruksi penugasan**")
    st.write(assignment.get("instruction") or "Tidak ada instruksi tambahan.")
    questions = assignment.get("verification_questions") or []
    if questions:
        st.markdown("**Pertanyaan yang perlu diverifikasi**")
        for item in questions:
            st.markdown(f"- {item}")

status_options = FIELD_STATUSES
current_status = assignment.get("status") if assignment.get("status") in status_options else "Ditugaskan"
new_status = st.selectbox("Status penugasan", status_options, index=status_options.index(current_status))
if new_status != current_status and st.button("Perbarui Status"):
    update_assignment_status(assignment_id, new_status, user)
    st.success("Status penugasan diperbarui.")
    st.rerun()

report_type = st.radio("Jenis laporan", ["Laporan Cepat", "Laporan Lengkap"], horizontal=True)
with st.form("field_report_form"):
    c1, c2 = st.columns(2)
    with c1:
        visit_date = st.date_input("Tanggal kunjungan", value=date.today())
        start_time = st.time_input("Waktu mulai", value=time(9, 0))
    with c2:
        finish_date = st.date_input("Tanggal selesai", value=date.today())
        finish_time = st.time_input("Waktu selesai", value=time(12, 0))
    officers = st.text_area("Petugas pelaksana, satu nama satu baris", value=actor_name(user), height=90)
    parties_met = st.text_area("Pihak yang ditemui, satu nama atau jabatan satu baris", height=90)
    activity_summary = st.text_area("Ringkasan kegiatan", height=110)
    facts_found = st.text_area("Fakta yang ditemukan", height=180, help="Tuliskan fakta yang dilihat, didengar, diperiksa, atau didukung dokumen.")
    upt_explanation = st.text_area("Keterangan UPT", height=130)
    documents_checked = st.text_area("Dokumen yang diperiksa, satu dokumen satu baris", height=100)
    obstacles = st.text_area("Hambatan pemeriksaan", height=90)
    immediate_actions = st.text_area("Tindakan langsung yang telah dilakukan", height=110)
    upt_commitments = st.text_area("Komitmen perbaikan UPT", height=110)
    commitment_due = st.date_input("Tenggat komitmen UPT", value=date.today())
    finding = st.selectbox("Klasifikasi temuan", FINDING_CLASSIFICATIONS)
    initial_conclusion = st.text_area("Kesimpulan awal lapangan", height=130)
    submitted = st.form_submit_button("Kirim Laporan Lapangan", type="primary")

if submitted:
    try:
        report = submit_field_report({
            "assignment_id": assignment_id,
            "case_id": str(assignment.get("case_id")),
            "report_type": report_type,
            "visit_started_at": datetime.combine(visit_date, start_time, tzinfo=WIB).isoformat(),
            "visit_finished_at": datetime.combine(finish_date, finish_time, tzinfo=WIB).isoformat(),
            "officers": [line.strip() for line in officers.splitlines() if line.strip()],
            "parties_met": [line.strip() for line in parties_met.splitlines() if line.strip()],
            "activity_summary": activity_summary,
            "facts_found": facts_found,
            "upt_explanation": upt_explanation,
            "documents_checked": [line.strip() for line in documents_checked.splitlines() if line.strip()],
            "obstacles": obstacles,
            "immediate_actions": immediate_actions,
            "upt_commitments": upt_commitments,
            "commitment_due_at": commitment_due.isoformat(),
            "finding_classification": finding,
            "initial_conclusion": initial_conclusion,
        }, user)
        st.session_state["last_field_report_id"] = str(report.get("id"))
        st.success("Laporan lapangan berhasil dikirim. Bukti dapat diunggah pada bagian bawah.")
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.subheader("Bukti Pendukung")
report_id = st.session_state.get("last_field_report_id")
if not report_id:
    st.info("Kirim laporan terlebih dahulu agar bukti terhubung pada laporan yang benar.")
else:
    uploaded = st.file_uploader("Unggah JPG, PNG, atau PDF", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)
    evidence_description = st.text_input("Keterangan bukti")
    if st.button("Unggah Bukti", type="primary", disabled=not uploaded):
        success_count = 0
        for file in uploaded or []:
            try:
                suffix = Path(file.name).suffix.lower()
                storage_path = f"{assignment.get('case_id')}/{report_id}/{uuid4().hex}{suffix}"
                get_db().storage.from_("field-evidence").upload(
                    storage_path,
                    file.getvalue(),
                    {"content-type": file.type or "application/octet-stream", "upsert": "false"},
                )
                evidence_row = insert_row("field_evidence", {
                    "report_id": report_id,
                    "case_id": str(assignment.get("case_id")),
                    "file_name": file.name,
                    "storage_path": storage_path,
                    "mime_type": file.type or "application/octet-stream",
                    "size_bytes": len(file.getvalue()),
                    "description": evidence_description,
                    "uploaded_by": actor_name(user),
                })
                record_audit(user, "field_evidence.upload", "field_evidence", str(evidence_row.get("id") or ""), {"report_id": report_id, "file_name": file.name, "storage_path": storage_path})
                success_count += 1
            except Exception as exc:
                st.error(f"Gagal mengunggah {file.name}: {exc}")
        if success_count:
            st.success(f"{success_count} bukti berhasil diunggah.")
