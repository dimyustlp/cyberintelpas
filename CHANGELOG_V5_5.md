# CyberIntelPAS V5.5 — Safe Pull Sync

- Crawler Google Apps Script lama tidak diubah.
- Google Spreadsheet hanya dibaca melalui Google Sheets API.
- Sinkronisasi berjalan pada Supabase Edge Function `sheet-sync`.
- Supabase Cron memanggil fungsi setiap lima menit.
- Tombol manual di aplikasi memanggil Edge Function yang sama.
- Service account Google hanya diberi akses Viewer pada Spreadsheet.
- Input manual tetap aktif.
- Upsert menggunakan `source_record_key` untuk mencegah duplikasi.
- Sinkronisasi mencatat data baru, diperbarui, dilewati, gagal, durasi, serta detail error.
