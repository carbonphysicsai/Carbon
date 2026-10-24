"""E8 (VALIDATOR_E2E_SUBMIT_TO_WEIGHTS_PLAN_20261022): the weight-source code (Workstream
I5) passes its tests with fixtures: a sealed crown is paid on testnet and refused off it.

The chain here is the real one end to end, in process, with no network, spend or real exam
material: a set-level KOTH comparator (`koth_registry.comparator_for_set`) -> the real
`PoolStore` through `BankPromotion.consider_private` (the crown, carrying its pack's
reason) -> `winner_eligibility.lean_promotion` -> the winner ledger's `decide` under a
policy -> `winner_decay.epoch_targets` (the weight). The owner-gated
`testnet_winner_publication` is not touched: this feeds the code it reads.

- (a) a sealed set-level crown produces a weight on testnet (netuid 567);
- (b) the same crown is refused for any other network, and no other netuid is authorized;
- (c) a development, practice or calibration grade never produces a weight;
- (d) no crown while the KOTH rebuild-noise registry is empty (KOTH UNAVAILABLE).
"""

from __future__ import annotations

import json

import pytest
from test_bank_koth_comparator import KEY, _Pairs, _store, body, pair

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator.interface import digest
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, Q12, RewardFailure

CHALLENGE = "electric-motor-magnetics"
POLICY = wd.load_policy("testnet-winner-v2-four-challenge-dev")
T0 = 20 * DAY_MS
NOISE = {"value": 0.05, "measurement_digest": digest("a measured rebuild noise")}


def _registry(tmp_path, noise):
    path = tmp_path / "koth_rebuild_noise.json"
    challenges = {} if noise is None else {CHALLENGE: noise}
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.koth.rebuild-noise-registry.v1",
                "challenges": challenges,
            }
        )
    )
    return path


def _set_comparator(path):
    """A set-level comparator over two batch packs (the weight source reads the set)."""
    packs = [
        {
            "pack_digest": digest(["batch", i]),
            "legs": {"A": {"minimum": 0.4}, "D": {"minimum": 0.4}},
            "value_weight": 0.5,
            "combination": "weighted_arithmetic_mean",
        }
        for i in range(2)
    ]
    return koth_registry.comparator_for_set(CHALLENGE, packs, [{}, {}], path=path)


def _set_body(model, comparator, total):
    """A model's SET-level private evaluation (`bp.SET_BINDING`) for the comparator's exam
    set: the comparator's score-pack digest is the set's."""
    found = body(model, total=total)
    found["evidence"] = {
        **found["evidence"],
        "schema": bp.SET_BINDING,
        "score_compatibility": {"score_pack_digest": comparator["score_pack_digest"]},
    }
    return found


def _crown(tmp_path, monkeypatch, registry, *, sealed, total=0.9):
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = _store(tmp_path, [0.0])
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    comparator = _set_comparator(registry)
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs(store, {"a": pair(_set_body("a", comparator, total), None)}),
    )
    outcome = flow.consider_private("a", KEY, comparator, sealed=sealed)
    return store, outcome


def _weight(store, policy, tmp_path, now_ms=T0):
    """The testnet weight a store's crown earns under ``policy``: ledger -> winner -> targets."""
    promotion = we.lean_promotion(store)
    if promotion is None:
        return wd.epoch_targets(policy, {}, now_ms)
    ledger = we.WinnerLedger(tmp_path / "ledger.jsonl")
    record = ledger.observe(
        policy, CHALLENGE, promotion, {promotion["hotkey"]: "ck"}, now_ms
    )
    winner = we.payable(record, {promotion["hotkey"]})
    winners = {} if winner is None else {CHALLENGE: winner}
    return wd.epoch_targets(policy, winners, now_ms), record


def test_a_sealed_set_level_crown_produces_a_weight_on_testnet_567(
    tmp_path, monkeypatch
):
    assert (POLICY.network, POLICY.netuid) == ("testnet", 567)
    assert wd.network_authorized(POLICY.network, POLICY.netuid, POLICY.authority)
    store, outcome = _crown(
        tmp_path, monkeypatch, _registry(tmp_path, NOISE), sealed=True
    )
    assert outcome["outcome"] == bp.FIRST_INCUMBENT
    assert store.incumbent()["reason"] == bp.SEALED_TESTNET_PROMOTION
    targets, record = _weight(store, POLICY, tmp_path)
    assert (record["eligible"], record["reason"]) == (
        True,
        "first_incumbent_no_baseline",
    )
    share = POLICY.share
    assert targets["winners"] == {"fixture-a": share}
    assert targets["burn"] == Q12 - share


class _OtherNetwork:
    """The same policy on another network."""

    def __init__(self, network):
        self.network, self.digest = network, POLICY.digest

    def baseline(self, challenge):
        return POLICY.baseline(challenge)


@pytest.mark.parametrize("network", ["finney", "mainnet", "devnet", "local"])
def test_the_same_crown_is_refused_off_testnet(tmp_path, monkeypatch, network):
    store, _ = _crown(tmp_path, monkeypatch, _registry(tmp_path, NOISE), sealed=True)
    promotion = we.lean_promotion(store)
    record = we.decide(
        _OtherNetwork(network), CHALLENGE, promotion, None, {"fixture-a": "ck"}, T0
    )
    assert (record["eligible"], record["reason"]) == (
        False,
        "sealed_crown_testnet_only",
    )
    assert we.payable(record, {"fixture-a"}) is None


@pytest.mark.parametrize("netuid", [1, 3, 566, 568, 65535])
def test_no_other_netuid_is_authorized_for_the_testnet_weight_authority(netuid):
    assert not wd.network_authorized("testnet", netuid, wd.AUTHORITY)
    # the testnet-only authority never names finney either
    assert not wd.network_authorized("finney", netuid, wd.AUTHORITY)


def test_a_development_grade_never_produces_a_weight(tmp_path, monkeypatch):
    store, outcome = _crown(
        tmp_path, monkeypatch, _registry(tmp_path, NOISE), sealed=False
    )
    assert (
        outcome["outcome"] == bp.FIRST_INCUMBENT
    )  # the contest is a development crown
    assert store.incumbent()["reason"] == bp.DEVELOPMENT_PROMOTION
    with pytest.raises(RewardFailure, match="PROMOTION_DEVELOPMENT_ONLY"):
        we.lean_promotion(store)  # the reward layer refuses to read it as a source


def test_a_practice_grade_never_reaches_the_crown():
    """A practice pack or definition cannot even build a comparator."""
    practice_pack = {
        "scope": "PUBLIC_PRACTICE_FEEDBACK",
        "pack_digest": digest("practice"),
        "legs": {"A": {"minimum": None}, "D": {"minimum": None}},
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
    }
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator_for_set(CHALLENGE, [practice_pack], [{}])
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator(CHALLENGE, practice_pack, {})


def test_a_calibration_grade_never_touches_the_pool_or_the_reward_layer():
    """The calibration tool and its driver import no pool store, promotion or reward
    module: whatever they grade stays aggregates in a calibration store."""
    import ast
    from pathlib import Path

    from carbon.challenge_validator import calibration_grade

    for name in ("calibration_grade.py", "calibration_grade_run.py"):
        path = Path(calibration_grade.__file__).with_name(name)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name if isinstance(n, ast.Import) else f"{n.module}.{alias.name}"
            for n in ast.walk(tree)
            if isinstance(n, ast.Import | ast.ImportFrom)
            for alias in n.names
        }
        assert not [
            m
            for m in imported
            if any(
                part in m
                for part in (
                    "pool_store",
                    "bank_promotion",
                    "carbon.rewards",
                    "winner_",
                    "koth_registry",
                )
            )
        ], name


def test_no_crown_while_the_rebuild_noise_registry_is_empty(tmp_path, monkeypatch):
    """KOTH UNAVAILABLE: with no registered rebuild noise the contest decides nothing,
    nobody is crowned and the whole share burns."""
    registry = _registry(tmp_path, None)
    assert koth_registry.rebuild_noise(CHALLENGE, path=registry) is None
    store, outcome = _crown(tmp_path, monkeypatch, registry, sealed=True)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == "rebuild_noise_unregistered"
    assert store.incumbent() is None
    assert we.lean_promotion(store) is None
    assert wd.epoch_targets(POLICY, {}, T0) == {"winners": {}, "burn": Q12}


def test_the_first_crown_must_beat_the_baseline_by_the_margin_end_to_end(
    tmp_path, monkeypatch
):
    """OWNER-FIRST-CROWN-BEATS-BASELINE-01, through the whole chain with a comparator
    carrying a non-null baseline_total (here 0.4, from the packs' leg minimums) and the
    registered margin (0.05): a first contender at or below baseline + margin is held back
    (no incumbent, every epoch target burns); one above it is crowned and paid on testnet.
    """
    registry = _registry(tmp_path, NOISE)
    comparator = _set_comparator(registry)
    assert comparator["baseline_total"] == pytest.approx(0.4)
    floor = comparator["baseline_total"] + NOISE["value"]
    # at the floor exactly, and below it: held back
    for total in (floor, floor - 0.01, 0.1):
        store, outcome = _crown(
            tmp_path / f"held-{total:.3f}".replace(".", "_"),
            monkeypatch,
            registry,
            sealed=True,
            total=total,
        )
        assert outcome["outcome"] == bp.NO_WINNER, total
        assert outcome["reason"] == "within_baseline_floor"
        assert store.incumbent() is None
        assert we.lean_promotion(store) is None
        assert wd.epoch_targets(POLICY, {}, T0) == {"winners": {}, "burn": Q12}
    # just above it: crowned, eligible on testnet, and paid
    store, outcome = _crown(
        tmp_path / "crowned", monkeypatch, registry, sealed=True, total=floor + 0.01
    )
    assert outcome["outcome"] == bp.FIRST_INCUMBENT
    assert store.incumbent()["reason"] == bp.SEALED_TESTNET_PROMOTION
    targets, record = _weight(store, POLICY, tmp_path)
    assert record["eligible"] is True
    assert targets["winners"] == {"fixture-a": POLICY.share}
    assert targets["burn"] == Q12 - POLICY.share
