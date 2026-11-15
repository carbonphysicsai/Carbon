"""EVERY ROUTE STAGES A GRAPH BEFORE ITS SUBMIT (Lead 3 Nov: the 947cf36c fix covered only the direct campaign; Motor
and Cooling submitted unstaged and refused construction_recipe_graph_workspace_missing).

Claims: `stage_graph_source` stages a graph recipe and records its manifest per receiver door; a catalog recipe stages
nothing; a SECOND, different graph replaces the held one by compare-and-swap with the recorded manifest; a door that lost
its manifest is staged afresh; a manifest held from before the record is found among the campaign's earlier frozen graph
recipes; a held manifest nobody names refuses with the receiver's conflict and records nothing; identical bytes are a
no-op. Motor, Cooling and the direct F08 route each stage first, then submit.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.challenge_registry.campaigns import campaign_for
from carbon.development_session import direct_source_submission as dss
from carbon.development_session import direct_submission, graph_adapters
from carbon.development_session.direct_submission import DirectIntakeRefusal

URL = "http://127.0.0.1:8769"
RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
MOTOR, COOLING, F08 = (
    "electric-motor-magnetics",
    "chip-cold-plate",
    "f08-ribbed-bracket",
)
A, B, C = ("sha256:" + c * 64 for c in "abc")


class Door:
    """The receiver's staging rule for the workspace manifest (`direct_source_staging.stage_source`)."""

    def __init__(self, held=None):
        self.held, self.calls = held, []

    def __call__(self, url, signer, *, recipe, expected_manifest_digest, **kw):
        new = recipe.to_dict()["source"]["submission_digest"]
        self.calls.append(expected_manifest_digest)
        if self.held != new:
            if self.held != expected_manifest_digest:
                raise DirectIntakeRefusal(
                    "construction_source_reference_not_found"
                    if self.held is None
                    else "construction_source_idempotency_conflict"
                )
            self.held = new
        return {"manifest_digest": new, "complete": True}


def _recipe(digest, key=(MOTOR, "1.5")):
    return graph_adapters.graph_recipe(*key, digest)


def _ledger(tmp_path, *frozen):
    tmp_path.mkdir(parents=True, exist_ok=True)
    for epoch, recipe in enumerate(frozen, 1):
        folder = tmp_path / f"epoch-{epoch}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "selected-recipe.json").write_text(json.dumps({"strategy": recipe}))
    return SimpleNamespace(root=tmp_path)


def _stage(ledger, recipe, door):
    return dss.stage_graph_source(
        URL,
        object(),
        ledger=ledger,
        owner="alice",
        recipe=recipe,
        contract_digest="sha256:" + "0" * 64,
        receiver=RECEIVER,
        context=object(),
        stage=door,
    )


def _recorded(ledger):
    return json.loads((ledger.root / dss.STAGED_GRAPHS).read_bytes())["doors"]


def test_a_catalog_recipe_stages_nothing(tmp_path):
    from carbon.challenge_registry.motor import catalog_recipe

    door = Door()
    assert (
        _stage(_ledger(tmp_path / "solo"), catalog_recipe("neuralop.FNO"), door) is None
    )
    assert door.calls == [] and not (tmp_path / "solo" / dss.STAGED_GRAPHS).exists()


def test_first_stage_then_a_second_graph_replaces_it_by_compare_and_swap(tmp_path):
    ledger, door = _ledger(tmp_path / "solo"), Door()
    assert _stage(ledger, _recipe(A), door)["manifest_digest"] == A
    assert door.calls == [None] and list(_recorded(ledger).values()) == [A]
    _stage(ledger, _recipe(B), door)
    assert (
        door.held == B and door.calls[-1] == A
    )  # the recorded manifest is the expectation
    assert list(_recorded(ledger).values()) == [B]
    calls = len(door.calls)
    _stage(ledger, _recipe(B), door)  # identical bytes: a no-op, still recorded
    assert door.held == B and len(door.calls) == calls + 1


def test_a_door_that_lost_its_manifest_is_staged_afresh(tmp_path):
    ledger, door = _ledger(tmp_path / "solo"), Door()
    _stage(ledger, _recipe(A), door)
    door.held = None  # a re-prepared door
    _stage(ledger, _recipe(B), door)
    assert door.held == B and door.calls[-2:] == [A, None]


def test_a_manifest_held_before_the_record_is_found_among_earlier_frozen_graphs(
    tmp_path,
):
    ledger, door = _ledger(tmp_path / "solo", _recipe(A), _recipe(B)), Door(held=A)
    _stage(ledger, _recipe(C), door)
    assert door.held == C and door.calls == [None, B, A]
    assert list(_recorded(ledger).values()) == [C]


def test_a_held_manifest_nobody_names_refuses_and_records_nothing(tmp_path):
    ledger, door = _ledger(tmp_path / "solo"), Door(held=C)
    with pytest.raises(DirectIntakeRefusal, match="idempotency_conflict"):
        _stage(ledger, _recipe(A), door)
    assert door.held == C and not (tmp_path / "solo" / dss.STAGED_GRAPHS).exists()


def test_another_refusal_stops_at_once(tmp_path):
    calls = []

    def refuse(*a, **k):
        calls.append(k["expected_manifest_digest"])
        raise DirectIntakeRefusal("construction_contract_binding_mismatch")

    with pytest.raises(DirectIntakeRefusal, match="binding_mismatch"):
        _stage(_ledger(tmp_path / "solo", _recipe(B)), _recipe(A), refuse)
    assert calls == [None]


ROUTES = [
    ((MOTOR, "1.5"), {MOTOR: URL}, {MOTOR: RECEIVER}),
    ((COOLING, "1.6"), {COOLING: URL}, {COOLING: RECEIVER}),
]


@pytest.mark.parametrize("key, intakes, receivers", ROUTES, ids=lambda v: str(v))
def test_motor_and_cooling_stage_a_graph_before_its_submit(
    tmp_path, monkeypatch, key, intakes, receivers
):
    order = []
    monkeypatch.setattr(
        dss,
        "stage_graph",
        lambda url, key, **kw: order.append("stage") or {"manifest_digest": A},
    )
    monkeypatch.setattr(
        direct_submission,
        "submit_and_wait",
        lambda url, k, **kw: order.append("submit") or {"state": "RECONSTRUCTED"},
    )
    monkeypatch.setattr(
        direct_submission, "read_exam_feedback", lambda url, k, **kw: {"best": None}
    )
    recipe = _recipe(A, key)
    campaign = campaign_for({"id": key[0], "version": key[1]})
    from carbon.cold_plate import campaign as cooling
    from carbon.motor import campaign as motor

    for module in (motor, cooling):
        monkeypatch.setattr(module, "record_verdict", lambda *a: None)
    ledger = _ledger(tmp_path / "solo", recipe)
    prepared = SimpleNamespace(
        ledger=ledger,
        owner="alice",
        args=SimpleNamespace(intakes=intakes, receivers=receivers),
        sdk=SimpleNamespace(
            connection=SimpleNamespace(miner_key=object(), chain_context=object())
        ),
    )
    asyncio.run(campaign.evaluate(prepared, 1, recipe))
    assert order == ["stage", "submit"]


# --- a manifest staged from an EARLIER campaign of the same miner (Lead 15 Nov, UID 269) ----------------------------


def _campaign(campaigns, name, *frozen, staged=None, mtime=None):
    """A campaign root on this host: ``campaign.sqlite3`` present, its frozen graph recipes, its staged-door record."""
    import os

    root = campaigns / name
    root.mkdir(parents=True)
    (root / "campaign.sqlite3").write_bytes(b"")
    ledger = _ledger(root, *frozen)
    if staged is not None:
        (root / dss.STAGED_GRAPHS).write_text(
            json.dumps({"schema": dss.STAGED_GRAPHS_SCHEMA, "doors": staged})
        )
    if mtime is not None:
        os.utime(root, (mtime, mtime))
    return ledger


def _key(recipe, url=URL, owner="alice"):
    from carbon.development_session.construction_recipe import ConstructionRecipe

    return dss._door_key(url, RECEIVER, ConstructionRecipe.from_dict(recipe), owner)


def test_a_new_campaign_finds_the_manifest_its_earlier_campaign_staged(tmp_path):
    """The UID 269 shape: campaign 1 staged and froze A at this door; campaign 2 (new ledger, nothing recorded, no
    earlier epochs) stages B. Its own candidates cannot name A; its sibling's record does.
    """
    campaigns = tmp_path / "campaigns"
    _campaign(campaigns, "first", _recipe(A), staged={_key(_recipe(A)): A})
    second = _campaign(campaigns, "second")
    door = Door(held=A)
    assert _stage(second, _recipe(B), door)["manifest_digest"] == B
    assert door.held == B and door.calls == [None, A]
    assert list(_recorded(second).values()) == [B]


def test_a_sibling_frozen_graph_is_offered_when_it_recorded_nothing(tmp_path):
    campaigns = tmp_path / "campaigns"
    _campaign(
        campaigns, "first", _recipe(C)
    )  # froze C, no staged record (staged before the record existed)
    second = _campaign(campaigns, "second")
    door = Door(held=C)
    _stage(second, _recipe(A), door)
    assert door.held == A and door.calls == [None, C]


def test_only_the_same_door_key_and_challenge_are_offered_and_nothing_held_stays_last(
    tmp_path,
):
    campaigns = tmp_path / "campaigns"
    cooling = _recipe(C, key=(COOLING, "1.5"))
    _campaign(
        campaigns,
        "other",
        cooling,  # another Challenge: never offered
        staged={
            _key(_recipe(A), url="http://elsewhere:1"): A,
            _key(_recipe(A), owner="bob"): B,  # another owner's key
            _key(_recipe(A)): "not-a-digest",
        },
    )
    second = _campaign(campaigns, "second")
    door = Door(held="sha256:" + "d" * 64)
    with pytest.raises(DirectIntakeRefusal, match="idempotency_conflict"):
        _stage(second, _recipe(A), door)
    assert door.calls == [
        None
    ]  # nothing from the other door, owner, Challenge or a malformed record
    assert not (second.root / dss.STAGED_GRAPHS).exists()


def test_siblings_are_bounded_newest_first_and_a_broken_one_is_skipped(
    tmp_path, monkeypatch
):
    campaigns = tmp_path / "campaigns"
    monkeypatch.setattr(dss, "SIBLING_CAMPAIGNS", 3)
    digests = ["sha256:" + f"{n:064x}" for n in range(1, 5)]
    for n, digest in enumerate(digests):
        _campaign(
            campaigns,
            f"c{n}",
            staged={_key(_recipe(digest)): digest},
            mtime=1_000_000 + n,
        )
    (campaigns / "broken").mkdir()
    (campaigns / "broken" / "campaign.sqlite3").write_bytes(b"")
    (campaigns / "broken" / dss.STAGED_GRAPHS).write_text("{not json")
    import os

    os.utime(campaigns / "broken", (1_000_002.5, 1_000_002.5))  # between the two newest
    current = _campaign(campaigns, "current", mtime=1)
    door = Door(
        held=digests[0]
    )  # held by the OLDEST sibling: beyond the bound, so never named
    with pytest.raises(DirectIntakeRefusal, match="idempotency_conflict"):
        _stage(current, _recipe(A), door)
    # the three newest siblings, newest first: c3, the broken one (adds nothing), c2; c1 and c0 are beyond the bound
    assert door.calls[1:] == [digests[3], digests[2]]
    assert digests[0] not in door.calls and digests[1] not in door.calls


def test_a_stage_its_own_candidates_settle_never_reads_other_campaigns(
    tmp_path, monkeypatch
):
    def forbidden(*args):
        raise AssertionError(
            "other campaigns were read before this campaign's own candidates were refused"
        )

    monkeypatch.setattr(dss, "_sibling_manifests", forbidden)
    ledger, door = _ledger(tmp_path / "solo", _recipe(A), _recipe(B)), Door(held=A)
    _stage(ledger, _recipe(C), door)
    assert door.calls == [None, B, A]


def test_a_siblings_exact_record_is_never_crowded_out_by_newer_siblings_guesses(
    tmp_path,
):
    campaigns = tmp_path / "campaigns"
    held = "sha256:" + "e" * 64
    _campaign(campaigns, "oldest", staged={_key(_recipe(held)): held}, mtime=1_000_000)
    for n in range(
        2
    ):  # two newer campaigns, each with 8 frozen Motor graphs (16 guesses)
        frozen = [_recipe("sha256:" + f"{n:02x}{i:062x}") for i in range(8)]
        _campaign(campaigns, f"newer{n}", *frozen, mtime=1_000_010 + n)
    current = _campaign(campaigns, "current", mtime=1)
    door = Door(held=held)
    _stage(current, _recipe(A), door)
    assert door.held == A and door.calls[:2] == [
        None,
        held,
    ]  # the record first, before any guess


def test_an_error_reading_other_campaigns_never_breaks_the_stage(tmp_path, monkeypatch):
    def broken(*args):
        raise RecursionError("deeply nested json")

    monkeypatch.setattr(dss, "_sibling_manifests", broken)
    ledger, door = _ledger(tmp_path / "solo"), Door(held=C)
    with pytest.raises(DirectIntakeRefusal, match="idempotency_conflict"):
        _stage(ledger, _recipe(A), door)  # exactly the refusal it gave before
