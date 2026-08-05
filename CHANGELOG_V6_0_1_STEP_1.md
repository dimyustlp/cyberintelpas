# CYBER-INTELPAS V6.0.1 — Step 1

Tanggal: 5 Agustus 2026

## Fokus
Stabilisasi hak akses, kompatibilitas akun lama, dan aktivasi navigasi modul V6.

## Perubahan utama
- Menyatukan kode enam peran resmi CYBER-INTELPAS dengan alias peran V4/V5.
- Memulihkan fungsi `can_edit_news` dan dua pola `require_permission`.
- Memperbaiki urutan konstruktor `UserContext` agar akun lama tidak terbaca sebagai peran yang salah.
- Membatasi Operator Akuisisi dan Validasi Data hanya pada berita miliknya.
- Mengaktifkan verifikasi berita untuk peran `media_intelligence_analyst`.
- Memetakan permission lama seperti `view_warning`, `view_data`, `use_ai`, dan `export_reports` ke permission V6.
- Menyambungkan Briefing Harian, Tren Mingguan, Kasus Intelijen, Laporan Intelijen, Keputusan Pimpinan, Verifikasi Lapangan, Evaluasi dan Rekomendasi, Tindak Lanjut, Manajemen Peran, serta Kesehatan Sistem.
- Menyamakan `app.py` dan `streamlit_app.py` sebagai entry point yang identik.
- Mempertahankan cakupan Kanwil dan UPT saat sesi pengguna dinormalisasi.
- Menyimpan `assigned_kanwil` dan `assigned_upt` ketika akun dibuat atau diperbarui.
- Menambahkan pengaturan cakupan Kantor Wilayah dan UPT pada halaman Manajemen Pengguna.
- Membuat layanan database tetap dapat masuk mode demo ketika library Supabase belum terpasang.
- Memperbaiki penyaringan data Pimpinan setelah nama peran dinormalisasi.

## Hasil pengujian
- Kompilasi Python: lulus.
- Unit dan regression test: 42 lulus, 0 gagal.
- `app.py` dan `streamlit_app.py`: identik.

## Belum termasuk Step 1
- Penyempurnaan klasifikasi kontekstual berita.
- Validasi koordinat seluruh UPT.
- Integrasi crawler, Telegram, dan pembacaan video media sosial.
- Pengujian langsung terhadap database Supabase produksi.
