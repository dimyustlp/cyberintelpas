from __future__ import annotations

import streamlit as st

from components.layout import render_sidebar_profile
from services.access_control import has_permission
from services.auth_service import current_user, init_auth_state, render_login
from styles.theme import inject_global_styles

st.set_page_config(
    page_title="SIMBERPAS — Executive Dashboard",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": "SIMBERPAS — Sistem Monitoring Berita Pemasyarakatan",
    },
)

inject_global_styles()
init_auth_state()

user = current_user()
if user is None:
    render_login()
    st.stop()

render_sidebar_profile(user)

pages: dict[str, list[st.Page]] = {
    "Executive": [
        st.Page("pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("pages/peta_indonesia.py", title="Peta Indonesia", icon=":material/map:"),
        st.Page("pages/ai_assistant.py", title="AI Assistant", icon=":material/smart_toy:"),
    ],
    "Monitoring": [
        st.Page("pages/data_berita.py", title="Pusat Data Berita", icon=":material/database:"),
        st.Page("pages/laporan.py", title="Laporan", icon=":material/description:"),
    ],
}

if has_permission(user, "create_news"):
    pages["Monitoring"].insert(
        0,
        st.Page("pages/input_berita.py", title="Input & Analisis", icon=":material/add_link:"),
    )

admin_pages: list[st.Page] = []
if has_permission(user, "manage_users") or has_permission(user, "manage_scoped_users"):
    admin_pages.append(
        st.Page("pages/manajemen_pengguna.py", title="Manajemen Pengguna", icon=":material/group:")
    )
if has_permission(user, "manage_settings"):
    admin_pages.append(
        st.Page("pages/pengaturan.py", title="Pengaturan", icon=":material/settings:")
    )
if admin_pages:
    pages["Administrasi"] = admin_pages

navigation = st.navigation(pages, position="sidebar", expanded=True)
navigation.run()
