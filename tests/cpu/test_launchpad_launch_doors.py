"""The shipped published-endpoints list names only launch doors.

Each entry is one Challenge's launch version behind its Cloudflare door
(`<door>.carbonphysics.ai`), pinned to the published receiver hotkey, for one
network. The list must load (a list that breaks the schema publishes nothing)
and name nothing but the launch versions of each network. A network's door is
its own host: the finney doors carry a `-116` suffix. No network is contacted.
"""

from __future__ import annotations

import json

from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
from scripts.dev.miner_launchpad.environment_setup import (
    PUBLISHED_ENDPOINTS,
    published_endpoints,
)

NETUID = {"testnet": 567, "finney": 116}

LAUNCH = {
    "testnet": {
        ("electric-motor-magnetics", "1.8"): "motor-door",
        ("chip-cold-plate", "1.6"): "cooling-door",
        ("f08-ribbed-bracket", "1.7"): "ribbed-bracket-door",
        ("f02", "2.5"): "burst-thermal-door",
    },
    "finney": {
        ("electric-motor-magnetics", "1.8"): "motor-door-116",
    },
}


def test_shipped_list_loads_and_names_only_launch_doors():
    published = published_endpoints()
    assert published["problem"] is None
    entries = json.loads(PUBLISHED_ENDPOINTS.read_bytes())["endpoints"]
    seen = set()
    for entry in entries:
        network = entry["network"]
        assert network in LAUNCH, network
        assert entry["netuid"] == NETUID[network]
        key = (entry["challenge"], entry["version"])
        assert key in LAUNCH[network], (network, key)
        assert entry["intake_url"] == f"https://{LAUNCH[network][key]}.carbonphysics.ai"
        assert (network, key) not in seen
        seen.add((network, key))
        if (network, entry["netuid"]) == (CARBON_NETWORK, CARBON_NETUID):
            assert (
                published["endpoints"][key[0]][key[1]]["intake_url"]
                == entry["intake_url"]
            )
