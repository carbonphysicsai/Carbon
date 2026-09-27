"""The Control Center's capability contract and the page built from it.

The contract (`carbon.control-center.capabilities.v1`) is derived from runtime
truth: the Challenge registry, the shared `options` operation, the agent's own
provider transport and the ledger's budget vocabulary. These tests pin its
shape, show that each part moves when its source moves, and check the page
sends the chosen Challenge and keeps the rehearsal out of the primary views.
No agent, provider, chain or container is touched.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
from html.parser import HTMLParser
from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import capabilities, controller

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "scripts/dev/miner_launchpad/index.html"
SCRIPT = ROOT / "scripts/dev/miner_launchpad/app.js"
TOP_KEYS = {
    "schema",
    "mode",
    "authority",
    "profile",
    "challenges",
    "agents",
    "model",
    "compute",
    "budget",
    "launch",
    "connections",
    "wallet",
}


@pytest.fixture
def host(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad.journey_fixture import journey_host

    root = tmp_path / "journey"
    root.mkdir(mode=0o700)
    runner = journey_host(root, patch=monkeypatch.setattr)
    yield runner
    runner.close()


def by_id(document):
    return {entry["challenge_id"]: entry for entry in document["challenges"]}


def unavailable_is_explained(item):
    return (
        item["availability"] == "unavailable"
        and type(item["reason"]) is str
        and item["reason"]
        and type(item["next_action"]) is str
        and item["next_action"]
    )


def test_the_contract_shape_without_a_profile():
    document = capabilities.control_center(None)
    assert set(document) == TOP_KEYS
    assert document["schema"] == "carbon.control-center.capabilities.v1"
    assert document["profile"]["configured"] is False
    # Nothing can launch without a runner profile, and each says why and what
    # to do next rather than appearing as a working choice.
    for entry in document["challenges"]:
        assert entry["selectable"] is False
        assert entry["reason"] and entry["next_action"]
    for choice in document["agents"]["choices"]:
        assert unavailable_is_explained(choice)
    for provider in document["model"]["providers"]:
        assert unavailable_is_explained(provider)
        # Not read is a different claim from not configured.
        assert provider["credential"]["configured"] is None
    assert unavailable_is_explained(document["compute"]["choices"][0])
    for group in (
        document["agents"]["unavailable"],
        document["model"]["unavailable"],
        document["compute"]["unavailable"],
        document["connections"],
    ):
        for item in group:
            assert unavailable_is_explained(item)


def test_challenges_are_the_registry_catalog_with_its_descriptions():
    from carbon.challenge_registry import catalog, describe

    document = capabilities.control_center(None)
    registry = {c["challenge_id"]: c for c in catalog()["challenges"]}
    assert set(by_id(document)) == set(registry)
    for challenge_id, entry in by_id(document).items():
        assert entry["status"] == registry[challenge_id]["status"]
        assert entry["version"] == registry[challenge_id]["version"]
        if entry["implemented"]:
            assert entry["description"] == describe(challenge_id, entry["version"])
            assert (
                entry["example_strategy"]
                == entry["description"]["examples"][0]["strategy"]
            )
            assert entry["tools"]["workflow"] == entry["description"].get(
                "workflow", {}
            )
        else:
            assert "description" not in entry
    # Reserved and deferred Challenges are listed with the registry's own code.
    reasons = {e["reason"] for e in document["challenges"] if not e["implemented"]}
    assert reasons == {"challenge_not_implemented", "challenge_deferred"}
    # The launch portfolio leads: the first Challenge offered is an implemented
    # launch Challenge, not the historical DEVELOPMENT one.
    first = document["challenges"][0]
    assert first["portfolio"] == "launch" and first["implemented"]


def test_the_catalog_follows_the_registry_when_it_changes(monkeypatch):
    """Derived, not listed: remove an entry from the registry and it goes."""
    from carbon.challenge_registry import registry

    original = registry._entries()
    kept = tuple(e for e in original if e.status == registry.IMPLEMENTED)
    monkeypatch.setattr(registry, "_entries", lambda: kept)
    document = capabilities.control_center(None)
    assert set(by_id(document)) == {e.challenge_id for e in kept}
    # The specimen: the same projection over the unmodified registry lists the
    # reserved Challenges this one dropped.
    monkeypatch.setattr(registry, "_entries", lambda: original)
    full = set(by_id(capabilities.control_center(None)))
    assert full > {e.challenge_id for e in kept}


def test_a_configured_profile_makes_implemented_challenges_launchable(host):
    document = capabilities.control_center(host)
    assert document["profile"] == {"configured": True, "profile_id": "journey-profile"}
    entries = by_id(document)
    launchable = {cid for cid, e in entries.items() if e["selectable"]}
    implemented = {cid for cid, e in entries.items() if e["implemented"]}
    assert launchable == implemented and launchable
    for entry in entries.values():
        if not entry["implemented"]:
            assert entry["selectable"] is False


def test_agents_come_from_the_shared_options_operation(host):
    from scripts.dev.miner_launchpad.operations import perform

    options = perform(host, "options", {})
    offered = {a["value"]: a for a in options["agents"]}
    document = capabilities.control_center(host)
    choices = {c["id"]: c for c in document["agents"]["choices"]}
    assert set(choices) == {"autonomous", "manual", "external_mcp"}
    for choice in choices.values():
        # Every choice is one the launch operation accepts, with its availability.
        source = offered[choice["launch_agent"]]
        assert choice["availability"] == source["availability"]
    # This host has no model key: Carbon's agent is unavailable with the
    # options operation's reason, and the manual path is not.
    assert choices["autonomous"]["reason"] == "model_provider_key_not_configured"
    assert choices["manual"]["availability"] == "available"
    assert choices["external_mcp"]["door"] == "stdio"
    # The model credential is reported as not configured, not as unread.
    provider = document["model"]["providers"][0]
    assert provider["credential"]["configured"] is False
    assert provider["reason"] == "model_provider_key_not_configured"


def test_the_model_is_the_agent_transports_own(monkeypatch):
    """The provider and model are read from the transport, never restated."""
    from carbon.development_session import agent

    capabilities._implemented_transport.cache_clear()
    monkeypatch.setattr(
        agent,
        "proposal",
        lambda **_: {"provider": "Specimen Provider", "model": "specimen-model-1"},
    )
    try:
        provider = capabilities.control_center(None)["model"]["providers"][0]
        assert provider["provider"] == "Specimen Provider"
        assert [m["id"] for m in provider["models"]] == ["specimen-model-1"]
    finally:
        monkeypatch.undo()
        capabilities._implemented_transport.cache_clear()
    real = capabilities.control_center(None)["model"]["providers"][0]
    assert [m["id"] for m in real["models"]] == [agent.MODEL]


def test_budget_vocabulary_is_the_ledgers_and_blank_is_no_limit():
    from carbon.development_session.product_campaign import BUDGET_KEYS
    from carbon.development_session.research_ledger import DIMENSIONS

    budget = capabilities.control_center(None)["budget"]
    assert budget["keys"] == sorted(BUDGET_KEYS)
    assert budget["ceilings"] == list(DIMENSIONS)
    assert budget["blank"] == "no limit"


def test_launch_contract_is_the_operation_and_names_the_challenge():
    from scripts.dev.miner_launchpad.operations import describe

    launch = capabilities.control_center(None)["launch"]
    table = next(op for op in describe() if op["operation"] == "launch")
    assert {k: launch[k] for k in table} == table
    assert {"challenge", "challenge_version"} <= set(launch["browser_sends"])
    assert launch["challenge_default"] is None


def test_unoffered_providers_are_unavailable_with_a_reason():
    document = capabilities.control_center(None)
    compute = {item["id"]: item for item in document["compute"]["unavailable"]}
    assert "runpod" in compute and unavailable_is_explained(compute["runpod"])
    models = {item["id"] for item in document["model"]["unavailable"]}
    assert {"chutes", "engy"} <= models


def test_the_stale_burgers_bridge_entry_is_gone():
    """The Burgers bridge exists; an entry saying it does not was stale.

    The specimen: the same check finds a reason that is really listed, so a
    green result means the stale one is absent, not that the check is blind.
    """
    listed = {item["reason"] for item in controller.capability_catalog()["unavailable"]}
    assert "research_bridge_not_implemented" not in listed
    assert "adapter_not_implemented" in listed
    ids = {item["id"] for item in controller.INTEGRATIONS}
    assert "carbon-burgers-development" not in ids
    assert "hermes" in ids
    # Every integration is placed somewhere a miner will meet it.
    assert ids == set(controller.INTEGRATION_PLACEMENT)


def test_the_route_serves_the_contract_behind_the_token(tmp_path):
    token = "y" * 40
    server = controller.Server(
        controller.Controller(tmp_path / "runs.sqlite3"), token, port=0
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:

        def get(headers):
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=30
            )
            connection.request(
                "GET", "/api/v1/control-center/capabilities", None, headers
            )
            response = connection.getresponse()
            body = response.read()
            connection.close()
            return response.status, body

        assert get({})[0] == 401
        status, body = get({"Authorization": "Bearer " + token})
        assert status == 200
        document = json.loads(body)
        assert document["schema"] == "carbon.control-center.capabilities.v1"
        assert token.encode() not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


VOID = {"input", "meta", "link", "br", "img"}


class _Views(HTMLParser):
    """Which data-nav view each element id sits inside."""

    def __init__(self):
        super().__init__()
        self.stack = []
        self.views = []
        self.inside = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append(attrs)
        if "data-nav" in attrs:
            self.views.append(
                (attrs["id"], attrs["data-nav"], attrs.get("data-nav-group"))
            )
        if "id" in attrs:
            self.inside[attrs["id"]] = next(
                (a["id"] for a in reversed(self.stack) if "data-nav" in a), None
            )
        if tag in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()


def views():
    parser = _Views()
    parser.feed(PAGE.read_text())
    return parser


def test_primary_navigation_is_the_control_center_and_rehearsal_is_development():
    parsed = views()
    primary = [label for _, label, group in parsed.views if group is None]
    assert primary == [
        "Overview",
        "Campaigns",
        "Challenges",
        "Agents",
        "Compute",
        "Connections",
        "Wallet & Identity",
        "Settings",
    ]
    development = [(vid, label) for vid, label, group in parsed.views if group]
    assert development == [("development", "Development")]
    # The rehearsal and developer diagnostics sit in the Development view -
    # the specimen being that the same lookup places registration in Wallet.
    for element in (
        "launch-form",
        "launch-button",
        "development-sources",
        "integrations",
    ):
        assert parsed.inside[element] == "development", element
    assert parsed.inside["onboarding-panel"] == "wallet"
    assert "Rehearsal" not in primary


def test_the_launch_body_sends_the_chosen_challenge():
    script = SCRIPT.read_text()
    launch = script[script.index('$("research-launch").addEventListener') :]
    body = launch[: launch.index("sessionStorage.setItem(researchKey")]
    assert "challenge: entry.challenge_id" in body
    assert "challenge_version: entry.version" in body
    # The idempotency the launch already had: one key per request, replayed.
    assert "crypto.randomUUID()" in body
    assert "pendingResearch.key" in launch


def test_no_challenge_is_hard_coded_into_the_page():
    """The page names no Challenge: every one it shows comes from the contract.

    The specimen: the same pattern finds each registered id in text that
    contains it, so an absent match is an absent id, not a blind pattern.
    """
    from carbon.challenge_registry import catalog

    ids = [c["challenge_id"] for c in catalog()["challenges"]]
    pattern = re.compile("|".join(re.escape(i) for i in ids))
    for path in (PAGE, SCRIPT):
        text = path.read_text()
        assert not pattern.search(text), (path.name, pattern.search(text))
        assert "burgers" not in text.lower(), path.name
    for challenge_id in ids:
        assert pattern.search("recipe for " + challenge_id + " here")
    assert "burgers" in "The Burgers research bridge".lower()
