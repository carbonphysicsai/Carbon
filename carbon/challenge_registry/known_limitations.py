"""Known limitations a Challenge version's card states, as the Validator
recorded them: one table for every Challenge (owner rule, 22 Oct: one
component across all five, no per-Challenge copies).

Keyed by Challenge id, then by version; "*" is every version of that
Challenge. Each line is shown to miners as it is written here.
"""

from __future__ import annotations

from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

KNOWN_LIMITATIONS = {
    # VALIDATOR_RULING_COOLING12_PEAK_GATE_20261022, finding G1: the gate
    # stands; the fix is the law-safe encoding on Cooling 1.3.
    COLD_PLATE_CHALLENGE: {
        "1.2": (
            (
                "Catalog recipes on this version are not eligible: the output "
                "encoding does not keep the peak temperature at or above its "
                "profile, so the mandatory peak_bounds_profile gate fails. A "
                "law-safe encoding comes with Cooling 1.3."
            ),
        ),
    },
    # VALIDATOR_BATTERY_SEALED_RULINGS_20261022, section 13: a statement
    # about Battery's sealed exam, so on every Battery version's card.
    BATTERY_CHALLENGE: {
        "*": (
            (
                "The sealed exam does not examine ambient below 10 °C with "
                "initial state of charge above 0.42, where the reference "
                "solver fails."
            ),
        ),
    },
}


def known_limitations(challenge_id, version):
    """The known limitations the card of `challenge_id` `version` states."""
    table = KNOWN_LIMITATIONS.get(challenge_id, {})
    return [*table.get("*", ()), *table.get(version, ())]
