"""The Merge gate hands the Hub result only to a gate that still names it.

The owner retired the Development Hub as a merge requirement (2026-10-03).
Merge gate runs the protected base's gate, so the PR that retires it is still
judged by a gate that requires the Hub, and every later PR by one that does
not. These cases execute the real shell block from the workflow rather than a
paraphrase of it, against both kinds of gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/ci.yml"
BEGIN = "# HUB-RETIREMENT BEGIN\n"
END = "# HUB-RETIREMENT END"
HUB_RESULT = "${{ needs.hub-validation.result }}"


def retirement_block(hub_result: str) -> str:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert BEGIN in workflow and END in workflow, "retirement markers missing"
    block = workflow.split(BEGIN, 1)[1].split(END, 1)[0]
    assert HUB_RESULT in block
    lines = (
        line[10:] if line.startswith(" " * 10) else line for line in block.splitlines()
    )
    return "\n".join(lines).replace(HUB_RESULT, hub_result)


def invoke(tmp_path: Path, *, names_hub: bool, hub_result: str):
    gate = tmp_path / "check_merge_gate.py"
    gate.write_text(
        'JOB_NAMES = ("preflight", "canonical"'
        + (', "hub_validation"' if names_hub else "")
        + ")\n",
        encoding="utf-8",
    )
    script = (
        "set -euo pipefail\n"
        f'gate="{gate.as_posix()}"\n'
        + retirement_block(hub_result)
        + '\nprintf "%s\\n" "${hub_args[@]}"\n'
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("result", ["success", "failure", "skipped"])
def test_a_gate_that_names_the_hub_receives_its_result(tmp_path, result):
    run = invoke(tmp_path, names_hub=True, hub_result=result)
    assert run.returncode == 0, run.stderr
    assert run.stdout.split() == ["--hub-validation", result]


def test_a_gate_without_the_hub_requires_the_job_skipped(tmp_path):
    run = invoke(tmp_path, names_hub=False, hub_result="skipped")
    assert run.returncode == 0, run.stderr
    assert run.stdout.split() == []


@pytest.mark.parametrize("result", ["success", "failure", "cancelled", ""])
def test_a_retired_hub_job_that_ran_is_refused(tmp_path, result):
    run = invoke(tmp_path, names_hub=False, hub_result=result)
    assert run.returncode == 1
    assert "Unexpected Development Hub job result" in run.stderr


def test_the_hub_job_runs_only_while_the_protected_gate_names_it():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "hub_required: ${{ steps.hub.outputs.hub_required }}" in workflow
    assert 'git show "${BASE_SHA}:scripts/dev/check_merge_gate.py"' in workflow
    assert "if: needs.preflight.outputs.hub_required == 'true' &&" in workflow
    current_gate = (REPOSITORY_ROOT / "scripts/dev/check_merge_gate.py").read_text(
        encoding="utf-8"
    )
    assert '"hub_validation"' not in current_gate
