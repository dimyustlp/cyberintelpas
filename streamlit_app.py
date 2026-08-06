from __future__ import annotations

import streamlit as st

from components.layout import render_sidebar_profile
from components.role_briefing import render_role_briefing
from services.access_control import has_permission
from services.auth_service import current_user, init_auth_state, render_login
from services.v6_navigation import attach_v6_pages
from styles.theme import inject_global_styles

st.set_page_config(
    page_title="CYBER-INTELPAS — Pusat Intelijen Pemberitaan",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": "CYBER-INTELPAS — Sistem Intelijen Pemberitaan Pemasyarakatan",
    },
)

inject_global_styles()
init_auth_state()

user = current_user()
if user is None:
    render_login()
    st.stop()

render_sidebar_profile(user)

# --- PERBAIKAN BUG BRIEFING DIMULAI DI SINI ---
# 1. Kita buat ingatan agar Streamlit tahu apakah briefing sudah ditutup
if "briefing_selesai" not in st.session_state:
    st.session_state.briefing_selesai = False

# 2. Jika belum selesai, tampilkan briefing dan tombol tutup
if not st.session_state.briefing_selesai:
    st.info("📢 Jangan lupa untuk membaca briefing harian Anda hari ini.")
    render_role_briefing(user)
    
    # Tombol untuk menutup briefing secara permanen di sesi ini
    if st.button("Saya Mengerti & Tutup Briefing"):
        st.session_state.briefing_selesai = True
        st.rerun() # Refresh halaman agar briefing hilang
# --- PERBAIKAN BUG BRIEFING SELESAI DI SINI ---

pages: dict[str, list[st.Page]] = {
    "Eksekutif": [
        st.Page("pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    ],
    "Operasional": [],
}

if has_permission(user, "view_warning"):
    pages["Eksekutif"].append(
        st.Page("pages/warning_news.py", title="Warning News", icon=":material/warning:")
    )
if has_permission(user, "view_map"):
    pages["Eksekutif"].append(
        st.Page("pages/peta_indonesia.py", title="Peta Indonesia", icon=":material/map:")
    )
if has_permission(user, "use_ai"):
    pages["Eksekutif"].append(
        st.Page("pages/ai_assistant.py", title="AI Assistant", icon=":material/smart_toy:")
    )

if has_permission(user, "create_news"):
    input_title = "Input & Analisis" if has_permission(user, "analyze_news") else "Input Berita"
    pages["Operasional"].append(
        st.Page("pages/input_berita.py", title=input_title, icon=":material/add_link:")
    )
if has_permission(user, "review_news"):
    pages["Operasional"].append(
        st.Page("pages/pusat_telaah.py", title="Pusat Telaah", icon=":material/fact_check:")
    )
    pages["Operasional"].append(
        st.Page("pages/pemetaan_upt.py", title="Pemetaan UPT", icon=":material/account_tree:")
    )
if has_permission(user, "view_data"):
    pages["Operasional"].append(
        st.Page("pages/data_berita.py", title="Pusat Data Berita", icon=":material/database:")
    )
if has_permission(user, "export_reports"):
    pages["Operasional"].append(
        st.Page("pages/laporan.py", title="Laporan Operasional", icon=":material/description:")
    )
if not pages["Operasional"]:
    del pages["Operasional"]

admin_pages: list[st.Page] = []
if has_permission(user, "manage_users"):
    admin_pages.append(
        st.Page("pages/manajemen_pengguna.py", title="Manajemen Pengguna", icon=":material/group:")
    )
if has_permission(user, "manage_coordinates"):
    admin_pages.append(
        st.Page("pages/koordinat_upt.py", title="Koordinat UPT", icon=":material/location_on:")
    )
if has_permission(user, "manage_sync"):
    admin_pages.append(
        st.Page("pages/sinkronisasi_spreadsheet.py", title="Sinkronisasi Spreadsheet", icon=":material/sync:")
    )
if has_permission(user, "view_audit"):
    admin_pages.append(
        st.Page("pages/audit_aktivitas.py", title="Audit Aktivitas", icon=":material/history:")
    )
if has_permission(user, "manage_settings"):
    admin_pages.append(
        st.Page("pages/pengaturan.py", title="Pengaturan", icon=":material/settings:")
    )
if admin_pages:
    pages["Administrasi Sistem"] = admin_pages

pages = attach_v6_pages(pages, user)
st.navigation(pages, position="sidebar", expanded=True).run()