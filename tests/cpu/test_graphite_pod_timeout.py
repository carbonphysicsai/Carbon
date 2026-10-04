"""The pod worker-timeout rule (OWNER-GRAPHITE-TEST-WAVE-02 §3, VALIDATOR-01 slice 2).

Attribution depends on the session's recorded construction level (the Test
Lead's VAL-D13 refinement). At Levels 0-3 only Carbon's own trainer writes the
pod's claims, so a program failure stays the candidate's. At Levels 4-5 on an
image without a separation record, the claim is evidence only. Timeouts follow
the retry rule at every level.

A worker timeout is never a scientific failure. A first one is FAILED_INFRA,
retried once on a fresh pod under the same declared budget. Only a second
timeout that host timing confirms is the candidate exceeding its budget, and
that is never scored. Host-observed timing and pod lifecycle decide. A
supervisor report from a separated image is admissible evidence. Anything
the candidate's process could write is evidence only, never classification.

The pods are scripted: no pod, key, network or spend. Carbon's admission,
rebuild check and frozen-rule scoring run for real on synthetic predictions.
None of this is a security audit (AGENTS.md §13).
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from graphite_phase3_fixtures import BASELINE, grant

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pod_outcome, pods
from carbon.agent_campaign.graphite.pod_outcome import HostTiming
from carbon.agent_campaign.graphite.pods import ScriptedPods, Step, synthetic_outputs

REPOSITORY = Path(__file__).resolve().parents[2]
#: Level 0: Carbon's own trainer on a declarative recipe. Level 4: participant
#: code in the pod (the strict case these tests default to).
L0, L4 = 0, pod_outcome.PARTICIPANT_CODE_LEVEL
WORK = pods.contract_work_seconds()  # battery's declared 600 s
#: Host readings confirming a timeout: the phase was seen running for more
#: than the declared worker seconds.
CONFIRMED = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 15.0 + WORK + 30,
    "ended": 15.0 + WORK + 45,
}
#: Host readings that make a claimed timeout impossible: the phase ended
#: well before the declared worker seconds could have passed.
IMPOSSIBLE = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 90.0,
    "ended": 105.0,
}
#: Host readings that neither confirm nor contradict a timeout.
UNCERTAIN = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": WORK - 100.0,
    "ended": WORK + 60.0,
}


class Ladder:
    def record_failure(self, *args, **kwargs):
        return "failure-1"


def experiment(tmp_path, steps, *, max_pods=None, backend=None, level=L4):
    budget = ex.phase3_budget(grant())
    if max_pods is not None:
        budget = ex.Phase3Budget(
            run_cap_usd=budget.run_cap_usd,
            hourly_usd=budget.hourly_usd,
            pod_minutes=budget.pod_minutes,
            max_pods=max_pods,
        )
    backend = ScriptedPods(steps=steps) if backend is None else backend
    events = []
    run = ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-timeout",
        pods=backend,
        budget=budget,
        baseline=BASELINE,
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=Ladder(),
        emit=lambda event_id, body: events.append((event_id, body)),
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x02" * n,
        construction_level=level,
    )
    return run, backend


def ended(stage=None, *, supervisor=None):
    """A pod that ended without finishing: the build Carbon pinned, and the
    pod's own (shared-filesystem) claim of which stage failed."""
    honest = synthetic_outputs(0.2)

    def outputs(job):
        files = {"built.json": honest(job)["built.json"]}
        if stage is not None:
            files["failure.json"] = json.dumps(
                {"stage": stage, "error": "claimed"}
            ).encode()
        if supervisor is not None:
            files["supervisor.json"] = json.dumps(supervisor).encode()
        return files

    return outputs


def timed_out(timing=CONFIRMED, supervisor=None, **step):
    return Step(
        outcome="failed",
        outputs=ended("timeout", supervisor=supervisor),
        timing=timing,
        **step,
    )


def scored():
    return Step(outcome="done", outputs=synthetic_outputs(0.2), timing=CONFIRMED)


def run_baseline(run):
    return run.run("baseline", "baseline", BASELINE, why=None)


def intents(run):
    return [r["intent_id"] for r in run.ledger.rows() if r["event"] == "pod_reserved"]


@pytest.mark.parametrize("level", [L0, L4, None])
def test_a_timeout_then_success_is_failed_infra_then_scored_once(tmp_path, level):
    run, backend = experiment(tmp_path, [timed_out(), scored()], level=level)
    record = run_baseline(run)
    assert (record["status"], record["scored"]) == ("SCORED", True)
    [first] = record["attempts"]
    assert (first["status"], first["reason_code"]) == (
        "FAILED_INFRA",
        "worker_timeout_retried",
    )
    assert first["attempt"] == 0 and first["claimed_stage"] == "timeout"
    # Two pods, two distinct intents, both reserved against the run.
    assert len(backend.launched) == 2
    assert intents(run) == [first["intent_id"], ex.retry_intent(first["intent_id"])]
    assert len(set(intents(run))) == 2
    assert run.pods_left() == run.budget.max_pods - 2
    typed = [r for r in run.ledger.rows() if r["event"] == "pod_attempt_typed"]
    assert [t["reason_code"] for t in typed] == ["worker_timeout_retried"]
    # Scored exactly once.
    assert len(run.records()) == 1 and run.rows("baseline") is not None
    assert run.findings() == []


@pytest.mark.parametrize("level", [L0, L4])
def test_two_confirmed_timeouts_are_a_candidate_resource_outcome_never_scored(
    tmp_path, level
):
    run, backend = experiment(tmp_path, [timed_out(), timed_out()], level=level)
    record = run_baseline(run)
    assert record["status"] == pod_outcome.CANDIDATE_RESOURCE_EXCEEDED
    assert record["reason_code"] == "worker_timeout_repeated"
    assert record["scored"] is False and "frozen_rule" not in record
    assert run.rows("baseline") is None
    assert [a["status"] for a in record["attempts"]] == [
        "FAILED_INFRA",
        "CANDIDATE_RESOURCE_EXCEEDED",
    ]
    assert len(backend.launched) == 2


@pytest.mark.parametrize("timing", [None, UNCERTAIN])
def test_a_second_timeout_host_timing_cannot_confirm_is_never_blamed(tmp_path, timing):
    run, _ = experiment(tmp_path, [timed_out(), timed_out(timing=timing)])
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "worker_timeout_unconfirmed",
    )
    assert record["scored"] is False


@pytest.mark.parametrize("level", [L0, L4])
def test_a_forged_timeout_claim_cannot_type_its_own_outcome(tmp_path, level):
    """The candidate writes failure.json saying "timeout" after a short run.
    Host timing makes that impossible: FAILED_INFRA, no retry, and an
    OTHER_SIGNAL finding bound to the claim's digest and the host readings."""
    run, backend = experiment(
        tmp_path, [timed_out(timing=IMPOSSIBLE), scored()], level=level
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "timeout_claim_contradicts_host_timing",
    )
    assert len(backend.launched) == 1  # no retry on a contradicted claim
    [finding] = run.findings()
    assert finding["condition"] == "OTHER_SIGNAL"
    detail = finding["evidence"]["detail"]
    assert finding["evidence"]["kind"] == "POD_TIMING_DISAGREEMENT"
    assert detail["claimed_stage"] == "timeout"
    assert detail["failure_digest"].startswith("sha256:")
    assert detail["host_timing"]["phase_max_s"] < detail["work_seconds"]
    assert record["attempts"][0]["finding"] == finding["id"]


@pytest.mark.parametrize(
    ("level", "claim"),
    [(L4, "program"), (L4, "compile"), (5, "program"), (None, "program")],
)
def test_a_shared_uid_claim_where_participant_code_runs_is_evidence_only(
    tmp_path, level, claim
):
    """Levels 4-5 on an image without a separation record, or an unknown
    level: the pod's claim never blames the candidate."""
    run, backend = experiment(
        tmp_path,
        [Step(outcome="failed", outputs=ended(claim), timing=CONFIRMED)],
        level=level,
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "candidate_failure_unattributed",
    )
    assert record["attempts"][0]["claimed_stage"] == claim
    assert record["attempts"][0]["construction_level"] == level
    assert len(backend.launched) == 1


@pytest.mark.parametrize("level", [L0, 3])
def test_at_levels_0_to_3_a_program_failure_stays_the_candidates(tmp_path, level):
    """Only Carbon's own trainer writes the claim, so a recipe that crashes it
    is charged to the candidate, never given infrastructure semantics (no
    retry, no refund: Track A selective crash and retry)."""
    run, backend = experiment(
        tmp_path,
        [Step(outcome="failed", outputs=ended("program"), timing=CONFIRMED), scored()],
        level=level,
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == ("CANDIDATE_FAILED", "program")
    assert record["scored"] is False
    assert len(backend.launched) == 1  # never retried


def test_at_level_0_a_pod_compile_failure_stays_infrastructure(tmp_path):
    """As before this rule: the pod's compile ran after Carbon's host compiled
    the same recipe, so its failure points at the pod's environment."""
    run, _ = experiment(
        tmp_path,
        [Step(outcome="failed", outputs=ended("compile"), timing=CONFIRMED)],
        level=L0,
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == ("FAILED_INFRA", "compile")


def test_a_supervisor_report_from_an_unseparated_image_is_evidence_only(tmp_path):
    """A supervisor.json claiming program failure, on an image with no
    separation record, cannot blame the candidate."""
    run, _ = experiment(
        tmp_path,
        [
            Step(
                outcome="failed",
                outputs=ended("program", supervisor={"stage": "program"}),
                timing=CONFIRMED,
            )
        ],
    )
    assert run_baseline(run)["status"] == "FAILED_INFRA"


def test_a_separated_images_supervisor_report_is_admissible(tmp_path, monkeypatch):
    """Levels 4-5: once an image has a separation record, its supervisor's
    report may name a program failure as the candidate's."""
    monkeypatch.setitem(
        pod_outcome.SEPARATED_IMAGES, "scripted-no-image", "test separation record"
    )
    run, _ = experiment(
        tmp_path,
        [
            Step(
                outcome="failed",
                # The shared-filesystem file says "timeout"; the admissible
                # report says "program". The admissible report wins.
                outputs=ended("timeout", supervisor={"stage": "program"}),
                timing=CONFIRMED,
            )
        ],
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == ("CANDIDATE_FAILED", "program")


def test_a_failed_pod_with_no_claim_is_infrastructure(tmp_path):
    run, _ = experiment(
        tmp_path, [Step(outcome="failed", outputs=ended(None), timing=None)]
    )
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == ("FAILED_INFRA", "pod")


def test_the_pods_own_deadline_stays_infrastructure_and_is_not_retried(tmp_path):
    run, backend = experiment(tmp_path, [Step(outcome="timeout"), scored()])
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == ("FAILED_INFRA", "infra")
    assert "attempts" not in record
    assert len(backend.launched) == 1


def test_a_launch_failure_on_the_retry_is_infrastructure(tmp_path):
    run, _ = experiment(tmp_path, [timed_out(), Step(launch="refused")])
    record = run_baseline(run)
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "launch_refused",
    )
    assert record["attempts"][0]["reason_code"] == "worker_timeout_retried"


def test_the_retry_is_charged_to_the_run_and_refused_when_it_cannot_fit(tmp_path):
    run, backend = experiment(tmp_path, [timed_out(), scored()], max_pods=1)
    record = run_baseline(run)
    assert record["status"] == "FAILED_INFRA"
    assert record["reason_code"] == (
        "worker_timeout_retry_refused:session_pod_limit_reached"
    )
    assert len(backend.launched) == 1


def test_a_restart_after_the_first_attempt_never_reruns(tmp_path):
    run, backend = experiment(tmp_path, [timed_out(crash="fetch"), scored()])
    from carbon.agent_campaign.controller import SimulatedCrash

    with pytest.raises(SimulatedCrash, match="pod fetch"):
        run_baseline(run)
    # The restarted process sees the reserved first attempt: the pod it may
    # have left is terminated, and nothing is launched again.
    again, _ = experiment(tmp_path, [], backend=backend)
    record = run_baseline(again)
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "interrupted_not_rerun",
    )
    assert len(backend.launched) == 1 and backend.alive == {}


# --- the classification itself ------------------------------------------------------


@pytest.mark.parametrize(
    ("claim", "admissible", "timing", "attempt", "level", "expected"),
    [
        (
            "timeout",
            None,
            CONFIRMED,
            0,
            L4,
            ("FAILED_INFRA", "worker_timeout_retried", True, False),
        ),
        (
            "timeout",
            None,
            None,
            0,
            L4,
            ("FAILED_INFRA", "worker_timeout_retried", True, False),
        ),
        (
            "timeout",
            None,
            CONFIRMED,
            1,
            L4,
            ("CANDIDATE_RESOURCE_EXCEEDED", "worker_timeout_repeated", False, False),
        ),
        (
            "timeout",
            None,
            UNCERTAIN,
            1,
            L4,
            ("FAILED_INFRA", "worker_timeout_unconfirmed", False, False),
        ),
        (
            "timeout",
            None,
            IMPOSSIBLE,
            0,
            L4,
            ("FAILED_INFRA", "timeout_claim_contradicts_host_timing", False, True),
        ),
        (
            "timeout",
            None,
            IMPOSSIBLE,
            1,
            L4,
            ("FAILED_INFRA", "timeout_claim_contradicts_host_timing", False, True),
        ),
        (
            "program",
            None,
            CONFIRMED,
            0,
            L4,
            ("FAILED_INFRA", "candidate_failure_unattributed", False, False),
        ),
        (
            "program",
            "program",
            CONFIRMED,
            0,
            L4,
            ("CANDIDATE_FAILED", "program", False, False),
        ),
        (
            "timeout",
            "program",
            CONFIRMED,
            0,
            L4,
            ("CANDIDATE_FAILED", "program", False, False),
        ),
        (None, None, None, 0, L4, ("FAILED_INFRA", "pod", False, False)),
        ("verification", None, CONFIRMED, 0, L4, ("FAILED_INFRA", "pod", False, False)),
        # Levels 0-3: Carbon's own trainer writes the claim.
        (
            "program",
            None,
            CONFIRMED,
            0,
            L0,
            ("CANDIDATE_FAILED", "program", False, False),
        ),
        (
            "program",
            None,
            CONFIRMED,
            0,
            3,
            ("CANDIDATE_FAILED", "program", False, False),
        ),
        ("compile", None, CONFIRMED, 0, L0, ("FAILED_INFRA", "compile", False, False)),
        (
            "timeout",
            None,
            CONFIRMED,
            0,
            L0,
            ("FAILED_INFRA", "worker_timeout_retried", True, False),
        ),
        (
            "timeout",
            None,
            CONFIRMED,
            1,
            L0,
            ("CANDIDATE_RESOURCE_EXCEEDED", "worker_timeout_repeated", False, False),
        ),
        (
            "timeout",
            None,
            IMPOSSIBLE,
            0,
            L0,
            ("FAILED_INFRA", "timeout_claim_contradicts_host_timing", False, True),
        ),
        (None, None, None, 0, L0, ("FAILED_INFRA", "pod", False, False)),
        # An unknown or malformed level is never trusted.
        (
            "program",
            None,
            CONFIRMED,
            0,
            None,
            ("FAILED_INFRA", "candidate_failure_unattributed", False, False),
        ),
        (
            "program",
            None,
            CONFIRMED,
            0,
            "0",
            ("FAILED_INFRA", "candidate_failure_unattributed", False, False),
        ),
        (
            "program",
            None,
            CONFIRMED,
            0,
            -1,
            ("FAILED_INFRA", "candidate_failure_unattributed", False, False),
        ),
        (
            "program",
            None,
            CONFIRMED,
            0,
            True,
            ("FAILED_INFRA", "candidate_failure_unattributed", False, False),
        ),
    ],
)
def test_the_order_of_authority(claim, admissible, timing, attempt, level, expected):
    verdict = pod_outcome.classify(
        claim=claim,
        admissible=admissible,
        timing=None if timing is None else HostTiming(**timing),
        work_seconds=WORK,
        attempt=attempt,
        level=level,
    )
    assert (verdict.status, verdict.reason_code, verdict.retry, verdict.signal) == (
        expected
    )


def test_host_timing_bounds():
    timing = HostTiming(**CONFIRMED)
    assert timing.phase_min() == WORK + 30
    assert timing.phase_max() == WORK + 60
    assert HostTiming().phase_min() is None and HostTiming().phase_max() is None
    assert pod_outcome.timeout_check(HostTiming(**IMPOSSIBLE), WORK) == "contradicted"
    assert pod_outcome.timeout_check(HostTiming(**UNCERTAIN), WORK) == "unconfirmed"
    assert pod_outcome.timeout_check(None, WORK) == "unconfirmed"


def test_admissibility_comes_from_the_hosts_record_never_the_pods_claim(
    monkeypatch,
):
    report = {"stage": "program", "separated": True, "uid": 65533}
    assert pod_outcome.admissible_stage(report, "any-image") is None
    monkeypatch.setitem(pod_outcome.SEPARATED_IMAGES, "img", "record")
    assert pod_outcome.admissible_stage(report, "img") == "program"
    assert pod_outcome.admissible_stage({"stage": "done"}, "img") is None
    assert pod_outcome.admissible_stage("program", "img") is None
    assert pod_outcome.SEPARATED_IMAGES.get(pods.prices()["image"]) is None


def test_the_runpod_backend_takes_its_timing_from_its_own_clock():
    """`RunPodPods.wait` records when each of the host's polls saw the phase:
    never a time the pod reports."""
    backend = object.__new__(pods.RunPodPods)
    now = [0.0]
    stages = iter(
        ["starting", "fetching_code", "running_phase", "running_phase", "phase_failed"]
    )

    def sleep(seconds):
        now[0] += seconds

    backend.clock = lambda: now[0]
    backend.sleep = sleep
    backend._get = lambda handle, path, timeout=60: (
        200,
        json.dumps({"stage": next(stages), "started_utc": "1970-01-01"}).encode(),
    )
    handle = pods.PodHandle("intent-1", "pod-1", "0.49")
    assert backend.wait(handle, deadline=10_000, cancelled=lambda: False) == "failed"
    timing = backend.timing(handle)
    step = pods.POLL_SECONDS
    assert timing == HostTiming(
        before_running=step,
        first_running=2 * step,
        last_running=3 * step,
        ended=4 * step,
    )
    assert backend.timing(pods.PodHandle("other", "pod-2", None)) is None


def test_the_level_comes_from_the_runs_recorded_permission_profile():
    """Phase 3 reads the level from the profile its run recorded, never from a
    submission: the profile's level only when the digests match."""
    from carbon.agent_campaign.graphite import phase3

    document, profile = phase3.permission_profile()
    assert document["level"] == 0
    assert phase3.recorded_level({"task": {"profile_digest": profile}}) == 0
    other = "sha256:" + "f" * 64
    assert phase3.recorded_level({"task": {"profile_digest": other}}) is None
    assert phase3.recorded_level({"task": {}}) is None
    assert phase3.recorded_level({}) is None
