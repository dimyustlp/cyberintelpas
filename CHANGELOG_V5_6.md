# CyberIntelPAS V5.6 — Public CSV Sync

## Perubahan

- Google Spreadsheet dibaca dari URL publikasi CSV, tanpa Google Cloud, OAuth, service account, atau key JSON.
- Crawler Apps Script lama tidak disentuh.
- Sinkronisasi hanya membaca data dan tidak pernah menulis kembali ke Spreadsheet.
- Supabase Edge Function menarik data setiap 5 menit melalui Cron.
- Input berita manual tetap berjalan.
- Data baru masuk sebagai `Belum Ditelaah`.
- Risiko Tinggi/Kritis langsung menghasilkan Peringatan Awal.
- Duplikat dicegah menggunakan identitas URL dan content hash.

## URL sumber

- HTML publik: https://docs.google.com/spreadsheets/d/e/2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft/pubhtml
- CSV read-only: https://docs.google.com/spreadsheets/d/e/2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft/pub?output=csv

## Peringatan privasi

Karena sumber telah dipublikasikan ke web, siapa pun yang memperoleh URL publikasi dapat membaca isinya. Jangan menaruh data rahasia atau data pribadi sensitif pada Sheet yang dipublikasikan.
