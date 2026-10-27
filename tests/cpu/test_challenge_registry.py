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
COLD_PLATE = r.COLD_PLATE_CHALLENGE
MOTOR = r.MOTOR_CHALLENGE
EVERYTHING = challenges.HostFacts(
    frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"})
)
NOTHING = challenges.HostFacts(frozenset())


def _expected_status(challenge_id, version):
    """A pool-graded version is RESERVED until its owner constants are registered and published (Validator
    06:55Z; tests/cpu/test_pool_reserved_status.py); every other version of these Challenges is implemented.
    """
    from carbon.challenge_registry import published_exam

    if (challenge_id, version) in published_exam._POOL_VERSIONS:
        registered = published_exam.registered_pool(challenge_id, version) is not None
        return "IMPLEMENTED" if registered else "RESERVED"
    return "IMPLEMENTED"


def test_the_catalog_names_launch_reserved_and_deferred_challenges():
    listed = {c["challenge_id"]: c for c in challenges.catalog(NOTHING)["challenges"]}
    # Battery is out of the launch set (OWNER-BATTERY-OUT-OF-LAUNCH-01): implemented and kept,
    # in the historical portfolio, and not offered to a miner (see test_battery_is_not_offered).
    assert {k for k, c in listed.items() if c["portfolio"] == "launch"} == {
        "chip-cold-plate",
        "electric-motor-magnetics",
        "photonic-coupler",
    }
    # F08 1.4 and F02 2.3, the direct-recipe-only versions: launch portfolio,
    # readiness record pending, so not `launch` yet (Gate6, 2026-10-21).
    assert {
        k for k, c in listed.items() if c["portfolio"] == "launch_pending_readiness"
    } == {"f08-ribbed-bracket", "f02"}
    assert {k for k, c in listed.items() if c["status"] == "DEFERRED"} == {
        "power-magnetics",
        "airfoil",
    }
    assert listed[BATTERY]["status"] == "IMPLEMENTED"
    assert listed[BATTERY]["portfolio"] == "historical_development"
    # Retired from the research path: still listed, never selectable.
    assert listed[r.BURGERS_CHALLENGE]["status"] == "RETIRED"
    assert all(not p["implemented"] for p in listed[r.BURGERS_CHALLENGE]["profiles"])
    # Cooling registers two versions: 1.0 (Level 0) and 1.2 (allowlist v7 and
    # the backbone catalog).
    cooling = {
        c["version"]: c
        for c in challenges.catalog(NOTHING)["challenges"]
        if c["challenge_id"] == COLD_PLATE
    }
    # Cooling 1.3: 1.2 with the law-safe output encoding (Validator ruling G1).
    # Cooling 1.4: graph route v2 (1.3 plus Carbon's graph training adapter v2).
    # Cooling 1.5: pool-graded (1.4's construction, the pool grader's exam).
    assert set(cooling) == {"1.0", "1.2", "1.3", "1.4", "1.5"}
    for entry in cooling.values():
        assert entry["status"] == _expected_status(COLD_PLATE, entry["version"])
        # A catalog version adds the one shared GPU practice profile.
        assert {p["profile"] for p in entry["profiles"]} == (
            {"cpu_research"}
            if entry["version"] == "1.0"
            else {"cpu_research", "gpu_research"}
        )
    # Motor registers three versions: 1.0 (Level 0), 1.2 (the backbone catalog)
    # and 1.3 (1.2 plus allowlist v7).
    motor = {
        c["version"]: c
        for c in challenges.catalog(NOTHING)["challenges"]
        if c["challenge_id"] == MOTOR
    }
    # Motor 1.4: graph route v2; Motor 1.5: pool-graded.
    assert set(motor) == {"1.0", "1.2", "1.3", "1.4", "1.5"}
    for entry in motor.values():
        assert entry["status"] == _expected_status(MOTOR, entry["version"])
        # A catalog version adds the one shared GPU practice profile.
        assert {p["profile"] for p in entry["profiles"]} == (
            {"cpu_research"}
            if entry["version"] == "1.0"
            else {"cpu_research", "gpu_research"}
        )
    reserved = "photonic-coupler"
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
        (COLD_PLATE, None, "cpu_research", challenges.UnsupportedVersion),
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
    rows = {
        p["profile"]: p
        for c in challenges.catalog(NOTHING)["challenges"]
        if c["challenge_id"] == BATTERY and c["version"] == "1.0"
        for p in c["profiles"]
    }
    # CPU practice, and the miner's own GPU for speed (C-MLP-03 slice 3).
    assert set(rows) == {"cpu_research", "gpu_research"}
    row = rows["cpu_research"]
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
    # Every example passes the admission a submission meets. Since LP-PROD-D
    # the verdict sits beside the examples, so each example is a check_design
    # design as is: `{strategy}`, nothing else.
    assert described["examples"][0]["strategy"] == SCAFFOLD
    assert all(set(e) == {"strategy"} for e in described["examples"])
    assert len(described["examples_admission"]) == len(described["examples"])
    assert all(v["valid"] for v in described["examples_admission"])
    assert described["profiles"][0]["usable_here"] is True
    # Nothing private is described: not a seed, root, hidden case or label.
    text = json.dumps(described).lower()
    for private in ("private_root", "duplicate_of", "screen-", "pscreen"):
        assert private not in text


@pytest.mark.parametrize("challenge_id", [BATTERY, COLD_PLATE, MOTOR])
def test_description_provisions_match_the_registered_public_projection(challenge_id):
    from carbon.challenge_kit import standard
    from scripts.dev.miner_launchpad import capabilities

    version = next(
        entry.version
        for entry in challenges.entries()
        if entry.challenge_id == challenge_id
    )
    provisions = challenges.describe(challenge_id, version, host=NOTHING)["provisions"]
    assert provisions == standard.public_provisions(challenge_id)
    assert provisions == capabilities._provisions(challenge_id)
    assert set(provisions) == set(standard.PROVISIONS)
    for name, declaration in standard.ENVIRONMENTS[challenge_id].items():
        public = provisions[name]
        if isinstance(declaration, standard.Gap):
            assert public == {
                "status": "gap",
                "reason": declaration.reason,
                "next_step": declaration.next_step,
            }
        else:
            assert public == {"status": "provided", "note": declaration.note}


def test_the_cold_plate_description_is_derived_and_public_only():
    described = challenges.describe(COLD_PLATE, "1.0", host=EVERYTHING)
    assert described["contract_digest"] == r.contract_digest(COLD_PLATE)
    assert set(described["models"]["controls"]) == set(r.catalog_surfaces(COLD_PLATE))
    assert described["models"]["rebuildable"][0]["selector"] == "kernel_ridge"
    assert described["execution"]["gpu_lane"] is False
    text = json.dumps(described).lower()
    for private in ("private_root", "duplicate_of", "counted-v1/completion"):
        assert private not in text


def test_the_motor_description_is_derived_and_public_only():
    described = challenges.describe(MOTOR, "1.0", host=EVERYTHING)
    assert described["contract_digest"] == r.contract_digest(MOTOR)
    assert set(described["models"]["controls"]) == set(r.catalog_surfaces(MOTOR))
    assert described["models"]["rebuildable"][0]["selector"] == "kernel_ridge"
    assert described["execution"]["gpu_lane"] is False
    assert described["interface"]["outputs"]["torque_nm"]["shape"] == [60]
    text = json.dumps(described).lower()
    for private in ("private_root", "duplicate_of", "motor-private", "confirmation-"):
        assert private not in text


def test_burgers_is_retired_and_its_reference_description_is_unchanged():
    from carbon.challenge_registry.burgers import describe as burgers_reference
    from carbon.development_session.research_service import BURGERS_SCAFFOLD

    with pytest.raises(challenges.ChallengeRetired) as refused:
        challenges.describe(r.BURGERS_CHALLENGE, "1.0", host=NOTHING)
    assert refused.value.public()["code"] == "challenge_retired"
    with pytest.raises(challenges.ChallengeRetired):
        challenges.resolve(r.BURGERS_CHALLENGE, "1.0", "cpu_research")
    # The code stays in the repository as reference, reading the same path.
    described = burgers_reference()
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

    assert RunnerAdapter._challenge(
        {"challenge": BATTERY, "challenge_version": "1.0"}
    ) == {"id": BATTERY, "version": "1.0"}
    for request, code in (
        ({"agent": "none"}, "challenge_required"),
        (
            {"challenge": r.BURGERS_CHALLENGE, "challenge_version": "1.0"},
            "challenge_retired",
        ),
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
    # Battery is implemented and kept, but NOT offered: the MCP list follows the one rule.
    offered = {c["challenge_id"] for c in listed["challenges"]}
    assert BATTERY not in offered and COLD_PLATE in offered and MOTOR in offered
    described = payload(
        asyncio.run(
            server.call_tool(
                PREFIX + "describe", {"challenge_id": BATTERY, "version": "1.0"}
            )
        )
    )
    assert described["challenge_id"] == BATTERY
    assert (
        described["provisions"]
        == challenges.describe(BATTERY, "1.0", host=EVERYTHING)["provisions"]
    )
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
    # OWNER-PYTORCH-BACKEND-01: PyTorch is an approved runtime, Julia is not.
    assert "JAX or PyTorch" in scope["submission"]
    assert "Julia submission" in scope["submission"]
    text = " ".join(scope["not_excluded"])
    assert "TRAIN" in text and "truth service" in text


def test_motor_resolves_each_registered_version_exactly():
    from carbon.challenge_registry import registry as reg

    assert reg.describe(MOTOR, "1.0")["version"] == "1.0"
    catalog = reg.describe(MOTOR, "1.2")
    assert catalog["version"] == "1.2"
    assert catalog["examples"][0]["recipe"]["source"]["kind"] == "catalog"
    assert {m["selector"] for m in catalog["models"]["rebuildable"]} == set(
        catalog["models"]["catalog"]["entries"]
    )
    with pytest.raises(reg.UnsupportedVersion, match="1.0, 1.2"):
        reg.describe(MOTOR, "1.1")


def test_cooling_resolves_each_registered_version_exactly():
    from carbon.challenge_registry import registry as reg

    assert reg.describe(COLD_PLATE, "1.0")["version"] == "1.0"
    catalog = reg.describe(COLD_PLATE, "1.2")
    assert catalog["version"] == "1.2"
    assert catalog["identity"] == "carbon.chip-cold-plate-catalog.1.2"
    assert {m["selector"] for m in catalog["models"]["rebuildable"]} == set(
        catalog["models"]["catalog"]["entries"]
    )
    with pytest.raises(reg.UnsupportedVersion, match="1.0, 1.2"):
        reg.describe(COLD_PLATE, "1.1")


# --- Validator, 2026-10-21: pending readiness never counts as launch ----------


def test_launch_pending_readiness_never_counts_as_launch():
    from carbon.challenge_registry.registry import LAUNCH_PENDING_READINESS, entries

    pending = {
        e.challenge_id for e in entries() if e.portfolio == LAUNCH_PENDING_READINESS
    }
    launch = {e.challenge_id for e in entries() if e.portfolio == "launch"}
    assert pending == {"f08-ribbed-bracket", "f02"}
    assert not pending & launch
    # The catalog carries the value as it is; nothing rewrites it to launch.
    listed = challenges.catalog(NOTHING)["challenges"]
    for item in listed:
        if item["challenge_id"] in pending:
            assert item["portfolio"] == LAUNCH_PENDING_READINESS


def test_no_code_reads_a_portfolio_prefix_as_launch():
    """Launch is only `== "launch"`: no reader may match a prefix or a
    substring, which would count launch_pending_readiness as launch."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    loose = re.compile(
        r"portfolio[^\n]{0,40}(startswith\(\s*[\"']launch|[\"']launch[\"']\s+in\b)"
        r"|[\"']launch[\"']\s+in\s+[^\n]{0,40}portfolio"
    )
    offenders = [
        str(path.relative_to(root))
        for base in ("carbon", "scripts")
        for path in (root / base).rglob("*")
        if path.suffix in (".py", ".js")
        and loose.search(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert offenders == []


def test_battery_is_not_offered_by_the_one_rule_the_page_the_wizard_and_the_mcp_list_share():
    """Owner (OWNER-BATTERY-OUT-OF-LAUNCH-01; Lead 2026-10-27): Battery is not offered at launch.
    The registry's offered rule is the one source: the MCP list and the catalog resource use it,
    and the Challenges page and the launch wizard filter by the same portfolio."""
    from pathlib import Path

    full = {c["challenge_id"] for c in challenges.catalog(NOTHING)["challenges"]}
    offered = challenges.offered_catalog(NOTHING)["challenges"]
    assert (
        BATTERY in full
    )  # still registered, resolvable and described (history, tests)
    assert BATTERY not in {c["challenge_id"] for c in offered}
    for item in offered:
        assert challenges.is_offered(item)
    # Everything that is not implemented stays listed with its status: it never reads as READY.
    by_status = {c["status"] for c in offered}
    assert {"RESERVED", "DEFERRED", "RETIRED"} <= by_status
    assert challenges.resolve(BATTERY, "1.0", "cpu_research") is not None
    # The page and the wizard filter by the same portfolio token.
    app = (
        Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/app.js"
    ).read_text(encoding="utf-8")
    start = app.index("function offeredChallenges()")
    assert "historical_development" in app[start : app.index("}", start)]
