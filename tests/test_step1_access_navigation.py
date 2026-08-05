from __future__ import annotations

from dataclasses import dataclass

from services.access_control import UserContext, can_edit_news, has_permission
import services.v6_navigation as nav


@dataclass
class FakePage:
    path: str
    title: str
    icon: str = ""
    default: bool = False


def _titles(pages: dict[str, list[FakePage]]) -> set[str]:
    return {page.title for section in pages.values() for page in section}


def _menus(monkeypatch, role: str) -> set[str]:
    monkeypatch.setattr(nav.st, "Page", FakePage, raising=False)
    pages = {"Eksekutif": [FakePage("pages/dashboard.py", "Dashboard")]}
    nav.attach_v6_pages(pages, UserContext("1", role, role, role))
    return _titles(pages)


def test_legacy_positional_user_context_keeps_role_order():
    user = UserContext("1", "analis", "Analis", "news_analyst")
    assert user.id == "1"
    assert user.username == "analis"
    assert user.role == "media_intelligence_analyst"


def test_legacy_page_permissions_are_mapped():
    executive = UserContext("1", "pimpinan", "Pimpinan", "executive_viewer")
    analyst = UserContext("2", "analis", "Analis", "news_analyst")
    operator = UserContext("3", "operator", "Operator", "news_intake")
    assert has_permission(executive, "view_warning")
    assert has_permission(executive, "use_ai")
    assert has_permission(analyst, "view_data")
    assert has_permission(analyst, "analyze_news")
    assert has_permission(operator, "view_data")
    assert not has_permission(operator, "analyze_news")


def test_operator_can_only_edit_own_pending_news():
    operator = UserContext("3", "operator_a", "Operator A", "news_intake")
    assert can_edit_news(operator, {"created_by": "operator_a", "status_verifikasi": "Belum Ditelaah"})
    assert not can_edit_news(operator, {"created_by": "operator_b", "status_verifikasi": "Belum Ditelaah"})
    assert not can_edit_news(operator, {"created_by": "operator_a", "status_verifikasi": "Terverifikasi"})


def test_executive_v6_navigation(monkeypatch):
    titles = _menus(monkeypatch, "executive_decision_maker")
    assert {"Briefing Harian", "Tren Mingguan", "Kasus Intelijen", "Laporan Intelijen", "Keputusan Pimpinan", "Tindak Lanjut"} <= titles
    assert "Verifikasi Lapangan" not in titles
    assert "Evaluasi & Rekomendasi" not in titles


def test_analyst_v6_navigation(monkeypatch):
    titles = _menus(monkeypatch, "media_intelligence_analyst")
    assert {"Briefing Harian", "Tren Mingguan", "Kasus Intelijen", "Laporan Intelijen", "Tindak Lanjut"} <= titles
    assert "Keputusan Pimpinan" not in titles


def test_field_officer_v6_navigation(monkeypatch):
    titles = _menus(monkeypatch, "field_verification_officer")
    assert {"Briefing Harian", "Verifikasi Lapangan", "Tindak Lanjut"} <= titles
    assert "Kasus Intelijen" not in titles


def test_evaluation_analyst_v6_navigation(monkeypatch):
    titles = _menus(monkeypatch, "evaluation_recommendation_analyst")
    assert {"Briefing Harian", "Tren Mingguan", "Kasus Intelijen", "Laporan Intelijen", "Evaluasi & Rekomendasi", "Tindak Lanjut"} <= titles


def test_super_admin_v6_navigation(monkeypatch):
    titles = _menus(monkeypatch, "super_admin")
    assert {"Briefing Harian", "Tren Mingguan", "Kasus Intelijen", "Laporan Intelijen", "Keputusan Pimpinan", "Verifikasi Lapangan", "Evaluasi & Rekomendasi", "Tindak Lanjut", "Manajemen Peran", "Kesehatan Sistem"} <= titles
