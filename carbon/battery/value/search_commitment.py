# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Versioned design-search requests, proposal commitments and verified results.

Handoff §11-12, as a **separate later experiment** (`EXPERIMENT`): it wraps the
fixed design-optimizer baseline of `docs/development/DESIGN_OPTIMIZER_SCOPE.md`
so that a different search method (for example one an external research agent
proposes) can be compared with it on development material only. It does not
modify EV4, its contract, its panel or `optimizer.py`; EV4's own conditions are
refused (`ev4_protected_conditions`).

The record carries everything the handoff lists:

- decision contract and model identity;
- search mode (PB-INV design search or PB-ADV adversarial search), conditions,
  candidate space and budgets;
- optimizer code and configuration digests;
- every model query and the ordered selections;
- a proposal **commitment** written before any reference access;
- reference results, unresolved cases and final outcomes.

Commitment before reference access is enforced by construction: `verify`
accepts only a `Commitment`, which only `commit` can create, and `verify`
re-reads the write-once commitment file before calling the reference. An
UNRESOLVED or unavailable reference stays exactly that; it is never counted
safe or unsafe. A best design is best-known, not a global optimum. Nothing here
passes or fails a model: PB-INV/PB-ADV acceptance policies are unset
(`DESIGN_OPTIMIZER_SCOPE.md` §4).

The fixed grid (`fixed_grid`) applies the scope's Mode D and Mode X rules over a
declared condition set. On EV4's in-band model conditions it reproduces
`optimizer.mode_d` and `optimizer.mode_x` (conformance test, run when that
module is present).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

from . import contract as ev
from . import decision as d

REQUEST_SCHEMA = "carbon.design-search.request.v1"
COMMITMENT_SCHEMA = "carbon.design-search.commitment.v1"
RESULT_SCHEMA = "carbon.design-search.result.v1"
COMPARISON_SCHEMA = "carbon.design-search.comparison.v1"
EXPERIMENT = (
    "MIRA-OPTIMIZER-DEV-01: separate development experiment, not EV4; "
    "development material only; no qualification"
)
MODES = ("PB-INV", "PB-ADV")
QUANTITIES = ("time_to_cv_onset_s", "plating_margin_v", "peak_temperature_c")
#: The scope's design grid (generator bounds; c1-major so the tie rule is the
#: grid order): 31 x 33 = 1023 designs.
C1 = tuple(round(0.50 + 0.05 * i, 2) for i in range(31))
C2 = tuple(round(0.200 + 0.025 * j, 3) for j in range(33))
GRID = tuple((c1, c2) for c1 in C1 for c2 in C2)
BOUNDS = {"c1": (0.5, 2.0), "c2": (0.2, 1.0)}


class SearchError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _digest(value):
    return "sha256:" + hashlib.sha256(ev.canonical(value)).hexdigest()


def _protected():
    from .ev4_protected_conditions import is_protected

    return is_protected


# --- requests ---------------------------------------------------------------------


def request(
    *,
    contract,
    model,
    mode,
    conditions,
    query_budget,
    verification_budget,
    optimizer,
    seed_policy,
    designs=GRID,
    material="DEVELOPMENT",
):
    """A validated, versioned search request."""
    if material != "DEVELOPMENT":
        raise SearchError("development_material_only")
    if mode not in MODES:
        raise SearchError("unknown_mode")
    if set(model) != {"member", "recipe_digest", "seed"}:
        raise SearchError("model_identity_fields")
    if set(optimizer) != {"name", "code_digest", "configuration_digest"}:
        raise SearchError("optimizer_identity_fields")
    for key in ("code_digest", "configuration_digest"):
        if not str(optimizer[key]).startswith("sha256:"):
            raise SearchError("optimizer_identity_unpinned")
    envelope = contract["operating_conditions"]["envelope"]
    is_protected = _protected()
    rows = []
    for t_amb, soc0 in conditions:
        t_amb, soc0 = float(t_amb), float(soc0)
        if not (
            envelope["t_amb_c"][0] <= t_amb <= envelope["t_amb_c"][1]
            and envelope["soc0"][0] <= soc0 <= envelope["soc0"][1]
        ):
            raise SearchError("condition_outside_envelope", f"{t_amb},{soc0}")
        if is_protected(t_amb, soc0):
            raise SearchError("protected_material_requested", f"{t_amb},{soc0}")
        rows.append([t_amb, soc0])
    if not rows or len({tuple(r) for r in rows}) != len(rows):
        raise SearchError("conditions_empty_or_repeated")
    space = []
    for c1, c2 in designs:
        if not (BOUNDS["c1"][0] <= c1 <= BOUNDS["c1"][1]) or not (
            BOUNDS["c2"][0] <= c2 <= BOUNDS["c2"][1]
        ):
            raise SearchError("design_outside_generator_bounds")
        space.append([float(c1), float(c2)])
    for name, value in (("query", query_budget), ("verification", verification_budget)):
        if type(value) is not int or value <= 0:
            raise SearchError(name + "_budget_positive_integer")
    body = {
        "schema": REQUEST_SCHEMA,
        "experiment": EXPERIMENT,
        "material": material,
        "contract_digest": ev.digest(contract),
        "model": dict(model),
        "mode": mode,
        "conditions": rows,
        "candidate_space": {"designs": len(space), "digest": _digest(space)},
        "query_budget": query_budget,
        "verification_budget": verification_budget,
        "optimizer": dict(optimizer),
        "seed_policy": seed_policy,
    }
    return {**body, "request_digest": _digest(body)}, space


# --- the budgeted model oracle --------------------------------------------------


class Oracle:
    """Model predictions for declared (design, condition) points only, within
    the query budget; every query is recorded."""

    def __init__(self, contract, infer, req, space):
        self.contract = contract
        self.infer = infer
        self.budget = req["query_budget"]
        self.conditions = {tuple(c) for c in req["conditions"]}
        self.designs = {tuple(x) for x in space}
        self.log = []
        self.elapsed = 0.0

    @property
    def used(self):
        return len(self.log)

    def query(self, points):
        """`points`: [(c1, c2, t_amb, soc0)] -> [quantities] in order."""
        points = [tuple(float(v) for v in p) for p in points]
        if self.used + len(points) > self.budget:
            raise SearchError("query_budget_exhausted")
        _protected_check = _protected()
        for c1, c2, t_amb, soc0 in points:
            if _protected_check(t_amb, soc0) or (t_amb, soc0) not in self.conditions:
                raise SearchError("undeclared_condition_queried")
            if (c1, c2) not in self.designs:
                raise SearchError("undeclared_design_queried")
        inputs = {
            f"q{self.used + i:06d}": {
                "c1": p[0],
                "c2": p[1],
                "t_amb_c": p[2],
                "soc0": p[3],
            }
            for i, p in enumerate(points)
        }
        start = time.perf_counter()
        outputs = self.infer(inputs)
        self.elapsed += time.perf_counter() - start
        out = []
        for key, point in zip(inputs, points):
            q = d.measure(self.contract, outputs[key])
            self.log.append({"point": list(point), "quantities": q})
            out.append(q)
        return out


# --- the fixed baseline -----------------------------------------------------------


def _passes(contract, q):
    if q["time_to_cv_onset_s"] is None:
        return False
    return all(v == d.PASS for v in d.check(contract, q).values())


def margins(contract, q):
    """Band-normalised constraint margins (positive = passing side); the
    scope's Mode X ordering, identical to `optimizer.margins`."""
    bands = contract["reference"]["uncertainty"]["bands"]
    rules = {c["id"]: c for c in contract["constraints"]}
    window = contract["objective"]["window_s"] - contract["objective"]["charge_start_s"]
    return {
        "reach_cv_in_window": (window - q["time_to_cv_onset_s"])
        / bands["time_to_cv_onset_s"],
        "no_plating_onset": (
            q["plating_margin_v"] - rules["no_plating_onset"]["threshold"]
        )
        / bands["plating_margin_v"],
        "peak_temperature": (
            rules["peak_temperature"]["threshold"] - q["peak_temperature_c"]
        )
        / bands["peak_temperature_c"],
    }


def fixed_grid(contract, oracle, req, space):
    """The declared baseline: query every (design, condition), then apply the
    scope's rule. PB-INV: the design predicted feasible at every condition with
    the lowest worst-case predicted time to CV; ties by lower c1 then c2; else
    abstain. PB-ADV: the predicted-feasible points with the smallest
    band-normalised margin, up to the verification budget."""
    conditions = [tuple(c) for c in req["conditions"]]
    points = [(c1, c2, t, s) for c1, c2 in space for t, s in conditions]
    quantities = oracle.query(points)
    table = dict(zip(points, quantities))
    if req["mode"] == "PB-INV":
        best = None
        for c1, c2 in space:
            worst = -math.inf
            for t, s in conditions:
                q = table[(c1, c2, t, s)]
                if not _passes(contract, q):
                    break
                worst = max(worst, q["time_to_cv_onset_s"])
            else:
                key = (worst, c1, c2)
                if best is None or key < best:
                    best = key
        if best is None:
            return []
        return [{"c1": best[1], "c2": best[2], "predicted_worst_time_to_cv_s": best[0]}]
    ranked = []
    for (c1, c2, t, s), q in table.items():
        if not _passes(contract, q):
            continue
        m = margins(contract, q)
        binding = min(m, key=lambda name: (m[name], name))
        ranked.append((m[binding], c1, c2, t, s, binding))
    ranked.sort(key=lambda p: p[:5])
    return [
        {
            "c1": c1,
            "c2": c2,
            "t_amb_c": t,
            "soc0": s,
            "predicted_margin_bands": margin,
            "binding_constraint": binding,
        }
        for margin, c1, c2, t, s, binding in ranked[: req["verification_budget"]]
    ]


# --- commitment -------------------------------------------------------------------

_TOKEN = object()


class Commitment:
    """A proposal committed to disk before reference access. Only `commit`
    builds one; a raw dict, even a correct one, is refused by `verify`."""

    def __init__(self, token, path, document):
        if token is not _TOKEN:
            raise SearchError("commitment_only_from_commit")
        self.path = path
        self.document = document


def commit(req, selections, oracle, directory):
    """Write the commitment once (exclusive create) and return it."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if req["mode"] == "PB-ADV" and len(selections) > req["verification_budget"]:
        raise SearchError("verification_budget_exceeded")
    if req["mode"] == "PB-INV" and len(selections) > 1:
        raise SearchError("pb_inv_commits_one_design")
    body = {
        "schema": COMMITMENT_SCHEMA,
        "request": req,
        "queries_used": oracle.used,
        "query_log_digest": _digest(oracle.log),
        "selections": [dict(s) for s in selections],
        "status": "PROPOSALS" if selections else "ABSTAIN",
    }
    document = {**body, "commitment_digest": _digest(body)}
    path = directory / (
        req["request_digest"].removeprefix("sha256:") + ".commitment.json"
    )
    data = (json.dumps(document, sort_keys=True, indent=1) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    return Commitment(_TOKEN, path, document)


def case_id(c1, c2, t_amb, soc0):
    return f"dsx:{ev.candidate_id({'c1': c1, 'c2': c2})}:t={t_amb!r},soc0={soc0!r}"


def _jobs(document):
    req = document["request"]
    jobs = []
    for s in document["selections"]:
        where = (
            req["conditions"]
            if req["mode"] == "PB-INV"
            else [[s["t_amb_c"], s["soc0"]]]
        )
        for t, soc0 in where:
            jobs.append(
                {
                    "case_id": case_id(s["c1"], s["c2"], t, soc0),
                    "c1": s["c1"],
                    "c2": s["c2"],
                    "t_amb_c": t,
                    "soc0": soc0,
                }
            )
    return jobs


def _verdict(contract, record):
    if record is None or record.get("status") != "OK":
        return d.UNAVAILABLE, None
    q = d.measure(contract, record["outputs"])
    checks = d.check(contract, q, contract["reference"]["uncertainty"]["bands"])
    values = set(checks.values())
    verdict = (
        d.INFEASIBLE
        if d.FAIL in values
        else d.UNRESOLVED if d.UNRESOLVED in values else d.FEASIBLE
    )
    return verdict, {"quantities": q, "checks": checks}


def _load_committed(commitment):
    """The committed document, only from a `Commitment` whose file is unchanged."""
    if type(commitment) is not Commitment:
        raise SearchError("commitment_only_from_commit")
    on_disk = json.loads(Path(commitment.path).read_bytes())
    if on_disk != commitment.document:
        raise SearchError("commitment_changed_after_commit")
    return on_disk


def verify(contract, commitment, reference):
    """Send the committed proposals to `reference(jobs) -> {case_id: record}`
    and report every outcome. UNRESOLVED and unavailable stay as they are."""
    on_disk = _load_committed(commitment)
    if on_disk["request"]["contract_digest"] != ev.digest(contract):
        raise SearchError("contract_mismatch")
    jobs = _jobs(on_disk)
    records = reference(jobs) if jobs else {}
    rows, counts = [], {
        s: 0 for s in (d.FEASIBLE, d.INFEASIBLE, d.UNRESOLVED, d.UNAVAILABLE)
    }
    for job in jobs:
        verdict, detail = _verdict(contract, records.get(job["case_id"]))
        counts[verdict] += 1
        rows.append({**job, "verdict": verdict, "reference": detail})
    return {
        "schema": RESULT_SCHEMA,
        "experiment": EXPERIMENT,
        "commitment_digest": on_disk["commitment_digest"],
        "request_digest": on_disk["request"]["request_digest"],
        "mode": on_disk["request"]["mode"],
        "status": on_disk["status"],
        "reference_jobs": len(jobs),
        "verdicts": counts,
        "rows": rows,
        "claims": {
            "best_design_is_global_optimum": False,
            "search_finding_nothing_proves_safety": False,
            "unresolved_counted_as_safe_or_unsafe": False,
            "qualification": False,
        },
    }


def compare(contract, infer, reference, methods, *, base, directory):
    """Run each method on the same request (equal query and verification
    budgets), commit, verify and report runtime. `methods` maps name ->
    `method(contract, oracle, req, space) -> selections`; it must include the
    fixed baseline under the name `fixed_grid`."""
    if methods.get("fixed_grid") is not fixed_grid:
        raise SearchError("baseline_required", "methods must include fixed_grid")
    rows = {}
    for name in sorted(methods):
        req, space = request(
            contract=contract,
            **{**base, "optimizer": {**base["optimizer"], "name": name}},
        )
        oracle = Oracle(contract, infer, req, space)
        start = time.perf_counter()
        selections = methods[name](contract, oracle, req, space)
        search_seconds = time.perf_counter() - start
        commitment = commit(req, selections, oracle, Path(directory) / name)
        result = verify(contract, commitment, reference)
        rows[name] = {
            "queries_used": oracle.used,
            "query_budget": req["query_budget"],
            "search_seconds": search_seconds,
            "model_seconds": oracle.elapsed,
            "selections": selections,
            "result": result,
        }
    return {
        "schema": COMPARISON_SCHEMA,
        "experiment": EXPERIMENT,
        "basis": "equal query and verification budgets; measured wall-clock runtime",
        "methods": rows,
        "separate_experiments": (
            "equal-time budgets and adaptive agent search are separate experiments "
            "and are labelled as such when run"
        ),
    }
