from __future__ import annotations

import logging
import os
import requests
import streamlit as st

logger = logging.getLogger(__name__)

def get_telegram_config() -> tuple[str | None, str | None]:
    """
    Mengambil Telegram Bot Token dan Chat ID dari Environment Variables (GitHub Actions)
    atau dari st.secrets (jika berjalan di aplikasi web Streamlit).
    """
    # 1. Cek dari Environment Variables (Prioritas untuk GitHub Actions/Server)
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("STREAMLIT_SECRETS_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("STREAMLIT_SECRETS_TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        return bot_token, chat_id

    # 2. Cek dari st.secrets (Untuk aplikasi web Streamlit)
    try:
        bot_token = st.secrets.get("telegram", {}).get("bot_token")
        chat_id = st.secrets.get("telegram", {}).get("chat_id")
        return bot_token, chat_id
    except Exception:
        return None, None


def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Mengirim pesan teks ke grup Telegram monitoring."""
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        logger.warning("Telegram config (bot_token / chat_id) belum diatur atau kosong.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Gagal kirim pesan Telegram: {response.text}")
        return response.status_code == 200
    except Exception as exc:
        logger.error(f"Gagal mengirim pesan Telegram: {exc}")
        return False


def send_telegram_document(
    file_bytes: bytes,
    filename: str,
    caption: str = "",
    parse_mode: str = "HTML",
) -> bool:
    """Mengirim berkas dokumen (PDF) ke grup Telegram monitoring."""
    bot_token, chat_id = get_telegram_config()
    if not bot_token or not chat_id:
        logger.warning("Telegram config (bot_token / chat_id) belum diatur atau kosong.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    files = {
        "document": (filename, file_bytes, "application/pdf")
    }
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        if response.status_code != 200:
            logger.error(f"Gagal kirim dokumen Telegram: {response.text}")
        return response.status_code == 200
    except Exception as exc:
        logger.error(f"Gagal mengirim dokumen Telegram: {exc}")
        return False


def send_breaking_alert_telegram(news_payload: dict) -> bool:
    """Mengirimkan Critical Alert khusus berita berurgensi Tinggi/Kritis atau Sentimen Negatif."""
    upt = news_payload.get("nama_upt", "-")
    judul = news_payload.get("judul", "-")
    media = news_payload.get("media", "-")
    link = news_payload.get("link", "")
    sentimen = news_payload.get("sentimen", "-")
    urgensi = news_payload.get("urgensi", "-")
    ringkasan = news_payload.get("ringkasan", "Tidak ada ringkasan.")

    pesan = f"""
🚨 <b>[CRITICAL INTEL ALERT — CYBER-INTELPAS]</b>

🏛️ <b>UPT:</b> {upt}
📰 <b>Media:</b> {media}
⚡ <b>Sentimen / Urgensi:</b> <b>{sentimen}</b> | <b>{urgensi}</b>

📝 <b>Judul Berita:</b>
<i>{judul}</i>

💡 <b>Ringkasan Kronologi & Bukti:</b>
{ringkasan}

🔗 <a href="{link}">Baca Sumber Asli</a>
    """.strip()

    return send_telegram_message(pesan)