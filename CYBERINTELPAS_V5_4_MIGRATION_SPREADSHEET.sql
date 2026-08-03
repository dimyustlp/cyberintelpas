-- CYBERINTELPAS V5.4 — GOOGLE SPREADSHEET SYNC
-- Aman dijalankan berulang. Tidak menghapus data lama.

begin;

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

create unique index if not exists berita_source_external_unique_idx
on public.berita (source_type, source_external_id)
where source_external_id is not null and btrim(source_external_id) <> '';

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

-- Beri tahu PostgREST agar schema cache segera dimuat ulang.
notify pgrst, 'reload schema';

commit;

select
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='source_sheet_id') as berita_source_sheet_id_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='detected_at') as berita_detected_at_ok,
    exists(select 1 from information_schema.tables where table_schema='public' and table_name='sheet_sync_log') as sheet_sync_log_ok;
