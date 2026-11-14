"""The app offers a miner only versions a door serves (owner rule, 13 Nov: "Once a challenge is on
main, no testnet": testnet Motor has no door, so testnet does not offer Motor 1.8 for submission).

`environment_setup.doorless_versions` names the implemented intake versions this deployment has no
door for (the published endpoints of the process network, the miner's own intakes); the MCP list
(`offered_catalog`) and the Control Center (`has_door`, read by `app.js` before its newest-per-Challenge
rule) leave them out. Practice stays reachable: a practice-only profile hides nothing, and a launch or
a describe by exact id is unchanged. A display filter only: nothing here grants or refuses a submit.
No network is contacted.
"""

from __future__ import annotations

import json

import pytest

from carbon import challenge_registry as registry
from carbon.chain import models as chain_models
from carbon.challenge_registry.registry import IMPLEMENTED
from scripts.dev.miner_launchpad import environment_setup as es

MOTOR, COOLING = "electric-motor-magnetics", "chip-cold-plate"
BRACKET, BURST = "f08-ribbed-bracket", "f02"
RECEIVER = "5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR"


def _entry(network, challenge, version, door):
    return {
        "network": network,
        "netuid": {"testnet": 567, "finney": 116}[network],
        "challenge": challenge,
        "version": version,
        "intake_url": f"https://{door}.carbonphysics.ai",
        "receiver_hotkey": RECEIVER,
    }


def _published(tmp_path, entries):
    path = tmp_path / "published_endpoints.json"
    path.write_text(
        json.dumps({"schema": es.PUBLISHED_SCHEMA, "endpoints": entries}), "utf-8"
    )
    return path


def _bind(monkeypatch, network):
    monkeypatch.setattr(chain_models, "CARBON_NETWORK", network)
    monkeypatch.setattr(
        chain_models, "CARBON_NETUID", {"testnet": 567, "finney": 116}[network]
    )


def _offered(host):
    return {
        (c["challenge_id"], c["version"])
        for c in registry.offered_catalog(host)["challenges"]
        if c["status"] == IMPLEMENTED
    }


def test_testnet_with_the_shipped_endpoints_has_no_motor_door(monkeypatch):
    _bind(monkeypatch, "testnet")
    doorless = es.doorless_versions()
    assert (MOTOR, "1.8") in doorless
    assert (MOTOR, "1.5") in doorless
    # Every version of a Challenge with an intake: the old ones too, so that the newest left
    # over (Motor 1.0, which never had an intake) does not come back once 1.8 is hidden.
    assert (MOTOR, "1.0") in doorless
    # The versions that keep a testnet door stay offered.
    for served in ((COOLING, "1.6"), (BRACKET, "1.7"), (BURST, "2.5")):
        assert served not in doorless
    # Older Cooling versions have no door either; only the launch version is served.
    assert (COOLING, "1.4") in doorless


def test_testnet_offered_list_keeps_every_served_version_and_drops_motor(monkeypatch):
    _bind(monkeypatch, "testnet")
    host = registry.HostFacts(doorless=es.doorless_versions())
    offered = _offered(host)
    assert {(COOLING, "1.6"), (BRACKET, "1.7"), (BURST, "2.5")} <= offered
    assert not {key for key in offered if key[0] == MOTOR}
    assert (COOLING, "1.4") not in offered
    # Unfiltered, the registry still knows every version (history, describe by exact id).
    assert (MOTOR, "1.8") in _offered(registry.HostFacts())
    assert registry.describe(MOTOR, "1.8", host=host)["version"] == "1.8"


def test_finney_offers_motor_1_8_once_its_endpoint_exists(monkeypatch, tmp_path):
    _bind(monkeypatch, "finney")
    path = _published(
        tmp_path,
        [
            _entry("testnet", COOLING, "1.6", "cooling-door"),
            _entry("finney", MOTOR, "1.8", "motor-door-116"),
        ],
    )
    monkeypatch.setattr(es, "PUBLISHED_ENDPOINTS", path)
    host = registry.HostFacts(doorless=es.doorless_versions())
    offered = _offered(host)
    assert (MOTOR, "1.8") in offered
    # The testnet doors are not this deployment's: nothing else is offered on finney.
    assert (COOLING, "1.6") not in offered
    assert not {key for key in offered if key[0] != MOTOR}
    # Before the finney endpoint is published, finney offers no Motor either.
    monkeypatch.setattr(
        es,
        "PUBLISHED_ENDPOINTS",
        _published(tmp_path, [_entry("testnet", COOLING, "1.6", "cooling-door")]),
    )
    assert (MOTOR, "1.8") in es.doorless_versions()


def test_a_practice_only_profile_hides_nothing(monkeypatch):
    _bind(monkeypatch, "testnet")
    assert es.doorless_versions({"practice_principal": "x"}) == frozenset()
    assert es.doorless_versions({"principal": "x"})  # a registered profile does


def test_an_unreadable_endpoint_list_hides_nothing(monkeypatch, tmp_path):
    _bind(monkeypatch, "testnet")
    path = tmp_path / "published_endpoints.json"
    path.write_text("{not json", "utf-8")
    monkeypatch.setattr(es, "PUBLISHED_ENDPOINTS", path)
    assert es.doorless_versions() == frozenset()


def test_the_miners_own_intake_counts_as_a_door(monkeypatch):
    _bind(monkeypatch, "testnet")
    own = es.doorless_versions({"intakes": {MOTOR: "https://own.example"}})
    assert not {key for key in own if key[0] == MOTOR}
    assert (COOLING, "1.4") in own
    # A published endpoint the profile once carried (version_intakes) is not a door:
    # a closed door leaves it behind.
    stale = es.doorless_versions(
        {"version_intakes": {MOTOR: {"1.8": [{"intake_url": "https://x.example"}]}}}
    )
    assert (MOTOR, "1.8") in stale
    served = es.doorless_versions(
        {
            "direct_intake_target": {
                "intake_url": "https://own.example",
                "receiver_hotkey": RECEIVER,
            },
            "direct_intake_serves": {"id": MOTOR, "version": "1.8"},
        }
    )
    assert (MOTOR, "1.8") not in served
    assert (MOTOR, "1.5") in served


def test_the_mcp_host_facts_carry_the_doorless_set(monkeypatch):
    from carbon.miner_mcp.mcp_challenges import configured_host_facts

    _bind(monkeypatch, "testnet")
    assert (MOTOR, "1.8") in configured_host_facts(None).doorless
    assert configured_host_facts({"practice_principal": "x"}).doorless == frozenset()
    # The set is not part of the host's identity: caches keyed by the host are unchanged.
    assert configured_host_facts(None) == registry.HostFacts.observe()


def test_a_failed_read_leaves_the_mcp_list_whole(monkeypatch):
    from carbon.miner_mcp import mcp_challenges

    def broken(profile=None):
        raise RuntimeError("fixture")

    monkeypatch.setattr(es, "doorless_versions", broken)
    assert mcp_challenges._doorless(None) == frozenset()


@pytest.mark.parametrize("practice_only", [False, True])
def test_the_page_document_marks_each_version_with_its_door(monkeypatch, practice_only):
    from scripts.dev.miner_launchpad import capabilities

    _bind(monkeypatch, "testnet")
    cfg = {"practice_principal": "x"} if practice_only else {"principal": "x"}
    host = capabilities._host_facts(cfg)
    rows = {
        (row["challenge_id"], row["version"]): row
        for row in capabilities._challenges(
            {"configured": False, "reason": "none", "next_action": "none"}, host, None
        )
        if row["implemented"]
    }
    for key in ((COOLING, "1.6"), (BRACKET, "1.7"), (BURST, "2.5")):
        assert rows[key]["has_door"] is True
    assert rows[(MOTOR, "1.8")]["has_door"] is practice_only
    assert rows[(COOLING, "1.4")]["has_door"] is practice_only
