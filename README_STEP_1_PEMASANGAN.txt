CYBER-INTELPAS V6.0.1 — PETUNJUK PEMASANGAN STEP 1

CARA PALING AMAN
1. Ekstrak ZIP patch ke folder biasa.
2. Klik dua kali PASANG_STEP_1.bat.
3. Tempel lokasi folder proyek, contoh:
   C:\Users\user\Documents\SIMBERPAS\SIMBERPAS_ENTERPRISE
4. Tekan Enter. Installer membuat backup otomatis sebelum menimpa file.
5. Buka CMD di folder proyek lalu jalankan:
   pip install -r requirements.txt
   streamlit run streamlit_app.py

FILE SECRETS TIDAK DISENTUH
Patch tidak membawa dan tidak menimpa .streamlit\secrets.toml.

HASIL YANG HARUS TERLIHAT
- Super Admin melihat seluruh menu lama dan V6.
- Pimpinan melihat Briefing, Tren, Kasus, Laporan, Keputusan, dan Tindak Lanjut.
- Analis Intelijen dapat membuka Pusat Telaah dan mengubah status berita.
- Operator hanya melihat berita yang dibuat sendiri.
- Petugas Lapangan melihat Verifikasi Lapangan dan Tindak Lanjut.
- Analis Evaluasi melihat Evaluasi dan Rekomendasi.

ROLLBACK
Installer menampilkan lokasi folder backup. Untuk kembali, salin isi folder backup ke folder proyek dan timpa file.
