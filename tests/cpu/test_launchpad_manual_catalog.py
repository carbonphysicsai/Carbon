"""BUG S22 (Test Lead, M1, Motor 1.3, a manual campaign's Tools tab, Recipe).

(a) The Recipe box said "This Challenge registers no example recipe": the
toolbox kept only Level 0 `strategy` examples, and a catalog version's
example is a `recipe`.
(b) Dry-validate answered with the Level 0 strategy compile on a catalog
version, so it refused every recipe the version takes.
(c) "Practice this recipe" on the exact catalog recipe read "Refused before it
started: contract incompatibility", where Graphite's call reached
backend_not_served. Both doors build the request in the same SDK admission
(`ResearchMinerTools._request`); the page printed only the refusal's generic
`reason` (every pre-dispatch refusal's is contract_incompatibility) and
dropped its correction code, field and text.

The page door here is the controller's own `ToolDoor` over the real MCP
server's tools; the agent door is the SDK call Graphite's tools make.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_lp_prod_research_tools import ledger

from carbon import research
from carbon.backbone_catalog import listing
from carbon.challenge_registry import motor as motor_registry
from carbon.challenge_registry import registry
from carbon.development_session.research_tools import PREFIX, ResearchMinerTools

MOTOR = "electric-motor-magnetics"
IDENTITY = "lp-s22-manual-0001"


class StubPractice:
    """A catalog practice that records what admission asked it, and either
    serves the recipe (None) or refuses it with the entries installed here."""

    construction_mode = "direct"
    root = "."

    def __init__(self, refusal=None):
        self.refusal = refusal
        self.asked = []

    def backend_refusal(self, strategy):
        self.asked.append(json.loads(json.dumps(strategy)))
        return self.refusal


class Unreachable(Exception):
    """Raised where the request would leave for the provider."""


async def _unreachable():
    raise Unreachable()


def _sdk(tmp_path, version, practice, name):
    from carbon.motor.research import make_motor_research_service

    meter = ledger(tmp_path / (name + "-ledger"))
    composition = make_motor_research_service(
        root=tmp_path / (name + "-tasks"),
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        practice=practice,
        version=version,
    )
    sdk = ResearchMinerTools(
        # Admission is all this test reaches: the registration check is the
        # first step after it, and stops the call there.
        connection=SimpleNamespace(check_registration=_unreachable),
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    built = []
    admit = sdk._request

    def recording(operation, args, identity):
        request = admit(operation, args, identity)
        built.append(request)
        return request

    sdk._request = recording
    return sdk, composition, built


def _page_door(sdk):
    from carbon.miner_mcp.standard import ResearchToolAdapter
    from scripts.dev.miner_launchpad.tool_door import ToolDoor

    adapter = ResearchToolAdapter(sdk, principal="alice")
    adapter._check_binding = lambda: None
    return ToolDoor(adapter)


def _page_practice(door, recipe):
    """What "Practice this recipe" posts to /api/v1/tools/<campaign>/start."""
    return asyncio.run(
        door.start(
            {
                "operation_id": "page-" + "5" * 24,
                "kind": "practice",
                "strategy": recipe,
                "action": None,
                "arguments": None,
                "hypothesis": "This recipe trains well on TRAIN data",
                "expected_effect": "A lower practice score than the last run",
            }
        )
    )


def _agent_practice(sdk, recipe):
    """Graphite's call: start_research_task kind=practice, strategy_json."""
    return asyncio.run(
        sdk.call(
            PREFIX + "start_research_task",
            {
                "kind": "practice",
                "strategy_json": json.dumps(recipe),
                "action": None,
                "arguments_json": None,
                "hypothesis": "This recipe trains well on TRAIN data",
                "expected_effect": "A lower practice score than the last run",
            },
            IDENTITY,
        )
    )


def _page_payload(reply):
    assert reply["ok"] is True and reply["task"] is None, reply
    return json.loads(reply["result"]["content"][0]["text"])["payload"]


@pytest.fixture
def recipe():
    return motor_registry.catalog_recipe("neuralop.FNO", version="1.3")


def test_the_manual_door_admits_the_catalog_recipe_as_the_agent_door_does(
    tmp_path, recipe
):
    page_practice, agent_practice = StubPractice(), StubPractice()
    page_sdk, page_comp, page_built = _sdk(tmp_path, "1.3", page_practice, "page")
    agent_sdk, agent_comp, agent_built = _sdk(tmp_path, "1.3", agent_practice, "agent")
    try:
        page = _page_practice(_page_door(page_sdk), recipe)
        with pytest.raises(Unreachable):
            _agent_practice(agent_sdk, recipe)
    finally:
        page_comp.tasks.close()
        agent_comp.tasks.close()
    # Both doors passed admission with one direct practice of the same
    # recipe, and stopped at the same next step (registration).
    assert page["ok"] is False and "OPERATIONAL_STOP" in page["error"]
    (page_request,) = page_built
    (agent_request,) = agent_built
    assert type(page_request.task_spec) is research.DirectPracticeTaskSpecV1
    assert page_request.task_spec == agent_request.task_spec
    assert page_request.task_spec.recipe == recipe
    assert page_practice.asked == agent_practice.asked == [recipe]


@pytest.mark.parametrize(
    ("refusal", "code"),
    [(("neuralop.TFNO",), "backend_not_served"), ((), "catalog_not_installed")],
)
def test_a_backend_refusal_reads_on_the_page_as_the_agent_reads_it(
    tmp_path, recipe, refusal, code
):
    page_sdk, page_comp, _ = _sdk(tmp_path, "1.3", StubPractice(refusal), "page")
    agent_sdk, agent_comp, _ = _sdk(tmp_path, "1.3", StubPractice(refusal), "agent")
    try:
        page = _page_payload(_page_practice(_page_door(page_sdk), recipe))
        agent = _agent_practice(agent_sdk, recipe)
    finally:
        page_comp.tasks.close()
        agent_comp.tasks.close()
    for payload in (page, agent):
        assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
        # The generic reason every pre-dispatch refusal carries ...
        assert payload["reason"] == "contract_incompatibility"
        # ... and the correction the page now shows beside it.
        assert payload["correction_code"] == code
    assert page["correction"] == agent["correction"].replace(
        "strategy_json", "strategy"
    )
    if refusal:
        assert "Allowed here: neuralop.TFNO." in page["correction"]


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda r: r["challenge"].update(version="1.2"),
            "construction_recipe_binding_mismatch",
        ),
        (
            lambda r: r["source"].update(catalog_id="neuralop.TFNO2"),
            "catalog_entry_unknown",
        ),
        (
            lambda r: r["procedure"]["train_use"].update(nonsense=1),
            "catalog_setting_unknown",
        ),
    ],
)
def test_both_doors_refuse_a_recipe_the_version_does_not_take_by_its_code(
    tmp_path, recipe, mutate, code
):
    mutate(recipe)
    practice = StubPractice()
    page_sdk, page_comp, _ = _sdk(tmp_path, "1.3", practice, "page")
    agent_sdk, agent_comp, _ = _sdk(tmp_path, "1.3", practice, "agent")
    try:
        page = _page_payload(_page_practice(_page_door(page_sdk), recipe))
        agent = _agent_practice(agent_sdk, recipe)
    finally:
        page_comp.tasks.close()
        agent_comp.tasks.close()
    for payload in (page, agent):
        assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
        assert payload["correction_code"] == "direct_recipe_required"
        # R9-1: an unknown setting also lists the settings that place takes;
        # every other code lists the source kinds the version takes (M1 G5a).
        tail = ", setting:" if code == "catalog_setting_unknown" else ", source."
        assert "Allowed here: " + code + tail in payload["correction"]
    assert practice.asked == []  # refused before the backend is asked


# --- dry_validate validates the format the version takes ----------------------


def _dry_validate(composition, key, strategy):
    reply = composition.service.call(
        research.ServiceCall(
            research.RESEARCH_NAMESPACE,
            "dry_validate",
            research.DryValidateRequest(key, strategy),
        )
    )
    assert reply.status is research.ReplyStatus.OK, reply
    result = reply.result
    return result.valid, tuple(i.code for i in result.issues)


def test_dry_validate_accepts_a_catalog_recipe_on_motor_1_3(tmp_path, recipe):
    _, composition, _ = _sdk(tmp_path, "1.3", StubPractice(), "dv")
    try:
        key = composition.challenge
        assert (key.challenge_id, key.version) == (MOTOR, "1.3")
        assert _dry_validate(composition, key, recipe) == (True, ())
        for item in listing.entries(MOTOR, "1.3"):
            other = motor_registry.catalog_recipe(item["catalog_id"], version="1.3")
            assert _dry_validate(composition, key, other) == (True, ()), item
        # Malformed ones, each by its own code.
        level0 = registry.describe(MOTOR, "1.0")["examples"][0]["strategy"]
        assert _dry_validate(composition, key, level0) == (
            False,
            ("construction_recipe_malformed",),
        )
        stale = motor_registry.catalog_recipe("neuralop.FNO", version="1.2")
        assert _dry_validate(composition, key, stale) == (
            False,
            ("construction_recipe_binding_mismatch",),
        )
        bad = json.loads(json.dumps(recipe))
        bad["procedure"]["train_use"]["steps"] = -1
        assert _dry_validate(composition, key, bad) == (
            False,
            ("catalog_setting_invalid",),
        )
    finally:
        composition.tasks.close()


def test_a_level_0_version_still_validates_strategies(tmp_path, recipe):
    from carbon.motor.research import make_motor_research_service

    meter = ledger(tmp_path / "ledger")
    composition = make_motor_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        practice=SimpleNamespace(root="."),
    )
    try:
        key = composition.challenge
        assert key.version == "1.0"
        scaffold = registry.describe(MOTOR, "1.0")["examples"][0]["strategy"]
        assert _dry_validate(composition, key, scaffold) == (True, ())
        valid, codes = _dry_validate(composition, key, recipe)
        assert not valid and codes
        assert not any(c.startswith(("construction_recipe", "catalog_")) for c in codes)
    finally:
        composition.tasks.close()


# --- the registered example and the backbone picker ---------------------------


def test_a_catalog_versions_toolbox_carries_its_example_and_picker():
    from scripts.dev.miner_launchpad import toolbox

    document = toolbox.build({"id": MOTOR, "version": "1.3"})
    described = registry.describe(MOTOR, "1.3")
    # (a): the version's registered example, a recipe, prefills the editor.
    assert document["examples"] == [e["recipe"] for e in described["examples"]]
    assert document["examples"][0] == motor_registry.catalog_recipe(
        "neuralop.FNO", version="1.3"
    )
    # The picker: every entry of the version's catalog, each with the
    # registered helper's ready recipe at the tested baseline.
    entries = listing.entries(MOTOR, "1.3")
    assert [c["catalog_id"] for c in document["catalog"]] == [
        e["catalog_id"] for e in entries
    ]
    for choice, item in zip(document["catalog"], entries):
        assert choice["backbone"] == item["backbone"]
        assert choice["recipe"] == motor_registry.catalog_recipe(
            item["catalog_id"], version="1.3"
        )
        assert choice["recipe"]["procedure"]["configuration"] == {}


def test_a_level_0_versions_toolbox_has_no_picker():
    from scripts.dev.miner_launchpad import toolbox

    document = toolbox.build({"id": MOTOR, "version": "1.0"})
    assert document["catalog"] == []
    assert (
        document["examples"]
        == [e["strategy"] for e in registry.describe(MOTOR, "1.0")["examples"]][:4]
    )


def test_a_direct_campaigns_toolbox_offers_only_recipe_examples():
    # M1 E2E H11: every new launch is direct and practises construction
    # recipes only; a Level 0 strategy example would be refused as
    # construction_recipe_malformed, so a direct campaign is not offered one.
    from scripts.dev.miner_launchpad import toolbox

    assert toolbox.build({"id": MOTOR, "version": "1.0"})["examples"]
    assert toolbox.build({"id": MOTOR, "version": "1.0"}, direct=True)["examples"] == []
    catalog = toolbox.build({"id": MOTOR, "version": "1.3"}, direct=True)
    assert catalog["examples"] == [
        e["recipe"] for e in registry.describe(MOTOR, "1.3")["examples"]
    ]


@pytest.mark.parametrize(
    ("challenge_id", "version"),
    [
        (MOTOR, "1.2"),
        (MOTOR, "1.3"),
        ("chip-cold-plate", "1.2"),
        ("f08-ribbed-bracket", "1.4"),
        ("f02", "2.3"),
    ],
)
def test_each_catalog_versions_picker_is_its_catalog(challenge_id, version):
    from scripts.dev.miner_launchpad import toolbox

    choices = toolbox.catalog_recipes(challenge_id, version)
    assert [c["catalog_id"] for c in choices] == [
        e["catalog_id"] for e in listing.entries(challenge_id, version)
    ]
    for choice in choices:
        assert choice["recipe"]["challenge"]["version"] == version
        assert choice["recipe"]["source"]["catalog_id"] == choice["catalog_id"]


def test_capabilities_expose_the_example_and_the_picker():
    from scripts.dev.miner_launchpad import capabilities, toolbox

    items = {
        (c["challenge_id"], c["version"]): c
        for c in capabilities.control_center()["challenges"]
    }
    motor = items[(MOTOR, "1.3")]
    assert motor["example_strategy"] == motor_registry.catalog_recipe(
        "neuralop.FNO", version="1.3"
    )
    assert motor["catalog_recipes"] == toolbox.catalog_recipes(MOTOR, "1.3")
    assert len(motor["catalog_recipes"]) == len(listing.entries(MOTOR, "1.3"))
    assert items[(MOTOR, "1.0")]["catalog_recipes"] == []


def test_a_catalog_variant_says_so_in_its_listing():
    # Validator: thuml.LSM is upstream's instance-norm variant (LICENCES.md,
    # "Variants"); any listing of it must say so.
    from scripts.dev.miner_launchpad import toolbox

    assert "instance-norm variant" in toolbox.ENTRY_VARIANTS["thuml.LSM"]
    for item in toolbox.catalog_recipes(MOTOR, "1.3"):
        if item["catalog_id"] in toolbox.ENTRY_VARIANTS:
            assert item["variant"] == toolbox.ENTRY_VARIANTS[item["catalog_id"]]
        else:
            assert "variant" not in item


def test_the_toolbox_serves_the_version_asked_for():
    # M1 E2E H6: carbon_toolbox with challenge_version read challenge_unknown.
    import pytest

    from scripts.dev.miner_launchpad import toolbox
    from scripts.dev.miner_launchpad.controller import Rejected

    host = None
    document = toolbox.for_request(
        host, {"challenge": MOTOR, "challenge_version": "1.3"}, lanes={}
    )
    assert document["catalog"] == toolbox.catalog_recipes(MOTOR, "1.3")
    with pytest.raises(Rejected) as refused:
        toolbox.for_request(
            host, {"challenge": MOTOR, "challenge_version": "9.9"}, lanes={}
        )
    assert refused.value.code == "challenge_unknown"
