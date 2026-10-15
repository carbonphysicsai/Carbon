"""Execute CI orchestration with recorded commands, never application work."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
JOURNEY = "tests/service/test_launchpad_production_journey.py"
SMOKE = "scripts/dev/miner_launchpad/browser_smoke.py"


def executable(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def run_ci(tmp_path, shard, *, required=True, fail_target=""):
    """Run the real shell entry point with inert command recorders."""
    script = tmp_path / "scripts/dev/ci.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/dev/ci.sh", script)
    calls = tmp_path / "calls.jsonl"
    executable(
        tmp_path / ".venv/bin/python",
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['CI_CALLS'], 'a') as out:\n"
        "    out.write(json.dumps(args) + '\\n')\n"
        "if os.environ['CI_FAIL_TARGET'] in args:\n"
        "    sys.exit(23)\n"
        "if args and args[0].endswith('select_cpu_profile.py'):\n"
        "    print('tests/cpu/stub.py' if '--tooling-tests' in args "
        "else 'TOOLING_ONLY')\n",
    )
    executable(
        tmp_path / ".venv/bin/git",
        "#!/usr/bin/env bash\nprintf '%s\\n' aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
    )
    executable(tmp_path / "scripts/dev/preflight.sh", "#!/usr/bin/env bash\nexit 0\n")
    env = {
        **os.environ,
        "CARBON_CI_SHARD": shard,
        "CARBON_UV_GROUPS": "mcp",
        "CARBON_REQUIRE_TYPESCRIPT_INTEROP": "0",
        "CARBON_LAUNCHPAD_SMOKE": "1" if required else "0",
        "CI_CALLS": str(calls),
        "CI_FAIL_TARGET": fail_target,
        "QUALITY_BASE_SHA": "a" * 40,
    }
    result = subprocess.run(
        ["bash", str(script)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    return result, commands


@pytest.mark.parametrize("shard", range(6))
def test_hosted_checks_run_once_on_their_assigned_shards(tmp_path, shard):
    result, commands = run_ci(tmp_path, f"{shard}/6")
    assert result.returncode == 0, result.stdout + result.stderr
    assert sum(JOURNEY in command for command in commands) == (shard == 3)
    assert sum(SMOKE in command for command in commands) == (shard == 4)


def test_serial_ci_retains_both_checks(tmp_path):
    result, commands = run_ci(tmp_path, "0/1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert sum(JOURNEY in command for command in commands) == 1
    assert sum(SMOKE in command for command in commands) == 1


@pytest.mark.parametrize("shard,target", [("3/6", JOURNEY), ("4/6", SMOKE)])
def test_required_check_failure_propagates(tmp_path, shard, target):
    result, commands = run_ci(tmp_path, shard, fail_target=target)
    assert any(target in command for command in commands)
    assert result.returncode == 23
    assert "passed." not in result.stdout


def test_browser_free_local_run_does_not_claim_coverage(tmp_path):
    result, commands = run_ci(tmp_path, "4/6", required=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(SMOKE in command for command in commands)
    assert "Launchpad real-browser smoke NOT RUN" in result.stdout


def test_required_workflow_enables_browser_in_canonical_command():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    job = workflow["jobs"]["canonical"]
    assert job["if"] == "needs.preflight.outputs.change_scope == 'RUNTIME_FULL'"
    assert 3 in job["strategy"]["matrix"]["shard"]
    assert 4 in job["strategy"]["matrix"]["shard"]
    commands = [s for s in job["steps"] if s.get("run") == "./scripts/dev/ci.sh"]
    assert len(commands) == 1
    assert commands[0]["env"]["CARBON_LAUNCHPAD_SMOKE"] == "1"
    assert "mcp" in commands[0]["env"]["CARBON_UV_GROUPS"].split()
    gate = workflow["jobs"]["merge-gate"]
    assert "canonical" in gate["needs"]
