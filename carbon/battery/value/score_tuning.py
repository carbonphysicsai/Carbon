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
from . import score_candidates_b1 as b1
from . import scoring as sc
from .near import near_cases

REGISTRY_SCHEMA = "carbon.battery.score-tuning-registry.v1"
RESULT_SCHEMA = "carbon.battery.score-tuning-result.v1"
LEGS = ("a", "r", "g", "m", "n", "p")
GATES = ("near", "envelope")
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
        set(gate) != {"measure", "cutoff"}
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
    candidates = [parse_candidate(e) for e in document["candidates"]]
    ids = [c.id for c in candidates]
    if len(ids) != len(set(ids)):
        raise TuningError("registry_duplicate_id")
    identity = {"sha256": hashlib.sha256(body).hexdigest(), "commit": None}
    if repository is not None:
        root = Path(repository)
        rel = str(path.resolve().relative_to(root.resolve()))
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", rel],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%H", "--", rel],
            capture_output=True,
            text=True,
            check=False,  # a repository with no commit yet: unregistered
        ).stdout.strip()
        if dirty or not commit:
            raise TuningError("registry_not_committed", rel)
        identity["commit"] = commit
    return {c.id: c for c in candidates}, identity


# --- legs ------------------------------------------------------------------------------


def member_legs(contract, predictions, store, case_ids):
    """One member's legs and gate measures on `case_ids` of `store`."""
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
        },
        "gates": {
            "near": admissibility.near_optimism(
                contract, predictions, case_ids, store.refs
            ),
            "envelope": admissibility.near_optimism(
                contract, predictions, inside, store.refs
            ),
        },
    }


# --- scoring ---------------------------------------------------------------------------


def score_member(candidate, row):
    """One member's raw score from its `member_legs` row, before the panel-level
    seed mean and gate (public: shared with the Validator's variants)."""
    if candidate.kind == "deciding":
        return -row["E"] if row["eligible"] and row["E"] is not None else None
    if not row["eligible"]:
        return 0.0
    return b1._geometric(
        tuple(row["legs"][leg] for leg in LEGS),
        tuple(candidate.weights.get(leg, 0.0) for leg in LEGS),
    )


def gate_verdict(candidate, row):
    """The candidate's gate verdict for one member (None without a gate)."""
    if candidate.gate is None:
        return None
    return admissibility.verdict(
        row["gates"][candidate.gate["measure"]], threshold=candidate.gate["cutoff"]
    )


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


def evaluate(scores, values, outcomes, recipe_of, members, one_seed, unsafe=()):
    """One candidate's alignment with decision value."""
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
            scores, values, outcomes, recipe_of, members, one_seed, unsafe
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
    return {
        "schema": RESULT_SCHEMA,
        "registry": identity,
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
            (legs[m]["legs"][leg], -values[m])
            for m in usable
            if legs[m]["legs"][leg] is not None
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
