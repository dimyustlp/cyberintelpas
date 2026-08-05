# Patch `app.py` CYBER-INTELPAS V6.0

Paket ini tidak mengganti `app.py` lama agar menu V5.7, sinkronisasi Spreadsheet, Pemetaan UPT, Warning News, dan Audit Aktivitas tetap utuh.

## Cara otomatis di Windows

Jalankan `PASANG_PATCH_APP_WINDOWS.bat`, lalu tempel alamat folder proyek aktif. Script membuat backup `app.py` sebelum mengubahnya. Bila struktur entrypoint berbeda, script berhenti dan perubahan dapat dilakukan dengan langkah manual di bawah.

## 1. Tambahkan dua import

Letakkan bersama import lain pada bagian atas `app.py`:

```python
from components.role_briefing import render_role_briefing
from services.v6_navigation import attach_v6_pages
```

## 2. Tampilkan briefing setelah login

Cari bagian berikut:

```python
render_sidebar_profile(user)
```

Tambahkan satu baris tepat setelahnya:

```python
render_role_briefing(user)
```

Hasilnya:

```python
render_sidebar_profile(user)
render_role_briefing(user)
```

Briefing akan muncul satu kali pada setiap sesi login. Sesudah pengguna menekan **Masuk ke Dashboard**, modal tidak muncul lagi selama sesi tersebut. Menu **Briefing Harian** tetap tersedia untuk dibuka ulang.

## 3. Tambahkan halaman V6 ke navigasi

Cari bagian sesudah seluruh dictionary `pages` dan seluruh penambahan halaman lama selesai, tetapi sebelum:

```python
navigation = st.navigation(...)
```

Tambahkan:

```python
pages = attach_v6_pages(pages, user)
```

Contoh akhir:

```python
if admin_pages:
    pages["Administrasi"] = admin_pages

pages = attach_v6_pages(pages, user)

navigation = st.navigation(pages, position="sidebar", expanded=True)
navigation.run()
```

## 4. Jangan menghapus menu lama

Paket V6 menambah halaman secara aditif. Menu berikut tetap dipertahankan:

- Dashboard
- Warning News
- Peta Indonesia
- AI Assistant
- Input Berita atau Input dan Analisis
- Pusat Telaah
- Pusat Data Berita
- Laporan lama
- Sinkronisasi Spreadsheet
- Pemetaan UPT
- Audit Aktivitas
- Manajemen Pengguna
- Pengaturan

## 5. Access control

Salin file baru `services/access_control.py` ke proyek dan pilih **Replace**. File baru tetap mengenali permission lama, tetapi menambahkan enam peran dan permission modul V6.
