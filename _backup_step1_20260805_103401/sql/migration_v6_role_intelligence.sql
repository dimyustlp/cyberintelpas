-- ============================================================================
-- CYBER-INTELPAS V6.0
-- ROLE-BASED INTELLIGENCE BRIEFING, CASE WORKFLOW, FIELD VERIFICATION,
-- EVALUATION, WEEKLY TRENDS, AND REPORT GENERATION
--
-- Aman dijalankan berulang. Bersifat aditif dan tidak menghapus data berita,
-- UPT, akun, lampiran, audit, atau riwayat sinkronisasi yang sudah ada.
-- ============================================================================

begin;

create extension if not exists pgcrypto;

-- --------------------------------------------------------------------------
-- 1. ENAM PERAN FINAL DAN KOMPATIBILITAS DENGAN V5.x
-- --------------------------------------------------------------------------
alter table public.app_users drop constraint if exists app_users_role_check;

create or replace function public.normalize_cyberintelpas_role()
returns trigger
language plpgsql
as $$
begin
    new.role := case new.role
        when 'executive_viewer' then 'executive_decision_maker'
        when 'pimpinan_eksekutif' then 'executive_decision_maker'
        when 'news_analyst' then 'media_intelligence_analyst'
        when 'analis_pemberitaan_strategis' then 'media_intelligence_analyst'
        when 'news_intake' then 'news_data_operator'
        when 'operator_akuisisi_data_berita' then 'news_data_operator'
        when 'petugas_verifikasi_lapangan' then 'field_verification_officer'
        when 'analis_evaluasi_rekomendasi' then 'evaluation_recommendation_analyst'
        when 'administrator_utama_sistem' then 'super_admin'
        when 'admin_pusat' then 'media_intelligence_analyst'
        when 'admin_kanwil' then 'media_intelligence_analyst'
        when 'operator_upt' then 'news_data_operator'
        when 'viewer' then 'executive_decision_maker'
        else new.role
    end;
    return new;
end;
$$;

drop trigger if exists trg_normalize_cyberintelpas_role on public.app_users;
create trigger trg_normalize_cyberintelpas_role
before insert or update of role on public.app_users
for each row execute function public.normalize_cyberintelpas_role();

update public.app_users
set role = case role
    when 'executive_viewer' then 'executive_decision_maker'
    when 'pimpinan_eksekutif' then 'executive_decision_maker'
    when 'news_analyst' then 'media_intelligence_analyst'
    when 'analis_pemberitaan_strategis' then 'media_intelligence_analyst'
    when 'news_intake' then 'news_data_operator'
    when 'operator_akuisisi_data_berita' then 'news_data_operator'
    when 'petugas_verifikasi_lapangan' then 'field_verification_officer'
    when 'analis_evaluasi_rekomendasi' then 'evaluation_recommendation_analyst'
    when 'administrator_utama_sistem' then 'super_admin'
    when 'admin_pusat' then 'media_intelligence_analyst'
    when 'admin_kanwil' then 'media_intelligence_analyst'
    when 'operator_upt' then 'news_data_operator'
    when 'viewer' then 'executive_decision_maker'
    else role
end;

alter table public.app_users
    add constraint app_users_role_check
    check (role in (
        'executive_decision_maker',
        'media_intelligence_analyst',
        'news_data_operator',
        'field_verification_officer',
        'evaluation_recommendation_analyst',
        'super_admin'
    ));

-- --------------------------------------------------------------------------
-- 2. PENGUATAN DATA BERITA DAN ATURAN LINK UNIK
-- --------------------------------------------------------------------------
alter table public.berita add column if not exists case_id uuid;
alter table public.berita add column if not exists issue_group_key text;
alter table public.berita add column if not exists actuality_status text default 'Tidak Dapat Dipastikan';
alter table public.berita add column if not exists incident_date date;
alter table public.berita add column if not exists duplicate_checked_at timestamptz;
alter table public.berita add column if not exists duplicate_checked_by text;

create index if not exists berita_case_id_idx on public.berita(case_id);
create index if not exists berita_issue_group_key_idx on public.berita(issue_group_key);
create index if not exists berita_actuality_status_idx on public.berita(actuality_status);

-- Menolak link_normalized yang sama pada input baru, tanpa menggagalkan migrasi
-- apabila data lama ternyata sudah memiliki duplikat.
create or replace function public.prevent_duplicate_news_link()
returns trigger
language plpgsql
as $$
declare
    duplicate_id text;
begin
    if new.link_normalized is null or btrim(new.link_normalized) = '' then
        return new;
    end if;

    select b.id::text
    into duplicate_id
    from public.berita b
    where lower(btrim(b.link_normalized)) = lower(btrim(new.link_normalized))
      and b.deleted_at is null
      and (tg_op = 'INSERT' or b.id::text <> new.id::text)
    limit 1;

    if duplicate_id is not null then
        raise exception using
            errcode = '23505',
            message = 'Link berita sudah pernah disimpan.',
            detail = 'duplicate_berita_id=' || duplicate_id,
            hint = 'Gunakan publikasi dengan link berbeda. Kesamaan isu diperbolehkan, tetapi link identik ditolak.';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_prevent_duplicate_news_link on public.berita;
create trigger trg_prevent_duplicate_news_link
before insert or update of link_normalized on public.berita
for each row execute function public.prevent_duplicate_news_link();

-- --------------------------------------------------------------------------
-- 3. KASUS INTELIJEN DAN RELASI PUBLIKASI
-- --------------------------------------------------------------------------
create sequence if not exists public.intelligence_case_number_seq start 1;

create or replace function public.next_intelligence_case_number()
returns text
language sql
volatile
as $$
    select 'CI-' || to_char(current_date, 'YYYY') || '-' || lpad(nextval('public.intelligence_case_number_seq')::text, 5, '0');
$$;

create table if not exists public.intelligence_cases (
    id uuid primary key default gen_random_uuid(),
    case_number text not null unique default public.next_intelligence_case_number(),
    title text not null,
    issue_type text not null default 'Lainnya',
    primary_upt text not null default 'Belum Teridentifikasi',
    status text not null default 'Terdeteksi',
    priority text not null default 'Sedang',
    actuality_status text not null default 'Tidak Dapat Dipastikan',
    first_detected_at timestamptz,
    last_media_at timestamptz,
    article_count integer not null default 0,
    media_count integer not null default 0,
    negative_count integer not null default 0,
    highest_urgency text not null default 'Rendah',
    summary text,
    owner_username text,
    created_by text not null,
    updated_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    closed_at timestamptz,
    reopened_at timestamptz,
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.case_news (
    id bigint generated by default as identity primary key,
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    berita_id text not null,
    linked_by text not null,
    created_at timestamptz not null default now(),
    unique(case_id, berita_id)
);

create index if not exists intelligence_cases_status_idx on public.intelligence_cases(status);
create index if not exists intelligence_cases_priority_idx on public.intelligence_cases(priority);
create index if not exists intelligence_cases_upt_idx on public.intelligence_cases(primary_upt);
create index if not exists intelligence_cases_updated_idx on public.intelligence_cases(updated_at desc);
create index if not exists case_news_case_idx on public.case_news(case_id);
create index if not exists case_news_berita_idx on public.case_news(berita_id);

-- --------------------------------------------------------------------------
-- 4. PENUGASAN DAN LAPORAN VERIFIKASI LAPANGAN
-- --------------------------------------------------------------------------
create sequence if not exists public.field_assignment_number_seq start 1;

create or replace function public.next_field_assignment_number()
returns text
language sql
volatile
as $$
    select 'TL-' || to_char(current_date, 'YYYY') || '-' || lpad(nextval('public.field_assignment_number_seq')::text, 5, '0');
$$;

create table if not exists public.field_assignments (
    id uuid primary key default gen_random_uuid(),
    assignment_number text not null unique default public.next_field_assignment_number(),
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    assigned_to text not null,
    assigned_team text not null default 'Tim Verifikasi Lapangan',
    instruction text,
    verification_questions jsonb not null default '[]'::jsonb,
    priority text not null default 'Sedang',
    status text not null default 'Ditugaskan',
    assigned_by text not null,
    assigned_at timestamptz not null default now(),
    accepted_at timestamptz,
    due_at timestamptz,
    completed_at timestamptz,
    updated_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.field_reports (
    id uuid primary key default gen_random_uuid(),
    assignment_id uuid not null references public.field_assignments(id) on delete cascade,
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    report_type text not null default 'Laporan Lengkap',
    visit_started_at timestamptz,
    visit_finished_at timestamptz,
    officers jsonb not null default '[]'::jsonb,
    parties_met jsonb not null default '[]'::jsonb,
    activity_summary text,
    facts_found text,
    upt_explanation text,
    documents_checked jsonb not null default '[]'::jsonb,
    obstacles text,
    immediate_actions text,
    upt_commitments text,
    commitment_due_at date,
    finding_classification text not null default 'Belum dapat disimpulkan',
    initial_conclusion text,
    status text not null default 'Dikirim',
    submitted_by text not null,
    submitted_at timestamptz not null default now(),
    reviewed_by text,
    reviewed_at timestamptz,
    review_note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.field_evidence (
    id uuid primary key default gen_random_uuid(),
    report_id uuid not null references public.field_reports(id) on delete cascade,
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    file_name text not null,
    storage_path text not null unique,
    mime_type text not null,
    size_bytes bigint not null default 0,
    description text,
    evidence_type text default 'Dokumen Pendukung',
    verification_status text not null default 'Belum Diverifikasi',
    uploaded_by text not null,
    created_at timestamptz not null default now(),
    verified_by text,
    verified_at timestamptz,
    deleted_at timestamptz,
    deleted_by text
);

create index if not exists field_assignments_case_idx on public.field_assignments(case_id);
create index if not exists field_assignments_assigned_to_idx on public.field_assignments(assigned_to);
create index if not exists field_assignments_status_idx on public.field_assignments(status);
create index if not exists field_assignments_due_idx on public.field_assignments(due_at);
create index if not exists field_reports_case_idx on public.field_reports(case_id);
create index if not exists field_reports_assignment_idx on public.field_reports(assignment_id);
create index if not exists field_evidence_report_idx on public.field_evidence(report_id);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'field-evidence',
    'field-evidence',
    false,
    15728640,
    array['image/jpeg','image/png','application/pdf']::text[]
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- --------------------------------------------------------------------------
-- 5. ANALISIS EVALUASI, REKOMENDASI, DAN TINDAK LANJ
-- --------------------------------------------------------------------------
create table if not exists public.case_analyses (
    id uuid primary key default gen_random_uuid(),
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    analysis_version integer not null default 1,
    media_narrative text,
    field_facts text,
    comparison_matrix jsonb not null default '[]'::jsonb,
    information_validity text not null default 'Belum terverifikasi',
    reputation_impact text not null default 'Sedang',
    operational_impact text not null default 'Terbatas',
    compliance_impact text not null default 'Perlu pemeriksaan',
    media_escalation_risk text not null default 'Stabil',
    root_causes jsonb not null default '[]'::jsonb,
    final_analysis text,
    follow_up_assessment text not null default 'Belum Dapat Dinilai',
    status text not null default 'Draf',
    created_by text not null,
    created_at timestamptz not null default now(),
    verified_by text,
    verified_at timestamptz,
    unique(case_id, analysis_version)
);

create table if not exists public.case_recommendations (
    id uuid primary key default gen_random_uuid(),
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    analysis_id uuid references public.case_analyses(id) on delete set null,
    recommendation_type text not null,
    recommendation text not null,
    responsible_party text,
    priority text not null default 'Sedang',
    due_at date,
    status text not null default 'Diusulkan',
    progress_percent integer not null default 0 check (progress_percent between 0 and 100),
    created_by text not null,
    created_at timestamptz not null default now(),
    decided_by text,
    decided_at timestamptz,
    decision_note text,
    completed_at timestamptz
);

create table if not exists public.case_decisions (
    id uuid primary key default gen_random_uuid(),
    case_id uuid not null references public.intelligence_cases(id) on delete cascade,
    decision text not null,
    decision_note text,
    recommendation_ids jsonb not null default '[]'::jsonb,
    decided_by text not null,
    decided_at timestamptz not null default now()
);

create table if not exists public.action_items (
    id uuid primary key default gen_random_uuid(),
    case_id uuid references public.intelligence_cases(id) on delete cascade,
    recommendation_id uuid references public.case_recommendations(id) on delete set null,
    title text not null,
    description text,
    assigned_role text,
    assigned_to text,
    priority text not null default 'Sedang',
    status text not null default 'Belum Dimulai',
    due_at timestamptz,
    progress_percent integer not null default 0 check (progress_percent between 0 and 100),
    created_by text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    last_reminded_at timestamptz
);

create index if not exists case_analyses_case_idx on public.case_analyses(case_id, created_at desc);
create index if not exists case_recommendations_case_idx on public.case_recommendations(case_id, created_at desc);
create index if not exists case_recommendations_status_idx on public.case_recommendations(status);
create index if not exists case_decisions_case_idx on public.case_decisions(case_id, decided_at desc);
create index if not exists action_items_role_idx on public.action_items(assigned_role);
create index if not exists action_items_user_idx on public.action_items(assigned_to);
create index if not exists action_items_due_idx on public.action_items(due_at);
create index if not exists action_items_status_idx on public.action_items(status);

-- --------------------------------------------------------------------------
-- 6. LAPORAN INTELIJEN MINGGUAN DAN SNAPSHOT DATA
-- --------------------------------------------------------------------------
create sequence if not exists public.weekly_report_number_seq start 1;

create or replace function public.next_weekly_report_number()
returns text
language sql
volatile
as $$
    select 'LIPM-' || to_char(current_date, 'YYYY') || '-' || lpad(nextval('public.weekly_report_number_seq')::text, 5, '0');
$$;

create table if not exists public.weekly_reports (
    id uuid primary key default gen_random_uuid(),
    report_number text not null unique default public.next_weekly_report_number(),
    period_start date not null,
    period_end date not null,
    status text not null default 'Draf Sistem',
    snapshot_data jsonb not null default '{}'::jsonb,
    ai_narrative jsonb not null default '{}'::jsonb,
    ai_provider text,
    template_version text not null default 'v6.0',
    created_by text not null,
    created_at timestamptz not null default now(),
    updated_by text,
    updated_at timestamptz not null default now(),
    verified_by text,
    verified_at timestamptz,
    approved_by text,
    approved_at timestamptz,
    published_by text,
    published_at timestamptz,
    locked_at timestamptz,
    unique(period_start, period_end, created_at)
);

create table if not exists public.report_exports (
    id uuid primary key default gen_random_uuid(),
    report_id uuid references public.weekly_reports(id) on delete cascade,
    export_format text not null,
    storage_path text,
    file_name text,
    size_bytes bigint,
    generated_by text not null,
    generated_at timestamptz not null default now(),
    status text not null default 'Berhasil',
    error_detail text
);

create index if not exists weekly_reports_period_idx on public.weekly_reports(period_start, period_end);
create index if not exists weekly_reports_status_idx on public.weekly_reports(status);
create index if not exists weekly_reports_created_idx on public.weekly_reports(created_at desc);
create index if not exists report_exports_report_idx on public.report_exports(report_id);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'intel-reports',
    'intel-reports',
    false,
    26214400,
    array[
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ]::text[]
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- --------------------------------------------------------------------------
-- 7. BRIEFING ACKNOWLEDGEMENT DAN KESEHATAN SISTEM
-- --------------------------------------------------------------------------
create table if not exists public.briefing_acknowledgements (
    id uuid primary key default gen_random_uuid(),
    username text not null,
    role text not null,
    briefing_date date not null default current_date,
    briefing_version text not null default 'v6.0',
    acknowledged_at timestamptz not null default now(),
    unique(username, role, briefing_date, briefing_version)
);

create table if not exists public.system_health_events (
    id bigint generated by default as identity primary key,
    component text not null,
    status text not null,
    message text not null,
    detail text,
    detected_at timestamptz not null default now(),
    resolved_at timestamptz,
    resolved_by text,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists briefing_ack_user_idx on public.briefing_acknowledgements(username, briefing_date desc);
create index if not exists system_health_status_idx on public.system_health_events(status, detected_at desc);

-- RPC dibaca oleh halaman Administrator. Dynamic SQL mencegah error apabila
-- schema cron belum terpasang pada proyek lain.
create or replace function public.cyberintelpas_system_health()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    cron_installed boolean := false;
    sheet_sync_cron_active boolean := false;
begin
    select exists(
        select 1 from pg_extension where extname = 'pg_cron'
    ) into cron_installed;

    if cron_installed then
        begin
            execute 'select exists(select 1 from cron.job where jobname = ''sheet-sync-auto'' and active = true)'
            into sheet_sync_cron_active;
        exception when others then
            sheet_sync_cron_active := false;
        end;
    end if;

    return jsonb_build_object(
        'cron_installed', cron_installed,
        'sheet_sync_cron_active', sheet_sync_cron_active,
        'checked_at', now()
    );
end;
$$;

grant execute on function public.cyberintelpas_system_health() to service_role;

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

drop trigger if exists trg_intelligence_cases_updated_at on public.intelligence_cases;
create trigger trg_intelligence_cases_updated_at
before update on public.intelligence_cases
for each row execute function public.set_updated_at();

drop trigger if exists trg_field_assignments_updated_at on public.field_assignments;
create trigger trg_field_assignments_updated_at
before update on public.field_assignments
for each row execute function public.set_updated_at();

drop trigger if exists trg_field_reports_updated_at on public.field_reports;
create trigger trg_field_reports_updated_at
before update on public.field_reports
for each row execute function public.set_updated_at();

drop trigger if exists trg_action_items_updated_at on public.action_items;
create trigger trg_action_items_updated_at
before update on public.action_items
for each row execute function public.set_updated_at();

drop trigger if exists trg_weekly_reports_updated_at on public.weekly_reports;
create trigger trg_weekly_reports_updated_at
before update on public.weekly_reports
for each row execute function public.set_updated_at();

-- --------------------------------------------------------------------------
-- 9. RLS DAN SERVICE ROLE
-- --------------------------------------------------------------------------
alter table public.intelligence_cases enable row level security;
alter table public.case_news enable row level security;
alter table public.field_assignments enable row level security;
alter table public.field_reports enable row level security;
alter table public.field_evidence enable row level security;
alter table public.case_analyses enable row level security;
alter table public.case_recommendations enable row level security;
alter table public.case_decisions enable row level security;
alter table public.action_items enable row level security;
alter table public.weekly_reports enable row level security;
alter table public.report_exports enable row level security;
alter table public.briefing_acknowledgements enable row level security;
alter table public.system_health_events enable row level security;

grant all on public.intelligence_cases to service_role;
grant all on public.case_news to service_role;
grant all on public.field_assignments to service_role;
grant all on public.field_reports to service_role;
grant all on public.field_evidence to service_role;
grant all on public.case_analyses to service_role;
grant all on public.case_recommendations to service_role;
grant all on public.case_decisions to service_role;
grant all on public.action_items to service_role;
grant all on public.weekly_reports to service_role;
grant all on public.report_exports to service_role;
grant all on public.briefing_acknowledgements to service_role;
grant all on public.system_health_events to service_role;
grant usage, select on all sequences in schema public to service_role;

notify pgrst, 'reload schema';

commit;

-- --------------------------------------------------------------------------
-- 10. HASIL PEMERIKSAAN
-- Semua nilai *_ok harus true dan role_invalid_count harus 0.
-- --------------------------------------------------------------------------
select
    to_regclass('public.intelligence_cases') is not null as intelligence_cases_ok,
    to_regclass('public.field_assignments') is not null as field_assignments_ok,
    to_regclass('public.field_reports') is not null as field_reports_ok,
    to_regclass('public.case_analyses') is not null as case_analyses_ok,
    to_regclass('public.case_decisions') is not null as case_decisions_ok,
    to_regclass('public.weekly_reports') is not null as weekly_reports_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='case_id') as berita_case_id_ok,
    exists(select 1 from information_schema.columns where table_schema='public' and table_name='berita' and column_name='actuality_status') as actuality_status_ok,
    (
        select count(*)
        from public.app_users
        where role not in (
            'executive_decision_maker',
            'media_intelligence_analyst',
            'news_data_operator',
            'field_verification_officer',
            'evaluation_recommendation_analyst',
            'super_admin'
        )
    ) as role_invalid_count;
