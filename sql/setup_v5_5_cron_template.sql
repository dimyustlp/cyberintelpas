-- CYBERINTELPAS V5.5 — SETUP CRON AMAN DENGAN SUPABASE VAULT
-- Jalankan SETELAH Edge Function `sheet-sync` berhasil dideploy dan dites manual.
-- Ganti dua placeholder sebelum Run:
--   https://PROJECT_REF_ANDA.supabase.co
--   TOKEN_SINKRONISASI_ANDA

create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net with schema extensions;

-- Simpan URL proyek dan token sinkronisasi dalam Vault terenkripsi.
-- Jika nama secret sudah ada, hapus melalui menu Vault terlebih dahulu atau gunakan nama baru.
select vault.create_secret(
  'https://PROJECT_REF_ANDA.supabase.co',
  'cyberintelpas_project_url',
  'URL proyek untuk Cron sinkronisasi Google Spreadsheet'
);

select vault.create_secret(
  'TOKEN_SINKRONISASI_ANDA',
  'cyberintelpas_sheet_sync_token',
  'Token header x-sync-token untuk Edge Function sheet-sync'
);

-- Hindari job ganda jika pernah dibuat sebelumnya.
do $$
begin
  if exists (select 1 from cron.job where jobname = 'cyberintelpas-sheet-sync-every-5-minutes') then
    perform cron.unschedule('cyberintelpas-sheet-sync-every-5-minutes');
  end if;
end $$;

select cron.schedule(
  'cyberintelpas-sheet-sync-every-5-minutes',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := (
      select decrypted_secret
      from vault.decrypted_secrets
      where name = 'cyberintelpas_project_url'
      limit 1
    ) || '/functions/v1/sheet-sync',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-sync-token', (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'cyberintelpas_sheet_sync_token'
        limit 1
      ),
      'x-trigger-type', 'scheduled'
    ),
    body := jsonb_build_object('source', 'supabase_cron'),
    timeout_milliseconds := 120000
  );
  $$
);

select jobid, jobname, schedule, active
from cron.job
where jobname = 'cyberintelpas-sheet-sync-every-5-minutes';
