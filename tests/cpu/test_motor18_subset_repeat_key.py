"""Validator-2B Q3 (a): a Motor 1.8 grade under the new producer digest shares the old-digest king's evaluation key
(bank_promotion.private_evaluation_key / carry_identity), through the R-1 successor row only: one hop, forward only, the
key alone (A-1..A-4; docs/records/2026-11-15-motor18-subset-repeat.json). Synthetic evidence on the real Motor 1.5
pool fixture's binding, relabelled; the producer digests are the real ones.
"""

# ruff: noqa: F811 (the imported case fixture is received by tests)
from __future__ import annotations

import copy
import json

import pytest
from test_motor18_subset_repeat import (
    MOTOR,
    OLD_MOTOR18,
    OTHER_DIGESTS,
    _motor18,
    _registry,
)
from test_pool_dual_e2e import _bind, _produce, case  # noqa: F401

from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import producer_successor
from carbon.scoring.engine import ScoreEngine


@pytest.fixture
def bound(case):
    prepared_source, measured = _produce(case)
    scoring = ScoreEngine.score_dual_benchmark_v4(
        json.loads(measured.raw)["benchmark"], case["score_pack"]
    )
    return _bind(case, prepared_source, measured, scoring)


def _as(evidence, version, digest):
    return {
        **copy.deepcopy(evidence),
        "challenge_version": version,
        "producer_digest": digest,
    }


def _keys(evidence):
    from carbon.challenge_validator.bank_promotion import (
        carry_identity,
        private_evaluation_key,
    )

    return private_evaluation_key(evidence), carry_identity(evidence)


def test_q3_a_new_digest_challenger_meets_the_old_digest_king(bound):
    new = physical.producer_digest(_motor18())
    king, challenger = _as(bound, "1.8", OLD_MOTOR18), _as(bound, "1.8", new)
    stored = copy.deepcopy(challenger)
    assert _keys(king) == _keys(challenger)
    # (iv) only the KEY maps: the evidence keeps its own digest
    assert challenger == stored and challenger["producer_digest"] == new
    assert king["producer_digest"] == OLD_MOTOR18


def test_q3_a_contender_finds_the_king_with_no_regrade(bound, tmp_path):
    """(i) through the store: a contender graded under the new digest is contended against the king graded under the old
    one (no INCUMBENT_REGRADE_REQUIRED)."""
    from carbon.challenge_validator.bank_promotion import private_evaluation_key

    new = physical.producer_digest(_motor18())
    store = {private_evaluation_key(_as(bound, "1.8", OLD_MOTOR18)): "king"}
    assert store.get(private_evaluation_key(_as(bound, "1.8", new))) == "king"


def test_q3_a_every_other_case_keys_differently(bound, tmp_path, monkeypatch):
    """(ii) fail closed: a wrong digest, another version, the reversed pair, a 2-hop chain and a malformed or missing
    row each give a DIFFERENT key."""
    new = physical.producer_digest(_motor18())
    old2 = "sha256:" + "d" * 64
    king = _keys(_as(bound, "1.8", OLD_MOTOR18))
    assert _keys(_as(bound, "1.8", "sha256:" + "e" * 64)) != king
    # another version (no row maps it), even carrying the new digest
    assert _keys(_as(bound, "1.5", new)) != _keys(_as(bound, "1.5", OLD_MOTOR18))
    # the pinned digest never maps forward again, and a row is never read backwards
    from carbon.challenge_validator import bank_promotion

    assert bank_promotion._key_producer(_as(bound, "1.8", OLD_MOTOR18)) == OLD_MOTOR18
    reversed_row = {"pack_producer_digest": new, "producer_digest": OLD_MOTOR18}
    for rows in (
        {f"{MOTOR} 1.8": reversed_row},
        # a 2-hop chain: a second row old2 -> old
        {
            f"{MOTOR} 1.8": {
                "pack_producer_digest": OLD_MOTOR18,
                "producer_digest": new,
            },
            f"{MOTOR} 1.7": {
                "pack_producer_digest": old2,
                "producer_digest": OLD_MOTOR18,
            },
        },
        {f"{MOTOR} 1.8": {"pack_producer_digest": OLD_MOTOR18}},
        {},
    ):
        monkeypatch.setattr(producer_successor, "REGISTRY", _registry(tmp_path, rows))
        assert _keys(_as(bound, "1.8", new)) != _keys(_as(bound, "1.8", OLD_MOTOR18))
        assert _keys(_as(bound, "1.8", old2)) != _keys(_as(bound, "1.8", OLD_MOTOR18))
    monkeypatch.setattr(producer_successor, "REGISTRY", tmp_path / "absent.json")
    assert _keys(_as(bound, "1.8", new)) != king


def test_q3_a_a_row_whose_digest_is_not_the_running_producer_does_not_map(
    bound, monkeypatch
):
    new = physical.producer_digest(_motor18())
    from carbon.challenge_validator import bank_promotion

    monkeypatch.setattr(
        bank_promotion, "_RUNNING_PRODUCER", {(MOTOR, "1.8"): "sha256:" + "c" * 64}
    )
    assert _keys(_as(bound, "1.8", new)) != _keys(_as(bound, "1.8", OLD_MOTOR18))


def test_q3_a_every_other_adapters_key_is_unchanged(bound):
    """(iii) no other adapter's digest maps, and the fixture's own (Motor 1.5) key is the exact-digest key."""
    import importlib

    from carbon.challenge_validator import bank_promotion

    for name, digest in OTHER_DIGESTS.items():
        module = importlib.import_module("carbon.scoring." + name)
        challenge = getattr(module, "CHALLENGE", None)
        for version in {getattr(module, "VERSION", None), "1.8", "1.5"}:
            assert (
                bank_promotion._key_producer(
                    {
                        "challenge": challenge,
                        "challenge_version": version,
                        "producer_digest": digest,
                    }
                )
                == digest
            )
    exact = bank_promotion._key_producer
    try:
        bank_promotion._key_producer = lambda evidence: evidence["producer_digest"]
        expected = _keys(bound)
    finally:
        bank_promotion._key_producer = exact
    assert _keys(bound) == expected
