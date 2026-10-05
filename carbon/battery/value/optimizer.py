"""Problem C: one two-step fast-charge protocol that is safe across 15-35 °C.

Use case (lead amendment 2026-10-01, before any EV4 solve, from EV2's public
references only): one protocol safe across 15-35 °C ambient, the realistic
indoor product range, at soc0 0.05-0.50. EV2 found no feasible protocol at
7 °C or at 40 °C (soc0 0.18), so a 5-40 °C requirement would make accurate
models abstain.

The design optimizer of `DESIGN_OPTIMIZER_SCOPE.md`, run on EV4's panel with
the EV4 contract's objective, constraints, uncertainty bands and baseline.
Owner decision 2026-10-01 delegated its engineering choices; every grid,
budget and rule below is fixed in `BATTERY_ENGINEERING_VALUE_EV4.md` before any
verification solve.

- **Design grid.** c1 0.50-2.00 C in steps of 0.05 (31) × c2 0.200-1.000 C in
  steps of 0.025 (33): 1023 designs.
- **Model condition grid** (the pod predicts all of it): t_amb {5, 10, …, 40}
  °C × soc0 {0.05, 0.20, 0.35, 0.50}: 32 conditions. The 20 with
  15 ≤ t_amb ≤ 35 are in band; {5, 10, 40} °C are out of band.
- **Mode D (robust design, PB-INV).** Per member, from its predictions only:
  the design predicted feasible (all three constraints, point predictions, no
  band) at all 20 in-band conditions with the lowest worst-case predicted time
  to CV onset; ties by lower c1, then c2 (the contract's tie rule); otherwise
  ABSTAIN.
- **Verification grid** (reference truth): t_amb = linspace(5, 40, 18) ×
  soc0 = linspace(0.05, 0.50, 5): 90 conditions. Every committed design and
  the contract baseline are solved at all 90. PRIMARY: the in-band points
  (15 ≤ t_amb ≤ 35). SECONDARY: the out-of-band points, reported
  descriptively, never counted against the in-band claim.
- **Mode X (adversarial, PB-ADV).** Per member, over all 1023 designs × the
  32 model conditions: the points it predicts feasible, ranked by the
  smallest constraint margin normalised by the contract's uncertainty bands;
  the top K = 50 distinct points are verified. A verified violation is a
  finding (`divergence.verified_violation`), labelled in band or out of band
  and counted separately.
- **Members** (pre-registered, applied after EV4's evaluation and before any
  verification solve): the best eligible member under the deciding rule; the
  best under the proposed rule; the median under the deciding rule; the best
  kNN; the lowest EV4 verification decision loss. Each role takes the next
  member in its own order when its first choice is already selected.
- **Budget.** At most 6 designs × 90 = 540 Mode D solves and 5 × 50 = 250
  Mode X solves; with EV4's 840, at most 1630. Job builders refuse to exceed
  these maxima.

Everything is a pure function of its inputs except the CLI wrappers. Public
synthetic DEVELOPMENT evidence: no qualification, reward or chain action.
"""

from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import contract as ev
from . import decision as d
from . import divergence as dv

GRID_SCHEMA = "carbon.ev4-optimizer-grid.v1"
SELECTION_SCHEMA = "carbon.ev4-optimizer-selection.v1"
RESULT_SCHEMA = "carbon.ev4-optimizer-results.v1"

C1 = tuple(round(0.50 + 0.05 * i, 2) for i in range(31))
C2 = tuple(round(0.200 + 0.025 * j, 3) for j in range(33))
#: c1-major, so the tie rule (lower c1, then c2) is the grid order.
DESIGNS = tuple((c1, c2) for c1 in C1 for c2 in C2)
MODEL_CONDITIONS = tuple(
    (float(t), float(s))
    for t in (5, 10, 15, 20, 25, 30, 35, 40)
    for s in (0.05, 0.20, 0.35, 0.50)
)
#: The in-band ambient range of the use case, inclusive (°C).
BAND = (15.0, 35.0)


def in_band(t_amb):
    return BAND[0] <= t_amb <= BAND[1]


#: Mode D's conditions: the in-band model conditions (20), as grid indices.
MODE_D_CONDITIONS = tuple(
    ci for ci, (t_amb, _soc0) in enumerate(MODEL_CONDITIONS) if in_band(t_amb)
)
VERIFY_CONDITIONS = tuple(
    (float(t), float(s))
    for t in np.linspace(5.0, 40.0, 18)
    for s in np.linspace(0.05, 0.50, 5)
)
K = 50
MEMBER_ROLES = (
    "best_deciding",
    "best_proposed",
    "median_deciding",
    "best_knn",
    "lowest_verification_loss",
)
MAX_DESIGNS = len(MEMBER_ROLES) + 1  # the members' designs and the baseline
MAX_MODE_D_SOLVES = MAX_DESIGNS * len(VERIFY_CONDITIONS)  # 540
MAX_MODE_X_SOLVES = len(MEMBER_ROLES) * K  # 250
EV4_SOLVES = 840
MAX_TOTAL_SOLVES = EV4_SOLVES + MAX_MODE_D_SOLVES + MAX_MODE_X_SOLVES  # 1630
QUANTITIES = ("time_to_cv_onset_s", "plating_margin_v", "peak_temperature_c")
DECIDING_RULE = dv.DECIDING_RULE
PROPOSED_RULE = "dar-p0-r100-a0"


@dataclass(frozen=True)
class Spec:
    """One study's optimizer: its grids, its proposed rule and the roles the
    admissibility gate applies to. Designs, K, the band, Mode D and Mode X are
    shared; the maxima follow from the grids and the roles."""

    study: str
    model_conditions: tuple
    verify_conditions: tuple
    proposed_rule: str
    prior_solves: int
    #: Roles whose pool is only the members the gate passes (`select_members`).
    gated_roles: tuple = ()
    #: EV4 tolerates an unscored proposed rule (the role is then empty); a
    #: later study refuses it.
    proposed_required: bool = False

    @property
    def mode_d_conditions(self):
        return tuple(
            ci for ci, (t, _s) in enumerate(self.model_conditions) if in_band(t)
        )

    @property
    def max_designs(self):
        return len(MEMBER_ROLES) + 1

    @property
    def max_mode_d_solves(self):
        return self.max_designs * len(self.verify_conditions)

    @property
    def max_mode_x_solves(self):
        return len(MEMBER_ROLES) * K

    @property
    def max_total_solves(self):
        return self.prior_solves + self.max_mode_d_solves + self.max_mode_x_solves

    @property
    def in_band_verify(self):
        return tuple(c for c in self.verify_conditions if in_band(c[0]))

    @property
    def out_of_band_verify(self):
        return tuple(c for c in self.verify_conditions if not in_band(c[0]))

    def maxima(self):
        return {
            "mode_d_solves": self.max_mode_d_solves,
            "mode_x_solves": self.max_mode_x_solves,
            "designs": self.max_designs,
            "k": K,
            "total_solves": self.max_total_solves,
        }


EV4_SPEC = Spec(
    study="ev4",
    model_conditions=MODEL_CONDITIONS,
    verify_conditions=VERIFY_CONDITIONS,
    proposed_rule=PROPOSED_RULE,
    prior_solves=EV4_SOLVES,
)


def spec_for(contract):
    """The optimizer spec of the study a contract belongs to: EV5's for EV5's
    contract (`ev5.optimizer_spec`), EV4's otherwise."""
    if contract.get("contract_id") == "ev5-battery-charge-protocol-selection":
        from . import ev5

        return ev5.optimizer_spec()
    return EV4_SPEC


class OptimizerError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def design_id(c1, c2):
    return ev.candidate_id({"c1": c1, "c2": c2})


def case_id(c1, c2, t_amb, soc0, spec=EV4_SPEC):
    """A verification case id: the study, the design and the condition."""
    return f"{spec.study}opt:{design_id(c1, c2)}:t={t_amb!r},soc0={soc0!r}"


def _job(c1, c2, t_amb, soc0, spec=EV4_SPEC):
    return {
        "case_id": case_id(c1, c2, t_amb, soc0, spec),
        "c1": float(c1),
        "c2": float(c2),
        "t_amb_c": float(t_amb),
        "soc0": float(soc0),
    }


# --- the model's grid predictions (made on the pod) ------------------------------------------


def grid_inputs(spec=EV4_SPEC):
    """Model inputs for every (design, model condition), by index ids."""
    return {
        f"g{di:04d}c{ci:02d}": {
            "c1": c1,
            "c2": c2,
            "t_amb_c": t_amb,
            "soc0": soc0,
        }
        for di, (c1, c2) in enumerate(DESIGNS)
        for ci, (t_amb, soc0) in enumerate(spec.model_conditions)
    }


def grid_predictions(contract, infer, *, chunk=4096):
    """Decision quantities for every grid point, from `infer(inputs) ->
    {case id: outputs}` (a member's prediction function). Only quantities
    are kept: [design][condition] lists, None where CV is not reached. The
    model grid is the contract's study's (`spec_for`)."""
    inputs = grid_inputs(spec_for(contract))
    ids = sorted(inputs)
    width = len(spec_for(contract).model_conditions)
    out = {q: [[None] * width for _ in DESIGNS] for q in QUANTITIES}
    for start in range(0, len(ids), chunk):
        part = ids[start : start + chunk]
        predictions = infer({i: inputs[i] for i in part})
        for i in part:
            q = d.measure(contract, predictions[i])
            di, ci = int(i[1:5]), int(i[6:8])
            for name in QUANTITIES:
                out[name][di][ci] = q[name]
    return out


def grid_document(contract, member, recipe_digest, seed, quantities, extra=None):
    return {
        "schema": GRID_SCHEMA,
        "member": member,
        "recipe_digest": recipe_digest,
        "seed": seed,
        "contract_digest": ev.digest(contract),
        "designs": "optimizer.DESIGNS (c1-major)",
        "conditions": [list(c) for c in spec_for(contract).model_conditions],
        "quantities": quantities,
        **(extra or {}),
    }


def load_grid(path, spec=EV4_SPEC):
    document = json.loads(gzip.decompress(Path(path).read_bytes()))
    if document.get("schema") != GRID_SCHEMA:
        raise OptimizerError("grid_schema", str(path))
    if document.get("conditions") != [list(c) for c in spec.model_conditions]:
        raise OptimizerError("grid_conditions", str(path))
    for name in QUANTITIES:
        rows = document["quantities"][name]
        if len(rows) != len(DESIGNS) or any(
            len(r) != len(spec.model_conditions) for r in rows
        ):
            raise OptimizerError("grid_shape", str(path))
    return document


def _point(grid, di, ci):
    return {name: grid["quantities"][name][di][ci] for name in QUANTITIES}


def _predicted_pass(contract, quantities):
    if quantities["time_to_cv_onset_s"] is None:
        return False
    return all(v == d.PASS for v in d.check(contract, quantities).values())


# --- Mode D: the robust design -----------------------------------------------------------------


def mode_d(contract, grid):
    """The design predicted feasible at all 20 in-band conditions with the
    lowest worst-case predicted time to CV there; ties by lower c1 then c2;
    else ABSTAIN. Out-of-band predictions play no part."""
    spec = spec_for(contract)
    best = None
    feasible = 0
    for di, (c1, c2) in enumerate(DESIGNS):
        worst = -math.inf
        for ci in spec.mode_d_conditions:
            q = _point(grid, di, ci)
            if not _predicted_pass(contract, q):
                break
            worst = max(worst, q["time_to_cv_onset_s"])
        else:
            feasible += 1
            key = (worst, c1, c2)
            if best is None or key < best:
                best = key
    if best is None:
        return {"status": "ABSTAIN", "feasible_designs": 0}
    worst, c1, c2 = best
    return {
        "status": "DESIGN",
        "design": design_id(c1, c2),
        "c1": c1,
        "c2": c2,
        "predicted_worst_time_to_cv_s": worst,
        "feasible_designs": feasible,
    }


# --- Mode X: the adversarial search ------------------------------------------------------------


def margins(contract, quantities):
    """Each constraint's predicted margin in units of its uncertainty band
    (positive = on the passing side)."""
    bands = contract["reference"]["uncertainty"]["bands"]
    rules = {c["id"]: c for c in contract["constraints"]}
    window = contract["objective"]["window_s"] - contract["objective"]["charge_start_s"]
    return {
        "reach_cv_in_window": (window - quantities["time_to_cv_onset_s"])
        / bands["time_to_cv_onset_s"],
        "no_plating_onset": (
            quantities["plating_margin_v"] - rules["no_plating_onset"]["threshold"]
        )
        / bands["plating_margin_v"],
        "peak_temperature": (
            rules["peak_temperature"]["threshold"] - quantities["peak_temperature_c"]
        )
        / bands["peak_temperature_c"],
    }


def mode_x(contract, grid, k=K):
    """The top `k` predicted-feasible (design, model condition) points with the
    smallest band-normalised constraint margin; ties by c1, c2, t_amb, soc0."""
    if k > K:
        raise OptimizerError("budget_exceeded", f"K {k} > {K}")
    spec = spec_for(contract)
    points = []
    for di, (c1, c2) in enumerate(DESIGNS):
        for ci, (t_amb, soc0) in enumerate(spec.model_conditions):
            q = _point(grid, di, ci)
            if not _predicted_pass(contract, q):
                continue
            m = margins(contract, q)
            binding = min(m, key=lambda name: (m[name], name))
            points.append((m[binding], c1, c2, t_amb, soc0, binding, q))
    points.sort(key=lambda p: p[:5])
    return [
        {
            "design": design_id(c1, c2),
            "c1": c1,
            "c2": c2,
            "t_amb_c": t_amb,
            "soc0": soc0,
            "case_id": case_id(c1, c2, t_amb, soc0, spec),
            "in_band": in_band(t_amb),
            "predicted_margin_bands": margin,
            "binding_constraint": binding,
            "predicted": q,
        }
        for margin, c1, c2, t_amb, soc0, binding, q in points[:k]
    ]


# --- member selection (after EV4's evaluation, before any verification solve) --------------------


def _score(results, member, rule):
    value = results["rule_scores"][member].get(rule)
    return value if isinstance(value, (int, float)) else None


def select_members(results, backbones, spec=EV4_SPEC, *, scores=None, admissible=None):
    """The pre-registered five members, from a study's result.

    `backbones` maps member → architecture family. Ties within a criterion go
    to the lower member id. A role whose first choice is already selected
    takes the next member in its own order.

    `scores` adds rule → {member: score} for a rule the contract does not
    declare (EV5's SR-2 candidate). `admissible` is the set of members the
    admissibility gate passes; a role in `spec.gated_roles` draws only from
    it, and a spec with gated roles refuses to select without it.
    """
    members = results["summary"]["members"]
    eligible = sorted(
        m
        for m, row in members.items()
        if row["kind"] == "RECONSTRUCTED" and row["eligible"] is True
    )
    if spec.gated_roles and admissible is None:
        raise OptimizerError("gate_missing", ",".join(spec.gated_roles))
    extra = scores or {}

    def score(member, rule):
        if rule in extra:
            value = extra[rule].get(member)
            return value if isinstance(value, (int, float)) else None
        return _score(results, member, rule)

    def by_score(rule, pool):
        scored = [m for m in pool if score(m, rule) is not None]
        return sorted(scored, key=lambda m: (-score(m, rule), m))

    if spec.proposed_required and not by_score(spec.proposed_rule, eligible):
        raise OptimizerError("proposed_unscored", spec.proposed_rule)

    def pool(role):
        if role in spec.gated_roles:
            return [m for m in eligible if m in admissible]
        return eligible

    deciding = by_score(DECIDING_RULE, pool("best_deciding"))
    median = deciding[(len(deciding) - 1) // 2 :] + deciding[: (len(deciding) - 1) // 2]
    loss = sorted(
        (m for m in eligible if members[m]["loss_verification"] is not None),
        key=lambda m: (members[m]["loss_verification"], m),
    )
    orders = {
        "best_deciding": deciding,
        "best_proposed": by_score(spec.proposed_rule, pool("best_proposed")),
        "median_deciding": median,
        "best_knn": by_score(
            DECIDING_RULE, [m for m in eligible if backbones.get(m) == "knn"]
        ),
        "lowest_verification_loss": loss,
    }
    chosen, out = set(), []
    for role in MEMBER_ROLES:
        pick = next((m for m in orders[role] if m not in chosen), None)
        if pick is not None:
            chosen.add(pick)
        out.append({"role": role, "member": pick})
    return out


# --- verification jobs ---------------------------------------------------------------------------


def verification_plan(contract, mode_d_results, mode_x_results):
    """The reference jobs for Mode D (committed designs and the baseline at the
    90 verification conditions) and Mode X (each member's top K). Refuses to
    exceed the pre-registered maxima."""
    spec = spec_for(contract)
    base = contract["baseline"]["protocol"]
    designs = [(float(base["c1"]), float(base["c2"]))]
    for row in mode_d_results.values():
        if row["status"] == "DESIGN" and (row["c1"], row["c2"]) not in designs:
            designs.append((row["c1"], row["c2"]))
    if len(designs) > spec.max_designs:
        raise OptimizerError("budget_exceeded", f"{len(designs)} designs")
    mode_d_jobs = [
        _job(c1, c2, t_amb, soc0, spec)
        for c1, c2 in designs
        for t_amb, soc0 in spec.verify_conditions
    ]
    if len(mode_d_jobs) > spec.max_mode_d_solves:
        raise OptimizerError("budget_exceeded", f"Mode D {len(mode_d_jobs)}")
    if len(mode_x_results) > len(MEMBER_ROLES) or any(
        len(points) > K for points in mode_x_results.values()
    ):
        raise OptimizerError("budget_exceeded", "Mode X points")
    mode_x_jobs = [
        _job(p["c1"], p["c2"], p["t_amb_c"], p["soc0"], spec)
        for member in sorted(mode_x_results)
        for p in mode_x_results[member]
    ]
    if len(mode_x_jobs) > spec.max_mode_x_solves:
        raise OptimizerError("budget_exceeded", f"Mode X {len(mode_x_jobs)}")
    jobs, seen = [], set()
    for job in mode_d_jobs + mode_x_jobs:
        if job["case_id"] not in seen:
            seen.add(job["case_id"])
            jobs.append(job)
    if spec.prior_solves + len(jobs) > spec.max_total_solves:
        raise OptimizerError(
            "budget_exceeded", f"total {spec.prior_solves + len(jobs)}"
        )
    return {
        "designs": [design_id(c1, c2) for c1, c2 in designs],
        "mode_d_solves": len(mode_d_jobs),
        "mode_x_solves": len(mode_x_jobs),
        "jobs": sorted(jobs, key=lambda j: j["case_id"]),
    }


def select(contract, results, backbones, grids, *, scores=None, admissible=None):
    """Members, Mode D designs, Mode X points and the verification jobs.
    `grids` maps member → loaded grid document; `scores` and `admissible` as
    in `select_members`."""
    spec = spec_for(contract)
    selection = select_members(
        results, backbones, spec, scores=scores, admissible=admissible
    )
    mode_d_results, mode_x_results = {}, {}
    for row in selection:
        member = row["member"]
        if member is None or member in mode_d_results:
            continue
        grid = grids.get(member)
        if grid is None:
            raise OptimizerError("grid_missing", member)
        if (
            grid["member"] != member
            or grid["contract_digest"] != ev.digest(contract)
            or grid.get("conditions") != [list(c) for c in spec.model_conditions]
        ):
            raise OptimizerError("grid_mismatch", member)
        mode_d_results[member] = mode_d(contract, grid)
        mode_x_results[member] = mode_x(contract, grid)
    plan = verification_plan(contract, mode_d_results, mode_x_results)
    return {
        "schema": SELECTION_SCHEMA,
        "contract_digest": ev.digest(contract),
        "results_digest": ev.digest(results["summary"]),
        "members": selection,
        "mode_d": mode_d_results,
        "mode_x": mode_x_results,
        **plan,
    }


# --- verified outcomes ---------------------------------------------------------------------------


def _verify(contract, record):
    """Reference verdict per constraint for one point, with the bands."""
    if record is None or record.get("status") != "OK":
        return d.UNAVAILABLE, None, None
    quantities = d.measure(contract, record["outputs"])
    checks = d.check(
        contract, quantities, contract["reference"]["uncertainty"]["bands"]
    )
    values = set(checks.values())
    verdict = (
        d.INFEASIBLE
        if d.FAIL in values
        else d.UNRESOLVED if d.UNRESOLVED in values else d.FEASIBLE
    )
    return verdict, checks, quantities


def _summary(contract, c1, c2, references, conditions):
    """Verification of one design on a set of conditions."""
    counts = {s: 0 for s in (d.FEASIBLE, d.INFEASIBLE, d.UNRESOLVED, d.UNAVAILABLE)}
    violations = {c["id"]: 0 for c in contract["constraints"]}
    times, unreached = [], 0
    for t_amb, soc0 in conditions:
        verdict, checks, q = _verify(
            contract, references.get(case_id(c1, c2, t_amb, soc0, spec_for(contract)))
        )
        counts[verdict] += 1
        if checks is None:
            continue
        for name, value in checks.items():
            violations[name] += value == d.FAIL
        if q["time_to_cv_onset_s"] is None:
            unreached += 1
        else:
            times.append(q["time_to_cv_onset_s"])
    complete = counts[d.UNAVAILABLE] == 0
    timed = not (unreached or not complete or not times)
    return {
        "points": len(conditions),
        "verdicts": counts,
        "feasible_at_every_point": complete and counts[d.FEASIBLE] == len(conditions),
        "violating_points_by_constraint": violations,
        "worst_time_to_cv_s": max(times) if timed else None,
        "mean_time_to_cv_s": sum(times) / len(times) if timed else None,
        "points_not_reaching_cv": unreached,
    }


IN_BAND_VERIFY = tuple(c for c in VERIFY_CONDITIONS if in_band(c[0]))
OUT_OF_BAND_VERIFY = tuple(c for c in VERIFY_CONDITIONS if not in_band(c[0]))


def design_outcome(contract, c1, c2, references):
    """One design verified at the 90 verification conditions. PRIMARY is the
    in-band claim (15 ≤ t_amb ≤ 35); SECONDARY describes where the design
    breaks outside the band and never counts against the in-band claim."""
    return {
        "design": design_id(c1, c2),
        "c1": c1,
        "c2": c2,
        "primary_in_band": _summary(
            contract, c1, c2, references, spec_for(contract).in_band_verify
        ),
        "secondary_out_of_band": _summary(
            contract, c1, c2, references, spec_for(contract).out_of_band_verify
        ),
    }


def _speed_up(design, baseline):
    """Seconds saved and ratio against the baseline, on the same points."""
    out = {}
    for key in ("worst_time_to_cv_s", "mean_time_to_cv_s"):
        a, b = design[key], baseline[key]
        out[key.replace("_time_to_cv_s", "_seconds_saved")] = (
            None if a is None or b is None else b - a
        )
        out[key.replace("_time_to_cv_s", "_ratio")] = (
            None if a is None or b is None or a == 0 else b / a
        )
    return out


def report(contract, results, selection, references):
    """The result table and the findings, from the frozen selection and the
    verification references. Deterministic."""
    if selection.get("schema") != SELECTION_SCHEMA:
        raise OptimizerError("selection_schema")
    if selection["contract_digest"] != ev.digest(contract):
        raise OptimizerError("contract_mismatch")
    if selection["results_digest"] != ev.digest(results["summary"]):
        raise OptimizerError("results_mismatch")
    base = contract["baseline"]["protocol"]
    baseline = design_outcome(
        contract, float(base["c1"]), float(base["c2"]), references
    )
    designs = []
    for row in selection["members"]:
        member = row["member"]
        decided = selection["mode_d"].get(member) if member else None
        entry = {"role": row["role"], "member": member}
        if decided is None or decided["status"] != "DESIGN":
            entry["mode_d"] = "ABSTAIN" if decided else None
        else:
            outcome = design_outcome(contract, decided["c1"], decided["c2"], references)
            entry["mode_d"] = {
                **outcome,
                "predicted_worst_time_to_cv_s": decided["predicted_worst_time_to_cv_s"],
                "in_band_versus_baseline": _speed_up(
                    outcome["primary_in_band"], baseline["primary_in_band"]
                ),
            }
        designs.append(entry)
    eligible = sorted(
        m
        for m, r in results["summary"]["members"].items()
        if r["kind"] == "RECONSTRUCTED" and r["eligible"] is True
    )
    scores = [
        _score(results, m, DECIDING_RULE)
        for m in eligible
        if _score(results, m, DECIDING_RULE) is not None
    ]
    adversarial, findings = {}, []
    for member in sorted(selection["mode_x"]):
        rows = []
        mine = _score(results, member, DECIDING_RULE)
        rank = None if mine is None else 1 + sum(1 for s in scores if s > mine)
        for point in selection["mode_x"][member]:
            verdict, checks, q = _verify(contract, references.get(point["case_id"]))
            rows.append({**point, "verdict": verdict, "reference_checks": checks})
            if verdict == d.INFEASIBLE:
                findings.append(
                    dv.verified_violation(
                        member=member,
                        kind="RECONSTRUCTED",
                        rank=rank,
                        eligible_members=len(scores),
                        detail={
                            "mode": "X",
                            "in_band": point["in_band"],
                            "design": point["design"],
                            "operating_condition": {
                                "t_amb_c": point["t_amb_c"],
                                "soc0": point["soc0"],
                            },
                            "violated": sorted(
                                k for k, v in checks.items() if v == d.FAIL
                            ),
                            "predicted": point["predicted"],
                            "reference": q,
                            "predicted_margin_bands": point["predicted_margin_bands"],
                        },
                    )
                )
        counts = {"in_band": {}, "out_of_band": {}}
        for r in rows:
            side = counts["in_band" if r["in_band"] else "out_of_band"]
            side[r["verdict"]] = side.get(r["verdict"], 0) + 1
        adversarial[member] = {
            "rank_under_deciding_rule": rank,
            "eligible_members": len(scores),
            "points": rows,
            "verdicts": counts,
        }
    return {
        "schema": RESULT_SCHEMA,
        "contract_digest": selection["contract_digest"],
        "use_case": (
            "one two-step fast-charge protocol safe across 15-35 °C ambient "
            "(the realistic indoor product range), soc0 0.05-0.50"
        ),
        "band_t_amb_c": list(BAND),
        "baseline": baseline,
        "designs": designs,
        "adversarial": adversarial,
        "findings": {
            "in_band": [f for f in findings if f["in_band"]],
            "out_of_band": [f for f in findings if not f["in_band"]],
        },
        "claims": {
            "best_design_is_global_optimum": False,
            "search_finding_nothing_proves_safety": False,
            "out_of_band_counts_against_in_band_claim": False,
            "qualification": False,
            "evidence_class": "PUBLIC_SYNTHETIC_DEVELOPMENT",
        },
    }


def render(result):
    """A readable table of the optimizer result."""

    def f(value, digits=1):
        return "—" if value is None else f"{value:.{digits}f}"

    def cells(s):
        v = s["violating_points_by_constraint"]
        return (
            f"{s['feasible_at_every_point']} "
            f"| {v['reach_cv_in_window']} / {v['no_plating_onset']} / "
            f"{v['peak_temperature']} "
            f"| {f(s['worst_time_to_cv_s'])} | {f(s['mean_time_to_cv_s'])}"
        )

    lines = [
        "# Problem C: one fast-charge protocol for 15-35 °C",
        "",
        (
            "Public synthetic DEVELOPMENT evidence. Each model chose one two-step "
            "protocol from its own predictions at the 20 in-band conditions; the "
            "reference verified it at 90 conditions over 5-40 °C. The claim is the "
            "in-band result (15-35 °C); out-of-band points describe where the "
            "design breaks and never count against it. Not a global optimum, not "
            "a qualification."
        ),
        "",
        "## Primary: in band (15-35 °C)",
        "",
        "| Role | Member | Design | Feasible at every in-band point | Violations (reach / plating / temp) | Worst t_CV (s) | Mean t_CV (s) | Worst saved vs baseline (s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    b = result["baseline"]
    lines.append(
        f"| baseline | — | {b['design']} | {cells(b['primary_in_band'])} | — |"
    )
    for row in result["designs"]:
        m = row["mode_d"]
        if not isinstance(m, dict):
            lines.append(
                f"| {row['role']} | {row['member'] or '—'} | {m or '—'} | — | — | — | — | — |"
            )
            continue
        lines.append(
            f"| {row['role']} | {row['member']} | {m['design']} "
            f"| {cells(m['primary_in_band'])} "
            f"| {f(m['in_band_versus_baseline']['worst_seconds_saved'])} |"
        )
    lines += [
        "",
        "## Secondary: out of band (below 15 °C, above 35 °C), descriptive",
        "",
        "| Role | Member | Design | Feasible at every out-of-band point | Violations (reach / plating / temp) | Worst t_CV (s) | Mean t_CV (s) |",
        "|---|---|---|---|---|---|---|",
        f"| baseline | — | {b['design']} | {cells(b['secondary_out_of_band'])} |",
    ]
    for row in result["designs"]:
        m = row["mode_d"]
        if isinstance(m, dict):
            lines.append(
                f"| {row['role']} | {row['member']} | {m['design']} "
                f"| {cells(m['secondary_out_of_band'])} |"
            )
    lines += [
        "",
        "## Adversarial search (Mode X)",
        "",
        "| Member | Rank (deciding rule) | Points verified | In-band violations / unresolved / confirmed | Out-of-band violations / unresolved / confirmed |",
        "|---|---|---|---|---|",
    ]
    for member, row in result["adversarial"].items():
        i, o = row["verdicts"]["in_band"], row["verdicts"]["out_of_band"]

        def trio(c):
            return (
                f"{c.get(d.INFEASIBLE, 0)} / {c.get(d.UNRESOLVED, 0)} / "
                f"{c.get(d.FEASIBLE, 0)}"
            )

        lines.append(
            f"| {member} | {row['rank_under_deciding_rule']} of "
            f"{row['eligible_members']} | {len(row['points'])} | {trio(i)} "
            f"| {trio(o)} |"
        )
    findings = result["findings"]
    lines += [
        "",
        (
            f"Findings: {len(findings['in_band'])} in band, "
            f"{len(findings['out_of_band'])} out of band "
            "(SCORE_VALUE_DIVERGENCE when the member is in the top half under the "
            "deciding rule, otherwise OTHER_SIGNAL). A search that finds nothing is "
            "not a safety bound."
        ),
        "",
    ]
    return "\n".join(lines)


# --- operator path, under an EV4 experiment root -------------------------------------------------

TERMINAL = ("OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")


def _dir(experiment, *parts):
    path = experiment.root.joinpath("optimizer", *parts)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _json_bytes(value, indent=2):
    return (json.dumps(value, sort_keys=True, indent=indent) + "\n").encode()


def _ev4_contract(experiment):
    """The experiment's contract, if it is a study the optimizer runs: EV4's,
    or EV5's (`spec_for` then selects EV5's grids, roles and gate)."""
    contract = experiment.contract()
    if contract.get("case_prefix") not in ("ev4", "ev5"):
        raise OptimizerError("not_ev4", "the optimizer runs under EV4 or EV5")
    return contract


def import_grids(experiment, source):
    """Copy a pod's grid predictions into the root, write-once, each checked
    against the frozen panel (recipe digest, seed) and contract digest."""
    from carbon.development_session.data import write_once

    from ..compile import compile_recipe

    contract = _ev4_contract(experiment)
    expected = {}
    for member, _label, strategy, seed in experiment._members():
        _, recipe = compile_recipe(strategy)
        expected[member] = (recipe.recipe_digest, seed)
    target = _dir(experiment, "grid")
    copied, kept = [], []
    for path in sorted(Path(source).glob("*.json.gz")):
        member = path.name[: -len(".json.gz")]
        if member not in expected:
            raise OptimizerError("grid_not_in_panel", member)
        body = path.read_bytes()
        grid = load_grid(path, spec_for(contract))
        if (
            grid["member"] != member
            or (grid["recipe_digest"], grid["seed"]) != expected[member]
            or grid["contract_digest"] != ev.digest(contract)
        ):
            raise OptimizerError("grid_mismatch", member)
        out = target / path.name
        if out.exists():
            if out.read_bytes() != body:
                raise OptimizerError("grid_conflict", member)
            kept.append(member)
            continue
        write_once(out, body)
        copied.append(member)
    return {"imported": copied, "already_present": kept}


def _results(experiment):
    path = experiment.root / "results" / "results.json"
    if not path.exists():
        raise OptimizerError("not_evaluated", "evaluate EV4 first")
    results = json.loads(path.read_bytes())
    if results["contract_digest"] != experiment.manifest()["contract_digest"]:
        raise OptimizerError("results_mismatch")
    return results


def run_select(experiment, *, scores=None, admissible=None):
    """Apply the pre-registered member rule to the study's results and write
    the selection and the verification jobs, once. A second call returns the
    recorded selection and never re-selects. `scores` and `admissible` are
    `select_members`' (EV5: the SR-2 candidate's scores and the members the
    gate passes; `carbon.battery.value.ev5_run` supplies them)."""
    from carbon.development_session.data import write_once

    contract = _ev4_contract(experiment)
    out = _dir(experiment)
    path = out / "selection.json"
    if path.exists():
        return json.loads(path.read_bytes())
    results = _results(experiment)
    backbones = {
        row["member"]: row["strategy"]["backbone"]
        for row in experiment.manifest()["panel"]
    }
    chosen = {
        r["member"]
        for r in select_members(
            results,
            backbones,
            spec_for(contract),
            scores=scores,
            admissible=admissible,
        )
        if r["member"]
    }
    grids = {
        m: load_grid(_dir(experiment, "grid") / f"{m}.json.gz", spec_for(contract))
        for m in chosen
    }
    selection = select(
        contract, results, backbones, grids, scores=scores, admissible=admissible
    )
    write_once(path, _json_bytes(selection))
    write_once(out / "jobs.json", _json_bytes({"jobs": selection["jobs"]}, indent=1))
    return selection


def _selection(experiment):
    path = _dir(experiment) / "selection.json"
    if not path.exists():
        raise OptimizerError("not_selected", "run optimize select first")
    return json.loads(path.read_bytes())


def references_path(experiment):
    return _dir(experiment) / "references.jsonl"


def reference_map(experiment):
    path = references_path(experiment)
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            out[record["case_id"]] = record
    return out


def import_references(experiment, records_path):
    """Ingest verification records solved on a pod. Only the selection's jobs
    are kept, with inputs checked exactly; nothing recorded is replaced and
    FAILED_INFRA is never a reference."""
    wanted = {job["case_id"]: job for job in _selection(experiment)["jobs"]}
    path = references_path(experiment)
    have = set(reference_map(experiment))
    added = 0
    with path.open("a") as out:
        for line in Path(records_path).read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            job = wanted.get(record.get("case_id"))
            if (
                job is None
                or record["case_id"] in have
                or record.get("refined")
                or record.get("status") not in TERMINAL
            ):
                continue
            inputs = record.get("inputs") or {}
            if any(
                abs(float(inputs.get(k, float("nan"))) - job[k]) > 1e-12
                for k in ("c1", "c2", "t_amb_c", "soc0")
            ):
                raise OptimizerError("reference_inputs_mismatch", record["case_id"])
            out.write(json.dumps(record, sort_keys=True) + "\n")
            have.add(record["case_id"])
            added += 1
    path.chmod(0o600)
    return {
        "imported": added,
        "jobs": len(wanted),
        "missing": len(set(wanted) - have),
    }


def run_report(experiment):
    contract = _ev4_contract(experiment)
    selection = _selection(experiment)
    references = reference_map(experiment)
    missing = [
        j["case_id"] for j in selection["jobs"] if j["case_id"] not in references
    ]
    result = report(contract, _results(experiment), selection, references)
    result["missing_references"] = len(missing)
    out = _dir(experiment)
    (out / "results.json").write_bytes(_json_bytes(result))
    (out / "findings.json").write_bytes(_json_bytes(result["findings"]))
    (out / "report.md").write_text(render(result))
    return {
        "designs": [
            {
                "role": r["role"],
                "member": r["member"],
                "design": (
                    r["mode_d"]["design"]
                    if isinstance(r["mode_d"], dict)
                    else r["mode_d"]
                ),
            }
            for r in result["designs"]
        ],
        "findings": {k: len(v) for k, v in result["findings"].items()},
        "missing_references": len(missing),
    }
