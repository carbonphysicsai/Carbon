"""The conditions of OWNER-COOL18-FIT-BREAKER-SEAL-WAIVER-01 hold while any row names it.

The record waives three fit-breaker rules for Cooling 1.8 until its seal: `separation_read`, `engineer_shortcut_d_zero`
and `ood_min_accuracy`. The conformance test itself is unchanged. This file pins the waiver's conditions, each one
read from the repository:
- only Cooling 1.8 names the record;
- the version is not served;
- it grades nothing (its row still refuses registration);
- the conditions report's bytes are the ones the waiver names.

The seal change removes the waiver entries in the same change that switches the rules on, and this file then has
nothing to check.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONSTANTS = ROOT / "scripts" / "validator_host_classes" / "pool_constants.json"
DECISIONS = ROOT / ".agent" / "decisions"
ENDPOINTS = ROOT / "scripts" / "dev" / "miner_launchpad" / "published_endpoints.json"
RECORD = "OWNER-COOL18-FIT-BREAKER-SEAL-WAIVER-01"
CONDITIONS = DECISIONS / "2026-11-12-COOL18-FIT-BREAKER-WAIVER-CONDITIONS.md"
COOLING_18 = ("chip-cold-plate", "1.8")
WAIVED = ("separation_read", "engineer_shortcut_d_zero", "ood_min_accuracy")


def _record_id(waiver):
    return waiver.get("record") if type(waiver) is dict else waiver


def _naming():
    """``{row name: [rule, ...]}`` of every row whose fit-breaker waivers name the record."""
    document = json.loads(CONSTANTS.read_bytes())
    found = {}
    for name, row in document["versions"].items():
        waivers = (row.get("fit_breaker") or {}).get("waivers") or {}
        rules = sorted(r for r, w in waivers.items() if _record_id(w) == RECORD)
        if rules:
            found[name] = rules
    return found, document


def test_only_cooling_1_8_names_the_seal_waiver_and_only_its_three_rules():
    found, _ = _naming()
    if not found:
        pytest.skip("the seal waiver is gone: Cooling 1.8's rules are checked in full")
    assert found == {"chip-cold-plate 1.8": sorted(WAIVED)}


def test_while_waived_cooling_1_8_is_not_served_and_grades_nothing():
    found, _ = _naming()
    if not found:
        pytest.skip("the seal waiver is gone")
    from carbon.challenge_registry import published_exam
    from carbon.scoring import pool_version

    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies(*COOLING_18)
    assert COOLING_18 not in published_exam._REGISTERED_POOL
    endpoints = json.loads(ENDPOINTS.read_bytes())["endpoints"]
    assert endpoints  # the list is read, not absent
    served = {(e.get("challenge"), e.get("version")) for e in endpoints}
    assert COOLING_18 not in served


def test_the_waiver_names_the_tracked_conditions_report_by_its_bytes():
    found, document = _naming()
    if not found:
        pytest.skip("the seal waiver is gone")
    waiver = document["versions"]["chip-cold-plate 1.8"]["fit_breaker"]["waivers"][
        "ood_min_accuracy"
    ]
    raw = CONDITIONS.read_bytes()
    assert b"\r" not in raw
    assert waiver["conditions_report_sha256"] == hashlib.sha256(raw).hexdigest()
    assert RECORD in raw.decode("utf-8")
