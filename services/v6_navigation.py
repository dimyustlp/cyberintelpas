from __future__ import annotations

from typing import Any

import streamlit as st

from services.access_control import has_permission


def _append_once(section: list[st.Page], page: st.Page) -> None:
    existing_titles = {getattr(item, "title", "") for item in section}
    if getattr(page, "title", "") not in existing_titles:
        section.append(page)


def attach_v6_pages(pages: dict[str, list[st.Page]], user: Any) -> dict[str, list[st.Page]]:
    """Memasang modul CYBER-INTELPAS V6 sesuai hak akses pengguna."""
    intelligence: list[st.Page] = pages.setdefault("Briefing & Intelijen", [])

    if has_permission(user, "view_executive_brief"):
        _append_once(
            intelligence,
            st.Page("pages/briefing_harian.py", title="Briefing Harian", icon=":material/notifications_active:"),
        )
    if has_permission(user, "view_weekly_trends"):
        _append_once(
            intelligence,
            st.Page("pages/tren_mingguan.py", title="Tren Mingguan", icon=":material/trending_up:"),
        )
    if has_permission(user, "view_cases") or has_permission(user, "manage_cases"):
        _append_once(
            intelligence,
            st.Page("pages/kasus_intelijen.py", title="Kasus Intelijen", icon=":material/account_tree:"),
        )
    if has_permission(user, "view_reports"):
        _append_once(
            intelligence,
            st.Page("pages/laporan_intelijen.py", title="Laporan Intelijen", icon=":material/summarize:"),
        )
    if has_permission(user, "decide_cases"):
        _append_once(
            intelligence,
            st.Page("pages/keputusan_pimpinan.py", title="Keputusan Pimpinan", icon=":material/gavel:"),
        )
    if not intelligence:
        pages.pop("Briefing & Intelijen", None)

    operational: list[st.Page] = pages.setdefault("Tindak Lanjut", [])
    if has_permission(user, "view_field_assignments"):
        _append_once(
            operational,
            st.Page("pages/verifikasi_lapangan.py", title="Verifikasi Lapangan", icon=":material/fact_check:"),
        )
    if has_permission(user, "analyze_cases"):
        _append_once(
            operational,
            st.Page("pages/analisis_evaluasi.py", title="Evaluasi & Rekomendasi", icon=":material/analytics:"),
        )
    if has_permission(user, "view_action_items"):
        _append_once(
            operational,
            st.Page("pages/tindak_lanjut.py", title="Tindak Lanjut", icon=":material/task_alt:"),
        )
    if not operational:
        pages.pop("Tindak Lanjut", None)

    if has_permission(user, "view_system_health") or has_permission(user, "manage_users"):
        admin = pages.setdefault("Administrasi Sistem", [])
        if has_permission(user, "manage_users"):
            _append_once(
                admin,
                st.Page("pages/manajemen_peran.py", title="Manajemen Peran", icon=":material/admin_panel_settings:"),
            )
        if has_permission(user, "view_system_health"):
            _append_once(
                admin,
                st.Page("pages/kesehatan_sistem.py", title="Kesehatan Sistem", icon=":material/monitor_heart:"),
            )
    return pages
