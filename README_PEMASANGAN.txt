CYBER-INTELPAS V6.0
ROLE-BASED INTELLIGENCE, CASE WORKFLOW & WEEKLY REPORT
======================================================

PENTING
-------
1. Sinkronisasi Spreadsheet dan Cron yang sudah berhasil tidak diubah oleh paket ini.
2. Paket ini merupakan pembaruan aditif di atas CYBER-INTELPAS V5.7.
3. Data berita, UPT, akun, lampiran, audit, dan log sinkronisasi tidak dihapus.
4. Jangan menghapus folder .git atau file .streamlit\secrets.toml.
5. Cadangkan folder proyek dan database sebelum pemasangan.

FITUR YANG DIBUAT
-----------------
1. Briefing dan reminder berbeda setelah login untuk enam peran.
2. Ringkasan khusus Pimpinan Pengambil Keputusan.
3. Kotak kerja khusus Analis Intelijen Pemberitaan.
4. Kotak kerja khusus Operator Akuisisi dan Validasi Data.
5. System Operations Center untuk Administrator Utama.
6. Tren mingguan per UPT berdasarkan link unik.
7. Pemisahan jumlah publikasi, media, UPT, dan kelompok isu.
8. Kasus Intelijen yang menghubungkan banyak publikasi pada satu isu.
9. Penugasan, laporan, dan bukti Verifikasi Lapangan.
10. Analisis Evaluasi dan Rekomendasi.
11. Keputusan dan disposisi pimpinan.
12. Tindak lanjut, reminder tenggat, dan progres pekerjaan.
13. Laporan mingguan dengan AI serta ekspor PDF, Word, dan PowerPoint.
14. Enam nama peran dan tupoksi final.
15. Audit aktivitas untuk tindakan penting pada modul V6.

ENAM PERAN FINAL
----------------
1. Pimpinan Pengambil Keputusan
2. Analis Intelijen Pemberitaan
3. Operator Akuisisi dan Validasi Data
4. Petugas Verifikasi Lapangan
5. Analis Evaluasi dan Rekomendasi
6. Administrator Utama CYBER-INTELPAS

URUTAN PEMASANGAN
-----------------
1. Hentikan aplikasi lokal dengan Ctrl+C.
2. Cadangkan folder proyek aktif.
3. Cadangkan database Supabase.
4. Buka Supabase > SQL Editor > New query.
5. Jalankan:
   sql\migration_v6_role_intelligence.sql
6. Pastikan seluruh hasil *_ok bernilai true dan role_invalid_count bernilai 0.
7. Salin folder components, services, pages, dan scripts dari paket ke proyek aktif.
8. Pilih Replace untuk services\access_control.py.
9. Jangan mengganti .streamlit\secrets.toml.
10. Tambahkan integrasi pada app.py memakai salah satu cara berikut:
    a. Jalankan PASANG_PATCH_APP_WINDOWS.bat, lalu tempel alamat folder proyek aktif.
    b. Ikuti docs\PATCH_APP_PY.md secara manual.
11. Gabungkan requirements_v6.txt ke requirements.txt proyek aktif.
12. Jalankan:
    py -m pip install -r requirements.txt
13. Jalankan:
    py -m streamlit run app.py
14. Login sebagai Administrator Utama CYBER-INTELPAS.
15. Buka Manajemen Peran dan tetapkan akun sesuai tupoksi.
16. Buka Kesehatan Sistem dan pastikan komponen utama berstatus Normal.
17. Lakukan uji sesuai docs\UJI_PENERIMAAN.md.

SECRETS
-------
Fitur AI laporan memakai secrets yang sudah dikenal proyek:
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-5-mini"

Bila OPENAI_API_KEY tidak diisi, laporan tetap dibuat memakai narasi lokal.
Tidak ada secret baru yang diwajibkan untuk modul V6.

ATURAN DATA BERITA
------------------
- Satu link_normalized unik sama dengan satu publikasi.
- Link identik atau link yang hanya berbeda parameter pelacakan ditolak.
- Kasus atau isu yang sama boleh memiliki banyak publikasi dari media berbeda.
- Banyak publikasi tidak boleh disebut sebagai banyak kejadian.
- Publikasi tanpa UPT tetap disimpan, tetapi tidak dimasukkan ke peringkat UPT sampai dipetakan.
- AI tidak menghitung angka. Angka dihitung oleh sistem dan dikirim ke AI sebagai payload terkunci.
- Laporan final tetap memerlukan telaah dan pengesahan manusia.

HASIL PENGUJIAN PAKET
----------------------
- Kompilasi seluruh file Python: LULUS
- Unit test: 7 lulus, 0 gagal
- Uji patch otomatis app.py: LULUS
- Uji langsung terhadap Supabase dan Streamlit Cloud tetap dilakukan setelah pemasangan pada proyek nyata.

LAPORAN MINGGUAN OTOMATIS
-------------------------
Paket menyediakan:
.github\workflows\cyberintelpas_weekly_report.yml
scripts\generate_weekly_report.py

Workflow membuat atau memperbarui Draf Sistem setiap Senin pukul 06.00 WIB untuk periode Senin sampai Minggu sebelumnya. Laporan yang sudah Diverifikasi, Disetujui, atau Dipublikasikan tidak ditimpa.

Tambahkan Repository Secrets berikut di GitHub:
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
OPENAI_API_KEY                 opsional
OPENAI_MODEL                   opsional

Jalankan workflow secara manual satu kali melalui GitHub Actions untuk pengujian. Service role hanya disimpan sebagai GitHub Secret dan tidak ditulis ke source code.
