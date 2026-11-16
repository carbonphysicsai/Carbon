"""Crowns decided on the OFFICIAL grades with no crown rebuild (owner 14 Nov via the Lead; `crown_official`).

Claims:
- the rule is registered outside ``carbon/`` per version, with no default; a malformed entry refuses; an unlisted version is
  off; installing it ON turns the crown average OFF (no screening, no N rebuilds, no king re-measure);
- a contender's official total GREATER than the king's official total + the registered margin crowns it at once; within the
  margin (a tie) the king keeps the crown; neither a repeat grade nor any rebuild is run (both would raise here);
- queue order is the existing one: with crowns paused, contenders are filed in admission order; once lifted, the sweep decides
  them oldest-first, each against the king of its moment; a later one never jumps an undecided earlier one;
- off (no entry): `consider_private` is exactly as before.

Every grade, digest and model here is a SYNTHETIC fixture.
"""

from __future__ import annotations

import json

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import crown_official, operator_pause
from carbon.challenge_validator import crown_pause_sweep as sweeper
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest
from tests.cpu.test_crown_average_wiring import (
    CHALLENGE,
    KEY,
    _active,
    _body,
    _comparator,
    _pair,
    _Pairs,
)

VERSION = "1.8"
MARGIN = 0.0129
EXAM = digest("exam")
PIN = digest("pin")
T0 = 1_000_000.0


class NoRebuild:
    """A `repeat` whose every use raises: the official-score rule must never call it."""

    entry_id = digest("entry")

    def __call__(self, submission_id):
        raise AssertionError("a repeat grade ran under official-score crowns")

    def rebuild_at(self, seed):
        raise AssertionError("a crown rebuild ran under official-score crowns")

    rebuild_again_at = rebuild_at


def _registry(tmp_path, versions):
    path = tmp_path / "crown_official_score.json"
    path.write_text(
        json.dumps({"schema": crown_official.SCHEMA, "versions": versions}),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def official(tmp_path, monkeypatch):
    path = _registry(tmp_path, {f"{CHALLENGE} {VERSION}": {"margin": MARGIN}})
    monkeypatch.setattr(ca, "ACTIVE", object())  # the crown average as the door had it
    monkeypatch.setattr(
        crown_official, "ACTIVE", crown_official.ACTIVE
    )  # restored after
    lines = []
    crown_official.install(CHALLENGE, VERSION, path=path, log=lines.append)
    return lines


@pytest.fixture
def rig(tmp_path, monkeypatch, official):
    clock = [T0]
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = PoolStore(state / "pool.sqlite3", clock=lambda: clock[0])
    for model in ("k", "a", "b", "c"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge=CHALLENGE,
            strategy={},
            binding={"challenge": {"id": CHALLENGE}},
        )
    bodies = {
        "k": _body("k", 0.70),
        "a": _body("a", 0.75),
        "b": _body("b", 0.80),
        "c": _body("c", 0.81),
    }
    pairs = {}
    monkeypatch.setattr(store, "private_evaluation_pair", _Pairs(pairs))
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    paused = [False]
    monkeypatch.setattr(operator_pause, "crowns_paused", lambda _state: paused[0])

    def king():
        held = store.incumbent()
        return None if held is None else held["model_id"]

    def consider(sid, average=None):
        held = king()
        pairs[sid] = _pair(bodies[sid], None if held is None else bodies[held])
        return flow.consider_private(
            sid, KEY, _comparator(), repeat=NoRebuild(), average=average
        )

    def live(sid):
        outcome = consider(sid)
        retention._file_if_paused(
            store,
            {**outcome, "evaluation_key": KEY},
            "pack",
            sid,
            EXAM,
            NoRebuild(),
            PIN,
        )
        return outcome

    def reconsider(record):
        return consider(record["submission_id"])

    # the sitting king: k
    store.set_incumbent("k", bp.DEVELOPMENT_PROMOTION, expected=None)
    return store, clock, bodies, paused, consider, live, reconsider, king


# ----------------------------------------------------------------------------------------- the registry


def test_the_rule_is_registered_with_no_default_and_malformed_refuses(tmp_path):
    key = f"{CHALLENGE} {VERSION}"
    good = crown_official.registered(
        CHALLENGE, VERSION, path=_registry(tmp_path, {key: {"margin": MARGIN}})
    )
    assert good["margin"] == MARGIN and good["digest"].startswith("sha256:")
    assert (
        crown_official.registered(CHALLENGE, "1.7", path=_registry(tmp_path, {}))
        is None
    )
    assert (
        crown_official.registered(CHALLENGE, VERSION, path=tmp_path / "absent.json")
        is None
    )
    for entry in (
        {"margin": None},
        {"margin": "0.0129"},
        {"margin": True},
        {"margin": 1.5},
        {"margin": -0.1},
        {"margin": MARGIN, "hold_hours": 48},
        {},
    ):
        with pytest.raises(
            crown_official.CrownOfficialInvalid, match="crown_official_entry_malformed"
        ):
            crown_official.registered(
                CHALLENGE, VERSION, path=_registry(tmp_path, {key: entry})
            )
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(crown_official.CrownOfficialInvalid, match="unreadable"):
        crown_official.registered(CHALLENGE, VERSION, path=bad)


def test_the_repositorys_registry_turns_it_on_for_motor_18_only():
    on = crown_official.registered("electric-motor-magnetics", "1.8")
    assert on is not None and on["margin"] == MARGIN
    for other in (
        ("electric-motor-magnetics", "1.7"),
        ("chip-cold-plate", "1.8"),
        ("f08-ribbed-bracket", "2.0"),
    ):
        assert crown_official.registered(*other) is None


def test_install_on_turns_the_crown_average_off_and_says_so(official):
    assert ca.ACTIVE is None
    assert crown_official.ACTIVE["margin"] == MARGIN
    assert official == [f"crown_official_score=true margin={MARGIN}"]


def test_install_off_leaves_the_crown_average_as_it_was(tmp_path, monkeypatch):
    monkeypatch.setattr(crown_official, "ACTIVE", crown_official.ACTIVE)
    sentinel = object()
    monkeypatch.setattr(ca, "ACTIVE", sentinel)
    lines = []
    crown_official.install(
        CHALLENGE, "1.7", path=_registry(tmp_path, {}), log=lines.append
    )
    assert crown_official.ACTIVE is None and ca.ACTIVE is sentinel
    assert lines == ["crown_official_score=false margin=none"]


# ----------------------------------------------------------------------------------------- the rule


def test_a_contender_above_the_king_by_more_than_the_margin_is_crowned_at_once_without_a_rebuild(
    rig,
):
    _store, _clock, _bodies, _paused, consider, _live, _reconsider, king = rig
    outcome = consider("a")  # 0.75 > 0.70 + 0.0129
    assert outcome["outcome"] == bp.CHALLENGER
    assert king() == "a"


def test_within_the_margin_the_king_keeps_the_crown(rig):
    _store, _clock, bodies, _paused, consider, _live, _reconsider, king = rig
    bodies["a"] = _body("a", 0.71)  # 0.71 is within 0.70 + 0.0129
    assert consider("a")["outcome"] == bp.INCUMBENT_KEEPS
    bodies["a"] = _body("a", 0.70)  # an exact tie
    assert consider("a")["outcome"] == bp.INCUMBENT_KEEPS
    assert king() == "k"


def test_a_crown_average_passed_in_is_not_used(rig, tmp_path):
    _store, _clock, _bodies, _paused, consider, _live, _reconsider, king = rig
    # even with an Active crown average handed in, the official grades decide and nothing rebuilds (NoRebuild would raise)
    assert consider("a", average=_active(tmp_path))["outcome"] == bp.CHALLENGER
    assert king() == "a"


def test_a_gate_failed_king_is_still_dethroned_as_before(rig):
    _store, _clock, bodies, _paused, consider, _live, _reconsider, king = rig
    bodies["k"] = _body("k", None, status="MANDATORY_GATE_FAILED")
    assert consider("a")["outcome"] == bp.CHALLENGER
    assert king() == "a"


# ----------------------------------------------------------------------------------------- queue order


def test_paused_contenders_are_decided_oldest_first_each_against_the_king_of_its_moment(
    rig,
):
    store, clock, _bodies, paused, consider, live, reconsider, king = rig
    paused[0] = True
    for sid in ("a", "b", "c"):
        assert live(sid)["reason"] == bp.CROWNS_PAUSED
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a", "b", "c"]
    assert king() == "k"
    paused[0] = False
    # a later one considered first never jumps the undecided earlier ones
    assert consider("b")["reason"] == bp.CROWN_QUEUED
    clock[0] += sweeper.RETRY_SECONDS + 1
    done = sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)
    assert [sid for sid, _ in done] == ["a", "b", "c"]
    # a beats k (0.75 > 0.7129); b beats a (0.80 > 0.7629); c is within b's margin (0.81 <= 0.8129): b keeps
    assert done[0][1].startswith(bp.CHALLENGER)
    assert done[1][1].startswith(bp.CHALLENGER)
    assert done[2][1].startswith(bp.INCUMBENT_KEEPS)
    assert king() == "b" and store.paused_crowns() == []


# ----------------------------------------------------------------------------------------- off


def test_off_the_decision_is_exactly_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(crown_official, "ACTIVE", None)
    assert crown_official.comparator(_comparator()) is None
    store = PoolStore(tmp_path / "pool.sqlite3", clock=lambda: T0)
    for model in ("k", "a"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge=CHALLENGE,
            strategy={},
            binding={"challenge": {"id": CHALLENGE}},
        )
    monkeypatch.setattr(
        store, "private_evaluation_pair", _Pairs({"a": _pair(_body("a", 0.75), None)})
    )
    monkeypatch.setattr(ca, "ACTIVE", None)
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    # off: a first crown goes to the repeat gate as before; the stand-in repeat fails, so no crown moves (as before)
    outcome = flow.consider_private("a", KEY, _comparator(), repeat=NoRebuild())
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == bp.REPEAT_UNAVAILABLE
    assert store.incumbent() is None


# ----------------------------------------------------------------------------------------- the decision record


def test_the_decision_record_quotes_the_owner_and_carries_the_registrys_margin():
    """docs/records/2026-11-14-motor18-crown-official-score.json: the owner's three lines (19:41, 19:44, 19:45, typed in
    the Lead session, ledger L591-L593) and EXACTLY the registry row's margin, so the two never drift apart.
    """
    from pathlib import Path

    root = Path(crown_official.REGISTRY).resolve().parents[2]
    record = json.loads(
        (root / "docs/records/2026-11-14-motor18-crown-official-score.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["challenge"] == CHALLENGE and record["version"] == VERSION
    assert [w["typed_at"] for w in record["owner_words"]] == [
        "Sat 14 Nov 2026 19:41 CST",
        "Sat 14 Nov 2026 19:44 CST",
        "Sat 14 Nov 2026 19:45 CST",
    ]
    assert all(w["typed_in"] == "the Lead session" for w in record["owner_words"])
    assert record["owner_words"][1]["verbatim"] == ".0129"
    assert record["values"] == {
        "margin": crown_official.registered(CHALLENGE, VERSION)["margin"]
    }


# ----------------------------------------------------------------------------------------- the weights loop + the king page


def test_an_official_crown_is_a_verified_crown_for_the_weights_loop(rig):
    """TE-B must-fix 2: a same-miner crown's self-improvement reset needs the crown verified
    (`winner_eligibility._averaged_crown`); an official crown files its verification record, so it is.
    """
    from carbon.rewards import winner_eligibility as we

    store, _clock, _bodies, _paused, consider, _live, _reconsider, king = rig
    outcome = consider("a")
    assert outcome["outcome"] == bp.CHALLENGER and king() == "a"
    # the caller files the decision row, as the receiver does after consider_private
    store.record_crown_decision("a", KEY, outcome["outcome"], outcome["reason"])
    assert we._averaged_crown(store, "a") is True
    assert we._averaged_crown(store, "b") is False  # no crown, no verification
    # the record is the rule and the two official totals, nothing else
    with store.db() as db:
        (raw,) = db.execute(
            "SELECT body FROM operations WHERE kind='crown_average.v1'"
        ).fetchone()
    private = json.loads(raw)["private"]
    assert private == {
        "rule": crown_official.RECORD_RULE,
        "margin": MARGIN,
        "margin_digest": crown_official.ACTIVE["digest"],
        "candidate_total": 0.75,
        "incumbent_total": 0.70,
    }


def test_the_official_record_check_refuses_anything_else():
    from carbon.rewards import winner_eligibility as we

    good = {"rule": "official_score", "margin": MARGIN, "candidate_total": 0.75}
    assert we._official_crown(good) is True
    for bad in (
        None,
        {**good, "rule": "other"},
        {**good, "margin": None},
        {**good, "candidate_total": float("nan")},
        {**good, "candidate_total": True},
    ):
        assert we._official_crown(bad) is False


def test_the_king_page_shows_the_official_margin_and_a_bar_never_below_the_real_one(
    official, monkeypatch
):
    """TE-B must-fix 1: under official crowns the page's margin is the rule's (never the rebuild noise). Official crowns
    ARE the single-grade rule, so the page keeps its original bar and id (no averaged bar; Deploy-B 14 Nov: the averaged
    id named a rule that no longer decides): the step-floored king total + step + margin, rounded UP, never below the
    real bar (the exact total + the margin), and the exact total never shown.
    """
    import types

    from carbon.challenge_validator import direct_receiver, koth_public
    from carbon.scoring import grade_feedback as gf

    challenge = types.SimpleNamespace(challenge_id=CHALLENGE, version=VERSION)
    assert direct_receiver._page_noise(challenge)["value"] == MARGIN
    monkeypatch.setattr(
        direct_receiver,
        "_open_pool_store",
        lambda _p: pytest.fail("the official page reads no averaged bar"),
    )
    assert direct_receiver._crown_bar("store", CHALLENGE) is None
    # TE-B's worst case: a king at 0.55999 must publish a score to beat at or above 0.55999 + 0.0129 = 0.57289
    for king_total in (0.5, 0.55999, 0.6, 0.66, 0.6655, 0.7129, 0.79):
        shown = koth_public.to_beat_v2(gf.floor_to_step(king_total, MARGIN), MARGIN)
        assert shown >= king_total + MARGIN - 1e-12, (king_total, shown)
    # the live 116 case: a king floored to 0.66 shows 0.693 (the true bar lies between 0.673 and 0.693)
    assert koth_public.to_beat_v2(0.66, MARGIN) == 0.693
    assert koth_public.TO_BEAT_RULE_FLOOR == "floor_plus_step_plus_margin"
    # owner 16 Nov: the page's bar is now the crown rule's own, the exact king total + the margin, rounded UP
    assert koth_public.TO_BEAT_RULE == "king_plus_margin"
    for king_total in (0.5, 0.55999, 0.6, 0.66, 0.6655, 0.7129, 0.79):
        shown = koth_public.to_beat_exact(king_total, MARGIN)
        assert king_total + MARGIN - 1e-12 <= shown < king_total + MARGIN + 0.001
    assert koth_public.to_beat_exact(0.77951, MARGIN) == 0.793


def test_off_the_king_page_is_as_before(monkeypatch):
    import types

    from carbon.challenge_validator import crown_average, direct_receiver, koth_registry

    monkeypatch.setattr(crown_official, "ACTIVE", None)
    monkeypatch.setattr(crown_average, "ACTIVE", None)
    monkeypatch.setattr(
        koth_registry, "rebuild_noise", lambda c, version=None: {"value": 0.0079}
    )
    challenge = types.SimpleNamespace(challenge_id=CHALLENGE, version=VERSION)
    assert direct_receiver._page_noise(challenge) == {"value": 0.0079}
    assert direct_receiver._crown_bar("store", CHALLENGE) is None
