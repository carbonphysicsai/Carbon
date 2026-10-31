"""the crown multi-rebuild average ruling (lead-records a322dea4) slice 2: the rule wired into `BankPromotion.consider_private`, OFF by default.

Claims: with no rule installed nothing differs from before; installed, the screening grade meets the king's MEAN at
margin_N and only a crown-changing win spends the N rebuilds (a win inside the margin spends none); the N-rebuild mean
decides in place of the repeat; one inadmissible seed is no takeover; a missing seeded rebuild, an unregistered margin
or an unreproducible record moves no crown; the seeds, totals and mean are filed privately and never returned; the
receiver turns the rule on only from its own configuration."""

from __future__ import annotations

import json
import os
from copy import deepcopy

import pytest

from carbon.battery.pool_store import PoolStore, StateError
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


def test_the_rule_is_off_by_default():
    assert ca.ACTIVE is None


def test_with_no_rule_installed_the_old_single_grade_rule_decides(
    tmp_path, monkeypatch
):
    # 0.72 does not beat 0.7 + the old noise 0.03; the rebuilds are never asked
    a, b = _body("a", 0.7), _body("b", 0.72)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None), "b": _pair(b, a)})
    again = lambda submission_id: store.private_evaluation_pair(
        submission_id, KEY, registered_source_receipt_sha256=digest("pin")
    )["candidate"]
    assert (
        flow.consider_private("a", KEY, _comparator(), repeat=again)["outcome"]
        == bp.FIRST_INCUMBENT
    )
    assert (
        flow.consider_private("b", KEY, _comparator(), repeat=again)["outcome"]
        == bp.INCUMBENT_KEEPS
    )


def test_a_first_crown_is_the_mean_beating_the_baseline_floor_by_the_margin(
    tmp_path, monkeypatch
):
    a = _body("a", 0.7)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None)})
    repeat = Repeat("a", [0.7] * 10)
    outcome = flow.consider_private(
        "a", KEY, _comparator(), repeat=repeat, average=_active(tmp_path)
    )
    assert (
        outcome["outcome"] == bp.FIRST_INCUMBENT
        and outcome["reason"] == ca.FIRST_BEATS_BASELINE
    )
    assert store.incumbent()["model_id"] == "a"
    assert len(repeat.asked) == 10 + 1  # N rebuilds plus the host-fault second build
    assert store.crown_mean("a") == pytest.approx(0.7)


def test_the_screening_grade_meets_the_kings_mean_at_margin_n_and_a_small_win_takes_the_crown(
    tmp_path, monkeypatch
):
    a, b = _body("a", 0.70), _body("b", 0.705)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None), "b": _pair(b, a)})
    average = _active(tmp_path)
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.70] * 10), average=average
    )
    # +0.005 is inside the OLD margin (0.03) but beyond margin_N (0.0035): now a takeover
    repeat = Repeat("b", [0.705] * 10)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=average
    )
    assert (outcome["outcome"], outcome["reason"]) == (bp.CHALLENGER, ca.MEAN_EXCEEDS)
    assert store.incumbent()["model_id"] == "b"
    assert store.crown_mean("b") == pytest.approx(0.705)


def test_the_king_is_compared_by_its_stored_mean_not_its_single_grade(
    tmp_path, monkeypatch
):
    # a's single grade was lucky (0.80) but its mean is 0.70: a challenger at 0.71 beats the MEAN by more than margin_N
    a, b = _body("a", 0.80), _body("b", 0.71)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None), "b": _pair(b, a)})
    average = _active(tmp_path)
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.70] * 10), average=average
    )
    assert store.crown_mean("a") == pytest.approx(0.70)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=Repeat("b", [0.71] * 10), average=average
    )
    assert outcome["outcome"] == bp.CHALLENGER


def test_a_screening_win_inside_the_margin_spends_no_rebuilds(tmp_path, monkeypatch):
    a, b = _body("a", 0.70), _body("b", 0.7020)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None), "b": _pair(b, a)})
    average = _active(tmp_path)
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.70] * 10), average=average
    )
    repeat = Repeat("b", [0.99] * 10)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=average
    )
    assert outcome["outcome"] == bp.INCUMBENT_KEEPS and repeat.asked == []
    assert store.incumbent()["model_id"] == "a"


def test_a_good_screening_grade_with_one_inadmissible_seed_is_no_takeover(
    tmp_path, monkeypatch
):
    a, b = _body("a", 0.70), _body("b", 0.95)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None), "b": _pair(b, a)})
    average = _active(tmp_path)
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.70] * 10), average=average
    )
    repeat = Repeat("b", [0.95] * 10, statuses={6: "MANDATORY_GATE_FAILED"})
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=average
    )
    assert (outcome["outcome"], outcome["reason"]) == (bp.INCUMBENT_KEEPS, ca.UNSTABLE)
    assert store.incumbent()["model_id"] == "a" and store.crown_mean("b") is None


def test_a_missing_seeded_rebuild_an_unregistered_margin_or_a_failed_rebuild_moves_no_crown(
    tmp_path, monkeypatch
):
    a = _body("a", 0.70)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None)})

    class NoRebuild:
        def __call__(self, submission_id):
            raise AssertionError

    none = flow.consider_private(
        "a", KEY, _comparator(), repeat=NoRebuild(), average=_active(tmp_path)
    )
    assert (none["outcome"], none["reason"]) == (bp.UNAVAILABLE, ca.REBUILD_UNAVAILABLE)
    unregistered = flow.consider_private(
        "a",
        KEY,
        _comparator(),
        repeat=Repeat("a", [0.7] * 10),
        average=_active(tmp_path, margin=None),
    )
    assert (unregistered["outcome"], unregistered["reason"]) == (
        bp.UNAVAILABLE,
        ca.MARGIN_UNREGISTERED,
    )
    no_noise = flow.consider_private(
        "a",
        KEY,
        _comparator(noise=None),
        repeat=Repeat("a", [0.7] * 10),
        average=_active(tmp_path),
    )
    assert no_noise["outcome"] == bp.UNAVAILABLE

    class Broken(Repeat):
        def rebuild_at(self, seed):
            raise OSError("construction lane down")

    broken = flow.consider_private(
        "a", KEY, _comparator(), repeat=Broken("a", []), average=_active(tmp_path)
    )
    assert (broken["outcome"], broken["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_UNAVAILABLE,
    )
    assert store.incumbent() is None  # nothing moved in any of them


def test_the_seeds_totals_and_mean_are_filed_privately_and_never_returned(
    tmp_path, monkeypatch
):
    a = _body("a", 0.70)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None)})
    repeat = Repeat("a", [0.70] * 10)
    outcome = flow.consider_private(
        "a", KEY, _comparator(), repeat=repeat, average=_active(tmp_path)
    )
    assert "private" not in outcome
    text = json.dumps(outcome, default=str)
    assert not any(str(seed) in text for seed in repeat.asked)
    with store.db() as db:
        rows = db.execute(
            "SELECT body FROM operations WHERE kind='crown_average.v1'"
        ).fetchall()
    record = json.loads(rows[0][0])["private"]
    assert (
        record["seeds"] == list(dict.fromkeys(repeat.asked))[:10]
        and len(record["totals"]) == 10
    )


def test_a_decision_that_rebuilds_differently_is_failed_infra_and_moves_nothing(
    tmp_path, monkeypatch
):
    a = _body("a", 0.70)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None)})
    average = _active(tmp_path)
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.70] * 10), average=average
    )
    store.vacate_incumbent("a", "test")
    # the same decision (same seeds) now rebuilds to different totals: the stored record must not be rewritten
    outcome = flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.71] * 10), average=average
    )
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.FAILED_INFRA,
        "crown_average_record_changed",
    )
    assert store.incumbent() is None
    assert store.crown_mean("a") == pytest.approx(0.70)


def test_the_store_records_are_write_once_and_the_mean_is_the_latest_complete_one(
    tmp_path,
):
    store = _store(tmp_path)
    assert store.crown_mean("a") is None
    store.record_crown_average("a", KEY, {"mean": 0.5, "seeds": [1, 2]})
    store.record_crown_average("a", KEY, {"mean": 0.5, "seeds": [1, 2]})  # idempotent
    with pytest.raises(StateError, match="crown_average_changed"):
        store.record_crown_average("a", KEY, {"mean": 0.6, "seeds": [1, 2]})
    other = digest("another key")
    store.record_crown_average(
        "a", other, {"seeds": [3], "statuses": ["MANDATORY_GATE_FAILED"]}
    )
    assert store.crown_mean("a") == 0.5  # an incomplete decision carries no mean
    store.record_crown_average("a", digest("third"), {"mean": 0.7, "seeds": [4]})
    assert store.crown_mean("a") == 0.7
    with pytest.raises(StateError, match="crown_average_invalid"):
        store.record_crown_average("a", "not-a-digest", {})


# --- the receiver turns it on from its own configuration -------------------------------------------------------


@pytest.fixture
def restore_active(monkeypatch):
    monkeypatch.setattr(ca, "ACTIVE", None)


def test_install_is_off_without_a_section_and_refuses_any_other_shape(restore_active):
    ca.install({})
    assert ca.ACTIVE is None
    for bad in (
        {"crown_average": []},
        {"crown_average": {}},
        {"crown_average": {"key_file": "x", "n": 1}},
    ):
        with pytest.raises(ca.CrownAverageInvalid):
            ca.install(bad)
    assert ca.ACTIVE is None


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only modes")
def test_install_reads_the_private_key_file_and_never_shows_it(
    tmp_path, restore_active
):
    key = tmp_path / "k"
    key.write_bytes(CROWN_KEY)
    key.chmod(0o600)
    ca.install({"crown_average": {"key_file": str(key)}})
    assert isinstance(ca.ACTIVE, ca.Active)
    assert repr(ca.ACTIVE) == "Active(<redacted>)"
    ca.install({})
    assert ca.ACTIVE is None


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only modes")
def test_the_receiver_configuration_validates_the_section(tmp_path, monkeypatch):
    from carbon.challenge_validator import direct_receiver as receiver

    key = tmp_path / "k"
    key.write_bytes(CROWN_KEY)
    key.chmod(0o600)
    base = {
        "schema": receiver.SCHEMA,
        "root": str(tmp_path / "receiver"),
        "runner_profile": str(tmp_path / "profile.json"),
        "host": "127.0.0.1",
        "port": 8767,
        "receiver_hotkey": "5" + "F" * 47,
        "lifetime_seconds": 30,
        "measure_query": True,
    }
    for section, ok in (
        ({"key_file": str(key)}, True),
        ({"key_file": "relative"}, False),
        ({"key_file": str(key), "n": 5}, False),
        ("path", False),
    ):
        cfg = {**base, "crown_average": section}
        monkeypatch.setattr(receiver, "private_json", lambda _, cfg=cfg: deepcopy(cfg))
        if ok:
            assert receiver.load_config(tmp_path / "c.json")["crown_average"] == section
        else:
            with pytest.raises((ValueError, ca.CrownAverageInvalid)):
                receiver.load_config(tmp_path / "c.json")


def test_the_construction_lane_has_no_seeded_rebuild_yet_so_the_rule_stays_unavailable():
    from carbon.challenge_validator import lean_recipe_retention as retention

    repeat = retention._repeat_of(None, "origin", digest("entry"))
    with pytest.raises(
        retention.RetentionUnavailable, match="seeded_rebuild_unavailable"
    ):
        repeat.rebuild_at(12345)


def test_a_king_never_measured_by_the_average_keeps_crowns_paused(
    tmp_path, monkeypatch
):
    # a was crowned by the old single-grade rule: no mean exists, so nobody is compared against a "mean" of one grade
    a, b = _body("a", 0.70), _body("b", 0.95)
    store, flow = _flow(tmp_path, monkeypatch, {"b": _pair(b, a)})
    store.set_incumbent("a", bp.DEVELOPMENT_PROMOTION)
    repeat = Repeat("b", [0.95] * 10)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=_active(tmp_path)
    )
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.UNAVAILABLE,
        ca.KING_UNMEASURED,
    )
    assert repeat.asked == [] and store.incumbent()["model_id"] == "a"


def test_a_resubmission_is_a_new_submission_with_fresh_seeds():
    first = ca.derive_seeds(CROWN_KEY, CHALLENGE, "submission-1", 10, 2147483647)
    again = ca.derive_seeds(CROWN_KEY, CHALLENGE, "submission-2", 10, 2147483647)
    assert not set(first) & set(
        again
    )  # nothing to tune to: each try is a new submission, new seeds


def test_every_triggered_decision_is_logged_for_the_per_day_count(
    tmp_path, monkeypatch
):
    clock = [100.0]
    a, b = _body("a", 0.70), _body("b", 0.72)
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: clock[0])
    for model in ("a", "b"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge=CHALLENGE,
            strategy={},
            binding={"challenge": {"id": CHALLENGE}},
        )
    monkeypatch.setattr(
        store,
        "private_evaluation_pair",
        _Pairs({"a": _pair(a, None), "b": _pair(b, a)}),
    )
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    average = _active(tmp_path)
    assert store.crown_triggers_since(0) == 0
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [0.70] * 10), average=average
    )
    clock[0] = 100.0 + 86400
    flow.consider_private(
        "b", KEY, _comparator(), repeat=Repeat("b", [0.72] * 10), average=average
    )
    flow.consider_private(
        "b", KEY, _comparator(), repeat=Repeat("b", [0.72] * 10), average=average
    )  # same trigger
    assert store.crown_triggers_since(0) == 2
    assert (
        store.crown_triggers_since(100.0 + 3600) == 1
    )  # the per-day count: only the later one
