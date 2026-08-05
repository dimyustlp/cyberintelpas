# Uji Penerimaan CYBER-INTELPAS V6.0

## Persiapan

1. Backup database dan folder aplikasi.
2. Jalankan migrasi V6.
3. Pasang seluruh file V6.
4. Pastikan aplikasi dapat dijalankan tanpa traceback.

## Uji Peran

### Pimpinan Pengambil Keputusan

- Briefing menampilkan berita hari ini, negatif, urgensi, keputusan tertunda, dan tindak lanjut terlambat.
- Menu Keputusan Pimpinan dapat dibuka.
- Keputusan mengubah status kasus dan rekomendasi.
- Disposisi menghasilkan tugas pada halaman Tindak Lanjut.
- Data mentah dan konfigurasi sistem tidak dapat diubah.

### Analis Intelijen Pemberitaan

- Briefing menampilkan berita belum ditelaah, UPT belum terpetakan, dan kasus dalam telaah.
- Publikasi berbeda dapat dihubungkan ke satu Kasus Intelijen.
- Link identik tetap ditolak oleh database.
- Draf laporan mingguan dapat dibuat dan diedit.

### Operator Akuisisi dan Validasi Data

- Briefing menampilkan data masuk, metadata kosong, kandidat duplikat, dan kegagalan sinkronisasi.
- Operator tetap dapat memakai menu input dan sinkronisasi lama.
- Operator tidak dapat mengesahkan analisis atau keputusan pimpinan.

### Petugas Verifikasi Lapangan

- Hanya penugasan miliknya yang tampil.
- Status penugasan dapat diperbarui.
- Laporan cepat dan laporan lengkap dapat dikirim.
- JPG, PNG, dan PDF dapat diunggah ke bucket field-evidence.
- Tugas tindak lanjut yang ditujukan kepadanya dapat diperbarui.

### Analis Evaluasi dan Rekomendasi

- Laporan lapangan dapat dibaca.
- Matriks narasi media dan fakta dapat disimpan.
- Penilaian lima dimensi, akar masalah, analisis akhir, dan rekomendasi dapat dibuat.
- Tindak lanjut dan progres dapat dipantau.

### Administrator Utama

- Seluruh menu dapat dibuka.
- Peran pengguna dapat diubah.
- Administrator Utama terakhir tidak dapat diturunkan perannya.
- Kesehatan Sistem menampilkan komponen normal, peringatan, dan kritis.
- Audit mencatat perubahan peran dan tindakan penting V6.

## Uji Tren

1. Masukkan dua berita dengan isu sama, media berbeda, dan link berbeda.
2. Pastikan keduanya dihitung sebagai dua publikasi.
3. Masukkan link sama dengan parameter utm atau fbclid berbeda.
4. Pastikan hanya satu publikasi yang dihitung.
5. Masukkan berita dengan UPT Belum Teridentifikasi.
6. Pastikan berita tetap tersimpan, tetapi tidak masuk peringkat UPT.
7. Pastikan jumlah publikasi tidak disebut sebagai jumlah kejadian.

## Uji Laporan

1. Pilih periode tujuh hari.
2. Buat draf laporan.
3. Pastikan angka pada narasi sama dengan kartu KPI dan tabel.
4. Unduh PDF, Word, dan PowerPoint.
5. Buka ketiga file dan pastikan tidak rusak.
6. Ubah status laporan melalui tahapan yang tersedia.
7. Pastikan AI gagal tidak membuat halaman laporan berhenti, karena fallback lokal tetap berjalan.

## Kriteria Lulus

- Tidak ada traceback.
- Tidak ada data lama yang hilang.
- Hak akses setiap peran sesuai tupoksi.
- Link identik tidak dihitung ulang.
- Bukti dan laporan terhubung pada kasus yang benar.
- Keputusan, tugas, progres, dan audit dapat ditelusuri.
