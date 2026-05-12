#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def bool_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes", "on"}


def has_files(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def resolve_models_dir(project_root: Path) -> Path:
    raw_models_dir = os.getenv("MODELS_DIR")
    if raw_models_dir == "/models" and not Path("/.dockerenv").exists():
        return project_root / "models"
    if raw_models_dir:
        return Path(raw_models_dir)
    return project_root / "models"


def safe_model_dir_name(model: str) -> str:
    return model.replace("/", "__")


def snapshot_download(repo_id: str, target: Path, token: str | None = None) -> None:
    try:
        from huggingface_hub import snapshot_download as hf_snapshot_download
    except ImportError as exc:
        raise SystemExit("huggingface-hub is required to download models. Install backend/requirements.txt first.") from exc

    target.mkdir(parents=True, exist_ok=True)
    hf_snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        token=token,
    )


def download_faster_whisper(models_dir: Path) -> None:
    model_name = os.getenv("FASTER_WHISPER_MODEL", "small")
    target = models_dir / "faster-whisper" / model_name
    if has_files(target):
        print(f"[models] faster-whisper model already exists, skipping: {target}")
        return

    repo_id = model_name if "/" in model_name else f"Systran/faster-whisper-{model_name}"
    print(f"[models] downloading faster-whisper model {repo_id} -> {target}")
    snapshot_download(repo_id, target, token=os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN"))


def download_pyannote(models_dir: Path) -> None:
    model_id = os.getenv("PYANNOTE_MODEL", "pyannote/speaker-diarization-3.1")
    safe_name = safe_model_dir_name(model_id)
    target = models_dir / "pyannote" / safe_name
    if has_files(target):
        print(f"[models] pyannote model already exists, skipping: {target}")
        return

    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if not token:
        raise SystemExit("[models] HUGGINGFACE_TOKEN is required to download pyannote models.")

    print(f"[models] downloading pyannote model {model_id} -> {target}")
    snapshot_download(model_id, target, token=token)


def download_qwen_asr_model(models_dir: Path) -> None:
    model_id = os.getenv("QWEN_ASR_MODEL") or "Qwen/Qwen3-ASR-1.7B"
    raw_forced_aligner_id = os.getenv("QWEN_ASR_FORCED_ALIGNER_MODEL")
    forced_aligner_id = (
        "Qwen/Qwen3-ForcedAligner-0.6B" if raw_forced_aligner_id is None else raw_forced_aligner_id
    )
    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")

    for label, repo_id in (("Qwen ASR", model_id), ("Qwen ASR forced aligner", forced_aligner_id)):
        if not repo_id:
            print(f"[models] {label} model is empty, skipping.")
            continue

        model_path = Path(repo_id)
        if model_path.is_absolute() and has_files(model_path):
            print(f"[models] {label} points to an existing local path, skipping: {model_path}")
            continue

        target = models_dir / "qwen-asr" / safe_model_dir_name(repo_id)
        if has_files(target):
            print(f"[models] {label} model already exists, skipping: {target}")
            continue

        print(f"[models] downloading {label} model {repo_id} -> {target}")
        snapshot_download(repo_id, target, token=token)


def download_vllm_model(models_dir: Path) -> None:
    model_id = os.getenv("VLLM_MODEL") or os.getenv("LLM_MODEL")
    if not model_id:
        raise SystemExit("[models] VLLM_MODEL or LLM_MODEL is required to download the vLLM model.")

    model_path = Path(model_id)
    if model_path.is_absolute() and has_files(model_path):
        print(f"[models] vLLM model points to an existing local path, skipping: {model_path}")
        return

    target = models_dir / "vllm" / safe_model_dir_name(model_id)
    if has_files(target):
        print(f"[models] vLLM model already exists, skipping: {target}")
        return

    print(f"[models] downloading vLLM model {model_id} -> {target}")
    snapshot_download(model_id, target, token=os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN"))


def main() -> None:
    script_path = Path(__file__).resolve()
    candidate_roots = [Path.cwd(), script_path.parents[1]]
    if len(script_path.parents) > 2:
        candidate_roots.append(script_path.parents[2])

    project_root = candidate_roots[0]
    for root in candidate_roots:
        if (root / ".env").exists():
            project_root = root
            break

    load_dotenv(project_root / ".env")

    models_dir = resolve_models_dir(project_root)
    models_dir.mkdir(parents=True, exist_ok=True)

    stt_provider = os.getenv("STT_PROVIDER", "mock").lower()
    diarization_provider = os.getenv("DIARIZATION_PROVIDER", "mock").lower()
    vllm_on_demand = bool_env("VLLM_ON_DEMAND")

    if stt_provider in {"faster_whisper", "faster-whisper"} or bool_env("DOWNLOAD_FAST_WHISPER_MODEL"):
        download_faster_whisper(models_dir)
    else:
        print("[models] faster-whisper download not needed for current STT_PROVIDER.")

    if stt_provider in {"qwen_asr", "qwen-asr", "qwen3_asr", "qwen3-asr"} or bool_env("DOWNLOAD_QWEN_ASR_MODEL"):
        download_qwen_asr_model(models_dir)
    else:
        print("[models] Qwen ASR download not needed for current STT_PROVIDER.")

    if diarization_provider == "pyannote" or bool_env("DOWNLOAD_PYANNOTE_MODEL"):
        download_pyannote(models_dir)
    else:
        print("[models] pyannote download not needed for current DIARIZATION_PROVIDER.")

    if vllm_on_demand or bool_env("DOWNLOAD_VLLM_MODEL"):
        download_vllm_model(models_dir)
    else:
        print("[models] vLLM model download not needed for current settings.")


if __name__ == "__main__":
    main()
