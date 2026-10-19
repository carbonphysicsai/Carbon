"""King of the hill on one shared bank key, DEVELOPMENT only.

The pairs are synthetic fixtures shaped like `PoolStore.private_evaluation_pair`
output; no model, solver or reference runs. Rebuild-noise values here are fixtures
under a DEVELOPMENT comparator that the reward layer never pays.
"""

from copy import deepcopy

import pytest

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator.interface import digest
from carbon.rewards.core import DAY_MS, Q12
from carbon.rewards.winner_decay import Winner, WinnerPolicy, epoch_targets

PACK = digest("score pack")
KEY = digest("evaluation context")


def body(model, status=bp.SCORED, total=1.0):
    return {
        "submission_id": model,
        "evidence": {
            "schema": bp.PAIRED_BINDING,
            "challenge": "electric-motor-magnetics",
            "score_compatibility": {"score_pack_digest": PACK},
            "model_p": {"score_status": status, "total_score": total},
        },
    }


def pair(candidate, incumbent):
    return {
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "evaluation_key": KEY,
        "expected_incumbent": None if incumbent is None else incumbent["submission_id"],
        "candidate": candidate,
        "incumbent": incumbent,
    }


def comparator(noise=None, **changes):
    rule = {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": "electric-motor-magnetics",
        "score_pack_digest": PACK,
        "rebuild_noise": noise,
        "ties": "incumbent_keeps",
    }
    rule.update(changes)
    return rule


NOISE = {"value": 0.1, "measurement_digest": digest("rebuild noise record")}
ZERO = {"value": 0, "measurement_digest": digest("rebuild noise record")}


@pytest.mark.parametrize(
    ("candidate", "incumbent", "noise", "expected"),
    [
        (body("c"), None, None, (bp.FIRST_INCUMBENT, "first_scored_contender")),
        (
            body("c", "FAILED_INFRA"),
            None,
            NOISE,
            (bp.NO_WINNER, "candidate_not_scored"),
        ),
        (
            body("c", total=2.0),
            body("k"),
            NOISE,
            (bp.CHALLENGER, "exceeds_incumbent_beyond_rebuild_noise"),
        ),
        (
            body("c", total=1.1),
            body("k"),
            NOISE,
            (bp.INCUMBENT_KEEPS, "within_rebuild_noise_or_tie"),
        ),
        (
            body("c", total=1.0),
            body("k"),
            ZERO,
            (bp.INCUMBENT_KEEPS, "within_rebuild_noise_or_tie"),
        ),
        (
            body("c", total=1.01),
            body("k"),
            ZERO,
            (bp.CHALLENGER, "exceeds_incumbent_beyond_rebuild_noise"),
        ),
        (
            body("c", total=9.0),
            body("k"),
            None,
            (bp.UNAVAILABLE, "rebuild_noise_unregistered"),
        ),
        (
            body("c", "MANDATORY_GATE_FAILED"),
            body("k"),
            NOISE,
            (bp.INCUMBENT_KEEPS, "candidate_not_scored"),
        ),
        (
            body("c", total=9.0),
            body("k", "FAILED_INFRA"),
            NOISE,
            (bp.UNAVAILABLE, "incumbent_evidence_unavailable"),
        ),
        (
            body("c", total=9.0),
            body("k", "MANDATORY_GATE_FAILED"),
            NOISE,
            (bp.UNAVAILABLE, "incumbent_not_scored"),
        ),
    ],
)
def test_comparator_outcomes(candidate, incumbent, noise, expected):
    outcome = bp.compare_private_pair(pair(candidate, incumbent), comparator(noise))
    assert (outcome["outcome"], outcome["reason"]) == expected
    assert outcome["evaluation_key"] == KEY


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"scope": "REGISTERED"}, "comparator_scope_unadopted"),
        ({"ties": "candidate_wins"}, "comparator_invalid"),
        (
            {"noise": {"value": -1, "measurement_digest": digest("x")}},
            "comparator_invalid",
        ),
        ({"noise": {"value": 0.1}}, "comparator_invalid"),
        ({"challenge": "chip-cold-plate"}, "comparator_not_for_this_evaluation"),
        (
            {"score_pack_digest": digest("other pack")},
            "comparator_not_for_this_evaluation",
        ),
    ],
)
def test_comparator_refuses_unadopted_or_mismatched_rules(changes, error):
    with pytest.raises(StateError, match=error):
        bp.compare_private_pair(
            pair(body("c"), body("k")), comparator(**{"noise": NOISE, **changes})
        )


def test_only_paired_dual_evidence_is_compared():
    old = body("c")
    old["evidence"]["schema"] = "carbon.scoring.private-evaluation-binding.v3"
    with pytest.raises(StateError, match="comparator_requires_paired_dual"):
        bp.compare_private_pair(pair(old, body("k")), comparator(NOISE))


class _Pairs:
    """Stands in for the store's pairing only; the incumbent writes are real."""

    def __init__(self, store, pairs):
        self.store, self.pairs = store, pairs

    def __call__(self, submission_id, key, *, registered_source_receipt_sha256):
        return self.pairs[submission_id]


def _store(tmp_path, clock):
    store = PoolStore(tmp_path / "koth.sqlite", clock=lambda: clock[0])
    for model in ("a", "b", "c"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge="electric-motor-magnetics",
            strategy={},
            binding={"challenge": {"id": "electric-motor-magnetics"}},
        )
    return store


def test_scored_results_drive_a_development_king_and_its_halving(tmp_path, monkeypatch):
    """Scored bank results → development promotions → the 1/N, 24 h then
    halving targets. Four Challenges in a test policy; only Motor has a king."""
    clock = [0.0]
    store = _store(tmp_path, clock)
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    a, b, c = body("a", total=1.0), body("b", total=1.05), body("c", total=1.5)
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs(store, {"a": pair(a, None), "b": pair(b, a), "c": pair(c, a)}),
    )
    rule = comparator(NOISE)

    assert flow.consider_private("a", KEY, rule)["outcome"] == bp.FIRST_INCUMBENT
    assert store.incumbent() == {"model_id": "a", "reason": bp.DEVELOPMENT_PROMOTION}
    crowned_ms = 0
    assert flow.consider_private("b", KEY, rule)["outcome"] == bp.INCUMBENT_KEEPS
    assert store.incumbent()["model_id"] == "a"
    clock[0] = 3 * DAY_MS / 1000
    assert flow.consider_private("c", KEY, rule)["outcome"] == bp.CHALLENGER
    assert store.incumbent()["model_id"] == "c"

    policy = WinnerPolicy(
        version="koth-four-challenge-development-fixture",
        digest=digest("fixture policy"),
        network="testnet",
        netuid=567,
        challenges=("electric-motor-magnetics", "chip-cold-plate", "f02", "f08"),
        self_improvement_factor=None,
        burn_uid=0,
        cadence_blocks=360,
    )
    share = Q12 // 4
    for days, fraction in ((0, 1), (1, 2), (2, 4)):
        targets = epoch_targets(
            policy,
            {"electric-motor-magnetics": Winner("fixture-a", crowned_ms)},
            crowned_ms + days * DAY_MS,
        )
        assert targets["winners"] == {"fixture-a": share // fraction}
        assert targets["burn"] == Q12 - share // fraction
    # The new king's 24 hours start at its own promotion, full share again.
    reign = 3 * DAY_MS
    assert epoch_targets(
        policy, {"electric-motor-magnetics": Winner("fixture-c", reign)}, reign
    )["winners"] == {"fixture-c": share}


def test_a_lost_race_does_not_move_the_incumbent(tmp_path, monkeypatch):
    clock = [0.0]
    store = _store(tmp_path, clock)
    store.set_incumbent("a", "fixture")
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    candidate = body("b", total=9.0)
    moved = pair(candidate, body("a"))
    moved["expected_incumbent"] = "c"  # the incumbent changed after pairing
    monkeypatch.setattr(store, "private_evaluation_pair", _Pairs(store, {"b": moved}))
    with pytest.raises(StateError, match="incumbent_moved"):
        flow.consider_private("b", KEY, comparator(NOISE))
    assert store.incumbent()["model_id"] == "a"
    unchanged = deepcopy(store.incumbent())
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs(store, {"b": pair(candidate, body("a"))}),
    )
    assert (
        flow.consider_private("b", KEY, comparator(None))["outcome"] == bp.UNAVAILABLE
    )
    assert store.incumbent() == unchanged
