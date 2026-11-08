"""The one-off tool that reclaims finished operations' trusted stage items already on a door's disk.

Real files; only the docker absence query is stood in. Dry run by default; only operations both old enough and with
their container absent are touched; its record matches the carrier's own.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

TOOL = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dev"
    / "reclaim_operation_stages.py"
)
UV = b"fixture uv" * 4096


def _tool():
    spec = importlib.util.spec_from_file_location("_reclaim_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _operation(root, owner, name, *, age_hours, container="carbon-d4-x", intent=True):
    operation = root / "owners" / owner / "ledger" / name
    stage = operation / "input"
    (stage / "overlay" / "pkg").mkdir(parents=True)
    (stage / "overlay" / "pkg" / "m.py").write_bytes(b"V = 1\n")
    (stage / "overlay" / ".overlay.json").write_text(
        json.dumps({"tree_digest": "sha256:" + "a" * 64})
    )
    (stage / "uv-bin").write_bytes(UV)
    (stage / "example.npz").write_bytes(b"keep")
    if intent:
        (operation / "intent.json").write_text(json.dumps({"container": container}))
    for path in sorted(stage.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() or path.name == "uv-bin" else 0o444)
    then = time.time() - age_hours * 3600
    os.utime(stage, (then, then))
    return stage


def _run(tool, root, *args):
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = tool.main([str(root), *args])
    return code, json.loads(buffer.getvalue())


@pytest.fixture
def tool(monkeypatch):
    module = _tool()
    present = {"carbon-d4-running"}
    monkeypatch.setattr(module, "_container_absent", lambda name: name not in present)
    return module


def test_the_dry_run_counts_and_touches_nothing(tool, tmp_path):
    stage = _operation(tmp_path, "h1", "operation-" + "1" * 64, age_hours=10)
    code, out = _run(tool, tmp_path)
    assert code == 0 and out["apply"] is False
    assert (out["stages_with_items"], out["eligible"]) == (1, 1)
    assert out["bytes_eligible"] >= len(UV) and out["bytes_freed"] == 0
    assert (stage / "uv-bin").exists() and (stage / "overlay").exists()


def test_apply_reclaims_only_old_operations_whose_container_is_gone(tool, tmp_path):
    done = _operation(tmp_path, "h1", "operation-" + "1" * 64, age_hours=10)
    young = _operation(tmp_path, "h1", "operation-" + "2" * 64, age_hours=1)
    running = _operation(
        tmp_path,
        "h2",
        "operation-" + "3" * 64,
        age_hours=10,
        container="carbon-d4-running",
    )
    no_intent = _operation(
        tmp_path, "h2", "operation-" + "4" * 64, age_hours=10, intent=False
    )
    code, out = _run(tool, tmp_path, "--apply")
    assert code == 0
    assert (
        out["eligible"],
        out["too_young"],
        out["container_present_or_unknown"],
        out["no_intent"],
    ) == (1, 1, 1, 1)
    assert out["bytes_freed"] >= len(UV)
    assert not (done / "uv-bin").exists() and not (done / "overlay").exists()
    assert (done / "example.npz").read_bytes() == b"keep"
    record = json.loads((done / "reclaimed.json").read_bytes())
    assert record["schema"] == "carbon.autoresearch.reclaimed-stage.v1"
    assert record["overlay_receipt"] == {"tree_digest": "sha256:" + "a" * 64}
    for kept in (young, running, no_intent):
        assert (kept / "uv-bin").exists() and (kept / "overlay").exists()


def test_the_tool_record_is_the_carriers_record(tool, tmp_path):
    from carbon.development_session import research_carrier as carrier

    ours = _operation(tmp_path / "a", "h", "operation-" + "1" * 64, age_hours=10)
    theirs = _operation(tmp_path / "b", "h", "operation-" + "1" * 64, age_hours=10)
    tool.reclaim(ours)
    carrier.reclaim_trusted_stage(theirs)
    assert (ours / "reclaimed.json").read_bytes() == (
        theirs / carrier.RECLAIMED_STAGE
    ).read_bytes()


def test_an_unsafe_age_floor_is_refused(tool, tmp_path):
    with pytest.raises(SystemExit):
        tool.main([str(tmp_path), "--min-age-hours", "0.1"])
