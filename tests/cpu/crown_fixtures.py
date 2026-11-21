"""Shared crown test fixtures (over-broad rules audit S7, crown delete stage 2a): the synthetic grade bodies, pairs,
comparator, pool store, averaged-rule rig and seeded `Repeat` that the crown sweep, queue, official-score, stepwise and
rebuild-evidence tests use. Moved verbatim from `test_crown_average_wiring` so that file can go with the averaging
machinery while these stay. A plain module (no tests). Synthetic values only.
"""

from __future__ import annotations

import json

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator.interface import digest

CHALLENGE = "electric-motor-magnetics"
PACK = digest("score pack")
KEY = digest("evaluation context")
CROWN_KEY = bytes(range(64))
# The old rule: the registered rebuild noise. The new margin_N at N = 10 is far inside it.
NOISE = {"value": 0.03, "measurement_digest": digest("noise")}
MARGIN = 0.0035


def _body(model, total, status=bp.SCORED):
    return {
        "submission_id": model,
        "evidence": {
            "schema": bp.PAIRED_BINDING,
            "challenge": CHALLENGE,
            "score_compatibility": {"score_pack_digest": PACK},
            "entry_id": digest(["entry", model]),
            "model_p": {"score_status": status, "total_score": total},
        },
    }


def _pair(candidate, incumbent):
    return {
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "evaluation_key": KEY,
        "expected_incumbent": None if incumbent is None else incumbent["submission_id"],
        "candidate": candidate,
        "incumbent": incumbent,
    }


def _comparator(noise=NOISE):
    return {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": CHALLENGE,
        "score_pack_digest": PACK,
        "rebuild_noise": noise,
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": [digest("baseline run")],
        "baseline_total": 0.5,
    }


class _Pairs:
    def __init__(self, pairs):
        self.pairs = pairs

    def __call__(self, submission_id, key, *, registered_source_receipt_sha256):
        return self.pairs[submission_id]


def _store(tmp_path):
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 0.0)
    for model in ("a", "b", "c", "d"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge=CHALLENGE,
            strategy={},
            binding={"challenge": {"id": CHALLENGE}},
        )
    return store


def _active(tmp_path, margin=MARGIN, n=10):
    path = tmp_path / "crown_average.json"
    margins = (
        {}
        if margin is None
        else {
            CHALLENGE: {
                "value": margin,
                "n": n,
                "measurement_digest": digest("margin"),
            }
        }
    )
    path.write_text(
        json.dumps(
            {
                "schema": ca.SCHEMA,
                "rule_version": "crown-average-v1",
                "n": n,
                "challenge_n": {},
                "seed_range": 2147483647,
                "margins": margins,
            }
        )
    )
    return ca.Active(ca.load_rule(path), CROWN_KEY)


class Repeat:
    """A `repeat` carrying a seeded rebuild: every seed gives ``totals[next]`` (or one status)."""

    entry_id = digest("entry")

    def __init__(self, model, totals, statuses=None):
        self.model, self.totals, self.statuses = model, list(totals), statuses or {}
        self.asked = []
        self.order = {}

    def __call__(
        self, submission_id
    ):  # the old second grade: must never run on the averaged path
        raise AssertionError("the single-grade repeat ran on the averaged path")

    def rebuild_at(self, seed):
        self.asked.append(seed)
        index = self.order.setdefault(seed, len(self.order))
        return _body(
            self.model, self.totals[index], self.statuses.get(index, bp.SCORED)
        )


def _flow(tmp_path, monkeypatch, pairs):
    store = _store(tmp_path)
    monkeypatch.setattr(store, "private_evaluation_pair", _Pairs(pairs))
    return store, bp.BankPromotion(
        store, registered_source_receipt_sha256=digest("pin")
    )
