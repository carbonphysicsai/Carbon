"""Every implemented campaign's research composition builds (BUG
MOTOR_COOLING_EMPTY_STRATA_20261020).

Motor and Cooling passed `()` as their measurement contract's stratum
applicability, which the measurement layer refuses (it requires at least one
binding), so a Graphite launch on either stopped at `run` before any model
call, on every base. No test built their `challenge_parts()`; this one builds
every implemented campaign's, from the registry, so a new campaign cannot be
missed, and composes its research service as a launch does.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from carbon.challenge_registry.campaigns import implemented_campaigns
from carbon.development_session import research_service
from carbon.measurement import model as m
from test_lp_prod_research_tools import ledger

CAMPAIGNS = implemented_campaigns()


def _research(campaign):
    return importlib.import_module(
        campaign.compose.__module__.rsplit(".", 1)[0] + ".research"
    )


def test_the_registry_lists_battery_motor_and_cooling():
    ids = {campaign.key.challenge_id for _, campaign in CAMPAIGNS}
    assert {
        "battery-fastcharge-ageing-development-v1",
        "electric-motor-magnetics",
        "chip-cold-plate",
    } <= ids


@pytest.mark.parametrize(
    "campaign", [c for _, c in CAMPAIGNS], ids=lambda c: c.key.challenge_id
)
def test_each_campaign_builds_its_parts_and_composes(campaign, tmp_path):
    parts = _research(campaign).challenge_parts()
    assert parts.key == campaign.key
    contract = parts.measurements
    assert type(contract) is m.MeasurementContract
    assert len(contract.stratum_applicability) >= 1
    for binding in contract.stratum_applicability:
        assert binding.stratum_ref.challenge_key == campaign.key
    composition = research_service.compose_research_service(
        parts,
        root=tmp_path / "tasks",
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=SimpleNamespace(),
    )
    composition.tasks.close()
