# 폐기물처리업체 통합 이력관리 및 지도점검 지원 시스템

지방자치단체 환경직 공무원이 폐기물처리업체의 기본 정보, 지도점검 이력, 행정처분 이력을 한 곳에서 확인하도록 지원하는 내부 업무용 프로젝트입니다.

현재 단계는 원본 CSV를 보존한 채 데이터 구조를 조사하고 MVP 설계를 문서화하는 단계입니다. 화면, 데이터 수정, Supabase 연결, PDF 분석·등록, 파일 내보내기는 아직 구현하지 않습니다.

## 빠른 시작

```powershell
python scripts/audit_data.py
```

입력 자료는 `data/private/input`에 보관하며 Git에서 제외됩니다. 감사 결과는 `docs/DATA_AUDIT.md`, `docs/DATA_MAPPING.md`, `reports/data_quality_summary.csv`에 생성됩니다.

## 주요 문서

- `docs/MVP_SCOPE.md`: 현재 단계 범위
- `docs/DATABASE_DESIGN.md`: 향후 데이터 구조
- `docs/PDF_IMPORT_DESIGN.md`: PDF 가져오기 설계
- `docs/EXPORT_DESIGN.md`: 내보내기 설계
- `docs/OPEN_QUESTIONS.md`: 확인이 필요한 사항

## 현재 실행

로컬 CSV 조회 화면은 계속 기본 모드로 동작합니다.

```powershell
streamlit run app.py
```

Supabase 준비 단계에서는 SQL을 실행하거나 데이터를 저장하지 않습니다. 아래 명령은 CSV를 DB 레코드로 변환할 수 있는지 검사만 합니다.

```powershell
python scripts/import_to_supabase.py
```

SQL 검토 자료는 `supabase/`, 설정 절차는 `docs/SUPABASE_SETUP.md`, 가져오기 정책은 `docs/IMPORT_PLAN.md`에 있습니다. 실제 적용 명령인 `--apply`는 사용자 승인 전 실행하지 않습니다.

## Supabase 조회 모드 및 운영 전 TODO

`DATA_BACKEND=supabase`이면 Streamlit의 서버 측 Python 프로세스가 환경변수의 `SUPABASE_SECRET_KEY`로 조회와 사용자가 최종 확인한 지도점검 한 건의 등록을 수행합니다. 키는 브라우저, URL, 화면, Git에 전달하거나 기록하지 않습니다. 행정처분 등록·수정은 지원하지 않습니다.

운영 배포 전에는 반드시 Supabase Auth, 부서·역할별 최소 권한, RLS 정책을 설계·검증해야 합니다. 서버 전용 Secret Key를 일반 사용자 접근용으로 사용하지 않습니다.
# -
