def chunk_by_lines(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.split("\n"):
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        if line_len > max_chars and not current:
            for offset in range(0, len(line), max_chars):
                chunks.append(line[offset : offset + max_chars])
            continue
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks or [""]
