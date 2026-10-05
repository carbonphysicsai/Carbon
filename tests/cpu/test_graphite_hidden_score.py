"""Graphite constructions scored on hidden batches through battery's real
validator (VALIDATOR-13).

The validator fixtures are the battery daemon's: real PyBaMM references
retained by the exam-design campaign, battery rule v2, and `DirectBackend` in
process. They check control flow and disclosure, not isolation or truth
solves. The pods are scripted: no pod, key, network or spend. None of this is
a security audit (AGENTS.md §13).

The central check is the non-leak differential. Two validators whose hidden
pools score one construction differently give the agent byte-identical
feedback, so no hidden result can reach it.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from graphite_phase3_fixtures import SCORING, grant
from test_battery_validator_daemon import (
    BATTERY,
    PIN_G,
    backend,  # noqa: F401 - fixture
    batch,
    make,
    refs,  # noqa: F401 - fixture
)

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import hidden_score
from carbon.agent_campaign.graphite.pods import (
    ScriptedPods,
    Step,
    synthetic_outputs,
)
from carbon.battery import exam, seeds
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.pool_store import PoolStore
from carbon.development_session.profile import canonical

V2 = exam.DEVELOPMENT_RULE_V2
TEMPO = V2["per_hotkey"]["window_blocks"]


def knn(neighbours=8):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "knn",
        "parameters": {"neighbours": neighbours},
    }


def locked(target, directory):
    target.lock_path = str(directory / "state.sqlite3.lock")
    target.readonly = False
    return target


def deployment(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
    order=(0, 1, 2, 3),
    finalist=False,
):
    """A rule-v2 validator whose first three imported screening batches (in
    `order`) are its active hidden pool, with one fresh finalist batch when
    `finalist`."""
    tmp_path.mkdir(mode=0o700, exist_ok=True)
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, rule_digest(V2)))
    target = BatteryValidator(
        store=PoolStore(tmp_path / "state.sqlite3", rule=V2),
        backend=backend,
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=False,
        allow_published_cases=True,
    )
    target.start()
    for b in order:
        fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        target.ingest_references(fp, list(refs.values()))
    if finalist:
        fp = target.import_batch(batch(refs, "pfinal", 198), kind="finalist")
        target.ingest_references(fp, list(refs.values()))
    target.open_pool()
    return locked(target, tmp_path)


def pool(target, block=TEMPO + 5, run_id="run-1"):
    return hidden_score.HiddenPool(target, run_id=run_id, clock=lambda: block)


# -- the pool -------------------------------------------------------------------------------


def test_a_rule_that_discloses_hidden_results_is_refused(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    v1 = locked(make(tmp_path, refs, backend), tmp_path)
    with pytest.raises(hidden_score.HiddenPoolRefused) as refused:
        pool(v1)
    assert refused.value.code == "hidden_rule_not_sealed"


def test_only_a_writable_battery_validator_is_served(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    with pytest.raises(hidden_score.HiddenPoolRefused) as refused:
        pool(object())
    assert refused.value.code == "hidden_pool_not_battery"
    target = deployment(tmp_path, refs, backend)
    target.readonly = True
    with pytest.raises(hidden_score.HiddenPoolRefused) as refused:
        pool(target)
    assert refused.value.code == "hidden_pool_readonly"


def test_a_scored_submission_shows_only_the_miner_outcome(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    target = deployment(tmp_path, refs, backend)
    view, operator = pool(target).submit("proposal", knn())
    assert view["state"] == "SCORED"
    assert view["evidence"] == "DEVELOPMENT_HIDDEN_POOL"
    # The validator's own allow-list, sealed: nothing computed from a hidden
    # batch (no screening, nomination or finals).
    assert view["outcome"] == target.outcome(view["outcome"]["submission_id"])
    assert not {"screening", "nominated", "finals"} & set(view["outcome"])
    assert operator["replay"] == "REPRODUCED"
    assert operator["rotation_overdue"] is False
    assert operator["active_batches"] == target.store.pool()["active"]
    assert operator["aggregate"]["n_scored"] > 0


def test_one_hidden_score_per_tempo_and_the_baseline_has_its_own_window(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    hidden = pool(deployment(tmp_path, refs, backend))
    assert hidden.submit("proposal", knn(8))[0]["state"] == "SCORED"
    view, operator = hidden.submit("proposal", knn(9))
    assert view == {
        "schema": hidden_score.VIEW_SCHEMA,
        "evidence": "DEVELOPMENT_HIDDEN_POOL",
        "state": "WINDOW_USED",
        "next_block": 2 * TEMPO,
    }
    assert operator is None
    assert hidden.submit("baseline", knn(9))[0]["state"] == "SCORED"


def test_a_missing_clock_is_infrastructure_never_a_submission(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    target = deployment(tmp_path, refs, backend)
    view, operator = pool(target, block=None).submit("proposal", knn())
    assert (view["state"], view["code"], operator) == (
        "UNAVAILABLE",
        "hidden_clock_unavailable",
        None,
    )
    assert target.store.pending_submissions() == []


def test_the_hidden_deployment_refuses_reserved_and_sealed_roles(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    from carbon.battery.pool_store import StateError

    target = deployment(tmp_path, refs, backend)
    for role in ("graphite-confirmation-v1", "EV5-Confirmation"):
        with pytest.raises(StateError):
            target.prepare_batch(role, kind="screening")


# -- the experiment -------------------------------------------------------------------------


class Ladder:
    def record_failure(self, *args, **kwargs):
        return "failure-1"


def experiment(tmp_path, hidden):
    events = []
    honest = Step(outputs=synthetic_outputs(0.2, scoring=SCORING))
    run = ex.Experiment(
        root=tmp_path / "experiment",
        run_id="run-hidden",
        pods=ScriptedPods(steps=[honest, honest]),
        budget=ex.phase3_budget(grant(), SCORING),
        baseline=knn(8),
        token_committed=lambda: Decimal(0),
        cancelled=lambda: False,
        ladder=Ladder(),
        emit=lambda event_id, body: events.append((event_id, body)),
        repository=REPOSITORY,
        clock=lambda: 1000.0,
        randomness=lambda n: b"\x02" * n,
        construction_level=0,
        scoring=SCORING,
        hidden=hidden,
    )
    return run, events


def propose(run, neighbours=7):
    return run.propose_tool(
        {
            "strategy_json": json.dumps(knn(neighbours)),
            "hypothesis": "fewer neighbours",
            "expected_effect": "lower error",
        },
        "call-1",
    )


def test_without_a_hidden_pool_nothing_changes(tmp_path):
    run, _ = experiment(tmp_path, None)
    feedback = propose(run)
    assert feedback["status"] == "SCORED"
    assert "hidden" not in feedback
    assert run.hidden_records() == []
    assert not list((tmp_path / "experiment").rglob("hidden-operator.json"))


def test_the_agent_feedback_is_identical_whatever_the_hidden_pool_says(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    """The non-leak differential: different hidden pools, one construction."""
    seen, records, staged = [], [], []
    for name, order in (("a", (0, 1, 2, 3)), ("b", (3, 2, 1, 0))):
        target = deployment(tmp_path / ("pool-" + name), refs, backend, order)
        run, events = experiment(tmp_path / ("run-" + name), pool(target))
        seen.append(canonical(propose(run)))
        records.append(run.hidden_records())
        staged.append(repr(run.pods.launched))
        # The operator record never reaches a record, an event or feedback.
        for result in (tmp_path / ("run-" + name)).rglob("result.json"):
            assert b"aggregate" not in result.read_bytes()
        assert "aggregate" not in repr(events)
        # No hidden batch reached a pod.
        for fingerprint in target.store.pool()["active"]:
            assert fingerprint not in staged[-1]
        assert "pscreen-" not in staged[-1]
    assert seen[0] == seen[1]
    assert json.loads(seen[0])["hidden"]["state"] == "SCORED"
    by_kind = [{r["kind"]: r for r in found} for found in records]
    assert set(by_kind[0]) == set(by_kind[1]) == {"baseline", "proposal"}
    # The pools did differ, so the equality above is not vacuous.
    assert by_kind[0]["proposal"]["aggregate"] != by_kind[1]["proposal"]["aggregate"]


def test_a_hidden_pool_serves_only_its_own_challenge_at_level_0(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    from carbon.challenge_validator import scoring as cs

    hidden = pool(deployment(tmp_path / "pool", refs, backend))
    with pytest.raises(ValueError):
        ex.Experiment(
            root=tmp_path / "experiment",
            run_id="run-cooling",
            pods=ScriptedPods(),
            budget=None,
            baseline=knn(8),
            token_committed=lambda: Decimal(0),
            cancelled=lambda: False,
            ladder=Ladder(),
            emit=lambda *_: None,
            clock=lambda: 1000.0,
            scoring=cs.scoring_for("chip-cold-plate"),
            hidden=hidden,
        )


# -- the fresh-case rerun (§6, amended) -----------------------------------------------------


def test_a_winner_is_rescored_once_on_a_fresh_batch_that_is_then_consumed(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    target = deployment(tmp_path, refs, backend, finalist=True)
    hidden = pool(target)
    [fresh] = [
        b["fingerprint"] for b in target.store.batches() if b["kind"] == "finalist"
    ]
    _, operator = hidden.submit("proposal", knn(8))
    sid = operator["submission_id"]
    result = hidden.fresh_rerun(sid)
    assert result["state"] == "SCORED"
    assert result["fingerprint"] == fresh
    assert result["fingerprint"] not in operator["active_batches"]
    assert result["aggregate"]["n_scored"] > 0
    # Single use: consumed, then releasable; never claimable by a final.
    assert target.store.batch(fresh)["state"] == "CONSUMED"
    assert fresh in target.store.releasable()
    # A replay is the same record, and a second winner waits for a new batch.
    assert hidden.fresh_rerun(sid) == result
    _, second = hidden.submit("baseline", knn(9))
    assert hidden.fresh_rerun(second["submission_id"])["state"] == (
        "WAITING_FOR_FRESH_SET"
    )


def test_only_a_screened_submission_can_be_rerun(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    from carbon.battery.pool_store import StateError

    hidden = pool(deployment(tmp_path, refs, backend, finalist=True))
    with pytest.raises(StateError) as refused:
        hidden.fresh_rerun("bsub-" + "0" * 32)
    assert refused.value.code == "rerun_not_scored"


def test_the_rerun_is_operator_evidence_only(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    target = deployment(tmp_path / "pool", refs, backend, finalist=True)
    run, events = experiment(tmp_path / "run", pool(target))
    feedback = propose(run)
    pid = feedback["proposal_id"]
    with pytest.raises(ValueError):
        run.hidden_rerun("p-unknown")
    first = run.hidden_rerun(pid)
    assert first["state"] == "SCORED"
    assert run.hidden_rerun(pid) == first
    assert (tmp_path / "run/experiment/proposals" / pid / "hidden-rerun.json").exists()
    record = (tmp_path / "run/experiment/proposals" / pid / "result.json").read_bytes()
    assert b"rerun" not in record
    assert "rerun" not in repr(events)


# -- overdue pools (the Test Lead's ruling, 2026-10-05) -------------------------------------


def test_a_score_on_an_overdue_pool_is_flagged_with_its_margin(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    # Three screening batches and none prepared: the rotation cannot happen.
    target = deployment(tmp_path, refs, backend, order=(0, 1, 2))
    every = V2["rotation"]["every_blocks"]
    _, on_time = pool(target, block=TEMPO + 5).submit("proposal", knn(8))
    late = TEMPO + 5 + every + 100
    _, overdue = pool(target, block=late).submit("baseline", knn(9))
    assert (on_time["rotation_overdue"], on_time["overdue_margin_blocks"]) == (
        False,
        None,
    )
    assert overdue["pool_version"] == on_time["pool_version"]
    assert (overdue["rotation_overdue"], overdue["overdue_margin_blocks"]) == (
        True,
        100,
    )


def record(pid, version, score, *, overdue=False, eligible=True, margin=None):
    return {
        "proposal_id": pid,
        "kind": "proposal",
        "submission_id": "bsub-" + pid,
        "pool_version": version,
        "aggregate": {"eligible": eligible, "score": score, "important_score": None},
        "rotation_overdue": overdue,
        "overdue_margin_blocks": margin,
        "replay": "REPRODUCED",
    }


def test_overdue_scores_never_enter_the_primary_ranking():
    found = hidden_score.report(
        [
            record("p-a", 1, 0.30),
            record("p-b", 1, 0.10, overdue=True, margin=40),
            record("p-c", 1, 0.20),
            record("p-d", 1, 0.05, eligible=False),
            record("p-e", 2, 0.50),
            {"submission_id": "bsub-x", "replay": "MISMATCH"},
        ]
    )
    primary = found["primary"]["by_pool_version"]
    assert [r["proposal_id"] for r in primary["1"]] == ["p-c", "p-a", "p-d"]
    assert [r["proposal_id"] for r in primary["2"]] == ["p-e"]
    ranked = {r["proposal_id"] for rows in primary.values() for r in rows}
    assert "p-b" not in ranked
    assert found["overdue"]["descriptive_only"] is True
    assert found["overdue"]["count"] == 1
    [late] = found["overdue"]["records"]
    assert (late["proposal_id"], late["overdue_margin_blocks"]) == ("p-b", 40)
    assert found["replay_mismatch"] == ["bsub-x"]
