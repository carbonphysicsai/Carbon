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
    assert _stage(_ledger(tmp_path), catalog_recipe("neuralop.FNO"), door) is None
    assert door.calls == [] and not (tmp_path / dss.STAGED_GRAPHS).exists()


def test_first_stage_then_a_second_graph_replaces_it_by_compare_and_swap(tmp_path):
    ledger, door = _ledger(tmp_path), Door()
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
    ledger, door = _ledger(tmp_path), Door()
    _stage(ledger, _recipe(A), door)
    door.held = None  # a re-prepared door
    _stage(ledger, _recipe(B), door)
    assert door.held == B and door.calls[-2:] == [A, None]


def test_a_manifest_held_before_the_record_is_found_among_earlier_frozen_graphs(
    tmp_path,
):
    ledger, door = _ledger(tmp_path, _recipe(A), _recipe(B)), Door(held=A)
    _stage(ledger, _recipe(C), door)
    assert door.held == C and door.calls == [None, B, A]
    assert list(_recorded(ledger).values()) == [C]


def test_a_held_manifest_nobody_names_refuses_and_records_nothing(tmp_path):
    ledger, door = _ledger(tmp_path), Door(held=C)
    with pytest.raises(DirectIntakeRefusal, match="idempotency_conflict"):
        _stage(ledger, _recipe(A), door)
    assert door.held == C and not (tmp_path / dss.STAGED_GRAPHS).exists()


def test_another_refusal_stops_at_once(tmp_path):
    calls = []

    def refuse(*a, **k):
        calls.append(k["expected_manifest_digest"])
        raise DirectIntakeRefusal("construction_contract_binding_mismatch")

    with pytest.raises(DirectIntakeRefusal, match="binding_mismatch"):
        _stage(_ledger(tmp_path, _recipe(B)), _recipe(A), refuse)
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
    ledger = _ledger(tmp_path, recipe)
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
