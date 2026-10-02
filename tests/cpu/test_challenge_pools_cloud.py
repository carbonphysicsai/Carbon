"""Public challenge pools on rented CPU pods: native execution and its guards.

No test reaches RunPod. The batch runners' native mode is exercised with real
shell commands. The pod phase's refusal of private plans and the pod
environment's agreement with the motor's Dockerfile are checked directly.
"""

from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["cold_plate", "motor"])
def runner(request):
    return _load(
        f"{request.param}_run_batch_native",
        f"scripts/dev/{request.param}/reference/run_batch.py",
    )


def test_a_native_case_reports_its_exit_code(runner, tmp_path):
    code, wall, _ = runner.run_native(["bash", "-c", "exit 3"], tmp_path, 10)
    assert code == 3 and wall < 10


def test_a_native_timeout_kills_the_whole_case_and_nothing_else(runner, tmp_path):
    marker = tmp_path / "survived"
    start = time.monotonic()
    code, _, _ = runner.run_native(
        ["bash", "-c", f"(sleep 3; touch {marker}) & sleep 30"], tmp_path, 1
    )
    assert code is None and time.monotonic() - start < 10
    time.sleep(3.5)
    # The background child was in the case's process group and died with it.
    assert not marker.exists()


def test_the_cold_plate_runs_its_pinned_commands_natively(tmp_path, monkeypatch):
    runner = _load(
        "cold_plate_run_batch_native2", "scripts/dev/cold_plate/reference/run_batch.py"
    )
    monkeypatch.setattr(runner, "NATIVE", "test-environment")
    monkeypatch.setattr(runner.openfoam, "COMMANDS", ("echo ran > ran.txt",))
    status, _, detail = runner.solve(tmp_path, "unused", 2.0, 10)
    assert (status, detail) == (None, "exit 0")
    assert (tmp_path / "ran.txt").read_text().strip() == "ran"
    monkeypatch.setattr(runner.openfoam, "COMMANDS", ("sleep 30",))
    status, _, _ = runner.solve(tmp_path, "unused", 2.0, 1)
    assert status == "REFERENCE_TIMEOUT"


def test_the_motor_runs_its_case_script_natively(tmp_path, monkeypatch):
    runner = _load(
        "motor_run_batch_native2", "scripts/dev/motor/reference/run_batch.py"
    )
    monkeypatch.setattr(runner, "NATIVE", "test-environment")
    # No mesh.py here, so the case's first command fails: the native path
    # reports the shell's exit, as the container path does.
    p = {"steps": [0], "n_gap": 1440, "poles": 8, "current_a": 0.0, "gamma_deg": 0.0}
    status, _, detail = runner.solve(tmp_path, p, "unused", 2.0, 30)
    assert status is None and detail != "exit 0"


def test_the_pod_phase_refuses_a_private_plan(tmp_path):
    phase = _load("pod_phase", "scripts/dev/challenge_pools/pod_phase.py")
    public = tmp_path / "public.json"
    public.write_text(json.dumps({"batch": "motor-train-v1", "cases": []}))
    assert phase.public_plan(public)["batch"] == "motor-train-v1"
    for plan in (
        {"batch": "motor-private-v1", "cases": []},
        {"batch": "x", "root_commitment": "sha256:0", "cases": []},
    ):
        path = tmp_path / "plan.json"
        path.write_text(json.dumps(plan))
        with pytest.raises(SystemExit, match="private"):
            phase.public_plan(path)
    command = phase.command("motor", public, tmp_path, 32, "env")
    assert command[-2:] == ["--native", "env"]
    assert "--keep" in command and command[command.index("--parallel") + 1] == "32"


def test_the_motor_pod_installs_exactly_what_the_motor_image_pins():
    pod_control = _load("pod_control", "scripts/dev/exam_design/runpod/pod_control.py")
    dockerfile = (REPOSITORY / "scripts/dev/motor/reference/Dockerfile").read_text()
    arg = dict(re.findall(r"^ARG (\w+)=(\S+)$", dockerfile, flags=re.MULTILINE))
    base = re.search(r"^FROM (\S+)$", dockerfile, flags=re.MULTILINE).group(1)
    motor = pod_control.CPU_KINDS["motor"]
    assert motor["image"] == base
    for key in ("SNAPSHOT", "GETDP_URL", "GETDP_SHA256", "GMSH_URL", "GMSH_SHA256"):
        assert arg[key] in motor["setup"], key
    cold = pod_control.CPU_KINDS["cold-plate"]
    from carbon.cold_plate import openfoam

    assert cold["image"].split("@")[1] == openfoam.IMAGE.split("@")[1]
    assert "challenge-pools" in pod_control.CAMPAIGNS
    assert pod_control.CAMPAIGNS["challenge-pools"]["ceiling_usd"] == 25.0
