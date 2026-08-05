from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.report_service import (
    ReportNarrative,
    build_report_package,
    fetch_weekly_reports,
    generate_docx,
    generate_pdf,
    generate_pptx,
    save_weekly_report,
    update_weekly_report_status,
)

user = current_user()
if user is None or not has_permission(user, "view_reports"):
    st.error("Anda tidak memiliki akses ke Laporan Intelijen.")
    st.stop()

st.title("Laporan Intelijen Pemberitaan")
st.caption("Database menghitung fakta, AI menyusun narasi, analis memverifikasi, dan pimpinan menggunakan laporan untuk pengambilan keputusan.")

start_default = date.today() - timedelta(days=6)
c1, c2 = st.columns(2)
with c1:
    start = st.date_input("Periode mulai", value=start_default)
with c2:
    end = st.date_input("Periode selesai", value=date.today())
if start > end:
    st.error("Periode tidak valid.")
    st.stop()

use_ai = st.toggle("Gunakan AI untuk menyusun narasi", value=True, help="Jika API AI tidak tersedia, sistem memakai narasi lokal berbasis angka.")
can_generate = has_permission(user, "generate_reports")
can_build_instant = can_generate or has_permission(user, "download_reports")
if st.button("Buat Laporan Sekarang", type="primary", disabled=not can_build_instant):
    with st.spinner("Menghitung publikasi unik dan menyusun laporan..."):
        snapshot, narrative = build_report_package(start, end, use_ai=use_ai)
        st.session_state["weekly_report_snapshot"] = snapshot
        st.session_state["weekly_report_narrative"] = narrative

snapshot = st.session_state.get("weekly_report_snapshot")
narrative = st.session_state.get("weekly_report_narrative")
if snapshot and isinstance(narrative, ReportNarrative):
    metrics = snapshot["metrics"]
    columns = st.columns(6)
    labels = ["Publikasi", "Negatif", "UPT", "Media", "Isu", "Tinggi/Kritis"]
    values = [
        metrics["total_publications"], metrics["negative_publications"], metrics["negative_upt_count"],
        metrics["unique_media"], metrics["issue_count"], metrics["high_critical_count"],
    ]
    for column, label, value in zip(columns, labels, values):
        column.metric(label, value)

    unmapped_negative = int(metrics.get("unmapped_negative_publications") or 0)
    if unmapped_negative:
        st.warning(f"{unmapped_negative} publikasi negatif belum memiliki pemetaan UPT dan tidak dimasukkan ke peringkat UPT.")

    st.subheader("Ringkasan Eksekutif")
    edited_exec = st.text_area("Ringkasan", value=narrative.executive_summary, height=180, label_visibility="collapsed")
    st.subheader("Analisis Tren")
    edited_trend = st.text_area("Analisis tren", value=narrative.trend_analysis, height=160, label_visibility="collapsed")
    st.subheader("Analisis Prioritas")
    edited_priority = st.text_area("Analisis prioritas", value=narrative.priority_analysis, height=160, label_visibility="collapsed")
    recommendations_text = st.text_area("Rekomendasi, satu baris satu butir", value="\n".join(narrative.recommendations), height=140)
    limitations = st.text_area("Catatan validasi dan batasan", value=narrative.limitations, height=120)

    edited_narrative = ReportNarrative(
        edited_exec,
        edited_trend,
        edited_priority,
        [line.strip() for line in recommendations_text.splitlines() if line.strip()],
        limitations,
        narrative.source,
    )

    upt_df = pd.DataFrame(snapshot["upt_table"])
    if not upt_df.empty:
        st.subheader("Rekap Publikasi Negatif per UPT")
        st.dataframe(upt_df, use_container_width=True, hide_index=True)

    if can_generate and st.button("Simpan sebagai Draf Sistem"):
        saved = save_weekly_report(snapshot, edited_narrative, user, "Draf Sistem")
        st.success(f"Draf laporan {saved.get('report_number', '')} berhasil disimpan.")

    safe_period = f"{snapshot['period']['start']}_{snapshot['period']['end']}"
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Unduh PDF",
            data=generate_pdf(snapshot, edited_narrative),
            file_name=f"Laporan_Intelijen_{safe_period}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Unduh Word",
            data=generate_docx(snapshot, edited_narrative),
            file_name=f"Laporan_Intelijen_{safe_period}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    with d3:
        st.download_button(
            "Unduh PowerPoint",
            data=generate_pptx(snapshot, edited_narrative),
            file_name=f"Bahan_Paparan_{safe_period}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )

st.divider()
st.subheader("Arsip Laporan")
reports = fetch_weekly_reports()
if not reports:
    st.info("Belum ada laporan tersimpan.")
else:
    report_df = pd.DataFrame(reports)
    show_cols = [column for column in ["report_number", "period_start", "period_end", "status", "ai_provider", "created_by", "created_at"] if column in report_df.columns]
    st.dataframe(report_df[show_cols], use_container_width=True, hide_index=True)

    options = {f"{row.get('report_number', '-')} · {row.get('period_start')} sampai {row.get('period_end')} · {row.get('status')}": str(row.get("id")) for row in reports}
    selected = st.selectbox("Pilih laporan tersimpan", list(options))
    selected_report_id = options[selected]
    selected_report = next(row for row in reports if str(row.get("id")) == selected_report_id)

    if st.button("Buka Laporan Tersimpan", use_container_width=True):
        stored_narrative = selected_report.get("ai_narrative") or {}
        st.session_state["weekly_report_snapshot"] = selected_report.get("snapshot_data") or {}
        st.session_state["weekly_report_narrative"] = ReportNarrative(
            str(stored_narrative.get("executive_summary") or ""),
            str(stored_narrative.get("trend_analysis") or ""),
            str(stored_narrative.get("priority_analysis") or ""),
            [str(item) for item in stored_narrative.get("recommendations") or []],
            str(stored_narrative.get("limitations") or ""),
            str(stored_narrative.get("source") or selected_report.get("ai_provider") or "stored"),
        )
        st.rerun()

    status_options: list[str] = []
    if has_permission(user, "edit_report_drafts"):
        status_options.extend(["Draf Sistem", "Ditelaah Analis", "Diverifikasi"])
    if has_permission(user, "approve_reports"):
        status_options.append("Disetujui")
    if has_permission(user, "publish_reports"):
        status_options.append("Dipublikasikan")
    status_options = list(dict.fromkeys(status_options))
    if status_options:
        new_status = st.selectbox("Status baru", status_options)
        if st.button("Perbarui Status Laporan"):
            update_weekly_report_status(selected_report_id, new_status, user)
            st.success("Status laporan diperbarui.")
            st.rerun()
