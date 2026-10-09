"""The development ladder's operator configuration against the real variant
registry (VALIDATOR-25): every variant the operator sheet lists for L1 to L3
is a registered variant of its level on battery's contract, so the sheet's
`ladder.json` loads. Registry data only.
"""

from __future__ import annotations

from carbon.battery import deployment

MINER_C = "5E49MhzFLBv35AbSPgtwrutCd6yvDm6GK9EC5ocmJ3Czb48N"
TESTNET = {
    "network": "testnet",
    "endpoint": "wss://test.finney.opentensor.ai:443",
    "provider": "bittensor-official-test",
    "genesis_hash": (
        "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
    ),
    "netuid": 567,
}
#: The operator sheet's variants (LADDER_DEPLOYMENT_VALV2.md step 1).
SHEET_VARIANTS = (
    "battery-l1-loss-expressions-v1",
    "battery-l2-v2",
    "battery-l3-numerics-v1",
)


def test_the_sheets_l1_to_l3_ladder_loads_on_the_real_registry():
    ladder = deployment.ladder_for(
        {
            "development_only": True,
            "batch_source": "answer_key",
            "require_commitment": True,
            "commitment_reader": dict(TESTNET),
            "ladder": {
                "levels": [1, 2, 3],
                "hotkeys": [MINER_C],
                "variants": list(SHEET_VARIANTS),
            },
        }
    )
    found = sorted((s["level"], s["version"]) for s in ladder["variants"].values())
    assert found == [
        (1, "battery-l1-loss-expressions-v1"),
        (2, "battery-l2-v2"),
        (3, "battery-l3-numerics-v1"),
    ]
