"""Import smoke checks use committed payloads and distinguish proposals."""

import json
import subprocess
import sys

from scripts.dev.reference_packages import ship_check


def test_committed_payload_and_missing_ship_are_not_masked_by_worktree(
    tmp_path, monkeypatch, capsys
):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        )

    git("init", "-q")
    package = tmp_path / "shipment_fixture"
    package.mkdir()
    (package / "__init__.py").write_text("from . import worker\n")
    worker = package / "worker.py"
    worker.write_text("VALUE = 1\n")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps({"kind": "elmer", "ship": ["shipment_fixture/__init__.py"]})
    )
    git("add", ".")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    monkeypatch.setattr(ship_check, "ROOT", tmp_path)
    monkeypatch.setattr(ship_check.pc, "REPO", str(tmp_path))
    monkeypatch.setattr(ship_check.pc, "SOLVER_SHIP", [])
    args = ["plan.json", "shipment_fixture", "--python", sys.executable]
    assert ship_check.main(args) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False and result["missing_ship"] == [
        "shipment_fixture/worker.py"
    ]
    # A dirty dependency must neither poison nor repair the committed payload.
    worker.write_text("raise RuntimeError('uncommitted file must not execute')\n")
    assert ship_check.main([*args, "--write"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requires_commit"] is True
    assert result["plan_source"] == "working-tree proposal"
    assert ship_check.main(args) == 1  # proposal has not been committed
    capsys.readouterr()
    git("add", "plan.json")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "shipment",
    )
    assert ship_check.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ref"] == git("rev-parse", "HEAD").stdout.strip()
    assert result["missing_ship"] == [] and result["plan_source"] == "commit"
    proposed = json.loads(plan.read_text())
    proposed["purpose"] = "updated public diagnostic"
    plan.write_text(json.dumps(proposed))
    assert ship_check.main([*args, "--write"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requires_commit"] is True and result["missing_ship"] == []
