"""The Control Center's capability document is not rebuilt from the registry on
every read (M3b Test Runner: 31 s per read on a quiet machine, past the page's 20 s
deadline). A version's description and what is derived from it are kept for the life
of the process, per host facts, and every use gets its own copy."""

from __future__ import annotations

from scripts.dev.miner_launchpad import capabilities

F08 = ("f08-ribbed-bracket", "1.5")


def _challenge(document, key):
    return next(
        c for c in document["challenges"] if (c["challenge_id"], c["version"]) == key
    )


def test_the_registry_is_described_once_per_version_and_host(monkeypatch):
    from carbon.challenge_registry import registry

    calls = []
    real = registry.describe

    def counting(challenge_id, version, *, host=None):
        calls.append((challenge_id, version))
        return real(challenge_id, version, host=host)

    capabilities._STATIC.clear()
    monkeypatch.setattr("carbon.challenge_registry.describe", counting)
    first = capabilities.control_center(None)
    described = len(calls)
    assert described > 0
    second = capabilities.control_center(None)
    assert len(calls) == described  # nothing described again
    assert first["challenges"] == second["challenges"]


def test_a_caller_changing_a_read_cannot_change_the_next(monkeypatch):
    capabilities._STATIC.clear()
    first = capabilities.control_center(None)
    item = _challenge(first, F08)
    item["description"]["title"] = "tampered"
    item["catalog_recipes"].append({"tampered": True})
    item["tools"] = ["tampered"]
    again = _challenge(capabilities.control_center(None), F08)
    assert again["description"]["title"] != "tampered"
    assert {"tampered": True} not in again["catalog_recipes"]
    assert again["tools"] != ["tampered"]


def test_the_cache_is_per_host_facts():
    from carbon.challenge_registry.registry import HostFacts

    capabilities._STATIC.clear()
    capabilities._static_description(*F08, HostFacts(frozenset()))
    capabilities._static_description(*F08, HostFacts(frozenset({"docker_cli"})))
    assert len(capabilities._STATIC) == 2
