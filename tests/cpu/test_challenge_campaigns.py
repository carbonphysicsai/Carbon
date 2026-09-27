"""A campaign reaches Challenge-specific behaviour only through the registry."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.challenge_registry import campaigns
from carbon.challenge_registry.registry import (
    ChallengeDeferred,
    ChallengeNotImplemented,
    UnknownChallenge,
    UnsupportedVersion,
)
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    BATTERY_CONTRACT,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (
    ROOT / "carbon" / "development_session" / "research_campaign.py",
    ROOT / "carbon" / "miner_mcp" / "standard_cli.py",
)


def _imports(path, package):
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        found += [n for n in names if n == package or n.startswith(package + ".")]
    return found


@pytest.mark.parametrize("path", WORKFLOW, ids=lambda p: p.name)
def test_the_shared_workflow_names_no_challenge_package(path):
    assert _imports(path, "carbon.battery") == []


def test_the_import_scan_finds_a_challenge_package_where_one_is_imported():
    # The specimen: the adapter module does import battery, so a scan that
    # could not see such an import would fail here rather than pass above.
    specimen = ROOT / "carbon" / "challenge_registry" / "campaigns.py"
    assert _imports(specimen, "carbon.battery") == ["carbon.battery"]


def test_battery_resolves_to_its_own_campaign():
    campaign = campaigns.campaign_for(
        {"id": BATTERY_CHALLENGE, "version": BATTERY_CONTRACT.version}
    )
    from carbon.battery import campaign as battery

    assert campaign.key == battery.CHALLENGE
    assert campaign.evaluate is battery.evaluate_frozen
    assert campaign.refusal_retains_candidate is True
    assert campaign.check_attached is battery.check_attached


@pytest.mark.parametrize(
    ("challenge", "refusal"),
    [
        ({"id": "chip-cold-plate", "version": None}, ChallengeNotImplemented),
        ({"id": "airfoil", "version": None}, ChallengeDeferred),
        ({"id": "no-such-challenge", "version": "1"}, UnknownChallenge),
        ({"id": BATTERY_CHALLENGE, "version": "0.0-not-it"}, UnsupportedVersion),
    ],
)
def test_an_unusable_selection_is_refused_by_its_code(challenge, refusal):
    with pytest.raises(refusal):
        campaigns.campaign_for(challenge)


def test_a_registered_challenge_without_a_campaign_is_refused(monkeypatch):
    monkeypatch.setattr(campaigns, "_campaigns", dict)
    with pytest.raises(campaigns.NoCampaignComposition) as refused:
        campaigns.campaign_for(
            {"id": BATTERY_CHALLENGE, "version": BATTERY_CONTRACT.version}
        )
    assert refused.value.public()["code"] == "challenge_has_no_campaign"


def test_a_selection_must_be_a_mapping():
    with pytest.raises(TypeError):
        campaigns.campaign_for(BATTERY_CHALLENGE)
