"""Score-value divergence: the condition a run emits, not a judgement.

OWNER-CHALLENGE-ADMISSION-01 (amended 2026-10-01) §3.2: an attack vector is
"anything that scored high and produced a poorly performing model... also
failing triggers and whatnot". This module turns that into conditions computed
from an engineering-value result (`carbon.engineering-value-results.v1`), so a
finding never depends on someone noticing. When in doubt it fires.

**SCORE_VALUE_DIVERGENCE** fires for member X on a split when some eligible
member Y makes clearly better decisions, yet X scores at or above Y under the
deciding rule:

    loss(Y) + band < loss(X)   and   score(X) >= score(Y)

- "Better decisions" is the result's own decision loss (lower is better);
  "score" is the deciding rule's score in `rule_scores` (higher is better).
- `band` is the loss noise band (`loss_noise_band`): the largest spread of
  decision loss between reconstruction seeds of one recipe in the same result.
  It is derived from the retained evidence, not chosen. A gap inside it is not
  counted, because a seed change alone moves loss that far.
- No threshold, rank cut or score scale is chosen here; the comparison is
  relative to the panel.

**GATE_ANOMALY** fires for every member that fails a mandatory gate.

Escalation (§3.3, §6.2): a condition stops widening. The state to review is the
newest expansion record per Challenge (Launchpad's §6.1 record, #468:
`carbon/reconstruction/expansions/<challenge>/NNNN.json`). This module does not
read that record; it names it.

**The progress noise band** (§4.2) is `tau_noise_band`: how far Kendall τ
between the deciding rule's ranking and the value ranking moves when only the
choice of reconstruction seed per recipe changes. A study counts as progress
only if its τ improves by more than that band.

Internal development evidence (§2): not a qualification gate, not mainnet.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from .decision import kendall_tau_b

SCHEMA = "carbon.admission-condition.v1"
DECIDING_RULE = "control-exam-v1"
SPLITS = ("development", "verification")
REVIEW_STATE = (
    "the newest expansion record per Challenge "
    "(carbon/reconstruction/expansions/<challenge>/NNNN.json, #468)"
)


def _check(results):
    if results.get("schema") != "carbon.engineering-value-results.v1":
        raise ValueError("unsupported_ev_result")


def _recipe(member):
    return member.rsplit("-s", 1)[0]


def loss_noise_band(results, split):
    """The largest seed-to-seed spread of decision loss within one recipe.

    None when no recipe has two seeds: then nothing is subtracted, so the
    detector fires on any gap (when in doubt, fire).
    """
    spreads = [
        row[split]["max"] - row[split]["min"]
        for row in results["seed_variation"].values()
        if row[split]["seeds"] >= 2
        and row[split]["max"] is not None
        and row[split]["min"] is not None
    ]
    return max(spreads) if spreads else None


def conditions(results, rule=DECIDING_RULE):
    """Every condition this result emits, in a stable order."""
    _check(results)
    members = results["summary"]["members"]
    out = []
    for member in sorted(members):
        if members[member]["eligible"] is not True:
            out.append(
                {
                    "schema": SCHEMA,
                    "condition": "GATE_ANOMALY",
                    "member": member,
                    "kind": members[member]["kind"],
                    "basis": "summary.members.<member>.eligible is false",
                    "review_state": REVIEW_STATE,
                }
            )
    eligible = [m for m in sorted(members) if members[m]["eligible"] is True]
    for split in SPLITS:
        band = loss_noise_band(results, split)
        margin = 0.0 if band is None else band
        key = "loss_" + split
        for x in eligible:
            lx, sx = members[x][key], results["rule_scores"][x].get(rule)
            if lx is None or not isinstance(sx, (int, float)):
                continue
            outranked = []
            for y in eligible:
                ly, sy = members[y][key], results["rule_scores"][y].get(rule)
                if y == x or ly is None or not isinstance(sy, (int, float)):
                    continue
                if ly + margin < lx and sx >= sy:
                    outranked.append(y)
            if outranked:
                out.append(
                    {
                        "schema": SCHEMA,
                        "condition": "SCORE_VALUE_DIVERGENCE",
                        "member": x,
                        "kind": members[x]["kind"],
                        "split": split,
                        "rule": rule,
                        "scored_at_or_above": outranked,
                        "loss": lx,
                        "loss_noise_band": band,
                        "basis": (
                            f"rule_scores.<member>.{rule} and "
                            f"summary.members.<member>.{key}; band from "
                            "seed_variation"
                        ),
                        "review_state": REVIEW_STATE,
                    }
                )
    return out


def verified_violation(*, member, kind, rank, eligible_members, detail):
    """A reference-verified false acceptance found by a search (the design
    optimizer's Mode X), as a condition record.

    SCORE_VALUE_DIVERGENCE when the member is in the top half of the eligible
    members under the deciding rule (2 × rank ≤ eligible), otherwise
    OTHER_SIGNAL: the model still made an unsafe call, but it did not score
    high. No threshold is chosen; the cut is the panel's own half.
    """
    top_half = rank is not None and 2 * rank <= eligible_members
    reserved = {"schema", "condition", "member", "kind", "rule", "rank", "basis"}
    if reserved & set(detail):
        raise ValueError("detail may not replace a condition field")
    return {
        "schema": SCHEMA,
        "condition": "SCORE_VALUE_DIVERGENCE" if top_half else "OTHER_SIGNAL",
        "member": member,
        "kind": kind,
        "rule": DECIDING_RULE,
        "rank": rank,
        "eligible_members": eligible_members,
        **detail,
        "basis": (
            "a reference-verified constraint FAIL (contract bands) at a point the "
            "member predicted to pass; rank from rule_scores.<member>."
            f"{DECIDING_RULE}"
        ),
        "review_state": REVIEW_STATE,
    }


def tau_noise_band(results, rule=DECIDING_RULE, split="verification"):
    """τ's spread over every one-seed-per-recipe panel of eligible real models.

    Returns `{"band", "tau_min", "tau_max", "panels"}`; band = max - min. It is
    the movement a study's τ shows from seed choice alone.
    """
    _check(results)
    members = results["summary"]["members"]
    groups = {}
    for m, row in sorted(members.items()):
        if row["kind"] == "RECONSTRUCTED" and row["eligible"] is True:
            groups.setdefault(_recipe(m), []).append(m)
    taus = []
    for panel in itertools.product(*groups.values()):
        scores = [results["rule_scores"][m].get(rule) for m in panel]
        losses = [members[m]["loss_" + split] for m in panel]
        if any(not isinstance(s, (int, float)) for s in scores) or None in losses:
            continue
        tau = kendall_tau_b(scores, [-loss for loss in losses])
        if tau is not None:
            taus.append(tau)
    if not taus:
        return {"band": None, "tau_min": None, "tau_max": None, "panels": 0}
    return {
        "band": max(taus) - min(taus),
        "tau_min": min(taus),
        "tau_max": max(taus),
        "panels": len(taus),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value.divergence")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    results = json.loads(args.results.read_text())
    report = {
        "schema": "carbon.admission-conditions.v1",
        "results": str(args.results),
        "deciding_rule": DECIDING_RULE,
        "loss_noise_band": {s: loss_noise_band(results, s) for s in SPLITS},
        "tau_noise_band": tau_noise_band(results),
        "conditions": conditions(results),
        "scope": "internal development evidence; not a qualification gate; not mainnet",
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        print(text, end="")
    return 1 if report["conditions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
