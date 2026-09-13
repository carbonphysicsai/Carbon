"""Static authority boundaries for the C-03 DEVELOPMENT worker."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


def _imports(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_worker_has_no_evaluator_reward_or_network_owner_import() -> None:
    imports = _imports("carbon/reconstruction/worker_entrypoint.py")
    forbidden = (
        "carbon.evaluation_packs",
        "carbon.rewards",
        "carbon.scoring",
        "carbon.traineval",
        "requests",
        "urllib",
    )
    assert not any(
        name == prefix or name.startswith(prefix + ".")
        for name in imports
        for prefix in forbidden
    )


def test_profile_structurally_excludes_protected_and_production_use() -> None:
    profile = json.loads(
        (ROOT / "carbon/reconstruction/profiles/c03_cpu_development_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert profile["scope"] == "UNQUALIFIED_PUBLIC_DEVELOPMENT"
    assert profile["security_state"] == "REVIEWABLE_NOT_SECURITY_ACCEPTED"
    assert profile["protected_workloads_enabled"] is False
    assert profile["network"] == {
        "docker_mode": "none",
        "downloads": False,
        "online_logging": False,
    }
    assert profile["claims"]["production_repeat_count"] is None
    assert profile["source"]["canonical_adapter"] == "carbon_jax_lab"
    assert (
        profile["source"]["optional_carbon_jax_research_v0_2"]
        == "ABSENT_UNVERIFIED_NOT_A_BLOCKER"
    )


def test_worker_request_has_no_command_import_uri_or_participant_path() -> None:
    source = (ROOT / "carbon/reconstruction/worker_entrypoint.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    request_fields: set[str] | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_REQUEST_FIELDS"
            and isinstance(node.value, ast.Call)
            and node.value.args
        ):
            request_fields = set(ast.literal_eval(node.value.args[0]))
    assert request_fields is not None
    forbidden = {"command", "argv", "import", "module", "uri", "url", "path"}
    assert request_fields.isdisjoint(forbidden)
    assert "solution" not in request_fields


def test_container_definition_has_fixed_unprivileged_entrypoint() -> None:
    dockerfile = (ROOT / ".worker/Dockerfile").read_text(encoding="utf-8")
    assert "USER 10001:10001" in dockerfile
    assert (
        'ENTRYPOINT ["/opt/carbon/.venv/bin/python", "-I", "-m", "carbon.reconstruction.worker_entrypoint"]'
        in dockerfile
    )
    assert "CARBON_C03_WORKER=1" in dockerfile
    assert "curl " not in dockerfile
    assert "wget " not in dockerfile
