-- ============================================================================
-- SIMBERPAS V5.3 — INTERNAL PUSAT & EARLY WARNING
-- Jalankan melalui Supabase > SQL Editor sebelum menggunakan kode V5.3.
-- Migrasi bersifat aditif dan tidak menghapus berita, UPT, akun, atau audit.
-- Sinkronisasi Google Spreadsheet BELUM termasuk dalam rilis ini.
-- ============================================================================

create extension if not exists pgcrypto;

-- --------------------------------------------------------------------------
-- 1. MASTER UPT DAN KOORDINAT
-- --------------------------------------------------------------------------
alter table public.upt add column if not exists jenis_upt text;
alter table public.upt add column if not exists kelas_upt text;
alter table public.upt add column if not exists subjenis_upt text;
alter table public.upt add column if not exists provinsi text;
alter table public.upt add column if not exists kanwil text;
alter table public.upt add column if not exists kabupaten_kota text;
alter table public.upt add column if not exists alamat text;
alter table public.upt add column if not exists latitude double precision;
alter table public.upt add column if not exists longitude double precision;
alter table public.upt add column if not exists coordinate_quality text default 'Belum tersedia';
alter table public.upt add column if not exists coordinate_source text;
alter table public.upt add column if not exists coordinate_score numeric(5,3);
alter table public.upt add column if not exists coordinate_verified_at timestamptz;
alter table public.upt add column if not exists coordinate_verified_by text;
alter table public.upt add column if not exists aktif boolean not null default true;
alter table public.upt add column if not exists catatan_verifikasi text;
alter table public.upt add column if not exists updated_at timestamptz not null default now();

update public.upt
set coordinate_quality = 'Belum tersedia'
where coordinate_quality is null or btrim(coordinate_quality) = '';

-- --------------------------------------------------------------------------
-- 2. BERITA, TELAAH INTERNAL, DUPLIKAT, SUMBER, DAN ARSIP
-- --------------------------------------------------------------------------
alter table public.berita add column if not exists updated_at timestamptz not null default now();
alter table public.berita add column if not exists status_verifikasi text;
alter table public.berita alter column status_verifikasi set default 'Belum Ditelaah';
alter table public.berita add column if not exists status_sebelumnya text;
alter table public.berita add column if not exists created_by text;
alter table public.berita add column if not exists submitted_by text;
alter table public.berita add column if not exists submitted_at timestamptz;
alter table public.berita add column if not exists reviewed_by text;
alter table public.berita add column if not exists reviewed_at timestamptz;
alter table public.berita add column if not exists verified_by text;
alter table public.berita add column if not exists verified_at timestamptz;
alter table public.berita add column if not exists review_note text;
alter table public.berita add column if not exists rejection_reason text;
alter table public.berita add column if not exists archived_by text;
alter table public.berita add column if not exists archived_at timestamptz;
alter table public.berita add column if not exists deleted_by text;
alter table public.berita add column if not exists deleted_at timestamptz;

alter table public.berita add column if not exists link_normalized text;
alter table public.berita add column if not exists content_hash text;
alter table public.berita add column if not exists source_type text not null default 'manual';
alter table public.berita add column if not exists source_external_id text;
alter table public.berita add column if not exists duplicate_relation text;
alter table public.berita add column if not exists duplicate_of text;

alter table public.berita add column if not exists dampak text default 'UPT';
alter table public.berita add column if not exists kata_kunci text[];
alter table public.berita add column if not exists lokasi text;
alter table public.berita add column if not exists tingkat_perhatian text default 'Rendah';
alter table public.berita add column if not exists ai_provider text default 'rules';
alter table public.berita add column if not exists ai_confidence numeric(4,3);

-- Konversi alur berjenjang lama menjadi alur telaah internal pusat.
update public.berita
set status_verifikasi = case
    when status_verifikasi in ('Draft', 'Diajukan', 'Sedang Diperiksa') then 'Belum Ditelaah'
    when status_verifikasi = 'Perlu Perbaikan' then 'Perlu Koreksi'
    when status_verifikasi = 'Ditolak' then 'Tidak Valid'
    when status_verifikasi is null or btrim(status_verifikasi) = '' then 'Belum Ditelaah'
    else status_verifikasi
end;

alter table public.berita alter column status_verifikasi set not null;

update public.berita
set source_type = 'manual'
where source_type is null or btrim(source_type) = '';

update public.berita
set link_normalized = link
where (link_normalized is null or btrim(link_normalized) = '')
  and link is not null;

-- --------------------------------------------------------------------------
-- 3. EMPAT PERAN INTERNAL PUSAT
-- --------------------------------------------------------------------------
create table if not exists public.app_users (
    id uuid primary key default gen_random_uuid(),
    username text not null unique,
    password_hash text not null,
    full_name text not null,
    role text not null,
    assigned_kanwil text,
    assigned_upt text,
    aktif boolean not null default true,
    last_login timestamptz,
    password_changed_at timestamptz,
    deleted_at timestamptz,
    deleted_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.app_users add column if not exists assigned_kanwil text;
alter table public.app_users add column if not exists assigned_upt text;
alter table public.app_users add column if not exists aktif boolean not null default true;
alter table public.app_users add column if not exists last_login timestamptz;
alter table public.app_users add column if not exists password_changed_at timestamptz;
alter table public.app_users add column if not exists deleted_at timestamptz;
alter table public.app_users add column if not exists deleted_by text;
alter table public.app_users add column if not exists created_at timestamptz not null default now();
alter table public.app_users add column if not exists updated_at timestamptz not null default now();

-- Hapus constraint lama jika pernah dibuat dengan lima peran wilayah.
alter table public.app_users drop constraint if exists app_users_role_check;

update public.app_users
set role = case
    when role in ('admin_pusat', 'admin_kanwil') then 'news_analyst'
    when role = 'operator_upt' then 'news_intake'
    when role = 'viewer' then 'executive_viewer'
    when role in ('super_admin', 'news_analyst', 'news_intake', 'executive_viewer') then role
    else 'executive_viewer'
end,
assigned_kanwil = null,
assigned_upt = null;

alter table public.app_users
    add constraint app_users_role_check
    check (role in ('super_admin', 'news_analyst', 'news_intake', 'executive_viewer'));

create unique index if not exists app_users_username_lower_idx
    on public.app_users (lower(username));

-- --------------------------------------------------------------------------
-- 4. AUDIT AKTIVITAS
-- --------------------------------------------------------------------------
create table if not exists public.audit_log (
    id bigint generated by default as identity primary key,
    created_at timestamptz not null default now(),
    actor_username text not null,
    actor_role text not null,
    action text not null,
    entity text not null,
    entity_id text,
    metadata jsonb not null default '{}'::jsonb
);

-- --------------------------------------------------------------------------
-- 5. RIWAYAT STATUS BERITA
-- --------------------------------------------------------------------------
create table if not exists public.berita_status_history (
    id bigint generated by default as identity primary key,
    berita_id text not null,
    status_from text,
    status_to text not null,
    changed_by text not null,
    changed_by_role text not null,
    note text,
    reason text,
    created_at timestamptz not null default now()
);

-- --------------------------------------------------------------------------
-- 6. BUKTI/LAMPIRAN BERITA (SOFT DELETE)
-- --------------------------------------------------------------------------
create table if not exists public.berita_attachments (
    id uuid primary key default gen_random_uuid(),
    berita_id text not null,
    file_name text not null,
    storage_path text not null,
    mime_type text not null,
    size_bytes bigint not null default 0,
    description text,
    uploaded_by text not null,
    created_at timestamptz not null default now(),
    deleted_at timestamptz,
    deleted_by text
);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'berita-bukti',
    'berita-bukti',
    false,
    10485760,
    array['image/jpeg','image/png','application/pdf']::text[]
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- --------------------------------------------------------------------------
-- 7. INDEX KINERJA
-- --------------------------------------------------------------------------
create index if not exists upt_nama_upt_lower_idx on public.upt (lower(nama_upt));
create index if not exists upt_provinsi_idx on public.upt (provinsi);
create index if not exists upt_kanwil_idx on public.upt (kanwil);
create index if not exists upt_coordinate_quality_idx on public.upt (coordinate_quality);
create index if not exists upt_aktif_idx on public.upt (aktif);

create index if not exists berita_status_verifikasi_idx on public.berita (status_verifikasi);
create index if not exists berita_urgensi_idx on public.berita (urgensi);
create index if not exists berita_sentimen_idx on public.berita (sentimen);
create index if not exists berita_nama_upt_idx on public.berita (nama_upt);
create index if not exists berita_created_at_idx on public.berita (created_at desc);
create index if not exists berita_verified_at_idx on public.berita (verified_at desc);
create index if not exists berita_link_normalized_idx on public.berita (link_normalized);
create index if not exists berita_content_hash_idx on public.berita (content_hash);
create index if not exists berita_source_type_idx on public.berita (source_type);
create index if not exists berita_deleted_at_idx on public.berita (deleted_at);

create index if not exists app_users_deleted_at_idx on public.app_users (deleted_at);
create index if not exists app_users_role_idx on public.app_users (role);

create index if not exists audit_log_created_at_idx on public.audit_log (created_at desc);
create index if not exists audit_log_actor_idx on public.audit_log (actor_username);
create index if not exists audit_log_entity_idx on public.audit_log (entity, entity_id);

create index if not exists berita_status_history_berita_idx
    on public.berita_status_history (berita_id, created_at desc);
create index if not exists berita_attachments_berita_idx
    on public.berita_attachments (berita_id, created_at desc);
create index if not exists berita_attachments_deleted_idx
    on public.berita_attachments (deleted_at);

-- --------------------------------------------------------------------------
-- 8. UPDATED_AT TRIGGERS
-- --------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_upt_updated_at on public.upt;
create trigger trg_upt_updated_at
before update on public.upt
for each row execute function public.set_updated_at();

drop trigger if exists trg_berita_updated_at on public.berita;
create trigger trg_berita_updated_at
before update on public.berita
for each row execute function public.set_updated_at();

drop trigger if exists trg_app_users_updated_at on public.app_users;
create trigger trg_app_users_updated_at
before update on public.app_users
for each row execute function public.set_updated_at();

-- --------------------------------------------------------------------------
-- 9. RLS DAN SERVICE ROLE
-- --------------------------------------------------------------------------
alter table public.upt enable row level security;
alter table public.berita enable row level security;
alter table public.app_users enable row level security;
alter table public.audit_log enable row level security;
alter table public.berita_status_history enable row level security;
alter table public.berita_attachments enable row level security;

grant all on public.upt to service_role;
grant all on public.berita to service_role;
grant all on public.app_users to service_role;
grant all on public.audit_log to service_role;
grant all on public.berita_status_history to service_role;
grant all on public.berita_attachments to service_role;
grant usage, select on all sequences in schema public to service_role;

-- Paksa PostgREST memperbarui schema cache agar kolom baru langsung terbaca.
notify pgrst, 'reload schema';

-- --------------------------------------------------------------------------
-- 10. HASIL PEMERIKSAAN
-- Semua nilai pada kolom *_ok harus bernilai true.
-- --------------------------------------------------------------------------
select
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='upt' and column_name='alamat') as upt_alamat_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='upt' and column_name='latitude') as upt_latitude_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='upt' and column_name='longitude') as upt_longitude_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='review_note') as berita_review_note_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='status_verifikasi') as berita_status_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='app_users' and column_name='role') as app_users_role_ok,
    (select count(*) = 0 from public.app_users where role not in ('super_admin','news_analyst','news_intake','executive_viewer')) as role_data_ok,
    (select count(*) = 0 from public.berita where status_verifikasi in ('Draft','Diajukan','Sedang Diperiksa','Perlu Perbaikan','Ditolak')) as status_data_ok;
