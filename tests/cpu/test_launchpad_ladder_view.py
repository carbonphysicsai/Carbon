"""A Challenge's construction levels in the Launchpad, from data (LAUNCHPAD-LEVELS-01 S1).

OWNER-LADDER-THROUGH-LAUNCHPAD-01: construction levels go into the Launchpad
generically and from data, on both doors, with no level's own screens or
code. S1 shows them, read only. These tests hold that:
- fixture ladders for levels 0-3 are drawn by the same code from the same
  keys, and an empty level shows what it leaves out;
- DEVELOPMENT is relative to the target deployment's own level, and
  MINER_FACING only where the ladder record names the level chosen;
- a contract with no compute budget shows NOT_SET, never a value;
- the browser and MCP doors give the same payload;
- the real battery data renders, with each registered variant's identity
  equal to the variant module's own lookup, and a tampered document is named
  with its refusal and widens nothing;
- the Contract view's construction_level is filled from the ladder, and stays
  NOT_YET_DEFINED for a Challenge without ladder data.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.dev.miner_launchpad import ladder_view

BATTERY = "battery-fastcharge-ageing-development-v1"
ROOT = Path(__file__).resolve().parents[2]
LEVEL_KEYS = {
    "level",
    "text",
    "state",
    "audience",
    "proposal_status",
    "capabilities",
    "left_out",
    "variant",
    "arms",
    "variant_refusal",
    "compute_budget",
}


def _proposal(level, ids, left_out=()):
    return {
        "status": "ACCEPTED",
        "capabilities": [
            {"id": i, "adds": f"adds {i}", "bounds": f"bounds of {i}"} for i in ids
        ],
        "left_out": list(left_out),
    }


def _variant(level, name, widened, arm=None):
    return {
        "name": name,
        "digest": "sha256:" + format(level, "x") * 64,
        "arm": arm,
        "status": "FIXTURE_NOT_PRODUCTION",
        "scope": ladder_view.VARIANT_SCOPE,
        "refusal": None,
        "widened": [
            {
                "id": i,
                "summary": f"widens {i}",
                "surface": {
                    "group": "train",
                    "kind": "choice",
                    "minimum_or_choices": ["a", "b"],
                    "maximum": None,
                    "default": "a",
                },
                "applies_to": ["mlp"],
                "bounds": {"menu": ["a", "b"]},
            }
            for i in widened
        ],
    }


def fixture_sources(chosen=1, budget=None):
    """A ladder climbed to Level 3: levels 0-2 TESTED, 3 OPEN."""
    return {
        "construction": {
            "challenge": "fixture-ladder-v1",
            "level": 3,
            "chosen": chosen,
            "levels": [
                {"level": n, "state": "TESTED" if n < 3 else "OPEN"} for n in range(4)
            ],
        },
        "proposals": {
            0: _proposal(0, ["model_family.mlp", "optimizer.learning_rate"]),
            1: _proposal(
                1, ["objective.relative_loss"], ["objective.code is excluded"]
            ),
            2: _proposal(2, ["optimizer.optimizer_family"]),
            3: _proposal(3, [], ["Level 3 adds nothing for this fixture."]),
        },
        "variants": {
            1: [
                _variant(
                    1, "fixture-l1-v1", ["objective.relative_loss", "objective.extra"]
                ),
                _variant(1, "fixture-l1-arm-v1", ["objective.armed"], arm="armed"),
            ],
            2: [_variant(2, "fixture-l2-v1", ["optimizer.new_rule"])],
            3: [_variant(3, "fixture-l3-v1", ["numerics.menu"])],
        },
        "compute_budget": budget or {"status": "NOT_SET"},
    }


# ---- Fixture ladders: generic, from data.


def test_fixture_levels_0_to_3_render_with_one_shape():
    view = ladder_view.build("fixture-ladder-v1", fixture_sources())
    assert view["status"] == ladder_view.ON_LADDER
    assert view["ladder"] == {"level": 3, "chosen": 1}
    assert [row["level"] for row in view["levels"]] == [0, 1, 2, 3, 4, 5]
    for row in view["levels"]:
        assert set(row) == LEVEL_KEYS
    states = [row["state"] for row in view["levels"]]
    assert states == ["TESTED", "TESTED", "TESTED", "OPEN", "NOT_RUN", "NOT_RUN"]
    from carbon.challenge_pipeline.ladder import LEVELS

    assert [row["text"] for row in view["levels"]] == [LEVELS[n] for n in range(6)]
    zero, one, two, three = view["levels"][:4]
    assert [c["id"] for c in zero["capabilities"]] == [
        "model_family.mlp",
        "optimizer.learning_rate",
    ]
    assert zero["variant"] is None and zero["variant_refusal"] is None
    # A proposal capability a variant widens is one row with both parts; a
    # widened-only capability follows; an arm's is marked with its arm.
    ids = [c["id"] for c in one["capabilities"]]
    assert ids == ["objective.relative_loss", "objective.extra", "objective.armed"]
    merged = one["capabilities"][0]
    assert merged["proposal"] == {
        "adds": "adds objective.relative_loss",
        "bounds": "bounds of objective.relative_loss",
    }
    assert [w["variant"] for w in merged["widened"]] == ["fixture-l1-v1"]
    assert merged["widened"][0]["bounds"] == {"menu": ["a", "b"]}
    assert one["capabilities"][1]["proposal"] is None
    assert one["capabilities"][2]["widened"][0]["arm"] == "armed"
    assert one["variant"]["name"] == "fixture-l1-v1" and one["variant"]["arm"] is None
    assert [a["arm"] for a in one["arms"]] == ["armed"]
    assert two["variant"]["name"] == "fixture-l2-v1"
    assert three["variant"]["name"] == "fixture-l3-v1"
    # Level 4 may hold a variant (graph-only) but the fixture registers none;
    # Level 5 shows the registry's refusal, not content.
    four, five = view["levels"][4:]
    for row in (four, five):
        assert row["variant"] is None and row["capabilities"] == []
    assert four["variant_refusal"] == ladder_view.UNREGISTERED
    assert five["variant_refusal"] == ladder_view.NEEDS_ISOLATION


def test_an_empty_level_shows_what_it_leaves_out():
    sources = fixture_sources()
    sources["variants"].pop(3)
    three = ladder_view.build("fixture-ladder-v1", sources)["levels"][3]
    assert three["capabilities"] == []
    assert three["left_out"] == ["Level 3 adds nothing for this fixture."]
    assert three["variant_refusal"] == ladder_view.UNREGISTERED


def test_development_is_relative_to_the_deployments_own_level():
    def audiences(deployment_level, chosen=1):
        view = ladder_view.build(
            "fixture-ladder-v1", fixture_sources(chosen), deployment_level
        )
        assert view["deployment_level"] == deployment_level
        return [row["audience"] for row in view["levels"]]

    M, D, N = ladder_view.MINER_FACING, ladder_view.DEVELOPMENT, ladder_view.NOT_OFFERED
    assert audiences(None) == [N, M, N, N, N, N]
    assert audiences(1) == [N, M, D, D, D, D]
    assert audiences(2) == [N, M, N, D, D, D]
    assert audiences(0, chosen=None) == [N, D, D, D, D, D]
    # Nothing is miner-facing unless the ladder record names it chosen.
    assert M not in audiences(None, chosen=None)


def test_without_a_compute_budget_the_view_shows_not_set():
    view = ladder_view.build("fixture-ladder-v1", fixture_sources())
    assert {json.dumps(r["compute_budget"]) for r in view["levels"]} == {
        json.dumps({"status": "NOT_SET"})
    }
    budget = {"status": "SET", "unit": "flops", "value": 10}
    view = ladder_view.build("fixture-ladder-v1", fixture_sources(budget=budget))
    assert all(r["compute_budget"] == budget for r in view["levels"])


def test_a_challenge_without_a_ladder_record_is_not_yet_defined():
    sources = {**fixture_sources(), "construction": None}
    view = ladder_view.build("fixture-ladder-v1", sources)
    assert view["status"] == ladder_view.NOT_YET_DEFINED and view["ladder"] is None
    assert {row["state"] for row in view["levels"]} == {"NOT_RUN"}
    assert ladder_view.MINER_FACING not in {row["audience"] for row in view["levels"]}


# ---- The real battery data.


def test_the_battery_ladder_renders_from_its_data():
    view = ladder_view.ladder_view(BATTERY)
    assert view["status"] == ladder_view.ON_LADDER
    assert view["ladder"] == {"level": 0, "chosen": None}
    zero, one, two, three, four, five = view["levels"]
    assert zero["state"] == "OPEN" and zero["audience"] == ladder_view.NOT_OFFERED
    assert len(zero["capabilities"]) == 48 and zero["variant"] is None
    assert one["variant"]["name"] == "battery-l1-loss-expressions-v1"
    assert [a["name"] for a in one["arms"]] == ["battery-l1-loss-expressions-signed-v1"]
    assert [a["arm"] for a in one["arms"]] == ["signed"]
    widened = {c["id"]: c for c in one["capabilities"] if c["widened"]}
    assert "objective.loss_expressions" in widened
    assert two["variant"]["name"] == "battery-l2-spectral-v1"
    muon = {c["id"]: c for c in two["capabilities"]}["optimizer.muon_spectral"]
    assert muon["proposal"] is None
    assert muon["widened"][0]["surface"]["kind"] == "bool"
    assert muon["widened"][0]["bounds"]["interpretation"] == "specmuon-carbon-v1"
    assert three["variant"]["name"] == "battery-l3-numerics-v1"
    quasi = {c["id"]: c for c in three["capabilities"]}["numerics.quasi_newton_family"]
    assert quasi["widened"][0]["surface"]["minimum_or_choices"] == [
        "lbfgs",
        "bfgs",
        "ssbfgs",
        "ssbroyden",
    ]
    assert three["left_out"]  # the accepted proposal adds nothing itself
    assert four["variant"]["name"] == "battery-l4-graph-v2"
    assert four["variant"]["scope"] == ladder_view.VARIANT_SCOPE
    assert four["variant"]["status"] == "REGISTERED_DEVELOPMENT_POLICY"
    graphs = [c for c in four["capabilities"] if c["widened"]]
    assert [c["id"] for c in graphs] == ["hybrid.composition_graphs"]
    assert graphs[0]["widened"][0]["surface"] is None
    assert graphs[0]["widened"][0]["bounds"]["admission"] == "graph_only"
    for row in (one, two, three, four):
        assert row["state"] == "NOT_RUN" and row["variant_refusal"] is None
    assert five["variant_refusal"] == ladder_view.NEEDS_ISOLATION
    assert five["variant"] is None
    assert {json.dumps(r["compute_budget"]) for r in view["levels"]} == {
        json.dumps({"status": "NOT_SET"})
    }


def test_the_views_variant_identities_are_the_variant_modules_own():
    """This miner surface reads the registry as data; the variant module's
    own lookup agrees on every identity and code."""
    from carbon.reconstruction import development_variants as dv

    assert ladder_view.VARIANT_LEVELS == dv.LEVELS
    assert ladder_view.VARIANT_SCOPE == dv.SCOPE
    for name in (
        "UNREGISTERED",
        "NEEDS_ISOLATION",
        "BASE_STALE",
        "ALTERED",
        "MALFORMED",
    ):
        assert getattr(ladder_view, name) == getattr(dv, name), name
    view = ladder_view.ladder_view(BATTERY)
    registry = dv.load()
    for row in view["levels"][1:5]:
        found = dv.variant(BATTERY, row["level"])
        assert (row["variant"]["name"], row["variant"]["digest"]) == (
            found.version,
            found.digest,
        )
        arms = [
            arm
            for (c, level, _), arm in registry.arms.items()
            if (c, level) == (BATTERY, row["level"])
        ]
        expected = set(found.permissions()).union(*(a.permissions() for a in arms))
        assert {c["id"] for c in row["capabilities"] if c["widened"]} == expected
        for arm in row["arms"]:
            other = dv.variant(BATTERY, row["level"], arm["arm"])
            assert (arm["name"], arm["digest"]) == (other.version, other.digest)


def test_a_tampered_variant_is_named_with_its_refusal_and_widens_nothing(
    tmp_path, monkeypatch
):
    from carbon.reconstruction import capability_registry as cr

    copy = tmp_path / "policies"
    shutil.copytree(cr.DEVELOPMENT_VARIANT_DIR, copy)
    path = copy / "battery-l2-spectral-v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["widened"][0]["bounds"]["constants"]["top_modes"] = 9
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(cr, "DEVELOPMENT_VARIANT_DIR", copy)
    sources = ladder_view.read_sources(BATTERY)
    two = ladder_view.build(BATTERY, sources)["levels"][2]
    assert two["variant_refusal"] == ladder_view.ALTERED
    assert two["variant"]["refusal"] == ladder_view.ALTERED
    assert all(not c["widened"] for c in two["capabilities"])
    assert "optimizer.muon_spectral" not in {c["id"] for c in two["capabilities"]}


# ---- The operation, on both doors.


def test_the_ladder_operation_reads_only():
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    op = OPERATIONS["ladder"]
    assert op.admits_work is False
    assert op.gates == OPERATIONS["options"].gates == ("request", "profile")
    assert op.required == {"challenge"} and op.optional == {"challenge_version"}


def test_unknown_and_variant_names_are_refused():
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad.controller import Rejected

    for name in ("no-such-challenge-v1", "battery-l2-spectral-v1"):
        with pytest.raises(Rejected) as refused:
            ladder_view.for_request({"challenge": name})
        assert refused.value.code == "challenge_unknown"
    with pytest.raises(Rejected) as refused:
        ladder_view.for_request({"challenge": BATTERY, "challenge_version": "0.0.0-no"})
    assert refused.value.code == "challenge_unknown"
    version = challenge_ref(BATTERY)["version"]
    value = ladder_view.for_request(
        {"challenge": BATTERY, "challenge_version": version}
    )
    assert value["version"] == version and value["challenge"] == BATTERY


@pytest.fixture
def browser(tmp_path):
    from scripts.dev.miner_launchpad import controller as launchpad

    def serve(host):
        server = launchpad.Server(
            launchpad.Controller(tmp_path / "launchpad.sqlite3"),
            "x" * 40,
            port=0,
            research_runner=host,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    servers = []
    yield serve
    for server in servers:
        server.shutdown()
        server.server_close()


def test_both_doors_give_the_same_ladder(browser):
    from test_miner_launchpad import auth, request

    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from scripts.dev.miner_launchpad.operations import perform
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner

    ladder_view.ladder_view(BATTERY)  # read once, so the doors answer in time
    host = FixtureRunner()
    code, _, content = request(
        browser(host),
        "/api/v1/operations/ladder",
        "POST",
        {"challenge": BATTERY},
        auth(),
    )
    tool = {t.name: t for t in make_operation_tools(host)}["carbon_ladder"]
    mcp = asyncio.run(tool.fn(challenge=BATTERY)).payload
    assert code == 200, content
    assert json.loads(content) == mcp == perform(host, "ladder", {"challenge": BATTERY})
    assert mcp["levels"][2]["variant"]["name"] == "battery-l2-spectral-v1"


# ---- The Contract view's slot.


def test_the_contract_slot_is_filled_from_the_ladder():
    slot = ladder_view.construction_slot(BATTERY)
    assert {"level", "status", "basis"} <= set(slot)
    assert slot["level"] == ladder_view.CAMPAIGN_LEVEL == 0
    assert slot["status"] == "DEFINED"
    assert slot["state"] == "OPEN" and slot["audience"] == ladder_view.NOT_OFFERED
    assert slot["ladder"] == {"level": 0, "chosen": None}


def test_the_contract_slot_without_ladder_data_stays_not_yet_defined(monkeypatch):
    real = ladder_view.read_sources

    def none(challenge):
        return {**real(challenge), "construction": None}

    ladder_view._repository_view.cache_clear()
    monkeypatch.setattr(ladder_view, "read_sources", none)
    try:
        slot = ladder_view.construction_slot(BATTERY)
    finally:
        ladder_view._repository_view.cache_clear()
    assert slot["level"] is None and slot["status"] == ladder_view.NOT_YET_DEFINED
    assert set(slot) == {"level", "status", "basis"}


def test_the_campaign_view_carries_the_slot():
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad import campaign_view

    campaign_view._contract.cache_clear()
    section = campaign_view.contract_section(challenge_ref(BATTERY), "FULL")
    assert section["construction_level"] == ladder_view.construction_slot(BATTERY)
