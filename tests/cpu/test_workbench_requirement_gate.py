"""The Merge gate's Workbench requirement must reach an explicit decision.

A scope module that exists but reports nothing is not the same as a module that
reported "not required". Collapsing the two would let a broken or truncated
scope run silently disable the job that exists to demand the Workbench suites,
and the job would then be expected to skip. These cases execute the real shell
block from the workflow rather than a paraphrase of it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/ci.yml"
BEGIN = "# WORKBENCH-REQUIREMENT BEGIN\n"
END = "# WORKBENCH-REQUIREMENT END"
SCOPE_RELATIVE = "scripts/dev/workbench_scope.py"

# A stub stands in for the candidate's scope module so each case can control
# exactly what the gate is handed, including nothing at all.
STUB = """import argparse, pathlib, sys
parser = argparse.ArgumentParser()
parser.add_argument("--repository"); parser.add_argument("--base")
parser.add_argument("--github-output", type=pathlib.Path)
args = parser.parse_args()
payload = {payload!r}
if args.github_output is not None:
    args.github_output.write_text(payload, encoding="utf-8")
sys.exit({status})
"""


def requirement_block() -> str:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert BEGIN in workflow and END in workflow, "requirement markers missing"
    block = workflow.split(BEGIN, 1)[1].split(END, 1)[0]
    # The workflow indents the block inside a YAML run scalar.
    return "\n".join(
        line[10:] if line.startswith(" " * 10) else line for line in block.splitlines()
    )


def invoke(
    tmp_path: Path,
    *,
    payload: str | None,
    workbench_result: str,
    preflight: str | None,
    status: int = 0,
) -> subprocess.CompletedProcess[str]:
    candidate = tmp_path / ".carbon-gate-candidate" / "scripts" / "dev"
    candidate.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        (candidate / "workbench_scope.py").write_text(
            STUB.format(payload=payload, status=status), encoding="utf-8"
        )
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir(exist_ok=True)
    environment = {
        **os.environ,
        "RUNNER_TEMP": str(runner_temp),
        "BASE_SHA": "0" * 40,
    }
    if preflight is not None:
        environment["PREFLIGHT_WORKBENCH"] = preflight
    else:
        environment.pop("PREFLIGHT_WORKBENCH", None)
    script = (
        "set -euo pipefail\n"
        f'workbench_result="{workbench_result}"\n' + requirement_block()
    )
    return subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


REQUIRED = "workbench_required=true\n"
NOT_REQUIRED = "workbench_required=false\n"


# --- the decision is honoured -------------------------------------------------


def test_required_and_successful_is_accepted(tmp_path: Path) -> None:
    result = invoke(
        tmp_path, payload=REQUIRED, workbench_result="success", preflight="true"
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("observed", ["failure", "cancelled", "skipped", ""])
def test_required_but_not_successful_is_refused(tmp_path: Path, observed: str) -> None:
    result = invoke(
        tmp_path, payload=REQUIRED, workbench_result=observed, preflight="true"
    )
    assert result.returncode != 0
    assert "did not succeed" in result.stderr


def test_not_required_and_skipped_is_accepted(tmp_path: Path) -> None:
    result = invoke(
        tmp_path, payload=NOT_REQUIRED, workbench_result="skipped", preflight="false"
    )
    assert result.returncode == 0, result.stderr


def test_not_required_but_run_anyway_is_refused(tmp_path: Path) -> None:
    result = invoke(
        tmp_path, payload=NOT_REQUIRED, workbench_result="success", preflight="false"
    )
    assert result.returncode != 0
    assert "Unexpected Workbench" in result.stderr


# --- a present module must decide --------------------------------------------


@pytest.mark.parametrize(
    "payload",
    ["", "unrelated_key=true\n", "workbench_required=\n", "workbench_required=maybe\n"],
    ids=["empty", "unrelated", "blank-value", "malformed"],
)
def test_present_module_without_an_explicit_decision_fails(
    tmp_path: Path, payload: str
) -> None:
    result = invoke(
        tmp_path, payload=payload, workbench_result="skipped", preflight="false"
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no explicit requirement" in result.stderr


def test_duplicate_requirement_output_fails(tmp_path: Path) -> None:
    result = invoke(
        tmp_path,
        payload="workbench_required=true\nworkbench_required=false\n",
        workbench_result="success",
        preflight="true",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Duplicate Workbench requirement" in result.stderr


@pytest.mark.parametrize("second", ["false", "true"], ids=["then-false", "then-true"])
def test_empty_first_record_does_not_hide_a_duplicate(
    tmp_path: Path, second: str
) -> None:
    """Duplicate detection must key on the record, not on its value.

    Keying it on "is the stored value still empty?" lets an empty first record
    wave a second one through, and the gate then acts on a decision drawn from
    output it should have refused outright.
    """
    result = invoke(
        tmp_path,
        payload=f"workbench_required=\nworkbench_required={second}\n",
        workbench_result="success" if second == "true" else "skipped",
        preflight=second,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Duplicate Workbench requirement" in result.stderr


def test_unterminated_final_record_is_not_dropped(tmp_path: Path) -> None:
    """A final line without a newline must still be read.

    A plain ``while read`` loop stops before the body runs for an unterminated
    line, so a trailing duplicate would go unexamined.
    """
    result = invoke(
        tmp_path,
        payload="workbench_required=false\nworkbench_required=true",
        workbench_result="skipped",
        preflight="false",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Duplicate Workbench requirement" in result.stderr


def test_unterminated_single_record_is_honoured(tmp_path: Path) -> None:
    """Reading the unterminated line means acting on it, not merely rejecting."""
    result = invoke(
        tmp_path,
        payload="workbench_required=true",
        workbench_result="success",
        preflight="true",
    )
    assert result.returncode == 0, result.stderr


def test_nonzero_scope_module_fails(tmp_path: Path) -> None:
    """A zero exit is the only basis for trusting the emitted decision."""
    result = invoke(
        tmp_path,
        payload=REQUIRED,
        workbench_result="success",
        preflight="true",
        status=2,
    )
    assert result.returncode != 0


def test_missing_preflight_decision_fails(tmp_path: Path) -> None:
    result = invoke(
        tmp_path, payload=REQUIRED, workbench_result="success", preflight=None
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Preflight produced no explicit" in result.stderr


def test_preflight_and_protected_disagreement_fails(tmp_path: Path) -> None:
    result = invoke(
        tmp_path, payload=REQUIRED, workbench_result="success", preflight="false"
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "disagree" in result.stderr


# --- the historical compatibility path is narrow ------------------------------


def test_candidate_without_the_module_is_treated_as_historical(
    tmp_path: Path,
) -> None:
    """Only a genuine absence may fall back to 'not required'."""
    result = invoke(tmp_path, payload=None, workbench_result="skipped", preflight=None)
    assert result.returncode == 0, result.stderr


def test_absent_module_cannot_accompany_a_preflight_requirement(
    tmp_path: Path,
) -> None:
    """A new missing file must not masquerade as a legacy candidate."""
    result = invoke(
        tmp_path, payload=None, workbench_result="success", preflight="true"
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no scope module" in result.stderr


def test_the_repository_ships_the_scope_module() -> None:
    """The compatibility path must not be reachable for current candidates."""
    assert (REPOSITORY_ROOT / SCOPE_RELATIVE).is_file()
