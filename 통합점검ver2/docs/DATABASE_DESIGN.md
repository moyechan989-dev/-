# 데이터베이스 설계(향후 구현)

## 핵심 테이블

| 테이블 | 키 | 용도 |
| --- | --- | --- |
| `companies` | `company_id` | 업체 마스터. 허가번호, 명칭, 주소, 지역, 업종, 영업상태 등 실제 제공 열만 저장한다. |
| `company_aliases` | `company_id`, 별칭 식별자 | 업체명·허가번호·주소 등의 별칭과 정규화 값을 관리한다. |
| `inspections` | `inspection_id` | 지도점검 일자, 유형, 결과, 지적 내용, 현장·후속 조치 등을 관리한다. |
| `dispositions` | `disposition_id` | 위반 내용과 행정처분 이력을 독립적으로 관리한다. |
| `report_imports` | `report_id` | PDF 업로드·추출의 원본, 상태, 담당자 검토 정보를 보관한다. |
| `report_items` | `report_item_id` | 보고서 안에서 검출한 업체별 후보 항목. 하나의 보고서에 여러 업체가 있을 가능성을 보존한다. |
| `inspection_summaries` | `company_id`, 생성 식별자 | 규칙 기반 지도점검 참고 요약을 캐시한다. |

## 관계와 무결성

- `inspections.company_id`, `dispositions.company_id`, `company_aliases.company_id`, `report_items.company_id`는 `companies.company_id`를 참조한다.
- 점검과 처분은 직접 종속시키지 않는다. 필요 시 `source_*` 정보 또는 검토된 연결 필드로 추적한다.
- 업체를 찾지 못했거나 다수 후보인 PDF 항목은 `report_items.company_id`를 비워 두고 검토 상태를 기록한다.

## 행정처분 후보 필드

`report_items`에는 다음 후보 필드를 둔다: `disposition_reference_status`, `disposition_review_needed`, `disposition_candidate_type`, `disposition_candidate_date`, `disposition_candidate_details`, `disposition_candidate_legal_basis`, `disposition_review_status`.

상태값은 `not_mentioned`, `review_needed`, `confirmed_in_report`, `unclear`를 사용한다. 어느 경우도 담당자 확인 전 자동 확정·등록하지 않는다.

## Supabase 준비 설계

현재 CSV 이름과 ID를 보존하는 것을 최우선으로 한다. `companies.company_id`, `inspections.inspection_id`, `dispositions.disposition_id`는 각각 `text` 기본 키로 사용한다. 시제품용 허가번호는 현재 고유하지만 실제 업무 고유성은 확정되지 않았으므로 고유 제약 대신 조회 인덱스만 둔다.

`companies`는 `01_companies.csv`의 21개 열을 모두 보존한다. `source_tags`, `source_record_count`는 원천 추적에 필요해 유지하고, 내부 수기 메모는 일반 검색·목록 API에서 제외한다.

`company_aliases`는 DB 생성용 `alias_id`를 추가하고 CSV 6개 열을 보존한다. 재가져오기 중복 방지를 위해 `(company_id, alias_type, alias_value, source)`를 자연 고유키로 사용한다.

`inspections`와 `dispositions`는 기존 CSV 열을 이름 변경 없이 보존한다. 향후 입력용 열은 별도 추가하며 기존 열과 무리하게 합치지 않는다. `inspection_date_raw`는 원천 보존용 문자열이고 조회·정렬은 `inspection_date`를 사용한다.

외래키는 모든 이력과 별칭에서 `companies.company_id`를 참조한다. `company_notes.related_inspection_id`는 선택적이며 점검 삭제 시 `null`로 전환한다. `report_items`의 업체 연결도 검토 전에는 비어 있을 수 있다.

시제품 단계에서는 모든 `public` 테이블에 RLS를 활성화하고 `anon`, `authenticated` 권한을 회수한다. 인증·부서·역할 모델이 정해지기 전에는 개방형 정책을 만들지 않는다. PDF의 행정처분 후보는 `report_items`에만 저장하며 담당자 확인만으로도 자동으로 `dispositions`에 등록되지 않는다.

기존 문서의 `inspection_summaries`는 현재 CSV에서 계산 가능한 파생 캐시이므로 이번 SQL에서는 만들지 않는다. 조회 성능 측정 후 필요성이 확인될 때 별도 단계에서 추가한다.
