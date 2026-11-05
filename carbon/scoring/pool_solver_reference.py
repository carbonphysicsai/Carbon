"""Pack-time solver-in-the-loop reference for the pool grader's D (option a1, Validator D page 4 Nov).

Today a target's reference is the best truly feasible point of its pre-solved pool (`pool_grader.build_target`), not
what a solver-driven optimiser finds. This module runs, ONCE PER TARGET AT PACK BUILD and only when the pack spec turns
it on, the grader's seeded CMA-ES (`pool_cmaes`, unchanged; this module repairs each sample into the design box before
the strategy adapts, so its trajectory is not the grader's) with the REAL solver as the objective, then a seeded walk
along the limit that is active at the solver's optimum. It returns the solver-optimum reference and every solved
point, typed, so the pack can add them to the target's pool (`extend_pool`). It never runs at grade time and never sees
a candidate.

Ranking on TRUE outputs (lower key is better): a truly feasible point (every margin >= 0) by its objective; then an
infeasible point by its summed limit violation in U units, then its objective; then a point the solver could not give
(reference failure or infrastructure), last; an exactly computed limit (U = 0) ranks its raw excess ahead of the U-scaled
ones, as the grader does. The reference is the best truly feasible OK point.

A1 NEEDS A2: without a near-limit rule (`build_target(near_limit=None)`, every registered version) the grader DROPS
every pool point within U of a limit, so the solver's on-limit optimum never becomes the reference; `extend_pool`
reports how many points fall within U. With a NEW version's rule (a2, `pool_grader` credit ramp, in main 581c7695) the
pack sets `Problem.near_limit` to that version's registered rule and `Problem.s_low` to the target's zero (the same
s_low `build_target` uses). Then the driver searches the grader's OWN value: a feasible point ranks by
`pool_grader.credit` x max(0, gain over s_low), the same function the grader scores with, so a point exactly on a limit
(credit 0) is not mistaken for the best; and the limit walk samples the credit-1 contour (true margin = U at the
optimum) instead of the limit itself. The value's peak can sit INSIDE the ramp (margin < U) when the gain is small next
to the objective's slope x U; the CMA-ES phase, which ranks by the same value, covers that, the walk does not.

The driver's reference is ADVISORY: the grader derives its own over the extended pool, and build_target recomputes
s_low there (the clean solver points move the median), so its argmax can differ from the driver's. Only the grader's
reference is the target's. Whether the zero should be fixed from the pre-solved pool is a grader rule (owner value).

Typed outcomes, never collapsed (AGENTS 7.5, invariant 7): `OK`; a reference failure (`REFERENCE_*` from the solve path,
or `REFERENCE_DERIVE_REFUSED` when the Challenge's own derive refuses the raw row): the reference's, never a candidate's;
`FAILED_INFRA`: retried up to the policy's count, else the target is `FAILED_INFRA_INCOMPLETE`, gives no reference and
adds nothing to the pool. Any other status from the solve path is refused (`solve_status_not_closed`), so no free text
reaches a count. `solve` must return records, not raise: an exception propagates and the caller marks the run
FAILED_INFRA.

Budget: B_s and the line-search count are DISTINCT DESIGNS solved; an infrastructure re-solve of the same design is
extra, at most `infra_retries` x designs, and counted (`solves`, `infra_attempts`). Whether re-solves should spend the
budget instead is the owner's call.

Every number the owner picks (the solver budget B_s, the population, the initial step, the line-search point count and
span, the infrastructure retries) is a required pack-spec value with no default; a missing one refuses with
`solver_reference_human_input_required`.

Custody only (Validator rule, 4 Nov): the adaptive trajectory traces the hidden optimum and its active limit, so
`run_pack` and `run_target` take the run's host class and refuse, before the first solve, any class not on
`CUSTODY_HOST_CLASSES` (`solver_reference_host_not_custody`). There is no default: a rented host never runs it.

Disclosure: designs, outputs and the reference are custody material; only
`public_summary` (counts and closed codes) may leave custody.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass

from carbon.scoring.pool_cmaes import CmaEs
from carbon.scoring.pool_grader import Limit, credit, u_value, valid_near_limit

SPEC_KEY = "solver_reference"
OK = "OK"
FAILED_INFRA = "FAILED_INFRA"
DERIVE_REFUSED = "REFERENCE_DERIVE_REFUSED"
#: Target outcomes.
TARGET_OK = "OK"
TARGET_NO_FEASIBLE = "REFERENCE_NO_FEASIBLE_POINT"
TARGET_INFRA = "FAILED_INFRA_INCOMPLETE"
_REFERENCE_STATUS = re.compile(r"REFERENCE_[A-Z][A-Z_]{0,63}")
# The custody hosts (custody2, Hostkey, GPUYard); exact strings, closed. Never a rented class.
CUSTODY_HOST_CLASSES = frozenset({"custody2", "hostkey", "gpuyard"})


class SolverReferenceRefused(ValueError):
    """The pack spec or a target's material cannot run the driver: Carbon's material, never a candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise SolverReferenceRefused(code)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class DriverPolicy:
    """The owner's values for one pack (no defaults: HUMAN_INPUT until set in the pack spec)."""

    budget: int  # B_s: distinct designs solved per target in the CMA-ES phase (infra re-solves are extra)
    population: int  # CMA-ES lambda (>= 2)
    sigma0: float  # initial step in the unit box
    line_search_points: int  # distinct designs solved along the active limit (0 = none)
    line_search_span: float  # half-width of the tangent walk, in the unit box
    infra_retries: int  # re-solves of a design whose solve failed on infrastructure

    def digest(self):
        body = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


_POLICY_FIELDS = (
    "budget",
    "population",
    "sigma0",
    "line_search_points",
    "line_search_span",
    "infra_retries",
)


def enabled(pack_spec):
    """True only when the pack spec says ``{"solver_reference": {"enabled": true, ...}}``; anything else is off."""
    block = pack_spec.get(SPEC_KEY) if type(pack_spec) is dict else None
    return type(block) is dict and block.get("enabled") is True


def policy_from_spec(pack_spec):
    """The `DriverPolicy` of an enabled pack spec, or `SolverReferenceRefused`. A field left out, None or
    "HUMAN_INPUT" refuses: nothing is defaulted."""
    _require(enabled(pack_spec), "solver_reference_not_enabled")
    block = pack_spec[SPEC_KEY]
    _require(
        set(block) <= {"enabled", *_POLICY_FIELDS}, "solver_reference_unknown_field"
    )
    _require(
        all(
            block.get(name) is not None and block.get(name) != "HUMAN_INPUT"
            for name in _POLICY_FIELDS
        ),
        "solver_reference_human_input_required",
    )
    ints = ("budget", "population", "line_search_points", "infra_retries")
    _require(
        all(type(block[name]) is int for name in ints),
        "solver_reference_policy_invalid",
    )
    _require(
        block["budget"] >= 1
        and block["population"] >= 2
        and block["line_search_points"] >= 0
        and block["infra_retries"] >= 0
        and _finite(block["sigma0"])
        and block["sigma0"] > 0
        and _finite(block["line_search_span"])
        and block["line_search_span"] > 0,
        "solver_reference_policy_invalid",
    )
    return DriverPolicy(**{name: block[name] for name in _POLICY_FIELDS})


@dataclass(frozen=True)
class Problem:
    """One target's sealed optimisation problem, in the grader's terms (custody material)."""

    target_id: str
    fixed: dict  # the target's fixed conditions, passed to `solve` unchanged
    outputs: tuple
    objective: str
    sense: str  # "max" | "min"
    limits: tuple  # pool_grader.Limit
    u: dict  # output -> U (number >= 0 or {"relative": r}), as the pool carries it
    box: tuple  # ((lo, hi), ...) design box
    start: tuple  # CMA-ES start in the unit box
    seed: int
    # A NEW version's registered near-limit rule (pool_grader credit ramp) and the target's zero s_low (as
    # build_target computes it), set together or not at all. None = today's grader (within-U points dropped).
    near_limit: dict | None = None
    s_low: float | None = None


def _check_problem(problem):
    _require(type(problem.target_id) is str and problem.target_id, "target_id_required")
    _require(problem.objective in problem.outputs, "objective_must_be_an_output")
    _require(problem.sense in ("max", "min"), "sense_must_be_max_or_min")
    _require(
        all(
            isinstance(limit, Limit)
            and limit.output in problem.outputs
            and limit.kind in ("<=", ">=")
            and _finite(limit.bound)
            for limit in problem.limits
        ),
        "limits_invalid",
    )
    _require(set(problem.u) == set(problem.outputs), "u_must_cover_the_outputs")
    _require(
        problem.box
        and all(_finite(lo) and _finite(hi) and hi > lo for lo, hi in problem.box),
        "box_invalid",
    )
    _require(
        len(problem.start) == len(problem.box)
        and all(_finite(x) and 0.0 <= x <= 1.0 for x in problem.start),
        "start_must_be_in_the_unit_box",
    )
    _require(type(problem.seed) is int, "seed_must_be_an_int")
    _require(
        (problem.near_limit is None and problem.s_low is None)
        or (valid_near_limit(problem.near_limit) and _finite(problem.s_low)),
        "near_limit_and_s_low_go_together",
    )


@dataclass(frozen=True)
class SolvedPoint:
    design: tuple  # raw design vector
    phase: str  # "cmaes" | "line_search"
    status: str  # OK | REFERENCE_* | FAILED_INFRA
    outputs: dict | None  # derived outputs when OK
    margins: dict | None  # limit index -> true margin, when OK
    attempts: int


@dataclass(frozen=True)
class TargetResult:
    target_id: str
    status: str  # TARGET_OK | TARGET_NO_FEASIBLE | TARGET_INFRA
    reference: int | None  # index into `points` of the solver optimum
    active_limit: (
        int | None
    )  # the limit index with the smallest margin/U at the optimum
    points: tuple  # SolvedPoint, in solve order
    counts: dict
    policy_digest: str


def _raw(problem, unit):
    return tuple(lo + x * (hi - lo) for x, (lo, hi) in zip(unit, problem.box))


def _unit(problem, design):
    return tuple((x - lo) / (hi - lo) for x, (lo, hi) in zip(design, problem.box))


def _margins(problem, outputs):
    return {
        index: limit.margin(outputs[limit.output])
        for index, limit in enumerate(problem.limits)
    }


def _key(problem, point):
    if point.status != OK:
        return (2, 0.0, 0.0, 0.0)
    loss = -(1.0 if problem.sense == "max" else -1.0) * point.outputs[problem.objective]
    violation = exact = 0.0
    for index, limit in enumerate(problem.limits):
        margin = point.margins[index]
        if margin < 0.0:
            scale = u_value(problem.u[limit.output], point.outputs[limit.output])
            if scale > 0.0:
                violation += -margin / scale
            else:
                exact += (
                    -margin
                )  # an exactly computed quantity: its raw excess ranks first
    if violation == 0.0 and exact == 0.0:
        if problem.near_limit is None:
            return (0, 0.0, 0.0, loss)
        # the grader's value of this point: credit x gain over the zero; ties (value 0) still climb by the objective
        c = credit(
            problem.limits,
            point.outputs,
            lambda name: u_value(problem.u[name], point.outputs[name]),
        )
        return (0, 0.0, -c * max(0.0, -loss - problem.s_low), loss)
    return (1, exact, violation, loss)


def _solve(problem, solve, designs, phase, policy, counts):
    """Solve `designs` (raw) in one call, re-solving infrastructure failures up to `infra_retries` times."""
    results = [None] * len(designs)
    attempts = [0] * len(designs)
    pending = list(range(len(designs)))
    for _ in range(policy.infra_retries + 1):
        if not pending:
            break
        batch = solve(problem.fixed, [list(designs[i]) for i in pending])
        _require(
            type(batch) is list and len(batch) == len(pending),
            "solve_returned_wrong_count",
        )
        still = []
        for index, record in zip(pending, batch):
            attempts[index] += 1
            counts["solves"] += 1
            status = record.get("status") if type(record) is dict else None
            _require(type(status) is str and status, "solve_record_untyped")
            _require(
                status in (OK, FAILED_INFRA) or _REFERENCE_STATUS.fullmatch(status),
                "solve_status_not_closed",
            )
            if status == FAILED_INFRA:
                counts["infra_attempts"] += 1
                still.append(index)
                continue
            results[index] = record
        pending = still
    points = []
    for index, design in enumerate(designs):
        record = results[index]
        if record is None:
            status, outputs = FAILED_INFRA, None
        elif record["status"] != OK:
            status, outputs = record["status"], None
        else:
            outputs = record.get("outputs")
            # A wrong output set is Carbon's setup error (adapter vs problem), never a scientific outcome.
            _require(
                type(outputs) is dict and set(outputs) == set(problem.outputs),
                "derive_outputs_do_not_match_problem",
            )
            try:
                values = {k: float(v) for k, v in outputs.items()}
            except (TypeError, ValueError):
                values = None
            if values is None or not all(math.isfinite(v) for v in values.values()):
                status, outputs = DERIVE_REFUSED, None
            else:
                status, outputs = OK, values
        counts["by_status"][status] = counts["by_status"].get(status, 0) + 1
        points.append(
            SolvedPoint(
                design=tuple(float(x) for x in design),
                phase=phase,
                status=status,
                outputs=outputs,
                margins=None if outputs is None else _margins(problem, outputs),
                attempts=attempts[index],
            )
        )
    return points


def _cmaes_phase(problem, solve, policy, counts):
    es = CmaEs(problem.start, policy.sigma0, problem.seed, policy.population)
    points = []
    while len(points) < policy.budget:
        samples = es.ask()
        room = policy.budget - len(points)
        units = [tuple(min(1.0, max(0.0, x)) for x in s) for s in samples]
        # Lamarckian repair: the strategy adapts on the in-box points it actually evaluated, so its mean cannot
        # walk out of the box (with unrepaired steps a mean outside the box spends the budget on clipped edges).
        # `pool_cmaes` itself is unchanged: the grader shares it.
        es._ys = [[(u - m) / es.sigma for u, m in zip(unit, es.mean)] for unit in units]
        units = units[:room]
        solved = _solve(
            problem, solve, [_raw(problem, u) for u in units], "cmaes", policy, counts
        )
        points.extend(solved)
        if len(solved) < len(samples):
            break  # the budget ended mid-generation: nothing left to adapt to
        es.tell([_key(problem, p) for p in solved])
    return points


def _fit_margin(problem, points, limit_index, centre, count):
    """Least squares m(x) ~ a + g.x of one limit's true margin over the `count` OK points nearest `centre`
    (unit box), or None when underdetermined."""
    ok = [p for p in points if p.status == OK]
    n = len(problem.box)
    if len(ok) < n + 1:
        return None
    ok.sort(
        key=lambda p: sum(
            (a - b) ** 2 for a, b in zip(_unit(problem, p.design), centre)
        )
    )
    rows = [(1.0, *_unit(problem, p.design)) for p in ok[: max(count, n + 1)]]
    ys = [p.margins[limit_index] for p in ok[: max(count, n + 1)]]
    m = n + 1
    # Normal equations by Gaussian elimination (pure Python, deterministic); a pivot at machine precision relative
    # to the matrix's scale means the points cannot determine a plane: None.
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(m)] for i in range(m)]
    tiny = max(abs(ata[i][i]) for i in range(m)) * 1e-12
    aty = [sum(r[i] * y for r, y in zip(rows, ys)) for i in range(m)]
    for col in range(m):
        pivot = max(range(col, m), key=lambda r: abs(ata[r][col]))
        if abs(ata[pivot][col]) <= tiny:
            return None
        ata[col], ata[pivot] = ata[pivot], ata[col]
        aty[col], aty[pivot] = aty[pivot], aty[col]
        for r in range(m):
            if r != col:
                f = ata[r][col] / ata[col][col]
                ata[r] = [a - f * b for a, b in zip(ata[r], ata[col])]
                aty[r] -= f * aty[col]
    coef = [aty[i] / ata[i][i] for i in range(m)]
    gradient = coef[1:]
    if not all(math.isfinite(c) for c in coef) or sum(g * g for g in gradient) == 0.0:
        return None
    return coef[0], gradient


def _line_targets(problem, points, reference, active, policy):
    """Seeded unit-box targets on the fitted active-limit boundary around the optimum: first the optimum's own
    projection onto it, then tangent walks both ways (seeded directions orthogonal to the fitted gradient).
    """
    n = len(problem.box)
    centre = _unit(problem, points[reference].design)
    fit = _fit_margin(problem, points, active, centre, 2 * n + 1)
    if fit is None:
        return None
    a, g = fit
    gg = sum(x * x for x in g)
    # under a near-limit rule the walk targets the credit-1 offset (margin = U at the optimum), not the limit itself
    goal = 0.0
    if problem.near_limit is not None:
        limit = problem.limits[active]
        goal = u_value(problem.u[limit.output], points[reference].outputs[limit.output])
    rng = random.Random(
        hashlib.sha256(f"line-search:{problem.seed}".encode()).hexdigest()
    )

    def on_boundary(x):
        m = a + sum(gi * xi for gi, xi in zip(g, x)) - goal
        return tuple(min(1.0, max(0.0, xi - m * gi / gg)) for xi, gi in zip(x, g))

    count = (
        policy.line_search_points + 1
    ) // 2  # each target has about two solves to reach the limit
    targets = [on_boundary(centre)]
    if n == 1:
        return (
            centre,
            targets,
        )  # one dimension: the limit is a point, no tangent to walk
    pairs = max(1, count // 2)
    j = 0
    while len(targets) < count:
        if j % 2 == 0:
            z = [rng.gauss(0.0, 1.0) for _ in range(n)]
            dot = sum(zi * gi for zi, gi in zip(z, g)) / gg
            t = [zi - dot * gi for zi, gi in zip(z, g)]
            norm = math.sqrt(sum(x * x for x in t)) or 1.0
        step = policy.line_search_span * (j // 2 + 1) / pairs
        step = step if j % 2 == 0 else -step
        targets.append(on_boundary([c + step * ti / norm for c, ti in zip(centre, t)]))
        j += 1
    return centre, targets


def _line_phase(problem, solve, points, reference, active, policy, counts):
    """Walk each target in from its boundary guess: solve every open target in one batch; a target that comes
    back truly infeasible halves its step back toward the feasible optimum and stays open; a feasible or failed
    one closes. Stops when the line-search budget ends. Returns the solved points, or None if the fit fails.
    """
    found = _line_targets(problem, points, reference, active, policy)
    if found is None:
        return None
    centre, targets = found
    # [target, tau, lo]: tau = the fraction of the way out to the target; lo = the largest known-feasible tau.
    unique = dict.fromkeys(tuple(round(x, 12) for x in t) for t in targets)
    open_ = [[target, 1.0, 0.0] for target in unique]
    solved_points, budget = [], policy.line_search_points
    while open_ and budget > 0:
        batch = open_[:budget]
        designs = [
            _raw(problem, [c + tau * (x - c) for c, x in zip(centre, target)])
            for target, tau, _ in batch
        ]
        solved = _solve(problem, solve, designs, "line_search", policy, counts)
        solved_points.extend(solved)
        budget -= len(batch)
        still = []
        for (target, tau, lo), point in zip(batch, solved):
            # Bisection on [lo, tau]: an infeasible point steps back to the midpoint. A feasible point closes:
            # the boundary guess is linear, so a feasible landing is already at or inside the limit.
            if point.status == OK and any(m < 0.0 for m in point.margins.values()):
                still.append([target, (lo + tau) / 2.0, lo])
        open_ = still + open_[len(batch) :]
    return solved_points


def _reference(problem, points):
    feasible = [
        i
        for i, p in enumerate(points)
        if p.status == OK and all(m >= 0.0 for m in p.margins.values())
    ]
    if not feasible:
        return None
    return min(feasible, key=lambda i: (_key(problem, points[i]), i))


def _active(problem, point):
    if not problem.limits:
        return None

    def scaled(index):
        limit = problem.limits[index]
        scale = u_value(problem.u[limit.output], point.outputs[limit.output])
        margin = point.margins[index]
        # Margins in U units are comparable; an exactly computed limit (U = 0) has no U unit, so it is the active
        # one only when no U-carrying limit exists (then by raw margin).
        return (0, margin / scale, index) if scale > 0.0 else (1, margin, index)

    return min(range(len(problem.limits)), key=scaled)


def _require_custody(host_class):
    _require(
        type(host_class) is str and host_class in CUSTODY_HOST_CLASSES,
        "solver_reference_host_not_custody",
    )


def run_target(problem, solve, policy, *, host_class):
    """The solver-driven reference of one target. `solve(fixed, designs)` returns one typed record per raw design,
    ``{"status": "OK", "outputs": {derived}}`` or ``{"status": "<REFERENCE_* | FAILED_INFRA>"}`` (the Challenge's pool
    solve path plus its `derive`; see `adapter_solver`). `host_class` must be a custody class.
    """
    _require_custody(host_class)
    _check_problem(problem)
    _require(isinstance(policy, DriverPolicy), "policy_required")
    counts = {
        "solves": 0,
        "infra_attempts": 0,
        "by_status": {},
        "line_search": "not_run",
    }
    points = _cmaes_phase(problem, solve, policy, counts)
    reference = _reference(problem, points)
    active = None
    if reference is not None:
        active = _active(problem, points[reference])
        if policy.line_search_points and active is not None:
            line = _line_phase(
                problem, solve, points, reference, active, policy, counts
            )
            if line is None:
                counts["line_search"] = "underdetermined"
            else:
                points.extend(line)
                counts["line_search"] = "run"
                best = _reference(problem, points)
                if best != reference:
                    reference, active = best, _active(problem, points[best])
    if any(p.status == FAILED_INFRA for p in points):
        status, reference, active = TARGET_INFRA, None, None
    elif reference is None:
        status = TARGET_NO_FEASIBLE
    else:
        status = TARGET_OK
    return TargetResult(
        target_id=problem.target_id,
        status=status,
        reference=reference,
        active_limit=active,
        points=tuple(points),
        counts=counts,
        policy_digest=policy.digest(),
    )


def run_pack(pack_spec, problems, solve, *, host_class):
    """Every target of a pack, or ``None`` when the pack spec leaves the driver off (nothing is solved). An enabled
    pack on a host class off the custody list refuses before any solve."""
    if not enabled(pack_spec):
        return None
    _require_custody(host_class)
    policy = policy_from_spec(pack_spec)
    return tuple(
        run_target(problem, solve, policy, host_class=host_class)
        for problem in problems
    )


def adapter_solver(adapter, run_rows):
    """A `solve` from a Challenge's `pool_adapters.PoolAdapter` and its pack-time solve path.

    `run_rows(rows)` runs the REAL solver on model input rows (the pool solve path: a plan of these rows through the
    Challenge's reference `run_batch`) and returns one typed record per row, ``{"status": ..., "raw": raw output row}``.
    The adapter's own `derive` turns an OK raw row into the derived outputs; a refused derive is the reference's
    (`REFERENCE_DERIVE_REFUSED`), never a candidate's."""

    def solve(fixed, designs):
        rows = [adapter.model_row(fixed, design) for design in designs]
        records = run_rows(rows)
        _require(
            type(records) is list and len(records) == len(rows),
            "solve_returned_wrong_count",
        )
        out = []
        for row, record in zip(rows, records):
            status = record.get("status") if type(record) is dict else None
            if status != OK:
                out.append({"status": status})
                continue
            derived = adapter.derive_row(row, record.get("raw"))
            out.append(
                {"status": DERIVE_REFUSED}
                if derived is None
                else {"status": OK, "outputs": derived}
            )
        return out

    return solve


def extend_pool(designs, truths, result, problem):
    """``(designs, truths, added, within_u)``: the pool with the result's OK points appended in solve order, the
    appended indices, and how many of them lie within U of a limit (today's `build_target` drops those; see A1 NEEDS
    A2). Only a TARGET_OK result extends a pool: an infrastructure-incomplete or no-feasible target adds nothing
    (`solver_reference_result_not_ok`). Reference and infrastructure failures are never added.
    """
    _require(result.status == TARGET_OK, "solver_reference_result_not_ok")
    _require(result.target_id == problem.target_id, "solver_reference_target_mismatch")
    designs, truths, added = list(designs), list(truths), []
    within = 0
    for point in result.points:
        if point.status != OK:
            continue
        added.append(len(designs))
        designs.append(list(point.design))
        truths.append(dict(point.outputs))
        within += any(
            abs(point.margins[index])
            <= u_value(problem.u[limit.output], point.outputs[limit.output])
            for index, limit in enumerate(problem.limits)
        )
    return designs, truths, tuple(added), within


def pool_start(problem, designs, truths):
    """The unit-box position of the pool's best truly feasible point: a warm start for the CMA-ES so the solver
    search begins where the pre-solved pool already is (custody material, like `Problem.start`). None when the pool
    has no feasible point."""
    best = None
    sign = 1.0 if problem.sense == "max" else -1.0
    for design, truth in zip(designs, truths):
        if all(limit.margin(truth[limit.output]) >= 0.0 for limit in problem.limits):
            score = sign * truth[problem.objective]
            if best is None or score > best[0]:
                best = (score, design)
    if best is None:
        return None
    return tuple(min(1.0, max(0.0, x)) for x in _unit(problem, best[1]))


def public_summary(results):
    """Counts and closed codes only: no design, output, margin or reference value."""
    return {
        "targets": len(results),
        "by_target_status": {
            status: sum(1 for r in results if r.status == status)
            for status in sorted({r.status for r in results})
        },
        "solves": sum(r.counts["solves"] for r in results),
        "by_point_status": {
            status: sum(r.counts["by_status"].get(status, 0) for r in results)
            for status in sorted({s for r in results for s in r.counts["by_status"]})
        },
    }
