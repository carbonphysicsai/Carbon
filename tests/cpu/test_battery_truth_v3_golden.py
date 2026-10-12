"""Literal v3 compatibility evidence for the deliberate truth_env helper re-pin.

This test also runs unchanged against main's pre-v4 truth_env.py. The actual
truth service and its serialization run with a synchronous fixture worker;
only the solver, provenance and OS/time measurements are deterministic fakes.
"""

import json
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

from carbon.battery import truth, truth_env

REPOSITORY = Path(__file__).resolve().parents[2]


class FixtureProcess:
    def __init__(self, *, target, args):
        self.pid = id(self)
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)

    def join(self, timeout):
        pass


def test_v3_command_and_record_bytes_match_the_literal_golden(tmp_path, monkeypatch):
    overlay, work = tmp_path / "overlay", tmp_path / "work"
    monkeypatch.setattr(truth_env.os, "getuid", lambda: 1000)
    monkeypatch.setattr(truth_env.os, "getgid", lambda: 1000)
    assert truth_env.solve_command(overlay, work, repository=REPOSITORY, workers=6) == [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,size=1g",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "1000:1000",
        "--mount",
        f"type=bind,source={overlay.resolve()},target=/overlay,readonly",
        "--mount",
        f"type=bind,source={REPOSITORY.resolve()},target=/carbon,readonly",
        "--mount",
        f"type=bind,source={work.resolve()},target=/work",
        "-w",
        "/carbon",
        "-e",
        "PYTHONPATH=/carbon:/overlay",
        "--entrypoint",
        "/opt/carbon-worker/bin/python",
        (
            "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:"
            "2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
        ),
        "-m",
        "carbon.battery.truth_env",
        "solve",
        "--jobs",
        "/work/jobs.json",
        "--records",
        "/work/records.jsonl",
        "--workers",
        "6",
        "--timeout-s",
        "1200.0",
    ]
    fixed_provenance = {
        "schema": "carbon.battery.solver-provenance.v1",
        "solver_image": "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:"
        "2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940",
        "overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json",
        "overlay_lock_sha256": "sha256:"
        "6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee",
        "pybamm": "26.8.0.0",
    }
    monkeypatch.setattr(truth_env, "provenance", lambda repository: fixed_provenance)

    def fake_solver(job):
        if job["case_id"] == "golden-failure":
            raise ValueError("fixture reference failure")
        return {"status": "OK", "outputs": {"voltage_v": [3.5, 3.6]}}

    monkeypatch.setattr(truth, "reference_solver", fake_solver)
    monkeypatch.setattr(
        truth.mp,
        "get_context",
        lambda method: SimpleNamespace(Queue=Queue, Process=FixtureProcess),
    )
    monkeypatch.setattr(truth, "_address_space", lambda: 0)
    monkeypatch.setattr(truth.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(
        truth.resource, "getrusage", lambda who: SimpleNamespace(ru_maxrss=1234)
    )
    monkeypatch.setattr(truth.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(truth.time, "sleep", lambda seconds: None)
    jobs = tmp_path / "jobs.json"
    jobs.write_text(
        json.dumps(
            {
                "fingerprint": "v3-golden-fixture",
                "jobs": [
                    {
                        "case_id": name,
                        "c1": 1.0,
                        "c2": 0.5,
                        "t_amb_c": 25.0,
                        "soc0": 0.2,
                    }
                    for name in ("golden-ok", "golden-failure")
                ],
            }
        )
    )
    records = tmp_path / "records.jsonl"
    truth_env.solve(jobs, records, repository=REPOSITORY, workers=6)
    expected = (
        b'{"case_id": "golden-ok", "inputs": {"c1": 1.0, "c2": 0.5, '
        b'"soc0": 0.2, "t_amb_c": 25.0}, "outputs": {"voltage_v": [3.5, 3.6]}, '
        b'"peak_rss_kb": 1234, "refined": false, "solver_provenance": {'
        b'"overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json", '
        b'"overlay_lock_sha256": "sha256:6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee", '
        b'"pybamm": "26.8.0.0", "schema": "carbon.battery.solver-provenance.v1", '
        b'"solver_image": "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:'
        b'2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"}, '
        b'"status": "OK", "wall_s": 0.0}\n'
        b'{"case_id": "golden-failure", "error": "ValueError", "inputs": {'
        b'"c1": 1.0, "c2": 0.5, "soc0": 0.2, "t_amb_c": 25.0}, '
        b'"peak_rss_kb": 1234, "refined": false, "solver_provenance": {'
        b'"overlay_lock": "scripts/dev/exam_design/locks/battery-overlay.lock.json", '
        b'"overlay_lock_sha256": "sha256:6267e033b30728b200d9e0c2aa6b55a9117cd67e03c6f89c9a17294d12e594ee", '
        b'"pybamm": "26.8.0.0", "schema": "carbon.battery.solver-provenance.v1", '
        b'"solver_image": "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:'
        b'2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"}, '
        b'"status": "REFERENCE_SOLVER_FAILED", "wall_s": 0.0}\n'
    )
    assert records.read_bytes() == expected
    assert all("schema" not in json.loads(line) for line in expected.splitlines())
