"""Rebuilds are consistently timed: a busy host's failure is never the model's (owner 5 Nov 21:3x; Validator-2 21:28).

Claims: `host_quiet.uncontended` is the ruling's three conditions (the lock held, no foreign GPU process, no other Carbon
build container; an unreadable sample is not quiet); `foreign_gpu_compute` counts only GPU processes outside Carbon worker
containers; a crown rebuild that fails while the host is NOT quiet is marked host-contended, raises
`RebuildInfra(REBUILD_HOST_CONTENDED)` and its next try is a fresh generation of the same seed, while on a quiet host
(and outside the grading loop) a failure is exactly as before; averaging that meets a busy host on every try ends
UNAVAILABLE / REBUILD_HOST_CONTENDED, never UNSTABLE or a loss; a stepwise re-measure never keeps a contended rebuild;
the decision's public view carries no probe field. All values are synthetic.
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import host_quiet
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.research import DirectTaskStateV3
from tests.cpu.test_crown_average import CHALLENGE, KEY, _grade, _rule
from tests.cpu.test_crown_rebuild_evidence import HOST, ORIGIN, _fixture, _starts

# ---------------------------------------------------------------- the three conditions


def _quiet(**changes):
    args = {
        "lock_held": True,
        "samples": [1, 1],
        "stop": 0,
        "gpu_samples": [0, 0],
        "gpu_stop": 0,
    }
    args.update(changes)
    return host_quiet.uncontended(**args)


@pytest.mark.parametrize(
    ("changes", "why"),
    [
        ({"lock_held": False}, "the build did not hold the host grading lock"),
        ({"samples": [1, 2]}, "another Carbon build container ran during it"),
        ({"stop": 1}, "a Carbon container still ran at the stop"),
        ({"samples": [1, None]}, "a container sample could not be read"),
        ({"gpu_samples": [0, 1]}, "a foreign GPU compute process ran during it"),
        ({"gpu_stop": 1}, "a foreign GPU compute process ran at the stop"),
        ({"gpu_samples": [None]}, "a GPU sample could not be read"),
        ({"gpu_stop": None}, "the GPU could not be read at the stop"),
    ],
)
def test_any_failed_condition_or_unreadable_sample_is_not_quiet(changes, why):
    assert _quiet() is True
    assert _quiet(**changes) is False, why


def test_a_build_with_no_in_run_samples_is_judged_by_its_stop_sample():
    assert _quiet(samples=[], gpu_samples=[]) is True
    assert _quiet(samples=[], gpu_samples=[], stop=None) is False


# ---------------------------------------------------------------- the GPU probe


def _fake_run(outputs):
    def run(argv, timeout=10):
        key = argv[0] if argv[0] != "docker" else "docker " + argv[1]
        out = outputs[key]
        if isinstance(out, BaseException):
            raise out
        code, text = out
        return SimpleNamespace(returncode=code, stdout=text.encode())

    return run


def test_no_nvidia_driver_means_no_gpu_to_contend(monkeypatch):
    monkeypatch.setattr(
        host_quiet, "_run", _fake_run({"nvidia-smi": FileNotFoundError()})
    )
    assert host_quiet.foreign_gpu_compute() == 0


@pytest.mark.parametrize(
    "outputs",
    [
        {"nvidia-smi": (9, "")},
        {"nvidia-smi": subprocess.TimeoutExpired("nvidia-smi", 10)},
        {"nvidia-smi": (0, "not-a-pid\n")},
        {"nvidia-smi": (0, "101\n"), "docker ps": (1, "")},
        {
            "nvidia-smi": (0, "101\n"),
            "docker ps": (0, "c1 carbon-d4-x\n"),
            "docker top": (1, ""),
        },
    ],
)
def test_an_unreadable_gpu_or_daemon_is_unknown(monkeypatch, outputs):
    monkeypatch.setattr(host_quiet, "_run", _fake_run(outputs))
    assert host_quiet.foreign_gpu_compute() is None


def test_only_gpu_processes_outside_carbon_worker_containers_are_foreign(monkeypatch):
    outputs = {
        "nvidia-smi": (0, "101\n202\n"),
        "docker ps": (0, "c1 carbon-d4-abc\nc9 someone-elses\n"),
        "docker top": (0, "PID\n101\n150\n"),
    }
    monkeypatch.setattr(host_quiet, "_run", _fake_run(outputs))
    assert host_quiet.foreign_gpu_compute() == 1  # 202 is not in our worker container
    outputs["nvidia-smi"] = (0, "101\n")
    assert host_quiet.foreign_gpu_compute() == 0
    outputs["nvidia-smi"] = (0, "")
    assert host_quiet.foreign_gpu_compute() == 0


def test_the_probe_samples_while_the_build_runs_and_takes_a_stop_sample():
    import time as clock

    probe = host_quiet.Probe(
        lock_held=True, containers=lambda: 1, gpu=lambda: 0, seconds=0.01
    ).start()
    clock.sleep(0.1)
    verdict = probe.verdict()
    assert verdict.samples >= 2 and verdict.max_worker_containers == 1
    assert (
        verdict.stop_worker_containers == 1 and verdict.quiet is False
    )  # a container left at the stop
    assert probe.verdict() is verdict  # taken once


def test_outside_the_grading_loop_there_is_no_probe():
    assert host_quiet.start() is None and host_quiet.finish(None) is None


# ---------------------------------------------------------------- the crown rebuild path


def _rebuilder(tmp_path, monkeypatch):
    adapter, host, _keys, _ = _fixture()
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    graded = _grade(0.70)
    monkeypatch.setattr(
        retention,
        "retain_rebuild_evidence",
        lambda a, t, **k: {"submission_id": t, "evidence": graded["evidence"]},
    )
    artifacts = tmp_path / "auto-grade" / "artifacts"
    artifacts.mkdir(parents=True)

    def rebuild(seed):
        return retention.rebuild_at_seed(
            adapter,
            ORIGIN,
            seed,
            host_owner=HOST,
            artifact_directory=artifacts,
            entry_directory=artifacts,
        )

    return host, rebuild, tmp_path / "auto-grade" / host_quiet.MARKS_DIR


@pytest.fixture
def loop():
    """A grading loop context (`AutoGrader.run_once`) whose host state each test sets."""
    state = {"lock_held": True, "containers": 0, "gpu": 0}
    token = host_quiet.activate(
        lock_held=True,
        containers=lambda: state["containers"],
        gpu=lambda: state["gpu"],
        seconds=60,  # one stop sample only: these builds return at once
    )
    yield state
    host_quiet.deactivate(token)


def _activate(lock_held, containers, gpu):
    return host_quiet.activate(
        lock_held=lock_held, containers=lambda: containers, gpu=lambda: gpu, seconds=60
    )


def test_a_quiet_host_failure_is_exactly_as_today_the_same_task_is_read_again(
    tmp_path, monkeypatch, loop
):
    host, rebuild, marks = _rebuilder(tmp_path, monkeypatch)
    host.state = (
        DirectTaskStateV3.REFUSED
    )  # the candidate's own build stop on a quiet host
    for _ in range(2):
        with pytest.raises(
            retention.RetentionUnavailable, match="rebuild_task_refused"
        ):
            rebuild(4242)
    assert (
        len(host.states) == 1
    )  # today's rule: a REFUSED task is reused, never rebuilt
    assert not marks.exists()


@pytest.mark.parametrize(
    ("lock_held", "containers", "gpu", "why"),
    [
        (False, 0, 0, "no host lock"),
        (True, 1, 0, "another Carbon build container at the stop"),
        (True, 0, 1, "a foreign GPU process"),
        (True, None, 0, "the daemon could not say"),
        (True, 0, None, "the GPU could not be read"),
    ],
)
def test_a_busy_host_failure_is_carbons_and_the_next_try_is_a_fresh_build(
    tmp_path, monkeypatch, lock_held, containers, gpu, why
):
    host, rebuild, marks = _rebuilder(tmp_path, monkeypatch)
    host.state = DirectTaskStateV3.REFUSED
    token = _activate(lock_held, containers, gpu)
    try:
        with pytest.raises(ca.RebuildInfra, match=host_quiet.REBUILD_HOST_CONTENDED):
            rebuild(4242)
    finally:
        host_quiet.deactivate(token)
    (failed,) = host.states
    mark = json.loads((marks / f"{failed}.json").read_text())
    assert mark["path"] == "crown_rebuild" and mark["quiet"] is False, why
    assert mark["reason"] == "rebuild_task_refused"
    logged = (marks.parent / host_quiet.LOG_NAME).read_text().splitlines()
    assert len(logged) == 1
    # the next try (the host quiet again): a FRESH generation of the same seed, built and graded
    host.state = DirectTaskStateV3.QUEUED
    token = _activate(True, 0, 0)
    try:
        result = rebuild(4242)
    finally:
        host_quiet.deactivate(token)
    assert result["evidence"]
    assert [g for _label, g in _starts(host)] == [0, 1]
    assert (
        host.states[failed] is DirectTaskStateV3.REFUSED
    )  # the failed task stays for audit
    assert host._seeds[failed] == host._seeds[result["submission_id"]] == 4242


def test_a_busy_host_failure_in_the_rebuilds_grade_is_carbons_too(
    tmp_path, monkeypatch
):
    host, rebuild, marks = _rebuilder(tmp_path, monkeypatch)

    def grade_wall(adapter, task, **kwargs):
        raise retention.RetentionUnavailable("rebuild_grade_WORKER_WALL_LIMIT_REACHED")

    monkeypatch.setattr(retention, "retain_rebuild_evidence", grade_wall)
    token = _activate(True, 0, 1)
    try:
        with pytest.raises(ca.RebuildInfra, match=host_quiet.REBUILD_HOST_CONTENDED):
            rebuild(7)
    finally:
        host_quiet.deactivate(token)
    (built,) = host.states
    assert json.loads((marks / f"{built}.json").read_text())["reason"] == (
        "rebuild_grade_WORKER_WALL_LIMIT_REACHED"
    )


def test_an_admission_failure_on_a_busy_host_is_not_marked(tmp_path, monkeypatch):
    """Only a task that RAN (rebuild_task_* / rebuild_grade_*) can have been slowed by the host."""
    _host, rebuild, marks = _rebuilder(tmp_path, monkeypatch)

    def refused(*a, **k):
        raise retention.RetentionUnavailable("rebuild_origin_unavailable")

    monkeypatch.setattr(retention, "_derived_build", refused)
    token = _activate(False, 0, 0)
    try:
        with pytest.raises(
            retention.RetentionUnavailable, match="rebuild_origin_unavailable"
        ):
            rebuild(7)
    finally:
        host_quiet.deactivate(token)
    assert not marks.exists()


def test_outside_the_grading_loop_a_failure_is_as_before(tmp_path, monkeypatch):
    host, rebuild, marks = _rebuilder(tmp_path, monkeypatch)
    host.state = DirectTaskStateV3.REFUSED
    with pytest.raises(retention.RetentionUnavailable, match="rebuild_task_refused"):
        rebuild(5)
    assert not marks.exists()


# ---------------------------------------------------------------- the averaging decision


class _Builds:
    def __init__(self, contended_first):
        self.contended = dict(
            contended_first
        )  # seed -> how many tries meet a busy host first

    def rebuild(self, seed):
        if self.contended.get(seed, 0) > 0:
            self.contended[seed] -= 1
            raise ca.RebuildInfra(host_quiet.REBUILD_HOST_CONTENDED)
        return _grade(0.70)

    def rebuild_again(self, seed):
        return _grade(0.70)


def _average(tmp_path, builds):
    return ca.run_average(
        key=KEY,
        challenge_id=CHALLENGE,
        submission_id="sub-1",
        rule=_rule(tmp_path),
        rebuild=builds.rebuild,
        rebuild_again=builds.rebuild_again,
        king_mean=0.60,
        baseline_floor=0.26,
        tolerance=0.0,
    )


def _seeds(tmp_path):
    return ca.derive_seeds(
        KEY, CHALLENGE, "sub-1", _rule(tmp_path).n_for(CHALLENGE), 2147483647
    )


def test_a_busy_host_on_every_try_is_unavailable_host_contended_never_unstable(
    tmp_path,
):
    first = _seeds(tmp_path)[0]
    result = _average(tmp_path, _Builds({first: 3}))
    assert (result["outcome"], result["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_HOST_CONTENDED,
    )
    assert ca.public_view(result) == {
        "outcome": bp.UNAVAILABLE,
        "reason": ca.REBUILD_HOST_CONTENDED,
    }


def test_a_busy_host_then_a_quiet_one_completes_the_average(tmp_path):
    first = _seeds(tmp_path)[0]
    result = _average(tmp_path, _Builds({first: 2}))
    assert (result["outcome"], result["reason"]) == (bp.CHALLENGER, ca.MEAN_EXCEEDS)
    assert len(result["private"]["totals"]) == len(_seeds(tmp_path))


def test_a_mix_of_busy_and_other_infrastructure_failures_keeps_todays_reason(tmp_path):
    first = _seeds(tmp_path)[0]
    builds = _Builds({first: 2})
    plain = builds.rebuild

    def rebuild(seed):
        if seed == first and builds.contended[first] == 0:
            raise ca.RebuildInfra("rebuild failed")
        return plain(seed)

    builds.rebuild = rebuild
    result = _average(tmp_path, builds)
    assert (result["outcome"], result["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_UNAVAILABLE,
    )


def test_a_stepwise_remeasure_never_keeps_a_contended_rebuild(tmp_path):
    class Store:
        def __init__(self):
            self.kept = {}

        def crown_rebuild_cached(self, sid, key, seed, again):
            return self.kept.get((seed, again))

        def record_crown_rebuild(self, sid, key, seed, again, body):
            self.kept[(seed, again)] = body

    calls = []

    def first(seed, *rest):
        calls.append(seed)
        if len(calls) == 1:
            raise ca.RebuildInfra(host_quiet.REBUILD_HOST_CONTENDED)
        return _grade(0.70)

    store = Store()
    repeat = SimpleNamespace(
        rebuild_at=first, rebuild_again_at=lambda seed: _grade(0.70)
    )
    retention._one_rebuild_per_call(repeat, store, "sub-1", "key")
    with pytest.raises(ca.RebuildInfra):
        repeat.rebuild_at(11)  # this call's one rebuild met a busy host
    with pytest.raises(retention.RebuildStep):
        repeat.rebuild_at(
            11
        )  # a second new rebuild in the same call is the next call's
    assert store.kept == {}  # nothing kept
    repeat.rebuild_at = first
    retention._one_rebuild_per_call(repeat, store, "sub-1", "key")  # the next tick
    assert repeat.rebuild_at(11)["evidence"]
    assert list(store.kept) == [(11, False)]
