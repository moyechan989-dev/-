# Supabase SQL 적용 순서

이 폴더의 SQL은 설계 초안이며 아직 Supabase에서 실행하지 않았습니다.

1. `schema.sql`: 테이블, 기본 키, 기본 외래키 생성
2. `constraints.sql`: 기존 프로젝트용 외래키 보완, 추가 unique/check 제약, RLS, 권한 회수
3. `indexes.sql`: 검색·연결·날짜 정렬 인덱스

현재 시제품은 인증 기능이 없으므로 `anon`, `authenticated` 권한을 모두 회수하고 정책을 만들지 않습니다. 따라서 SQL Editor 또는 서버 측 비밀키를 사용하는 승인된 가져오기 작업 외에는 Data API 접근이 차단됩니다.

운영 전에는 사용자 역할과 부서별 데이터 범위를 먼저 결정한 뒤 작업별 `GRANT`와 RLS 정책을 추가하고, Dashboard의 RLS Tester와 Database Advisors로 검증해야 합니다. `service_role` 또는 secret key는 Streamlit 화면이나 Git에 넣지 않습니다.

2026년 Supabase 변경에 따라 새 `public` 테이블이 Data API에 자동 노출되지 않을 수 있습니다. RLS와 API 권한은 별개이므로, 운영 정책 확정 후 필요한 권한만 명시적으로 부여합니다.

## 이미 schema.sql을 실행한 현재 프로젝트

`schema.sql`을 다시 실행하지 않습니다. 먼저 수정된 `constraints.sql`을 실행하고, 성공한 뒤 `indexes.sql`을 실행합니다. 두 파일은 기존 제약·인덱스 이름을 확인해 재실행에도 안전하게 동작하도록 작성했습니다.

`company_aliases_natural_key`처럼 기존에 같은 이름의 고유 인덱스가 있다면, 열 구성이 정확히 같을 때만 `UNIQUE USING INDEX`로 제약에 연결합니다. 다른 객체라면 삭제·변경하지 않고 명확한 오류로 중단합니다.
