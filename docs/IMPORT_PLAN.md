# 초기 데이터 가져오기 계획

## 원칙

- 원본 CSV는 읽기만 하며 수정하지 않는다.
- 기본 실행은 항상 dry-run이고 DB 연결·쓰기를 하지 않는다.
- 입력 순서는 `companies`, `company_aliases`, `inspections`, `dispositions`이다.
- 미래용 빈 테이블에는 임의 데이터를 만들지 않는다.
- 기존 ID를 보존한다.

## 예상 건수

| 테이블 | 원본 | 등록 예정 | 제외·오류 |
| --- | ---: | ---: | ---: |
| `companies` | 545 | 545 | 0 |
| `company_aliases` | 2,371 | 2,371 | 0 |
| `inspections` | 616 | 616 | 0 |
| `dispositions` | 366 | 366 | 0 |

## 검증 항목

필수값 누락, ID 또는 자연키 중복, 업체마스터에 없는 `company_id`, 정식 날짜열 변환 실패, 정수·숫자 변환 실패를 검사한다. `inspection_date_raw`는 원천 문자열이므로 변환하지 않는다.

## 중복 방지 정책

`companies`, `inspections`, `dispositions`는 기존 ID 충돌 시 건너뛴다. `company_aliases`는 CSV에 `alias_id`가 없고 DB가 ID를 생성하므로 `(company_id, alias_type, alias_value, source)` 자연 키 충돌 시 건너뛴다. 기존 DB 행을 수정하는 update/upsert는 수행하지 않으며, 원격 preflight에서 건너뛸 건수를 먼저 계산한다.

검증 오류나 제외 행이 하나라도 있으면 `--apply`도 중단한다. 실제 저장 뒤에는 DB 건수, ID 중복, 외래키 미연결을 다시 조회해 dry-run 결과와 대조해야 한다.

## 현재 상태

`python scripts/import_to_supabase.py` dry-run만 실행했으며 Supabase 네트워크 연결과 실제 insert는 수행하지 않았다.
