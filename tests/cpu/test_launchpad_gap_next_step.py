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
    # Still a registered catalog refusal code, so a renamed code fails here.
    assert code in entries.REFUSAL_CODES
