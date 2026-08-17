from __future__ import annotations

import ast
from pathlib import Path


def test_runtime_ranking_dependency_graph_excludes_offline_annotations() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    queue = ["app.services.ranking.service", "app.services.ranking.model"]
    visited: set[str] = set()
    imports: set[str] = set()
    while queue:
        module = queue.pop()
        if module in visited:
            continue
        visited.add(module)
        path = app_root.parent / (module.replace(".", "/") + ".py")
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
                if node.module.startswith("app."):
                    queue.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
                    if alias.name.startswith("app."):
                        queue.append(alias.name)

    forbidden = (
        "evaluation",
        "relevance",
        "label",
        "pairwise",
        "hard_negative",
        "query_splits",
    )
    assert all(not any(term in module for term in forbidden) for module in imports)


def test_runtime_ranking_source_has_no_phase7_or_forbidden_model_inputs() -> None:
    root = Path(__file__).resolve().parents[1] / "app/services/ranking"
    source = "\n".join(
        (root / name).read_text(encoding="utf-8")
        for name in ("service.py", "model.py", "contract.py")
        if (root / name).exists()
    )
    for forbidden in (
        "hard_negative",
        "pairwise",
        "query_splits",
        "final_match_score",
        "CrossEncoder",
    ):
        assert forbidden not in source
