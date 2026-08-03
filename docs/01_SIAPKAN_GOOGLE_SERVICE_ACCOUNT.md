# 1. Menyiapkan Google Service Account

1. Buka Google Cloud Console dan buat atau pilih satu proyek khusus CyberIntelPAS.
2. Aktifkan **Google Sheets API**.
3. Buka **IAM & Admin → Service Accounts** lalu buat akun layanan, misalnya `cyberintelpas-sheet-reader`.
4. Buat key JSON untuk service account tersebut dan unduh satu kali.
5. Dari file JSON, siapkan hanya nilai `client_email` dan `private_key` untuk Supabase Edge Function Secrets.
6. Buka Google Spreadsheet sumber, klik **Bagikan**, lalu masukkan `client_email` service account sebagai **Viewer**.
7. Jangan memberi Editor karena layanan sinkronisasi hanya memerlukan akses baca.

Jangan mengirim file JSON ke chat, GitHub, atau Streamlit Secrets.
