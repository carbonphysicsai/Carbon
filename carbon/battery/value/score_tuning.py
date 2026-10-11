"""The battery score-tuning loop (OWNER-GRAPHITE-TEST-WAVE-08).

Does a different weighting of battery's score legs rank models by the quality
of their engineering decisions better than the deciding rule, without
retraining anything? Steps:

1. **Panel.** Each member's stored predictions on a scoring set (for Graphite,
   the sealed tuning set `graphite-tuning-v1`, scored operator-side by the
   Validator's tooling). `member_legs` turns them into legs.
2. **Candidates.** Every weighting is registered BEFORE anything is
   computed: a committed registry file (`load_registry`), clean in git.
   `evaluate_all` refuses any candidate the registry does not hold, and
   records the registry's commit and digest.
3. **Evaluation.** Re-scoring the stored predictions (`candidate_scores`) is
   ranked against decision value on DEVELOPMENT decision data. The metrics
   are τ-b and ρ with a seed band, regret, the top choice's false-feasible
   rate, divergences, and whether it would pick a known-unsafe member.
4. **Diagnosis** (`diagnosis`). Which scenarios decisions are sensitive to,
   and where the score spends its weight (each leg's alignment with decision
   value). This seeds step 2.
5. **Stage 2** (`chain_mappings`). The score-to-chain-weight mapping:
   decision value of what each mapping would pay.

**Legs, per member** (higher is better, in (0, 1]):
- `a`, `r`, `g`: `ratios.legs` (accuracy, important-region accuracy,
  decision agreement);
- `m`: SR-2's margin leg on every case;
- `n`: the same margin leg on the near-limit cases only;
- `p`: SR-B1's proximity-weighted optimism leg.

Gate measures: `admissibility.near_optimism` on the near cases (`near`), and
on the near cases inside SR-B1's decision envelope (`envelope`). A gate
failure ranks LAST (the EV5 ruling): never `admissibility.gated`'s 0.0.

DEVELOPMENT evidence only: nothing here changes a rule, gate or reward.
Adopting any weighting stays with the science owner.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from carbon.design_search import score_value

from . import admissibility, margins, ratios
from . import decision as d
from . import false_acceptance as fa
from . import score_candidates_b1 as b1
from . import scoring as sc
from .near import near_cases

REGISTRY_SCHEMA = "carbon.battery.score-tuning-registry.v1"
RESULT_SCHEMA = "carbon.battery.score-tuning-result.v1"
LEGS = ("a", "r", "g", "m", "n", "p", "q")
GATES = ("near", "envelope", "feasibility", "plating_fa", "error")
#: How a gate compares its measure with its cutoff. "at_or_above" fails at
#: or above the cutoff (`admissibility.verdict`, pinned, and every candidate
#: registered before v5 without a `comparison`). "exceeds" fails only above
#: it: OWNER-BATTERY-SCORE-RULE-01's wording, "ineligible if [the rate]
#: exceeds 0.05", aligned prospectively in registry v5 (#961's boundary
#: finding: exactly 0.05 failed under the shared `>=`).
COMPARISONS = ("at_or_above", "exceeds")
#: A registered threshold sweep expands to one candidate per cutoff (`load_registry`).
SWEEP_KIND = "gate_sweep"
DECIDING = "control-exam-v1"
INFEASIBLE = "SELECTED_INFEASIBLE"


class TuningError(ValueError):
    def __init__(self, code, detail=None):
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True)
class Candidate:
    """One registered weighting. `kind` is "geometric" (weights over LEGS) or
    "deciding" (the deciding rule, −E, the baseline)."""

    id: str
    kind: str = "geometric"
    weights: dict = field(default_factory=dict)
    gate: dict | None = None
    stable: bool = False
    basis: str = ""


def parse_candidate(entry):
    """One registry entry as a `Candidate`, validated (public: the Validator's
    development score variants wrap the same entry, VALIDATOR-09)."""
    if set(entry) - {"id", "kind", "weights", "gate", "stable", "basis"}:
        raise TuningError("candidate_fields", entry.get("id"))
    kind = entry.get("kind", "geometric")
    weights = dict(entry.get("weights") or {})
    if kind not in ("geometric", "deciding"):
        raise TuningError("candidate_kind", entry.get("id"))
    if kind == "geometric":
        if not weights or set(weights) - set(LEGS):
            raise TuningError("candidate_legs", entry.get("id"))
        if any(not isinstance(w, (int, float)) or w < 0 for w in weights.values()):
            raise TuningError("candidate_weights", entry.get("id"))
        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
            raise TuningError("candidate_weights_sum", entry.get("id"))
    gate = entry.get("gate")
    if gate is not None and (
        set(gate) - {"comparison"} != {"measure", "cutoff"}
        or gate.get("comparison", COMPARISONS[0]) not in COMPARISONS
        or gate["measure"] not in GATES
        or not isinstance(gate["cutoff"], (int, float))
    ):
        raise TuningError("candidate_gate", entry.get("id"))
    return Candidate(
        entry["id"],
        kind,
        weights,
        gate,
        bool(entry.get("stable", False)),
        entry.get("basis", ""),
    )


def load_registry(path, *, repository=None):
    """The registered candidates, and the registry's identity.

    With `repository`, the file must be committed and unmodified in git:
    registration precedes computation, and the commit proves the order.
    """
    path = Path(path)
    body = path.read_bytes()
    document = json.loads(body)
    if document.get("schema") != REGISTRY_SCHEMA:
        raise TuningError("registry_schema")
    candidates, sweeps = [], {}
    for entry in document["candidates"]:
        if entry.get("kind") == SWEEP_KIND:
            expanded = expand_sweep(entry, {c.id: c for c in candidates})
            sweeps[entry["id"]] = [c.id for c in expanded]
            candidates += expanded
        else:
            candidates.append(parse_candidate(entry))
    ids = [c.id for c in candidates]
    if len(ids) != len(set(ids)):
        raise TuningError("registry_duplicate_id")
    identity = {
        "sha256": hashlib.sha256(body).hexdigest(),
        "commit": None,
        "sweeps": sweeps,
    }
    if repository is not None:
        root = Path(repository)
        # The producer reads a root-owned checkout (/opt/carbon) as its own
        # service account; git refuses that as "dubious ownership" unless the
        # checkout is named safe for this one call (2026-10-08, AX42 step 12).
        rel = str(path.resolve().relative_to(root.resolve()))
        dirty = subprocess.run(
            [
                "git",
                "-c",
                "safe.directory=" + str(root.resolve()),
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--",
                rel,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        commit = subprocess.run(
            [
                "git",
                "-c",
                "safe.directory=" + str(root.resolve()),
                "-C",
                str(root),
                "log",
                "-1",
                "--format=%H",
                "--",
                rel,
            ],
            capture_output=True,
            text=True,
            check=False,  # a repository with no commit yet: unregistered
        ).stdout.strip()
        if dirty or not commit:
            raise TuningError("registry_not_committed", rel)
        identity["commit"] = commit
    return {c.id: c for c in candidates}, identity


def expand_sweep(entry, registered):
    """A registered threshold sweep: one candidate per cutoff, each the base
    candidate's weighting gated at that cutoff. No cutoff is chosen here."""
    if set(entry) - {"id", "kind", "measure", "grid", "base", "basis", "comparison"}:
        raise TuningError("sweep_fields", entry.get("id"))
    if entry.get("comparison", COMPARISONS[0]) not in COMPARISONS:
        raise TuningError("sweep_comparison", entry.get("id"))
    # A sweep registered without `comparison` keeps its gate exactly as
    # before (two keys), so no earlier registry's candidates change.
    comparison = {"comparison": entry["comparison"]} if "comparison" in entry else {}
    if entry.get("measure") not in GATES:
        raise TuningError("sweep_measure", entry.get("id"))
    base = registered.get(entry.get("base"))
    if base is None:
        raise TuningError("sweep_base_unregistered", entry.get("id"))
    grid = entry.get("grid")
    if (
        not isinstance(grid, list)
        or not grid
        or any(not isinstance(x, (int, float)) or x <= 0 for x in grid)
        or grid != sorted(set(grid))
    ):
        raise TuningError("sweep_grid", entry.get("id"))
    return [
        Candidate(
            f"{entry['id']}@{cutoff:g}",
            base.kind,
            dict(base.weights),
            {"measure": entry["measure"], "cutoff": float(cutoff), **comparison},
            base.stable,
            f"sweep {entry['id']} of {base.id} at {cutoff:g}",
        )
        for cutoff in grid
    ]


# --- legs ------------------------------------------------------------------------------


def member_legs(contract, predictions, store, case_ids, decision_regret=None):
    """One member's legs and gate measures on `case_ids` of `store`.
    `decision_regret`: the member's mean Q3 decision regret over the quiz's
    feasible decision scenarios (registry v3's leg q), or None."""
    near = near_cases(store, case_ids)
    inside = b1.envelope_ids(store, case_ids)
    component = sc.components(predictions, case_ids, store, contract)
    a, r, g = ratios.legs(component)
    m = margins.margin_component(contract, predictions, case_ids, store.refs)
    n = margins.margin_component(contract, predictions, near, store.refs)
    return {
        "eligible": bool(component["eligible"]),
        "E": component["E"],
        "legs": {
            "a": a,
            "r": r,
            "g": g,
            "m": None if m is None else m["score"],
            "n": None if n is None else n["score"],
            "p": b1.proximity_leg(contract, predictions, case_ids, store.refs),
            "q": None if decision_regret is None else 1.0 / (1.0 + decision_regret),
        },
        "gates": {
            "near": admissibility.near_optimism(
                contract, predictions, case_ids, store.refs
            ),
            "envelope": admissibility.near_optimism(
                contract, predictions, inside, store.refs
            ),
            "feasibility": false_feasible_rate(
                contract, predictions, case_ids, store.refs
            ),
            "plating_fa": _plating_fa(contract, predictions, near, store.refs),
            # Accuracy as a gate (registry v4's design-primary family): the
            # exam error E, higher is worse; an ineligible member is
            # unmeasured, so a set gate fails it.
            "error": component["E"] if component["eligible"] else None,
        },
    }


def false_feasible_rate(contract, predictions, case_ids, refs):
    """G-FEAS's measure: of the cases the reference fails on any constraint
    (contract bands), the share the model calls feasible on every constraint
    (no band). Computed on the scoring set, never on decision scenarios, so
    the gate cannot grade the decisions it is evaluated against. None when a
    case is missing or no case fails."""
    bands = contract["reference"]["uncertainty"]["bands"]
    fails = accepted = 0
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        truth = d.check(contract, d.measure(contract, reference), bands)
        if any(v == d.FAIL for v in truth.values()):
            said = d.check(contract, d.measure(contract, outputs))
            fails += 1
            accepted += all(v == d.PASS for v in said.values())
    return None if fails == 0 else accepted / fails


def false_infeasible_rate(contract, predictions, case_ids, refs):
    """The mirror of `false_feasible_rate`: of the cases the reference passes
    on every constraint (contract bands), the share the model calls
    infeasible on any (no band). None when a case is missing or none passes."""
    bands = contract["reference"]["uncertainty"]["bands"]
    passes = rejected = 0
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        truth = d.check(contract, d.measure(contract, reference), bands)
        if all(v == d.PASS for v in truth.values()):
            said = d.check(contract, d.measure(contract, outputs))
            passes += 1
            rejected += any(v == d.FAIL for v in said.values())
    return None if passes == 0 else rejected / passes


def near_limit_cautious(outputs):
    """The near-limit-cautious constructed control (quiz-registry-v6): the
    mirror of `panel`'s boundary optimist. Accurate everywhere except just
    inside the limits, where it reports 0.012 V less plating margin and a
    3.5 degC hotter trajectory, so it rejects near-limit designs that are
    feasible. Kept here, not in `panel.CONTROLS`, so no frozen study's panel
    changes."""
    import copy

    out = copy.deepcopy(outputs)
    margin = out["plating_margin_v"]
    temperatures = out["temperature_c"]
    if -0.003 < margin < 0.012:
        out["plating_margin_v"] = margin - 0.012
    if 41.5 < max(temperatures) < 46.0:
        out["temperature_c"] = [temperatures[0]] + [t + 3.5 for t in temperatures[1:]]
    return out


def near_limit(contract, reference_outputs, margin):
    """Whether a reference lies within `margin` contract bands of the plating
    or peak-temperature limit, on either side (`margins._margins`). The
    quiz stratum's selector; `margin` stays HUMAN_INPUT and swept."""
    values = margins._margins(contract, reference_outputs)
    return min(abs(v) for v in values.values()) <= margin


def _plating_fa(contract, predictions, near, refs):
    """G-PLATE's measure: near-limit plating false acceptance
    (`false_acceptance.component`, the run-5 9.5 % measure)."""
    component = fa.component(contract, predictions, near, refs)
    if component is None:
        return None
    return component["constraints"]["no_plating_onset"]["false_acceptance_rate"]


# --- scoring ---------------------------------------------------------------------------


def score_member(candidate, row):
    """One member's raw score from its `member_legs` row, before the panel-level
    seed mean and gate (public: shared with the Validator's variants)."""
    if candidate.kind == "deciding":
        return -row["E"] if row["eligible"] and row["E"] is not None else None
    if not row["eligible"]:
        return 0.0
    return b1._geometric(
        tuple(row["legs"].get(leg) for leg in LEGS),
        tuple(candidate.weights.get(leg, 0.0) for leg in LEGS),
    )


def gate_verdict(candidate, row):
    """The candidate's gate verdict for one member (None without a gate)."""
    if candidate.gate is None:
        return None
    measured = row["gates"][candidate.gate["measure"]]
    cutoff = candidate.gate["cutoff"]
    if candidate.gate.get("comparison") == "exceeds":
        return exceeds_verdict(measured, cutoff)
    return admissibility.verdict(measured, threshold=cutoff)


def exceeds_verdict(measured, cutoff):
    """FAIL only when `measured` exceeds `cutoff` (strictly), or is unmeasured
    (never waved through); PASS at or below it."""
    if measured is None:
        return admissibility.FAIL
    return admissibility.FAIL if measured > cutoff else admissibility.PASS


def candidate_scores(candidate, legs, recipe_of):
    """Each member's score under `candidate`: raw, then the recipe's seed mean
    when `stable`, then the gate (failures strictly below every pass)."""
    scores = {m: score_member(candidate, row) for m, row in legs.items()}
    if candidate.stable:
        by_recipe = {}
        for m, s in scores.items():
            by_recipe.setdefault(recipe_of[m], []).append(s)
        means = {
            r: (None if any(s is None for s in v) else statistics.fmean(v))
            for r, v in by_recipe.items()
        }
        scores = {m: means[recipe_of[m]] for m in scores}
    if candidate.gate is None:
        return scores, {}
    verdicts = {m: gate_verdict(candidate, row) for m, row in legs.items()}
    finite = [s for s in scores.values() if s is not None]
    floor = (min(finite) if finite else 0.0) - 1.0
    gated = {
        m: (None if s is None else floor if verdicts[m] == admissibility.FAIL else s)
        for m, s in scores.items()
    }
    return gated, verdicts


# --- decision value --------------------------------------------------------------------


def decision_values(results, members, split="development"):
    """Each member's mean decision loss on the common resolved mask, the mask,
    and each member's outcome kind per masked scenario."""
    decisions = results["decisions"]
    scenarios = sorted(
        {s for m in members for s, v in decisions[m].items() if v["split"] == split}
    )
    mask = [
        s
        for s in scenarios
        if all(decisions[m][s]["outcome"]["decision_loss"] is not None for m in members)
    ]
    values = {
        m: (
            statistics.fmean(decisions[m][s]["outcome"]["decision_loss"] for s in mask)
            if mask
            else None
        )
        for m in members
    }
    outcomes = {
        m: {s: decisions[m][s]["outcome"]["kind"] for s in mask} for m in members
    }
    return values, mask, outcomes


def _top(scores, pool):
    ranked = sorted(
        (m for m in pool if scores.get(m) is not None), key=lambda m: (-scores[m], m)
    )
    return ranked


def evaluate(
    scores, values, outcomes, recipe_of, members, one_seed, unsafe=(), adversarial=()
):
    """One candidate's alignment with decision value. `adversarial` members
    (EV5's top-half infeasible constructions and Mode X violators) must leave
    the top half without the good deciders (the best quarter by decision
    value) leaving it with them."""
    usable = [m for m in members if scores.get(m) is not None and values[m] is not None]
    panels, count, mode = b1.seed_panels(recipe_of, members)
    taus = [b1._tau(scores, values, p) for p in panels]
    band = score_value.value_noise_band(
        {
            m: {"value": values[m], "eligible": True, "recipe": recipe_of[m]}
            for m in members
            if values[m] is not None
        }
    )
    margin = 0.0 if band is None else band
    divergent = sorted(
        x
        for x in usable
        if any(
            y != x and values[y] + margin < values[x] and scores[x] >= scores[y]
            for y in usable
        )
    )
    ranked = _top(scores, one_seed)
    top1 = ranked[0] if ranked else None
    best = min((values[m] for m in one_seed if values[m] is not None), default=None)
    kinds = outcomes.get(top1, {}) if top1 else {}
    all_ranked = _top(scores, members)
    n = len(all_ranked)

    def in_top_half(m):
        return m in all_ranked and 2 * (all_ranked.index(m) + 1) <= n

    valued = sorted(
        (m for m in members if values.get(m) is not None), key=lambda m: (values[m], m)
    )
    good = valued[: max(1, len(valued) // 4)] if valued else []
    return {
        "tau_one_seed": b1._tau(scores, values, one_seed),
        "tau_all": b1._tau(scores, values, members),
        "rho_all": score_value.spearman_rho(
            [scores[m] for m in usable], [-values[m] for m in usable]
        ),
        "tau_seed_band": b1._interval(taus),
        "seed_panels": {"panels": len(panels), "product": count, "mode": mode},
        "top1_one_seed": top1,
        "regret": (
            None
            if top1 is None or values[top1] is None or best is None
            else values[top1] - best
        ),
        "top1_false_feasible_rate": (
            None
            if not kinds
            else sum(1 for k in kinds.values() if k == INFEASIBLE) / len(kinds)
        ),
        "divergence_count": len(divergent),
        "value_noise_band": band,
        "picks_unsafe": top1 in set(unsafe),
        "adversarial_in_top_half": sorted(m for m in adversarial if in_top_half(m)),
        "good_deciders_top_half_share": (
            sum(1 for m in good if in_top_half(m)) / len(good) if good else None
        ),
        "unsafe_ranks": {
            u: (all_ranked.index(u) + 1 if u in all_ranked else None, len(all_ranked))
            for u in unsafe
        },
    }, taus


def evaluate_all(
    registry,
    legs,
    values,
    outcomes,
    recipe_of,
    members,
    one_seed,
    *,
    unsafe=(),
    adversarial=(),
    ids=None,
    baseline="CE",
):
    """Every requested registered candidate, with paired Δτ against `baseline`
    over the same seed panels. Refuses an unregistered id."""
    candidates, identity = registry
    ids = list(candidates) if ids is None else list(ids)
    missing = sorted(set(ids) - set(candidates))
    if missing:
        raise TuningError("candidate_not_registered", ",".join(missing))
    if baseline not in candidates:
        raise TuningError("baseline_not_registered", baseline)
    ids = list(dict.fromkeys([baseline, *ids]))
    out, taus = {}, {}
    for cid in ids:
        scores, verdicts = candidate_scores(candidates[cid], legs, recipe_of)
        out[cid], taus[cid] = evaluate(
            scores, values, outcomes, recipe_of, members, one_seed, unsafe, adversarial
        )
        out[cid]["gate_failures"] = sorted(
            m for m, v in verdicts.items() if v == admissibility.FAIL
        )
    for cid in ids:
        deltas = [
            None if a is None or b is None else a - b
            for a, b in zip(taus[cid], taus[baseline], strict=True)
        ]
        interval = b1._interval(deltas)
        out[cid]["delta_tau_vs_baseline"] = interval
        out[cid]["progress_vs_baseline"] = (
            cid != baseline and interval is not None and interval[0] > 0
        )
    curves = {
        sweep: [
            {
                "cutoff": candidates[cid].gate["cutoff"],
                "top1_false_feasible_rate": out[cid]["top1_false_feasible_rate"],
                "regret": out[cid]["regret"],
                "tau_all": out[cid]["tau_all"],
                "tau_seed_band": out[cid]["tau_seed_band"],
                "gate_failures": len(out[cid]["gate_failures"]),
                "adversarial_in_top_half": out[cid]["adversarial_in_top_half"],
            }
            for cid in members_of
            if cid in out
        ]
        for sweep, members_of in identity.get("sweeps", {}).items()
    }
    return {
        "schema": RESULT_SCHEMA,
        "registry": identity,
        "sweep_curves": curves,
        "threshold": "HUMAN_INPUT: the owner picks a cutoff from each curve",
        "baseline": baseline,
        "candidates": out,
        "claims": "DEVELOPMENT evidence; nothing adopted; no rule, gate or reward changed",
    }


# --- diagnosis -------------------------------------------------------------------------


def diagnosis(results, members, legs, values, mask, split="development"):
    """Where decisions are sensitive and where the score spends its weight."""
    decisions = results["decisions"]
    scenarios = sorted(
        {s for m in members for s, v in decisions[m].items() if v["split"] == split}
    )
    sensitivity = {}
    for s in scenarios:
        rows = [decisions[m][s]["outcome"] for m in members]
        losses = [r["decision_loss"] for r in rows if r["decision_loss"] is not None]
        sensitivity[s] = {
            "in_mask": s in mask,
            "distinct_selections": len({r.get("selected") for r in rows}),
            "infeasible_picks": sum(1 for r in rows if r["kind"] == INFEASIBLE),
            "unresolved": sum(1 for r in rows if r["decision_loss"] is None),
            "loss_spread": (max(losses) - min(losses)) if losses else None,
        }
    usable = [m for m in members if values[m] is not None]
    attribution = {}
    for leg in LEGS:
        pairs = [
            (legs[m]["legs"].get(leg), -values[m])
            for m in usable
            if legs[m]["legs"].get(leg) is not None
        ]
        attribution[leg] = {
            "rho_with_decision_value": (
                score_value.spearman_rho(*zip(*pairs, strict=True))
                if len(pairs) > 2
                else None
            ),
            "unmeasured": len(usable) - len(pairs),
        }
    return {
        "scenarios": sensitivity,
        "mask": {"resolved": len(mask), "of": len(scenarios)},
        "leg_alignment": attribution,
        "most_sensitive": sorted(
            (s for s in scenarios if sensitivity[s]["loss_spread"] is not None),
            key=lambda s: (-sensitivity[s]["loss_spread"], s),
        )[:3],
    }


# --- stage 2: score to chain weight ----------------------------------------------------


def chain_mappings(scores, values, pool, *, k=3, unsafe=()):
    """What each score-to-weight mapping pays: the weight-averaged decision
    loss of the members it pays, against the best possible at the same k,
    and the weight on known-unsafe members."""
    ranked = [m for m in _top(scores, pool) if values.get(m) is not None]
    top = ranked[:k]
    best = sorted(values[m] for m in pool if values.get(m) is not None)[:k]
    mappings = {
        "winner_take_all": {top[0]: 1.0} if top else {},
        "top_k_equal": {m: 1.0 / len(top) for m in top} if top else {},
        "top_k_rank": (
            {m: (len(top) - i) / sum(range(1, len(top) + 1)) for i, m in enumerate(top)}
            if top
            else {}
        ),
    }
    unsafe = set(unsafe)
    return {
        name: {
            "weights": weights,
            "weighted_loss": (
                sum(w * values[m] for m, w in weights.items()) if weights else None
            ),
            "best_possible_loss": (
                statistics.fmean(best[: len(weights) or 1]) if best else None
            ),
            "weight_on_unsafe": sum(w for m, w in weights.items() if m in unsafe),
        }
        for name, weights in mappings.items()
    }
