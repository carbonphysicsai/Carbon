"""The GPU probe and `pod-attribution-v2` (GRAPHITE-POD-GPU-PROBE-01).

Graphite R2 runs 4 and 5: pods exited 1 with `RuntimeError: Unable to
initialize backend 'cuda': ... no supported devices found`, and under
pod-attribution-v1 a Level 0-3 `program` claim is CANDIDATE_FAILED, so a host
fault was charged to the agent. The fix, approved by the Test Lead under
OWNER-GRAPHITE-TEST-WAVE-02 §3 with the Carbon Validator's seven constraints:

- Carbon's pod phase probes the GPU backend before any candidate code, in the
  program's own interpreter and environment, and a failed probe claims stage
  `environment` (the program never runs);
- pod-attribution-v2 types an admissible, consistent environment failure
  FAILED_INFRA with one relaunch, inside one cap on a proposal's
  infrastructure retries; a second one stops the session FAILED_INFRA;
- Graphite pods are created with `allowedCudaVersions` derived from the
  pinned image's JAX CUDA plugin;
- a log withheld for protected material names the marker's class only.

Scripted pods only: no pod, key, network or spend. The probe and program
tests run Carbon's pod phase on the CPU; none uses a GPU. None of this is a
security audit (AGENTS.md §13).
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from graphite_phase3_fixtures import BASELINE, SCORING, grant

from carbon.agent_campaign.graphite import (
    baseline_retry,
    pod_logs,
    pod_outcome,
    pod_phase,
    pods,
)
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite.pod_outcome import HostTiming
from carbon.agent_campaign.graphite.pods import (
    ScriptedPods,
    Step,
    environment_outputs,
    failed_outputs,
    synthetic_outputs,
)

REPOSITORY = Path(__file__).resolve().parents[2]
V1, V2 = "pod-attribution-v1", "pod-attribution-v2"
#: pod-attribution-v1's registered digest before this change: v1 replays.
V1_DIGEST = "sha256:a349dbf8821d01e553e7c4355d7185f1780a6f06987303912da6f89cbce60c97"
L0, L4 = 0, 4
WORK = pods.contract_work_seconds(SCORING)
#: Host readings of a pod that ran its whole worker allowance.
RAN_FULL = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 15.0 + WORK + 30,
    "ended": 15.0 + WORK + 45,
}
ENDED_EARLY = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 60.0,
    "ended": 75.0,
}
CONFIRMED_TIMEOUT = RAN_FULL
#: What an honest probe failure exports (`environment_outputs`).
HONEST = ("failure.json", "phase.log", "supervisor.json")
RELAUNCH = ("FAILED_INFRA", "pod_environment")


class Ladder:
    def record_failure(self, *args, **kwargs):
        return "failure-1"


def experiment(tmp_path, steps, *, level=L0, max_pods=None, policy=None, **kw):
    budget = ex.phase3_budget(grant(), SCORING)
    if max_pods is not None:
        budget = ex.Phase3Budget(
            run_cap_usd=budget.run_cap_usd,
            hourly_usd=budget.hourly_usd,
            pod_minutes=budget.pod_minutes,
            max_pods=max_pods,
            challenge_id=budget.challenge_id,
        )
    backend = kw.pop("backend", None) or ScriptedPods(steps=steps)
    events = []
    run = ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-environment",
        pods=backend,
        budget=budget,
        baseline=BASELINE,
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=Ladder(),
        emit=lambda event_id, body: events.append((event_id, body)),
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x04" * n,
        construction_level=level,
        scoring=SCORING,
        attribution_policy=policy,
        **kw,
    )
    run.events = events
    return run, backend


def env_step(**outputs):
    return Step(outcome="failed", outputs=environment_outputs(**outputs))


def scored(quality=0.2):
    return Step(outputs=synthetic_outputs(quality))


def timed_out():
    honest = synthetic_outputs(0.2)

    def outputs(job):
        return {
            "built.json": honest(job)["built.json"],
            "failure.json": json.dumps({"stage": "timeout", "error": "x"}).encode(),
        }

    return Step(outcome="failed", outputs=outputs, timing=CONFIRMED_TIMEOUT)


def baseline_of(run):
    return run.run("baseline", "baseline", BASELINE, why=None)


def reasons(record):
    return [a["reason_code"] for a in record.get("attempts", [])]


def rows(run, event):
    return [r for r in run.ledger.rows() if r["event"] == event]


def classify(claim="environment", *, level=L0, files=HONEST, report=None, **kw):
    report = _report() if report is None else report
    kw.setdefault("timing", None)
    return pod_outcome.classify(
        claim=claim,
        admissible=pod_outcome.admissible_stage(report, kw.pop("image", "img")),
        work_seconds=WORK,
        attempt=kw.pop("attempt", 0),
        level=level,
        policy=pod_outcome.load_policy(kw.pop("version", V2)),
        export=pod_outcome.environment_export(files, report),
        **kw,
    )


def _report(*, stage="environment", ok=False, started=False, before=True):
    return {
        "schema": pod_outcome.SUPERVISOR_SCHEMA,
        "stage": stage,
        "probe": {"ok": ok, "before_program": before},
        "program_started": started,
    }


def _verdict(v):
    return (v.status, v.reason_code, v.retry, v.signal, v.relaunch, v.stop)


# -- 1. registration -------------------------------------------------------------------------
def test_v2_is_registered_current_and_v1_is_byte_unchanged():
    registry = json.loads((pod_outcome.POLICY_DIR / "registry.json").read_text())
    assert registry["current"] == V2
    assert registry["versions"][V1] == V1_DIGEST
    v1, v2 = pod_outcome.load_policy(V1), pod_outcome.load_policy(V2)
    assert v1.digest == V1_DIGEST and v1.environment is None
    assert v2.environment["relaunches"] == 1 and v2.infra_retry_cap == 1
    assert pod_outcome.load_policy().version == V2
    assert v2.stages == ("timeout", "program", "compile", "environment")
    assert v1.stages == ("timeout", "program", "compile")


def test_v1_typed_evidence_replays_unchanged():
    """Under v1 an `environment` claim is no claim, exactly as before (it
    named no stage v1 knows), never relaunched; every v1 table row is
    unchanged (`test_graphite_pod_timeout.EXPECTED`)."""
    for level in (L0, L4, None):
        verdict = classify(level=level, version=V1)
        assert _verdict(verdict) == ("FAILED_INFRA", "pod", False, False, False, False)
    for claim, expected in (
        ("program", ("CANDIDATE_FAILED", "program")),
        ("compile", ("FAILED_INFRA", "compile")),
        (None, ("FAILED_INFRA", "pod")),
    ):
        v = classify(claim, version=V1)
        assert (v.status, v.reason_code) == expected


def test_every_outcome_records_the_policy_it_was_typed_under(tmp_path):
    run, _ = experiment(tmp_path, [env_step(), scored()])
    record = baseline_of(run)
    policy = pod_outcome.load_policy()
    assert record["attribution_policy"] == policy.record()
    assert all(a["attribution_policy"] == policy.record() for a in record["attempts"])
    replay, _ = experiment(tmp_path / "v1", [env_step()], policy=V1)
    old = baseline_of(replay)
    assert (old["status"], old["reason_code"]) == ("FAILED_INFRA", "pod")
    assert old["attribution_policy"] == {"version": V1, "digest": V1_DIGEST}


def _v2_document():
    return json.loads((pod_outcome.POLICY_DIR / (V2 + ".json")).read_text())


def _register(tmp_path, document):
    import shutil

    from carbon.agent_campaign.graphite.pod_outcome import _digest

    directory = tmp_path / "policies"
    if not directory.exists():
        shutil.copytree(pod_outcome.POLICY_DIR, directory)
    (directory / (document["version"] + ".json")).write_text(json.dumps(document))
    registry = json.loads((directory / "registry.json").read_text())
    registry["versions"][document["version"]] = _digest(document)
    (directory / "registry.json").write_text(json.dumps(registry))
    return directory


def _with(document, path, value):
    document = json.loads(json.dumps(document))
    *parents, key = path
    target = document
    for name in parents:
        target = target[name]
    if value is KeyError:
        del target[key]
    else:
        target[key] = value
    return document


@pytest.mark.parametrize(
    ("path", "value"),
    [
        # The environment stage is never typed as the candidate's.
        (("admissible", "environment"), ["CANDIDATE_FAILED", "environment"]),
        (("evidence_only", "environment"), ["CANDIDATE_FAILED", "environment"]),
        (("environment", "inconsistent"), ["CANDIDATE_FAILED", "x"]),
        (("environment", "contradicted"), ["CANDIDATE_RESOURCE_EXCEEDED", "x"]),
        (("environment", "repeated"), ["CANDIDATE_FAILED", "x"]),
        (("infra_retries", "cap_reached"), ["CANDIDATE_FAILED", "x"]),
        (("environment", "repeated"), ["SCORED", "x"]),
        # A relaunch never loops, and the cap is one counter for all retries.
        (("environment", "relaunches"), 2),
        (("infra_retries", "max"), 2),
        (("infra_retries", "max"), True),
        (("environment", "relaunches"), -1),
        (("timeout", "retries"), 2),
        # Only the tests this module implements; a repeat stops the session.
        (("environment", "confirm"), "the_pod_says_so"),
        (("environment", "contradict"), "host_phase_max_below_work_seconds"),
        (("environment", "on_repeated"), "relaunch_again"),
        # Closed key sets and a known outcome per stage.
        (("environment", "extra"), 1),
        (("environment", "repeated"), KeyError),
        (("admissible", "environment"), KeyError),
        (("evidence_only", "gpu"), ["FAILED_INFRA", "x"]),
        (("infra_retries",), KeyError),
        (("extra",), True),
        (("schema",), "carbon.graphite.pod-attribution-policy.v3"),
    ],
)
def test_a_v2_policy_cannot_blame_the_environment_or_loop(tmp_path, path, value):
    document = _with(_v2_document(), path, value)
    document["version"] = "pod-attribution-unsafe"
    directory = _register(tmp_path, document)
    with pytest.raises(pod_outcome.PolicyRefused):
        pod_outcome.load_policy("pod-attribution-unsafe", directory=directory)


def test_a_v1_document_cannot_carry_the_environment_stage(tmp_path):
    v1 = json.loads((pod_outcome.POLICY_DIR / (V1 + ".json")).read_text())
    document = _with(v1, ("admissible", "environment"), ["FAILED_INFRA", "x"])
    document["version"] = "pod-attribution-mixed"
    directory = _register(tmp_path, document)
    with pytest.raises(pod_outcome.PolicyRefused):
        pod_outcome.load_policy("pod-attribution-mixed", directory=directory)


# -- the v2 environment table ------------------------------------------------------------------
ENVIRONMENT_TABLE = [
    # (name, kwargs, expected (status, reason, retry, signal, relaunch, stop))
    ("honest_level0", {}, (*RELAUNCH, True, False, True, False)),
    ("honest_level3", {"level": 3}, (*RELAUNCH, True, False, True, False)),
    (
        "level4_evidence_only",
        {"level": L4},
        ("FAILED_INFRA", "candidate_failure_unattributed", False, False, False, False),
    ),
    (
        "unknown_level_evidence_only",
        {"level": None},
        ("FAILED_INFRA", "candidate_failure_unattributed", False, False, False, False),
    ),
    (
        "program_log_present",
        {"files": (*HONEST, "program.log")},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "predictions_present",
        {"files": (*HONEST, "predictions.json")},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "built_json_present",
        {"files": (*HONEST, "built.json")},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "probe_passed",
        {"report": _report(ok=True)},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "report_says_program_started",
        {"report": _report(started=True)},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "probe_not_before_program",
        {"report": _report(before=False)},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "no_report",
        {"report": {}, "files": ("failure.json", "phase.log")},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "report_names_another_stage",
        {"report": _report(stage="program")},
        ("FAILED_INFRA", "environment_claim_unattributed", False, True, False, False),
    ),
    (
        "host_saw_the_full_allowance",
        {"timing": HostTiming(**RAN_FULL)},
        (
            "FAILED_INFRA",
            "environment_claim_contradicts_host_timing",
            False,
            True,
            False,
            False,
        ),
    ),
    (
        "host_saw_the_full_allowance_level4",
        {"timing": HostTiming(**RAN_FULL), "level": L4},
        (
            "FAILED_INFRA",
            "environment_claim_contradicts_host_timing",
            False,
            True,
            False,
            False,
        ),
    ),
    ("host_saw_it_end_early", {"timing": HostTiming(**ENDED_EARLY)}, None),
    (
        "second_environment_failure_stops",
        {"attempt": 1, "earlier": ("pod_environment",)},
        ("FAILED_INFRA", "pod_environment_repeated", False, False, False, True),
    ),
    (
        "environment_after_a_timeout_retry_has_no_retry_left",
        {"attempt": 1, "earlier": ("worker_timeout_retried",)},
        ("FAILED_INFRA", "infra_retry_cap_reached", False, False, False, False),
    ),
]


@pytest.mark.parametrize(
    ("name", "kwargs", "expected"),
    ENVIRONMENT_TABLE,
    ids=[r[0] for r in ENVIRONMENT_TABLE],
)
def test_the_environment_order_of_authority(name, kwargs, expected):
    verdict = classify(**kwargs)
    if expected is None:
        expected = (*RELAUNCH, True, False, True, False)
    assert _verdict(verdict) == expected


def test_a_first_timeout_after_a_relaunch_is_never_blamed():
    """The cap is shared, and a first timeout is never the candidate's: with
    the retry spent on a relaunch it is FAILED_INFRA with no retry."""
    verdict = classify(
        "timeout",
        attempt=1,
        earlier=("pod_environment",),
        timing=HostTiming(**CONFIRMED_TIMEOUT),
        files=("built.json", "failure.json"),
        report={},
    )
    assert _verdict(verdict) == (
        "FAILED_INFRA",
        "infra_retry_cap_reached",
        False,
        False,
        False,
        False,
    )
    # A host-confirmed repeated timeout stays the candidate's, whatever else.
    repeated = classify(
        "timeout",
        attempt=1,
        earlier=("worker_timeout_retried",),
        timing=HostTiming(**CONFIRMED_TIMEOUT),
        report={},
    )
    assert repeated.status == "CANDIDATE_RESOURCE_EXCEEDED"


def test_a_separated_images_probe_report_is_admissible_at_level4(monkeypatch):
    """VALIDATOR-04's uid split: once an image has a separation record, the
    probe's stage in the supervisor report is admissible at Levels 4-5 with no
    policy change."""
    assert classify(level=L4, image="separated").status == "FAILED_INFRA"
    assert not classify(level=L4, image="separated").relaunch
    monkeypatch.setitem(pod_outcome.SEPARATED_IMAGES, "separated", "test record")
    verdict = classify(level=L4, image="separated")
    assert _verdict(verdict) == (*RELAUNCH, True, False, True, False)
    # The consistency check still applies to an admissible report.
    late = classify(level=L4, image="separated", files=(*HONEST, "program.log"))
    assert late.reason_code == "environment_claim_unattributed" and not late.retry


# -- the experiment: relaunch, ledger, stop -----------------------------------------------
def test_an_environment_failure_is_relaunched_once_and_scores(tmp_path):
    run, backend = experiment(tmp_path, [env_step(), scored()])
    record = baseline_of(run)
    assert (record["status"], record["scored"]) == ("SCORED", True)
    assert reasons(record) == ["pod_environment"]
    [first] = record["attempts"]
    assert first["claimed_stage"] == "environment"
    assert first["environment_export"] == {
        "program_started": False,
        "probe_failed_before_program": True,
    }
    # Both attempts reserved, ledgered and typed; distinct intents.
    reserved = [r["intent_id"] for r in rows(run, "pod_reserved")]
    assert reserved == [first["intent_id"], ex.retry_intent(first["intent_id"])]
    assert len(rows(run, "pod_environment_relaunch")) == 1
    assert [r["reason_code"] for r in rows(run, "pod_attempt_typed")] == [
        "pod_environment"
    ]
    assert len(backend.launched) == 2 and not backend.alive
    assert run.pods_left() == run.budget.max_pods - 2
    assert run.stopped() is None and run.findings() == []


def test_a_second_environment_failure_stops_the_session_failed_infra(tmp_path):
    run, backend = experiment(tmp_path, [env_step(), env_step(), scored()])
    refused = run.run("p-after", "proposal", BASELINE, why={"h": "x"})
    record = run.record("baseline")
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "pod_environment_repeated",
    )
    assert reasons(record) == ["pod_environment", "pod_environment_repeated"]
    stop = run.stopped()
    assert stop is not None
    assert stop["status"] == "FAILED_INFRA" and stop["candidate_charged"] is False
    assert stop["policy"] == pod_outcome.load_policy().record()
    assert refused["status"] == ex.SESSION_STOPPED and refused["scored"] is False
    assert len(backend.launched) == 2 and not backend.alive  # never a loop
    assert run.baseline_retry() is None  # the stopped baseline is not retried
    assert run.summary()["session_stop"] == stop
    assert [b["kind"] for _e, b in run.events].count("session_stopped") == 1
    tool = run.propose_tool(
        {
            "strategy_json": json.dumps(BASELINE),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        "after-the-stop",
    )
    assert tool["status"] == "REJECTED_BEFORE_DISPATCH" and not tool["dispatched"]
    assert len(backend.launched) == 2


def test_a_level4_environment_claim_is_evidence_only_and_never_relaunched(tmp_path):
    run, backend = experiment(tmp_path, [env_step(), scored()], level=L4)
    record = baseline_of(run)
    assert (record["status"], record.get("reason_code")) == (
        "FAILED_INFRA",
        "candidate_failure_unattributed",
    )
    assert len(backend.launched) == 1 and run.stopped() is None


def test_an_inconsistent_environment_claim_is_a_signal_never_a_free_retry(tmp_path):
    forged = env_step(
        extra={"program.log": b"SYNTHETIC program ran\n", "built.json": b"{}"}
    )
    run, backend = experiment(tmp_path, [forged, scored()])
    record = baseline_of(run)
    # built.json is there, so the rebuild check runs first and refuses it.
    assert record["status"] == "REBUILD_MISMATCH" and len(backend.launched) == 1
    run2, backend2 = experiment(
        tmp_path / "b",
        [env_step(extra={"program.log": b"SYNTHETIC program ran\n"}), scored()],
    )
    record2 = baseline_of(run2)
    assert (record2["status"], record2.get("reason_code")) == (
        "FAILED_INFRA",
        "environment_claim_unattributed",
    )
    assert len(backend2.launched) == 1
    [finding] = run2.findings()
    assert finding["condition"] == "OTHER_SIGNAL"
    assert finding["evidence"]["kind"] == "POD_ENVIRONMENT_CLAIM_DISAGREEMENT"
    assert finding["evidence"]["detail"]["environment_export"]["program_started"]


def test_an_environment_claim_the_host_contradicts_is_a_signal(tmp_path):
    step = Step(outcome="failed", outputs=environment_outputs(), timing=RAN_FULL)
    run, backend = experiment(tmp_path, [step, scored()])
    record = baseline_of(run)
    assert record.get("reason_code") == "environment_claim_contradicts_host_timing"
    assert len(backend.launched) == 1
    assert run.findings()[0]["condition"] == "OTHER_SIGNAL"


def test_the_retry_counter_never_resets_between_timeouts_and_relaunches(tmp_path):
    """Timeout then environment: the one retry went to the timeout, so the
    environment failure has none (never blamed). Environment then timeout:
    the relaunch used it, so the first timeout is infrastructure."""
    run, backend = experiment(tmp_path, [timed_out(), env_step(), scored()])
    record = baseline_of(run)
    assert reasons(record) == ["worker_timeout_retried", "infra_retry_cap_reached"]
    assert record["status"] == "FAILED_INFRA" and len(backend.launched) == 2
    run2, backend2 = experiment(tmp_path / "b", [env_step(), timed_out(), scored()])
    record2 = baseline_of(run2)
    assert reasons(record2) == ["pod_environment", "infra_retry_cap_reached"]
    assert record2["status"] == "FAILED_INFRA" and len(backend2.launched) == 2


def test_the_attempt_loop_is_bounded_whatever_the_policy_asks(tmp_path, monkeypatch):
    always = pod_outcome.Verdict(*RELAUNCH, retry=True, relaunch=True)
    monkeypatch.setattr(pod_outcome, "classify", lambda **kw: always)
    run, backend = experiment(tmp_path, [env_step()] * 6)
    record = baseline_of(run)
    assert len(backend.launched) == ex.pod_attempts(run.attribution) == 2
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "infra_retry_cap_reached",
    )


def test_a_relaunch_is_held_to_the_runs_limits(tmp_path):
    run, backend = experiment(tmp_path, [env_step(), scored()], max_pods=1)
    record = baseline_of(run)
    assert record["reason_code"] == (
        "pod_environment_relaunch_refused:session_pod_limit_reached"
    )
    assert len(backend.launched) == 1
    run2, backend2 = experiment(
        tmp_path / "b", [env_step(), scored()], seconds_left=lambda: 60.0
    )
    record2 = baseline_of(run2)
    assert record2["reason_code"] == (
        "pod_environment_relaunch_refused:relaunch_cannot_fit_remaining_time"
    )
    assert len(backend2.launched) == 1
    run3, _ = experiment(tmp_path / "c", [env_step(), Step(launch="refused")])
    record3 = baseline_of(run3)
    assert (record3["status"], record3["reason_code"]) == (
        "FAILED_INFRA",
        "launch_refused",
    )
    assert reasons(record3) == ["pod_environment"]


def test_a_baseline_environment_failure_does_not_also_use_the_baseline_retry(
    tmp_path,
):
    """The relaunch is the baseline's one extra pod: a relaunch that then
    crashes is not retried again (`baseline-retry-v1` would otherwise retry
    the program crash)."""
    crash = Step(outcome="failed", outputs=failed_outputs("program"))
    run, backend = experiment(tmp_path, [env_step(), crash, scored(0.4)])
    record = run.run("p-next", "proposal", BASELINE, why={"h": "x"})
    first = run.record("baseline")
    assert reasons(first) == ["pod_environment", "program"]
    assert (first["status"], first["reason_code"]) == ("CANDIDATE_FAILED", "program")
    decision = run.baseline_retry()
    assert decision["retry"] is False
    assert decision["reason_code"] == baseline_retry.ENVIRONMENT_RELAUNCH_USED
    assert len(backend.launched) == 3  # baseline, its relaunch, the proposal
    assert record["status"] == "SCORED"
    # And the baseline retry's own environment failure is not relaunched.
    run2, backend2 = experiment(
        tmp_path / "b", [crash, env_step(), scored(0.4)], policy=None
    )
    run2.run("p-next", "proposal", BASELINE, why={"h": "x"})
    retried = run2.record(baseline_retry.RETRY_ID)
    assert retried["reason_code"] == (
        "pod_environment_relaunch_refused:baseline_retry_used"
    )
    assert len(backend2.launched) == 3


def test_baseline_retry_decide_refuses_after_a_relaunch():
    policy = baseline_retry.load_policy()
    first = {
        "proposal_id": "baseline",
        "kind": "baseline",
        "status": "CANDIDATE_FAILED",
        "reason_code": "program",
    }
    common = {
        "policy": policy,
        "first": first,
        "budget_refusal": None,
        "time_fits": True,
    }
    assert baseline_retry.decide(retries_used=0, **common) == (True, "retried")
    assert baseline_retry.decide(
        retries_used=0, environment_relaunched=True, **common
    ) == (False, baseline_retry.ENVIRONMENT_RELAUNCH_USED)


# -- the session stop through the provider -------------------------------------------------
def test_the_provider_ends_a_stopped_session_failed_infra(tmp_path):
    import graphite_phase3_fixtures as p3f

    account = ScriptedPods(steps=[env_step(), env_step(), scored()])
    script = [p3f.propose(p3f.variant(width=48)), p3f.text("more")]
    result, graphite, _control = p3f.session(tmp_path, script, account)
    assert result["provider_state"] == "failed"
    state = json.loads((graphite._dir(p3f.run_id()) / "state.json").read_bytes())
    assert state["failure"] == {
        "code": "failed_infra",
        "reason_code": "pod_environment_repeated",
        "candidate_charged": False,
    }
    assert graphite.model.remaining == 1  # the next call was never sent
    assert len(account.launched) == 2 and not account.alive
    assert result["summary"]["session_stop"]["status"] == "FAILED_INFRA"


# -- 6. the probe runs first, in the program's own environment -----------------------------
PASS_PROBE = "import json, sys\njson.dump({'ok': True}, open(sys.argv[1], 'w'))\n"
FAIL_PROBE = (
    "import json, sys\n"
    "json.dump({'ok': False, 'error_type': 'RuntimeError'}, open(sys.argv[1], 'w'))\n"
    "raise RuntimeError('SYNTHETIC no supported devices found for platform CUDA')\n"
)
KNN = {**BASELINE, "backbone": "knn", "parameters": {"neighbours": 6}}


def _config():
    contract = ex.recorded_contract(SCORING)["contract_digest"]
    built, _files, _program = pod_phase.built_record(KNN, contract, 7, REPOSITORY)
    return {
        "strategy": KNN,
        "contract_digest": contract,
        "seed": 7,
        "expected": {"files": built["staged"], "program": built["program"]},
        "seconds": 600,
    }


def _hostile(monkeypatch, program):
    """The pinned build with `program` in place of the practice program, as a
    construction that could reach the pod phase's directory would run."""
    real = pod_phase.built_record

    def built_record(strategy, contract_digest, seed, root=".", scoring=None):
        record, files, _program = real(strategy, contract_digest, seed, root, scoring)
        return record, files, program

    monkeypatch.setattr(pod_phase, "built_record", built_record)


def _files(out):
    return {p.name: p.read_bytes() for p in Path(out).iterdir() if p.is_file()}


def test_the_probe_runs_before_any_candidate_code(tmp_path, monkeypatch):
    config = _config()
    compiled = []
    real = pod_phase.built_record
    monkeypatch.setattr(
        pod_phase,
        "built_record",
        lambda *a, **k: compiled.append(a) or real(*a, **k),
    )
    sentinel = tmp_path / "the-program-ran"
    _hostile(monkeypatch, f"open({str(sentinel)!r}, 'w').write('ran')\n")
    out = tmp_path / "out"
    assert pod_phase.run(config, out, root=REPOSITORY, probe=FAIL_PROBE) == (
        pod_phase.EXIT_ENVIRONMENT
    )
    assert not sentinel.exists() and compiled == []
    files = _files(out)
    assert set(files) == {"failure.json", "supervisor.json"}
    assert json.loads(files["failure.json"]) == {
        "stage": "environment",
        "error": "RuntimeError",
    }
    report = json.loads(files["supervisor.json"])
    assert report["schema"] == pod_outcome.SUPERVISOR_SCHEMA
    assert report["stage"] == "environment" and report["program_started"] is False
    assert report["probe"]["ok"] is False and report["probe"]["before_program"]
    # The host accepts exactly this export as an environment failure.
    export = pod_outcome.environment_export(files, report)
    assert pod_outcome.environment_consistent(export)


def test_the_probe_and_the_program_share_one_interpreter_and_environment(
    tmp_path, monkeypatch
):
    config = _config()
    _hostile(monkeypatch, "import os\n")
    calls = []
    real = pod_phase.subprocess.run

    def spy(argv, **kwargs):
        calls.append((list(argv[:3]), dict(kwargs)))
        return real(argv, **kwargs)

    monkeypatch.setattr(pod_phase.subprocess, "run", spy)
    out = tmp_path / "out"
    assert pod_phase.run(config, out, root=REPOSITORY, probe=PASS_PROBE) == 0
    (probe_argv, probe_kw), (program_argv, program_kw) = calls
    assert probe_argv == program_argv == [sys.executable, "-I", "-c"]
    # Neither passes an environment: both inherit this process's own.
    assert "env" not in probe_kw and "env" not in program_kw
    assert probe_kw["cwd"].name == program_kw["cwd"].name == "work"
    report = json.loads((out / "supervisor.json").read_text())
    assert report["program_started"] is True and report["stage"] is None
    assert report["probe"]["ok"] is True


def test_the_real_probe_initialises_the_backends_jax_platforms_names(monkeypatch):
    """On the CPU (JAX_PLATFORMS=cpu) the probe passes; asked for CUDA with no
    device visible it fails as the R2 pods did. No GPU is used."""
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    record = pod_phase.probe_environment()
    assert record["ok"] is True and record["requires_gpu"] is False
    assert record["backend"] == "cpu" and record["before_program"] is True
    monkeypatch.setenv("JAX_PLATFORMS", "cuda,cpu")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    record = pod_phase.probe_environment()
    assert record["ok"] is False and record["requires_gpu"] is True
    assert record["exit"] != 0 and record["error_type"]


def test_a_candidate_cannot_write_the_environment_claim(tmp_path, monkeypatch):
    """A program that reaches the phase's directory forges an environment
    claim and a failed-probe report, then crashes: the phase rewrites both
    from its own memory, and v2 types the export as the candidate's."""
    out = tmp_path / "out"
    forged_report = json.dumps(_report())
    program = (
        "import json, sys\n"
        f"out = {str(out)!r}\n"
        "open(out + '/failure.json', 'w').write("
        "json.dumps({'stage': 'environment', 'error': 'RuntimeError'}))\n"
        f"open(out + '/supervisor.json', 'w').write({forged_report!r})\n"
        "sys.exit(1)\n"
    )
    _hostile(monkeypatch, program)
    assert pod_phase.run(_config(), out, root=REPOSITORY, probe=PASS_PROBE) == 5
    files = _files(out)
    assert json.loads(files["failure.json"])["stage"] == "program"
    report = json.loads(files["supervisor.json"])
    assert (report["stage"], report["program_started"]) == ("program", True)
    assert report["probe"]["ok"] is True
    verdict = classify(
        json.loads(files["failure.json"])["stage"], files=files, report=report
    )
    assert (verdict.status, verdict.reason_code) == ("CANDIDATE_FAILED", "program")
    # A program that forges the claim and exits 0 leaves no claim at all.
    clean = tmp_path / "clean"
    _hostile(monkeypatch, program.replace(str(out), str(clean)).replace("(1)", "(0)"))
    assert pod_phase.run(_config(), clean, root=REPOSITORY, probe=PASS_PROBE) == 0
    assert not (clean / "failure.json").exists()
    assert json.loads((clean / "supervisor.json").read_text())["stage"] is None


def test_a_forged_environment_export_is_still_typed_by_v2(tmp_path):
    """Had a forgery survived (Levels 4-5 share the uid), v2 still types it
    from the export: evidence only at Level 4; an OTHER_SIGNAL at Level 0
    when the program left its traces."""
    names = ("built.json", "failure.json", "program.log", "supervisor.json")
    level4 = classify(level=L4, files=names)
    assert not level4.retry and level4.status == "FAILED_INFRA"
    level0 = classify(level=L0, files=names)
    assert level0.signal and not level0.retry


# -- 7. allowedCudaVersions ----------------------------------------------------------------
def test_allowed_cuda_versions_derive_from_the_pinned_plugin():
    assert pods.allowed_cuda_versions(REPOSITORY) == ("13.0",)
    lock = (REPOSITORY / pods.ACCELERATOR_LOCK).read_text()
    assert "jax-cuda13-plugin==0.10.2" in lock and "jax-cuda13-pjrt==0.10.2" in lock
    assert "nvidia-cuda-runtime==13.0.48" in lock
    # The host lock pins the same jax and jaxlib release (read only).
    uv = (REPOSITORY / "uv.lock").read_text()
    for name in ("jax", "jaxlib"):
        assert f'name = "{name}"\nversion = "0.10.2"' in uv
    from scripts.dev.exam_design.runpod import pod_control

    # A different image is a different derivation: this test pins the pair.
    assert pod_control.IMAGE.endswith(
        "2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
    )


def test_a_lock_without_a_plugin_runtime_refuses_the_launch(tmp_path):
    (tmp_path / ".devcontainer/accelerators").mkdir(parents=True)
    path = tmp_path / pods.ACCELERATOR_LOCK
    path.write_text("jax==0.10.2\n")
    with pytest.raises(pods.PodFailure) as refused:
        pods.allowed_cuda_versions(tmp_path)
    assert refused.value.executed is False
    path.write_text("jax-cuda13-plugin==0.10.2\nnvidia-cuda-runtime==13.1.0\n")
    with pytest.raises(pods.PodFailure):
        pods.allowed_cuda_versions(tmp_path)


def test_the_create_request_carries_the_recorded_cuda_versions(tmp_path):
    from scripts.dev.exam_design.runpod.operator_compute import PodSpec
    from scripts.dev.exam_design.runpod.operator_compute.runpod import RunPodAdapter

    image = pods.prices()["image"]
    spec = PodSpec(
        image=image,
        gpu_type_id="NVIDIA A40",
        gpu_count=1,
        allowed_cuda_versions=("13.0",),
    )
    body = RunPodAdapter.create_body(object.__new__(RunPodAdapter), spec, "a" * 24)
    assert body["allowedCudaVersions"] == ["13.0"]
    assert spec.canonical()["allowed_cuda_versions"] == ["13.0"]
    # Absent when empty: every earlier request keeps its digest.
    plain = PodSpec(image=image, gpu_type_id="NVIDIA A40", gpu_count=1)
    assert "allowed_cuda_versions" not in plain.canonical()
    assert "allowedCudaVersions" not in RunPodAdapter.create_body(
        object.__new__(RunPodAdapter), plain, "a" * 24
    )
    with pytest.raises(ValueError):
        PodSpec(image=image, gpu_type_id=None, allowed_cuda_versions=("13",))


def test_the_pod_record_fixes_the_cuda_versions_for_replay(tmp_path):
    backend = object.__new__(pods.RunPodPods)
    backend.cuda_versions = ("13.0",)
    backend.clock = lambda: 1000.0
    import threading

    backend._record_lock = threading.Lock()
    job = pods.PodJob("intent-1", {}, "sha256:" + "0" * 64, 1, {}, 30, 600)
    private = pods.private_dir(tmp_path / "p")
    record = backend._record(job, private)
    assert record["allowed_cuda_versions"] == ["13.0"]
    backend.cuda_versions = ("12.8",)  # a later derivation never moves a replay
    assert backend._record(job, private)["allowed_cuda_versions"] == ["13.0"]


def test_the_real_path_sends_the_derived_cuda_versions(tmp_path):
    report = pods.real_path_check(tmp_path / "real", scoring=SCORING)
    assert report["status"] == "OK", report
    assert report["allowed_cuda_versions"] == [["13.0"], ["13.0"]]


# -- 4. withheld-log diagnostics -------------------------------------------------------------
def test_a_withheld_log_names_the_marker_class_never_the_marker(tmp_path):
    from carbon.agent_campaign.graphite.protected_material import (
        CHECKOUT_DENY_CLASS,
        MARKER_CLASSES,
        PROTECTED_MARKERS,
        protected,
    )

    body = b"step 1\nloading the official_seed and a hidden-case\n"
    listed = {"program.log": __import__("hashlib").sha256(body).hexdigest()}
    [summary] = pod_logs.keep(
        tmp_path / "logs", [("i-1", {"program.log": body}, listed)]
    )
    index = (tmp_path / "logs" / "attempt-0" / "index.json").read_bytes()
    [entry] = json.loads(index)["logs"]
    assert entry["status"] == pod_logs.WITHHELD_PROTECTED
    assert entry["marker_classes"] == ["exam_material", "seed_material"]
    assert not protected(json.loads(index))
    lowered = index.decode().lower()
    assert not any(marker in lowered for marker in PROTECTED_MARKERS)
    assert b"official" not in index and b"hidden" not in index
    assert not (tmp_path / "logs" / "attempt-0" / "program.log").exists()
    # Every marker has exactly one class; no class name is protected itself.
    classed = [m for markers in MARKER_CLASSES.values() for m in markers]
    assert sorted(classed) == sorted(PROTECTED_MARKERS)
    for name in (*MARKER_CLASSES, CHECKOUT_DENY_CLASS):
        assert not protected(name)
        assert not any(m in name for m in PROTECTED_MARKERS)
    assert summary["logs"][0]["status"] == pod_logs.WITHHELD_PROTECTED


# -- 5. the Attacker probe ---------------------------------------------------------------------
def test_the_attacker_probe_holds_and_its_specimen_fires():
    from carbon.agent_campaign.attack import pod_attribution as pa
    from carbon.agent_campaign.attack.adapters import battery as b

    adapter = b.ADAPTER
    spec = adapter.family_spec("resource_accounting")
    ours = dict(pa.attacks())
    assert ours and set(ours) <= dict(spec.attacks()).keys()
    for name, value in ours.items():
        reading = adapter.assess(spec, (name, value))
        assert (reading.reading, reading.oracle.verdict) == (b.HELD, b.HELD), name
        assert spec.breached(spec.specimen(value)), name
        assert not spec.breached(spec.boundary(value)), name
    # The Carbon Validator's case: Level 4, crash, failure.json rewritten.
    case = ours["level4_crash_rewritten_as_environment"]
    assert pa.specimen(case)["relaunch"] and not pa.boundary(case)["relaunch"]
    # The honest failure is relaunched by the real boundary (a valid control).
    assert pa.control_passes(pa.control())
    assert b._resource_control(pa.control())
