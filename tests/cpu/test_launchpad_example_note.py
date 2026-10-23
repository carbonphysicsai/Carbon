"""A catalog example never reads as a recipe tested to grade valid (Validator,
2026-10-23: F02 2.3's FullyConnected default fails verified_pick)."""

from __future__ import annotations

from carbon.challenge_kit import version_registry
from carbon.challenge_registry import direct
from carbon.direct_campaign.spec import SPECS


def test_every_catalog_example_says_it_is_a_starting_point_not_a_valid_grade():
    with_examples = []
    for spec in SPECS.values():
        for version in spec.versions:
            if version_registry.find(spec.challenge_id, version) is None:
                continue  # not served (Battery 2.2, OWNER-BATTERY-OUT-OF-LAUNCH-01)
            document = direct.describe(spec, version)
            if document.get("examples"):
                with_examples.append((spec.challenge_id, version))
                assert document["examples_note"] == direct.EXAMPLE_NOTE
            else:
                # An empty catalog keeps its round-8b note: why there is no
                # ready recipe yet, never the example note.
                assert document.get("examples_note") != direct.EXAMPLE_NOTE
    assert ("f02", "2.3") in with_examples
    assert "not a recipe tested to pass" in direct.EXAMPLE_NOTE


def test_the_toolbox_carries_the_note_beside_its_examples():
    from scripts.dev.miner_launchpad import toolbox

    built = toolbox.build({"id": "f02", "version": "2.3"}, lanes={}, direct=True)
    assert built["examples"]
    assert built["examples_note"] == direct.EXAMPLE_NOTE
