from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.evaluation.contracts import EvaluationManifestV1
from app.services.match_runs.contracts import canonical_fingerprint


def quality_result_fingerprint(quality: dict[str, Any]) -> str:
    def deterministic(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: deterministic(item)
                for key, item in value.items()
                if key not in {"recorded_at", "started_at", "ended_at"}
                and "latency" not in key.casefold()
                and not key.casefold().endswith("_ms")
            }
        if isinstance(value, list):
            return [deterministic(item) for item in value]
        return value

    return canonical_fingerprint({"contract": "phase11_quality_result_v1", "quality": deterministic(quality)})


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ArtifactWriter:
    def __init__(self, output_root: Path, run_id: str, identity: dict[str, Any]) -> None:
        if not run_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in run_id):
            raise ValueError("run_id contains unsupported characters")
        self.output_root = output_root
        self.run_id = run_id
        self.identity = dict(identity)
        self.staging = output_root / f".{run_id}.staging"
        self.final = output_root / run_id
        self._started = False
        self._started_at: str | None = None

    def start(self) -> None:
        if self.final.exists() or self.staging.exists():
            raise FileExistsError(f"evaluation run already exists: {self.run_id}")
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.staging.mkdir()
        self._started = True
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._write_manifest("RUNNING")

    def _write_manifest(self, status: str, **values: Any) -> None:
        payload = {
            "contract_version": "phase11_evaluation_manifest_v1",
            "evaluation_run_id": self.run_id,
            **self.identity,
            "status": status,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "started_at": self._started_at,
            "ended_at": None if status == "RUNNING" else datetime.now(timezone.utc).isoformat(),
            **values,
        }
        fingerprint_payload = {key: value for key, value in payload.items() if key != "manifest_fingerprint"}
        payload["manifest_fingerprint"] = canonical_fingerprint(fingerprint_payload)
        EvaluationManifestV1.model_validate(payload)
        _write_json(self.staging / "manifest.json", payload)

    def _finalize(self) -> Path:
        if not self._started or not self.staging.is_dir():
            raise RuntimeError("evaluation run is not RUNNING")
        if self.final.exists():
            raise FileExistsError(f"evaluation run already exists: {self.run_id}")
        self.staging.rename(self.final)
        self._started = False
        return self.final

    def complete(self, *, quality: dict[str, Any], diagnostics: dict[str, Any], warnings: list[str], report: str | None = None) -> Path:
        if not quality or not any(key in quality for key in ("r1", "r2", "explanation")):
            raise ValueError("required quality output is empty")
        if report is None:
            raise ValueError("COMPLETED artifact requires report.md")
        if not report.endswith("\n") or report.endswith("\n\n"):
            raise ValueError("report.md must have exactly one final newline")
        if any(line != line.rstrip() for line in report.splitlines()):
            raise ValueError("report.md contains trailing whitespace")
        per_query = {
            "r1": quality.get("r1", {}).get("per_query_provenance", {}),
            "r2": {
                "pool_provenance": quality.get("r2", {}).get("per_query_pool_provenance", {}),
                "metrics": {
                    strategy: {
                        metric: values.get("per_query", {})
                        for metric, values in metrics.items()
                    }
                    for strategy, metrics in quality.get("r2", {}).get("strategies", {}).items()
                },
            },
            "r3": quality.get("r3", {}).get("per_query", {}),
        }
        _write_json(self.staging / "per_query.json", per_query)
        _write_json(self.staging / "report.json", {"quality": quality, "diagnostics": diagnostics})
        (self.staging / "report.md").write_text(report, encoding="utf-8")
        hashes = {
            path.name: file_sha256(path)
            for path in sorted(self.staging.iterdir())
            if path.is_file() and path.name != "manifest.json"
        }
        self._write_manifest(
            "COMPLETED",
            quality_result_fingerprint=quality_result_fingerprint(quality),
            file_sha256=hashes,
            warnings=warnings,
        )
        return self._finalize()

    def invalidate(self, reason: str) -> Path:
        self._discard_partial_success_files()
        _write_json(self.staging / "failure.json", {"status": "INVALID", "reason": reason})
        self._write_manifest("INVALID", failure_reason=reason)
        return self._finalize()

    def fail(self, reason: str) -> Path:
        self._discard_partial_success_files()
        _write_json(self.staging / "failure.json", {"status": "FAILED", "reason": reason})
        self._write_manifest("FAILED", failure_reason=reason)
        return self._finalize()

    def _discard_partial_success_files(self) -> None:
        for name in ("per_query.json", "report.json", "report.md", "latency.json"):
            path = self.staging / name
            if path.is_file():
                path.unlink()
