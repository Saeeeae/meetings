import json
import sys
from pathlib import Path

from app.core.logging import configure_logging
from app.services.diarization_service import get_diarization_service
from app.services.stt_service import get_stt_service


def main() -> int:
    configure_logging()

    if len(sys.argv) != 4:
        print("Usage: python -m app.workers.stage_runner <stt|diarization> <audio_path> <output_json>", file=sys.stderr)
        return 2

    stage = sys.argv[1]
    audio_path = sys.argv[2]
    output_path = Path(sys.argv[3])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if stage == "stt":
        result = get_stt_service().transcribe(audio_path)
    elif stage == "diarization":
        result = get_diarization_service().diarize(audio_path)
    else:
        print(f"Unknown stage: {stage}", file=sys.stderr)
        return 2

    output_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
