# 데이터 감사 결과

이 문서는 `python scripts/audit_data.py` 실행으로 생성됩니다. 입력 CSV는 읽기만 하며 수정하지 않습니다.

## 파일 요약

| 파일 | 인코딩 | 행 수 | 열 수 | 최대 빈 값 비율 | 상태 |
| --- | --- | --- | --- | --- | --- |
| 01_companies.csv | utf-8-sig | 545 | 21 | 100.0% | 감사 완료 |
| 02_inspections.csv | utf-8-sig | 616 | 21 | 100.0% | 감사 완료 |
| 03_dispositions.csv | utf-8-sig | 366 | 19 | 72.1% | 감사 완료 |
| 04_company_aliases.csv | utf-8-sig | 2371 | 6 | 0.0% | 감사 완료 |
| 05_report_import_template.csv | utf-8-sig | 1 | 17 | 100.0% | 감사 완료 |
| 06_complaint_input_template.csv | utf-8-sig | 1 | 9 | 0.0% | 감사 완료 |
| 07_matching_review.csv | utf-8-sig | 860 | 10 | 0.1% | 감사 완료 |
| 08_data_issues.csv | utf-8-sig | 7 | 6 | 28.6% | 감사 완료 |
| 09_data_dictionary.csv | utf-8-sig | 46 | 6 | 100.0% | 감사 완료 |

## 무결성 검사

| 검사 | 결과 | 문제 건수 |
| --- | --- | --- |
| 01_companies.csv company_id 중복 | 통과 | 0 |
| 02_inspections.csv inspection_id 중복 | 통과 | 0 |
| 03_dispositions.csv disposition_id 중복 | 통과 | 0 |
| 01_companies.csv 완전 중복 행 | 통과 | 0 |
| 01_companies.csv 문자열 NaN | 통과 | 0 |
| 02_inspections.csv 완전 중복 행 | 통과 | 0 |
| 02_inspections.csv 문자열 NaN | 통과 | 0 |
| 03_dispositions.csv 완전 중복 행 | 통과 | 0 |
| 03_dispositions.csv 문자열 NaN | 통과 | 0 |
| 04_company_aliases.csv 완전 중복 행 | 통과 | 0 |
| 04_company_aliases.csv 문자열 NaN | 통과 | 0 |
| 05_report_import_template.csv 완전 중복 행 | 통과 | 0 |
| 05_report_import_template.csv 문자열 NaN | 통과 | 0 |
| 06_complaint_input_template.csv 완전 중복 행 | 통과 | 0 |
| 06_complaint_input_template.csv 문자열 NaN | 통과 | 0 |
| 07_matching_review.csv 완전 중복 행 | 통과 | 0 |
| 07_matching_review.csv 문자열 NaN | 통과 | 0 |
| 08_data_issues.csv 완전 중복 행 | 통과 | 0 |
| 08_data_issues.csv 문자열 NaN | 통과 | 0 |
| 09_data_dictionary.csv 완전 중복 행 | 통과 | 0 |
| 09_data_dictionary.csv 문자열 NaN | 통과 | 0 |
| 02_inspections.csv의 company_id 참조 | 통과 | 0 |
| 03_dispositions.csv의 company_id 참조 | 통과 | 0 |
| 04_company_aliases.csv의 company_id 참조 | 통과 | 0 |
| 02_inspections.csv inspection_date 날짜 | 통과 | 0 |
| 02_inspections.csv inspection_date_raw 날짜 | 확인 필요 | 7 |
| 03_dispositions.csv disposition_date 날짜 | 통과 | 0 |
| 03_dispositions.csv inspection_date 날짜 | 통과 | 0 |
| 05_report_import_template.csv reviewed_at 날짜 | 통과 | 0 |
| 05_report_import_template.csv inspection_date 날짜 | 통과 | 0 |
| 06_complaint_input_template.csv complaint_date 날짜 | 통과 | 0 |
| 데이터 사전 열 설명 | 확인 필요 | 46 |
| 업체 검색·필터 후보 열 | 통과 | 10 |
| 가명 처리 후보 열 | 검토 필요 | inspector_alias, manager_alias, representative_alias, reviewer_alias |

## 입력 복사본 지문

| 파일 | 바이트 | SHA-256 앞 16자리 |
| --- | --- | --- |
| 01_companies.csv | 137866 | f28e75141416637d… |
| 02_inspections.csv | 248407 | 9a8039ffc3d4feda… |
| 03_dispositions.csv | 128985 | 6c76cda9cb13e661… |
| 04_company_aliases.csv | 225254 | 8d343c0a16247f3d… |
| 05_report_import_template.csv | 560 | 51d572e22b9cbda3… |
| 06_complaint_input_template.csv | 267 | 84b1744150c9236a… |
| 07_matching_review.csv | 165601 | dfe8ac730f578b7e… |
| 08_data_issues.csv | 590 | de5f08c7363f3a78… |
| 09_data_dictionary.csv | 4005 | 9fadc02497ab4aca… |
