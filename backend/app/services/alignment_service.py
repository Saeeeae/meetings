class AlignmentService:
    def align(self, stt_segments: list[dict], speaker_segments: list[dict]) -> list[dict]:
        aligned_segments: list[dict] = []

        for segment in stt_segments:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            best_speaker = "UNKNOWN"
            best_overlap = 0.0

            for speaker_segment in speaker_segments:
                speaker_start = float(speaker_segment.get("start", 0.0))
                speaker_end = float(speaker_segment.get("end", speaker_start))
                overlap = max(0.0, min(end, speaker_end) - max(start, speaker_start))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = str(speaker_segment.get("speaker", "UNKNOWN"))

            aligned_segments.append(
                {
                    "start": start,
                    "end": end,
                    "speaker": best_speaker,
                    "text": str(segment.get("text", "")).strip(),
                }
            )

        return aligned_segments
