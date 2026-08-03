# SIMBERPAS V5.3 — Internal Pusat & Early Warning

SIMBERPAS adalah Sistem Monitoring Berita Pemasyarakatan untuk penggunaan internal pusat Direktorat Jenderal Pemasyarakatan.

## Empat peran resmi

1. **Administrator Utama Sistem** (`super_admin`)
2. **Analis Pemberitaan Strategis** (`news_analyst`)
3. **Operator Akuisisi Data Berita** (`news_intake`)
4. **Pimpinan Eksekutif** (`executive_viewer`)

Kanwil dan UPT tetap digunakan sebagai objek data, filter, statistik, dan lokasi peta. Kanwil/UPT tidak lagi digunakan sebagai pembatas akun.

## Alur telaah internal

```text
Input manual/otomatis
→ Belum Ditelaah
→ Terverifikasi / Perlu Koreksi / Tidak Valid
→ Diarsipkan
```

Berita dengan urgensi Tinggi/Kritis langsung menghasilkan **Peringatan Awal — Belum Ditelaah**. Setelah diverifikasi analis, statusnya menjadi **Peringatan Terverifikasi**.

## Fitur utama

- Dashboard eksekutif dan Early Warning.
- Menu Warning News.
- Menu Pusat Telaah khusus analis.
- Input terpisah berdasarkan peran.
- Operator input tidak dapat mengubah analisis final.
- Peta 492 UPT dengan status warna dan tanda peringatan awal.
- Verifikasi internal pusat yang sederhana.
- Deteksi duplikat dasar.
- Bukti JPG, PNG, dan PDF.
- Audit aktivitas.
- Manajemen akun dengan soft delete/arsip.
- AI Assistant berbasis database internal.
- Ekspor Excel dan CSV.

## Sinkronisasi Google Spreadsheet

Belum disertakan dalam rilis ini. Struktur aplikasi telah mempertahankan `source_type` agar sinkronisasi dapat ditambahkan kemudian tanpa mengubah alur manual.

## Instalasi pembaruan

Gunakan petunjuk `PETUNJUK_UPDATE_V5_3_INTERNAL_PUSAT.txt`.

## Keamanan

- Jangan unggah `.streamlit/secrets.toml` ke GitHub.
- Jangan membagikan `SUPABASE_KEY`, `OPENAI_API_KEY`, kode akses, atau kata sandi.
- Gunakan service-role key hanya pada server Streamlit.
- Lakukan pencadangan database dan folder aplikasi sebelum migrasi.


## V5.6 Public CSV Sync

Sumber Spreadsheet dibaca read-only dari `https://docs.google.com/spreadsheets/d/e/2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft/pub?output=csv` melalui Supabase Edge Function. Tidak membutuhkan service account Google.
