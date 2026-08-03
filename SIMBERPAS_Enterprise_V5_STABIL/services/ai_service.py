from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from services.analytics_service import deterministic_summary, rule_based_answer
from services.config import get_config


def _client():
    cfg = get_config()
    if not cfg.has_openai:
        return None
    from openai import OpenAI
    return OpenAI(api_key=cfg.openai_api_key)


def _extract_json(text: str) -> dict[str, Any]:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?", "", clean, flags=re.I).strip()
    clean = re.sub(r"```$", "", clean).strip()
    match = re.search(r"\{.*\}", clean, flags=re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def analyze_news_with_ai(extracted: dict[str, str], manual_text: str) -> dict[str, Any]:
    client = _client()
    cfg = get_config()
    if client is None:
        return {}
    prompt = f"""
Analisis berita Pemasyarakatan berikut. Kembalikan JSON murni tanpa markdown dengan keys:
kategori, subkategori, sentimen, urgensi, tingkat_perhatian, ringkasan, kata_kunci, lokasi, ai_confidence.
Nilai sentimen: Positif|Netral|Negatif. Urgensi: Rendah|Sedang|Tinggi.
Kategori utama: Keamanan dan Ketertiban|Pembinaan|Pelayanan|SDM|Sarana dan Prasarana|Kehumasan|Lainnya.
ai_confidence angka 0 sampai 1.

Judul: {extracted.get('judul','')}
Ringkasan halaman: {extracted.get('ringkasan','')}
Teks tambahan: {manual_text}
"""
    response = client.responses.create(
        model=cfg.openai_model,
        instructions="Anda adalah analis media Pemasyarakatan Indonesia. Jawab akurat, singkat, dan hanya berdasarkan teks yang diberikan.",
        input=prompt,
    )
    data = _extract_json(response.output_text)
    if not data:
        return {}
    data["ai_provider"] = f"openai:{cfg.openai_model}"
    return data


def executive_summary(df: pd.DataFrame) -> tuple[str, str, str, str]:
    fallback_summary, attention, recommendation = deterministic_summary(df)
    client = _client()
    cfg = get_config()
    if client is None or df.empty:
        return fallback_summary, attention, recommendation, "Analitik otomatis"
    context = {
        "total": len(df),
        "sentimen": df["sentimen"].value_counts().to_dict(),
        "urgensi": df["urgensi"].value_counts().to_dict(),
        "kategori": df["kategori"].value_counts().head(8).to_dict(),
        "platform": df["platform"].value_counts().head(8).to_dict(),
        "upt": df["nama_upt"].value_counts().head(10).to_dict(),
        "judul_prioritas": df[(df["sentimen"] == "Negatif") | (df["urgensi"] == "Tinggi")]["judul"].head(8).tolist(),
    }
    response = client.responses.create(
        model=cfg.openai_model,
        instructions=(
            "Anda adalah analis eksekutif Pemasyarakatan. Buat briefing Bahasa Indonesia maksimal 120 kata. "
            "Jangan menambah fakta di luar data. Sertakan tingkat perhatian RENDAH/SEDANG/TINGGI dan satu rekomendasi."
        ),
        input=json.dumps(context, ensure_ascii=False),
    )
    text = response.output_text.strip()
    if not text:
        return fallback_summary, attention, recommendation, "Analitik otomatis"
    return text, attention, recommendation, f"AI • {cfg.openai_model}"


def assistant_answer(question: str, df: pd.DataFrame) -> tuple[str, str]:
    client = _client()
    cfg = get_config()
    if client is None:
        return rule_based_answer(question, df), "Analitik lokal"
    context = {
        "total": len(df),
        "sentimen": df["sentimen"].value_counts().to_dict(),
        "urgensi": df["urgensi"].value_counts().to_dict(),
        "kategori": df["kategori"].value_counts().head(10).to_dict(),
        "platform": df["platform"].value_counts().head(10).to_dict(),
        "upt": df["nama_upt"].value_counts().head(15).to_dict(),
        "berita_prioritas": df[(df["sentimen"] == "Negatif") | (df["urgensi"] == "Tinggi")][["judul", "nama_upt", "urgensi", "sentimen"]].head(20).to_dict("records"),
    }
    response = client.responses.create(
        model=cfg.openai_model,
        instructions=(
            "Jawab sebagai AI Assistant SIMBERPAS. Gunakan hanya konteks data yang diberikan. "
            "Jawab dalam Bahasa Indonesia, ringkas, gunakan angka, dan nyatakan bila data tidak cukup."
        ),
        input=f"PERTANYAAN:\n{question}\n\nKONTEKS DATA:\n{json.dumps(context, ensure_ascii=False)}",
    )
    return response.output_text.strip(), f"AI • {cfg.openai_model}"
