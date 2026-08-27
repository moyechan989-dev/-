# 데이터 매핑

이 문서는 실제 `data/private/input` CSV의 헤더를 기준으로 생성됩니다. 검색·필터는 업체 마스터에 실제 존재하고 업무상 허용된 열만 사용합니다.

## 01_companies.csv

- 행 수: 545
- 열: `company_id`, `permit_number`, `company_name`, `company_name_normalized`, `address`, `address_normalized`, `district`, `industry`, `entity_type`, `is_2026_target`, `planned_inspection_type`, `manager_alias`, `air_scale`, `water_scale`, `air_grade`, `water_grade`, `target_media_waste`, `source_tags`, `source_record_count`, `major_complaint_note`, `manual_inspection_note`

### 열 품질 요약

- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 545건
- `permit_number`: 빈 값 0건, 고유 비어있지 않은 값 545건
- `company_name`: 빈 값 0건, 고유 비어있지 않은 값 540건
- `company_name_normalized`: 빈 값 0건, 고유 비어있지 않은 값 535건
- `address`: 빈 값 1건, 고유 비어있지 않은 값 527건
- `address_normalized`: 빈 값 1건, 고유 비어있지 않은 값 516건
- `district`: 빈 값 5건, 고유 비어있지 않은 값 21건
- `industry`: 빈 값 80건, 고유 비어있지 않은 값 86건
- `entity_type`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `is_2026_target`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `planned_inspection_type`: 빈 값 126건, 고유 비어있지 않은 값 3건
- `manager_alias`: 빈 값 126건, 고유 비어있지 않은 값 24건
- `air_scale`: 빈 값 193건, 고유 비어있지 않은 값 3건
- `water_scale`: 빈 값 302건, 고유 비어있지 않은 값 2건
- `air_grade`: 빈 값 193건, 고유 비어있지 않은 값 3건
- `water_grade`: 빈 값 302건, 고유 비어있지 않은 값 2건
- `target_media_waste`: 빈 값 545건, 고유 비어있지 않은 값 0건
- `source_tags`: 빈 값 0건, 고유 비어있지 않은 값 7건
- `source_record_count`: 빈 값 0건, 고유 비어있지 않은 값 7건
- `major_complaint_note`: 빈 값 545건, 고유 비어있지 않은 값 0건
- `manual_inspection_note`: 빈 값 545건, 고유 비어있지 않은 값 0건

## 02_inspections.csv

- 행 수: 616
- 열: `inspection_id`, `company_id`, `company_name`, `inspection_date`, `inspection_date_raw`, `inspection_type`, `inspection_media`, `inspection_result_status`, `inspection_result_detail`, `key_findings`, `suspected_violation`, `on_site_action`, `follow_up_action`, `inspector_alias`, `manager_alias`, `review_status`, `source_file`, `source_sheet`, `source_row`, `match_method`, `match_score`

### 열 품질 요약

- `inspection_id`: 빈 값 0건, 고유 비어있지 않은 값 616건
- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 314건
- `company_name`: 빈 값 0건, 고유 비어있지 않은 값 314건
- `inspection_date`: 빈 값 14건, 고유 비어있지 않은 값 146건
- `inspection_date_raw`: 빈 값 10건, 고유 비어있지 않은 값 180건
- `inspection_type`: 빈 값 0건, 고유 비어있지 않은 값 5건
- `inspection_media`: 빈 값 0건, 고유 비어있지 않은 값 4건
- `inspection_result_status`: 빈 값 0건, 고유 비어있지 않은 값 5건
- `inspection_result_detail`: 빈 값 0건, 고유 비어있지 않은 값 94건
- `key_findings`: 빈 값 0건, 고유 비어있지 않은 값 94건
- `suspected_violation`: 빈 값 520건, 고유 비어있지 않은 값 36건
- `on_site_action`: 빈 값 616건, 고유 비어있지 않은 값 0건
- `follow_up_action`: 빈 값 616건, 고유 비어있지 않은 값 0건
- `inspector_alias`: 빈 값 287건, 고유 비어있지 않은 값 12건
- `manager_alias`: 빈 값 298건, 고유 비어있지 않은 값 9건
- `review_status`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `source_file`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `source_sheet`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `source_row`: 빈 값 0건, 고유 비어있지 않은 값 548건
- `match_method`: 빈 값 0건, 고유 비어있지 않은 값 5건
- `match_score`: 빈 값 0건, 고유 비어있지 않은 값 13건

## 03_dispositions.csv

- 행 수: 366
- 열: `disposition_id`, `company_id`, `company_name`, `inspection_date`, `disposition_date`, `violation_content`, `legal_basis`, `administrative_disposition`, `accusation`, `penalty`, `violation_category`, `representative_alias`, `source_media`, `disposition_status`, `source_file`, `source_sheet`, `source_row`, `match_method`, `match_score`

### 열 품질 요약

- `disposition_id`: 빈 값 0건, 고유 비어있지 않은 값 366건
- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 231건
- `company_name`: 빈 값 0건, 고유 비어있지 않은 값 231건
- `inspection_date`: 빈 값 7건, 고유 비어있지 않은 값 161건
- `disposition_date`: 빈 값 0건, 고유 비어있지 않은 값 161건
- `violation_content`: 빈 값 0건, 고유 비어있지 않은 값 124건
- `legal_basis`: 빈 값 0건, 고유 비어있지 않은 값 77건
- `administrative_disposition`: 빈 값 129건, 고유 비어있지 않은 값 25건
- `accusation`: 빈 값 264건, 고유 비어있지 않은 값 1건
- `penalty`: 빈 값 197건, 고유 비어있지 않은 값 7건
- `violation_category`: 빈 값 1건, 고유 비어있지 않은 값 10건
- `representative_alias`: 빈 값 73건, 고유 비어있지 않은 값 203건
- `source_media`: 빈 값 0건, 고유 비어있지 않은 값 3건
- `disposition_status`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `source_file`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `source_sheet`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `source_row`: 빈 값 0건, 고유 비어있지 않은 값 306건
- `match_method`: 빈 값 0건, 고유 비어있지 않은 값 5건
- `match_score`: 빈 값 0건, 고유 비어있지 않은 값 4건

## 04_company_aliases.csv

- 행 수: 2371
- 열: `company_id`, `alias_type`, `alias_value`, `normalized_value`, `source`, `is_primary`

### 열 품질 요약

- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 545건
- `alias_type`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `alias_value`: 빈 값 0건, 고유 비어있지 않은 값 2327건
- `normalized_value`: 빈 값 1건, 고유 비어있지 않은 값 1173건
- `source`: 빈 값 0건, 고유 비어있지 않은 값 3건
- `is_primary`: 빈 값 0건, 고유 비어있지 않은 값 2건

## 05_report_import_template.csv

- 행 수: 1
- 열: `report_id`, `upload_filename`, `company_id`, `extracted_company_name`, `inspection_date`, `inspection_type`, `inspection_result_status`, `key_findings`, `suspected_violation`, `on_site_action`, `follow_up_action`, `administrative_review_needed`, `unconfirmed_items`, `source_text_excerpt`, `review_status`, `reviewer_alias`, `reviewed_at`

### 열 품질 요약

- `report_id`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `upload_filename`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `extracted_company_name`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `inspection_date`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `inspection_type`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `inspection_result_status`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `key_findings`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `suspected_violation`: 빈 값 1건, 고유 비어있지 않은 값 0건
- `on_site_action`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `follow_up_action`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `administrative_review_needed`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `unconfirmed_items`: 빈 값 1건, 고유 비어있지 않은 값 0건
- `source_text_excerpt`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `review_status`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `reviewer_alias`: 빈 값 1건, 고유 비어있지 않은 값 0건
- `reviewed_at`: 빈 값 1건, 고유 비어있지 않은 값 0건

## 06_complaint_input_template.csv

- 행 수: 1
- 열: `complaint_id`, `company_id`, `complaint_date`, `complaint_category`, `complaint_summary`, `action_result`, `status`, `is_key_issue`, `note`

### 열 품질 요약

- `complaint_id`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `complaint_date`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `complaint_category`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `complaint_summary`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `action_result`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `status`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `is_key_issue`: 빈 값 0건, 고유 비어있지 않은 값 1건
- `note`: 빈 값 0건, 고유 비어있지 않은 값 1건

## 07_matching_review.csv

- 행 수: 860
- 열: `match_id`, `source`, `source_row`, `source_company_name`, `source_address`, `company_id`, `matched_company_name`, `match_method`, `match_score`, `review_required`

### 열 품질 요약

- `match_id`: 빈 값 0건, 고유 비어있지 않은 값 860건
- `source`: 빈 값 0건, 고유 비어있지 않은 값 3건
- `source_row`: 빈 값 0건, 고유 비어있지 않은 값 860건
- `source_company_name`: 빈 값 0건, 고유 비어있지 않은 값 585건
- `source_address`: 빈 값 1건, 고유 비어있지 않은 값 712건
- `company_id`: 빈 값 0건, 고유 비어있지 않은 값 545건
- `matched_company_name`: 빈 값 0건, 고유 비어있지 않은 값 540건
- `match_method`: 빈 값 0건, 고유 비어있지 않은 값 5건
- `match_score`: 빈 값 0건, 고유 비어있지 않은 값 8건
- `review_required`: 빈 값 0건, 고유 비어있지 않은 값 2건

## 08_data_issues.csv

- 행 수: 7
- 열: `issue_type`, `source`, `source_row`, `company_id`, `detail`, `severity`

### 열 품질 요약

- `issue_type`: 빈 값 0건, 고유 비어있지 않은 값 4건
- `source`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `source_row`: 빈 값 2건, 고유 비어있지 않은 값 5건
- `company_id`: 빈 값 2건, 고유 비어있지 않은 값 5건
- `detail`: 빈 값 0건, 고유 비어있지 않은 값 7건
- `severity`: 빈 값 0건, 고유 비어있지 않은 값 2건

## 09_data_dictionary.csv

- 행 수: 46
- 열: `sheet`, `column`, `data_type`, `required`, `description`, `example`

### 열 품질 요약

- `sheet`: 빈 값 0건, 고유 비어있지 않은 값 4건
- `column`: 빈 값 0건, 고유 비어있지 않은 값 39건
- `data_type`: 빈 값 0건, 고유 비어있지 않은 값 3건
- `required`: 빈 값 0건, 고유 비어있지 않은 값 2건
- `description`: 빈 값 0건, 고유 비어있지 않은 값 28건
- `example`: 빈 값 46건, 고유 비어있지 않은 값 0건


## Supabase CSV 매핑

| CSV | DB 테이블 | 기본/중복 방지 키 | 변환 |
| --- | --- | --- | --- |
| `01_companies.csv` | `companies` | `company_id` | `source_record_count`만 정수, 나머지 실제 열 보존 |
| `04_company_aliases.csv` | `company_aliases` | `(company_id, alias_type, alias_value, source)` | `alias_id`는 DB에서 생성 |
| `02_inspections.csv` | `inspections` | `inspection_id` | `inspection_date`는 date, `inspection_date_raw`는 text 보존 |
| `03_dispositions.csv` | `dispositions` | `disposition_id` | `inspection_date`, `disposition_date`는 date |

CSV의 기존 열은 DB에서도 같은 이름을 사용한다. 향후 입력용 열은 별도로 추가한다. `source_*`, `match_*`, 검토 상태는 이력 추적을 위해 보존하지만 일반 업체 조회 화면의 검색·표시 대상에서는 제외한다.
