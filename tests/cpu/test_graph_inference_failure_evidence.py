"""A failed graph inference program keeps private, bounded evidence of how far it got (13 Nov, Motor 1.8 testnet wall stops).

The direct graph route's inference program (the counted grade's graded pass, its pair, the single-call loop, the menu re-check)
was in neither of the carrier's evidence sets, so a failed one left only `intent.json` and its input folder, whether a slow model
hit the wall or a worker stalled. It now keeps what the bundle inference already keeps: the baseline observation (the container
running, before the program), the failure evidence (elapsed, deadline reached, exit, OOM, watchdog and cancel flags), the container
end, and a closed failure record per stage before the program. None of it changes WHO the failure is blamed on: a wall stop stays
the candidate's typed failure when the existing guard says so, a start-up fault stays infrastructure, the same exception reaches
the caller, and the policy diagnosis (`diagnose_policy`) now also names the failed control for this provenance, privately.
"""

import contextlib
import json
import time
from types import SimpleNamespace

import pytest
from test_candidate_resource_failure import (
    GRAPH_BUILD,
    GRAPH_INFERENCE,
    _observation,
    _observe,
    _run_failing,
    _state,
)
from test_candidate_resource_failure import harness as _harness
from test_fixed_practice_failure_diagnostics import records

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _harness

SECRET = b"PRIVATE_SECRET-token /private/fixture"


def _operation(harness):
    (operation,) = harness.ledger.root.glob("operation-*")
    return operation


def test_the_graph_inference_provenance_is_in_both_evidence_sets_and_the_build_is_not():
    assert GRAPH_INFERENCE == carrier.GRAPH_INFERENCE_PROVENANCE
    assert GRAPH_INFERENCE in carrier._FIXED_DIAGNOSTIC_PROVENANCES
    assert GRAPH_INFERENCE in carrier._PROGRAM_EVIDENCE_PROVENANCES
    # the reconstruction (the build) is a different program: its evidence is unchanged by this
    assert GRAPH_BUILD not in carrier._FIXED_DIAGNOSTIC_PROVENANCES
    assert GRAPH_BUILD not in carrier._PROGRAM_EVIDENCE_PROVENANCES


def test_a_wall_stop_is_still_the_candidates_and_now_leaves_its_evidence(
    harness, monkeypatch
):
    _observe(monkeypatch, _observation())
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )
    # 46 s leaves the program stage a 1 s allowance, which the instant fake stream has used up (as the existing wall test does)
    with pytest.raises(carrier.MinerProgramFailure) as caught:
        _run_failing(harness, error, provenance=GRAPH_INFERENCE, seconds=46)
    # blame is unchanged: the candidate's typed wall stop, settled FAILED_MINER, cleanup ran
    assert caught.value.code is WorkerCode.DEADLINE
    assert caught.value.result["observation"] == carrier.CANDIDATE_WALL_LIMIT
    assert _state(harness) == "FAILED_MINER"
    assert "CLEANUP" in harness.events
    # the evidence: a baseline before the program, a failure record after it
    operation = _operation(harness)
    baseline_raw = (operation / "private-program-baseline.json").read_bytes()
    failed_raw = (operation / "private-program-failure-evidence.json").read_bytes()
    baseline, failed = json.loads(baseline_raw), json.loads(failed_raw)
    assert baseline["launch_digest"] == failed["launch_digest"]
    assert failed["baseline_digest"] == carrier.digest(baseline_raw)
    # (the instant fake stream reports the timeout before its 1 s allowance has run, so the flag is a recorded bool here)
    assert type(failed["program_deadline_reached"]) is bool
    assert failed["elapsed_milliseconds"] >= 0
    assert len(baseline_raw) <= 4096 and len(failed_raw) <= 4096
    # the controller's diagnostic text is never copied into it
    assert b"stream command timed out" not in baseline_raw + failed_raw


@pytest.mark.parametrize(
    "diagnostic,expected_exit",
    [(b"exit=7\n" + SECRET, 7), (SECRET, None), (b"exit=999\n", None)],
)
def test_a_failed_program_keeps_the_same_exception_and_a_private_closed_record(
    harness, monkeypatch, diagnostic, expected_exit
):
    _observe(monkeypatch, {"status": "UNKNOWN", "state": None, "memory": None})
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic)
    with pytest.raises(WorkerFailure) as caught:
        _run_failing(harness, original, provenance=GRAPH_INFERENCE)
    assert (
        caught.value is original
    )  # the same exception, an infrastructure stop as before
    assert _state(harness) == "RESERVED"
    operation = _operation(harness)
    failed_raw = (operation / "private-program-failure-evidence.json").read_bytes()
    assert json.loads(failed_raw)["observed_exec_exit"] == expected_exit
    # private and bounded: no secret from the controller's diagnostic, and the records stay small
    for path in operation.glob("private-program-*.json"):
        raw = path.read_bytes()
        assert len(raw) <= 4096 and SECRET not in raw
    assert harness.events[-2:] == ["CLEANUP", "ABSENCE_QUERY"]


@pytest.mark.parametrize("stage", ["STAGING", "CREATE", "START", "CONTROLS"])
def test_a_start_up_fault_leaves_its_stage_record_and_stays_infrastructure(
    harness, monkeypatch, stage
):
    """The door-side question: did the container start? Each stage before the program now names where it stopped."""
    _observe(monkeypatch, _observation())
    error = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=SECRET)
    harness.fail_stage, harness.error = stage, error
    with pytest.raises(WorkerFailure) as caught:
        harness.run(provenance=GRAPH_INFERENCE)
    assert caught.value is error
    (record,) = records(harness.ledger.root).values()
    assert record["stage"] == stage
    assert record["exception_class"] == "WorkerFailure"
    assert SECRET not in json.dumps(record).encode()
    assert (
        _state(harness) != "FAILED_MINER"
    )  # a start-up fault is never the candidate's


def test_the_build_program_still_leaves_no_new_evidence(harness, monkeypatch):
    """Only the inference program changed: the reconstruction's failure shape is what it was."""
    _observe(monkeypatch, _observation())
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )
    with pytest.raises(carrier.MinerProgramFailure):
        _run_failing(harness, error, provenance=GRAPH_BUILD, seconds=46)
    operation = _operation(harness)
    assert not list(operation.glob("private-program-*.json"))
    assert not list(operation.glob("failure-*.json"))


def test_the_policy_diagnosis_feed_names_the_failed_control_for_graph_inference_only(
    harness, monkeypatch
):
    """`diagnose_policy=provenance in _FIXED_DIAGNOSTIC_PROVENANCES`: the feed now names a failed control privately for the
    graph inference; the build, outside the set, keeps the bare refusal."""
    seen = []

    def controls(**kwargs):
        seen.append(kwargs.get("diagnose_policy"))
        return "sha256:" + "1" * 64, {}

    monkeypatch.setattr(carrier, "inspect_effective_controls", controls)
    _observe(monkeypatch, _observation())
    # the fixture has no output to finish with; only the feed matters here
    with contextlib.suppress(Exception):
        harness.run(provenance=GRAPH_INFERENCE)
    assert seen[:1] == [True]
    # the build is outside the set: whatever it passes (or never reaches), it is never the diagnosing form
    assert GRAPH_BUILD not in carrier._FIXED_DIAGNOSTIC_PROVENANCES


def test_the_policy_diagnostic_is_only_a_private_marker_and_the_code_stays_policy():
    """What the feed changes: a nested policy refusal gains a private marker; the worker code and the public result do not."""
    from carbon.reconstruction.worker import docker_runtime as runtime

    bare = runtime._policy_refusal(False, "anything")
    named = runtime._policy_refusal(True, "anything")
    assert bare.code is named.code is WorkerCode.POLICY
    assert bare.private_diagnostic == b""
    assert named.private_diagnostic.startswith(runtime._CONTROL_PREDICATE_PREFIX)


# ---- CPU time vs wall time: the host-side stall-vs-slow reading ------------------------------------------

LAUNCH = "sha256:" + "1" * 64
NAME = "carbon-d4-" + LAUNCH[7:31]


class CpuCLI:
    def __init__(self, stdout=b"", error=False):
        self.stdout, self.error, self.calls = stdout, error, []

    def run(self, arguments, *, timeout):
        self.calls.append((arguments, timeout))
        if self.error:
            raise WorkerFailure(WorkerCode.RUNTIME)
        return SimpleNamespace(stdout=self.stdout)


def _cpu(cli, **changes):
    return carrier._fixed_program_cpu_usage_usec(
        cli,
        **{
            "container_name": NAME,
            "launch_digest": LAUNCH,
            "deadline": time.monotonic() + 1,
            **changes,
        },
    )


CPU_STAT = (
    b"usage_usec 123456789\nuser_usec 100000000\nsystem_usec 23456789\nnr_periods 0\n"
)


def test_the_cpu_reading_is_one_bounded_read_of_this_launchs_cgroup():
    cli = CpuCLI(CPU_STAT)
    assert _cpu(cli) == 123456789
    ((arguments, timeout),) = cli.calls
    assert arguments == ["exec", NAME, "/bin/cat", "/sys/fs/cgroup/cpu.stat"]
    assert 0 < timeout <= 0.5


@pytest.mark.parametrize(
    "cli,changes",
    [
        (CpuCLI(b""), {}),  # nothing read
        (CpuCLI(b"user_usec 5\n"), {}),  # no usage_usec line
        (CpuCLI(b"usage_usec -5\n"), {}),  # not a decimal
        (CpuCLI(b"usage_usec 12x\n"), {}),
        (CpuCLI(b"usage_usec " + b"9" * 30 + b"\n"), {}),  # not a u64
        (CpuCLI(b"usage_usec 1\n" + b"x" * 5000), {}),  # over the bound
        (CpuCLI(b"\xff\xfe"), {}),  # not ascii
        (CpuCLI(error=True), {}),  # the read failed
        (CpuCLI(CPU_STAT), {"container_name": "carbon-d4-other"}),  # not this launch
        (CpuCLI(CPU_STAT), {"launch_digest": "sha256:short"}),
        (CpuCLI(CPU_STAT), {"deadline": time.monotonic() - 1}),  # no budget left
        (
            CpuCLI(CPU_STAT),
            {"deadline": float("inf") * 0},
        ),  # a deadline that is not a number
    ],
)
def test_a_cpu_reading_that_cannot_be_trusted_is_none_and_never_raises(cli, changes):
    assert _cpu(cli, **changes) is None


def _readings(monkeypatch, *values):
    """The CPU reading answers with ``values`` in order (the baseline, then the failure)."""
    answers = list(values)
    monkeypatch.setattr(
        carrier,
        "_fixed_program_cpu_usage_usec",
        lambda *a, **k: answers.pop(0) if answers else None,
    )


def test_the_baseline_and_the_failure_evidence_carry_the_cpu_time_of_the_pass(
    harness, monkeypatch
):
    _observe(monkeypatch, _observation())
    _readings(monkeypatch, 1_000_000, 1_900_000)
    error = WorkerFailure(
        WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
    )
    with pytest.raises(carrier.MinerProgramFailure):
        _run_failing(harness, error, provenance=GRAPH_INFERENCE, seconds=46)
    operation = _operation(harness)
    baseline = json.loads((operation / "private-program-baseline.json").read_bytes())
    failed = json.loads(
        (operation / "private-program-failure-evidence.json").read_bytes()
    )
    assert baseline["cpu_usage_usec"] == 1_000_000
    assert failed["cpu_usage_usec"] == 1_900_000
    # 0.9 s of CPU during the program, against the wall time recorded beside it: the discriminator, no verdict
    assert failed["cpu_usec_during_program"] == 900_000
    assert "elapsed_milliseconds" in failed
    # blame is untouched: still the candidate's typed wall stop
    assert _state(harness) == "FAILED_MINER"


@pytest.mark.parametrize(
    "readings",
    [
        (None, 5),  # no baseline
        (5, None),  # no reading at the failure
        (None, None),
        (
            9,
            5,
        ),  # a counter that went backwards (a different cgroup): never a negative figure
    ],
)
def test_a_missing_or_inconsistent_cpu_reading_gives_none_and_the_same_failure(
    harness, monkeypatch, readings
):
    _observe(monkeypatch, {"status": "UNKNOWN", "state": None, "memory": None})
    _readings(monkeypatch, *readings)
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")
    with pytest.raises(WorkerFailure) as caught:
        _run_failing(harness, original, provenance=GRAPH_INFERENCE)
    assert caught.value is original
    failed = json.loads(
        (_operation(harness) / "private-program-failure-evidence.json").read_bytes()
    )
    assert failed["cpu_usec_during_program"] is None
    assert harness.events[-2:] == ["CLEANUP", "ABSENCE_QUERY"]


def test_the_cpu_reading_is_only_for_the_graph_inference_evidence(harness, monkeypatch):
    """The overlay build keeps exactly the evidence it had: no cpu fields, no extra read."""
    from test_fixed_program_failure_evidence import _overlay_arguments

    _observe(monkeypatch, {"status": "UNKNOWN", "state": None, "memory": None})
    monkeypatch.setattr(
        carrier,
        "_fixed_program_cpu_usage_usec",
        lambda *a, **k: pytest.fail("a cpu read outside the graph inference"),
    )
    provenance = carrier.LIBRARY_OVERLAY_BUILD_PROVENANCE
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")
    with pytest.raises(WorkerFailure):
        _run_failing(
            harness,
            original,
            provenance=provenance,
            **_overlay_arguments(harness, provenance),
        )
    operation = _operation(harness)
    for name in (
        "private-program-baseline.json",
        "private-program-failure-evidence.json",
    ):
        assert "cpu_usage_usec" not in json.loads((operation / name).read_bytes())
