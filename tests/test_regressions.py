from datetime import datetime, timezone
import sys
import types

import pandas as pd

streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.error = lambda *args, **kwargs: None
streamlit_stub.stop = lambda *args, **kwargs: None
sys.modules.setdefault("streamlit", streamlit_stub)

from services.access_control import UserContext, can_edit_news, has_permission, scope_news, scope_upt
from services.export_service import excel_bytes, excel_safe_dataframe
from services.geo_service import attach_news_counts, build_upt_status, province_map_data


def test_none_user_does_not_crash():
    df = pd.DataFrame([{"nama_upt": "UPT A"}])
    assert has_permission(None, "view_all") is False
    assert scope_news(df, None).empty


def test_geo_count_column_is_always_present():
    upt = pd.DataFrame([{"nama_upt": "UPT A", "provinsi": "DKI Jakarta", "latitude": None, "longitude": None}])
    news = pd.DataFrame([{"nama_upt": "UPT A"}])
    attached = attach_news_counts(upt, news)
    assert attached["jumlah_berita"].tolist() == [1]
    mapped = province_map_data(upt, news)
    assert "jumlah_berita" in mapped.columns


def test_excel_timezone_is_removed():
    df = pd.DataFrame({
        "created_at": [pd.Timestamp("2026-07-30T04:21:52+00:00")],
        "python_dt": [datetime(2026, 7, 30, tzinfo=timezone.utc)],
        "judul": ["Tes"],
    })
    safe = excel_safe_dataframe(df)
    assert safe.loc[0, "created_at"].tzinfo is None
    assert safe.loc[0, "python_dt"].tzinfo is None
    assert len(excel_bytes(df)) > 100


def test_marker_priority_and_preliminary_warning():
    upt = pd.DataFrame([
        {"nama_upt": "UPT KRITIS", "provinsi": "DKI Jakarta", "latitude": -6.2, "longitude": 106.8},
        {"nama_upt": "UPT AWAL", "provinsi": "Jawa Barat", "latitude": -6.9, "longitude": 107.6},
        {"nama_upt": "UPT NEGATIF", "provinsi": "Jawa Tengah", "latitude": -7.1, "longitude": 110.1},
        {"nama_upt": "UPT KOSONG", "provinsi": "Aceh", "latitude": 4.6, "longitude": 96.7},
    ])
    news = pd.DataFrame([
        {"nama_upt": "UPT KRITIS", "status_verifikasi": "Terverifikasi", "sentimen": "Positif", "urgensi": "Kritis"},
        {"nama_upt": "UPT AWAL", "status_verifikasi": "Belum Ditelaah", "sentimen": "Negatif", "urgensi": "Kritis"},
        {"nama_upt": "UPT NEGATIF", "status_verifikasi": "Terverifikasi", "sentimen": "Negatif", "urgensi": "Rendah"},
    ])
    result = build_upt_status(upt, news).set_index("nama_upt")
    assert result.loc["UPT KRITIS", "marker_status"] == "critical"
    assert result.loc["UPT AWAL", "marker_status"] == "draft"
    assert bool(result.loc["UPT AWAL", "preliminary_warning"]) is True
    assert result.loc["UPT NEGATIF", "marker_status"] == "negative"
    assert result.loc["UPT KOSONG", "marker_status"] == "none"


def test_four_role_permissions_are_separated():
    admin = UserContext("1", "admin", "Admin", "super_admin")
    analyst = UserContext("2", "analis", "Analis", "news_analyst")
    intake = UserContext("3", "input", "Operator", "news_intake")
    executive = UserContext("4", "pimpinan", "Pimpinan", "executive_viewer")
    assert has_permission(admin, "manage_users") is True
    assert has_permission(analyst, "verify_news") is True
    assert has_permission(intake, "verify_news") is False
    assert has_permission(intake, "analyze_news") is False
    assert has_permission(executive, "create_news") is False
    assert has_permission(executive, "view_warning") is True


def test_intake_only_sees_and_edits_own_news():
    intake = UserContext("3", "operator_a", "Operator A", "news_intake")
    news = pd.DataFrame([
        {"created_by": "operator_a", "nama_petugas": "Operator A", "status_verifikasi": "Belum Ditelaah", "judul": "A"},
        {"created_by": "operator_b", "nama_petugas": "Operator B", "status_verifikasi": "Belum Ditelaah", "judul": "B"},
    ])
    result = scope_news(news, intake)
    assert result["judul"].tolist() == ["A"]
    assert can_edit_news(intake, result.iloc[0]) is True


def test_all_internal_roles_can_use_upt_master():
    upt = pd.DataFrame([{"nama_upt": "UPT A"}, {"nama_upt": "UPT B"}])
    for role in ["super_admin", "news_analyst", "news_intake", "executive_viewer"]:
        assert len(scope_upt(upt, UserContext("1", role, role, role))) == 2
