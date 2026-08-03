# 3. Mengaktifkan Supabase Cron

Cron memanggil Edge Function setiap lima menit. URL dan token disimpan terenkripsi melalui Supabase Vault.

1. Pastikan fungsi `sheet-sync` sudah berhasil dites manual.
2. Buka `sql/setup_v5_5_cron_template.sql`.
3. Ganti `PROJECT_REF_ANDA` dengan project reference Supabase.
4. Ganti `TOKEN_SINKRONISASI_ANDA` dengan nilai `SHEET_SYNC_TOKEN` yang sama.
5. Jalankan melalui SQL Editor.
6. Pastikan hasil menampilkan job aktif bernama `cyberintelpas-sheet-sync-every-5-minutes`.
7. Riwayat eksekusi dapat diperiksa melalui menu **Cron → Jobs → History** pada Supabase.

Jangan menjalankan template berulang tanpa memperhatikan secret Vault. Jika nama secret sudah ada, hapus atau perbarui melalui menu Vault terlebih dahulu.
