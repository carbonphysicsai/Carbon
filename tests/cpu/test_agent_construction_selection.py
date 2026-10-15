"""Scripted agent SELECT preserves contract identity; no provider or chain.

Composition health is substituted only by the private existing fixture.
The real compiler, graph envelope validation and candidate builder are used.
"""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from composition_check_fixtures import accepted_fixture_checks
from test_battery_composed_graph import graph_input
from test_battery_composed_graph import strategy as graph_strategy
from test_cw1_research_ledger import ledger as fixture_ledger
from test_cw1_research_loop import response

from carbon.battery import campaign
from carbon.development_session import construction_level as cl
from carbon.development_session import research_loop as loop
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    GRAPHITE_MINER,
    PARALLEL_CALLS_V2,
    STOP,
    STOP_TOOL,
)
from carbon.development_session.research_campaign import OperationRefused
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.level4 import staging
from carbon.reconstruction import capability_registry as registry

__all__ = ["accepted_fixture_checks", "graph_input"]

BATTERY = registry.BATTERY_CHALLENGE
RECIPE = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "knn",
    "parameters": {"neighbours": 6},
}
URL = "http://127.0.0.1:9"


def meter(tmp_path, found=None):
    template = fixture_ledger(tmp_path / "template")
    with template.db() as db:
        manifest = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    manifest["challenge"] = {"id": BATTERY, "version": "1.0"}
    manifest["contract_digest"] = registry.contract_digest(BATTERY)
    if found is not None:
        manifest[cl.MANIFEST_KEY] = found
    value = CampaignLedger(tmp_path / "actual", clock=lambda: 1000)
    value.freeze(manifest)
    return value, manifest


def practiced(value, recipe):
    with value.db() as db:
        db.execute(
            "CREATE TABLE research_results(owner TEXT,task TEXT,body BLOB,digest TEXT)"
        )
        raw = canonical({"provenance": "BATTERY_PUBLIC_PRACTICE", "recipe": recipe})
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("alice", "fixture", raw, digest(raw)),
        )


def bound(kind="composition"):
    found = (
        cl.resolve_composition(BATTERY)
        if kind == "composition"
        else cl.resolve(BATTERY, 4)
    )
    return cl.with_target(found, URL)


def serves(monkeypatch, found):
    monkeypatch.setattr(cl, "READ_TARGET", lambda *args: {"served_contracts": [found]})
    cl._compiled.cache_clear()


def run_selection(value, recipe, calls):
    def transport(request):
        calls.append(request)
        selecting = len(calls) == 1
        arguments = (
            {
                "strategy_json": json.dumps(recipe),
                "reason": "fixture comparison",
                "used_feedback": True,
            }
            if selecting
            else {
                "reason": "no_feasible_action",
                "evidence": "fixture refusal observed",
                "used_feedback": False,
            }
        )
        return response(
            [
                {
                    "type": "function_call",
                    "name": loop.SELECT if selecting else STOP,
                    "call_id": "fixture-" + str(len(calls)),
                    "arguments": json.dumps(arguments),
                }
            ]
        )

    return asyncio.run(
        loop.run_epoch(
            value,
            owner="alice",
            epoch=1,
            sdk=None,
            credential_file=None,
            initial_observation={"fixture": True},
            transport=transport,
            agent_policy=GRAPHITE_MINER,
            parallel_calls=PARALLEL_CALLS_V2,
            instructions="Deterministic fixture: select the practiced recipe.",
            tools=[loop.SELECTION_TOOL, STOP_TOOL],
        )
    )


@pytest.mark.parametrize("kind", ["composition", "standalone"])
def test_actual_agent_select_keeps_contract_for_plain_recipe(
    tmp_path, monkeypatch, accepted_fixture_checks, kind
):
    found = bound(kind)
    serves(monkeypatch, found)
    value, manifest = meter(tmp_path, found)
    practiced(value, RECIPE)
    calls = []
    result = run_selection(value, RECIPE, calls)
    assert result["status"] == "SELECTED"
    folder = value.root / "epoch-1"
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    assert selected["status"] == "SELECTED"
    assert selected["strategy"] == RECIPE
    assert selected["contract_digest"] == found["digest"]
    assert selected[cl.MANIFEST_KEY]["digest"] == found["digest"]
    if kind == "composition":
        assert selected[cl.MANIFEST_KEY]["level"] == 0
        assert selected[cl.MANIFEST_KEY]["changes"] == []
    assert {key: result[key] for key in selected} == selected
    assert result["schema"] == "carbon.autoresearch.epoch-outcome.v1"
    assert not (folder / cl.LEVEL4_ENVELOPE).exists()
    campaign._level_record_bound(SimpleNamespace(manifest=manifest), selected)
    # Commitment still recomputes the compiled contract; no signer is involved.
    assert campaign.frozen_commitment(selected, manifest)
    epoch_plan = json.loads((folder / "plan.json").read_bytes())
    observed = epoch_plan["initial_observation"]["construction_contract"]
    assert observed["digest"] == found["digest"]
    assert "not permissions" in observed["basis"]
    # Historical outcomes replay without another model call or re-freezing.
    assert run_selection(value, RECIPE, calls) == result
    assert len(calls) == 1
    for mutation in ("missing", "wrong"):
        broken = copy.deepcopy(selected)
        if mutation == "missing":
            del broken[cl.MANIFEST_KEY]
        else:
            broken["contract_digest"] = registry.contract_digest(BATTERY)
        with pytest.raises(OperationRefused, match="level_not_registered"):
            campaign._level_record_bound(SimpleNamespace(manifest=manifest), broken)


def test_unbound_base_agent_selection_is_unchanged(tmp_path):
    value, _ = meter(tmp_path)
    practiced(value, RECIPE)
    result = run_selection(value, RECIPE, [])
    expected = loop.candidate_record(RECIPE, "fixture comparison", True)
    selected = json.loads(
        (value.root / "epoch-1" / "selected-recipe.json").read_bytes()
    )
    assert selected == expected
    assert {key: result[key] for key in expected} == expected
    assert result["schema"] == "carbon.autoresearch.epoch-outcome.v1"
    plan = json.loads((value.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["initial_observation"] == {"fixture": True}


@pytest.mark.parametrize("bad", [None, {}, "model-supplied-binding"])
def test_malformed_frozen_binding_cannot_silently_become_base(tmp_path, bad):
    value, manifest = meter(tmp_path)
    manifest[cl.MANIFEST_KEY] = bad
    with value.db() as db:
        db.execute(
            "UPDATE campaign SET manifest=?,digest=?",
            (canonical(manifest), digest(canonical(manifest))),
        )
    calls = []
    with pytest.raises(ValueError, match="binding is malformed"):
        run_selection(value, RECIPE, calls)
    assert calls == []
    assert not (value.root / "epoch-1" / "selected-recipe.json").exists()


def test_contract_compile_mismatch_is_a_selection_refusal(tmp_path, monkeypatch):
    found = bound("standalone")
    serves(monkeypatch, found)
    value, _ = meter(tmp_path, found)
    practiced(value, RECIPE)
    monkeypatch.setattr(
        cl,
        "RUN",
        lambda request: {
            "variant": found["variant"],
            "variant_digest": "sha256:" + "0" * 64,
        },
    )
    result = run_selection(value, RECIPE, [])
    assert result["status"] == "STOPPED"
    refused = json.loads(
        (value.root / "epoch-1" / "epoch-1-tool-000-result.json").read_bytes()
    )
    assert refused["code"] == loop.CANDIDATE_INVALID
    assert refused["construction_code"] == "level_not_registered"
    assert not (value.root / "epoch-1" / "selected-recipe.json").exists()


def test_graph_selection_requires_real_workspace_documents(
    tmp_path, monkeypatch, accepted_fixture_checks, graph_input
):
    found = bound()
    serves(monkeypatch, found)
    recipe = graph_strategy(composition_graphs=graph_input[0])
    value, _ = meter(tmp_path, found)
    practiced(value, recipe)
    result = run_selection(value, recipe, [])
    assert result["status"] == "STOPPED"
    refused = json.loads(
        (value.root / "epoch-1" / "epoch-1-tool-000-result.json").read_bytes()
    )
    assert refused["construction_code"] == "level4_submission_refused"
    assert not (value.root / "epoch-1" / "selected-recipe.json").exists()
    assert not (value.root / "epoch-1" / cl.LEVEL4_ENVELOPE).exists()


def test_graph_select_validates_and_retains_exact_envelope(
    tmp_path, monkeypatch, accepted_fixture_checks, graph_input
):
    found = bound()
    serves(monkeypatch, found)
    recipe = graph_strategy(composition_graphs=graph_input[0])
    value, manifest = meter(tmp_path, found)
    practiced(value, recipe)
    workspace = ResearchWorkspace(value, "alice")
    for name, raw in graph_input[1].items():
        workspace.put(name, raw)
    result = run_selection(value, recipe, [])
    assert result["status"] == "SELECTED"
    folder = value.root / "epoch-1"
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    assert selected["strategy"] == recipe
    assert selected["contract_digest"] == found["digest"]
    assert selected[cl.MANIFEST_KEY]["digest"] == found["digest"]
    retained = cl.read_envelope(folder, selected)
    raw, files = staging.from_workspace(graph_input[1], graph_input[0])
    assert staging.from_envelope(retained) == (graph_input[0], raw, files)
    campaign._level_record_bound(SimpleNamespace(manifest=manifest), selected)
    assert not list(value.root.glob("agent-graph-*"))


def test_unpracticed_recipe_is_not_written_under_bound_contract(
    tmp_path, monkeypatch, accepted_fixture_checks
):
    found = bound()
    serves(monkeypatch, found)
    value, _ = meter(tmp_path, found)
    result = run_selection(value, RECIPE, [])
    assert result["status"] == "STOPPED"
    assert not (value.root / "epoch-1" / "selected-recipe.json").exists()
