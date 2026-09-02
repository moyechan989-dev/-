-- 기준선 전용 migration입니다.
-- 원격 프로젝트(rebhrlcgcavvruhbfqsp)에는 아래 테이블 정의가 SQL Editor로 이미 적용되었습니다.
-- 기존 원격에는 이 파일을 실행하거나 db push로 적용하지 말고, migration repair로 이 버전만
-- applied 상태로 등록합니다. 새 빈 프로젝트에서는 다음 migration과 함께 전체 스키마를 구성할 수 있습니다.

create table if not exists public.companies (
    company_id text primary key,
    permit_number text not null,
    company_name text not null,
    company_name_normalized text not null,
    address text,
    address_normalized text,
    district text,
    industry text,
    entity_type text not null,
    is_2026_target text not null,
    planned_inspection_type text,
    manager_alias text,
    air_scale text,
    water_scale text,
    air_grade text,
    water_grade text,
    target_media_waste text,
    source_tags text,
    source_record_count integer,
    major_complaint_note text,
    manual_inspection_note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.company_aliases (
    alias_id bigint generated always as identity primary key,
    company_id text not null,
    alias_type text not null,
    alias_value text not null,
    normalized_value text,
    source text not null,
    is_primary text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.inspections (
    inspection_id text primary key,
    company_id text not null,
    company_name text not null,
    inspection_date date,
    inspection_date_raw text,
    inspection_type text not null,
    inspection_media text not null,
    inspection_result_status text not null,
    inspection_result_detail text,
    key_findings text,
    suspected_violation text,
    on_site_action text,
    follow_up_action text,
    inspector_alias text,
    manager_alias text,
    review_status text not null,
    source_file text,
    source_sheet text,
    source_row integer,
    match_method text,
    match_score numeric,
    inspection_purpose text,
    correction_due_date date,
    next_check_points text,
    data_source text not null default 'legacy_csv',
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.dispositions (
    disposition_id text primary key,
    company_id text not null,
    company_name text not null,
    inspection_date date,
    disposition_date date not null,
    violation_content text not null,
    legal_basis text,
    administrative_disposition text,
    accusation text,
    penalty text,
    violation_category text,
    representative_alias text,
    source_media text not null,
    disposition_status text not null,
    source_file text,
    source_sheet text,
    source_row integer,
    match_method text,
    match_score numeric,
    note text,
    data_source text not null default 'legacy_csv',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.company_notes (
    note_id uuid primary key default gen_random_uuid(),
    company_id text not null,
    note_date date not null default current_date,
    note_type text not null,
    content text not null,
    status text not null default 'active',
    related_inspection_id text,
    created_by_alias text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    is_active boolean not null default true
);

create table if not exists public.report_imports (
    report_id uuid primary key default gen_random_uuid(),
    original_filename text not null,
    file_hash text not null,
    uploaded_at timestamptz not null default now(),
    report_status text not null default 'uploaded',
    detected_company_count integer not null default 0,
    review_status text not null default 'pending',
    error_message text,
    created_at timestamptz not null default now()
);

create table if not exists public.report_items (
    report_item_id uuid primary key default gen_random_uuid(),
    report_id uuid not null,
    company_id text,
    item_order integer not null,
    extracted_company_name text,
    extracted_permit_number text,
    extracted_inspection_date date,
    extracted_data jsonb not null default '{}'::jsonb,
    disposition_reference_status text not null default 'not_mentioned',
    disposition_review_needed boolean not null default false,
    disposition_candidate_type text,
    disposition_candidate_date date,
    disposition_candidate_details text,
    disposition_candidate_legal_basis text,
    review_status text not null default 'pending',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
