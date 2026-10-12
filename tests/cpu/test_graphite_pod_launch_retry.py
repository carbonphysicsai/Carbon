"""GRAPHITE-POD-LAUNCH-RETRY-01: a refused launch records its code and the
provider's (bounded, redacted) message, and the session baseline retries a
transient refusal in place with a jittered wait. Hard refusals never retry.

The pods are scripted (fault injection): no pod, key, network or spend.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from graphite_phase3_fixtures import BASELINE, SCORING, grant, variant

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pods
from carbon.agent_campaign.graphite.pods import ScriptedPods, Step, synthetic_outputs

REPOSITORY = Path(__file__).resolve().parents[2]
WHY = {"hypothesis": "h", "expected_effect": "e"}


class Ladder:
    def record_failure(self, *args, **kwargs):
        return "failure-1"


def experiment(tmp_path, steps):
    slept = []
    backend = ScriptedPods(steps=steps)
    run = ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-launch",
        pods=backend,
        budget=ex.phase3_budget(grant(), SCORING),
        baseline=BASELINE,
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=Ladder(),
        emit=lambda event_id, body: None,
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x80" * n,
        scoring=SCORING,
        construction_level=4,
        sleep=slept.append,
    )
    return run, backend, slept


def scored(quality=1.0, **step):
    return Step(outputs=synthetic_outputs(quality), **step)


def rows(run, event):
    return [r for r in run.ledger.rows() if r["event"] == event]


@pytest.mark.parametrize(
    "detail,code",
    [
        ("Too Many Requests (429)", "rate_limited"),
        ("no A40 Secure pod at or below the rate ceiling now", "offer_unavailable"),
        ("", "empty"),
        ("   ", "empty"),
        ("balance would fall below the floor", "balance_floor"),
        ("401 Unauthorized: bad api key", "credential"),
        ("the torch CUDA runtime is above RunPod's", "cuda_policy"),
        (
            "pod_env_too_large: the pod environment is 70000 characters",
            "pod_env_too_large",
        ),
        ("pod job record conflict", "job_record_conflict"),
        ("something else entirely", "provider_other"),
    ],
)
def test_every_refusal_is_classified(detail, code):
    assert pods.refusal_code(detail) == code
    assert pods.PodFailure("launch", detail, executed=False).code == code
    assert (code in pods.TRANSIENT_REFUSALS) == (
        code in ("rate_limited", "offer_unavailable", "empty")
    )


def test_the_recorded_detail_is_one_line_bounded_and_redacted():
    secret = "rk_" + "A1b2C3d4" * 6
    detail = f"provider said:\n  key {secret} invalid " + "x" * 600
    shown = pods.bounded_detail(detail)
    assert "\n" not in shown and len(shown) <= pods.DETAIL_LIMIT
    assert secret not in shown and "<redacted>" in shown


def test_a_transient_baseline_refusal_is_retried_and_the_baseline_scores(tmp_path):
    steps = [
        scored(1.0, refusals=2, refusal_detail="Too Many Requests (429)"),
        scored(0.4),
    ]
    run, backend, slept = experiment(tmp_path, steps)
    record = run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert run.record("baseline")["status"] == "SCORED"
    assert record["against_baseline"]["outcome"] != "NO_BASELINE"
    retries = rows(run, "pod_launch_retry")
    assert [r["attempt"] for r in retries] == [1, 2]
    assert {r["code"] for r in retries} == {"rate_limited"}
    assert all(ex.LAUNCH_BACKOFF_S[0] <= w <= ex.LAUNCH_BACKOFF_S[1] for w in slept)
    assert len(slept) == 2 and slept == [r["wait_s"] for r in retries]
    assert not rows(run, "pod_launch_refused")
    # One intent for the baseline, launched three times, one pod created.
    baseline_intents = [i for i, _ in backend.launched if i == backend.launched[0][0]]
    assert len(baseline_intents) == 3
    assert (
        len([r for r in rows(run, "pod_created") if r["proposal"] == "baseline"]) == 1
    )


def test_a_baseline_refused_on_every_try_records_why(tmp_path):
    steps = [
        scored(
            1.0,
            refusals=5,
            refusal_detail="no A40 Secure pod at or below the rate ceiling now",
        ),
        scored(0.4),
    ]
    run, _backend, slept = experiment(tmp_path, steps)
    run.run("p-one", "proposal", variant(width=128), why=WHY)
    first = run.record("baseline")
    assert (first["status"], first["reason_code"]) == ("FAILED_INFRA", "launch_refused")
    assert first["launch_refusal"] == {
        "stage": "launch",
        "code": "offer_unavailable",
        "detail": "no A40 Secure pod at or below the rate ceiling now",
        "attempts": ex.LAUNCH_ATTEMPTS,
    }
    [refused] = [
        r for r in rows(run, "pod_launch_refused") if r["proposal"] == "baseline"
    ]
    assert (
        refused["code"] == "offer_unavailable"
        and refused["attempt"] == ex.LAUNCH_ATTEMPTS
    )
    assert len(slept) == ex.LAUNCH_ATTEMPTS - 1


@pytest.mark.parametrize(
    "detail",
    ["balance would fall below the floor", "401 Unauthorized", "scripted refusal"],
)
def test_a_hard_refusal_is_never_retried(tmp_path, detail):
    run, _backend, slept = experiment(
        tmp_path, [scored(1.0, refusals=1, refusal_detail=detail), scored(0.4)]
    )
    run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert run.record("baseline")["reason_code"] == "launch_refused"
    assert run.record("baseline")["launch_refusal"]["code"] == pods.refusal_code(detail)
    assert slept == [] and not rows(run, "pod_launch_retry")


def test_an_agent_proposals_transient_refusal_is_recorded_not_retried(tmp_path):
    steps = [
        scored(1.0),
        scored(0.4, refusals=1, refusal_detail="Too Many Requests (429)"),
    ]
    run, _backend, slept = experiment(tmp_path, steps)
    record = run.run("p-one", "proposal", variant(width=128), why=WHY)
    assert (record["status"], record["reason_code"]) == (
        "FAILED_INFRA",
        "launch_refused",
    )
    assert record["launch_refusal"]["code"] == "rate_limited"
    assert slept == []


@pytest.mark.parametrize(
    "source,code",
    [
        ("runpod.graphql.gpuTypes.lowestPrice.http429", "rate_limited"),
        ("runpod.graphql.gpuTypes.lowestPrice", "offer_unavailable"),
    ],
)
def test_lane_ds_offer_read_is_recorded_and_transient(source, code):
    """Lane D (2026-10-12): a start-of-run offer read with no price (a non-200
    answer, or a null stock) refused the baseline. The refusal now names the
    read, and it classifies as transient."""
    detail = (
        "no A40 Secure pod at or below the rate ceiling now "
        f"(price None, stock None, source {source})"
    )
    assert pods.refusal_code(detail) == code
    assert code in pods.TRANSIENT_REFUSALS
    assert "price None" in pods.bounded_detail(detail)
