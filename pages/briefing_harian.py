from __future__ import annotations

import streamlit as st

from components.role_briefing import render_briefing_page
from services.auth_service import current_user

user = current_user()
if user is None:
    st.error("Sesi pengguna tidak tersedia.")
    st.stop()
render_briefing_page(user)
