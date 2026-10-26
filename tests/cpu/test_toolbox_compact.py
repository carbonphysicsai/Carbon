"""Test Runner 03:20Z, RED A: carbon_toolbox for Motor 1.4 was 173,751 bytes on rc50 (the catalog
half of it), so an agent that cannot read a spilled file (Hermes) could not use it. The default
answer now summarises the long catalog and family lists; `include` brings them back whole."""

from __future__ import annotations

import json

import pytest

from scripts.dev.miner_launchpad import supervisor, toolbox
from scripts.dev.miner_launchpad.controller import Rejected

LAUNCH = [
    ("electric-motor-magnetics", "1.4"),
    ("chip-cold-plate", "1.4"),
    ("f08-ribbed-bracket", "1.5"),
    ("f02", "2.4"),
]


def _ask(challenge, version, **extra):
    return toolbox.for_request(
        None, {"challenge": challenge, "challenge_version": version, **extra}, lanes={}
    )


def _size(value):
    return len(json.dumps(value, separators=(",", ":")).encode())


@pytest.mark.parametrize(("challenge", "version"), LAUNCH)
def test_the_default_answer_is_small_enough_for_any_agent(challenge, version):
    box = _ask(challenge, version)
    assert _size(box) <= toolbox.COMPACT_TARGET_BYTES, _size(box)
    # What an agent needs to start is whole: the ready examples.
    assert box["examples"] and all(type(e) is dict for e in box["examples"])
    assert box["catalog"]["summary"] is True and box["catalog"]["entries"] > 0
    assert box["catalog"]["ready_example"]
    assert "include=catalog" in box["catalog"]["full"]
    assert box["families"]["summary"] is True and box["families"]["count"] > 0


@pytest.mark.parametrize(("challenge", "version"), LAUNCH[:1])
def test_include_brings_the_full_lists_back(challenge, version):
    whole = _ask(challenge, version, include="catalog,families")
    assert type(whole["catalog"]) is list and type(whole["families"]) is list
    assert _size(whole) > 4 * toolbox.COMPACT_TARGET_BYTES  # the long lists really are long
    only_catalog = _ask(challenge, version, include="catalog")
    assert type(only_catalog["catalog"]) is list
    assert only_catalog["families"]["summary"] is True
    compact = _ask(challenge, version)
    # The summary loses nothing it names: the same number of entries.
    assert compact["catalog"]["entries"] == len(whole["catalog"])
    assert compact["families"]["count"] == len(whole["families"])


def test_a_bad_include_is_refused_with_a_next_step():
    for bad in ("catalogs", "catalog;families", 3):
        with pytest.raises(Rejected) as refused:
            _ask("electric-motor-magnetics", "1.4", include=bad)
        assert refused.value.code == "toolbox_include_invalid"
    assert "catalog" in supervisor.NEXT_ACTIONS.get(
        "toolbox_include_invalid", supervisor.next_action("toolbox_include_invalid")
    )


def test_the_page_s_own_reader_is_untouched():
    """The page builds its editor from `build`, never `for_request`: the full picker stays."""
    box = toolbox.build({"id": "electric-motor-magnetics", "version": "1.4"}, lanes={})
    assert type(box["catalog"]) is list and type(box["families"]) is list
