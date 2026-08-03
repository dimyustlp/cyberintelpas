-- CYBERINTELPAS V5.6 — PUBLIC CSV READ-ONLY SYNC
-- Aman dijalankan berulang. Tidak mengubah Google Spreadsheet dan tidak menghapus data lama.

begin;

alter table public.berita add column if not exists source_record_key text;
alter table public.berita add column if not exists source_sheet_id text;
alter table public.berita add column if not exists source_sheet_name text;
alter table public.berita add column if not exists source_row_number integer;
alter table public.berita add column if not exists source_updated_at timestamptz;
alter table public.berita add column if not exists last_synced_at timestamptz;
alter table public.berita add column if not exists sync_status text;
alter table public.berita add column if not exists sync_error text;
alter table public.berita add column if not exists detected_at timestamptz;
alter table public.berita add column if not exists raw_analysis text;
alter table public.berita add column if not exists rekomendasi text;
alter table public.berita add column if not exists status_tindak_lanjut text;
alter table public.berita add column if not exists petugas_respon text;
alter table public.berita add column if not exists waktu_respon timestamptz;

update public.berita
set source_type = coalesce(nullif(source_type, ''), 'manual')
where source_type is null or source_type = '';

update public.berita
set source_record_key = source_type || ':' || source_external_id
where source_record_key is null
  and source_external_id is not null
  and btrim(source_external_id) <> '';

-- Kolom nullable tetap mengizinkan banyak NULL, tetapi nilai sumber eksternal harus unik.
create unique index if not exists berita_source_record_key_unique_idx
on public.berita (source_record_key);

create index if not exists berita_detected_at_idx on public.berita (detected_at desc);
create index if not exists berita_source_type_idx on public.berita (source_type);
create index if not exists berita_sync_status_idx on public.berita (sync_status);

create table if not exists public.sheet_sync_log (
    id uuid primary key default gen_random_uuid(),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    status text not null default 'Berjalan',
    spreadsheet_id text,
    sheet_name text,
    trigger_type text default 'scheduled',
    rows_seen integer not null default 0,
    rows_inserted integer not null default 0,
    rows_updated integer not null default 0,
    rows_skipped integer not null default 0,
    rows_failed integer not null default 0,
    duration_ms integer,
    message text,
    error_detail text,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists sheet_sync_log_started_idx
on public.sheet_sync_log (started_at desc);

alter table public.sheet_sync_log enable row level security;
grant all on public.sheet_sync_log to service_role;

notify pgrst, 'reload schema';

commit;

select
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='source_record_key') as source_record_key_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='source_sheet_id') as source_sheet_id_ok,
    exists(select 1 from information_schema.tables where table_schema='public' and table_name='sheet_sync_log') as sheet_sync_log_ok;
