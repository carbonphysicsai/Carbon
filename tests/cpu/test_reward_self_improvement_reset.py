"""OWNER-KING-SELF-IMPROVEMENT-RESET-01: under policy testnet-winner-v5-launch a crown
holder that beats its OWN repeat-confirmed crown restarts its decay clock.

Claims: v5 is v4 plus the closed factor ``full_reset`` (registered by digest; v4 is
unchanged and still keeps the old clock); the reset applies to the same miner (hotkey or
coldkey) only, to a bank promotion only, and only with the promotion's repeat mark (a
promotion without it is refused and the ledger is left as it was); what qualifies is the
existing KOTH rule (a win within the rebuild noise is no promotion, so no reset); another
miner's takeover resets as before under both versions; past ledger records are never
rewritten; an unknown factor does not load. In process: no chain, spend or exam material.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator.interface import digest
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, Q12, RewardFailure

V4 = wd.load_policy("testnet-winner-v4-launch")
V5 = wd.load_policy("testnet-winner-v5-launch")
CHALLENGE = V5.challenges[0]
T0 = 20 * DAY_MS
LATER = T0 + 2 * DAY_MS
DIRECTORY = Path(wd.POLICY_DIR)


def first(model, hotkey):
    return {"model_id": model, "hotkey": hotkey, "previous": None, "kind": we.FIRST}


def bank(model, hotkey, previous, previous_hotkey, *, repeat=True):
    promotion = {
        "model_id": model,
        "hotkey": hotkey,
        "previous": previous,
        "previous_hotkey": previous_hotkey,
        "kind": we.BANK,
    }
    if repeat is not None:
        promotion["repeat_verified"] = repeat
    return promotion


def ledger(tmp_path):
    return we.WinnerLedger(tmp_path / "winners.jsonl")


def crowned(tmp_path, policy, coldkeys=None):
    book = ledger(tmp_path)
    book.observe(
        policy, CHALLENGE, first("m1", "hk-a"), coldkeys or {"hk-a": "ck-a"}, T0
    )
    return book


# --- the policy ------------------------------------------------------------------------


def test_v5_is_v4_plus_the_closed_full_reset_factor():
    assert V5.self_improvement_factor == wd.FULL_RESET == "full_reset"
    assert V4.self_improvement_factor is None
    v4 = json.loads((DIRECTORY / "testnet-winner-v4-launch.json").read_text())
    v5 = json.loads((DIRECTORY / "testnet-winner-v5-launch.json").read_text())
    differing = {k for k in v5 if v5[k] != v4[k]}
    assert differing == {"version", "self_improvement_factor", "membership_note"}
    assert V5.challenges == V4.challenges and V5.baselines == V4.baselines
    assert V5.digest != V4.digest


def test_the_registry_covers_v5_and_v4_stays_byte_identical():
    registry = json.loads((DIRECTORY / "registry.json").read_text())
    document = json.loads((DIRECTORY / "testnet-winner-v5-launch.json").read_text())
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    assert registry["versions"]["testnet-winner-v5-launch"] == (
        "sha256:" + hashlib.sha256(canonical).hexdigest()
    )
    assert registry["versions"]["testnet-winner-v4-launch"] == (
        "sha256:b26fed6c50229413223b3c785bc0439b66094e60b9af1afad2dce406fe41c325"
    )
    # v5 is not the current policy: it activates only when the loop is switched to it
    assert registry["current"] == "testnet-winner-v1"


@pytest.mark.parametrize("factor", ["half_reset", "FULL_RESET", 0.5, 1, True, [], {}])
def test_an_unknown_factor_does_not_load(tmp_path, factor):
    directory = tmp_path / "policies"
    shutil.copytree(DIRECTORY, directory)
    path = directory / "testnet-winner-v5-launch.json"
    document = json.loads(path.read_text())
    document["self_improvement_factor"] = factor
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    registry = json.loads((directory / "registry.json").read_text())
    registry["versions"]["testnet-winner-v5-launch"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    (directory / "registry.json").write_text(json.dumps(registry))
    with pytest.raises(RewardFailure, match="WEIGHT_POLICY_MALFORMED"):
        wd.load_policy("testnet-winner-v5-launch", directory)


def test_an_edited_v5_document_is_altered(tmp_path):
    directory = tmp_path / "policies"
    shutil.copytree(DIRECTORY, directory)
    path = directory / "testnet-winner-v5-launch.json"
    document = json.loads(path.read_text())
    document["membership_note"] += " "
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    with pytest.raises(RewardFailure, match="WEIGHT_POLICY_ALTERED"):
        wd.load_policy("testnet-winner-v5-launch", directory)


# --- the reset -------------------------------------------------------------------------


def test_a_repeat_verified_self_beat_under_v5_restarts_the_clock(tmp_path):
    book = crowned(tmp_path, V5)
    record = book.observe(
        V5, CHALLENGE, bank("m2", "hk-a", "m1", "hk-a"), {"hk-a": "ck-a"}, LATER
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "self_improvement_reset",
        LATER,
    )
    paid = wd.epoch_targets(V5, {CHALLENGE: we.payable(record, {"hk-a"})}, LATER)
    assert paid["winners"] == {"hk-a": V5.share}  # a full first day again
    assert V5.share == Q12 // len(V5.challenges)


def test_the_same_coldkey_on_another_hotkey_is_the_same_miner_and_resets_only_under_v5(
    tmp_path,
):
    coldkeys = {"hk-a": "ck-a", "hk-a2": "ck-a"}
    (tmp_path / "v4").mkdir()
    v4 = crowned(tmp_path / "v4", V4, coldkeys)
    kept = v4.observe(V4, CHALLENGE, bank("m2", "hk-a2", "m1", "hk-a"), coldkeys, LATER)
    assert (kept["reason"], kept["clock_ms"]) == ("same_miner_no_reset", T0)
    (tmp_path / "v5").mkdir()
    v5 = crowned(tmp_path / "v5", V5, coldkeys)
    reset = v5.observe(
        V5, CHALLENGE, bank("m2", "hk-a2", "m1", "hk-a"), coldkeys, LATER
    )
    assert (reset["reason"], reset["clock_ms"], reset["eligible"]) == (
        "self_improvement_reset",
        LATER,
        True,
    )


def test_v4_behaves_as_today_for_a_self_beat(tmp_path):
    book = crowned(tmp_path, V4)
    record = book.observe(
        V4, CHALLENGE, bank("m2", "hk-a", "m1", "hk-a"), {"hk-a": "ck-a"}, LATER
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "same_miner_no_reset",
        T0,
    )
    paid = wd.epoch_targets(V4, {CHALLENGE: we.payable(record, {"hk-a"})}, LATER)
    assert paid["winners"] == {"hk-a": V4.share // 4}  # halving continues from T0


@pytest.mark.parametrize("policy", [V4, V5], ids=["v4", "v5"])
def test_a_takeover_by_another_miner_resets_under_both_versions(tmp_path, policy):
    book = crowned(tmp_path, policy)
    record = book.observe(
        policy,
        CHALLENGE,
        bank("m2", "hk-b", "m1", "hk-a"),
        {"hk-a": "ck-a", "hk-b": "ck-b"},
        LATER,
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "bank_improvement",
        LATER,
    )


def test_only_a_bank_promotion_can_reset(tmp_path):
    final = {
        "model_id": "m2",
        "hotkey": "hk-a",
        "previous": "m1",
        "previous_hotkey": "hk-a",
        "kind": we.FINAL,
        "final_id": "final-m2",
        "fresh_set": "fp-m2",
        "nomination_pool_version": 2,
        "nomination_overdue": False,
    }
    book = crowned(tmp_path, V5)
    record = book.observe(V5, CHALLENGE, final, {"hk-a": "ck-a"}, LATER)
    assert (record["reason"], record["clock_ms"]) == ("same_miner_no_reset", T0)


def test_an_ineligible_predecessor_gains_nothing_from_a_self_beat(tmp_path):
    book = ledger(tmp_path)
    # a first incumbent under a registered baseline is recorded ineligible
    ineligible = {
        "schema": we.LEDGER_SCHEMA,
        "challenge": CHALLENGE,
        "policy": V5.digest,
        "promotion": first("m1", "hk-a"),
        "observed_ms": T0,
        "winner_coldkey": "ck-a",
        "eligible": False,
        "reason": "baseline_registered_first_incumbent_unchecked",
        "clock_ms": T0,
    }
    book._append(ineligible)
    record = book.observe(
        V5, CHALLENGE, bank("m2", "hk-a", "m1", "hk-a"), {"hk-a": "ck-a"}, LATER
    )
    assert (record["eligible"], record["reason"]) == (False, "same_miner_no_reset")


# --- fail closed -----------------------------------------------------------------------


@pytest.mark.parametrize("repeat", [False, None, 1, "yes"], ids=str)
def test_a_self_beat_without_the_repeat_mark_is_refused_and_leaves_the_ledger(
    tmp_path, repeat
):
    book = crowned(tmp_path, V5)
    before = book.path.read_bytes()
    with pytest.raises(RewardFailure, match="SELF_IMPROVEMENT_UNVERIFIED"):
        book.observe(
            V5,
            CHALLENGE,
            bank("m2", "hk-a", "m1", "hk-a", repeat=repeat),
            {"hk-a": "ck-a"},
            LATER,
        )
    assert book.path.read_bytes() == before


def test_the_mark_is_not_asked_of_a_takeover_or_of_v4(tmp_path):
    # another miner's takeover and every v4 decision read no mark: exactly as before
    book = crowned(tmp_path, V5)
    taken = book.observe(
        V5,
        CHALLENGE,
        bank("m2", "hk-b", "m1", "hk-a", repeat=None),
        {"hk-a": "ck-a", "hk-b": "ck-b"},
        LATER,
    )
    assert taken["reason"] == "bank_improvement"
    (tmp_path / "x").mkdir()
    old = crowned(tmp_path / "x", V4)
    kept = old.observe(
        V4,
        CHALLENGE,
        bank("m2", "hk-a", "m1", "hk-a", repeat=None),
        {"hk-a": "ck-a"},
        LATER,
    )
    assert kept["reason"] == "same_miner_no_reset"


# --- the past is untouched -------------------------------------------------------------


def test_switching_to_v5_leaves_every_past_record_and_its_weights_unchanged(tmp_path):
    book = crowned(tmp_path, V4)
    past = book.observe(
        V4, CHALLENGE, bank("m2", "hk-a", "m1", "hk-a"), {"hk-a": "ck-a"}, LATER
    )
    before = book.path.read_bytes()
    weights_before = wd.epoch_targets(
        V4, {CHALLENGE: we.payable(past, {"hk-a"})}, LATER + DAY_MS
    )
    # the same promotion observed again under v5 is not re-decided
    again = book.observe(
        V5,
        CHALLENGE,
        bank("m2", "hk-a", "m1", "hk-a"),
        {"hk-a": "ck-a"},
        LATER + DAY_MS,
    )
    assert again == past and book.path.read_bytes() == before
    # a promotion observed after the switch is decided under v5 and appended
    new = book.observe(
        V5,
        CHALLENGE,
        bank("m3", "hk-a", "m2", "hk-a"),
        {"hk-a": "ck-a"},
        LATER + 5 * DAY_MS,
    )
    assert new["reason"] == "self_improvement_reset" and new["policy"] == V5.digest
    assert book.path.read_bytes().startswith(before)
    assert (
        wd.epoch_targets(V4, {CHALLENGE: we.payable(past, {"hk-a"})}, LATER + DAY_MS)
        == weights_before
    )


# --- what qualifies is the existing KOTH rule, end to end ------------------------------

PACK = digest("score pack")
KEY = digest("evaluation context")
NOISE = {"value": 0.03, "measurement_digest": digest("noise")}


def _body(model, total):
    return {
        "submission_id": model,
        "evidence": {
            "schema": bp.PAIRED_BINDING,
            "challenge": "electric-motor-magnetics",
            "score_compatibility": {"score_pack_digest": PACK},
            "entry_id": digest(["entry", model]),
            "model_p": {"score_status": bp.SCORED, "total_score": total},
        },
    }


def _compare(candidate_total, king_total=0.6):
    pair = {
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "evaluation_key": KEY,
        "expected_incumbent": "m1",
        "candidate": _body("m2", candidate_total),
        "incumbent": _body("m1", king_total),
    }
    comparator = {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": "electric-motor-magnetics",
        "score_pack_digest": PACK,
        "rebuild_noise": NOISE,
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": [digest("baseline run")],
        "baseline_total": 0.5,
    }
    return bp.compare_private_pair(pair, comparator)


def test_a_self_beat_within_the_margin_is_no_promotion_so_nothing_resets(tmp_path):
    book = crowned(tmp_path, V5)
    before = book.path.read_bytes()
    outcome = _compare(0.6 + NOISE["value"])  # at the margin is not beyond it
    assert outcome["outcome"] == bp.INCUMBENT_KEEPS
    # the incumbent stays: the lean store reads the same king, which is already recorded
    same = book.observe(V5, CHALLENGE, first("m1", "hk-a"), {"hk-a": "ck-a"}, LATER)
    assert same["clock_ms"] == T0 and book.path.read_bytes() == before


def test_a_self_beat_beyond_the_margin_is_a_promotion_that_resets_under_v5(tmp_path):
    book = crowned(tmp_path, V5)
    outcome = _compare(0.6 + NOISE["value"] + 0.01)
    assert outcome["outcome"] == bp.CHALLENGER
    record = book.observe(
        V5, CHALLENGE, bank("m2", "hk-a", "m1", "hk-a"), {"hk-a": "ck-a"}, LATER
    )
    assert record["reason"] == "self_improvement_reset" and record["clock_ms"] == LATER


# --- the promotion carries the store's repeat mark -------------------------------------


class _Store:
    def __init__(self, marks=None):
        self._marks = marks

    def incumbent(self):
        return {"model_id": "m2", "reason": bp.SEALED_TESTNET_PROMOTION}

    def events(self, kind=None):
        return [{"body": {"model_id": "m2", "previous": "m1"}}]

    def submission(self, model_id):
        return {"hotkey": "hk-a", "binding": {}}

    def __getattr__(self, name):
        if name == "repeat_marks" and self._marks is not None:
            return lambda model_id: self._marks.get(model_id, [])
        raise AttributeError(name)


def test_lean_promotion_reports_the_repeat_mark_of_the_incumbent():
    marked = we.lean_promotion(_Store({"m2": [digest("k")]}))
    assert marked["kind"] == we.BANK and marked["repeat_verified"] is True
    unmarked = we.lean_promotion(_Store({"m1": [digest("k")]}))
    assert unmarked["repeat_verified"] is False
    # a store that cannot say carries no field, so v5 refuses the self-beat
    assert "repeat_verified" not in we.lean_promotion(_Store(None))


def test_the_real_store_lists_the_marks_a_crown_filed(tmp_path):
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 0.0)
    for model in ("m1", "m2"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="hk-a",
            challenge="electric-motor-magnetics",
            strategy={},
            binding={"challenge": {"id": "electric-motor-magnetics"}},
        )
    assert store.repeat_marks("m2") == []
    store.record_repeat_verified("m2", digest("key-1"), digest("fp-1"))
    store.record_repeat_verified("m1", digest("key-1"), digest("fp-0"))
    store.record_repeat_verified("m2", digest("key-2"), digest("fp-2"))
    assert store.repeat_marks("m2") == [digest("key-1"), digest("key-2")]
    assert store.repeat_marks("m1") == [digest("key-1")]
    assert store.repeat_marks("other") == []
