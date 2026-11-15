"""The Motor 1.8 kit page states the information budget the grade enforces: allowlist v8 serves accounting v6, whose one
budget is the zlib-9 compressed size of the whole recipe, capped at `V6_CONSTANT_BYTES` (read here, not retyped).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from carbon.level4 import allowlist

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "kits" / "motor" / "HOW_YOURE_TESTED.md"
OVERLAY = ROOT / "scripts" / "validator_host_classes" / "version_overlay.json"
MINING = ROOT / "docs" / "MINING.md"


def _page():
    return " ".join(PAGE.read_text(encoding="utf-8").split())


def test_motor_18_is_on_allowlist_v8_which_serves_accounting_v6():
    row = json.loads(OVERLAY.read_text(encoding="utf-8"))["versions"][
        "electric-motor-magnetics 1.8"
    ]
    version = "level4-allowlist-" + row["allowlist"]
    assert version in allowlist.ACCOUNTING_V6_VERSIONS
    assert allowlist.accounting_for(version)[0] == allowlist.CONSTANT_ACCOUNTING_V6
    assert allowlist.caps_for(version)["constant_bytes"] == allowlist.V6_CONSTANT_BYTES


def test_page_states_the_v6_budget_as_one_compressed_size_of_the_whole_graph():
    text = _page()
    kib = allowlist.V6_CONSTANT_BYTES // 1024
    assert allowlist.V6_CONSTANT_BYTES % 1024 == 0
    bullet = re.search(r"\*\*Information budget:\*\* (.*?) - \*\*", text)
    assert bullet is not None, "the information budget bullet is missing"
    words = bullet.group(1)
    assert f"one {kib} KiB budget" in words
    assert "compressed (zlib level 9) size" in words
    for counted in ("operations", "wiring", "shapes", "constants", "static value"):
        assert counted in words, counted
    # the older caps and the older per-value accounting are not the page's budget
    assert "16 KiB" not in words
    assert "by what it holds" not in words


def _mining_bullet(label):
    text = " ".join(MINING.read_text(encoding="utf-8").split())
    found = re.search(r"- \*\*" + re.escape(label) + r"(.*?) - \*\*", text)
    assert found is not None, label
    return found.group(1)


def test_mining_guide_states_the_same_v6_budget_in_both_places_it_names_it():
    kib = allowlist.V6_CONSTANT_BYTES // 1024
    for label in (
        "Constants and static values.",
        "Fitted constants and small tables inside the graph: yes, inside the 32 KiB budget.",
    ):
        words = _mining_bullet(label)
        assert f"one {kib} KiB budget" in words, label
        assert "compressed (zlib level 9) size" in words, label
        # the older per-value accounting and the older cap are not the guide's budget
        assert "identical copies once" not in words, label
        assert "by what it holds" not in words, label
        assert "16 KiB" not in words, label
        assert "uses only a small part of the budget" not in words, label
    assert f"inside the {kib} KiB budget" in " ".join(
        MINING.read_text(encoding="utf-8").split()
    )


def test_mining_guide_no_longer_promises_averaged_crowns_on_motor_18():
    text = " ".join(MINING.read_text(encoding="utf-8").split())
    assert "crown averaging" not in text
    assert "average over several seeds" not in text
    assert (
        "On Motor 1.8 the crown is decided on that official grade, with no averaging over seeds or rebuilds."
        in text
    )


def test_mining_guide_states_the_registered_motor_18_margin_and_no_open_crown_for_cooling_16():
    margin = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "crown_official_score.json"
        ).read_text(encoding="utf-8")
    )["versions"]["electric-motor-magnetics 1.8"]["margin"]
    text = " ".join(MINING.read_text(encoding="utf-8").split())
    assert f"On Motor 1.8 the margin is {margin:g} and takeovers are live." in text
    assert f"on Motor 1.8 it is {margin:g};" in text
    assert "The margin is **not yet registered**" not in text
    assert "so takeovers are paused" not in text
    # Cooling 1.6 has no crown rule registered anywhere, so the guide may say no crown is open for it
    floors = json.loads(
        (ROOT / "scripts" / "validator_host_classes" / "crown_floor.json").read_text(
            encoding="utf-8"
        )
    )["floors"]
    registered = {(row["challenge"], row["version"]) for row in floors}
    assert ("chip-cold-plate", "1.6") not in registered
    assert (
        "Crowns are not open for this version: no crown rule is registered for it, so no crown changes hands."
        in text
    )
