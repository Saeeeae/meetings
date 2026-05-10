from app.utils.time_utils import format_timestamp


class MinutesService:
    def build_raw_transcript(self, stt_result: dict) -> str:
        return str(stt_result.get("text") or "").strip()

    def build_speaker_transcript(self, aligned_segments: list[dict]) -> str:
        lines = []
        for segment in aligned_segments:
            timestamp = format_timestamp(float(segment["start"]))
            speaker = segment["speaker"]
            text = segment["text"]
            lines.append(f"[{timestamp}] {speaker}: {text}")
        return "\n".join(lines).strip()
