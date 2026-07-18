import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import IO

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


_warm_process: subprocess.Popen | None = None
_warm_log_file: IO[bytes] | None = None


def shutdown_warm_vllm() -> None:
    global _warm_process, _warm_log_file
    if _warm_process is None:
        return
    logger.info("Shutting down warm vLLM server (worker shutdown).")
    try:
        _warm_process.terminate()
        try:
            _warm_process.wait(timeout=settings.vllm_shutdown_timeout_seconds)
        except subprocess.TimeoutExpired:
            logger.warning("Warm vLLM did not stop in time; killing process.")
            _warm_process.kill()
            _warm_process.wait(timeout=10)
    finally:
        _warm_process = None
        if _warm_log_file is not None:
            _warm_log_file.close()
            _warm_log_file = None


class OnDemandVLLM:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.process: subprocess.Popen | None = None
        self.log_file: IO[bytes] | None = None
        self._started_by_manager = False

    def __enter__(self) -> "OnDemandVLLM":
        if not self.settings.vllm_on_demand:
            return self

        if self.settings.llm_provider.lower() not in {"openai", "openai_compatible", "openai-compatible"}:
            raise RuntimeError("VLLM_ON_DEMAND requires LLM_PROVIDER=openai_compatible.")

        if self.settings.vllm_warm_keep and _warm_process is not None and _warm_process.poll() is None:
            self.process = _warm_process
            self.log_file = _warm_log_file
            logger.debug("Reusing warm-kept vLLM server.")
            return self

        if self._health_check():
            if not self._serves_openai_models():
                raise RuntimeError(
                    f"Port {self.settings.vllm_port} is already serving something that is not an "
                    "OpenAI-compatible LLM server. Stop that service or change VLLM_PORT."
                )
            if self.settings.vllm_reuse_existing or self.settings.vllm_warm_keep:
                logger.info("Existing vLLM server is healthy; reusing it for this job.")
                return self
            raise RuntimeError(f"vLLM port is already serving: {self.settings.vllm_health_url}")

        command = self._build_command()
        log_dir = self.settings.storage_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._prune_old_logs(log_dir)
        log_path = log_dir / f"vllm-{int(time.time())}.log"
        self.log_file = log_path.open("ab")

        logger.info("Starting on-demand vLLM server on %s:%s", self.settings.vllm_host, self.settings.vllm_port)
        try:
            self.process = subprocess.Popen(
                command,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                cwd="/app" if Path("/app").exists() else None,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "vLLM executable was not found. Build the GPU image with INSTALL_VLLM=true or install requirements-vllm.txt."
            ) from exc

        self._started_by_manager = True
        try:
            self._wait_until_ready()
        except BaseException:
            # __exit__ is never called when __enter__ raises, so the spawned
            # server must be reaped here or it keeps holding GPU memory.
            self._terminate_process()
            raise

        if self.settings.vllm_warm_keep:
            self._promote_to_warm()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._started_by_manager or self.process is None:
            self._close_log()
            return

        if self.settings.vllm_warm_keep and _warm_process is self.process:
            return

        logger.info("Stopping on-demand vLLM server.")
        self._terminate_process()

    def _terminate_process(self) -> None:
        if self.process is None:
            self._close_log()
            return
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=self.settings.vllm_shutdown_timeout_seconds)
            except subprocess.TimeoutExpired:
                logger.warning("vLLM did not stop in time; killing process.")
                self.process.kill()
                self.process.wait(timeout=10)
        finally:
            self._close_log()

    def _promote_to_warm(self) -> None:
        global _warm_process, _warm_log_file
        _warm_process = self.process
        _warm_log_file = self.log_file

    def _prune_old_logs(self, log_dir: Path) -> None:
        retention = max(1, self.settings.vllm_log_retention)
        existing = sorted(log_dir.glob("vllm-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in existing[retention - 1 :]:
            try:
                stale.unlink()
            except OSError as exc:
                logger.warning("Failed to prune vLLM log %s: %s", stale, exc)

    def _close_log(self) -> None:
        if self.log_file is not None and self.log_file is not _warm_log_file:
            self.log_file.close()
        self.log_file = None

    def _build_command(self) -> list[str]:
        if self.settings.vllm_command:
            return shlex.split(self.settings.vllm_command)

        command = [
            "vllm",
            "serve",
            self._resolve_model_reference(),
            "--host",
            self.settings.vllm_host,
            "--port",
            str(self.settings.vllm_port),
            "--download-dir",
            str(self.settings.models_dir / "vllm"),
            "--gpu-memory-utilization",
            str(self.settings.vllm_gpu_memory_utilization),
        ]

        if self.settings.llm_api_key:
            command.extend(["--api-key", self.settings.llm_api_key])
        if self.settings.vllm_dtype:
            command.extend(["--dtype", self.settings.vllm_dtype])
        if self.settings.vllm_max_model_len:
            command.extend(["--max-model-len", str(self.settings.vllm_max_model_len)])
        if self.settings.vllm_trust_remote_code:
            command.append("--trust-remote-code")
        if self.settings.vllm_extra_args:
            command.extend(shlex.split(self.settings.vllm_extra_args))

        return command

    def _resolve_model_reference(self) -> str:
        model = self.settings.effective_vllm_model
        local_path = self._local_model_path(model)
        if local_path.exists() and any(local_path.iterdir()):
            return str(local_path)
        return model

    def _local_model_path(self, model: str) -> Path:
        safe_name = model.replace("/", "__")
        return self.settings.models_dir / "vllm" / safe_name

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.settings.vllm_startup_timeout_seconds
        last_error = "not ready"

        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                raise RuntimeError(f"vLLM exited before becoming healthy. Check logs under {self.settings.storage_dir}/logs.")

            try:
                if self._health_check():
                    logger.info("On-demand vLLM server is ready.")
                    return
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(2)

        raise RuntimeError(f"vLLM did not become healthy in time: {last_error}")

    def _health_check(self) -> bool:
        try:
            response = httpx.get(self.settings.vllm_health_url, timeout=2.0)
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def _serves_openai_models(self) -> bool:
        base_url = (
            self.settings.effective_llm_base_url
            or f"http://{self.settings.vllm_host}:{self.settings.vllm_port}/v1"
        ).rstrip("/")
        headers = {}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        try:
            response = httpx.get(f"{base_url}/models", headers=headers, timeout=5.0)
            if response.status_code != 200:
                return False
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return False
        return isinstance(payload, dict) and isinstance(payload.get("data"), list)
