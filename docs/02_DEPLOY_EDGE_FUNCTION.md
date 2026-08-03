# 2. Deploy Edge Function sheet-sync

## Melalui Supabase Dashboard

1. Buka proyek Supabase.
2. Masuk ke **Edge Functions** dan buat fungsi baru bernama `sheet-sync`.
3. Salin isi `supabase/functions/sheet-sync/index.ts` ke editor fungsi.
4. Deploy fungsi dengan JWT verification/non-public authentication bawaan dimatikan. Fungsi tetap terlindungi oleh header `x-sync-token`.
5. Buka menu **Edge Function Secrets** dan isi:

```text
GOOGLE_SERVICE_ACCOUNT_EMAIL
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY
GOOGLE_SPREADSHEET_ID
GOOGLE_SHEET_NAME
GOOGLE_SHEET_RANGE
SHEET_SYNC_TOKEN
```

Nilai yang digunakan:

```text
GOOGLE_SPREADSHEET_ID = 1uAA7KfJVnsgUbhKDKfsnYwDYtOEkN1rgsXahbnxPy54
GOOGLE_SHEET_NAME = Sheet1
GOOGLE_SHEET_RANGE = Sheet1!A:I
```

Untuk `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY`, tempel seluruh nilai private key dari JSON, termasuk BEGIN/END PRIVATE KEY. Supabase menyimpannya sebagai secret.

`SHEET_SYNC_TOKEN` dibuat sendiri berupa teks acak panjang. Nilai yang sama dipakai di Cron dan Streamlit Secrets.

## Melalui Supabase CLI

```bash
supabase functions deploy sheet-sync --no-verify-jwt
supabase secrets set GOOGLE_SERVICE_ACCOUNT_EMAIL="..."
supabase secrets set GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY="..."
supabase secrets set GOOGLE_SPREADSHEET_ID="1uAA7KfJVnsgUbhKDKfsnYwDYtOEkN1rgsXahbnxPy54"
supabase secrets set GOOGLE_SHEET_NAME="Sheet1"
supabase secrets set GOOGLE_SHEET_RANGE="Sheet1!A:I"
supabase secrets set SHEET_SYNC_TOKEN="TOKEN_ACAK_PANJANG"
```
