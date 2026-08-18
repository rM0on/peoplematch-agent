from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_settings_expose_explicit_cross_encoder_paths_and_batch_size() -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None)
    assert settings.cross_encoder_model_path.endswith(
        "artifacts\\phase7\\cross_encoder_ms_marco_minilm_l6_v2"
    ) or settings.cross_encoder_model_path.endswith(
        "artifacts/phase7/cross_encoder_ms_marco_minilm_l6_v2"
    )
    assert settings.cross_encoder_model_manifest_path.endswith(
        "data\\eval\\phase7\\cross_encoder_model_manifest_v1.json"
    ) or settings.cross_encoder_model_manifest_path.endswith(
        "data/eval/phase7/cross_encoder_model_manifest_v1.json"
    )
    assert settings.cross_encoder_text_contract_path.endswith(
        "data\\eval\\phase7\\cross_encoder_text_contract_v1.json"
    ) or settings.cross_encoder_text_contract_path.endswith(
        "data/eval/phase7/cross_encoder_text_contract_v1.json"
    )
    assert settings.cross_encoder_batch_size == 10


def test_latency_benchmark_uses_portfolio_sample_defaults() -> None:
    import inspect

    from scripts.benchmark_cross_encoder_latency import run_benchmark

    signature = inspect.signature(run_benchmark)
    assert signature.parameters["warmup_count"].default == 5
    assert signature.parameters["measurement_count"].default == 50


def test_backend_docker_installs_pinned_torch_from_cpu_index_first() -> None:
    requirements = (REPOSITORY_ROOT / "backend" / "requirements.txt").read_text(
        encoding="utf-8"
    )
    dockerfile = (REPOSITORY_ROOT / "backend" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    normalized_dockerfile = " ".join(
        line.strip().removesuffix("\\").strip() for line in dockerfile.splitlines()
    )

    assert "torch==2.8.0" in requirements.splitlines()
    assert "torch==2.8.0+cpu" not in requirements
    assert "nvidia-" not in requirements.lower()
    assert (
        "ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu"
        in dockerfile
    )

    cpu_install = (
        'python -m pip install --index-url "${PYTORCH_CPU_INDEX_URL}" '
        "torch==2.8.0"
    )
    shared_install = "python -m pip install -r requirements.txt"
    assert cpu_install in normalized_dockerfile
    assert normalized_dockerfile.index(cpu_install) < normalized_dockerfile.index(
        shared_install
    )
    assert "--extra-index-url" not in dockerfile
