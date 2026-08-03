# SIMBERPAS Enterprise V4.1

Redesign modular Executive Dashboard untuk Sistem Monitoring Berita Pemasyarakatan.

## Fitur utama

- UI/UX full-screen yang responsif untuk laptop dan tablet.
- Struktur modular: `pages/`, `components/`, `services/`, `styles/`.
- Dashboard KPI, tren, sentimen, platform, kategori, prioritas, dan top UPT.
- Peta Indonesia dengan filter Provinsi → Kanwil → UPT.
- Executive Summary dan AI Assistant.
- Fallback analitik lokal ketika API AI belum dikonfigurasi.
- Hak akses: Super Admin, Admin Pusat, Admin Kanwil, Operator UPT, Viewer.
- Audit log aktivitas.
- Tema Light/Dark menggunakan sistem tema Streamlit.
- Kompatibilitas dengan tabel `upt` dan `berita` versi lama.

## Migrasi aman dari aplikasi lama

1. Jangan hapus folder aplikasi lama.
2. Ekstrak ZIP ini ke folder baru, misalnya:
   `C:\Users\user\Documents\FILE\SIMBERPAS_Enterprise_V4`
3. Salin file rahasia lama:
   `.streamlit\secrets.toml`
   ke folder `.streamlit` proyek baru.
4. Buka Supabase → SQL Editor.
5. Salin seluruh isi `sql/migration_v4_enterprise.sql`, lalu klik **Run**.
6. Instal pustaka:
   `python -m pip install -r requirements.txt`
7. Jalankan:
   `python -m streamlit run streamlit_app.py`
8. Masuk memakai `ACCESS_CODE` lama. Akun ini otomatis memperoleh hak Super Admin dalam mode kompatibilitas.
9. Buka **Manajemen Pengguna** untuk membuat akun bertingkat.
10. Buka **Pengaturan** dan impor `data/upt_enterprise_template.csv` untuk menambahkan data provinsi.

## Peta Indonesia

Peta langsung dapat menampilkan agregasi provinsi setelah kolom provinsi diimpor. Titik UPT yang presisi memerlukan latitude dan longitude. Jika koordinat belum tersedia, sistem memakai pusat provinsi dan memberi label `Pusat provinsi` agar tidak dianggap sebagai lokasi pasti UPT.

## AI

Tanpa API AI, Executive Summary dan Assistant tetap bekerja memakai analitik lokal. Untuk mengaktifkan model AI, isi `OPENAI_API_KEY` dan `OPENAI_MODEL` pada `.streamlit/secrets.toml`.

## Keamanan

- Jangan unggah `.streamlit/secrets.toml` ke GitHub.
- Gunakan `SUPABASE_KEY` secret/service-role hanya pada Streamlit server-side.
- Setelah akun bertingkat dibuat dan diuji, ACCESS_CODE lama dapat diganti atau dikosongkan.
