from __future__ import annotations

from pathlib import Path

import streamlit as st


def inject_global_styles() -> None:
    css_path = Path(__file__).with_name("executive.css")
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
