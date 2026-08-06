from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
import pandas as pd

# Impor dari service yang sudah kita bangun sebelumnya
from services.database import fetch_news_df
from services.pdf_report_service import create_daily_pdf_bytes
from services.telegram_service import send_telegram_document, send_telegram_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CyberIntelpasAutoJob")


def run_daily_automated_report():
    """
    Eksekusi otomatis cetak PDF Laporan Harian & kirim ke Telegram Pimpinan.
    Diberlakukan untuk periode 24 jam terakhir (17.00 WIB kemarin - 07.00 WIB hari ini).
    """
    logger.info("Mulai mengeksekusi Laporan Harian Otomatis Cyber-Intelpas...")

    # 1. Tentukan label periode waktu laporan (Sesuai format resmi Ditjenpas)
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    periode_label = (
        f"{yesterday.strftime('%d %B %Y')} (17.00 WIB) - "
        f"{now.strftime('%d %B %Y')} (07.00 WIB)"
    )

    # 2. Ambil seluruh data berita dari database Google Sheets
    df_news = fetch_news_df()
    if df_news.empty:
        logger.warning("Database berita kosong. Mengirimkan notifikasi nihil ke Telegram.")
        send_telegram_message(
            f"🏛️ <b>[LAPORAN HARIAN CYBER-INTELPAS]</b>\n"
            f"📅 <b>Periode:</b> {periode_label}\n\n"
            f"💡 <i>Nihil temuan pemberitaan pada rentang waktu ini.</i>"
        )
        return

    # 3. Filter berita untuk rentang waktu harian (opsional: filter tanggal/status)
    # Jika tabel Anda memiliki kolom 'tanggal_publikasi' atau 'created_at':
    df_filtered = df_news.copy()
    if "status_verifikasi" in df_filtered.columns:
        # Prioritaskan berita yang sudah ditelaah atau tidak ditolak
        df_filtered = df_filtered[df_filtered["status_verifikasi"] != "Ditolak"]

    total = len(df_filtered)
    pos = len(df_filtered[df_filtered["sentimen"] == "Positif"]) if total > 0 else 0
    neg = len(df_filtered[df_filtered["sentimen"] == "Negatif"]) if total > 0 else 0

    # 4. Render PDF Laporan Harian beserta Kliping & QR Code
    logger.info(f"Merender PDF untuk {total} berita ({pos} Positif, {neg} Negatif)...")
    try:
        pdf_bytes = create_daily_pdf_bytes(df_filtered, periode_label)
    except Exception as exc:
        logger.error(f"Gagal merender berkas PDF: {exc}")
        send_telegram_message(f"❌ <b>[SYSTEM ERROR]</b> Gagal merender PDF Laporan Harian: {exc}")
        return

    # 5. Kirim Dokumen PDF ke Telegram Grup Pimpinan
    nama_file = f"Laporan_Harian_CyberIntelpas_{now.strftime('%Y%m%d')}.pdf"
    caption = (
        f"🔴 <b>[LAPORAN HARIAN MONITORING PEMBERITAAN]</b>\n"
        f"📅 <b>Periode:</b> {periode_label}\n"
        f"🏛️ <b>Instansi:</b> Ditjen Pemasyarakatan\n\n"
        f"📊 <b>RINGKASAN STATISTIK:</b>\n"
        f"🔹 <b>Total Berita:</b> {total} Berita\n"
        f"✅ <b>Sentimen Positif:</b> {pos} Berita\n"
        f"🔻 <b>Sentimen Negatif:</b> {neg} Berita\n\n"
        f"📎 <i>Dokumen PDF resmi (Dashboard, Tabel Temuan, Kliping & QR Code) terlampir di atas.</i>"
    )

    berhasil = send_telegram_document(pdf_bytes, nama_file, caption)
    if berhasil:
        logger.info("✅ Sukses mengirim Laporan Harian PDF ke Telegram Pimpinan!")
    else:
        logger.error("❌ Gagal mengirim Laporan Harian PDF ke Telegram.")


if __name__ == "__main__":
    run_daily_automated_report()