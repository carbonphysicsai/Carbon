"""stage_scratch_twin.py stages a GPU twin's material into a scratch cache and runs no Docker, builds no image and creates or
moves no tag (the 4090 validator's parity measurement; Validator, 2026-10-29)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/stage_scratch_twin.py"
spec = importlib.util.spec_from_file_location("stage_scratch_twin", SCRIPT)
stage_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_tool)

CATALOG = [
    {
        "catalog_id": "v2.f02.physicsnemo.FullyConnected",
        "bundle_refs": {"torch-cu130-py311": {}, "torch-cpu-py311": {}},
    },
    {"catalog_id": "v2.f02.cno.CNO1d", "bundle_refs": {"torch-cpu-py311": {}}},
]


@pytest.fixture
def no_docker(monkeypatch):
    """Any process start or shell-out fails: staging is file copying only."""

    def refuse(*args, **kwargs):
        raise AssertionError("staging started a process")

    for name in ("run", "Popen", "check_call", "check_output", "call"):
        monkeypatch.setattr(subprocess, name, refuse)
    monkeypatch.setattr(os, "system", refuse)


def fake_pipeline(monkeypatch, staged_calls):
    def twin_directory(item, runtime, target, wheelhouse=None):
        target.mkdir(parents=True)
        (target / "bundle.json").write_text("{}")
        return target

    monkeypatch.setattr(stage_tool.pipeline, "twin_directory", twin_directory)

    def stage_bundle(directory, state_dir):
        staged_calls.append((Path(directory).name, Path(state_dir)))
        return {
            "status": "PINNED_MATERIAL_STAGED",
            "bundle_ref": {"bundle_digest": "sha256:" + "d" * 64},
            "image_status": "NOT_BUILT",
        }

    return stage_bundle


def test_staging_copies_the_twin_material_and_runs_no_docker_builds_no_image_creates_no_tag(
    tmp_path, monkeypatch, no_docker
):
    calls = []
    stage_bundle = fake_pipeline(monkeypatch, calls)
    report = stage_tool.stage(
        ["v2.f02.physicsnemo.FullyConnected", "v2.f02.cno.CNO1d"],
        scratch_state_dir=tmp_path / "scratch",
        runtimes=["torch-cu130-py311"],
        catalog=CATALOG,
        stage_bundle=stage_bundle,
    )
    assert [s["catalog_id"] for s in report["staged"]] == [
        "v2.f02.physicsnemo.FullyConnected"
    ]
    assert report["staged"][0]["image_status"] == "NOT_BUILT"
    assert report["skipped"] == [
        {
            "catalog_id": "v2.f02.cno.CNO1d",
            "runtime": "torch-cu130-py311",
            "reason": "no_twin_for_runtime",
        }
    ]
    assert (
        report["docker_commands_run"]
        == report["images_built"]
        == report["tags_created_or_moved"]
        == 0
    )
    assert calls == [("twin", tmp_path / "scratch")]
    assert (
        Path(report["cache_root"])
        == tmp_path
        / "scratch"
        / "environment"
        / "campaigns"
        / ".direct-development"
        / "library-cache"
    )


def test_staging_refuses_unknown_entries_no_entries_and_a_link_as_the_scratch_directory(
    tmp_path, monkeypatch, no_docker
):
    stage_bundle = fake_pipeline(monkeypatch, [])
    kwargs = {
        "runtimes": ["torch-cu130-py311"],
        "catalog": CATALOG,
        "stage_bundle": stage_bundle,
    }
    with pytest.raises(ValueError, match="at least one"):
        stage_tool.stage([], scratch_state_dir=tmp_path / "s", **kwargs)
    with pytest.raises(ValueError, match="not in the catalog"):
        stage_tool.stage(["nope"], scratch_state_dir=tmp_path / "s", **kwargs)
    (tmp_path / "file").write_text("x")
    with pytest.raises(ValueError, match="directory"):
        stage_tool.stage(
            ["v2.f02.cno.CNO1d"], scratch_state_dir=tmp_path / "file", **kwargs
        )
    if hasattr(os, "symlink"):
        try:
            (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
        except OSError:
            return
        with pytest.raises(ValueError, match="link"):
            stage_tool.stage(
                ["v2.f02.cno.CNO1d"], scratch_state_dir=tmp_path / "link", **kwargs
            )


def test_the_runtimes_come_from_the_recorded_manifests_and_an_unregistered_worker_is_refused():
    runtimes = stage_tool.runtimes_of(
        ["a.json", "b.json", "c.json"],
        load_identity=lambda path: path,
        runtime_of=lambda identity: {
            "a.json": "torch-cu130-py311",
            "b.json": "jax-cuda13-py311",
            "c.json": "torch-cu130-py311",
        }[identity],
    )
    assert runtimes == ["torch-cu130-py311", "jax-cuda13-py311"]  # in order, once each
    with pytest.raises(ValueError, match="no registered GPU worker"):
        stage_tool.runtimes_of(
            ["x.json"],
            load_identity=lambda path: path,
            runtime_of=lambda identity: None,
        )


def test_the_module_issues_no_docker_command_of_its_own():
    import ast

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.Import):
            used.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            used.update([node.module or "", *(alias.name for alias in node.names)])
    for forbidden in (
        "subprocess",
        "DockerCLI",
        "system",
        "Popen",
        "run",
        "docker_runtime_cli",
    ):
        assert forbidden not in used, forbidden
