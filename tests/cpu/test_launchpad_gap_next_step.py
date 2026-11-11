"""A build refused for a Carbon capability gap gets the Validator's one GAP
line (2026-10-20), never the fallback's "correct what it names"."""

from __future__ import annotations

from carbon.development_session import build_refusal
from scripts.dev.miner_launchpad.supervisor import FALLBACK_ACTION, NEXT_ACTIONS


def test_the_public_gap_code_has_the_validators_one_line():
    step = NEXT_ACTIONS["carbon_capability_gap"]
    assert step != FALLBACK_ACTION
    assert step.startswith(
        "Carbon capability gap: this doesn't count against you; the op is on "
        "Carbon's add list; see the kit's supported-ops notes for an alternative"
    )


def test_the_private_build_refusal_codes_have_no_per_code_steps():
    # One line for the class: the private reason codes never reach the miner.
    assert not set(build_refusal.CODES) & set(NEXT_ACTIONS)


def test_a_catalog_backbone_not_gpu_checked_is_carbons_side_not_the_fallback():
    from carbon.backbone_catalog import entries, served
    from scripts.dev.miner_launchpad.supervisor import next_action

    code = "catalog_gpu_receipt_pending"
    step = next_action(code)
    assert step == NEXT_ACTIONS[code] != FALLBACK_ACTION
    assert "change what this names" not in step  # never the miner's setup
    assert "Carbon's side" in step and "does not count against you" in step
    # The picker's own note, word for word, so the miner can find the safe choices.
    assert served.GPU_RECEIPT_PENDING in step
    assert "own graph" in step and "Practice" in step
    assert "practice only" in step  # the smoke-only entries' picker label
    # Still a registered catalog refusal code, so a renamed code fails here.
    assert code in entries.REFUSAL_CODES


def test_the_smoke_only_catalog_entries_are_marked_practice_only():
    import json

    from carbon.backbone_catalog import gpu_receipt
    from scripts.dev.miner_launchpad import toolbox

    seen = set()
    for challenge_id, version in (
        ("electric-motor-magnetics", "1.6"),
        ("chip-cold-plate", "1.7"),
        ("f08-ribbed-bracket", "1.7"),
        ("f02", "2.5"),
    ):
        for entry in json.loads(toolbox._catalog_recipes(challenge_id, version)):
            if entry["catalog_id"] in gpu_receipt.SMOKE_ONLY:
                seen.add(entry["catalog_id"])
                assert entry["practice_only"] == toolbox.PRACTICE_ONLY_NOTE
                assert entry.get("recommended") is not True  # never the starting entry
            else:
                assert "practice_only" not in entry
    assert seen, "no smoke-only entry is served on the checked versions"
    note = toolbox.PRACTICE_ONLY_NOTE
    assert note.startswith("Practice only:") and "bit-reproducible on the GPU" in note
    assert "Pick another entry to be graded." in note


def test_the_picker_shows_practice_only_unless_the_validator_lists_it_ready():
    import pathlib

    app = pathlib.Path("scripts/dev/miner_launchpad/app.js").read_text(encoding="utf-8")
    assert "item.officially_gradable !== true" in app
    assert '" (practice only)"' in app
    assert "current().practice_only" in app
