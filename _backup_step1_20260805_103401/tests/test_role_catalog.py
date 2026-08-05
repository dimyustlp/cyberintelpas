from services.access_control import has_permission
from services.role_catalog import canonical_role, role_name


class User:
    def __init__(self, role: str):
        self.role = role


def test_legacy_role_aliases():
    assert canonical_role("executive_viewer") == "executive_decision_maker"
    assert canonical_role("news_analyst") == "media_intelligence_analyst"
    assert canonical_role("news_intake") == "news_data_operator"
    assert canonical_role("admin_pusat") == "media_intelligence_analyst"
    assert canonical_role("operator_upt") == "news_data_operator"
    assert canonical_role("viewer") == "executive_decision_maker"


def test_role_display_names():
    assert role_name("field_verification_officer") == "Petugas Verifikasi Lapangan"
    assert role_name("evaluation_recommendation_analyst") == "Analis Evaluasi dan Rekomendasi"


def test_permissions_are_separated():
    executive = User("executive_decision_maker")
    field = User("field_verification_officer")
    admin = User("super_admin")
    assert has_permission(executive, "view_weekly_trends")
    assert not has_permission(executive, "manage_users")
    assert has_permission(field, "submit_field_reports")
    assert not has_permission(field, "manage_settings")
    assert has_permission(admin, "anything")
