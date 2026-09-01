from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_doctor_reports_closed_readiness_checks_without_secret_values(monkeypatch) -> None:
    from scripts.demo_doctor import collect_readiness

    monkeypatch.setenv("EXPLANATION_DEEPSEEK_API_KEY", "must-not-be-reported")
    report = collect_readiness(ROOT, command_runner=lambda _command: (0, "v22.14.0"))

    assert report["provider_credential"]["status"] == "configured"
    assert "must-not-be-reported" not in repr(report)
    assert report["backend_venv"]["status"] == "ready"
    assert report["ltr_artifact"]["status"] == "ready"
    assert report["ce_artifact"]["status"] == "ready"


def test_doctor_marks_wrong_node_and_missing_docker_as_blocking(monkeypatch) -> None:
    from scripts.demo_doctor import collect_readiness

    monkeypatch.delenv("EXPLANATION_DEEPSEEK_API_KEY", raising=False)

    def runner(command: list[str]) -> tuple[int, str]:
        if command[0] == "node":
            return 0, "v20.13.1"
        if command[:2] == ["docker", "info"]:
            return 1, "daemon unavailable"
        return 0, "10.5.2"

    report = collect_readiness(ROOT, command_runner=runner)
    assert report["node"]["status"] == "blocked"
    assert report["docker"]["status"] == "blocked"
    assert report["provider_credential"] == {
        "status": "optional",
        "detail": "not configured; deterministic mock mode remains available",
    }


def test_doctor_resolves_windows_command_shims(monkeypatch) -> None:
    from scripts import demo_doctor

    monkeypatch.setattr(
        demo_doctor.shutil,
        "which",
        lambda name: "C:/Program Files/nodejs/npm.cmd" if name == "npm.cmd" else None,
    )

    assert demo_doctor._resolve_command("npm") == "C:/Program Files/nodejs/npm.cmd"
