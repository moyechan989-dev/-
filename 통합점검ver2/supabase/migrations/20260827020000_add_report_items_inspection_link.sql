-- 최종 지도점검과 출장보고서 검토 항목의 감사추적 연결입니다.
-- 기존 report_items 행은 inspection_id NULL 상태로 유지합니다.
-- 기존 데이터는 수정하지 않습니다.

alter table public.report_items
    add column if not exists inspection_id text;

do $$ begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.report_items'::regclass
          and conname = 'report_items_inspection_fk'
    ) then
        alter table public.report_items
            add constraint report_items_inspection_fk
            foreign key (inspection_id)
            references public.inspections (inspection_id)
            on delete set null;
    end if;
end $$;

-- NULL(아직 최종 저장 전) 값은 여러 건 허용하고,
-- 연결된 inspection_id만 하나의 report_item에만 연결합니다.
create unique index if not exists report_items_inspection_id_unique
    on public.report_items (inspection_id)
    where inspection_id is not null;
