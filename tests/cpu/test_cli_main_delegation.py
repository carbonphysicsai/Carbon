"""Every CLI here runs its package module's own `main` under `python -m`.

Under `python -m pkg.mod`, the file runs as `__main__`: a second module
whose classes are not the package's. A `main` defined there that checks
`isinstance` against its own class, or catches its own exception type,
misses objects and exceptions made by the package module (3a, 2026-10-08:
`battery_bank status` refused `producer_no_bank` for a valid bank
configuration). The guard therefore imports `main` from the package module.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULES = (
    "carbon.challenge_validator.answer_key",
    "carbon.challenge_validator.battery_bank",
    "carbon.challenge_validator.battery_quiz",
    "carbon.challenge_validator.confirmation",
    "carbon.challenge_validator.distribution",
    "carbon.challenge_validator.leak_detection",
    "carbon.challenge_validator.motor_hidden",
    "carbon.challenge_validator.motor_source",
    "carbon.challenge_validator.onboard",
    "carbon.challenge_validator.producer",
    "carbon.challenge_validator.startup_shard",
    "carbon.challenge_validator.study_sets",
    "carbon.challenge_validator.tuning",
    "carbon.battery.intake",
    "carbon.battery.dev_submit",
    "carbon.battery.od4a",
    "carbon.battery.od4a_dispatch",
    "carbon.battery.truth_env",
    "carbon.battery.operate",
    "carbon.rewards.testnet_winner_publication",
)


def _guard(tree):
    for node in tree.body:
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and getattr(node.test.left, "id", None) == "__name__"
        ):
            return node
    return None


@pytest.mark.parametrize("dotted", MODULES)
def test_the_main_guard_runs_the_package_modules_main(dotted):
    path = ROOT / (dotted.replace(".", "/") + ".py")
    guard = _guard(ast.parse(path.read_text()))
    assert guard is not None, dotted
    imports = [
        node
        for node in ast.walk(guard)
        if isinstance(node, ast.ImportFrom) and node.module == dotted
    ]
    assert [alias.name for node in imports for alias in node.names] == ["main"]
    calls = [
        node
        for node in ast.walk(guard)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "main"
    ]
    assert calls == [], f"{dotted} calls this copy's main"


def test_battery_bank_status_through_python_dash_m(tmp_path):
    """The bank CLI as the owner runs it, a real `python -m` subprocess: a
    valid bank configuration reports its bank, not `producer_no_bank`."""
    import pwd

    from carbon.battery import operate

    user = pwd.getpwuid(os.geteuid()).pw_name
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    deployment = tmp_path / "bank-battery.json"
    deployment.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.validator-deployment.v1",
                "state": str(state / "state.sqlite3"),
                "private_root": str(state / "root.bin"),
                "journal": str(state / "journal.jsonl"),
                "work": str(state),
                "backend": "direct",
                "rule": "v2-bank",
                "require_commitment": False,
                "service_account": user,
            }
        )
    )
    deployment.chmod(0o600)
    assert operate.main(["init", "--config", str(deployment)]) == 0
    record = "2026-10-06-OWNER-REHEARSAL-AND-RELEASE-01.md"
    import hashlib

    digest = hashlib.sha256((ROOT / ".agent/decisions" / record).read_bytes())
    config = tmp_path / "bank-producer.json"
    config.write_text(
        json.dumps(
            {
                "schema": "carbon.challenge-validator.producer-config.v1",
                "service_account": user,
                "producer_dir": str(tmp_path / "producer"),
                "sources": {
                    "battery-fastcharge-ageing-development-v1": {
                        "deployment": str(deployment),
                        "bank": str(tmp_path / "bank"),
                        "approval": {
                            "record": "OWNER-REHEARSAL-AND-RELEASE-01",
                            "file": record,
                            "sha256": digest.hexdigest(),
                        },
                    }
                },
            }
        )
    )
    config.chmod(0o600)
    command = [sys.executable, "-m", "carbon.challenge_validator.battery_bank"]
    done = subprocess.run(
        [*command, "status", "--config", str(config)],
        capture_output=True,
        check=False,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=300,
    )
    answer = json.loads(done.stdout.strip().splitlines()[-1])
    assert done.returncode == 0, (answer, done.stderr[-2000:])
    assert "refused" not in answer and "status" in answer
