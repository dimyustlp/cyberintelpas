from __future__ import annotations

import pytest

import services.news_service as news_service


def test_normalize_url_removes_tracking_parameters():
    url = "https://www.Example.com/news/item/?utm_source=x&fbclid=abc&id=7#bagian"
    assert news_service.normalize_url(url) == "https://example.com/news/item?id=7"


def test_reviewer_can_verify_directly_from_unreviewed(monkeypatch):
    updates = []
    monkeypatch.setattr(news_service, "_current_status", lambda news_id: "Belum Ditelaah")
    monkeypatch.setattr(news_service, "update_rows", lambda *args: updates.append(args))
    monkeypatch.setattr(news_service, "table_exists", lambda table: False)
    monkeypatch.setattr(news_service, "log_action", lambda *args, **kwargs: None)
    news_service.change_news_status("1", "Terverifikasi", "Sumber sesuai", "analis", "news_analyst")
    assert updates and updates[0][1]["status_verifikasi"] == "Terverifikasi"


def test_intake_cannot_verify(monkeypatch):
    monkeypatch.setattr(news_service, "_current_status", lambda news_id: "Belum Ditelaah")
    with pytest.raises(PermissionError):
        news_service.change_news_status("1", "Terverifikasi", "", "operator", "news_intake")


def test_correction_requires_reason(monkeypatch):
    monkeypatch.setattr(news_service, "_current_status", lambda news_id: "Belum Ditelaah")
    with pytest.raises(ValueError):
        news_service.change_news_status("1", "Perlu Koreksi", "", "analis", "news_analyst")


def test_intake_can_resubmit_correction(monkeypatch):
    updates = []
    monkeypatch.setattr(news_service, "_current_status", lambda news_id: "Perlu Koreksi")
    monkeypatch.setattr(news_service, "update_rows", lambda *args: updates.append(args))
    monkeypatch.setattr(news_service, "table_exists", lambda table: False)
    monkeypatch.setattr(news_service, "log_action", lambda *args, **kwargs: None)
    news_service.change_news_status("1", "Belum Ditelaah", "Sudah diperbaiki", "operator", "news_intake")
    assert updates[0][1]["status_verifikasi"] == "Belum Ditelaah"


def test_warning_state_distinguishes_preliminary_and_verified():
    assert news_service.warning_state({"urgensi": "Kritis", "status_verifikasi": "Belum Ditelaah"}) == "preliminary"
    assert news_service.warning_state({"urgensi": "Tinggi", "status_verifikasi": "Terverifikasi"}) == "verified"
    assert news_service.warning_state({"urgensi": "Kritis", "status_verifikasi": "Tidak Valid"}) == "none"


def test_duplicate_url_is_detected():
    import pandas as pd

    df = pd.DataFrame([
        {"id": "1", "link": "https://example.com/a?utm_source=x", "judul": "Berita A", "nama_upt": "UPT A", "media": "Media", "tanggal_publikasi": "2026-08-01"}
    ])
    result = news_service.find_duplicate_news(
        "https://www.example.com/a", "Judul lain", "Media lain", "UPT B", "2026-08-02", df
    )
    assert not result.empty
    assert result.iloc[0]["duplicate_reason"] == "URL sama"


def test_attachment_signature_validation():
    from services.attachment_service import validate_attachment

    validate_attachment("bukti.pdf", b"%PDF-1.7\ncontoh")
    with pytest.raises(ValueError):
        validate_attachment("bukti.exe", b"MZ")
    with pytest.raises(ValueError):
        validate_attachment("bukti.png", b"bukan gambar")
