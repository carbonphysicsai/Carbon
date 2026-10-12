"""Registry v10's `sign` gate measure (SCORE-PROOF-01 amendment 11).

Sign consistency at probe pairs, from PHYSICS-CONTRACT-01's pair laws B5-B8:
pairs of scoring cases that differ in exactly one law input, all other inputs
equal. Per law, the output is the contract's measured quantity:

- B5: peak temperature against c1, and against c2;
- B6: plating margin against c1;
- B7: plating margin against T_amb;
- B8: peak temperature against T_amb.

The measure is the share of evaluable pairs on which the member's predicted
change has the opposite sign to the REFERENCE's change (a zero predicted
change counts as a disagreement). A pair is evaluable when the reference's
|change| is at least `EPSILON` of that output's reference range over the
law's pairs. The reference's sign is used, not the law's asserted direction,
so B7's possible non-monotonicity at high rate (RES-06) cannot fail a correct
model. `None` (unmeasured) when no pair is evaluable, or when any evaluable
pair lacks a prediction: an unmeasured gate withholds its candidates.

EPSILON is a registered candidate value; adopting it is HUMAN_INPUT.
DEVELOPMENT only.
"""

from __future__ import annotations

from itertools import combinations

from . import decision as d

EPSILON = 0.01
#: (law, measured output, varied input).
PAIR_LAWS = (
    ("B5", "peak_temperature_c", "c1"),
    ("B5", "peak_temperature_c", "c2"),
    ("B6", "plating_margin_v", "c1"),
    ("B7", "plating_margin_v", "t_amb_c"),
    ("B8", "peak_temperature_c", "t_amb_c"),
)


def probe_pairs(refs, case_ids, varied):
    """Case pairs that differ in `varied` only, every other input equal."""
    groups = {}
    for case_id in case_ids:
        inputs = refs[case_id].get("inputs") or {}
        if varied not in inputs:
            continue
        rest = tuple(sorted((k, v) for k, v in inputs.items() if k != varied))
        groups.setdefault(rest, []).append(case_id)
    out = []
    for members in groups.values():
        for a, b in combinations(sorted(members), 2):
            if refs[a]["inputs"][varied] != refs[b]["inputs"][varied]:
                out.append((a, b))
    return out


def _sign(x):
    return (x > 0) - (x < 0)


def sign_disagreement(contract, predictions, case_ids, refs, measure=None):
    """The member's share of evaluable probe pairs with the wrong sign, or None."""
    measure = d.measure if measure is None else measure
    truth = {}
    for case_id in case_ids:
        outputs = refs[case_id].get("outputs")
        if outputs is not None:
            truth[case_id] = measure(contract, outputs)
    said = {}
    evaluated = disagree = 0
    for _law, output, varied in PAIR_LAWS:
        pairs = [
            (a, b)
            for a, b in probe_pairs(refs, case_ids, varied)
            if a in truth and b in truth
        ]
        values = [truth[c][output] for pair in pairs for c in pair]
        if not values:
            continue
        floor = EPSILON * (max(values) - min(values))
        for a, b in pairs:
            ref_change = truth[b][output] - truth[a][output]
            if abs(ref_change) < floor or ref_change == 0:
                continue
            for c in (a, b):
                if c not in said:
                    if predictions.get(c) is None:
                        return None
                    said[c] = measure(contract, predictions[c])
            evaluated += 1
            if _sign(said[b][output] - said[a][output]) != _sign(ref_change):
                disagree += 1
    return None if evaluated == 0 else disagree / evaluated
