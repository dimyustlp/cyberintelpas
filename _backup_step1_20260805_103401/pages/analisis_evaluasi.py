from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.case_service import (
    fetch_case_analyses,
    fetch_cases,
    fetch_field_reports,
    fetch_recommendations,
    save_case_analysis,
    save_recommendations,
)

user = current_user()
if user is None or not has_permission(user, "analyze_cases"):
    st.error("Anda tidak memiliki akses ke Analisis Evaluasi dan Rekomendasi.")
    st.stop()

st.title("Analisis Evaluasi dan Rekomendasi")
st.caption("Bandingkan narasi media dengan fakta lapangan, lalu susun rekomendasi yang memiliki penanggung jawab dan tenggat.")

cases = fetch_cases()
if not cases:
    st.info("Belum ada kasus intelijen.")
    st.stop()

labels = {
    f"{row.get('case_number', '-')} · {row.get('primary_upt', 'UPT')} · {row.get('title', 'Kasus')}": str(row.get("id"))
    for row in cases
}
selected_label = st.selectbox("Pilih kasus", list(labels))
case_id = labels[selected_label]
case = next(row for row in cases if str(row.get("id")) == case_id)
reports = fetch_field_reports(case_id)
analyses = fetch_case_analyses(case_id)
recommendations = fetch_recommendations(case_id)

with st.container(border=True):
    st.markdown(f"### {case.get('case_number', '')} · {case.get('title', '')}")
    st.write(case.get("summary") or "Belum ada ringkasan kasus.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Publikasi", case.get("article_count", 0))
    c2.metric("Media", case.get("media_count", 0))
    c3.metric("Negatif", case.get("negative_count", 0))
    c4.metric("Urgensi", case.get("highest_urgency", "Rendah"))

left, right = st.columns(2)
with left:
    st.subheader("Narasi media")
    media_narrative_default = case.get("summary") or ""
    media_narrative = st.text_area("Ringkasan narasi media", value=media_narrative_default, height=220, label_visibility="collapsed")
with right:
    st.subheader("Fakta lapangan")
    latest_report = reports[0] if reports else {}
    facts_default = latest_report.get("facts_found") or "Belum ada laporan lapangan."
    field_facts = st.text_area("Ringkasan fakta lapangan", value=facts_default, height=220, label_visibility="collapsed")

st.subheader("Matriks Perbandingan Media dan Fakta")
comparison_df = pd.DataFrame([
    {"Unsur": "Waktu kejadian", "Narasi Media": "", "Temuan Lapangan": "", "Penilaian": ""},
    {"Unsur": "Lokasi dan pihak terkait", "Narasi Media": "", "Temuan Lapangan": "", "Penilaian": ""},
    {"Unsur": "Kronologi", "Narasi Media": "", "Temuan Lapangan": "", "Penilaian": ""},
    {"Unsur": "Tindak lanjut", "Narasi Media": "", "Temuan Lapangan": "", "Penilaian": ""},
    {"Unsur": "Kondisi terkini", "Narasi Media": "", "Temuan Lapangan": "", "Penilaian": ""},
])
comparison = st.data_editor(comparison_df, num_rows="dynamic", use_container_width=True, hide_index=True)

st.subheader("Penilaian Lima Dimensi")
c1, c2, c3 = st.columns(3)
with c1:
    information_validity = st.selectbox("Validitas informasi", ["Terverifikasi", "Sebagian terverifikasi", "Belum terverifikasi", "Tidak terbukti"])
    reputation_impact = st.selectbox("Dampak reputasi", ["Sangat Rendah", "Rendah", "Sedang", "Tinggi", "Sangat Tinggi"], index=2)
with c2:
    operational_impact = st.selectbox("Dampak operasional", ["Tidak Ada", "Terbatas", "Mengganggu Layanan", "Mengganggu Keamanan", "Mengancam Keberlangsungan Operasional"], index=1)
    compliance_impact = st.selectbox("Dampak hukum dan kepatuhan", ["Tidak Terindikasi", "Perlu Pemeriksaan", "Terdapat Ketidaksesuaian", "Berpotensi Pelanggaran", "Memerlukan Penanganan Khusus"], index=1)
with c3:
    escalation_risk = st.selectbox("Risiko eskalasi media", ["Menurun", "Stabil", "Berpotensi Meningkat", "Sedang Meningkat", "Viral"], index=1)
    follow_up_assessment = st.selectbox("Kualitas tindak lanjut UPT", ["Memadai", "Cukup Memadai", "Belum Memadai", "Tidak Memadai", "Belum Dapat Dinilai"], index=4)

root_causes = st.multiselect("Akar masalah", [
    "Kelemahan Prosedur", "Kelemahan Pengawasan", "Keterbatasan Sumber Daya Manusia",
    "Kelebihan Kapasitas", "Keterlambatan Respons", "Kesenjangan Komunikasi Publik",
    "Kelemahan Koordinasi", "Sarana dan Prasarana", "Perilaku Individu",
    "Isu Lama yang Tidak Ditutup secara Komunikasi", "Informasi Keliru atau di Luar Konteks",
])
final_analysis = st.text_area("Analisis akhir", height=220)

if st.button("Simpan Analisis", type="primary"):
    try:
        saved = save_case_analysis({
            "case_id": case_id,
            "analysis_version": len(analyses) + 1,
            "media_narrative": media_narrative,
            "field_facts": field_facts,
            "comparison_matrix": comparison.to_dict("records"),
            "information_validity": information_validity,
            "reputation_impact": reputation_impact,
            "operational_impact": operational_impact,
            "compliance_impact": compliance_impact,
            "media_escalation_risk": escalation_risk,
            "root_causes": root_causes,
            "final_analysis": final_analysis,
            "follow_up_assessment": follow_up_assessment,
            "status": "Draf",
        }, user)
        st.success(f"Analisis versi {saved.get('analysis_version', len(analyses)+1)} berhasil disimpan.")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.subheader("Rekomendasi Bertingkat")
with st.form("recommendation_form"):
    rec_type = st.selectbox("Jenis rekomendasi", ["Tindakan Segera", "Jangka Pendek", "Tindakan Struktural"])
    recommendation = st.text_area("Isi rekomendasi", height=120)
    c1, c2, c3 = st.columns(3)
    with c1:
        responsible_party = st.text_input("Penanggung jawab")
    with c2:
        due_at = st.date_input("Tenggat", value=date.today())
    with c3:
        priority = st.selectbox("Prioritas", ["Rendah", "Sedang", "Tinggi", "Kritis"], index=1)
    add_rec = st.form_submit_button("Tambahkan Rekomendasi", type="primary")
if add_rec:
    count = save_recommendations(case_id, [{
        "recommendation_type": rec_type,
        "recommendation": recommendation,
        "responsible_party": responsible_party,
        "due_at": due_at.isoformat(),
        "priority": priority,
    }], user)
    if count:
        st.success("Rekomendasi berhasil ditambahkan.")
        st.rerun()
    else:
        st.warning("Isi rekomendasi belum diisi.")

if recommendations:
    st.dataframe(pd.DataFrame(recommendations), use_container_width=True, hide_index=True)
