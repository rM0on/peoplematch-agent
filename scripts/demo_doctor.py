"""Read-only Phase 12 local demo readiness checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable


CommandRunner = Callable[[list[str]], tuple[int, str]]


def _resolve_command(name: str) -> str:
    return shutil.which(f"{name}.cmd") or shutil.which(name) or name


def _run(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return 1, "unavailable"
    return completed.returncode, (completed.stdout or completed.stderr).strip()


def _file(path: Path) -> dict[str, str]:
    return {"status": "ready" if path.is_file() else "blocked", "detail": path.as_posix() if path.is_file() else f"missing: {path.as_posix()}"}


def collect_readiness(root: Path, *, command_runner: CommandRunner = _run) -> dict[str, dict[str, str]]:
    node_code, node_output = command_runner(["node", "--version"])
    npm_code, npm_output = command_runner([_resolve_command("npm"), "--version"])
    docker_code, _docker_output = command_runner(["docker", "info"])
    node_major = int(node_output.lstrip("v").split(".", 1)[0]) if node_code == 0 and node_output.lstrip("v").split(".", 1)[0].isdigit() else 0
    credential = bool(os.getenv("EXPLANATION_DEEPSEEK_API_KEY", "").strip())
    return {
        "node": {"status": "ready" if node_major == 22 else "blocked", "detail": node_output if node_code == 0 else "not available; Node 22 LTS required"},
        "npm": {"status": "ready" if npm_code == 0 else "blocked", "detail": npm_output if npm_code == 0 else "not available"},
        "docker": {"status": "ready" if docker_code == 0 else "blocked", "detail": "daemon available" if docker_code == 0 else "daemon unavailable"},
        "backend_venv": _file(root / "backend" / ".venv" / "Scripts" / "python.exe"),
        "ltr_artifact": _file(root / "artifacts" / "phase6" / "ltr_ranker_v1.txt"),
        "ce_artifact": _file(root / "artifacts" / "phase7" / "cross_encoder_ms_marco_minilm_l6_v2" / "model.safetensors"),
        "provider_credential": {"status": "configured", "detail": "local credential configured; value redacted"} if credential else {"status": "optional", "detail": "not configured; deterministic mock mode remains available"},
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = collect_readiness(root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] == "blocked" for item in report.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
