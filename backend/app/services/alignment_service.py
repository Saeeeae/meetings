DOMINANT_SPEAKER_RATIO = 0.8
SPACE_SNAP_WINDOW = 5


class AlignmentService:
    def align(
        self,
        stt_segments: list[dict],
        speaker_segments: list[dict],
        words: list[dict] | None = None,
    ) -> list[dict]:
        aligned: list[dict] = []
        words_by_time = sorted(words or [], key=lambda w: float(w.get("start", 0.0)))

        for stt in stt_segments:
            start = float(stt.get("start", 0.0))
            end = float(stt.get("end", start))
            text = str(stt.get("text", "")).strip()

            overlaps = self._overlapping_turns(start, end, speaker_segments)

            if not overlaps:
                aligned.append({"start": start, "end": end, "speaker": "UNKNOWN", "text": text})
                continue

            merged = self._merge_consecutive(overlaps)
            speaker_totals: dict[str, float] = {}
            for ov_start, ov_end, speaker in merged:
                speaker_totals[speaker] = speaker_totals.get(speaker, 0.0) + (ov_end - ov_start)
            total_overlap = sum(speaker_totals.values())
            top_speaker = max(speaker_totals, key=speaker_totals.get)

            if (
                not text
                or len(merged) == 1
                or total_overlap <= 0
                or speaker_totals[top_speaker] / total_overlap >= DOMINANT_SPEAKER_RATIO
            ):
                aligned.append({"start": start, "end": end, "speaker": top_speaker, "text": text})
                continue

            segment_words = self._words_within(words_by_time, start, end)
            if segment_words:
                word_pieces = self._split_by_words(segment_words, speaker_segments)
                if word_pieces:
                    aligned.extend(word_pieces)
                    continue

            aligned.extend(self._split_by_turns(text, merged))

        return aligned

    def _overlapping_turns(
        self, start: float, end: float, speaker_segments: list[dict]
    ) -> list[tuple[float, float, str]]:
        turns: list[tuple[float, float, str]] = []
        for sp in speaker_segments:
            sp_start = float(sp.get("start", 0.0))
            sp_end = float(sp.get("end", sp_start))
            ov_start = max(start, sp_start)
            ov_end = min(end, sp_end)
            if ov_end > ov_start:
                turns.append((ov_start, ov_end, str(sp.get("speaker", "UNKNOWN"))))
        turns.sort(key=lambda x: x[0])
        return turns

    def _merge_consecutive(
        self, turns: list[tuple[float, float, str]]
    ) -> list[tuple[float, float, str]]:
        merged: list[tuple[float, float, str]] = []
        for turn in turns:
            if merged and merged[-1][2] == turn[2] and turn[0] - merged[-1][1] < 0.1:
                prev_start, prev_end, prev_speaker = merged[-1]
                merged[-1] = (prev_start, max(prev_end, turn[1]), prev_speaker)
            else:
                merged.append(turn)
        return merged

    def _words_within(self, words: list[dict], start: float, end: float) -> list[dict]:
        return [
            w
            for w in words
            if float(w.get("start", 0.0)) >= start - 0.05 and float(w.get("end", w.get("start", 0.0))) <= end + 0.05
        ]

    def _best_speaker_for_window(
        self, start: float, end: float, speaker_segments: list[dict]
    ) -> str:
        best_speaker = "UNKNOWN"
        best_overlap = 0.0
        for sp in speaker_segments:
            sp_start = float(sp.get("start", 0.0))
            sp_end = float(sp.get("end", sp_start))
            overlap = max(0.0, min(end, sp_end) - max(start, sp_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = str(sp.get("speaker", "UNKNOWN"))
        return best_speaker

    def _split_by_words(self, words: list[dict], speaker_segments: list[dict]) -> list[dict]:
        if not words:
            return []

        annotated: list[tuple[float, float, str, str]] = []
        for word in words:
            w_start = float(word.get("start", 0.0))
            w_end = float(word.get("end", w_start))
            text = str(word.get("text", "")).strip()
            if not text:
                continue
            speaker = self._best_speaker_for_window(w_start, w_end, speaker_segments)
            annotated.append((w_start, w_end, speaker, text))

        if not annotated:
            return []

        pieces: list[dict] = []
        cur_start = annotated[0][0]
        cur_end = annotated[0][1]
        cur_speaker = annotated[0][2]
        cur_tokens: list[str] = [annotated[0][3]]

        for w_start, w_end, speaker, token in annotated[1:]:
            if speaker == cur_speaker:
                cur_end = w_end
                cur_tokens.append(token)
            else:
                pieces.append(
                    {
                        "start": cur_start,
                        "end": cur_end,
                        "speaker": cur_speaker,
                        "text": " ".join(cur_tokens).strip(),
                    }
                )
                cur_start = w_start
                cur_end = w_end
                cur_speaker = speaker
                cur_tokens = [token]

        pieces.append(
            {
                "start": cur_start,
                "end": cur_end,
                "speaker": cur_speaker,
                "text": " ".join(cur_tokens).strip(),
            }
        )
        return [p for p in pieces if p["text"]]

    def _split_by_turns(
        self, text: str, turns: list[tuple[float, float, str]]
    ) -> list[dict]:
        total = sum(t_end - t_start for t_start, t_end, _ in turns)
        if total <= 0:
            return [{"start": turns[0][0], "end": turns[-1][1], "speaker": turns[0][2], "text": text}]

        cursor = 0
        text_len = len(text)
        pieces: list[dict] = []

        for index, (t_start, t_end, speaker) in enumerate(turns):
            if index == len(turns) - 1:
                portion = text[cursor:].strip()
            else:
                share = (t_end - t_start) / total
                end_idx = cursor + max(1, round(text_len * share))
                snap = self._snap_to_space(text, end_idx, cursor)
                portion = text[cursor:snap].strip()
                cursor = snap
            if portion:
                pieces.append({"start": float(t_start), "end": float(t_end), "speaker": speaker, "text": portion})

        if not pieces:
            return [{"start": turns[0][0], "end": turns[-1][1], "speaker": turns[0][2], "text": text}]
        return pieces

    def _snap_to_space(self, text: str, idx: int, lower_bound: int) -> int:
        text_len = len(text)
        if idx <= lower_bound or idx >= text_len:
            return min(max(idx, lower_bound + 1), text_len)
        hi = min(text_len, idx + SPACE_SNAP_WINDOW)
        for j in range(idx, hi):
            if text[j] == " ":
                return j
        lo = max(lower_bound + 1, idx - SPACE_SNAP_WINDOW)
        for j in range(idx - 1, lo - 1, -1):
            if text[j] == " ":
                return j
        return idx
