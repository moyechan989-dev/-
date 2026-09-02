# Supabase 시제품 설정 절차

이 문서는 비개발자도 따라 할 수 있도록 작성한 준비 안내입니다. 현재 작업에서는 아래 절차를 실제로 수행하지 않았습니다.

## 1. 프로젝트 만들기

1. Supabase Dashboard에 로그인한다.
2. 새 프로젝트를 만들고 조직, 프로젝트 이름, 가까운 지역을 선택한다.
3. 데이터베이스 비밀번호는 비밀번호 관리자에 보관한다. 문서, 메신저, Git에 기록하지 않는다.
4. 프로젝트 생성이 끝날 때까지 기다린다.

## 2. SQL 검토 및 적용

Dashboard의 SQL Editor에서 다음 파일을 순서대로 열어 내용을 검토한 후 각각 실행한다.

1. `supabase/schema.sql`
2. `supabase/constraints.sql`
3. `supabase/indexes.sql`

실행 후 Table Editor에서 7개 테이블이 생성됐는지 확인한다. 초기에는 모두 빈 테이블이어야 한다. RLS가 모든 테이블에서 활성화됐고 `anon`, `authenticated` 권한이 열려 있지 않은지도 확인한다.

## 3. 키와 환경변수 준비

Project Settings의 API 관련 화면에서 프로젝트 URL과 서버 측 비밀키를 확인한다. 비밀키는 Streamlit 화면에 노출하거나 Git에 저장하지 않는다.

프로젝트 루트의 `.env.example`을 참고해 Git에서 제외된 `.env` 또는 운영체제 환경변수에 다음 값을 넣는다.

```text
SUPABASE_URL=프로젝트 URL
SUPABASE_SECRET_KEY=서버 전용 Secret Key
SUPABASE_PUBLISHABLE_KEY=일반 앱용 Publishable Key
DATA_BACKEND=local
OPENAI_API_KEY=
```

초기 import 스크립트와 `DATA_BACKEND=supabase`인 Streamlit 서버 프로세스만 `SUPABASE_SECRET_KEY`를 사용한다. 키는 브라우저·URL·클라이언트 JavaScript에 전달하지 않으며, 현재 기본값은 `DATA_BACKEND=local`로 유지한다. `OPENAI_API_KEY`는 사용하지 않으며 비워 둔다.

## 4. dry-run 확인

다음 명령은 네트워크 연결이나 DB 쓰기를 수행하지 않는다.

```powershell
python scripts/import_to_supabase.py
```

예상 건수, 필수값, ID 중복, 외래키, 날짜·숫자 변환 오류가 모두 정상인지 확인한다.

## 5. 운영 전 보안 확인

- 사용자 로그인, 부서, 역할별 접근 범위를 먼저 결정한다.
- 필요한 작업별 최소 `GRANT`와 RLS 정책을 별도 SQL로 작성한다.
- 공개되지 않아야 할 내부 메모와 가명 정보를 `anon`에 허용하지 않는다.
- Dashboard의 RLS Tester로 역할별 조회 결과를 확인한다.
- Database Advisors에서 보안·성능 경고를 확인한다.
- Data API 자동 노출 설정과 실제 권한을 함께 확인한다. RLS만 켰다고 API 권한이 설정되는 것은 아니다.
- 운영 전에는 사용자 로그인, 역할별 최소 권한 및 RLS 정책을 확정한다. 서버 전용 Secret Key는 인증된 일반 사용자 요청을 대신하는 운영용 키가 아니다.

## 6. 실제 가져오기 전 승인

실제 데이터 저장은 사용자가 SQL과 dry-run 결과를 확인하고 명시적으로 승인한 뒤 별도 작업으로 수행한다. 승인 전에는 `python scripts/import_to_supabase.py --apply`를 실행하지 않는다.
