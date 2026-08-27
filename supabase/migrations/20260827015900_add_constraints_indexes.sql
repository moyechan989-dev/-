-- 기존 SQL Editor 기준선 뒤에 적용할 제약조건과 일반 검색 인덱스입니다.
-- DROP, DELETE, TRUNCATE를 포함하지 않으며, 이미 존재하는 동일 제약조건/인덱스는 건너뜁니다.

-- company_aliases_natural_key는 UNIQUE 제약조건의 backing index 이름입니다.
-- 같은 이름의 기존 고유 인덱스가 정확히 동일한 정의일 때만 해당 인덱스를 제약조건으로 연결합니다.
do $$
declare
    relation_kind "char";
begin
    if exists (
        select 1 from pg_constraint
        where conrelid = 'public.company_aliases'::regclass
          and conname = 'company_aliases_natural_key'
    ) then
        return;
    end if;

    select relkind into relation_kind
    from pg_class
    where oid = to_regclass('public.company_aliases_natural_key');

    if relation_kind is null then
        alter table public.company_aliases
            add constraint company_aliases_natural_key
            unique (company_id, alias_type, alias_value, source);
    elsif relation_kind = 'i' and exists (
        select 1
        from pg_index index_definition
        where index_definition.indexrelid = 'public.company_aliases_natural_key'::regclass
          and index_definition.indrelid = 'public.company_aliases'::regclass
          and index_definition.indisunique
          and index_definition.indisvalid
          and index_definition.indpred is null
          and index_definition.indexprs is null
          and (
              select array_agg(attribute.attname order by key_column.ordinality)
              from unnest(index_definition.indkey) with ordinality as key_column(attnum, ordinality)
              join pg_attribute attribute
                on attribute.attrelid = index_definition.indrelid
               and attribute.attnum = key_column.attnum
              where key_column.attnum > 0
          ) = array['company_id', 'alias_type', 'alias_value', 'source']::name[]
    ) then
        alter table public.company_aliases
            add constraint company_aliases_natural_key
            unique using index company_aliases_natural_key;
    else
        raise exception using message =
            'company_aliases_natural_key 이름의 기존 객체를 안전하게 재사용할 수 없습니다. 객체를 삭제하지 말고 정의를 확인하세요.';
    end if;
end $$;

-- 기준선에는 foreign key가 없으므로, 원격에 없는 경우에만 보강합니다.
do $$ begin
    if not exists (select 1 from pg_constraint where conrelid = 'public.company_aliases'::regclass and conname = 'company_aliases_company_fk') then
        alter table public.company_aliases add constraint company_aliases_company_fk foreign key (company_id) references public.companies (company_id) on delete restrict;
    end if;
end $$;

do $$ begin
    if not exists (select 1 from pg_constraint where conrelid = 'public.inspections'::regclass and conname = 'inspections_company_fk') then
        alter table public.inspections add constraint inspections_company_fk foreign key (company_id) references public.companies (company_id) on delete restrict;
    end if;
end $$;

do $$ begin
    if not exists (select 1 from pg_constraint where conrelid = 'public.dispositions'::regclass and conname = 'dispositions_company_fk') then
        alter table public.dispositions add constraint dispositions_company_fk foreign key (company_id) references public.companies (company_id) on delete restrict;
    end if;
end $$;

do $$ begin
    if not exists (select 1 from pg_constraint where conrelid = 'public.company_notes'::regclass and conname = 'company_notes_company_fk') then
        alter table public.company_notes add constraint company_notes_company_fk foreign key (company_id) references public.companies (company_id) on delete restrict;
    end if;
    if not exists (select 1 from pg_constraint where conrelid = 'public.company_notes'::regclass and conname = 'company_notes_inspection_fk') then
        alter table public.company_notes add constraint company_notes_inspection_fk foreign key (related_inspection_id) references public.inspections (inspection_id) on delete set null;
    end if;
end $$;

do $$ begin
    if not exists (select 1 from pg_constraint where conrelid = 'public.report_items'::regclass and conname = 'report_items_report_fk') then
        alter table public.report_items add constraint report_items_report_fk foreign key (report_id) references public.report_imports (report_id) on delete cascade;
    end if;
    if not exists (select 1 from pg_constraint where conrelid = 'public.report_items'::regclass and conname = 'report_items_company_fk') then
        alter table public.report_items add constraint report_items_company_fk foreign key (company_id) references public.companies (company_id) on delete set null;
    end if;
end $$;

do $$ begin
    if not exists (select 1 from pg_constraint where conrelid = 'public.company_aliases'::regclass and conname = 'company_aliases_is_primary_check') then
        alter table public.company_aliases add constraint company_aliases_is_primary_check check (is_primary in ('Y', 'N'));
    end if;
    if not exists (select 1 from pg_constraint where conrelid = 'public.companies'::regclass and conname = 'companies_is_2026_target_check') then
        alter table public.companies add constraint companies_is_2026_target_check check (is_2026_target in ('Y', 'N'));
    end if;
    if not exists (select 1 from pg_constraint where conrelid = 'public.report_items'::regclass and conname = 'report_items_disposition_status_check') then
        alter table public.report_items add constraint report_items_disposition_status_check check (disposition_reference_status in ('not_mentioned', 'review_needed', 'confirmed_in_report', 'unclear'));
    end if;
end $$;

-- report_items_order_unique도 기존 동일 이름 인덱스가 있을 때만 안전하게 연결합니다.
do $$
declare
    relation_kind "char";
begin
    if exists (
        select 1 from pg_constraint
        where conrelid = 'public.report_items'::regclass
          and conname = 'report_items_order_unique'
    ) then
        return;
    end if;

    select relkind into relation_kind
    from pg_class
    where oid = to_regclass('public.report_items_order_unique');

    if relation_kind is null then
        alter table public.report_items
            add constraint report_items_order_unique unique (report_id, item_order);
    elsif relation_kind = 'i' and exists (
        select 1
        from pg_index index_definition
        where index_definition.indexrelid = 'public.report_items_order_unique'::regclass
          and index_definition.indrelid = 'public.report_items'::regclass
          and index_definition.indisunique
          and index_definition.indisvalid
          and index_definition.indpred is null
          and index_definition.indexprs is null
          and (
              select array_agg(attribute.attname order by key_column.ordinality)
              from unnest(index_definition.indkey) with ordinality as key_column(attnum, ordinality)
              join pg_attribute attribute
                on attribute.attrelid = index_definition.indrelid
               and attribute.attnum = key_column.attnum
              where key_column.attnum > 0
          ) = array['report_id', 'item_order']::name[]
    ) then
        alter table public.report_items
            add constraint report_items_order_unique
            unique using index report_items_order_unique;
    else
        raise exception using message =
            'report_items_order_unique 이름의 기존 객체를 안전하게 재사용할 수 없습니다. 객체를 삭제하지 말고 정의를 확인하세요.';
    end if;
end $$;

-- 현재 원격에서 이미 켜진 RLS에도 안전하게 다시 적용됩니다.
alter table public.companies enable row level security;
alter table public.company_aliases enable row level security;
alter table public.inspections enable row level security;
alter table public.dispositions enable row level security;
alter table public.company_notes enable row level security;
alter table public.report_imports enable row level security;
alter table public.report_items enable row level security;

revoke all on table public.companies from anon, authenticated;
revoke all on table public.company_aliases from anon, authenticated;
revoke all on table public.inspections from anon, authenticated;
revoke all on table public.dispositions from anon, authenticated;
revoke all on table public.company_notes from anon, authenticated;
revoke all on table public.report_imports from anon, authenticated;
revoke all on table public.report_items from anon, authenticated;
revoke all on sequence public.company_aliases_alias_id_seq from anon, authenticated;

-- 검색·정렬 성능용 일반 인덱스입니다. UNIQUE 제약조건의 backing index는 여기서 만들지 않습니다.
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
