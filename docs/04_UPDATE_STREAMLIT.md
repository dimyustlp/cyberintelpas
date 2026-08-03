# 4. Menghubungkan CyberIntelPAS

Tambahkan pada `.streamlit/secrets.toml` lokal dan Streamlit Community Cloud Secrets:

```toml
SHEET_SYNC_TOKEN = "TOKEN_YANG_SAMA"
SHEET_SYNC_FUNCTION_URL = "https://PROJECT_REF.supabase.co/functions/v1/sheet-sync"
GOOGLE_SPREADSHEET_ID = "1uAA7KfJVnsgUbhKDKfsnYwDYtOEkN1rgsXahbnxPy54"
GOOGLE_SHEET_NAME = "Sheet1"
```

Private key Google tidak boleh dimasukkan ke Streamlit. Hanya Edge Function yang menyimpannya.

Setelah Save, reboot aplikasi. Buka **Sinkronisasi Spreadsheet**, lalu klik **Sinkronkan Sekarang** untuk pengujian.
