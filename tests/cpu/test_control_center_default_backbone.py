"""The Control Center's default backbone is the starting entry, never a smoke-only CNO build, on every launch version.

The picker's `recommended` entry (`toolbox.catalog_recipes`), the MCP door's ready recipe (`_baseline_start`) and
`starting_entry` must name the same catalog id; that id must not be in `gpu_receipt.SMOKE_ONLY` (smoke-only on GPU: it
can never be graded officially). The page keeps the starting entry in place of the untouched registered example
(`control_center_page_check.cjs`, "the backbone picker starts on the server's starting entry").
"""

import pytest

from carbon.backbone_catalog import gpu_receipt
from carbon.challenge_kit import served_versions
from carbon.miner_mcp import mcp_challenges
from scripts.dev.miner_launchpad import toolbox
from scripts.dev.miner_launchpad.starting_entry import starting_entry

LAUNCH_VERSIONS = {
    (served_versions.COOLING, "1.6"): "v2.cooling.physicsnemo.MeshGraphNet",
    (served_versions.F02, "2.5"): "v2.f02.prior_krr",
    (served_versions.MOTOR, "1.5"): "v2.motor.prior_krr",
    (served_versions.F08, "1.7"): "v2.f08.prior_krr",
}


def _launch_versions():
    return list(LAUNCH_VERSIONS)


@pytest.mark.parametrize("challenge_id,version", _launch_versions())
def test_control_center_default_is_the_starting_entry(challenge_id, version):
    expected = LAUNCH_VERSIONS[(challenge_id, version)]
    assert starting_entry(challenge_id, version) == expected
    recommended = [
        item["catalog_id"]
        for item in toolbox.catalog_recipes(challenge_id, version)
        if item.get("recommended") is True
    ]
    assert recommended == [expected]
    assert expected not in gpu_receipt.SMOKE_ONLY


@pytest.mark.parametrize("challenge_id,version", _launch_versions())
def test_mcp_door_default_agrees(challenge_id, version):
    ready = {
        "schema": "carbon.construction-recipe.v1",
        "source": {"kind": "catalog", "catalog_id": "cno.CNO1d"},
    }
    described = {"challenge_id": challenge_id, "version": version}
    swapped = mcp_challenges._baseline_start(described, "recipe", ready)
    assert swapped["source"]["catalog_id"] == starting_entry(challenge_id, version)
