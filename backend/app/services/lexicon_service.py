import re
from collections.abc import Mapping
from typing import Any


class LexiconCorrectionService:
    def __init__(self, corrections: Mapping[str, str] | None = None) -> None:
        rules = [
            (source.strip(), target.strip())
            for source, target in (corrections or {}).items()
            if source.strip() and target.strip() and source != target
        ]
        rules.sort(key=lambda item: len(item[0]), reverse=True)
        self._targets = {f"r{index}": target for index, (_, target) in enumerate(rules)}
        self._pattern = self._compile_pattern(rules)

    @property
    def enabled(self) -> bool:
        return self._pattern is not None

    def _compile_pattern(self, rules: list[tuple[str, str]]) -> re.Pattern[str] | None:
        if not rules:
            return None

        groups: list[str] = []
        for index, (source, _) in enumerate(rules):
            escaped = re.escape(source)
            prefix = r"(?<![0-9A-Za-z])" if source[0].isascii() and source[0].isalnum() else ""
            suffix = r"(?![0-9A-Za-z])" if source[-1].isascii() and source[-1].isalnum() else ""
            groups.append(f"(?P<r{index}>{prefix}{escaped}{suffix})")
        return re.compile("|".join(groups), flags=re.IGNORECASE)

    def correct_text(self, text: str) -> str:
        if self._pattern is None or not text:
            return text
        return self._pattern.sub(lambda match: self._targets[match.lastgroup or ""], text)

    def correct_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **segment,
                "text": self.correct_text(str(segment.get("text", ""))),
            }
            for segment in segments
        ]

    def correct_stt_result(self, stt_result: dict[str, Any]) -> dict[str, Any]:
        corrected = dict(stt_result)
        corrected["text"] = self.correct_text(str(stt_result.get("text", "")))
        corrected["segments"] = self.correct_segments(list(stt_result.get("segments") or []))
        if "words" in stt_result:
            corrected["words"] = self.correct_segments(list(stt_result.get("words") or []))
        return corrected
