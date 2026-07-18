import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LexiconData:
    terms: tuple[str, ...]
    corrections: dict[str, str]


def _unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.casefold()
        if normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return tuple(result)


def _add_correction(corrections: dict[str, str], source: str, target: str, location: str) -> None:
    source = source.strip()
    target = target.strip()
    if not source or not target:
        raise ValueError(f"Empty lexicon entry at {location}")

    existing_key = next((key for key in corrections if key.casefold() == source.casefold()), None)
    if existing_key is not None:
        if corrections[existing_key] != target:
            raise ValueError(f"Conflicting lexicon entry for '{source}' at {location}")
        return
    corrections[source] = target


def _load_json(path: Path) -> LexiconData:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON lexicon at {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"JSON lexicon must be an object of \"misheard\": \"canonical\" pairs: {path}")

    corrections: dict[str, str] = {}
    for source, target in payload.items():
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError(f"JSON lexicon keys and values must be strings: {path}")
        _add_correction(corrections, source, target, str(path))

    return LexiconData(terms=_unique(list(corrections.values())), corrections=corrections)


def _split_mapping(line: str) -> tuple[str, str] | None:
    for separator in ("\t", "=>", "->"):
        if separator in line:
            source, target = line.split(separator, 1)
            return source, target
    return None


def _load_text(path: Path) -> LexiconData:
    terms: list[str] = []
    corrections: dict[str, str] = {}

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        mapping = _split_mapping(line)
        if mapping is None:
            terms.append(line)
            continue
        source, target = mapping
        _add_correction(corrections, source, target, f"{path}:{line_number}")
        terms.append(target.strip())

    return LexiconData(terms=_unique(terms), corrections=corrections)


def load_lexicon(path: Path | None) -> LexiconData:
    if path is None or not path.is_file():
        return LexiconData(terms=(), corrections={})
    if path.suffix.lower() == ".json":
        return _load_json(path)
    return _load_text(path)
