"""The published endpoints list carries Motor 1.8 on finney subnet 116 beside the testnet entries (13 Nov).

A miner on finney 116 reads the entry for (finney, 116) only, and a testnet miner never sees it: entries for another network or
subnet are skipped. The real file loads without a problem (a malformed entry would publish nothing at all).
"""

from __future__ import annotations

import json

import pytest

from carbon.chain import models
from scripts.dev.miner_launchpad import environment_setup as environment

MOTOR = "electric-motor-magnetics"
FINNEY_URL = "https://motor-door-116.carbonphysics.ai"
FINNEY_RECEIVER = "5DDLUnX2yicKLC1T5PN7bkwgU51buJt93XQFV1giqhDsGUTk"


def test_the_list_names_motor_1_8_on_finney_116_exactly():
    document = json.loads(environment.PUBLISHED_ENDPOINTS.read_bytes())
    finney = [e for e in document["endpoints"] if e["network"] == "finney"]
    assert finney == [
        {
            "network": "finney",
            "netuid": 116,
            "challenge": MOTOR,
            "version": "1.8",
            "intake_url": FINNEY_URL,
            "receiver_hotkey": FINNEY_RECEIVER,
        }
    ]
    # the testnet entries are untouched: four, all on netuid 567
    testnet = [e for e in document["endpoints"] if e["network"] == "testnet"]
    assert len(testnet) == 4 and {e["netuid"] for e in testnet} == {567}


@pytest.fixture
def on(monkeypatch):
    def select(network, netuid):
        monkeypatch.setattr(models, "CARBON_NETWORK", network)
        monkeypatch.setattr(models, "CARBON_NETUID", netuid)
        return environment.published_endpoints()

    return select


def test_a_finney_116_miner_reads_only_the_finney_entry(on):
    published = on("finney", 116)
    assert published["problem"] is None
    assert published["endpoints"] == {
        MOTOR: {
            "1.8": {
                "intake_url": FINNEY_URL,
                "receiver_hotkey": FINNEY_RECEIVER,
                "network": "finney",
                "netuid": 116,
                "challenge": MOTOR,
                "version": "1.8",
            }
        }
    }


def test_a_testnet_miner_never_sees_the_finney_entry(on):
    published = on("testnet", 567)
    assert published["problem"] is None
    urls = {
        entry["intake_url"]
        for versions in published["endpoints"].values()
        for entry in versions.values()
    }
    assert FINNEY_URL not in urls
    assert set(published["endpoints"]) == {
        "f08-ribbed-bracket",
        MOTOR,
        "chip-cold-plate",
        "f02",
    }
    assert (
        published["endpoints"][MOTOR]["1.8"]["intake_url"]
        == "https://motor-door.carbonphysics.ai"
    )
