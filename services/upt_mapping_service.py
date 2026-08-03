from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any

import pandas as pd

from services.audit_service import log_action
from services.database import update_rows

_GENERIC_WORDS = {
    "kelas", "i", "ii", "iia", "iib", "iii", "negara", "lembaga",
    "pemasyarakatan", "rumah", "tahanan", "khusus", "anak", "perempuan",
    "narkotika", "terbuka", "balai", "pembinaan", "penempatan", "sementara",
}


@dataclass(frozen=True)
class MappingSuggestion:
    nama_upt: str
    confidence: float
    reason: str


def _normalize(value: Any) -> str:
    text = str(value or "").casefold()
    replacements = {
        "lapas": "lembaga pemasyarakatan",
        "rutan": "rumah tahanan negara",
        "lpka": "lembaga pembinaan khusus anak",
        "bapas": "balai pemasyarakatan",
        "karutan": "rumah tahanan negara",
        "kalapas": "lembaga pemasyarakatan",
    }
    for old, new in replacements.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _tokens(value: Any) -> set[str]:
    return {token for token in _normalize(value).split() if len(token) > 2 and token not in _GENERIC_WORDS}


def suggest_upt(text: str, upt_df: pd.DataFrame, limit: int = 5) -> list[MappingSuggestion]:
    if upt_df.empty or not str(text or "").strip():
        return []
    haystack = _normalize(text)
    haystack_tokens = _tokens(haystack)
    suggestions: list[MappingSuggestion] = []
    for name in upt_df.get("nama_upt", pd.Series(dtype=str)).dropna().astype(str).unique():
        norm_name = _normalize(name)
        name_tokens = _tokens(norm_name)
        if not norm_name:
            continue
        exact = norm_name in haystack
        overlap = len(haystack_tokens & name_tokens) / max(len(name_tokens), 1)
        sequence = SequenceMatcher(None, norm_name, haystack).ratio()
        location_tokens = [t for t in name_tokens if t not in _GENERIC_WORDS]
        location_hit = bool(location_tokens) and any(re.search(rf"\b{re.escape(t)}\b", haystack) for t in location_tokens)
        score = 1.0 if exact else min(0.99, overlap * 0.72 + sequence * 0.18 + (0.10 if location_hit else 0))
        if score < 0.35:
            continue
        reason = "Nama UPT ditemukan utuh dalam teks" if exact else "Kemiripan nama, jenis UPT, dan lokasi"
        suggestions.append(MappingSuggestion(name, round(score, 3), reason))
    suggestions.sort(key=lambda item: item.confidence, reverse=True)
    return suggestions[:limit]


def news_text(row: pd.Series | dict[str, Any]) -> str:
    parts = [
        row.get("judul"), row.get("ringkasan"), row.get("raw_analysis"),
        row.get("caption_manual"), row.get("catatan"), row.get("media"),
    ]
    return " ".join(str(part or "") for part in parts)


def apply_mapping(
    news_id: str,
    nama_upt: str,
    actor_username: str,
    actor_role: str,
    method: str = "manual",
    confidence: float | None = None,
) -> None:
    payload = {
        "nama_upt": nama_upt,
        "catatan": f"UPT dipetakan melalui {method}." + (f" Confidence {confidence:.0%}." if confidence is not None else ""),
    }
    update_rows("berita", payload, "id", news_id)
    log_action(
        "map_upt",
        "berita",
        news_id,
        actor_username,
        actor_role,
        {"nama_upt": nama_upt, "method": method, "confidence": confidence},
    )
