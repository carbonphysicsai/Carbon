"""A refused `library_bundle.py` command is actionable (Launchpad J0, 19 Oct).

Every refusal names a closed code and the step that clears it; the refusal's
own words stay in `reason`. Before, "step_not_checked" had no next step and
"wheel identity differs" had no code.
"""

from __future__ import annotations

import json

from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from scripts.dev import library_bundle as command
from scripts.dev.miner_launchpad.environment_setup import SetupRefused
from scripts.dev.miner_launchpad.setup_operations import NEXT_STEPS


def test_each_refusal_kind_names_a_code_and_a_next_step():
    unchecked = command.refusal(SetupRefused("compute", "step_not_checked"))
    assert unchecked["code"] == "step_not_checked"
    assert unchecked["field"] == "compute"
    assert unchecked["next_step"] == NEXT_STEPS["step_not_checked"]

    differs = command.refusal(ValueError("wheel identity differs"))
    assert differs["code"] == "library_bundle_material_differs"
    assert differs["reason"] == "wheel identity differs"
    assert differs["next_step"] == command.MATERIAL_NEXT_STEP

    unreadable = command.refusal(FileNotFoundError(2, "No such file or directory"))
    assert unreadable["code"] == "library_bundle_unreadable"

    worker = command.refusal(WorkerFailure(WorkerCode.INVALID))
    assert worker["code"].startswith("library_worker_")
    for row in (unchecked, differs, unreadable, worker):
        assert row["status"] == "REFUSED" and row["next_step"]


def test_the_cli_prints_the_typed_refusal(tmp_path, capsys):
    assert command.main(["doctor", str(tmp_path / "missing")]) == 2
    printed = json.loads(capsys.readouterr().err)
    assert printed["status"] == "REFUSED"
    assert printed["code"] in (
        "library_bundle_unreadable",
        "library_bundle_material_differs",
    )
    assert printed["next_step"]
