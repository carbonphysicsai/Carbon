"""The operator pause switch: crown changes and the weights run (one flag file, read at decision time)."""

import argparse
import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import operator_pause
from carbon.validator_setup import weights
from carbon.validator_setup.bundle import SetupRefused
from tests.cpu import test_crown_grade_repeat as base

pytestmark = pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only file modes are POSIX"
)


def flag(directory, body, mode=0o600):
    path = operator_pause.flag_path(directory)
    path.write_text(json.dumps(body), encoding="utf-8")
    path.chmod(mode)
    return path


class Store(base.Store):
    def __init__(self, fixed, directory):
        super().__init__(fixed)
        self.path = directory / "pool.sqlite3"


def consider(fixed, directory, repeat=None):
    store = Store(fixed, directory)
    promotion = bp.BankPromotion.__new__(bp.BankPromotion)
    promotion.store = store
    promotion.registered_source_receipt_sha256 = base.digest("pin")
    outcome = promotion.consider_private(
        fixed["candidate"]["submission_id"],
        base.KEY,
        base.comparator(),
        repeat=repeat or base.same_again(fixed),
    )
    return outcome, store


def never(model):
    raise AssertionError("a paused crown change spends no repeat grade")


CHANGES = dict(base.CASES)
CHANGES["dethrone_without_successor"] = base.pair(
    base.body("c", "FAILED_INFRA"), base.body("k", "MANDATORY_GATE_FAILED", 0.0)
)


@pytest.mark.parametrize("name", sorted(CHANGES))
def test_paused_crowns_change_nothing_for_every_crown_changing_outcome(name, tmp_path):
    flag(tmp_path, {"crowns_paused": True})
    outcome, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == "crowns_paused"
    assert outcome["candidate"] == "c"
    assert store.moves == [] and store.marks == {}


@pytest.mark.parametrize("name", sorted(CHANGES))
def test_removing_the_flag_lets_the_same_contender_be_considered_again(name, tmp_path):
    path = flag(tmp_path, {"crowns_paused": True})
    paused, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert paused["reason"] == "crowns_paused" and store.moves == []
    path.unlink()
    resumed, store = consider(CHANGES[name], tmp_path)
    assert resumed["outcome"] in bp.CROWN_CHANGING
    assert store.moves != []
    # The contender's repeat ran as normal and was marked.
    assert store.marks


def test_an_outcome_that_changes_no_crown_is_not_touched_by_the_pause(tmp_path):
    flag(tmp_path, {"crowns_paused": True})
    fixed = base.pair(base.body("c", total=0.55), base.body("k", total=0.5))
    outcome, store = consider(fixed, tmp_path, repeat=never)
    assert outcome["outcome"] == bp.INCUMBENT_KEEPS and store.moves == []


def test_the_weights_flag_alone_does_not_pause_crowns(tmp_path):
    flag(tmp_path, {"weights_paused": True})
    outcome, store = consider(CHANGES["takeover"], tmp_path)
    assert outcome["outcome"] == bp.CHALLENGER and store.moves != []


@pytest.mark.parametrize(
    "bad",
    ["not json", "[]", '{"crowns_paused": "yes"}', '{"crowns": true}', "{}x"],
)
def test_an_unreadable_flag_pauses_both(tmp_path, bad):
    path = operator_pause.flag_path(tmp_path)
    path.write_text(bad, encoding="utf-8")
    path.chmod(0o600)
    assert operator_pause.read(tmp_path) == {
        "crowns_paused": True,
        "weights_paused": True,
    }


def test_a_flag_others_can_write_or_a_symlink_pauses_both(tmp_path):
    flag(tmp_path, {"crowns_paused": False}, mode=0o644)
    assert operator_pause.crowns_paused(tmp_path) is True
    operator_pause.flag_path(tmp_path).unlink()
    target = tmp_path / "elsewhere"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o600)
    operator_pause.flag_path(tmp_path).symlink_to(target)
    assert operator_pause.weights_paused(tmp_path) is True


def test_no_flag_means_running(tmp_path):
    running = {"crowns_paused": False, "weights_paused": False}
    assert operator_pause.read(tmp_path) == running
    flag(tmp_path, running)
    assert operator_pause.read(tmp_path) == running


def operator_config(tmp_path):
    from tests.cpu.test_validator_setup_weights import config

    return config(tmp_path)[0]


def test_weights_run_is_refused_before_any_wallet_issuer_or_reader(
    tmp_path, monkeypatch
):
    from carbon.chain import sdk, sdk_weights
    from carbon.rewards import testnet_winner_publication as publication

    def forbidden(*args, **kwargs):
        raise AssertionError("a paused run must not reach these")

    monkeypatch.setattr(sdk, "BittensorReader", forbidden)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", forbidden)
    monkeypatch.setattr(publication, "_issuer", forbidden)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    flag(state, {"weights_paused": True})
    args = argparse.Namespace(
        config=operator_config(tmp_path),
        action="run",
        journal=state / "journal.sqlite3",
    )
    with pytest.raises(SetupRefused, match="weights_paused"):
        asyncio.run(weights.execute(args))
    assert list(state.iterdir()) == [operator_pause.flag_path(state)]


def test_preview_still_works_while_weights_are_paused(tmp_path, monkeypatch):
    from carbon.chain import sdk
    from carbon.rewards import testnet_winner_publication as publication

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    flag(state, {"crowns_paused": True, "weights_paused": True})

    class Reader:
        async def capture(self, _context):
            return "snapshot"

    monkeypatch.setattr(publication, "_issuer", lambda *a: "issuer")
    monkeypatch.setattr(sdk, "BittensorReader", Reader)
    monkeypatch.setattr(publication, "preview", lambda issuer, snap: (issuer, snap))
    args = SimpleNamespace(
        config=operator_config(tmp_path),
        action="preview",
        journal=state / "journal.sqlite3",
    )
    assert asyncio.run(weights.execute(args)) == ("issuer", "snapshot")


def test_the_crowns_flag_alone_does_not_refuse_the_weights_run(tmp_path, monkeypatch):
    from carbon.rewards import testnet_winner_publication as publication

    class Reached(Exception):
        pass

    def issuer(*args, **kwargs):
        raise Reached

    monkeypatch.setattr(publication, "_issuer", issuer)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    flag(state, {"crowns_paused": True})
    args = SimpleNamespace(
        config=operator_config(tmp_path),
        action="run",
        journal=state / "journal.sqlite3",
    )
    with pytest.raises(Reached):
        asyncio.run(weights.execute(args))


# --- the resume sweep: a paused contender is decided again once the flag is gone ----------------------------------


def digest(name):
    return base.digest(name)


KEY_A, KEY_B, KEY_C = digest("key a"), digest("key b"), digest("key c")
EXAM, OTHER_EXAM = digest("exam"), digest("another exam")
ENTRY, PIN = digest("entry"), digest("pin")


def pool(tmp_path):
    from carbon.battery.pool_store import PoolStore

    state = tmp_path / "state"
    state.mkdir(mode=0o700, exist_ok=True)
    return PoolStore(state / "pool.sqlite3")


def file_paused(store, submission_id, key, kind="pack", exam=EXAM):
    store.record_crown_paused(
        submission_id, key, kind=kind, exam=exam, entry_id=ENTRY, pin=PIN
    )


def decided(outcome=bp.CHALLENGER, reason="bank_comparison_development"):
    return {"outcome": outcome, "reason": reason}


def test_paused_contenders_are_filed_once_and_listed_oldest_first(tmp_path):
    store = pool(tmp_path)
    for name, key in (("a", KEY_A), ("b", KEY_B), ("c", KEY_C)):
        file_paused(store, name, key)
    file_paused(store, "a", KEY_A)  # idempotent
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a", "b", "c"]
    assert store.paused_crowns("set") == []


def test_a_resolution_is_write_once(tmp_path):
    from carbon.battery.pool_store import StateError

    store = pool(tmp_path)
    file_paused(store, "a", KEY_A)
    store.resolve_crown_pause("a", KEY_A, "CHALLENGER:x")
    store.resolve_crown_pause("a", KEY_A, "CHALLENGER:x")
    with pytest.raises(StateError, match="crown_pause_resolution_changed"):
        store.resolve_crown_pause("a", KEY_A, "INCUMBENT_KEEPS:y")
    assert store.crown_pause_resolved("a", KEY_A) == "CHALLENGER:x"
    assert store.paused_crowns() == []


def sweep(store, reconsider, kind="pack", exam=EXAM):
    from carbon.challenge_validator import crown_pause_sweep

    return crown_pause_sweep.sweep(store, reconsider, kind=kind, current_exam=exam)


def test_oldest_first_each_against_the_incumbent_of_that_moment(tmp_path):
    store = pool(tmp_path)
    for name, key in (("a", KEY_A), ("b", KEY_B), ("c", KEY_C)):
        file_paused(store, name, key)
    incumbent = [None]
    seen = []
    store.incumbent = lambda: (
        None if incumbent[0] is None else {"model_id": incumbent[0]}
    )

    def reconsider(record):
        seen.append((record["submission_id"], incumbent[0]))
        incumbent[0] = record["submission_id"]
        return decided()

    done = sweep(store, reconsider)
    assert seen == [("a", None), ("b", "a"), ("c", "b")]
    assert [name for name, _code in done] == ["a", "b", "c"]


def test_a_crash_mid_sweep_resumes_where_it_stopped_and_decides_nobody_twice(
    tmp_path,
):
    store = pool(tmp_path)
    for name, key in (("a", KEY_A), ("b", KEY_B), ("c", KEY_C)):
        file_paused(store, name, key)
    calls = []

    def flaky(record):
        calls.append(record["submission_id"])
        if record["submission_id"] == "b" and calls.count("b") == 1:
            raise RuntimeError("host went away")
        return decided()

    assert [n for n, _ in sweep(store, flaky)] == [
        "a"
    ]  # stopped at b: c not decided ahead of it
    assert [r["submission_id"] for r in store.paused_crowns()] == ["b", "c"]
    assert [n for n, _ in sweep(store, flaky)] == ["b", "c"]
    assert calls == ["a", "b", "b", "c"]
    assert sweep(store, flaky) == []
    assert calls == ["a", "b", "b", "c"]


def test_a_contender_that_is_already_the_incumbent_is_not_decided_again(tmp_path):
    store = pool(tmp_path)
    file_paused(store, "a", KEY_A)
    store.incumbent = lambda: {"model_id": "a"}

    def never(record):
        raise AssertionError("already crowned")

    assert sweep(store, never) == [("a", "already_incumbent")]


def test_a_rotation_during_the_pause_never_crowns(tmp_path):
    store = pool(tmp_path)
    file_paused(store, "a", KEY_A, exam=OTHER_EXAM)

    def never(record):
        raise AssertionError("the exam is no longer the active one")

    assert sweep(store, never) == [("a", "UNAVAILABLE:exam_rotated_during_pause")]
    assert store.paused_crowns() == []


def test_nothing_is_decided_while_the_flag_stands_or_when_it_returns(tmp_path):
    store = pool(tmp_path)
    file_paused(store, "a", KEY_A)
    file_paused(store, "b", KEY_B)
    path = flag(store.path.parent, {"crowns_paused": True})

    def never(record):
        raise AssertionError("paused")

    assert sweep(store, never) == []
    path.unlink()
    again = [decided(reason="crowns_paused")]
    assert sweep(store, lambda record: again[0]) == []  # paused again mid-sweep
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a", "b"]
    assert [n for n, _ in sweep(store, lambda record: decided())] == ["a", "b"]


def test_a_refusal_is_not_a_decision_and_stays_unresolved(tmp_path):
    store = pool(tmp_path)
    file_paused(store, "a", KEY_A)
    assert sweep(store, lambda record: {"error": "pool_refused"}) == []
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a"]


def test_a_paused_decision_is_filed_by_the_path_and_nothing_else_is(tmp_path):
    from carbon.challenge_validator import lean_recipe_retention as retention

    store = pool(tmp_path)

    def repeat(model):
        raise AssertionError("not run")

    repeat.entry_id = ENTRY
    paused = {
        "outcome": bp.UNAVAILABLE,
        "reason": "crowns_paused",
        "evaluation_key": KEY_A,
    }
    retention._file_if_paused(store, paused, "pack", "a", EXAM, repeat, PIN)
    retention._file_if_paused(
        store, decided() | {"evaluation_key": KEY_B}, "pack", "b", EXAM, repeat, PIN
    )
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a"]
    record = store.paused_crowns()[0]
    assert (record["kind"], record["exam"], record["entry_id"], record["pin"]) == (
        "pack",
        EXAM,
        ENTRY,
        PIN,
    )

    def bare(model):
        return None

    with pytest.raises(retention.RetentionUnavailable, match="entry_unavailable"):
        retention._file_if_paused(store, paused, "pack", "c", EXAM, bare, PIN)


def test_the_pack_decision_is_made_from_the_filed_evaluation_with_no_regrade(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import koth_registry
    from carbon.challenge_validator import lean_recipe_retention as retention

    store = pool(tmp_path)
    file_paused(store, "a", KEY_A)
    (record,) = store.paused_crowns()
    taken = {}

    def consider(self, submission_id, key, comparator, *, sealed, repeat):
        taken.update(
            submission_id=submission_id,
            key=key,
            pin=self.registered_source_receipt_sha256,
            repeat_entry=repeat.entry_id,
            sealed=sealed,
        )
        return decided()

    def forbidden(*args, **kwargs):
        raise AssertionError("a resumed decision takes no regrade, slot or Ladder")

    monkeypatch.setattr(bp.BankPromotion, "consider_private", consider)
    monkeypatch.setattr(koth_registry, "comparator", lambda *a: {"c": 1})
    monkeypatch.setattr(retention, "regrade_retained_entry", forbidden)
    monkeypatch.setattr(retention, "_record_ladder", forbidden)
    snapshot = SimpleNamespace(read_json_role=lambda *a, **k: {})
    adapter = SimpleNamespace(
        challenge_id="chip-cold-plate",
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_private_root="p",
            evaluation_pack_public_root="q",
            evaluation_pack_sealed=True,
        ),
    )
    out = retention.reconsider_paused_pack(
        adapter, store, record, artifact_directory=tmp_path, entry_directory=tmp_path
    )
    assert out == decided()
    assert taken == {
        "submission_id": "a",
        "key": KEY_A,
        "pin": PIN,
        "repeat_entry": ENTRY,
        "sealed": True,
    }


def test_the_set_decision_is_made_again_under_the_set_key_with_no_regrade(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.challenge_validator import pack_set_grading as grading

    store = pool(tmp_path)
    file_paused(store, "a", KEY_A, kind="set", exam=EXAM)
    (record,) = store.paused_crowns("set")
    taken = {}

    def contend(promotion, adapters, batches, set_key, origin, pins, repeat):
        taken.update(
            set_key=set_key,
            origin=origin,
            pins=pins,
            repeat_entry=repeat.entry_id,
            batches=batches,
        )
        return decided()

    def forbidden(*args, **kwargs):
        raise AssertionError("a resumed decision takes no regrade, slot or Ladder")

    monkeypatch.setattr(grading, "_contend_set", contend)
    monkeypatch.setattr(retention, "regrade_retained_entry", forbidden)
    monkeypatch.setattr(retention, "_record_ladder", forbidden)
    done = grading.resume_paused_sets(
        store,
        {"d1": object(), "d2": object()},
        ["d1", "d2"],
        EXAM,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    assert done == [("a", "CHALLENGER:bank_comparison_development")]
    assert taken == {
        "set_key": EXAM,
        "origin": "a",
        "pins": {PIN},
        "repeat_entry": ENTRY,
        "batches": ["d1", "d2"],
    }
    assert record["kind"] == "set"


def test_a_set_rotation_during_the_pause_never_crowns(tmp_path, monkeypatch):
    from carbon.challenge_validator import pack_set_grading as grading

    store = pool(tmp_path)
    file_paused(store, "a", KEY_A, kind="set", exam=OTHER_EXAM)

    def forbidden(*args, **kwargs):
        raise AssertionError("rotated")

    monkeypatch.setattr(grading, "_contend_set", forbidden)
    done = grading.resume_paused_sets(
        store,
        {},
        ["d1"],
        EXAM,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    assert done == [("a", "UNAVAILABLE:exam_rotated_during_pause")]


def test_the_auto_grade_tick_resumes_pack_decisions_before_new_grades(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.challenge_validator.auto_grade import AutoGrader

    store = pool(tmp_path)
    file_paused(store, "a", KEY_A)
    calls = []
    monkeypatch.setattr(
        retention,
        "reconsider_paused_pack",
        lambda adapter, pool_store, record, **kw: calls.append(record) or decided(),
    )
    intake = SimpleNamespace(
        adapter=SimpleNamespace(
            contract_digest="c",
            ledger=SimpleNamespace(submitted_outcomes=lambda digest: []),
            discovery=SimpleNamespace(evaluation_pack_digest=EXAM),
        )
    )
    auto = AutoGrader(intake, tmp_path)
    auto._pool = lambda: store
    flag(store.path.parent, {"crowns_paused": True})
    assert auto.run_once() is None and calls == []
    operator_pause.flag_path(store.path.parent).unlink()
    assert auto.run_once() is None
    assert [r["submission_id"] for r in calls] == ["a"]
    assert store.paused_crowns() == []


def test_a_grade_that_is_not_paused_never_reads_the_exam_digest(tmp_path):
    from carbon.challenge_validator import lean_recipe_retention as retention

    store = pool(tmp_path)

    def exam():
        raise AssertionError("only a paused decision needs the exam digest")

    retention._file_if_paused(
        store, decided() | {"evaluation_key": KEY_A}, "pack", "a", exam, None, PIN
    )
    assert store.paused_crowns() == []
