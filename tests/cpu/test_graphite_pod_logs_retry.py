"""Graphite R2 run 4 fixes (GRAPHITE-POD-LOGS-RETRY-01).

Fix 2, kept logs: a proposal whose pod outcome is not SCORED keeps its pods'
`program.log` and `phase.log`, bounded, in its record directory under the
session root. A log is stored only when its bytes match the digest the pod
listed and it names no protected material; it is operator evidence only and
never reaches a result record, a feedback document, an event, the session
summary or a delivery bundle.

Fix 3, the baseline retry: a baseline that closes FAILED_INFRA because its pod
ran and ended in infrastructure is run once more, on a later pod, under the
registered policy `baseline-retry-v1`, held to every existing limit; a retry
that scores becomes the session's baseline.

The pods are scripted: no pod, key, network or spend. Carbon's admission,
rebuild check and frozen-rule scoring run for real on synthetic predictions.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from graphite_phase3_fixtures import (
    BASELINE,
    grant,
    propose,
    run_id,
    session,
    variant,
)

from carbon.agent_campaign.controller import SimulatedCrash
from carbon.agent_campaign.graphite import baseline_retry, pod_logs, pods
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite.model import text
from carbon.agent_campaign.graphite.pods import (
    ScriptedPods,
    Step,
    failed_outputs,
    synthetic_outputs,
)

REPOSITORY = Path(__file__).resolve().parents[2]
L0, L4 = 0, 4
RETRY = baseline_retry.RETRY_ID
WORK = pods.contract_work_seconds()
CONFIRMED = {
    "before_running": 0.0,
    "first_running": 15.0,
    "last_running": 15.0 + WORK + 30,
    "ended": 15.0 + WORK + 45,
}
#: A log larger than the per-file cap whose traceback ends it.
LONG_LOG = (
    b"".join(b"step %06d loss 0.5\n" % i for i in range(12000))
    + b"Traceback (most recent call last):\n"
    + b'  File "<string>", line 9, in <module>\n'
    + b"FloatingPointError: SYNTHETIC non-finite loss\n"
)
WHY = {"hypothesis": "h", "expected_effect": "e"}


class Ladder:
    def record_failure(self, *args, **kwargs):
        return "failure-1"


def experiment(
    tmp_path,
    steps,
    *,
    max_pods=None,
    backend=None,
    level=L4,
    tokens=Decimal(0),
    seconds_left=None,
):
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
        run_id="run-r2",
        pods=backend,
        budget=budget,
        baseline=BASELINE,
        token_committed=lambda: tokens,
        cancelled=lambda: False,
        ladder=Ladder(),
        emit=lambda event_id, body: events.append((event_id, body)),
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x02" * n,
        construction_level=level,
        seconds_left=seconds_left,
    )
    run.events = events
    return run, backend


def program_failure(logs=None, stage="program", **step):
    """The run-4 shape: compile and digest checks passed, the program exited 1."""
    return Step(outcome="failed", outputs=failed_outputs(stage, logs=logs), **step)


def infra_failure(**step):
    """A pod that ran and ended with no claim (FAILED_INFRA, `pod`)."""
    return Step(outcome="failed", outputs=failed_outputs(None), **step)


def scored(quality=1.0, logs=None):
    honest = synthetic_outputs(quality)

    def outputs(job):
        return {**honest(job), **(logs or {})}

    return Step(outputs=outputs)


def logs_of(run, pid):
    return pod_logs.read_index(run.root / "proposals" / pid / "pod-logs")


def entry(run, pid, name, attempt=0):
    [found] = [e for e in logs_of(run, pid)[attempt]["logs"] if e["name"] == name]
    return found


def stored(run, pid, name, attempt=0):
    return (
        run.root / "proposals" / pid / "pod-logs" / f"attempt-{attempt}" / name
    ).read_bytes()


def everything_but_logs(run):
    """Every byte the run wrote outside the kept-log folders, and its events."""
    out = b""
    for path in sorted(run.root.rglob("*")):
        if path.is_file() and "pod-logs" not in path.parts:
            out += path.read_bytes()
    return out + b"".join(json.dumps(body).encode() for _e, body in run.events)


# -- fix 2: kept logs ----------------------------------------------------------------------
@pytest.mark.parametrize("level", [L0, L4])
def test_a_failed_pods_logs_are_kept_bounded_with_the_truncation_recorded(
    tmp_path, level
):
    run, _ = experiment(
        tmp_path,
        [program_failure({"program.log": LONG_LOG, "phase.log": b"phase ok\n"})],
        level=level,
    )
    record = run.run("baseline", "baseline", BASELINE, why=None)
    assert record["status"] != "SCORED"
    [index] = logs_of(run, "baseline")
    assert index["operator_evidence_only"] is True
    assert index["intent_id"] == "run-r2-baseline"
    assert index["caps"] == pod_logs.caps()
    program = entry(run, "baseline", "program.log")
    head, tail = pod_logs.LOG_HEAD_BYTES, pod_logs.LOG_TAIL_BYTES
    assert program["status"] == pod_logs.KEPT
    assert program["bytes"] == len(LONG_LOG)
    assert program["digest"] == "sha256:" + hashlib.sha256(LONG_LOG).hexdigest()
    assert program["kept_bytes"] == head + tail
    assert program["truncated_bytes"] == len(LONG_LOG) - head - tail
    assert program["exception_class"] == "FloatingPointError"
    body = stored(run, "baseline", "program.log")
    first, rest = body.split(b"\n", 1)
    assert first.startswith(b"[carbon pod log] program.log: %d bytes" % len(LONG_LOG))
    assert b"%d bytes truncated" % program["truncated_bytes"] in first
    marker = (
        b"\n[carbon pod log: %d bytes truncated here]\n" % (program["truncated_bytes"])
    )
    assert rest == LONG_LOG[:head] + marker + LONG_LOG[-tail:]
    assert len(body) < head + tail + 1024  # the header and marker are small
    phase = entry(run, "baseline", "phase.log")
    assert (phase["status"], phase["truncated_bytes"]) == (pod_logs.KEPT, 0)
    assert stored(run, "baseline", "phase.log").endswith(b"kept whole\nphase ok\n")
    # The ledger carries names, statuses and digests only.
    [row] = [r for r in run.ledger.rows() if r["event"] == "pod_logs_kept"]
    assert row["proposal"] == "baseline"
    assert set(row["attempts"][0]["logs"][0]) == {"name", "status", "bytes", "digest"}


def test_a_scored_pods_logs_are_not_kept(tmp_path):
    run, _ = experiment(tmp_path, [scored(logs={"program.log": b"fine\n"})])
    record = run.run("baseline", "baseline", BASELINE, why=None)
    assert record["status"] == "SCORED"
    assert not (run.root / "proposals" / "baseline" / "pod-logs").exists()
    assert "pod_logs_kept" not in [r["event"] for r in run.ledger.rows()]


@pytest.mark.parametrize(
    "text",
    [
        b"loading official_seed from the pack\n",
        b"echo CARBON-CANARY-1234\n",
        b"Verification Reference loaded\n",
    ],
)
def test_a_log_naming_protected_material_is_withheld_with_its_digest(tmp_path, text):
    body = b"line\n" * 10 + text + b"line\n"
    run, _ = experiment(
        tmp_path, [program_failure({"program.log": body, "phase.log": b"ok\n"})]
    )
    run.run("baseline", "baseline", BASELINE, why=None)
    program = entry(run, "baseline", "program.log")
    assert program["status"] == pod_logs.WITHHELD_PROTECTED
    assert program["digest"] == "sha256:" + hashlib.sha256(body).hexdigest()
    assert "exception_class" not in program and "kept_bytes" not in program
    folder = run.root / "proposals" / "baseline" / "pod-logs" / "attempt-0"
    assert not (folder / "program.log").exists()
    assert entry(run, "baseline", "phase.log")["status"] == pod_logs.KEPT
    assert text not in everything_but_logs(run)


def test_a_log_that_does_not_match_the_pods_listing_is_a_digest_mismatch(tmp_path):
    run, _ = experiment(tmp_path, [program_failure(listed={"program.log": "0" * 64})])
    run.run("baseline", "baseline", BASELINE, why=None)
    program = entry(run, "baseline", "program.log")
    assert (program["status"], program["listed_sha256"]) == (
        pod_logs.DIGEST_MISMATCH,
        "0" * 64,
    )
    body = pods.SYNTHETIC_LOGS["program.log"]
    assert program["digest"] == "sha256:" + hashlib.sha256(body).hexdigest()
    folder = run.root / "proposals" / "baseline" / "pod-logs" / "attempt-0"
    assert not (folder / "program.log").exists()
    assert (folder / "phase.log").exists()  # its own listing matches


def test_a_backend_that_lists_nothing_keeps_no_log(tmp_path):
    class Unlisted(ScriptedPods):
        def listing(self, handle):
            return None

    run, _ = experiment(tmp_path, [], backend=Unlisted(steps=[program_failure()]))
    run.run("baseline", "baseline", BASELINE, why=None)
    statuses = {e["status"] for e in logs_of(run, "baseline")[0]["logs"]}
    assert statuses == {pod_logs.DIGEST_MISMATCH}


def test_the_proposals_total_allowance_bounds_every_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(pod_logs, "LOG_TOTAL_BYTES", 1000)
    big = b"x" * 900 + b"\n"
    run, _ = experiment(
        tmp_path, [program_failure({"program.log": big, "phase.log": big})]
    )
    run.run("baseline", "baseline", BASELINE, why=None)
    program = entry(run, "baseline", "program.log")
    phase = entry(run, "baseline", "phase.log")
    assert (program["status"], program["kept_bytes"]) == (pod_logs.KEPT, 901)
    # 99 bytes remain: kept as head and tail, the truncation recorded.
    assert (phase["status"], phase["kept_bytes"]) == (pod_logs.KEPT, 99)
    assert phase["truncated_bytes"] == 901 - 99
    assert b"bytes truncated here" in stored(run, "baseline", "phase.log")


def test_a_spent_allowance_withholds_the_log(tmp_path, monkeypatch):
    monkeypatch.setattr(pod_logs, "LOG_TOTAL_BYTES", 10)
    run, _ = experiment(
        tmp_path,
        [program_failure({"program.log": b"0123456789", "phase.log": b"more\n"})],
    )
    run.run("baseline", "baseline", BASELINE, why=None)
    assert entry(run, "baseline", "phase.log")["status"] == pod_logs.WITHHELD_TOTAL_CAP


def test_a_log_too_large_to_scan_is_withheld(tmp_path, monkeypatch):
    monkeypatch.setattr(pod_logs, "MAX_LOG_SCAN_BYTES", 100)
    run, _ = experiment(tmp_path, [program_failure({"program.log": b"y" * 101})])
    run.run("baseline", "baseline", BASELINE, why=None)
    assert entry(run, "baseline", "program.log")["status"] == (
        pod_logs.WITHHELD_TOO_LARGE
    )


def test_kept_logs_never_reach_records_feedback_events_or_the_summary(tmp_path):
    secret_text = b"SYNTHETIC distinctive log text 7f3a\n"
    run, _ = experiment(
        tmp_path,
        [scored(1.0), program_failure({"program.log": secret_text})],
        level=L0,
    )
    feedback = run.propose_tool(
        {
            "strategy_json": json.dumps(variant(width=128)),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        "identity-1",
    )
    assert feedback["status"] == "CANDIDATE_FAILED"
    [pid] = [r["proposal_id"] for r in run.records("proposal")]
    assert entry(run, pid, "program.log")["status"] == pod_logs.KEPT
    assert secret_text.strip() not in json.dumps(feedback).encode()
    assert secret_text.strip() not in json.dumps(run.summary()).encode()
    assert secret_text.strip() not in everything_but_logs(run)
    assert "pod-logs" not in json.dumps(feedback)


def test_kept_logs_stay_under_the_session_root_outside_the_repository(tmp_path):
    run, _ = experiment(tmp_path, [program_failure()])
    run.run("baseline", "baseline", BASELINE, why=None)
    kept = list(tmp_path.rglob("pod-logs"))
    assert kept and all(tmp_path in path.parents for path in kept)
    assert REPOSITORY not in tmp_path.parents


def test_the_live_backend_records_the_pods_listing(tmp_path):
    """`RunPodPods.fetch` keeps the sha256 the pod listed per file, with RunPod
    in memory (no network, no spend)."""
    import subprocess

    from carbon.agent_campaign.graphite.pods import (
        CHECK_KEY,
        InMemoryRunPod,
        PodJob,
        RunPodPods,
    )

    account = InMemoryRunPod()
    key = tmp_path / "key"
    key.write_text(CHECK_KEY + "\n")
    key.chmod(0o600)
    head = subprocess.run(
        ["git", "-C", str(REPOSITORY), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    backend = RunPodPods(
        root=tmp_path / "pods",
        key_file=key,
        code_ref=head,
        transport=account.transport,
        http=account.http,
        sleep=lambda _s: None,
        balance_floor=lambda: Decimal(0),
    )
    job = PodJob("listing-1", {"x": 1}, "sha256:" + "0" * 64, 1, {"files": {}}, 30, 600)
    private = pods.private_dir(tmp_path / "private")
    handle = backend.launch(job, private)
    assert backend.listing(handle) is None
    files = backend.fetch(handle)
    assert backend.listing(handle) == {
        name: hashlib.sha256(body).hexdigest() for name, body in files.items()
    }
    assert backend.terminate(handle)


def test_the_exception_class_is_the_last_tracebacks_name_only():
    chained = (
        "Traceback (most recent call last):\n  x\nKeyError: 'a'\n\n"
        "During handling of the above exception, another exception occurred:\n\n"
        'Traceback (most recent call last):\n  File "p", line 1\n'
        "jax.errors.ConcretizationTypeError: secret message\n"
    )
    assert pod_logs.exception_class(chained) == "jax.errors.ConcretizationTypeError"
    assert pod_logs.exception_class("no traceback here\n") is None
    assert pod_logs.exception_class("Traceback (most recent call last):\n") is None
    assert (
        pod_logs.exception_class(
            "Traceback (most recent call last):\n  f\nSystemExit\n"
        )
        == "SystemExit"
    )


# -- fix 3: the baseline retry -------------------------------------------------------------
def decided(run):
    return run.baseline_retry()


def seed_of(run, pid):
    return (run.root / "proposals" / pid / "seed.bin").read_bytes()


def test_a_baseline_failed_as_infrastructure_is_retried_once_and_becomes_the_baseline(
    tmp_path,
):
    """Level 4: the run-4 shape (a `program` claim on a shared uid) is evidence
    only, FAILED_INFRA `candidate_failure_unattributed`: retried on a later
    pod with the same seed, and the retry is the session's baseline."""
    run, backend = experiment(
        tmp_path, [program_failure(), scored(1.0), scored(0.4)], level=L4
    )
    record = run.run("p-one", "proposal", variant(width=128), why=WHY)
    first = run.record("baseline")
    assert (first["status"], first["reason_code"]) == (
        "FAILED_INFRA",
        "candidate_failure_unattributed",
    )
    retried = run.record(RETRY)
    assert (retried["status"], retried["kind"]) == ("SCORED", "baseline")
    assert run.baseline_id() == RETRY
    assert seed_of(run, RETRY) == seed_of(run, "baseline")
    assert retried["recipe_digest"] == first["recipe_digest"]
    # The proposal is compared with the retry: promotable-eligible.
    assert record["status"] == "SCORED"
    assert record["against_baseline"]["outcome"] == "IMPROVEMENT"
    assert record["against_baseline"]["promotable"] is True
    assert record["baseline"]["proposal_id"] == RETRY
    assert record["baseline"]["score"] == retried["frozen_rule"]["score"]
    # Three pods, three distinct intents.
    assert len(backend.launched) == 3
    assert len({intent for intent, _job in backend.launched}) == 3
    # Recorded: the run's decision, the pod ledger and the session's events.
    decision = decided(run)
    policy = baseline_retry.load_policy()
    assert decision["schema"] == baseline_retry.DECISION_SCHEMA
    assert (decision["retry"], decision["reason_code"]) == (True, "retried")
    assert decision["policy"] == policy.record()
    assert decision["policy"]["version"] == "baseline-retry-v1"
    assert decision["baseline"] == {
        "proposal_id": "baseline",
        "status": "FAILED_INFRA",
        "reason_code": "candidate_failure_unattributed",
    }
    assert decision["earlier_scored_not_recompared"] == []
    [row] = [r for r in run.ledger.rows() if r["event"] == "baseline_retry_decided"]
    assert (row["retry"], row["retry_proposal_id"]) == (True, RETRY)
    [event] = [body for event_id, body in run.events if event_id == "baseline-retry"]
    assert event["kind"] == "baseline_retry" and event["retry"] is True
    assert run.summary()["baseline_retry"] == decision
    # Its pod's logs were kept; the retry scored, so none for it.
    assert logs_of(run, "baseline")
    assert not (run.root / "proposals" / RETRY / "pod-logs").exists()


def test_no_retry_when_the_baseline_failed_as_the_candidate(tmp_path):
    """Level 0: Carbon's own trainer wrote the claim, so a program failure is
    CANDIDATE_FAILED (pod-attribution-v1) and is never retried."""
    run, backend = experiment(
        tmp_path, [program_failure(), scored(0.4), scored(0.4)], level=L0
    )
    record = run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert run.record("baseline")["status"] == "CANDIDATE_FAILED"
    assert (decided(run)["retry"], decided(run)["reason_code"]) == (
        False,
        baseline_retry.CANDIDATE_ATTRIBUTED,
    )
    assert run.record(RETRY) is None and len(backend.launched) == 2
    assert record["against_baseline"]["outcome"] == "NO_BASELINE"
    assert record["against_baseline"]["promotable"] is False


def test_no_retry_when_the_baseline_exceeded_its_resources(tmp_path):
    timed = Step(
        outcome="failed",
        outputs=failed_outputs("timeout"),
        timing=CONFIRMED,
    )
    run, backend = experiment(tmp_path, [timed, timed, scored(0.4)], level=L4)
    run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert run.record("baseline")["status"] == "CANDIDATE_RESOURCE_EXCEEDED"
    assert decided(run)["reason_code"] == baseline_retry.CANDIDATE_ATTRIBUTED
    assert len(backend.launched) == 3  # two timeout attempts and the proposal


def test_no_retry_when_the_launch_gate_refused_the_baseline(tmp_path):
    run, backend = experiment(tmp_path, [Step(launch="refused"), scored(0.4)])
    record = run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert run.record("baseline")["reason_code"] == "launch_refused"
    assert decided(run)["reason_code"] == baseline_retry.NOT_RETRYABLE_REASON
    assert record["against_baseline"]["outcome"] == "NO_BASELINE"
    assert len(backend.launched) == 2


def test_no_second_retry(tmp_path):
    run, backend = experiment(
        tmp_path,
        [infra_failure(), infra_failure(), scored(0.4), scored(0.4), scored(0.4)],
    )
    first = run.run("p-one", "proposal", variant(width=128), why=WHY)
    second = run.run("p-two", "proposal", variant(width=96), why=WHY)
    assert run.record("baseline")["reason_code"] == "pod"
    assert run.record(RETRY)["status"] == "FAILED_INFRA"
    assert run.baseline_id() == "baseline"
    for record in (first, second):
        assert record["against_baseline"]["outcome"] == "NO_BASELINE"
    assert len(backend.launched) == 4  # baseline, its one retry, two proposals
    assert [r["event"] for r in run.ledger.rows()].count("baseline_retry_decided") == 1
    assert len(run.records("baseline")) == 2


def _tight_tokens():
    """Token spend that leaves the run's cap room for the baseline's pod and
    one more after it, but not two."""
    budget = ex.phase3_budget(grant())
    return budget.run_cap_usd - Decimal("1.5") * budget.pod_reservation_usd


@pytest.mark.parametrize(
    ("limits", "code"),
    [
        (lambda: {"max_pods": 2}, "not_retried:session_pod_limit_reached"),
        (
            lambda: {"tokens": _tight_tokens()},
            "not_retried:run_cap_reached_tokens_plus_pods",
        ),
    ],
)
def test_no_retry_when_the_budget_cannot_cover_it(tmp_path, limits, code):
    """The retry and the waiting proposal's pod must both fit the session's
    pod limit and the run's money cap (tokens and pods together)."""
    run, backend = experiment(tmp_path, [infra_failure(), scored(0.4)], **limits())
    record = run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert (decided(run)["retry"], decided(run)["reason_code"]) == (False, code)
    assert run.record(RETRY) is None
    # The proposal still runs on the pod the retry did not take.
    assert len(backend.launched) == 2
    assert record["status"] == "SCORED"
    assert record["against_baseline"]["outcome"] == "NO_BASELINE"


def test_no_retry_when_its_pods_cannot_finish_in_the_remaining_time(tmp_path):
    run, _ = experiment(
        tmp_path,
        [infra_failure(), scored(0.4)],
        seconds_left=lambda: 1.5 * run.budget.pod_minutes * 60,
    )
    run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert decided(run)["reason_code"] == baseline_retry.NO_TIME
    assert run.record(RETRY) is None


def test_a_retry_a_process_death_interrupted_runs_once_on_resume(tmp_path):
    steps = [infra_failure(), scored(1.0), scored(0.4)]
    run, backend = experiment(tmp_path, steps)
    original = ex.Experiment._run_retry

    def crash(self, decision):
        raise SimulatedCrash("before the retry")

    ex.Experiment._run_retry = crash
    try:
        with pytest.raises(SimulatedCrash):
            run.run("p-one", "proposal", variant(width=128), why=WHY)
    finally:
        ex.Experiment._run_retry = original
    assert decided(run)["retry"] is True and run.record(RETRY) is None
    assert run.pods_before_proposal() == 1  # the time gate counts it
    again, _ = experiment(tmp_path, [], backend=backend)
    record = again.run("p-one", "proposal", variant(width=128), why=WHY)
    assert again.record(RETRY)["status"] == "SCORED"
    assert record["against_baseline"]["outcome"] == "IMPROVEMENT"
    assert again.pods_before_proposal() == 0
    assert len(backend.launched) == 3


def test_results_scored_before_the_retry_stay_no_baseline_and_are_listed(
    tmp_path, monkeypatch
):
    """A session whose baseline failed before this rule existed: its earlier
    scored proposal is not re-compared (records are write-once), and the
    decision says so."""
    run, _ = experiment(
        tmp_path, [infra_failure(), scored(0.4), scored(1.0), scored(0.4)]
    )
    monkeypatch.setattr(ex.Experiment, "_retry_baseline", lambda self: None)
    early = run.run("p-early", "proposal", variant(width=128), why=WHY)
    monkeypatch.undo()
    late = run.run("p-late", "proposal", variant(width=96), why=WHY)
    assert early["against_baseline"]["outcome"] == "NO_BASELINE"
    assert run.record("p-early") == early  # never rewritten
    decision = decided(run)
    assert decision["retry"] is True
    assert decision["earlier_scored_not_recompared"] == ["p-early"]
    assert "write-once" in decision["earlier_scored_note"]
    assert late["against_baseline"]["outcome"] != "NO_BASELINE"


def test_the_decision_is_a_pure_function_of_the_record_and_the_limits():
    policy = baseline_retry.load_policy()

    def decide(status, reason, used=0, budget=None, time=True):
        return baseline_retry.decide(
            policy=policy,
            first={"status": status, "reason_code": reason},
            retries_used=used,
            budget_refusal=budget,
            time_fits=time,
        )

    for reason in ("candidate_failure_unattributed", "compile", "infra", "pod"):
        assert decide("FAILED_INFRA", reason) == (True, "retried")
    assert decide("FAILED_INFRA", "predictions_missing") == (True, "retried")
    for reason in (
        "launch_refused",
        "launch_unresolved",
        "interrupted_not_rerun",
        "worker_timeout_unconfirmed",
        "timeout_claim_contradicts_host_timing",
        "worker_timeout_retry_refused:session_pod_limit_reached",
    ):
        assert decide("FAILED_INFRA", reason) == (
            False,
            "not_retried:reason_not_retryable",
        )
    assert (
        decide("CANDIDATE_FAILED", "program")[1] == "not_retried:candidate_attributed"
    )
    assert decide("CANDIDATE_RESOURCE_EXCEEDED", "worker_timeout_repeated")[1] == (
        "not_retried:candidate_attributed"
    )
    assert decide("REBUILD_MISMATCH", None)[1] == "not_retried:status_not_retryable"
    assert decide("FAILED_INFRA", "pod", used=1) == (
        False,
        "not_retried:retry_already_used",
    )
    assert decide("FAILED_INFRA", "pod", budget="session_pod_limit_reached") == (
        False,
        "not_retried:session_pod_limit_reached",
    )
    assert decide("FAILED_INFRA", "pod", time=False)[1] == NO_TIME
    with pytest.raises(TypeError):
        baseline_retry.decide(
            policy=None,
            first={},
            retries_used=0,
            budget_refusal=None,
            time_fits=True,
        )


NO_TIME = baseline_retry.NO_TIME


def _policy_dir(tmp_path, change):
    folder = tmp_path / "policies"
    shutil.copytree(baseline_retry.POLICY_DIR, folder)
    path = folder / "baseline-retry-v1.json"
    document = json.loads(path.read_text())
    change(document)
    path.write_text(json.dumps(document))
    registry = json.loads((folder / "registry.json").read_text())
    registry["versions"]["baseline-retry-v1"] = baseline_retry._digest(document)
    (folder / "registry.json").write_text(json.dumps(registry))
    return folder


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(max_retries=2),
        lambda d: d.update(retry_on_status="CANDIDATE_FAILED"),
        lambda d: d["retry_on_reasons"].append("launch_refused"),
        lambda d: d["retry_on_reasons"].append("launch_unresolved"),
        lambda d: d.update(never_on_status=["CANDIDATE_FAILED"]),
        lambda d: d["never_on_status"].append("FAILED_INFRA"),
        lambda d: d.update(pods_required=0),
        lambda d: d["limits"].remove("remaining_elapsed_time"),
        lambda d: d["limits"].append("session_pod_limit"),
        lambda d: d.update(seed="fresh_draw"),
        lambda d: d.update(earlier_scored_results="recompared"),
        lambda d: d.update(extra=True),
    ],
)
def test_an_unsafe_registered_policy_is_refused(tmp_path, change):
    folder = _policy_dir(tmp_path, change)
    with pytest.raises(baseline_retry.PolicyRefused):
        baseline_retry.load_policy(directory=folder)


def test_an_altered_or_unregistered_policy_is_refused(tmp_path):
    folder = tmp_path / "policies"
    shutil.copytree(baseline_retry.POLICY_DIR, folder)
    path = folder / "baseline-retry-v1.json"
    document = json.loads(path.read_text())
    document["pods_required"] = 1
    path.write_text(json.dumps(document))
    with pytest.raises(baseline_retry.PolicyRefused, match="altered"):
        baseline_retry.load_policy(directory=folder)
    with pytest.raises(baseline_retry.PolicyRefused, match="not registered"):
        baseline_retry.load_policy("baseline-retry-v9")
    assert baseline_retry.registered_policies() == ["baseline-retry-v1"]
    policy = baseline_retry.load_policy()
    assert (policy.max_retries, policy.pods_required) == (1, 2)


def test_a_session_compares_with_the_retried_baseline_and_bundles_it(tmp_path):
    """Through the phase-3 provider and controller (Level 0, the session's
    recorded level): the baseline's pod ends with no claim, the retry scores,
    the proposal improves on it, and the bundle's baseline is the retry."""
    account = ScriptedPods(
        steps=[
            infra_failure(),
            scored(1.0),
            scored(0.4),
            *[scored(0.4) for _ in range(4)],
        ]
    )
    result, graphite, _ = session(
        tmp_path, [propose(variant(width=128)), text("done")], account
    )
    experiment = graphite.experiment(run_id())
    assert experiment.construction_level == L0
    assert experiment.baseline_id() == RETRY
    assert result["summary"]["baseline_retry"]["retry"] is True
    delivery = result["delivery"]
    assert delivery["clean_rebuild"]["status"] == "REBUILT"
    bundle = Path(delivery["bundle"])
    baseline = json.loads((bundle / "baseline.json").read_bytes())
    assert baseline["result"]["proposal_id"] == RETRY
    assert b"pod_logs_kept" not in (bundle / "run-log.jsonl").read_bytes()
    assert account.alive == {}


def test_the_failure_path_check_is_ok_and_fails_when_a_fix_is_off(tmp_path):
    budget = ex.phase3_budget(grant())
    report = ex.failure_path_check(tmp_path / "ok", baseline=BASELINE, budget=budget)
    assert report["status"] == "OK", report
    assert report["pods_launched"] == 4
    assert report["baseline_retry"]["retry_status"] == "SCORED"
    assert report["compared"]["baseline"] == RETRY
    [program, phase] = report["failed_pod"]["logs"]
    assert program["status"] == "kept" and program["truncated_bytes"] > 0
    assert program["exception_class"] == "RuntimeError"
    assert phase["status"] == "kept"
