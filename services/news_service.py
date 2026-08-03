from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from services.audit_service import log_action
from services.classification import classify_rule_based
from services.database import fetch_news_df, get_db, insert_row, table_exists, update_rows

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
}

WORKFLOW_STATUSES = [
    "Belum Ditelaah",
    "Perlu Koreksi",
    "Terverifikasi",
    "Tidak Valid",
    "Diarsipkan",
]

# Status lama tetap dikenali agar data sebelum migrasi masih dapat dibuka.
STATUS_ALIASES = {
    "Draft": "Belum Ditelaah",
    "Diajukan": "Belum Ditelaah",
    "Sedang Diperiksa": "Belum Ditelaah",
    "Perlu Perbaikan": "Perlu Koreksi",
    "Ditolak": "Tidak Valid",
}
PENDING_STATUSES = {"Belum Ditelaah", "Perlu Koreksi", "Draft", "Diajukan", "Sedang Diperiksa", "Perlu Perbaikan"}
REVIEWER_ROLES = {"super_admin", "news_analyst", "admin_pusat", "admin_kanwil"}
ALLOWED_TRANSITIONS = {
    "Belum Ditelaah": {"Terverifikasi", "Perlu Koreksi", "Tidak Valid", "Diarsipkan"},
    "Perlu Koreksi": {"Belum Ditelaah", "Terverifikasi", "Tidak Valid", "Diarsipkan"},
    "Terverifikasi": {"Perlu Koreksi", "Tidak Valid", "Diarsipkan"},
    "Tidak Valid": {"Belum Ditelaah", "Diarsipkan"},
    "Diarsipkan": {"Belum Ditelaah"},
}


def normalize_status(status: str | None) -> str:
    clean = str(status or "Belum Ditelaah").strip()
    return STATUS_ALIASES.get(clean, clean)


def warning_state(row: dict | pd.Series) -> str:
    """Kembalikan preliminary, verified, atau none untuk Warning News."""
    status = normalize_status(str(row.get("status_verifikasi") or "Belum Ditelaah"))
    urgency = clean_text(str(row.get("urgensi") or "Rendah")).casefold()
    if urgency not in {"tinggi", "kritis"} or status in {"Tidak Valid", "Diarsipkan"}:
        return "none"
    return "verified" if status == "Terverifikasi" else "preliminary"

TRACKING_PARAMS = {
    "fbclid", "gclid", "igsh", "igshid", "mc_cid", "mc_eid", "ref", "ref_src",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
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
    parsed = urlparse(value)
    scheme = (parsed.scheme or "https").lower()
    host = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    clean_query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.casefold() not in TRACKING_PARAMS and not k.casefold().startswith("utm_")
    ]
    query = urlencode(sorted(clean_query))
    return urlunparse((scheme, host, path, "", query, ""))


def content_hash(url: str, title: str = "", media: str = "", published: str = "") -> str:
    raw = "|".join([
        normalize_url(url).casefold(), clean_text(title).casefold(), clean_text(media).casefold(), str(published or "")[:10]
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        "judul": "", "media": urlparse(url).netloc.replace("www.", ""), "platform": platform,
        "tanggal_publikasi": "", "ringkasan": "", "status_baca": "",
    }
    if platform in {"Instagram", "Facebook", "TikTok"}:
        return {
            **base,
            "judul": f"Tautan {platform}",
            "ringkasan": "Konten media sosial terdeteksi. Tempel caption atau transkrip agar analisis lebih akurat.",
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


def find_duplicate_news(
    url: str,
    title: str = "",
    media: str = "",
    nama_upt: str = "",
    publication_date: str = "",
    news_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    df = fetch_news_df() if news_df is None else news_df.copy()
    if df.empty:
        return pd.DataFrame()
    normalized = normalize_url(url)
    if "link_normalized" not in df.columns:
        df["link_normalized"] = df["link"].astype(str).map(normalize_url)
    exact = df[df["link_normalized"].astype(str).str.casefold() == normalized.casefold()].copy()
    if not exact.empty:
        exact["duplicate_reason"] = "URL sama"
        exact["similarity"] = 1.0
        return exact.head(10)

    clean_title = clean_text(title).casefold()
    if not clean_title:
        return pd.DataFrame()
    rows: list[dict] = []
    target_date = str(publication_date or "")[:10]
    for _, row in df.head(5000).iterrows():
        candidate = clean_text(str(row.get("judul") or "")).casefold()
        if not candidate:
            continue
        similarity = SequenceMatcher(None, clean_title, candidate).ratio()
        same_upt = clean_text(str(row.get("nama_upt") or "")).casefold() == clean_text(nama_upt).casefold()
        same_media = clean_text(str(row.get("media") or "")).casefold() == clean_text(media).casefold()
        row_date = str(row.get("tanggal_publikasi") or "")[:10]
        same_date = bool(target_date and row_date and target_date == row_date)
        if similarity >= 0.88 or (similarity >= 0.78 and same_upt and (same_media or same_date)):
            item = row.to_dict()
            item["duplicate_reason"] = "Judul sangat mirip"
            item["similarity"] = round(similarity, 3)
            rows.append(item)
    return pd.DataFrame(rows).sort_values("similarity", ascending=False).head(10) if rows else pd.DataFrame()


def _json_safe(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _current_news(news_id: str) -> dict:
    db = get_db()
    if db is None:
        return {}
    try:
        response = db.table("berita").select("*").eq("id", news_id).limit(1).execute()
        rows = response.data or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def save_news(payload: dict, actor_username: str, actor_role: str) -> tuple[bool, str, str]:
    prepared = {k: _json_safe(v) for k, v in payload.items()}
    prepared = {k: v for k, v in prepared.items() if v is not None or k in {"duplicate_of", "ai_confidence"}}
    prepared.setdefault("status_verifikasi", "Belum Ditelaah")
    prepared.setdefault("source_type", "manual")
    prepared.setdefault("created_by", actor_username)
    prepared["link"] = normalize_url(str(prepared.get("link") or ""))
    prepared["link_normalized"] = prepared["link"]
    prepared["content_hash"] = content_hash(
        prepared.get("link", ""), prepared.get("judul", ""), prepared.get("media", ""), prepared.get("tanggal_publikasi", "")
    )
    try:
        rows = insert_row("berita", prepared)
    except Exception as exc:
        message = str(exc)
        if "duplicate" in message.casefold() or "berita_link_key" in message.casefold():
            return False, "Tautan tersebut sudah pernah disimpan.", ""
        try:
            legacy = {k: v for k, v in prepared.items() if k in LEGACY_NEWS_COLUMNS}
            rows = insert_row("berita", legacy)
        except Exception:
            return False, f"Gagal menyimpan berita: {message}", ""
    entity_id = str(rows[0].get("id", "")) if rows else ""
    log_action(
        "create", "berita", entity_id, actor_username, actor_role,
        {"link": prepared.get("link"), "source_type": prepared.get("source_type"), "status": prepared.get("status_verifikasi")},
    )
    return True, "Berita berhasil disimpan dan masuk antrean Belum Ditelaah.", entity_id


def update_news(news_id: str, payload: dict, actor_username: str, actor_role: str) -> None:
    prepared = {key: _json_safe(value) for key, value in payload.items()}
    if "link" in prepared:
        prepared["link"] = normalize_url(str(prepared["link"] or ""))
        prepared["link_normalized"] = prepared["link"]
    if any(key in prepared for key in {"link", "judul", "media", "tanggal_publikasi"}):
        current = _current_news(news_id)
        merged = {**current, **prepared}
        prepared["content_hash"] = content_hash(
            str(merged.get("link") or ""),
            str(merged.get("judul") or ""),
            str(merged.get("media") or ""),
            str(merged.get("tanggal_publikasi") or ""),
        )
    update_rows("berita", prepared, "id", news_id)
    log_action("update", "berita", news_id, actor_username, actor_role, {"fields": sorted(prepared)})


def _current_status(news_id: str) -> str:
    db = get_db()
    if db is None:
        return "Belum Ditelaah"
    try:
        response = db.table("berita").select("status_verifikasi").eq("id", news_id).limit(1).execute()
        rows = response.data or []
        return normalize_status(str(rows[0].get("status_verifikasi") or "Belum Ditelaah")) if rows else "Belum Ditelaah"
    except Exception:
        return "Belum Ditelaah"


def change_news_status(
    news_id: str,
    new_status: str,
    note: str,
    actor_username: str,
    actor_role: str,
    reason: str = "",
) -> None:
    new_status = normalize_status(new_status)
    if new_status not in WORKFLOW_STATUSES:
        raise ValueError("Status telaah tidak valid.")
    old_status = normalize_status(_current_status(news_id))
    if old_status == new_status:
        raise ValueError("Status berita sudah sama dengan status tujuan.")
    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise ValueError(f"Perubahan status {old_status} → {new_status} tidak diizinkan.")

    normalized_role = {
        "admin_pusat": "news_analyst",
        "admin_kanwil": "news_analyst",
        "operator_upt": "news_intake",
        "viewer": "executive_viewer",
    }.get(actor_role, actor_role)
    reviewer_action = new_status in {"Terverifikasi", "Perlu Koreksi", "Tidak Valid", "Diarsipkan"}
    restore_action = old_status in {"Tidak Valid", "Diarsipkan"} and new_status == "Belum Ditelaah"
    correction_resubmit = old_status == "Perlu Koreksi" and new_status == "Belum Ditelaah"
    if (reviewer_action or restore_action) and normalized_role not in {"super_admin", "news_analyst"}:
        raise PermissionError("Tindakan ini hanya dapat dilakukan oleh Analis Pemberitaan Strategis atau Administrator Utama Sistem.")
    if new_status == "Perlu Koreksi" and not clean_text(reason or note):
        raise ValueError("Catatan koreksi wajib diisi.")
    if new_status == "Tidak Valid" and not clean_text(reason or note):
        raise ValueError("Alasan tidak valid wajib diisi.")
    if correction_resubmit and normalized_role not in {"super_admin", "news_analyst", "news_intake"}:
        raise PermissionError("Pengajuan ulang koreksi tidak diizinkan untuk peran ini.")

    now = datetime.now(timezone.utc).isoformat()
    payload: dict[str, object] = {
        "status_sebelumnya": old_status,
        "status_verifikasi": new_status,
        "review_note": clean_text(note),
    }
    if new_status == "Belum Ditelaah":
        payload.update({
            "submitted_by": actor_username,
            "submitted_at": now,
            "reviewed_by": None,
            "reviewed_at": None,
            "verified_by": None,
            "verified_at": None,
            "rejection_reason": "",
            "archived_by": None,
            "archived_at": None,
        })
    elif new_status == "Perlu Koreksi":
        payload.update({
            "reviewed_by": actor_username,
            "reviewed_at": now,
            "verified_by": None,
            "verified_at": None,
            "rejection_reason": clean_text(reason or note),
        })
    elif new_status == "Terverifikasi":
        payload.update({
            "reviewed_by": actor_username,
            "reviewed_at": now,
            "verified_by": actor_username,
            "verified_at": now,
            "rejection_reason": "",
            "archived_by": None,
            "archived_at": None,
        })
    elif new_status == "Tidak Valid":
        payload.update({
            "reviewed_by": actor_username,
            "reviewed_at": now,
            "verified_by": None,
            "verified_at": None,
            "rejection_reason": clean_text(reason or note),
        })
    elif new_status == "Diarsipkan":
        payload.update({"archived_by": actor_username, "archived_at": now})

    update_rows("berita", payload, "id", news_id)

    if table_exists("berita_status_history"):
        db = get_db()
        if db is not None:
            try:
                db.table("berita_status_history").insert({
                    "berita_id": news_id,
                    "status_from": old_status,
                    "status_to": new_status,
                    "changed_by": actor_username,
                    "changed_by_role": normalized_role,
                    "note": clean_text(note),
                    "reason": clean_text(reason),
                }).execute()
            except Exception:
                pass
    log_action(
        "status_change", "berita", news_id, actor_username, normalized_role,
        {"from": old_status, "to": new_status, "note": clean_text(note), "reason": clean_text(reason)},
    )


def review_news(news_id: str, status: str, note: str, actor_username: str, actor_role: str) -> None:
    change_news_status(news_id, status, note, actor_username, actor_role)


def archive_news(news_id: str, note: str, actor_username: str, actor_role: str) -> None:
    change_news_status(news_id, "Diarsipkan", note, actor_username, actor_role)
