from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from services.audit_service import log_action
from services.classification import classify_rule_based
from services.database import delete_rows, get_db, insert_row, table_exists, update_rows

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
}

LEGACY_NEWS_COLUMNS = {
    "nama_upt", "nama_petugas", "link", "judul", "media", "platform",
    "tanggal_publikasi", "kategori", "subkategori", "sentimen", "urgensi",
    "ringkasan", "caption_manual", "status_baca", "catatan",
}


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def normalize_url(url: str) -> str:
    value = clean_text(url)
    if not value:
        return ""
    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    return value.rstrip("/")


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if "instagram.com" in host:
        return "Instagram"
    if "facebook.com" in host or "fb.watch" in host:
        return "Facebook"
    if "tiktok.com" in host:
        return "TikTok"
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube"
    if "news.google.com" in host:
        return "Google News"
    return "Portal Berita" if host else "Tidak diketahui"


def _meta(soup: BeautifulSoup, *, prop: str | None = None, name: str | None = None) -> str:
    tag = soup.find("meta", attrs={"property": prop}) if prop else None
    if tag is None and name:
        tag = soup.find("meta", attrs={"name": name})
    return clean_text(tag.get("content")) if tag else ""


def read_public_page(url: str) -> dict[str, str]:
    platform = detect_platform(url)
    base = {
        "judul": "",
        "media": urlparse(url).netloc.replace("www.", ""),
        "platform": platform,
        "tanggal_publikasi": "",
        "ringkasan": "",
        "status_baca": "",
    }
    if platform in {"Instagram", "Facebook", "TikTok"}:
        return {
            **base,
            "judul": f"Tautan {platform}",
            "ringkasan": "Konten media sosial terdeteksi. Tempel caption pada kolom teks tambahan agar analisis lebih akurat.",
            "status_baca": "PERLU CEK MANUAL",
        }
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=20, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = _meta(soup, prop="og:title") or _meta(soup, name="twitter:title") or clean_text(soup.title.string if soup.title else "")
        media = _meta(soup, prop="og:site_name") or urlparse(response.url).netloc.replace("www.", "")
        published = _meta(soup, prop="article:published_time") or _meta(soup, name="date") or _meta(soup, name="pubdate")
        description = _meta(soup, prop="og:description") or _meta(soup, name="description") or _meta(soup, name="twitter:description")
        return {
            **base,
            "judul": title or "Judul tidak ditemukan",
            "media": media or base["media"],
            "tanggal_publikasi": published,
            "ringkasan": description or "Ringkasan otomatis belum ditemukan.",
            "status_baca": "BERHASIL",
        }
    except requests.RequestException:
        return {
            **base,
            "judul": "Judul belum dapat diambil",
            "ringkasan": "Halaman tidak dapat dibaca otomatis. Tautan tetap dapat dicatat dan dilengkapi manual.",
            "status_baca": "GAGAL MEMBACA",
        }


def analyze_news(url: str, manual_text: str = "") -> dict[str, object]:
    extracted = read_public_page(url)
    combined = " ".join([extracted["judul"], extracted["ringkasan"], manual_text])
    result = {**extracted, **classify_rule_based(combined)}
    try:
        from services.ai_service import analyze_news_with_ai
        ai_result = analyze_news_with_ai(extracted, manual_text)
        if ai_result:
            result.update(ai_result)
    except Exception:
        pass
    return result


def save_news(payload: dict, actor_username: str, actor_role: str) -> tuple[bool, str]:
    prepared = {k: v for k, v in payload.items() if v is not pd.NaT}
    try:
        rows = insert_row("berita", prepared)
    except Exception as exc:
        message = str(exc)
        if "duplicate" in message.casefold() or "berita_link_key" in message.casefold():
            return False, "Tautan tersebut sudah pernah disimpan (duplikat)."
        # Kompatibilitas dengan schema lama.
        try:
            legacy = {k: v for k, v in prepared.items() if k in LEGACY_NEWS_COLUMNS}
            rows = insert_row("berita", legacy)
        except Exception:
            return False, f"Gagal menyimpan berita: {message}"
    entity_id = str(rows[0].get("id", "")) if rows else ""
    log_action("create", "berita", entity_id, actor_username, actor_role, {"link": payload.get("link")})
    return True, "Berita berhasil disimpan ke database online."


def update_news(news_id: str, payload: dict, actor_username: str, actor_role: str) -> None:
    update_rows("berita", payload, "id", news_id)
    log_action("update", "berita", news_id, actor_username, actor_role, {"fields": sorted(payload)})


def delete_news(news_id: str, actor_username: str, actor_role: str) -> None:
    delete_rows("berita", "id", news_id)
    log_action("delete", "berita", news_id, actor_username, actor_role)
