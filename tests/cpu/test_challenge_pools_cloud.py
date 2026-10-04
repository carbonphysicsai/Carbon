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
    # Its ceiling is operator configuration, never in the repository.
    assert "ceiling_usd" not in pod_control.CAMPAIGNS["challenge-pools"]


def _write(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def test_a_pool_is_assembled_in_plan_order_preferring_ok_records(tmp_path):
    assemble = _load("assemble", "scripts/dev/challenge_pools/assemble.py")
    plan = {"cases": [{"case_id": f"train-{i:04d}"} for i in range(4)]}
    local = _write(
        tmp_path / "local.jsonl",
        [
            {"case_id": "train-0001", "status": "OK", "outputs": {"t": [1.0]}},
            {"case_id": "train-0002", "status": "REFERENCE_TIMEOUT"},
        ],
    )
    pod = _write(
        tmp_path / "pod.jsonl",
        [
            {"case_id": "train-0000", "status": "OK", "outputs": {"t": [0.5]}},
            # The same case again, with only analysis round-off: kept once.
            {"case_id": "train-0001", "status": "OK", "outputs": {"t": [1.0 + 1e-13]}},
            {"case_id": "train-0002", "status": "OK", "outputs": {"t": [2.0]}},
            {"case_id": "train-0009", "status": "OK", "outputs": {"t": [9.0]}},
        ],
    )
    records, missing, summary = assemble.assemble(plan, 3, [local, pod])
    assert [r["case_id"] for r in records] == ["train-0000", "train-0001", "train-0002"]
    assert missing == [] and summary["outcomes"] == {"OK": 3}
    # Sources are named relative to their common directory, never by host path.
    assert records[1]["assembled_from"] == "local.jsonl"
    assert records[2]["assembled_from"] == "pod.jsonl"  # OK replaces the timeout
    nested = tmp_path / "run" / "out"
    nested.mkdir(parents=True)
    moved = _write(
        nested / "records.jsonl",
        [{"case_id": "train-0003", "status": "OK", "outputs": {}}],
    )
    records, _, summary = assemble.assemble(plan, 4, [local, moved])
    assert records[-1]["assembled_from"] == "run/out/records.jsonl"
    assert not any(str(tmp_path) in key for key in summary["sources"])
    _, missing, _ = assemble.assemble(plan, 4, [local, pod])
    assert missing == ["train-0003"]


def test_disagreeing_ok_records_are_refused_not_chosen_between(tmp_path):
    assemble = _load("assemble2", "scripts/dev/challenge_pools/assemble.py")
    plan = {"cases": [{"case_id": "train-0000"}]}
    a = _write(
        tmp_path / "a.jsonl",
        [{"case_id": "train-0000", "status": "OK", "outputs": {"t": [1.0]}}],
    )
    b = _write(
        tmp_path / "b.jsonl",
        [{"case_id": "train-0000", "status": "OK", "outputs": {"t": [1.1]}}],
    )
    with pytest.raises(ValueError, match="disagree"):
        assemble.assemble(plan, 1, [a, b])


def test_the_motor_timing_campaign_rents_cpu5c_alone_under_a_lower_rate_guard(
    monkeypatch,
):
    pod_control = _load(
        "pod_control_timing", "scripts/dev/exam_design/runpod/pod_control.py"
    )
    monkeypatch.setattr(pod_control, "CAMPAIGN", "motor-timing")
    flavors, rate = pod_control.cpu_policy()
    # The approved CPU reference timing route: cpu5c, with no fallback flavor.
    assert flavors == ["cpu5c"] and 0 < rate < pod_control.MAX_CPU_RATE
    assert "ceiling_usd" not in pod_control.CAMPAIGNS["motor-timing"]
    monkeypatch.setattr(pod_control, "CAMPAIGN", "challenge-pools")
    assert pod_control.cpu_policy() == (
        pod_control.CPU_FLAVORS,
        pod_control.MAX_CPU_RATE,
    )
    # A campaign may narrow the flavors and the rate guard, never widen them.
    for widened in (
        {"cpu_flavors": ["cpu5c", "gpu"]},
        {"cpu_flavors": []},
        {"max_cpu_rate": pod_control.MAX_CPU_RATE * 2},
        {"max_cpu_rate": 0},
    ):
        spec = {**pod_control.CAMPAIGNS["motor-timing"], **widened}
        monkeypatch.setitem(pod_control.CAMPAIGNS, "motor-timing", spec)
        monkeypatch.setattr(pod_control, "CAMPAIGN", "motor-timing")
        with pytest.raises(SystemExit, match="invalid CPU policy"):
            pod_control.cpu_policy()


def test_the_motor_timing_plan_is_public_train_geometry_only():
    phase = _load("pod_phase_timing", "scripts/dev/challenge_pools/pod_phase.py")
    evidence = REPOSITORY / "docs/development/evidence/motor-timing-2026-10-04"
    plan = phase.public_plan(evidence / "plans/motor-timing-calibration.json")
    study = json.loads(
        (
            REPOSITORY / "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V1.json"
        ).read_text()
    )
    train = {
        json.loads(line)["case_id"]: json.loads(line)["inputs"]
        for line in (
            REPOSITORY / "docs/development/evidence/motor-pools-v1/train.jsonl"
        )
        .read_text()
        .splitlines()
        if line.strip()
    }
    geometry = [k for k in study["designs"][0]["values"]]
    designs = [tuple(d["values"][k] for k in geometry) for d in study["designs"]]
    conditions = {
        c["condition_id"]: c["values"]
        for c in study["conditions"]
        if c["condition_id"] in ("b01", "b02")
    }
    assert len(plan["cases"]) == 12
    for case in plan["cases"]:
        # cal-<TRAIN case id>-<condition id>
        source, condition = case["case_id"][len("cal-") :].rsplit("-", 1)
        inputs = case["inputs"]
        assert tuple(inputs[k] for k in geometry) not in designs
        assert all(inputs[k] == train[source][k] for k in geometry)
        assert all(inputs[k] == v for k, v in conditions[condition].items())


@pytest.mark.parametrize("kind", ["cold_plate", "motor"])
def test_each_runner_imports_from_exactly_what_a_cpu_pod_ships(kind, tmp_path):
    """A pod receives only CPU_SHIP and the plan; the runner must start there."""
    import shutil
    import subprocess
    import sys

    pod_control = _load(
        "pod_control_ship", "scripts/dev/exam_design/runpod/pod_control.py"
    )
    for prefix in pod_control.CPU_SHIP:
        source = REPOSITORY / prefix
        files = [source] if source.is_file() else sorted(source.rglob("*.py"))
        for path in files:
            target = tmp_path / path.relative_to(REPOSITORY)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    runner = tmp_path / f"scripts/dev/{kind}/reference/run_batch.py"
    done = subprocess.run(
        [sys.executable, "-I", "-S", str(runner), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
