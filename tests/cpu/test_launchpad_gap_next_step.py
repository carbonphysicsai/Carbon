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
