"""A crown decision the host could not make is retried, never lost; the host owner of the derived rebuilds is servable.

Claims. FIX 1: `OwnerProviders` opens EXACTLY `crown_average.HOST_OWNER` (no registration to observe, an always-live frozen
campaign), only through the provider factory the rebuild path uses; every other non-ss58 owner is still refused, the host
owner is never a submitter, and it survives a restart. FIX 2: the sweep leaves a paused decision UNRESOLVED on an UNAVAILABLE
or FAILED_INFRA outcome (counted, one retry per epoch, a typed alert after three failures), resolves only decided outcomes,
and a live trigger that hits infra keeps its screening grade filed for the same retry."""

from __future__ import annotations

import os
from dataclasses import replace

import pytest
from test_direct_receiver import OTHER, OWNER, RECEIVER
from test_operator_pause import (
    ENTRY,
    EXAM,
    KEY_A,
    KEY_B,
    PIN,
    decided,
    file_paused,
)

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import crown_pause_sweep as sweeper
from carbon.challenge_validator import direct_receiver as receiver
from carbon.challenge_validator import lean_recipe_retention as retention

posix = pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only file modes are POSIX"
)


# --- FIX 1: the host owner -----------------------------------------------------------------------------------


def _pool(tmp_path, monkeypatch=None):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import (
        CARBON_NETUID,
        CARBON_NETWORK,
        ChainContext,
        Participant,
    )
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    snapshot = replace(
        snapshot,
        participants=snapshot.participants + (Participant(2, OTHER, "cold2", 2),),
    )
    root = receiver._private_directory(tmp_path / "owners")

    def make():
        return receiver.OwnerProviders(
            root,
            discovery,
            parent,
            tmp_path / "cache",
            inference_image=parent,
            implementation={"revision": "a" * 40},
            snapshot=snapshot,
            receiver=RECEIVER,
        )

    return make


@posix
def test_the_provider_factory_serves_exactly_the_host_owner_and_no_other_non_ss58_owner(
    tmp_path,
):
    from carbon.challenge_validator.interface import Unavailable

    pool = _pool(tmp_path)()
    host = pool(ca.HOST_OWNER)
    assert host.owner == ca.HOST_OWNER and pool(ca.HOST_OWNER) is host
    with host.ledger.db() as db:
        import json

        frozen = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert frozen["owner"] == ca.HOST_OWNER and frozen["admission"] is None
    for other in (
        "carbon-crown-average-host2",
        "carbon-crown-average",
        "",
        "host",
        "miner",
        ca.HOST_OWNER + " ",
        None,
        5,
    ):
        with pytest.raises(Unavailable, match="direct_provider_owner_invalid"):
            pool(other)
    # a miner is still opened by registration, and the two never share a ledger
    assert pool(OWNER).ledger.root != host.ledger.root
    pool.cancel()
    pool.close()


@posix
def test_the_host_owner_is_never_reached_by_a_miner_path_and_survives_a_restart(
    tmp_path,
):
    from carbon.challenge_validator.interface import Unavailable

    make = _pool(tmp_path)
    pool = make()
    first = pool(ca.HOST_OWNER).ledger.root
    # the private open refuses the host owner unless the factory marked it as the host
    with pytest.raises(Unavailable, match="direct_provider_owner_invalid"):
        pool._open(ca.HOST_OWNER, restoring=False)
    with pytest.raises(Unavailable, match="direct_provider_owner_invalid"):
        pool._open(OWNER, restoring=False, host=True)
    pool.cancel()
    pool.close()
    restarted = make()
    restarted.restore()
    assert restarted(ca.HOST_OWNER).ledger.root == first
    restarted.cancel()
    restarted.close()


def test_the_host_owner_is_never_a_submitter_and_is_not_an_ss58_address():
    import re
    from types import SimpleNamespace

    from carbon.challenge_validator.interface import Unavailable
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter

    assert not receiver.ADDRESS.fullmatch(ca.HOST_OWNER)
    assert not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{47,48}", ca.HOST_OWNER)
    fake = SimpleNamespace(require_registered_pool=lambda: None)
    with pytest.raises(Unavailable, match="direct_owner_reserved"):
        LeanRecipeAdapter.evaluate(
            fake, SimpleNamespace(hotkey=ca.HOST_OWNER, strategy={})
        )


# --- FIX 2: a decision the host could not make is retried, never lost ------------------------------------------------

t0 = 1_000_000.0


def _store(tmp_path, clock):
    state = tmp_path / "state"
    state.mkdir(mode=0o700, exist_ok=True)
    return PoolStore(state / "pool.sqlite3", clock=lambda: clock[0])


def _sweep(store, reconsider):
    return sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)


def outcome(kind, reason):
    return {"outcome": kind, "reason": reason, "evaluation_key": KEY_A}


UNDECIDED = [
    (bp.UNAVAILABLE, ca.REBUILD_UNAVAILABLE),
    (bp.UNAVAILABLE, bp.REPEAT_UNAVAILABLE),
    (bp.UNAVAILABLE, ca.MARGIN_UNREGISTERED),
    (bp.UNAVAILABLE, ca.KING_UNMEASURED),
    (bp.UNAVAILABLE, "incumbent_regrade_required"),
    (bp.FAILED_INFRA, bp.REPEAT_MISMATCH),
]


@posix
@pytest.mark.parametrize(("kind", "reason"), UNDECIDED)
def test_an_undecided_outcome_leaves_the_record_unresolved_and_is_never_a_no_crown(
    tmp_path, kind, reason
):
    clock = [t0]
    store = _store(tmp_path, clock)
    file_paused(store, "a", KEY_A)
    assert _sweep(store, lambda record: outcome(kind, reason)) == []
    assert [r["submission_id"] for r in store.paused_crowns()] == ["a"]
    assert store.crown_pause_resolved("a", KEY_A) is None
    assert store.crown_pause_attempts("a", KEY_A) == (1, t0)


@posix
def test_a_retry_is_at_most_once_per_epoch_and_a_third_failure_raises_a_typed_alert(
    tmp_path,
):
    clock = [t0]
    store = _store(tmp_path, clock)
    file_paused(store, "a", KEY_A)
    calls = []

    def host_down(record):
        calls.append(clock[0])
        return outcome(bp.UNAVAILABLE, ca.REBUILD_UNAVAILABLE)

    _sweep(store, host_down)
    for _tick in range(
        50
    ):  # a persistent fault ticking every few seconds burns nothing inside the epoch
        clock[0] += 60
        if clock[0] - t0 >= sweeper.EPOCH_SECONDS:
            break
        _sweep(store, host_down)
    assert calls == [t0]
    clock[0] = t0 + sweeper.EPOCH_SECONDS
    _sweep(store, host_down)
    assert len(calls) == 2 and store.crown_pause_alerts() == []
    clock[0] += sweeper.EPOCH_SECONDS
    _sweep(store, host_down)
    assert len(calls) == 3
    (alert,) = store.crown_pause_alerts()
    assert alert["code"] == "crown_decision_unavailable" and alert["attempts"] == 3
    assert alert["action"] == "recheck_validator_host" and alert["submission_id"] == "a"
    assert alert["last_code"] == f"UNAVAILABLE:{ca.REBUILD_UNAVAILABLE}"
    clock[0] += sweeper.EPOCH_SECONDS
    _sweep(store, host_down)  # a fourth failure: still one alert, still unresolved
    assert len(store.crown_pause_alerts()) == 1
    assert (
        store.crown_pause_resolved("a", KEY_A) is None
        and len(store.paused_crowns()) == 1
    )


@posix
def test_the_decision_is_made_once_the_host_recovers_and_then_resolves(tmp_path):
    clock = [t0]
    store = _store(tmp_path, clock)
    file_paused(store, "a", KEY_A)
    _sweep(store, lambda record: outcome(bp.FAILED_INFRA, bp.REPEAT_MISMATCH))
    clock[0] += sweeper.EPOCH_SECONDS
    done = _sweep(
        store,
        lambda record: decided(bp.CHALLENGER, "mean_exceeds_incumbent_beyond_margin"),
    )
    assert done == [("a", "CHALLENGER:mean_exceeds_incumbent_beyond_margin")]
    assert store.paused_crowns() == []


@posix
@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (bp.FIRST_INCUMBENT, ca.FIRST_BEATS_BASELINE),
        (bp.CHALLENGER, ca.MEAN_EXCEEDS),
        (bp.INCUMBENT_KEEPS, ca.MEAN_WITHIN),
        (bp.INCUMBENT_KEEPS, ca.UNSTABLE),
        (bp.NO_WINNER, ca.UNSTABLE),
        (bp.NO_WINNER, ca.WITHIN_BASELINE),
    ],
)
def test_only_decided_outcomes_resolve_including_unstable_across_seeds(
    tmp_path, kind, reason
):
    clock = [t0]
    store = _store(tmp_path, clock)
    file_paused(store, "a", KEY_A)
    assert _sweep(store, lambda record: outcome(kind, reason)) == [
        ("a", f"{kind}:{reason}")
    ]
    assert store.crown_pause_attempts("a", KEY_A) == (0, None)


@posix
def test_a_waiting_decision_holds_back_later_contenders_so_none_is_decided_ahead_of_it(
    tmp_path,
):
    clock = [t0]
    store = _store(tmp_path, clock)
    file_paused(store, "a", KEY_A)
    file_paused(store, "b", KEY_B)
    seen = []

    def reconsider(record):
        seen.append(record["submission_id"])
        return outcome(bp.UNAVAILABLE, ca.REBUILD_UNAVAILABLE)

    _sweep(store, reconsider)
    _sweep(store, reconsider)  # inside the epoch: a waits, b is not decided ahead of it
    assert seen == ["a"]


# --- the live trigger that hits infra keeps its screening grade filed ---------------------------------------------------


def _filed(store, kind, reason, *, entry="x"):
    class Repeat:
        pass

    repeat = Repeat()
    if entry is not None:
        repeat.entry_id = ENTRY
    retention._file_if_paused(
        store, outcome(kind, reason), "pack", "a", EXAM, repeat, PIN
    )
    return [r["submission_id"] for r in store.paused_crowns()]


@posix
@pytest.mark.parametrize(
    ("kind", "reason"), [u for u in UNDECIDED if u[1] != "incumbent_regrade_required"]
)
def test_a_live_trigger_that_hits_infra_files_its_screening_grade_for_retry(
    tmp_path, kind, reason
):
    store = _store(tmp_path, [t0])
    assert _filed(store, kind, reason) == ["a"]
    assert _filed(store, kind, reason) == ["a"]  # filing is idempotent
    assert (
        store.crown_pause_attempts("a", KEY_A)[0] == 2
    )  # each live failure is one attempt


@posix
@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (bp.CHALLENGER, ca.MEAN_EXCEEDS),
        (bp.INCUMBENT_KEEPS, ca.UNSTABLE),
        (bp.NO_WINNER, ca.WITHIN_BASELINE),
        (bp.UNAVAILABLE, "incumbent_regrade_required"),
    ],
)
def test_a_decided_or_unrelated_outcome_files_nothing(tmp_path, kind, reason):
    assert _filed(_store(tmp_path, [t0]), kind, reason) == []


@posix
def test_a_retryable_outcome_without_a_retained_entry_is_the_answer_not_an_error(
    tmp_path,
):
    store = _store(tmp_path, [t0])
    assert _filed(store, bp.UNAVAILABLE, ca.REBUILD_UNAVAILABLE, entry=None) == []
    with pytest.raises(
        retention.RetentionUnavailable, match="crown_paused_entry_unavailable"
    ):
        _filed(store, bp.UNAVAILABLE, bp.CROWNS_PAUSED, entry=None)


@posix
def test_end_to_end_a_triggered_decision_survives_a_host_outage_and_is_decided_later(
    tmp_path,
):
    from test_crown_average_wiring import (
        KEY,
        Repeat,
        _active,
        _body,
        _comparator,
        _pair,
        _Pairs,
    )

    from carbon.challenge_validator.interface import digest

    clock = [t0]
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = PoolStore(state / "pool.sqlite3", clock=lambda: clock[0])
    for model in ("a", "b"):
        store.admit(
            model,
            request_digest=digest(["request", model]),
            hotkey="fixture-" + model,
            challenge="electric-motor-magnetics",
            strategy={},
            binding={"challenge": {"id": "electric-motor-magnetics"}},
        )
    a = _body("a", 0.70)
    store.private_evaluation_pair = _Pairs({"a": _pair(a, None)})
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    average = _active(tmp_path)

    class Down(Repeat):
        def rebuild_at(self, seed):
            raise OSError("construction lane down")

    down = Down("a", [])
    down.entry_id = ENTRY
    first = flow.consider_private("a", KEY, _comparator(), repeat=down, average=average)
    assert (first["outcome"], first["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_UNAVAILABLE,
    )
    retention._file_if_paused(store, first, "pack", "a", EXAM, down, digest("pin"))
    assert [r["submission_id"] for r in store.paused_crowns()] == [
        "a"
    ] and store.incumbent() is None
    # the sweep tick inside the epoch decides nothing; the host recovers; the next epoch decides it
    up = Repeat("a", [0.70] * 10)
    up.entry_id = ENTRY

    def reconsider(record):
        return flow.consider_private(
            record["submission_id"],
            record["evaluation_key"],
            _comparator(),
            repeat=up,
            average=average,
        )

    sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)
    assert (
        store.incumbent() is None
    )  # the live failure was attempt one: the retry waits for its epoch
    assert store.crown_pause_attempts("a", KEY) == (1, t0)
    clock[0] += sweeper.EPOCH_SECONDS
    sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)
    assert store.incumbent() is not None and store.incumbent()["model_id"] == "a"
    assert store.paused_crowns() == []
