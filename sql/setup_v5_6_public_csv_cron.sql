-- CYBERINTELPAS V5.6 — JADWAL SINKRONISASI CSV PUBLIK SETIAP 5 MENIT
-- Jalankan SETELAH Edge Function `sheet-sync` berhasil diuji manual.
-- Ganti PROJECT_REF dan TOKEN_ACAK_PANJANG sebelum menjalankan.

create extension if not exists pg_cron;
create extension if not exists pg_net;
create extension if not exists supabase_vault;

-- Jalankan hanya sekali untuk menyimpan nilai. Bila nama secret sudah ada, hapus/ubah dari Vault terlebih dahulu.
select vault.create_secret(
  'https://PROJECT_REF.supabase.co/functions/v1/sheet-sync',
  'cyberintelpas_sheet_sync_url',
  'URL Edge Function sinkronisasi Spreadsheet publik'
);
select vault.create_secret(
  'TOKEN_ACAK_PANJANG',
  'cyberintelpas_sheet_sync_token',
  'Token pemanggilan Edge Function sinkronisasi'
);

-- Hindari jadwal ganda bila script dijalankan ulang.
do $$
begin
  if exists (select 1 from cron.job where jobname = 'cyberintelpas-public-sheet-sync-5m') then
    perform cron.unschedule('cyberintelpas-public-sheet-sync-5m');
  end if;
end $$;

select cron.schedule(
  'cyberintelpas-public-sheet-sync-5m',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='cyberintelpas_sheet_sync_url' limit 1),
    headers := jsonb_build_object(
      'Content-Type','application/json',
      'x-sync-token',(select decrypted_secret from vault.decrypted_secrets where name='cyberintelpas_sheet_sync_token' limit 1),
      'x-trigger-type','scheduled_cron'
    ),
    body := jsonb_build_object('source','supabase_cron','mode','public_csv_read_only')
  );
  $$
);

select jobid, jobname, schedule, active from cron.job where jobname='cyberintelpas-public-sheet-sync-5m';
