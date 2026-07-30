from services.geo_service import normalize_province
from services.classification import classify_rule_based


def test_province_alias():
    assert normalize_province("Bangka Belitung") == "Kepulauan Bangka Belitung"


def test_negative_classification():
    result = classify_rule_based("Petugas menggagalkan penyelundupan narkoba ke dalam lapas")
    assert result["sentimen"] == "Negatif"
    assert result["kategori"] == "Keamanan dan Ketertiban"
