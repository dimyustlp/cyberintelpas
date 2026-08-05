from __future__ import annotations

from typing import Any

import streamlit as st

from services.briefing_service import RoleBriefing, build_role_briefing
from services.case_service import actor_name
from services.role_catalog import canonical_role


def _state_key(user: Any) -> str:
    role = canonical_role(user.get("role") if isinstance(user, dict) else getattr(user, "role", ""))
    return f"cyberintelpas_briefing_dismissed::{actor_name(user)}::{role}"


def _render_briefing_content(briefing: RoleBriefing) -> None:
    st.caption(briefing.role_name)
    st.markdown(f"### {briefing.title}")
    status_type = (
        "error" if briefing.status == "Perhatian Tinggi"
        else "warning" if briefing.status in {"Perlu Tindakan", "Perlu Perhatian"}
        else "success"
    )
    getattr(st, status_type)(briefing.punchline)

    if briefing.cards:
        columns = st.columns(min(len(briefing.cards), 5))
        for idx, card in enumerate(briefing.cards):
            with columns[idx % len(columns)]:
                st.metric(card.label, card.value, help=card.help_text or None)

    if briefing.priorities:
        st.markdown("#### Sorotan utama")
        for item in briefing.priorities:
            with st.container(border=True):
                st.markdown(f"**{item.get('title', 'Tanpa judul')}**")
                st.caption(item.get("meta", ""))
                analysis = str(item.get("analysis") or "")
                if analysis:
                    st.write(analysis[:500])

    st.markdown("#### Yang perlu dilakukan")
    for todo in briefing.todos:
        st.markdown(f"- {todo}")


@st.dialog("Briefing Harian", width="large", icon=":material/notifications_active:")
def _briefing_dialog(user: Any) -> None:
    try:
        briefing = build_role_briefing(user)
        _render_briefing_content(briefing)
    except Exception as exc:
        st.warning("Briefing belum dapat dimuat penuh. Dashboard utama tetap dapat digunakan.")
        st.caption(str(exc))

    if st.button("Masuk ke Dashboard", type="primary", use_container_width=True):
        st.session_state[_state_key(user)] = True
        st.rerun()


def render_role_briefing(user: Any, *, force: bool = False) -> None:
    """Dipanggil satu kali pada entrypoint setelah login dan sebelum navigation.run()."""
    key = _state_key(user)
    if force:
        st.session_state[key] = False
    if not st.session_state.get(key, False):
        _briefing_dialog(user)


def render_briefing_page(user: Any) -> None:
    st.title("Briefing Harian")
    st.caption("Ringkasan dinamis sesuai tugas pokok dan fungsi pengguna.")
    briefing = build_role_briefing(user)
    _render_briefing_content(briefing)
