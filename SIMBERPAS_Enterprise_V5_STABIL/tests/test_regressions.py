from datetime import datetime, timezone
import sys
import types

import pandas as pd

# Stub ringan agar fungsi akses dapat diuji tanpa menjalankan server Streamlit.
streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.error = lambda *args, **kwargs: None
streamlit_stub.stop = lambda *args, **kwargs: None
sys.modules.setdefault("streamlit", streamlit_stub)

from services.access_control import has_permission, scope_news
from services.export_service import excel_bytes, excel_safe_dataframe
from services.geo_service import attach_news_counts, province_map_data


def test_none_user_does_not_crash():
    df = pd.DataFrame([{"nama_upt": "UPT A"}])
    assert has_permission(None, "view_all") is False
    assert scope_news(df, None).empty


def test_geo_count_column_is_always_present():
    upt = pd.DataFrame([
        {
            "nama_upt": "UPT A",
            "provinsi": "DKI Jakarta",
            "latitude": None,
            "longitude": None,
            "coordinate_quality": "",
            "jumlah_berita": 99,
        }
    ])
    news = pd.DataFrame([{"nama_upt": "UPT A"}])
    attached = attach_news_counts(upt, news)
    assert attached["jumlah_berita"].tolist() == [1]
    mapped = province_map_data(upt, news)
    assert "jumlah_berita" in mapped.columns
    assert int(mapped.iloc[0]["jumlah_berita"]) == 1


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
