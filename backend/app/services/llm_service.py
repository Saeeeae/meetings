from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, settings
from app.utils.text_chunking import chunk_by_lines


PROMPTS_BY_LANG: dict[str, dict[str, str]] = {
    "ko": {
        "cleanup_system": "한국어 회의 대화 스크립트를 의미 왜곡 없이 문장부호와 반복만 정리한다.",
        "cleanup_user_prefix": "화자별 발화 형식을 유지해서 정리하세요.",
        "lexicon_template": (
            " 다음 용어 사전을 우선 적용해 STT 오인식을 보정하되, 사전에 없는 단어는 "
            "임의로 바꾸지 마세요. 사전: {terms}"
        ),
        "minutes_system": (
            "한국어 회의록을 Markdown으로 작성한다. 필수 섹션: 회의 개요, 참석자 / 화자, "
            "주요 논의 사항, 결정 사항, 액션 아이템, 이슈 및 리스크, 다음 회의에서 논의할 사항."
        ),
        "minutes_partial_system": (
            "한국어 회의록 작성을 위해 회의 일부에서 확인된 정보만 같은 섹션 구조로 정리한다. "
            "이 부분만으로 회의 전체를 결론짓지 말고 해당 구간에서 확인된 사실만 적는다."
        ),
        "minutes_merge_system": (
            "여러 구간 회의록 초안을 하나의 일관된 한국어 회의록으로 통합한다. "
            "중복은 제거하고, 충돌은 시간순으로 정리하며, 위 회의록 필수 섹션 구조를 유지한다."
        ),
        "summary_system": (
            "한국어 회의 요약을 Markdown으로 작성한다. "
            "필수 섹션: 핵심 요약, 주요 결정, 액션 아이템, 참고 사항."
        ),
        "summary_partial_system": "한국어 회의 일부의 핵심 포인트를 간결하게 정리한다.",
        "summary_merge_system": (
            "여러 구간 요약을 하나의 일관된 한국어 회의 요약으로 통합한다. "
            "필수 섹션: 핵심 요약, 주요 결정, 액션 아이템, 참고 사항."
        ),
        "chunk_label": "부분 {index}/{total}",
    },
    "en": {
        "cleanup_system": (
            "Clean up an English meeting transcript without altering meaning. "
            "Fix punctuation, remove obvious repetitions, keep speaker-by-speaker format."
        ),
        "cleanup_user_prefix": "Preserve the speaker-by-speaker structure as you clean the text.",
        "lexicon_template": (
            " Prefer the following lexicon when correcting likely STT errors; do not substitute "
            "words that are not in the lexicon. Lexicon: {terms}"
        ),
        "minutes_system": (
            "Write meeting minutes in Markdown. Required sections: Overview, Attendees / Speakers, "
            "Key Discussion Points, Decisions, Action Items, Issues & Risks, Topics for Next Meeting."
        ),
        "minutes_partial_system": (
            "These are minutes for one slice of a longer meeting. Use the same section structure "
            "but only record what is actually confirmed by this slice — do not draw conclusions "
            "about the meeting as a whole."
        ),
        "minutes_merge_system": (
            "Merge several partial meeting-minutes drafts into one coherent set of English minutes. "
            "Remove duplicates, resolve conflicts chronologically, and keep the required sections."
        ),
        "summary_system": (
            "Write a meeting summary in Markdown. Required sections: Key Summary, Major Decisions, "
            "Action Items, Notes."
        ),
        "summary_partial_system": "Summarize the key points of one slice of a meeting concisely.",
        "summary_merge_system": (
            "Merge several partial summaries into one coherent English meeting summary. "
            "Required sections: Key Summary, Major Decisions, Action Items, Notes."
        ),
        "chunk_label": "Part {index}/{total}",
    },
}


def _resolve_language(hint: str | None) -> str:
    if not hint:
        return "ko"
    normalized = hint.strip().lower().replace("_", "-")
    if normalized.startswith(("ko", "korean")):
        return "ko"
    if normalized.startswith(("en", "english")):
        return "en"
    return "ko"


class LLMService(ABC):
    def __init__(self, app_settings: Settings = settings, language: str | None = None) -> None:
        self.settings = app_settings
        self._lang = _resolve_language(language or self.settings.stt_language)

    @abstractmethod
    def _run_prompt(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def _prompts(self) -> dict[str, str]:
        return PROMPTS_BY_LANG[self._lang]

    def _lexicon_clause(self) -> str:
        entries = self.settings.load_lexicon_prompt_entries()
        if not entries:
            return ""
        return self._prompts()["lexicon_template"].format(terms=", ".join(entries))

    def _chunks(self, text: str) -> list[str]:
        return chunk_by_lines(text, max(2000, self.settings.llm_max_input_chars))

    def _label_chunk(self, index: int, total: int) -> str:
        return self._prompts()["chunk_label"].format(index=index, total=total)

    def cleanup_transcript(self, speaker_transcript: str) -> str:
        prompts = self._prompts()
        system_prompt = prompts["cleanup_system"] + self._lexicon_clause()
        cleaned_parts: list[str] = []
        for chunk in self._chunks(speaker_transcript):
            cleaned_parts.append(
                self._run_prompt(system_prompt, f"{prompts['cleanup_user_prefix']}\n\n{chunk}")
            )
        return "\n".join(part.strip() for part in cleaned_parts if part).strip()

    def generate_minutes(self, cleaned_transcript: str) -> str:
        prompts = self._prompts()
        chunks = self._chunks(cleaned_transcript)
        if len(chunks) == 1:
            return self._run_prompt(prompts["minutes_system"], chunks[0])

        partials: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            partials.append(
                self._run_prompt(
                    prompts["minutes_partial_system"],
                    f"{self._label_chunk(index, len(chunks))}\n\n{chunk}",
                )
            )
        return self._run_prompt(prompts["minutes_merge_system"], "\n\n---\n\n".join(partials))

    def generate_summary(self, cleaned_transcript: str) -> str:
        prompts = self._prompts()
        chunks = self._chunks(cleaned_transcript)
        if len(chunks) == 1:
            return self._run_prompt(prompts["summary_system"], chunks[0])

        partials: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            partials.append(
                self._run_prompt(
                    prompts["summary_partial_system"],
                    f"{self._label_chunk(index, len(chunks))}\n\n{chunk}",
                )
            )
        return self._run_prompt(prompts["summary_merge_system"], "\n\n---\n\n".join(partials))


class MockLLMService(LLMService):
    def _run_prompt(self, system_prompt: str, user_prompt: str) -> str:
        return user_prompt

    def cleanup_transcript(self, speaker_transcript: str) -> str:
        return speaker_transcript

    def generate_minutes(self, cleaned_transcript: str) -> str:
        if self._lang == "en":
            return _MOCK_MINUTES_EN
        return _MOCK_MINUTES_KO

    def generate_summary(self, cleaned_transcript: str) -> str:
        if self._lang == "en":
            return _MOCK_SUMMARY_EN
        return _MOCK_SUMMARY_KO


class OpenAICompatibleLLMService(LLMService):
    def __init__(self, app_settings: Settings = settings, language: str | None = None) -> None:
        super().__init__(app_settings, language)
        self.base_url = self.settings.effective_llm_base_url
        self.model = self.settings.effective_llm_model
        if not self.base_url:
            raise RuntimeError("LLM_BASE_URL is required for OpenAI-compatible provider.")
        if not self.model:
            raise RuntimeError("LLM_MODEL or VLLM_MODEL is required for OpenAI-compatible provider.")

    def _run_prompt(self, system_prompt: str, user_prompt: str) -> str:
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
            timeout=self.settings.llm_request_timeout_seconds,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data["choices"][0]["message"]["content"].strip()


class OllamaLLMService(LLMService):
    def __init__(self, app_settings: Settings = settings, language: str | None = None) -> None:
        super().__init__(app_settings, language)
        if not self.settings.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is required for Ollama provider.")
        if not self.settings.llm_model:
            raise RuntimeError("LLM_MODEL is required for Ollama provider.")

    def _run_prompt(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self.settings.llm_base_url.rstrip('/')}/api/chat",
            json={
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=self.settings.llm_request_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()


def get_llm_service(app_settings: Settings = settings, language: str | None = None) -> LLMService:
    provider = app_settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMService(app_settings, language)
    if provider in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleLLMService(app_settings, language)
    if provider == "ollama":
        return OllamaLLMService(app_settings, language)
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {app_settings.llm_provider}")


_MOCK_MINUTES_KO = """# 회의록

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

_MOCK_SUMMARY_KO = """# 회의 요약

## 핵심 요약

- 업로드 기반 회의록 생성 MVP의 전체 처리 흐름을 검증합니다.

## 주요 결정

- mock provider를 기본값으로 사용해 GPU와 API 키 없이도 개발 모드에서 동작하게 합니다.

## 액션 아이템

- 업로드 안정성, 상태 polling, 다운로드 동작을 확인합니다.

## 참고 사항

- 실제 STT/화자분리/LLM 전환은 환경변수와 모델 캐시 설정으로 처리합니다.
"""

_MOCK_MINUTES_EN = """# Meeting Minutes

## 1. Overview

- Reviewed progress on the upload-driven meeting-minutes MVP.

## 2. Attendees / Speakers

- SPEAKER_00
- SPEAKER_01

## 3. Key Discussion Points

- Backend API is complete; frontend integration remains.
- Upload reliability and result download need verification.

## 4. Decisions

- Validate the full pipeline against the mock provider first.

## 5. Action Items

| Owner | Task | Due | Notes |
|---|---|---|---|
| SPEAKER_00 | Verify upload reliability and download flow | Next week | Against mock output |

## 6. Issues & Risks

- Switching to real STT, diarization, and LLM providers requires model and token setup.

## 7. Topics for Next Meeting

- Provider switch results and processing-time measurements
"""

_MOCK_SUMMARY_EN = """# Meeting Summary

## Key Summary

- Validate the end-to-end flow of the upload-driven meeting-minutes MVP.

## Major Decisions

- Default to the mock provider so the dev mode works without GPU or API keys.

## Action Items

- Verify upload reliability, status polling, and the download flow.

## Notes

- Switch real STT / diarization / LLM via env vars and the model cache.
"""
