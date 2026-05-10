from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, settings


class LLMService(ABC):
    @abstractmethod
    def cleanup_transcript(self, speaker_transcript: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_minutes(self, cleaned_transcript: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_summary(self, meeting_minutes: str) -> str:
        raise NotImplementedError


class MockLLMService(LLMService):
    def cleanup_transcript(self, speaker_transcript: str) -> str:
        return speaker_transcript

    def generate_minutes(self, cleaned_transcript: str) -> str:
        return f"""# 회의록

## 1. 회의 개요

- 업로드 기반 회의록 생성 MVP 진행 상황을 점검했습니다.

## 2. 참석자 / 화자

- SPEAKER_00
- SPEAKER_01

## 3. 주요 논의 사항

- API 구현은 완료되었고 프론트엔드 연동이 남아 있습니다.
- 업로드 안정성과 결과 다운로드 검증이 필요합니다.

## 4. 결정 사항

- mock provider 기반으로 전체 파이프라인을 먼저 검증합니다.

## 5. 액션 아이템

| 담당자 | 할 일 | 기한 | 비고 |
|---|---|---|---|
| SPEAKER_00 | 업로드 안정성과 다운로드 검증 | 다음 주 | mock 결과 기준 |

## 6. 이슈 및 리스크

- 실제 STT, 화자 분리, LLM provider 전환 시 모델과 토큰 설정이 필요합니다.

## 7. 다음 회의에서 논의할 사항

- 실제 provider 전환 결과와 처리 시간 측정
"""

    def generate_summary(self, meeting_minutes: str) -> str:
        return """# 회의 요약

## 핵심 요약

- 업로드 기반 회의록 생성 MVP의 전체 처리 흐름을 검증합니다.

## 주요 결정

- mock provider를 기본값으로 사용해 GPU와 API 키 없이도 개발 모드에서 동작하게 합니다.

## 액션 아이템

- 업로드 안정성, 상태 polling, 다운로드 동작을 확인합니다.

## 참고 사항

- 실제 STT/화자분리/LLM 전환은 환경변수와 모델 캐시 설정으로 처리합니다.
"""


class OpenAICompatibleLLMService(LLMService):
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.base_url = self.settings.effective_llm_base_url
        self.model = self.settings.effective_llm_model
        if not self.base_url:
            raise RuntimeError("LLM_BASE_URL is required for OpenAI-compatible provider.")
        if not self.model:
            raise RuntimeError("LLM_MODEL or VLLM_MODEL is required for OpenAI-compatible provider.")

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        response = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def cleanup_transcript(self, speaker_transcript: str) -> str:
        return self._chat(
            "한국어 회의 대화 스크립트를 의미 왜곡 없이 문장부호와 반복만 정리한다.",
            f"화자별 발화 형식을 유지해서 정리하세요.\n\n{speaker_transcript}",
        )

    def generate_minutes(self, cleaned_transcript: str) -> str:
        return self._chat(
            "한국어 회의록을 Markdown으로 작성한다.",
            (
                "다음 섹션을 반드시 포함하세요: 회의 개요, 참석자 / 화자, 주요 논의 사항, 결정 사항, "
                "액션 아이템, 이슈 및 리스크, 다음 회의에서 논의할 사항.\n\n"
                f"{cleaned_transcript}"
            ),
        )

    def generate_summary(self, meeting_minutes: str) -> str:
        return self._chat(
            "한국어 회의 요약을 Markdown으로 작성한다.",
            "핵심 요약, 주요 결정, 액션 아이템, 참고 사항 섹션으로 요약하세요.\n\n" + meeting_minutes,
        )


class OllamaLLMService(LLMService):
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        if not self.settings.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is required for Ollama provider.")
        if not self.settings.llm_model:
            raise RuntimeError("LLM_MODEL is required for Ollama provider.")

    def _chat(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.settings.llm_base_url.rstrip('/')}/api/chat",
            json={
                "model": self.settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()

    def cleanup_transcript(self, speaker_transcript: str) -> str:
        return self._chat(
            "다음 한국어 회의 대화 스크립트를 화자별 형식을 유지하며 정리하세요. "
            "의미를 왜곡하지 말고 STT 오류, 반복, 문장부호만 보정하세요.\n\n"
            + speaker_transcript
        )

    def generate_minutes(self, cleaned_transcript: str) -> str:
        return self._chat(
            "다음 대화로 Markdown 회의록을 작성하세요. 필수 섹션: 회의 개요, 참석자 / 화자, 주요 논의 사항, "
            "결정 사항, 액션 아이템 표, 이슈 및 리스크, 다음 회의에서 논의할 사항.\n\n"
            + cleaned_transcript
        )

    def generate_summary(self, meeting_minutes: str) -> str:
        return self._chat(
            "다음 회의록을 Markdown으로 요약하세요. 필수 섹션: 핵심 요약, 주요 결정, 액션 아이템, 참고 사항.\n\n"
            + meeting_minutes
        )


def get_llm_service(app_settings: Settings = settings) -> LLMService:
    provider = app_settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMService()
    if provider in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleLLMService(app_settings)
    if provider == "ollama":
        return OllamaLLMService(app_settings)
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {app_settings.llm_provider}")
