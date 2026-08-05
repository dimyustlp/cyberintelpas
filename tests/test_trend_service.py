from datetime import date

from services.trend_service import build_weekly_snapshot, normalize_url


def test_normalize_url_removes_tracking_parameters():
    first = normalize_url("https://www.media.id/a?utm_source=x&fbclid=abc")
    second = normalize_url("https://media.id/a")
    assert first == second


def test_different_links_same_issue_are_counted_as_publications():
    rows = [
        {
            "id": "1",
            "judul": "Video lama penggerebekan rumah dinas Lapas Waingapu kembali viral",
            "nama_upt": "Lembaga Pemasyarakatan Kelas IIA Waingapu",
            "media": "Media A",
            "sentimen": "Negatif",
            "urgensi": "Tinggi",
            "link": "https://media-a.id/berita-1",
            "detected_at": "2026-08-01T01:00:00Z",
        },
        {
            "id": "2",
            "judul": "Penggerebekan rumah dinas Lapas Waingapu kembali beredar",
            "nama_upt": "Lembaga Pemasyarakatan Kelas IIA Waingapu",
            "media": "Media B",
            "sentimen": "Negatif",
            "urgensi": "Tinggi",
            "link": "https://media-b.id/berita-2",
            "detected_at": "2026-08-02T01:00:00Z",
        },
    ]
    snapshot = build_weekly_snapshot(rows, date(2026, 8, 1), date(2026, 8, 7))
    assert snapshot["metrics"]["negative_publications"] == 2
    assert snapshot["metrics"]["unique_media"] == 2
    assert snapshot["upt_table"][0]["Jumlah Publikasi"] == 2
    assert snapshot["upt_table"][0]["Jumlah Isu"] == 1


def test_identical_normalized_link_is_counted_once():
    rows = [
        {
            "id": "1",
            "judul": "Berita A",
            "nama_upt": "UPT A",
            "media": "Media A",
            "sentimen": "Negatif",
            "urgensi": "Sedang",
            "link": "https://media.id/a?utm_source=x",
            "detected_at": "2026-08-01T01:00:00Z",
        },
        {
            "id": "2",
            "judul": "Berita A salinan",
            "nama_upt": "UPT A",
            "media": "Media A",
            "sentimen": "Negatif",
            "urgensi": "Sedang",
            "link": "https://media.id/a",
            "detected_at": "2026-08-01T02:00:00Z",
        },
    ]
    snapshot = build_weekly_snapshot(rows, date(2026, 8, 1), date(2026, 8, 7))
    assert snapshot["metrics"]["total_publications"] == 1
    assert snapshot["metrics"]["negative_publications"] == 1


def test_unmapped_negative_is_not_counted_as_upt_ranking():
    rows = [
        {
            "id": "1",
            "judul": "Isu tanpa nama UPT",
            "nama_upt": "Belum Teridentifikasi",
            "media": "Media A",
            "sentimen": "Negatif",
            "urgensi": "Tinggi",
            "link": "https://media.id/tanpa-upt",
            "detected_at": "2026-08-01T01:00:00Z",
        },
        {
            "id": "2",
            "judul": "Isu pada UPT A",
            "nama_upt": "UPT A",
            "media": "Media B",
            "sentimen": "Negatif",
            "urgensi": "Sedang",
            "link": "https://media.id/upt-a",
            "detected_at": "2026-08-02T01:00:00Z",
        },
    ]
    snapshot = build_weekly_snapshot(rows, date(2026, 8, 1), date(2026, 8, 7))
    assert snapshot["metrics"]["negative_publications"] == 2
    assert snapshot["metrics"]["mapped_negative_publications"] == 1
    assert snapshot["metrics"]["unmapped_negative_publications"] == 1
    assert snapshot["metrics"]["negative_upt_count"] == 1
    assert len(snapshot["upt_table"]) == 1
    assert snapshot["upt_table"][0]["UPT"] == "UPT A"
