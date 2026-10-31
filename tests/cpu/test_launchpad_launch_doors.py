"""The shipped published-endpoints list names only launch doors.

Each entry is one Challenge's launch version behind its Cloudflare door
(`<door>.carbonphysics.ai`), pinned to the published receiver hotkey. The list
must load (a list that breaks the schema publishes nothing) and name nothing but
the launch versions. No network is contacted.
"""

from __future__ import annotations

import json

from scripts.dev.miner_launchpad.environment_setup import (
    PUBLISHED_ENDPOINTS,
    published_endpoints,
)

LAUNCH = {
    ("electric-motor-magnetics", "1.5"): "motor-door",
    ("chip-cold-plate", "1.6"): "cooling-door",
    ("f08-ribbed-bracket", "1.7"): "ribbed-bracket-door",
    ("f02", "2.5"): "burst-thermal-door",
}


def test_shipped_list_loads_and_names_only_launch_doors():
    published = published_endpoints()
    assert published["problem"] is None
    entries = json.loads(PUBLISHED_ENDPOINTS.read_bytes())["endpoints"]
    seen = set()
    for entry in entries:
        key = (entry["challenge"], entry["version"])
        assert key in LAUNCH, key
        assert entry["intake_url"] == f"https://{LAUNCH[key]}.carbonphysics.ai"
        assert key not in seen
        seen.add(key)
        assert (
            published["endpoints"][key[0]][key[1]]["intake_url"] == entry["intake_url"]
        )
