-- 조회 패턴과 외래키를 위한 최소 인덱스입니다.

create index if not exists companies_name_normalized_idx
    on public.companies (company_name_normalized text_pattern_ops);
create index if not exists companies_permit_number_idx
    on public.companies (permit_number);
create index if not exists companies_filter_idx
    on public.companies (district, industry, entity_type, is_2026_target);

create index if not exists company_aliases_normalized_value_idx
    on public.company_aliases (normalized_value text_pattern_ops);

create index if not exists inspections_company_date_idx
    on public.inspections (company_id, inspection_date desc);
create index if not exists dispositions_company_date_idx
    on public.dispositions (company_id, disposition_date desc);
create index if not exists company_notes_company_date_idx
    on public.company_notes (company_id, note_date desc) where is_active;
create index if not exists company_notes_inspection_id_idx
    on public.company_notes (related_inspection_id) where related_inspection_id is not null;
create index if not exists report_items_company_id_idx
    on public.report_items (company_id) where company_id is not null;
