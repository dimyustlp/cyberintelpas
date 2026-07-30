from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from services.access_control import ROLE_LABELS, UserContext


def format_number(value: int | float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(value):,}".replace(",", ".")


def page_header(title: str, subtitle: str, kicker: str = "Executive Intelligence") -> None:
    now = pd.Timestamp.now(tz="Asia/Jakarta")
    st.markdown(
        f"""
        <div class="sim-hero">
            <div class="sim-hero-kicker">{escape(kicker)}</div>
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
            <div class="sim-hero-meta">
                Kementerian Imigrasi dan Pemasyarakatan &nbsp;•&nbsp;
                Direktorat Jenderal Pemasyarakatan &nbsp;•&nbsp;
                {now.strftime('%d %B %Y, %H:%M')} WIB
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_grid(items: list[dict]) -> None:
    cards: list[str] = []
    for item in items:
        accent = escape(str(item.get("accent", "#1769AA")))
        icon = escape(str(item.get("icon", "•")))
        title = escape(str(item.get("title", "")))
        value = escape(str(item.get("value", "0")))
        foot = escape(str(item.get("foot", "")))
        cards.append(
            f'<div class="sim-kpi" style="--accent:{accent}">'
            f'<div class="sim-kpi-icon">{icon}</div>'
            f'<div class="sim-kpi-title">{title}</div>'
            f'<div class="sim-kpi-value">{value}</div>'
            f'<div class="sim-kpi-foot">{foot}</div>'
            f'</div>'
        )
    html = '<div class="sim-kpi-grid">' + ''.join(cards) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def info_panel(kicker: str, title: str, body_html: str, extra_class: str = "") -> None:
    st.markdown(
        f"""
        <div class="sim-panel {escape(extra_class)}">
            <div class="sim-panel-kicker">{escape(kicker)}</div>
            <div class="sim-panel-title">{title}</div>
            <div class="sim-panel-body">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="sim-section">
            <div>
                <div class="sim-section-title">{escape(title)}</div>
                <div class="sim-section-subtitle">{escape(subtitle)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str) -> None:
    info_panel("Status Sistem", escape(title), escape(body))


def render_sidebar_profile(user: UserContext) -> None:
    role = ROLE_LABELS.get(user.role, user.role)
    scope = user.assigned_upt or user.assigned_kanwil or "Cakupan nasional"
    with st.sidebar:
        st.markdown(
            """
            <div class="sim-brand">
                <div class="sim-brand-kicker">Executive Command Center</div>
                <div class="sim-brand-title">🏛️ SIMBERPAS</div>
                <div class="sim-brand-subtitle">Sistem Monitoring Berita Pemasyarakatan</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="sim-user-card">
                <div class="sim-user-name">{escape(user.full_name or user.username)}</div>
                <div class="sim-user-role">{escape(role)}</div>
                <div class="sim-user-scope">{escape(scope)}</div>
                <div class="sim-online"><span class="sim-online-dot"></span>Sistem aktif</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Keluar", icon=":material/logout:", use_container_width=True):
            from services.auth_service import logout
            logout()
        st.caption("Tema terang/gelap dapat diubah melalui menu ⋮ → Settings → Theme.")
