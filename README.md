# Meeting Minutes AI

회의 녹음 파일을 업로드하면 서버에서 STT, 화자 분리, 스크립트 정리, 회의록 생성, 요약 생성을 비동기로 처리하는 MVP 서비스입니다.

이 문서는 개발자가 아니어도 로컬 PC나 GPU 서버에서 서비스를 실행하고, 브라우저로 녹음 파일을 업로드해 결과를 확인할 수 있도록 작성한 실행 명세서입니다.

## 먼저 고를 실행 방식

처음 실행한다면 아래 둘 중 하나만 고르면 됩니다.

| 목적 | 필요한 장비 | 결과 | 추천 대상 |
| --- | --- | --- | --- |
| 화면과 업로드 흐름만 확인 | Docker만 설치된 PC | 데모 transcript 반환 | 설치 확인, 시연 화면 점검 |
| 실제 Qwen ASR로 음성 인식 | NVIDIA GPU 서버 또는 GPU PC | 실제 녹음 파일 transcription | 실제 테스트, 운영 검증 |

## 준비물

공통 준비물:

- Docker Desktop 또는 Docker Engine
- 이 프로젝트 폴더 전체
- 인터넷 연결
- 브라우저: Chrome, Edge, Safari 중 하나
- 비어 있는 포트: `5173`, `8000`, `5432`, `6379`

실제 Qwen ASR 실행 준비물:

- NVIDIA GPU 1장 이상. L40S 1GPU 기준으로 설계되어 있습니다.
- NVIDIA driver와 NVIDIA Container Toolkit
- 모델 다운로드용 디스크 여유 공간. 처음 실행 시 `models/` 폴더에 Hugging Face 모델을 받습니다.
- 첫 실행은 모델 다운로드 때문에 오래 걸릴 수 있습니다.

선택 준비물:

- 화자 분리를 실제로 쓰려면 Hugging Face token과 pyannote 모델 접근 권한
- 로컬 LLM까지 쓰려면 vLLM 또는 OpenAI-compatible endpoint

## 1. 폴더 열기

터미널에서 프로젝트 폴더로 이동합니다.

```bash
cd meeting-minutes-ai
```

현재 위치가 맞는지 확인합니다.

```bash
ls
```

아래 파일이 보이면 맞습니다.

```text
docker-compose.yml
docker-compose.gpu.yml
backend
frontend
models
data
```

## 2. 설정 파일 확인

실행 설정은 `.env` 파일에서 바꿉니다.

처음 받은 폴더에 `.env`가 없다면 `.env.example`을 복사합니다.

```bash
cp .env.example .env
```

`.env`는 메모장, VS Code, nano 등 편한 편집기로 수정하면 됩니다.

## 3. 데모 모드로 실행하기

GPU 없이 화면과 업로드 흐름만 확인하는 방식입니다. 실제 음성 인식 결과가 아니라 샘플 결과가 나옵니다.

`.env`에서 아래 값으로 바꿉니다.

```env
STT_PROVIDER=mock
DIARIZATION_PROVIDER=mock
LLM_PROVIDER=mock
VLLM_ON_DEMAND=false
```

실행합니다.

```bash
docker compose up --build
```

브라우저에서 접속합니다.

```text
http://localhost:5173
```

녹음 파일을 업로드하면 데모 결과가 생성됩니다.

## 4. 실제 Qwen ASR로 실행하기

실제 녹음 파일을 Qwen ASR로 음성 인식하는 방식입니다. GPU가 필요합니다.

`.env`에서 STT 설정을 아래처럼 둡니다.

```env
STT_PROVIDER=qwen_asr
STT_LANGUAGE=ko
QWEN_ASR_MODEL=Qwen/Qwen3-ASR-1.7B
QWEN_ASR_FORCED_ALIGNER_MODEL=Qwen/Qwen3-ForcedAligner-0.6B
QWEN_ASR_DTYPE=bfloat16
QWEN_ASR_DEVICE_MAP=cuda:0
QWEN_ASR_MAX_INFERENCE_BATCH_SIZE=8
QWEN_ASR_MAX_NEW_TOKENS=4096
QWEN_ASR_RETURN_TIMESTAMPS=true
```

처음에는 화자 분리와 LLM을 mock으로 두고 STT만 먼저 확인하는 것을 권장합니다.

```env
DIARIZATION_PROVIDER=mock
LLM_PROVIDER=mock
VLLM_ON_DEMAND=false
```

GPU 모드로 실행합니다.

```bash
CUDA_VISIBLE_DEVICES=0 docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

첫 실행 중 worker 로그에 모델 다운로드 메시지가 보입니다. 다운로드가 끝난 뒤 브라우저에서 접속합니다.

```text
http://localhost:5173
```

## 5. 파일 업로드와 결과 확인

지원 파일 형식:

```text
.mp3 .wav .m4a .aac .flac .mp4 .webm
```

사용 순서:

1. 브라우저에서 `http://localhost:5173` 접속
2. 녹음 파일 선택
3. 업로드
4. 상태가 `completed`가 될 때까지 대기
5. 결과 화면에서 원문, 화자별 transcript, 회의록, 요약 확인
6. 필요한 결과 다운로드

업로드 파일과 결과 데이터는 `data/` 폴더에 저장됩니다. 다운로드된 모델은 `models/` 폴더에 저장됩니다.

결과 화면에서 다음 내용은 서버에 저장됩니다.

- 노트 제목
- 참석자 이름
- 수정한 발화문
- 메모, 북마크, 하이라이트

노트 우측 상단의 휴지통 버튼을 누르면 원본 업로드, 처리된 음성, transcript, 회의록과 메모를 함께 삭제합니다. 처리 중인 노트는 작업 충돌을 막기 위해 삭제할 수 없습니다.

## 오인식 단어 사전 설정

회사명, 제품명, 사람 이름처럼 음성 인식이 반복해서 틀리는 단어는 `config/stt_dictionary.json`에서 직접 고칠 수 있습니다.

기본 형식은 `"잘못 인식된 표현": "화면에 표시할 올바른 표현"`입니다.

```json
{
  "큐원": "Qwen",
  "큐웬": "Qwen",
  "브이 엘 엘 엠": "vLLM",
  "에이 아이 회의록": "AI 회의록"
}
```

사용 방법:

1. `config/stt_dictionary.json`을 메모장이나 VS Code로 엽니다.
2. 쉼표를 유지하면서 오인식 표현과 표준 표현을 추가합니다.
3. 파일을 저장합니다.
4. 새 녹음 파일을 업로드합니다.

worker는 작업을 시작할 때 사전을 다시 읽으므로 사전만 수정한 경우 Docker를 재시작할 필요가 없습니다. 이미 완료된 결과는 자동으로 다시 바뀌지 않으므로 같은 녹음 파일을 새로 업로드해야 합니다.

`.env`에는 아래 경로가 설정되어 있어야 합니다.

```env
LEXICON_PATH=config/stt_dictionary.json
```

교정은 대소문자를 구분하지 않고 긴 표현부터 적용합니다. `"api": "API"`처럼 영문 약어를 등록해도 `capitol` 같은 다른 영단어의 일부는 바꾸지 않습니다. 한 번 교정된 결과를 다시 다른 항목으로 연쇄 치환하지 않습니다.

기존의 단어 힌트 파일도 계속 사용할 수 있습니다. JSON 대신 일반 텍스트 파일을 쓰려면 한 줄에 표준어 하나를 쓰거나, 아래처럼 탭으로 오인식과 표준어를 구분합니다.

```text
# 표준어 힌트
카프카

# 오인식<TAB>표준어
큐 원	Qwen
브이 엘 엘 엠	vLLM
```

## 6. 종료와 재실행

실행 중인 터미널에서 종료:

```bash
Ctrl + C
```

컨테이너 정리:

```bash
docker compose down
```

GPU 모드로 실행한 컨테이너 정리:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
```

다시 실행할 때는 같은 실행 명령을 다시 입력하면 됩니다. `models/` 폴더가 남아 있으면 이미 받은 모델은 다시 받지 않습니다.

## 7. 로그 확인

전체 로그:

```bash
docker compose logs -f
```

worker 로그만 확인:

```bash
docker compose logs -f worker
```

GPU 모드 worker 로그:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml logs -f worker
```

## 8. 자주 쓰는 설정 명세

| 설정 | 의미 | 추천값 |
| --- | --- | --- |
| `STT_PROVIDER` | 음성 인식 방식 | 실제 실행은 `qwen_asr`, 데모는 `mock` |
| `STT_LANGUAGE` | 음성 언어 | 한국어는 `ko`, 자동 감지는 빈 값 |
| `LEXICON_PATH` | 오인식 교정 사전 경로 | `config/stt_dictionary.json` |
| `QWEN_ASR_MODEL` | Hugging Face Qwen ASR 모델명 | `Qwen/Qwen3-ASR-1.7B` |
| `QWEN_ASR_FORCED_ALIGNER_MODEL` | timestamp 생성용 모델명 | `Qwen/Qwen3-ForcedAligner-0.6B` |
| `DIARIZATION_PROVIDER` | 화자 분리 방식 | 처음 테스트는 `mock`, 실제 화자분리는 `pyannote` |
| `LLM_PROVIDER` | 회의록 생성 LLM 방식 | 처음 테스트는 `mock` |
| `VLLM_ON_DEMAND` | 작업 중 vLLM 자동 실행 여부 | 처음 테스트는 `false` |
| `RECOVER_INTERRUPTED_JOBS` | worker 재시작 시 중단 작업 자동 재등록 | `true` |
| `HUGGINGFACE_TOKEN` | Hugging Face 접근 token | pyannote 사용 시 필요 |

`APP_ENV=production`에서는 안전하지 않은 설정으로 시작하지 않습니다. `API_KEY`가 비어 있거나, STT·화자 분리·LLM 중 하나가 `mock`이거나, CORS 주소가 localhost이면 backend와 worker가 시작 단계에서 오류를 냅니다.

편집·삭제 API:

- `PATCH /api/results/{job_id}`: 제목, 발화문, 화자명, 메모, 북마크, 하이라이트 저장
- `DELETE /api/jobs/{job_id}`: 완료·실패 작업의 원본 음성, 전처리 음성, 분석 결과와 작업 기록 삭제

발화문 편집 시 기존 구간의 시작·종료 timestamp와 구간 개수는 유지됩니다. 편집 후 기존 AI 요약·회의록은 자동 재생성되지 않으며 화면에 재생성 필요 상태가 표시됩니다.

이 안전장치는 단일 사내 설치의 기본 노출을 줄이는 용도입니다. 다중 사용자 로그인과 조직별 데이터 격리를 대신하지 않습니다.

## 9. 문제 해결

`docker: command not found`

Docker가 설치되어 있지 않거나 터미널에서 Docker를 찾지 못하는 상태입니다. Docker Desktop 또는 Docker Engine 설치 후 다시 실행합니다.

`port is already allocated`

이미 같은 포트를 쓰는 프로그램이 있습니다. 기존 컨테이너를 끕니다.

```bash
docker compose down
```

브라우저에서 접속이 안 됨

서비스가 아직 뜨는 중일 수 있습니다. 터미널 로그에서 `frontend`와 `backend`가 정상 시작됐는지 확인한 뒤 `http://localhost:5173`으로 접속합니다.

Qwen ASR 첫 실행이 너무 오래 걸림

정상일 수 있습니다. 첫 실행은 Hugging Face에서 모델을 받기 때문에 오래 걸립니다. `models/` 폴더를 지우지 않으면 다음 실행부터는 다운로드를 건너뜁니다.

GPU 메모리 부족 오류

동시에 여러 worker를 띄우지 말고 1개 worker만 사용합니다. 그래도 부족하면 `QWEN_ASR_MAX_INFERENCE_BATCH_SIZE=4` 또는 `QWEN_ASR_MODEL=Qwen/Qwen3-ASR-0.6B`로 낮춰 테스트합니다.

pyannote 다운로드 오류

`HUGGINGFACE_TOKEN`이 비어 있거나 pyannote 모델 접근 권한이 없을 가능성이 큽니다. 처음에는 `DIARIZATION_PROVIDER=mock`으로 둔 뒤 STT부터 확인합니다.

결과가 데모 문장으로 나옴

`.env`의 `STT_PROVIDER`, `DIARIZATION_PROVIDER`, `LLM_PROVIDER`가 `mock`인지 확인합니다. 실제 Qwen ASR을 쓰려면 `STT_PROVIDER=qwen_asr`로 바꿔야 합니다.

## 10. 운영 체크리스트

- `.env`가 원하는 실행 모드로 설정되어 있는지 확인
- GPU 모드는 `docker-compose.gpu.yml`을 함께 사용
- 첫 실행 전 디스크 여유 공간 확인
- `models/` 폴더는 모델 캐시이므로 운영 중 삭제하지 않기
- 여러 작업을 동시에 돌리기 전 GPU 메모리 사용량 확인
- 데모 모드 결과는 실제 분석 결과가 아니라는 점을 사용자에게 고지
- 상용화 전에 [`docs/COMMERCIALIZATION_TODO.md`](docs/COMMERCIALIZATION_TODO.md)의 P0 항목 완료

## 참고: 내부 구조

### 처리 순서

```text
사용자가 Windows 또는 회의 플랫폼에서 녹음 파일 준비
→ 웹페이지 접속
→ 녹음 파일 업로드
→ Backend가 분석 Job 생성
→ Worker가 STT 실행
→ 오인식 단어 사전 적용
→ Worker가 화자 분리 실행
→ STT 결과와 화자 분리 결과 결합
→ LLM으로 스크립트 정리
→ LLM으로 회의록 작성
→ LLM으로 회의 요약 작성
→ 웹에서 결과 확인
→ 회의록/요약/스크립트 다운로드
```

### 아키텍처

```text
frontend React/Vite
  → FastAPI backend
    → PostgreSQL: job/result metadata
    → Redis: Celery broker/result backend
    → Celery worker
      → ffmpeg preprocessing
      → STT provider
      → diarization provider
      → alignment
      → LLM provider
      → result 저장
```

### 폴더 구조

```text
meeting-minutes-ai/
  backend/
    app/
      main.py
      api/routes/
      core/
      models/
      schemas/
      services/
      workers/
      utils/
    scripts/download_models.py
    Dockerfile
    requirements.txt
    requirements-ml.txt
  frontend/
    src/
      api/
      components/
      pages/
    Dockerfile
    package.json
  docker/nginx/nginx.conf
  docker-compose.yml
  docker-compose.gpu.yml
  .env
  .env.example
  models/
  data/
```

## 모델 캐시와 다운로드

로컬 `./models` 디렉터리가 컨테이너의 `/models`로 마운트됩니다.

```yaml
./models:/models
```

worker 시작 시 `backend/scripts/download_models.py`가 실행됩니다.

- `STT_PROVIDER=qwen_asr`이면 `/models/qwen-asr/{QWEN_ASR_MODEL}`과 `/models/qwen-asr/{QWEN_ASR_FORCED_ALIGNER_MODEL}`을 확인합니다.
- 모델 파일이 이미 있으면 다운로드를 건너뜁니다.
- 없으면 Hugging Face에서 다운로드합니다.
- `DIARIZATION_PROVIDER=pyannote`이면 `/models/pyannote/{모델명}`을 확인합니다.
- pyannote 모델 다운로드에는 `HUGGINGFACE_TOKEN`이 필요합니다.
- `VLLM_ON_DEMAND=true`이면 `/models/vllm/{모델명}`을 확인합니다.
- vLLM 모델이 이미 있으면 다운로드를 건너뛰고, 없으면 Hugging Face에서 받습니다.

수동 다운로드:

```bash
cd meeting-minutes-ai
python backend/scripts/download_models.py
```

강제로 Qwen ASR 모델과 forced aligner 받기:

```bash
DOWNLOAD_QWEN_ASR_MODEL=1 QWEN_ASR_MODEL=Qwen/Qwen3-ASR-1.7B python backend/scripts/download_models.py
```

강제로 pyannote 모델 받기:

```bash
DOWNLOAD_PYANNOTE_MODEL=1 HUGGINGFACE_TOKEN=... python backend/scripts/download_models.py
```

강제로 vLLM 모델 받기:

```bash
DOWNLOAD_VLLM_MODEL=1 VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct python backend/scripts/download_models.py
```

## Qwen ASR 설정

`.env`를 수정합니다.

```env
STT_PROVIDER=qwen_asr
STT_LANGUAGE=ko
QWEN_ASR_MODEL=Qwen/Qwen3-ASR-1.7B
QWEN_ASR_FORCED_ALIGNER_MODEL=Qwen/Qwen3-ForcedAligner-0.6B
QWEN_ASR_DTYPE=bfloat16
QWEN_ASR_DEVICE_MAP=cuda:0
QWEN_ASR_MAX_INFERENCE_BATCH_SIZE=8
QWEN_ASR_MAX_NEW_TOKENS=4096
QWEN_ASR_RETURN_TIMESTAMPS=true
```

GPU/ML 의존성을 포함해 실행합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

`STT_LANGUAGE=ko`는 내부적으로 Qwen ASR의 `Korean`으로 매핑됩니다. 빈 값으로 두면 Qwen ASR의 자동 언어 감지를 사용합니다. 한국어/영어 회의 모두 자동 감지가 잘 동작합니다.

## pyannote 설정

Hugging Face에서 pyannote 모델 사용 권한을 승인한 뒤 token을 설정합니다.

```env
DIARIZATION_PROVIDER=pyannote
PYANNOTE_MODEL=pyannote/speaker-diarization-3.1
HUGGINGFACE_TOKEN=...
```

GPU override로 실행합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

## LLM Provider 설정

OpenAI-compatible endpoint:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=...
```

Ollama:

```env
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=llama3.1
```

## 1 GPU + On-demand vLLM 설계

GPU가 1개이고 STT, 화자 분리, LLM을 모두 로컬 GPU에서 처리하려면 동시에 올리지 않고 job 안에서 순차 실행합니다.

```text
ffmpeg: CPU
→ STT: GPU subprocess
→ STT subprocess 종료로 VRAM 회수
→ diarization: GPU subprocess
→ diarization subprocess 종료로 VRAM 회수
→ vLLM server 기동
→ script cleanup / minutes / summary 호출
→ vLLM server 종료
```

이 구조에서는 worker를 반드시 1개만 둡니다. 현재 Docker Compose worker는 `--pool=solo --concurrency=1`로 실행됩니다.

`.env` 예시:

```env
STT_PROVIDER=qwen_asr
STT_LANGUAGE=ko
QWEN_ASR_MODEL=Qwen/Qwen3-ASR-1.7B
QWEN_ASR_FORCED_ALIGNER_MODEL=Qwen/Qwen3-ForcedAligner-0.6B
QWEN_ASR_DTYPE=bfloat16
QWEN_ASR_DEVICE_MAP=cuda:0
QWEN_ASR_MAX_INFERENCE_BATCH_SIZE=8
QWEN_ASR_MAX_NEW_TOKENS=4096
QWEN_ASR_RETURN_TIMESTAMPS=true

DIARIZATION_PROVIDER=pyannote
PYANNOTE_MODEL=pyannote/speaker-diarization-3.1
HUGGINGFACE_TOKEN=...

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=

GPU_STAGE_SUBPROCESS=true

VLLM_ON_DEMAND=true
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_HOST=127.0.0.1
VLLM_PORT=8001
VLLM_GPU_MEMORY_UTILIZATION=0.85
VLLM_DTYPE=auto
VLLM_MAX_MODEL_LEN=8192
VLLM_TRUST_REMOTE_CODE=false
```

실행:

```bash
CUDA_VISIBLE_DEVICES=0 INSTALL_VLLM=true docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

GPU STT/화자분리만 테스트하고 vLLM 패키지를 이미지에 넣지 않으려면 `INSTALL_VLLM=false`로 실행합니다.

```bash
CUDA_VISIBLE_DEVICES=0 INSTALL_VLLM=false docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

vLLM이 너무 무겁거나 이미 별도 서버로 떠 있다면 on-demand를 끄고 외부 endpoint를 지정합니다.

```env
VLLM_ON_DEMAND=false
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://host.docker.internal:8001/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

## GPU 사용과 Scale-out

단일 GPU 기본 실행:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

GPU 지정:

```bash
CUDA_VISIBLE_DEVICES=0 docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

단일 GPU에서 on-demand vLLM까지 쓰는 경우 worker scale-out을 하지 마세요. 여러 job은 Redis queue에 쌓이고 worker 1개가 순차 처리합니다.

4개 worker로 확장:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build --scale worker=4
```

운영에서는 worker별 GPU 할당 정책을 별도로 두는 것이 좋습니다.

## API 명세

### Health Check

```http
GET /health
```

응답:

```json
{"status":"ok"}
```

### 파일 업로드

```http
POST /api/uploads
Content-Type: multipart/form-data
```

form field:

```text
file
```

응답:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "filename": "meeting.mp3"
}
```

### Job 상태 조회

```http
GET /api/jobs/{job_id}
```

상태값:

```text
queued processing completed failed
```

단계:

```text
uploaded preprocessing stt diarization alignment script_cleanup minutes_generation summary_generation completed failed
```

### 결과 조회

```http
GET /api/results/{job_id}
```

완료되지 않은 job은 `409 Conflict`를 반환합니다.

### 결과 다운로드

```http
GET /api/results/{job_id}/download?type=minutes
GET /api/results/{job_id}/download?type=summary
GET /api/results/{job_id}/download?type=transcript
GET /api/results/{job_id}/download?type=cleaned_transcript
GET /api/results/{job_id}/download?type=json
```

## 프론트엔드 사용 방법

1. `http://localhost:5173` 접속
2. 녹음 파일 선택 또는 drag-and-drop
3. 업로드 시작
4. 진행률과 현재 단계 확인
5. 완료 후 결과 탭 확인
6. 회의록, 요약, 스크립트, JSON 다운로드

## Windows 사용자가 접근하는 방법

Ubuntu 서버와 Windows PC가 같은 네트워크에 있으면 Windows 브라우저에서 다음 주소로 접속합니다.

```text
http://{ubuntu-server-ip}:5173
```

Backend API는 기본적으로 다음 포트를 사용합니다.

```text
http://{ubuntu-server-ip}:8000
```

운영 환경에서는 방화벽, HTTPS, reverse proxy, 인증을 추가해야 합니다.

## 녹음 파일 준비

사용자는 다음 방식으로 녹음 파일을 만들 수 있습니다.

- Zoom 자체 녹음
- MS Teams 자체 녹음
- Webex 자체 녹음
- Windows Sound Recorder
- OBS, Audacity
- 스마트폰 녹음 앱
- 기타 오디오/비디오 녹음 도구

상대방 소리까지 분석하려면 업로드하는 파일에 내 목소리와 상대방 목소리가 모두 포함되어 있어야 합니다. 업로드 전에 파일을 재생해 상대방 음성이 들어 있는지 확인하세요.

## 보안 / 개인정보 주의사항

- 회의 녹음 파일은 민감정보일 수 있습니다.
- 참가자 동의 없이 녹음하거나 업로드하지 마세요.
- MVP는 인증을 생략했습니다. 외부 공개 전 JWT, SSO, API key 등 인증을 추가하세요.
- 운영 환경에서는 업로드 파일 보관 기간과 삭제 정책을 명확히 해야 합니다.
- API key와 token은 `.env`로 관리하고 코드에 하드코딩하지 않습니다.
- API 응답은 내부 파일 경로를 노출하지 않습니다.

## 향후 Windows Recorder Agent 계획

MVP 이후 Windows 전용 Recorder Agent를 별도 앱으로 추가할 수 있습니다.

권장 방향:

- C# .NET Desktop App
- WASAPI loopback으로 시스템 오디오 캡처
- 마이크와 시스템 오디오 동시 녹음
- 녹음 종료 후 서버 자동 업로드
- 실패 시 재시도
- job 상태 조회
- 결과 페이지 열기

웹에서 앱을 제어하려면 custom URI scheme보다 localhost bridge 방식이 더 적합합니다.

```http
POST http://127.0.0.1:38123/recordings/start
POST http://127.0.0.1:38123/recordings/stop
GET  http://127.0.0.1:38123/recordings/status
```

보안상 localhost listen, pairing token, origin 검증, 사용자 명시적 동의가 필요합니다.

## 이번 MVP에서 제외된 것

- 실시간 회의 봇
- Zoom/Teams/Webex API 직접 연동
- Windows Recorder Agent 실제 구현
- 웹에서 로컬 Windows 앱 제어
- 실시간 스트리밍 STT
- 멀티테넌트 인증/결제
