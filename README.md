# Meeting Minutes AI

회의 녹음 파일을 업로드하면 서버에서 STT, 화자 분리, 스크립트 정리, 회의록 생성, 요약 생성을 비동기로 처리하는 MVP 서비스입니다.

기본값은 `mock` provider입니다. GPU, Hugging Face token, LLM API key 없이도 전체 업로드-분석-결과-다운로드 흐름을 검증할 수 있습니다.

## MVP 제품 시퀀스

```text
사용자가 Windows 또는 회의 플랫폼에서 녹음 파일 준비
→ 웹페이지 접속
→ 녹음 파일 업로드
→ Backend가 분석 Job 생성
→ Worker가 STT 실행
→ Worker가 화자 분리 실행
→ STT 결과와 화자 분리 결과 결합
→ LLM으로 스크립트 정리
→ LLM으로 회의록 작성
→ LLM으로 회의 요약 작성
→ 웹에서 결과 확인
→ 회의록/요약/스크립트 다운로드
```

## 아키텍처

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

## 폴더 구조

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

## 빠른 실행

```bash
cd meeting-minutes-ai
docker compose up --build
```

브라우저에서 접속합니다.

```text
http://localhost:5173
```

Backend health check:

```bash
curl http://localhost:8000/health
```

## Mock Provider 테스트

기본 `.env`는 다음 provider를 사용합니다.

```env
STT_PROVIDER=mock
DIARIZATION_PROVIDER=mock
LLM_PROVIDER=mock
```

이 상태에서는 업로드된 오디오를 ffmpeg로 16kHz mono WAV로 변환한 뒤, STT/화자분리/LLM 결과는 데모 데이터를 반환합니다.

지원 파일 형식:

```text
.mp3 .wav .m4a .aac .flac .mp4 .webm
```

## 모델 캐시와 다운로드

로컬 `./models` 디렉터리가 컨테이너의 `/models`로 마운트됩니다.

```yaml
./models:/models
```

worker 시작 시 `backend/scripts/download_models.py`가 실행됩니다.

- `STT_PROVIDER=faster_whisper`이면 `/models/faster-whisper/{FASTER_WHISPER_MODEL}`을 확인합니다.
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

강제로 faster-whisper 모델만 받기:

```bash
DOWNLOAD_FAST_WHISPER_MODEL=1 FASTER_WHISPER_MODEL=small python backend/scripts/download_models.py
```

강제로 pyannote 모델 받기:

```bash
DOWNLOAD_PYANNOTE_MODEL=1 HUGGINGFACE_TOKEN=... python backend/scripts/download_models.py
```

강제로 vLLM 모델 받기:

```bash
DOWNLOAD_VLLM_MODEL=1 VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct python backend/scripts/download_models.py
```

## faster-whisper 설정

`.env`를 수정합니다.

```env
STT_PROVIDER=faster_whisper
FASTER_WHISPER_MODEL=small
FASTER_WHISPER_DEVICE=auto
FASTER_WHISPER_COMPUTE_TYPE=int8
```

GPU/ML 의존성을 포함해 실행합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

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
STT_PROVIDER=faster_whisper
FASTER_WHISPER_MODEL=small
FASTER_WHISPER_DEVICE=cuda
FASTER_WHISPER_COMPUTE_TYPE=float16

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
