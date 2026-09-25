"""Challenge selection: exact resolution, typed refusals, derived descriptions.

The registry is the one place a Challenge is chosen. These tests hold it to:
- no default and no fallback: every unusable selection is a typed error;
- descriptions derived from what Carbon executes, not written beside it;
- implemented kept separate from usable on this host;
- the discovery tools present on the open tier, reading and granting nothing.
"""

import asyncio
import json

import pytest

from carbon import challenge_registry as challenges
from carbon.battery.research import (
    EVALUATION_FEEDBACK_FIELDS,
    SCAFFOLD,
    BatteryPublicMaterial,
)
from carbon.reconstruction import capability_registry as r

BATTERY = r.BATTERY_CHALLENGE
EVERYTHING = challenges.HostFacts(
    frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"})
)
NOTHING = challenges.HostFacts(frozenset())


def test_the_catalog_names_launch_reserved_and_deferred_challenges():
    listed = {c["challenge_id"]: c for c in challenges.catalog(NOTHING)["challenges"]}
    assert {k for k, c in listed.items() if c["portfolio"] == "launch"} == {
        BATTERY,
        "chip-cold-plate",
        "electric-motor-magnetics",
        "photonic-coupler",
    }
    assert {k for k, c in listed.items() if c["status"] == "DEFERRED"} == {
        "power-magnetics",
        "airfoil",
    }
    assert listed[BATTERY]["status"] == "IMPLEMENTED"
    assert listed[r.BURGERS_CHALLENGE]["status"] == "IMPLEMENTED"
    for reserved in ("chip-cold-plate", "electric-motor-magnetics", "photonic-coupler"):
        # A reserved Challenge has a name and an issue, and nothing to run.
        assert listed[reserved]["status"] == "RESERVED"
        assert listed[reserved]["version"] is None
        assert listed[reserved]["profiles"] == []
        assert listed[reserved]["tracking"].startswith("carbonphysicsai/Carbon#")


@pytest.mark.parametrize(
    ("challenge_id", "version", "profile", "error"),
    [
        ("burgers", "1.0", "cpu_research", challenges.UnknownChallenge),
        (BATTERY, "2.0", "cpu_research", challenges.UnsupportedVersion),
        (BATTERY, None, "cpu_research", challenges.UnsupportedVersion),
        (BATTERY, "1.0", "gpu_diagnostic", challenges.ProfileUnavailable),
        ("photonic-coupler", None, "cpu_research", challenges.ChallengeNotImplemented),
        ("chip-cold-plate", None, "cpu_research", challenges.ChallengeNotImplemented),
        ("airfoil", None, "cpu_research", challenges.ChallengeDeferred),
        (None, "1.0", "cpu_research", challenges.UnknownChallenge),
    ],
)
def test_every_unusable_selection_is_a_typed_refusal(
    challenge_id, version, profile, error
):
    with pytest.raises(error) as refused:
        challenges.resolve(challenge_id, version, profile)
    public = refused.value.public()
    assert public["code"] == error.code and public["next_action"]


def test_implemented_is_not_usable_until_the_host_has_it():
    entry, profile = challenges.resolve(BATTERY, "1.0", "cpu_research")
    assert entry.challenge_id == BATTERY
    with pytest.raises(challenges.ProfileUnavailable, match="not usable here"):
        challenges.resolve(BATTERY, "1.0", "cpu_research", host=NOTHING)
    challenges.resolve(BATTERY, "1.0", "cpu_research", host=EVERYTHING)
    (row,) = [
        p
        for c in challenges.catalog(NOTHING)["challenges"]
        if c["challenge_id"] == BATTERY
        for p in c["profiles"]
    ]
    assert row["implemented"] is True and row["usable_here"] is False
    assert set(row["missing_here"]) == set(profile.requirements)


def test_the_battery_description_is_derived_from_executable_registrations():
    described = challenges.describe(BATTERY, "1.0", host=EVERYTHING)
    assert described["contract_digest"] == r.contract_digest(BATTERY)
    assert set(described["models"]["controls"]) == set(r.catalog_surfaces(BATTERY))
    assert [m["selector"] for m in described["models"]["rebuildable"]] == [
        s for s, _ in r.rebuildable_families(BATTERY)
    ]
    registry = r.public_registry(BATTERY)["capabilities"]
    assert {u["id"] for u in described["unsupported"]} == {
        c["id"] for c in registry if c["status"] != "rebuildable_development"
    }
    assert described["public_material"]["names"] == list(BatteryPublicMaterial.NAMES)
    assert described["feedback"]["evaluation_fields"] == list(
        EVALUATION_FEEDBACK_FIELDS
    )
    # Every example passes the admission a submission meets.
    assert described["examples"][0]["strategy"] == SCAFFOLD
    assert all(e["admission"]["valid"] for e in described["examples"])
    assert described["profiles"][0]["usable_here"] is True
    # Nothing private is described: not a seed, root, hidden case or label.
    text = json.dumps(described).lower()
    for private in ("private_root", "duplicate_of", "screen-", "pscreen"):
        assert private not in text


def test_the_burgers_description_reads_the_unchanged_burgers_path():
    from carbon.development_session.research_service import BURGERS_SCAFFOLD

    described = challenges.describe(r.BURGERS_CHALLENGE, "1.0", host=NOTHING)
    assert described["examples"][0]["strategy"] == BURGERS_SCAFFOLD
    assert described["examples"][0]["admission"]["valid"]
    assert described["lanes"]["session"] == ["fno", "deeponet"]


def test_a_launch_binds_exactly_one_resolved_challenge():
    from test_miner_launchpad_runner import registered

    from carbon.development_session.product_campaign import ProductLaunch

    def launch(challenge):
        return ProductLaunch(
            campaign_id="cmp-x",
            principal="p",
            miner=registered(),
            runtime={"implementation": {}, "images": []},
            budget={},
            agent="none",
            challenge=challenge,
        )

    assert "challenge" not in launch(None).manifest_fields()  # history unchanged
    bound = launch({"id": BATTERY, "version": "1.0"}).manifest_fields()
    assert bound["challenge"] == {"id": BATTERY, "version": "1.0"}
    with pytest.raises(challenges.ChallengeNotImplemented):
        launch({"id": "photonic-coupler", "version": None})
    with pytest.raises(ValueError):
        launch({"id": BATTERY})


def test_the_launch_operation_refuses_by_code_never_falls_back():
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    assert RunnerAdapter._challenge({"agent": "none"}) is None
    assert RunnerAdapter._challenge(
        {"challenge": BATTERY, "challenge_version": "1.0"}
    ) == {"id": BATTERY, "version": "1.0"}
    for request, code in (
        ({"challenge": "airfoil"}, "challenge_deferred"),
        ({"challenge": BATTERY}, "challenge_version_unsupported"),
        ({"challenge_version": "1.0"}, "challenge_unknown"),
        ({"challenge": "photonic-coupler"}, "challenge_not_implemented"),
    ):
        with pytest.raises(Rejected) as refused:
            RunnerAdapter._challenge(request)
        assert refused.value.code == code


def test_discovery_is_on_the_open_tier_and_grants_nothing(tmp_path, monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.mcp_challenges import CATALOG_URI, PREFIX
    from carbon.miner_mcp.open_tier import create_open_tier_server

    monkeypatch.chdir(tmp_path)
    server = create_open_tier_server(host_facts=lambda: EVERYTHING)
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {PREFIX + "list", PREFIX + "describe"} <= names

    def payload(result):
        assert not result.is_error
        return result.structured_content["payload"]

    listed = payload(asyncio.run(server.call_tool(PREFIX + "list", {})))
    assert BATTERY in {c["challenge_id"] for c in listed["challenges"]}
    described = payload(
        asyncio.run(
            server.call_tool(
                PREFIX + "describe", {"challenge_id": BATTERY, "version": "1.0"}
            )
        )
    )
    assert described["challenge_id"] == BATTERY
    # Refused by its stable code; the caller's text is never echoed back.
    with pytest.raises(ToolError, match="challenge_not_implemented"):
        asyncio.run(
            server.call_tool(
                PREFIX + "describe",
                {"challenge_id": "photonic-coupler", "version": None},
            )
        )
    catalog = json.loads(asyncio.run(server.read_resource(CATALOG_URI))[0].content)
    assert catalog["schema"] == challenges.CATALOG_SCHEMA
    # Discovery created no campaign, ledger or file.
    assert list(tmp_path.rglob("*")) == []


def test_battery_states_the_scope_of_its_submission_exclusions():
    from carbon.challenge_registry import describe

    scope = describe(BATTERY, "1.0")["exclusion_scope"]
    assert "JAX" in scope["submission"] and "PyBaMM" in scope["submission"]
    text = " ".join(scope["not_excluded"])
    assert "TRAIN" in text and "truth service" in text
