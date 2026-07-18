# 상용화 개발 및 연동 TODO

이 문서는 현재 MVP를 외부 고객이 직접 가입하고 결제하는 상용 서비스로 전환할 때 필요한 개발·연동 항목을 정리합니다.

## 현재 구현된 범위

- Qwen ASR과 forced aligner 기반 STT
- pyannote와 OpenAI-compatible/vLLM provider 연결 구조
- GPU stage subprocess 종료 후 VRAM 반환
- 업로드, 비동기 처리, SSE 진행 상태, polling fallback
- 화자별 transcript, 검색, 재생, AI 요약과 회의록
- 제목·참석자·발화문 편집
- 서버 저장형 메모·북마크·하이라이트
- 노트와 음성·결과 데이터 완전 삭제 API
- worker 재시작 시 queued/processing 작업 재등록
- production에서 API 키·실제 provider·HTTPS CORS 설정 검사
- JSON 오인식 교정 사전

현재 인증은 서버 전체가 공유하는 API 키 하나입니다. 사용자 계정, 조직 격리, 결제, 공유 기능은 구현되어 있지 않습니다.

## P0: 유료 고객을 받기 전에 필수

### 1. 사용자 인증과 조직별 데이터 격리

먼저 인증 제공자를 결정합니다.

- 자체 구축: Keycloak
- AWS 중심: Cognito
- Microsoft 기업 고객: Entra ID
- 빠른 SaaS 출시: Auth0 또는 Clerk

개발 항목:

- `users`, `organizations`, `memberships` 테이블 추가
- `jobs`에 `organization_id`, `owner_user_id` 추가
- 모든 조회·수정·삭제 쿼리에 조직 소유권 조건 적용
- 관리자, 일반 사용자, 읽기 전용 역할 구분
- 브라우저에 `VITE_API_KEY`를 넣는 방식 제거
- OIDC Authorization Code + PKCE 또는 보안 쿠키 세션 적용
- 공유 링크는 별도 만료 token과 읽기 권한으로 구현

완료 기준:

- 다른 조직의 job ID를 알아도 상태·오디오·결과를 조회할 수 없음
- 목록, SSE, 다운로드, retry, delete 모두 동일한 권한 검사 사용
- 권한 우회 통합 테스트가 CI에서 실행됨

### 2. 실제 음성 정확도 및 성능 기준

고객 동의를 받은 한국어 회의 평가 세트를 준비합니다.

- 조용한 회의실, 원거리 마이크, 전화, 잡음, 겹침 발화
- 일반 회의와 회사 고유명사가 많은 기술 회의
- 최소 30시간, 출시 전 권장 50시간 이상

측정 항목:

- STT: CER과 고유명사 정확도
- 화자 분리: DER과 화자 수 오류율
- timestamp 평균 오차
- 오디오 1시간당 처리시간과 GPU 최대 VRAM
- 업로드부터 결과 완료까지 p50/p95
- 100건 연속 처리 성공률

개발 항목:

- 평가 음성·정답 manifest 형식 정의
- `backend/scripts/evaluate_asr.py`와 회귀 리포트 작성
- 모델·사전·전처리 설정별 결과 버전 저장
- 품질이 기준보다 낮으면 배포를 막는 CI 또는 release gate 구성

완료 기준은 고객 도메인별로 합의합니다. 측정값 없이 “정확도 보장” 문구를 사용하지 않습니다.

### 3. 운영용 파일 저장소와 완전 삭제

현재 파일은 Docker host volume에 저장됩니다. 상용 환경에서는 S3, MinIO 또는 호환 object storage로 교체합니다.

개발 항목:

- object storage adapter와 database metadata 분리
- 서버 측 암호화와 KMS key 정책
- 업로드·재생·다운로드용 짧은 만료 signed URL
- 고객별 보관 기간과 즉시 삭제 정책
- 원본, 전처리본, 결과, 백업에서의 삭제 추적
- DB 암호화 백업과 정기 복원 훈련
- 저장 위치와 데이터 국외 이전 정책 결정

완료 기준:

- 삭제 요청 후 정해진 시간 안에 모든 저장 계층에서 제거
- 삭제 audit ID를 운영자가 확인 가능
- 백업에서 실제 복원하는 훈련을 정기적으로 통과

### 4. 작업 신뢰성과 다중 GPU 운영

현재 재시작 복구는 단일 worker 운영을 전제로 합니다. worker를 여러 개 실행하려면 분산 실행권이 필요합니다.

개발 항목:

- Redis 또는 DB 기반 job lease와 heartbeat
- lease 만료 후에만 다른 worker가 작업 인수
- stage별 재시도 횟수와 지수 backoff
- dead-letter queue와 관리자 재처리
- 처리 취소와 graceful shutdown
- GPU별 worker queue 및 장치 고정
- 같은 job의 중복 결과 쓰기를 막는 idempotency key
- 장시간 STT/LLM 단계의 heartbeat 갱신

완료 기준:

- worker 강제 종료 후 자동 복구
- 동일 job이 동시에 두 GPU에서 처리되지 않음
- Redis·DB 일시 장애 후 유실 없이 재개

### 5. 보안과 개인정보

개발·연동 항목:

- TLS 인증서와 HTTPS 강제
- frontend는 `npm run build` 산출물을 CDN 또는 production web server로 배포하고 Vite dev server를 운영에 사용하지 않음
- API rate limit, 업로드 횟수와 용량 제한
- Secret Manager/Vault를 통한 token 관리
- 업로드 파일 실제 포맷 검사와 악성 파일 검사
- 관리자 작업 및 다운로드 audit log
- 개인정보 처리방침, 이용약관, 녹음 동의 안내
- 탈퇴·삭제·정보 열람 요청 처리 절차
- 의존성 취약점 검사, SBOM과 컨테이너 이미지 서명
- Qwen, pyannote, ffmpeg, sox 및 LLM 모델의 상업 라이선스 검토

현재 query string API key는 URL 로그에 남을 수 있으므로 사용자 인증 도입 시 제거합니다.

### 6. 프론트엔드와 API 자동 검증

개발 항목:

- Vitest + React Testing Library 단위 테스트
- Playwright E2E: 업로드, 진행 상태, 편집, 메모, 다운로드, 삭제
- API contract test와 migration upgrade/downgrade test
- 모바일 실제 기기 테스트
- 긴 제목, 100명 화자, 수천 segment, 3시간 음성 성능 테스트
- 접근성 검사와 키보드 편집 흐름

완료 기준:

- 핵심 사용자 흐름이 CI에서 자동 실행
- 릴리스마다 desktop/mobile screenshot 회귀 검사

## P1: 유료 베타 운영에 필요

### 결제와 사용량

국내 중심이면 PortOne/Toss Payments, 해외 중심이면 Stripe를 후보로 검토합니다.

- 오디오 초 단위 불변 usage ledger
- 요금제별 월 처리시간, 파일 크기, 보관 기간 제한
- 결제 webhook 서명 검증과 idempotency
- 결제 실패, 환불, 해지, 초과 사용 정책
- 관리자 수동 크레딧과 사용량 정정 audit
- 세금계산서와 부가세 처리 방식 결정

### 편집 후 AI 결과 재생성

현재 transcript를 수정해도 기존 요약과 회의록은 유지됩니다.

- 변경된 transcript 버전 저장
- “요약·회의록 다시 생성” 비동기 job
- 생성 비용과 사용량 반영
- 이전 버전 복구와 변경 이력
- 동시에 편집할 때 optimistic locking

### 알림과 녹음

- 완료·실패 이메일 또는 앱 알림
- 브라우저 직접 녹음과 업로드 재개
- 대용량 multipart upload
- 여러 파일 일괄 업로드
- 웹을 닫아도 확인 가능한 작업 센터

### 관측성과 고객 지원

- OpenTelemetry trace
- Prometheus/Grafana 또는 관리형 metrics
- Sentry 등 오류 수집
- provider별 latency, 실패율, GPU VRAM dashboard
- 고객별 job 검색, 재처리, 삭제가 가능한 관리자 화면
- 서비스 상태 페이지와 장애 공지 절차

## P2: 정식 제품 확장

- 폴더, 태그, 전체 노트 검색
- 공유, 댓글, 멘션, 팀 편집
- 사용자별·조직별 고유명사 사전 UI
- Word, PDF, SRT/VTT 등 추가 export
- 회의 플랫폼 연동과 캘린더 bot
- 모바일 앱과 push notification
- 다국어 및 번역
- action item을 Notion, Jira, Slack, Teams로 전송

## 권장 출시 순서

1. 단일 고객의 사내 설치형 PoC로 정확도와 처리시간 측정
2. 인증·조직 격리·object storage·audit를 적용한 private beta
3. 결제·usage ledger·고객 관리자 기능을 적용한 유료 beta
4. 다중 GPU 장애 훈련과 개인정보 절차를 통과한 정식 출시

각 단계는 기능 개수보다 실제 고객 음성의 품질 지표, 데이터 격리 테스트, 삭제 증빙과 장애 복구 결과를 기준으로 통과시킵니다.
