"""Pool grader: the design half as optimisation over a pre-solved pool, with no solver at grade time.

Basis: OWNER-INVERSE-DESIGN-PROOF-01 and OWNER-HEADROOM-REGIONS-01; spec
`codex-queue/reports/POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024.md` (Validator). One module for every
Challenge: a Challenge plugs in only data (its design box, outputs, limits, objective, U, pool and the
true outputs of each pool design) and a `predict` callable. Nothing here names a Challenge.

How one target is graded (spec section 2):
1. Carbon's seeded CMA-ES (`pool_cmaes`) searches the target's normalised design box. Each proposal
   snaps to the nearest unqueried queryable pool point. The model predicts that point's outputs (one
   batched call per generation). Ranking is feasibility-first on the PREDICTED outputs, then by the
   predicted objective: the exact, constant-free form of "predicted objective with a penalty for
   predicted limit violations".
2. The final pick is the best predicted-feasible point among those queried. Its truth is looked up.
3. D(target) = 0 if the pick is truly infeasible (or there is no predicted-feasible pick), else
   q * h, with q the closeness to the reference optimum (clipped to [0, 1], the median feasible
   objective scoring 0) and h = exp(-e / s_h) the honesty of the model's own prediction at its pick.
   A NEW version may register the engineer's-shortcut zero instead (OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01:
   `OptimizerPolicy.d_zero`, per target `build_target(zero=...)`): the objective the version's registered cheap
   method reached screen-then-verify at budget B scores 0, so a high D means beating the engineer's shortcut.
4. D(set) is the mean over the set's targets. No simulator runs.

Every constant the spec marks OWNER (the query budget B, the honesty scale s_h, the A and A_gen
scales, how A_gen enters A, the C rule) is a required argument with no default. The CMA-ES initial
step size and the honesty error reduction (max or rms over outputs) are also explicit: the spec does
not fix them.

Disclosure: only `SetGrade.public()` (the set's D and closed reason codes) may leave custody; picks,
per-target values, pool points and queries stay in custody.

Reference failure is not candidate failure: a pool that cannot give a non-degenerate reference is
refused at build time (`PoolRefused`), never scored as a candidate's loss. A malformed prediction is
the candidate's (closed code, D = 0); an exception from `predict` (a crashed sandbox) propagates, so
the caller can mark the grade FAILED_INFRA.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass, replace

from carbon.scoring.design_fidelity import benefit
from carbon.scoring.pool_cmaes import CmaEs

REASONS = (
    "graded",
    "no_predicted_feasible_pick",
    "pick_infeasible",
    "prediction_invalid",
)


SHELL_MODES = ("designs", "conditions")


def _shell_row(row):
    lo, hi, ext_lo, ext_hi = (float(x) for x in row)
    _require(
        all(math.isfinite(v) for v in (lo, hi, ext_lo, ext_hi))
        and lo < hi
        and ext_lo >= 0.0
        and ext_hi >= 0.0,
        "shell_rows_are_train_lo_hi_and_non_negative_extensions",
    )
    return (lo, hi, ext_lo, ext_hi)


def _valid_shell(shell, design_inputs, fixed):
    """The explicit shell of an extended target: {"mode": "designs" | "conditions", "inputs": ...}. The MODE comes
    from the pool source, never inferred. "designs": one (train_lo, train_hi, ext_lo, ext_hi) row per design input
    in box order, and every queryable point (the reference included) must lie in the shell. "conditions" (a
    condition input extends): a row per condition input NAME, and the target's fixed conditions must lie in the
    shell once; the design box is then not constrained."""
    _require(
        type(shell) is dict and set(shell) == {"mode", "inputs"},
        "shell_must_be_a_mode_and_its_inputs",
    )
    mode = shell["mode"]
    _require(mode in SHELL_MODES, "shell_mode_must_be_designs_or_conditions")
    if mode == "designs":
        rows = tuple(_shell_row(r) for r in shell["inputs"])
        _require(len(rows) == design_inputs, "shell_needs_one_row_per_design_input")
        return {"mode": mode, "inputs": rows}
    _require(
        type(shell["inputs"]) is dict and shell["inputs"],
        "conditions_shell_needs_a_row_per_condition_name",
    )
    named = {str(name): _shell_row(r) for name, r in shell["inputs"].items()}
    _require(
        set(named) <= set(fixed), "conditions_shell_names_must_be_fixed_conditions"
    )
    return {"mode": mode, "inputs": named}


def _shell_json(shell):
    if shell is None:
        return None
    if shell["mode"] == "designs":
        return {"mode": "designs", "inputs": [list(r) for r in shell["inputs"]]}
    return {
        "mode": "conditions",
        "inputs": {name: list(r) for name, r in sorted(shell["inputs"].items())},
    }


def _in_row(x, row):
    lo, hi, ext_lo, ext_hi = row
    tol = 1e-9 * max(1.0, hi - lo)
    return (ext_hi > 0.0 and hi + 0.5 * ext_hi - tol <= x <= hi + ext_hi + tol) or (
        ext_lo > 0.0 and lo - ext_lo - tol <= x <= lo - 0.5 * ext_lo + tol
    )


def conditions_in_ood_shell(fixed, shell):
    """Whether a target's fixed conditions have at least one input in the outer half of its approved extension."""
    return any(_in_row(fixed[name], row) for name, row in shell["inputs"].items())


def in_ood_shell(design, shell):
    """Whether a design has at least one input in the OUTER half of that input's approved extension: beyond the TRAIN
    edge by at least half the extension and at most all of it. An input with no approved extension counts for
    nothing; a point inside the TRAIN box is never in the shell. `shell` is the rows of a "designs" shell.
    """
    return any(_in_row(x, row) for x, row in zip(design, shell, strict=True))


def _is_relative(value):
    return (
        type(value) is dict
        and set(value) == {"relative"}
        and _finite(value["relative"])
        and value["relative"] > 0
    )


def _valid_u(value):
    return _is_relative(value) or (_finite(value) and value >= 0)


def attach_raw(spec, raw_rows):
    """The spec with the runner's raw output rows attached, given in the ORIGINAL pool order (`pool-raw-<tid>.json`):
    each kept point takes the row of its origin. Refused when the count is not the original pool's. The rows are
    custody only: they feed the physics gates and the truths-pass-gates check, never a score or a public field.
    """
    _require(
        len(raw_rows) == spec.pool_size and spec.pool_size > 0,
        "raw_rows_must_match_the_original_pool",
    )
    rows = tuple(tuple(float(v) for v in raw_rows[i]) for i in spec.origin)
    return replace(spec, raw=rows)


def u_value(u, true_value):
    """A U at one row: a number as it is, or {"relative": r} as r x |true_value|."""
    return u["relative"] * abs(true_value) if type(u) is dict else u


class PoolRefused(ValueError):
    """The pool or its policy cannot give a sound grade: the Challenge's material, not a candidate's failure."""


def _require(condition, reason):
    if not condition:
        raise PoolRefused(reason)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class WaveformOutput:
    """A derived output whose value is a waveform, not a number (TE-B 7 Nov): ``valid(value)`` says
    whether a value is one (a prediction that is not is the candidate's invalid answer; a truth that is not refuses the
    pool), and ``error(predicted, true)`` is its registered |error| >= 0, in place of ``abs(predicted - true)``. Its U is
    an absolute number > 0, and it is never an objective or a limit."""

    valid: object
    error: object


#: The registered waveform outputs, by output name (`register_waveform_output`). EMPTY for every registered version, so
#: every check below is then exactly the scalar one.
_WAVEFORMS = {}


def register_waveform_output(name, output):
    """Register one waveform output (add-only: the same registration again is a no-op, a different one refuses)."""
    _require(
        type(name) is str and name and isinstance(output, WaveformOutput),
        "waveform_output_registration_invalid",
    )
    _require(
        _WAVEFORMS.setdefault(name, output) == output,
        "waveform_output_already_registered_differently",
    )


def _value_ok(name, value):
    output = _WAVEFORMS.get(name)
    return _finite(value) if output is None else output.valid(value) is True


def _keep(name, value):
    return float(value) if name not in _WAVEFORMS else tuple(float(v) for v in value)


def difference(name, predicted, true):
    """|predicted - true| of output ``name``: the registered waveform error for a waveform output, else the plain one."""
    output = _WAVEFORMS.get(name)
    if output is None:
        return abs(predicted - true)
    error = output.error(predicted, true)
    _require(_finite(error) and error >= 0, "waveform_error_invalid")
    return float(error)


@dataclass(frozen=True)
class Limit:
    output: str
    kind: (
        str  # "<=" (the output must not exceed bound) or ">=" (must not fall below it)
    )
    bound: float

    def margin(self, value):
        """Positive when the limit is met, by how much."""
        return self.bound - value if self.kind == "<=" else value - self.bound


@dataclass(frozen=True)
class OptimizerPolicy:
    """The query budget B per target (OWNER), the CMA-ES initial step in the unit box, and the population
    (None = the tutorial's 4 + floor(3 ln n))."""

    budget: int
    sigma0: float
    population: int | None
    #: The design rule, for NEW exam versions only (week-1 item: top-k design regret). None is today's single pick, and a
    #: registered version without one is unchanged. ``{"kind": "top_k", "k": k}`` grades the model's k best distinct
    #: feasible-predicted designs together (see `grade_target`); k = 1 is the single pick, bit for bit. k is the owner's and
    #: has no default.
    pick_rule: dict | None = None
    #: How a set's D aggregates its targets, for NEW exam versions only. None is the plain mean of the per-target d (every
    #: registered version). ``"balanced_region_mean"`` is the mean over REGION CLASSES of each class's mean d, so a regime with
    #: few targets (the outer shell, a band edge) cannot be averaged away behind a majority that is near perfect.
    d_aggregate: str | None = None
    #: How a set's A_gen aggregates its targets, for NEW exam versions only. None is the plain mean over the targets with a
    #: reserved slice (every registered version). ``"balanced_region_mean"`` is the mean over the coverage plan's classes of
    #: each class's mean A_gen, so a small class cannot be averaged away. It needs a registered coverage plan.
    #: ``"ood_class_mean"`` (OWNER-ACCURACY-OOD-MIN-01 item 1) is the OUT-OF-RANGE form: A_gen is scored on out-of-range
    #: classes only (a class is out of range when every target in it is an extended, OOD-shell target; a reserved slice on
    #: an in-range target, or a class mixing both, refuses), each class's mean A_gen averaged over the classes, and the
    #: classes with fewer than ``a_gen_min_class_cases`` reserved cases pooled into one ``other_ood`` class.
    a_gen_aggregate: str | None = None
    #: N of OWNER-ACCURACY-OOD-MIN-01 item 1 ("classes with fewer than N cases pool into other OOD"; N is set in the version
    #: plan): an int >= 1, required with ``a_gen_aggregate == "ood_class_mean"`` and None otherwise. A case is one reserved
    #: A_gen point of a target in that class.
    a_gen_min_class_cases: int | None = None
    #: The sha256 (64 hex) of the version's registered coverage-plan class map (`coverage_plan`): the class-map document
    #: the grader reads, as the pool constants name it; None for every registered version. When set, a set is graded only
    #: with that exact map attached.
    coverage_plan_sha256: str | None = None
    #: The sha256 (64 hex) of the coverage plan package's SHA256SUMS file, which must list the class-map document; registered
    #: beside `coverage_plan_sha256` (both or neither). None for every registered version.
    coverage_plan_sums_sha256: str | None = None
    #: The version's registered ADMISSION class vocabulary (X-1, Carbon Validator-C COOL18_CELL_CLASS_RULING b98e6e19):
    #: a tuple of unique class names, read from the version's registration in the pool constants (never typed in the
    #: grader). When set, the coverage plan's classes must be exactly these names (`pool_exam.attach_coverage_plan`)
    #: instead of geometric-v1 names. None (every version that registers none) keeps the geometric-v1 check unchanged.
    #: Needs a registered coverage plan.
    coverage_class_vocabulary: tuple | None = None
    #: The attached class map (`CoveragePlan`, custody material checked against both digests), or None.
    coverage_plan: object = None
    #: Neighbour-task robustness of D, for NEW exam versions only (OWNER-DESIGN-DECISION-FIDELITY-01: V_var, the pick
    #: question re-asked with a Challenge's main limit shifted, dropped when D moved to the pool). None is today's D, bit
    #: for bit, for every registered version. ``{"kind": "limit_shift", "limits": [output, ...], "shifts": [s, ...],
    #: "min_valid": n, "aggregate": "mean"}``: each target is graded again on one VARIANT per (limit, shift), the same
    #: pool designs and truths with that limit's bound x (1 + s) (`attach_variants`), and D(target) is the mean over the
    #: base and its valid variants; with fewer than ``min_valid`` valid variants it is the base D alone (reported).
    #: Optional ``"basis"``: ``"absolute"`` (the default: bound x (1 + s)) or ``"margin_above:<condition>"`` (the margin
    #: over that fixed condition is shifted: c + (bound - c) x (1 + s), e.g. a temperature limit over the inlet). A
    #: refused variant is a reference failure (dropped, counted), never the candidate's. The shifts (the record's
    #: starting value is +-5 %), the limits per Challenge, ``min_valid`` and the weighting are the owner's.
    variant_rule: dict | None = None
    #: The design score's zero, for NEW exam versions only (OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01). None is today's
    #: median feasible pool objective (every registered version, unchanged). ``{"kind": "engineer_shortcut", "budget":
    #: B}``: each target's zero is the objective the version's registered cheap method reached screen-then-verify at budget B
    #: (B exam-rung solves under the equal-wall rule; `build_target`'s ``zero``, from the custody shortcut run). B is NOT ``budget`` (the model's queries; Validator 21:45):
    #: a separate owner value, recorded beside it. B is the owner's, per version, from the
    #: dry-run curve; it has no default.
    d_zero: dict | None = None
    #: Near-limit picks scored by TRUE margin with U (owner option (a2), 4 Nov; Validator 22:01), NEW versions only. None
    #: is today: every pool point within U of a limit is dropped at build (every registered version, unchanged).
    #: ``{"kind": "credit_ramp", "shape": "linear"}`` (`build_target`'s ``near_limit``): those points stay; each truly
    #: feasible point earns credit c = min over limits of min(1, margin / U) (c = 0 when truly infeasible; an exact,
    #: U = 0 output only needs margin >= 0), its value is c x max(0, s - s_low), the reference is the best value, the pick
    #: the best PREDICTED value, and q = value(pick) / value(reference). Inside U is never a clean pass; with every point
    #: clean it is today's q. The ramp shape is the owner's (linear = the starting assumption on his sheet).
    near_limit: dict | None = None


#: The 2-class fallback of a version with ``balanced_region_mean`` D and no registered coverage plan (`region_class`): a
#: target's own kind, never a model's property. A version WITH a coverage plan takes its classes and their order from the
#: plan alone; no class name is typed here for it.
VARIANT_KINDS = ("limit_shift",)
VARIANT_AGGREGATES = ("mean",)
REGION_CLASSES = ("in_train", "extended_shell")
D_AGGREGATES = (None, "balanced_region_mean")
A_GEN_AGGREGATES = (None, "balanced_region_mean", "ood_class_mean")
#: The pooled class of OWNER-ACCURACY-OOD-MIN-01 item 1: out-of-range classes with fewer than N reserved cases.
OTHER_OOD = "other_ood"
#: The engineer's-shortcut zero's kind, and each target's zero status from the custody shortcut run: ``anchored`` (the
#: shortcut's best verified-feasible objective is the zero), ``no_verified_feasible`` (none of its verified designs is
#: feasible) and ``not_screened`` (its method does not predict this target's objective) keep the median zero, recorded.
D_ZERO_KIND = "engineer_shortcut"
NEAR_LIMIT_KINDS = ("credit_ramp",)
NEAR_LIMIT_SHAPES = ("linear",)
ZERO_STATUSES = ("anchored", "no_verified_feasible", "not_screened")
COVERAGE_PLAN_SCHEMA = "carbon.pool.coverage-plan.v1"


@dataclass(frozen=True)
class CoveragePlan:
    """A version's registered class map: target id -> the coverage plan's class name, and the class order.

    Built only by `coverage_plan` from the custody document whose sha256 the pool constants register. The classes are
    the plan's own (never derived from any model output) and their order is the plan's (the report and summation order).
    """

    classes: tuple  # the class names, in the registered order
    targets: tuple  # ((target_id, class name), ...), sorted by target id
    sha256: str  # 64 hex: sha256 of the canonical document

    def class_of(self, target_id):
        """The target's class, or `PoolRefused`: a target missing from the map is never given a default class."""
        for name, region in self.targets:
            if name == target_id:
                return region
        raise PoolRefused("target_not_in_the_coverage_plan")


def _is_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def coverage_plan(document):
    """The `CoveragePlan` of a document ``{"schema": COVERAGE_PLAN_SCHEMA, "classes": [name, ...], "targets": {target_id:
    name}}``, or `PoolRefused`. Every class is named by at least one target and every target's class is listed.
    """
    _require(
        type(document) is dict
        and set(document) == {"schema", "classes", "targets"}
        and document["schema"] == COVERAGE_PLAN_SCHEMA,
        "coverage_plan_malformed",
    )
    classes, targets = document["classes"], document["targets"]
    _require(
        type(classes) is list
        and classes
        and all(type(c) is str and c for c in classes)
        and len(set(classes)) == len(classes),
        "coverage_plan_classes_must_be_unique_names",
    )
    _require(
        type(targets) is dict
        and targets
        and all(type(t) is str and t for t in targets)
        and all(type(c) is str and c in classes for c in targets.values()),
        "coverage_plan_targets_must_name_listed_classes",
    )
    _require(
        set(targets.values()) == set(classes), "coverage_plan_class_without_a_target"
    )
    return CoveragePlan(
        classes=tuple(classes),
        targets=tuple(sorted(targets.items())),
        sha256=hashlib.sha256(coverage_plan_bytes(document)).hexdigest(),
    )


def coverage_plan_bytes(document):
    """The canonical bytes of a class-map document: the file the coverage plan package lists in its SHA256SUMS, so the
    file's sha256 is the document's `CoveragePlan.sha256`."""
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sums_list(sums, sha256):
    """Whether a SHA256SUMS text lists `sha256`. Every non-empty line must be ``<64 hex><space><space or *><path>`` (the
    ``sha256sum`` format), else `PoolRefused`."""
    _require(type(sums) is str and sums, "coverage_plan_sums_malformed")
    listed = set()
    for line in sums.splitlines():
        if not line:
            continue
        _require(
            len(line) > 66
            and _is_sha256(line[:64])
            and line[64] == " "
            and line[65] in " *",
            "coverage_plan_sums_malformed",
        )
        listed.add(line[:64])
    return sha256 in listed


def region_class(spec, plan=None):
    """The region class of a target. With a coverage plan: the plan's class of its target id (a target missing from the plan
    is refused, never defaulted). Without one (the 2-class fallback): ``extended_shell`` for an EXTENDED target (T5/T6, its
    OOD shell), else ``in_train``."""
    if plan is not None:
        return plan.class_of(spec.target_id)
    return "extended_shell" if spec.extended else "in_train"


def class_order(plan):
    """The region classes in their report and summation order: the plan's, or the 2-class fallback's."""
    return REGION_CLASSES if plan is None else plan.classes


def _set_plan(optimizer):
    """The coverage plan a set is graded with: the attached one, or None for a version that registers none. A version that
    registers a plan grades nothing without it (never the 2-class fallback)."""
    _require(
        optimizer.coverage_plan_sha256 is None or optimizer.coverage_plan is not None,
        "coverage_plan_not_attached",
    )
    return optimizer.coverage_plan


def pick_count(optimizer):
    """The number of picks the design rule grades: 1 for no rule, else the rule's k."""
    rule = optimizer.pick_rule
    return 1 if rule is None else rule["k"]


@dataclass(frozen=True)
class HonestyPolicy:
    """s_h (OWNER) and how the per-output U-normalised errors reduce to one number: "max" or "rms"."""

    scale: float
    reduction: str


def _check_policies(optimizer, honesty):
    _require(
        type(optimizer.budget) is int and optimizer.budget >= 1,
        "budget_must_be_a_positive_int",
    )
    _require(
        _finite(optimizer.sigma0) and optimizer.sigma0 > 0, "sigma0_must_be_positive"
    )
    _require(
        optimizer.population is None
        or (type(optimizer.population) is int and optimizer.population >= 2),
        "population_must_be_none_or_at_least_2",
    )
    rule = optimizer.pick_rule
    _require(
        rule is None
        or (
            type(rule) is dict
            and set(rule) == {"kind", "k"}
            and rule["kind"] == "top_k"
            and type(rule["k"]) is int
            and rule["k"] >= 1
        ),
        "pick_rule_must_be_none_or_top_k_with_a_positive_int_k",
    )
    _require(
        optimizer.d_aggregate in D_AGGREGATES,
        "d_aggregate_must_be_none_or_balanced_region_mean",
    )
    _require(
        optimizer.a_gen_aggregate in A_GEN_AGGREGATES,
        "a_gen_aggregate_must_be_none_balanced_region_mean_or_ood_class_mean",
    )
    _require(
        optimizer.coverage_plan_sha256 is None
        or _is_sha256(optimizer.coverage_plan_sha256),
        "coverage_plan_sha256_must_be_64_hex",
    )
    _require(
        optimizer.coverage_plan_sums_sha256 is None
        or _is_sha256(optimizer.coverage_plan_sums_sha256),
        "coverage_plan_sums_sha256_must_be_64_hex",
    )
    _require(
        (optimizer.coverage_plan_sha256 is None)
        == (optimizer.coverage_plan_sums_sha256 is None),
        "coverage_plan_needs_its_map_and_sums_digests",
    )
    vocabulary = optimizer.coverage_class_vocabulary
    _require(
        vocabulary is None
        or (
            type(vocabulary) is tuple
            and vocabulary
            and all(type(c) is str and c for c in vocabulary)
            and len(set(vocabulary)) == len(vocabulary)
        ),
        "coverage_class_vocabulary_must_be_unique_names",
    )
    _require(
        vocabulary is None or optimizer.coverage_plan_sha256 is not None,
        "coverage_class_vocabulary_needs_a_registered_coverage_plan",
    )
    _require(
        optimizer.a_gen_aggregate is None or optimizer.coverage_plan_sha256 is not None,
        "a_gen_aggregate_needs_a_registered_coverage_plan",
    )
    _require(
        _valid_min_class_cases(
            optimizer.a_gen_aggregate, optimizer.a_gen_min_class_cases
        ),
        "a_gen_min_class_cases_must_be_a_positive_int_with_ood_class_mean_only",
    )
    plan = optimizer.coverage_plan
    _require(
        plan is None
        or (
            isinstance(plan, CoveragePlan)
            and plan.sha256 == optimizer.coverage_plan_sha256
        ),
        "coverage_plan_is_not_the_registered_one",
    )
    zero = optimizer.d_zero
    _require(
        zero is None
        or (
            type(zero) is dict
            and set(zero) == {"kind", "budget"}
            and zero["kind"] == D_ZERO_KIND
            and type(zero["budget"]) is int
            and zero["budget"] >= 1
        ),
        "d_zero_must_be_none_or_engineer_shortcut_with_a_positive_int_budget",
    )
    _require(
        optimizer.variant_rule is None or _valid_variant_rule(optimizer.variant_rule),
        VARIANT_RULE_INVALID,
    )
    _require(
        optimizer.near_limit is None or valid_near_limit(optimizer.near_limit),
        NEAR_LIMIT_INVALID,
    )
    # The top-k rule has no near-limit form yet: which credit k picks share is the owner's (fail closed).
    _require(
        optimizer.near_limit is None or pick_count(optimizer) == 1,
        "near_limit_needs_the_single_pick",
    )
    _require(
        _finite(honesty.scale) and honesty.scale > 0, "honesty_scale_must_be_positive"
    )
    _require(
        honesty.reduction in ("max", "rms"), "honesty_reduction_must_be_max_or_rms"
    )


VARIANT_RULE_INVALID = (
    "variant_rule_must_be_none_or_limit_shift_with_limits_shifts_min_valid_and_mean"
)


_VARIANT_KEYS = {"kind", "limits", "shifts", "min_valid", "aggregate"}
MARGIN_ABOVE = "margin_above:"


def _variant_basis(rule):
    """``None`` for an absolute shift, else the fixed condition a ``margin_above:<condition>`` basis measures from."""
    basis = rule.get("basis", "absolute")
    return None if basis == "absolute" else basis[len(MARGIN_ABOVE) :]


def _valid_variant_rule(rule):
    if type(rule) is not dict or not (
        set(rule) == _VARIANT_KEYS or set(rule) == _VARIANT_KEYS | {"basis"}
    ):
        return False
    basis = rule.get("basis", "absolute")
    if not (
        basis == "absolute"
        or (
            type(basis) is str
            and basis.startswith(MARGIN_ABOVE)
            and len(basis) > len(MARGIN_ABOVE)
        )
    ):
        return False
    limits, shifts = rule["limits"], rule["shifts"]
    return bool(
        rule["kind"] in VARIANT_KINDS
        and rule["aggregate"] in VARIANT_AGGREGATES
        and type(limits) in (list, tuple)
        and limits
        and all(type(name) is str and name for name in limits)
        and len(set(limits)) == len(limits)
        and type(shifts) in (list, tuple)
        and shifts
        and all(_finite(x) and x != 0.0 and -1.0 < x < 1.0 for x in shifts)
        and len(set(shifts)) == len(shifts)
        and len({f"{x:+g}" for x in shifts})
        == len(shifts)  # the variant ids stay distinct
        and type(rule["min_valid"]) is int
        and 0 <= rule["min_valid"] <= len(limits) * len(shifts)
    )


def variant_slots(rule):
    """The rule's variants in the one order every custody start/seed list follows: ``(limit output, shift)`` for each
    limit, then each shift."""
    _require(_valid_variant_rule(rule), VARIANT_RULE_INVALID)
    return tuple(
        (name, float(shift)) for name in rule["limits"] for shift in rule["shifts"]
    )


@dataclass(frozen=True)
class TargetSpec:
    """One sealed optimisation problem with its pre-solved pool. Build it with `build_target`."""

    def u_at(self, index, name):
        """The U of output `name` at pool row `index`: the number, or r x |that row's true value|."""
        return u_value(self.u[name], self.truths[index][name])

    target_id: str
    conditions: dict
    outputs: tuple
    objective: str
    sign: (
        float  # +1 maximise, -1 minimise: sign * objective is always "bigger is better"
    )
    limits: tuple
    u: dict
    box: tuple
    designs: tuple  # raw design vectors, one per kept pool point
    norm: tuple  # the same designs in the unit box
    truths: tuple  # true outputs per point
    feasible: tuple  # truly feasible (every margin >= 0; kept points are clear of U)
    queryable: tuple  # indices the optimiser may query (the A_gen slice excluded)
    agen: tuple  # indices reserved for accuracy only
    reference: int  # best feasible queryable point
    s_ref: float
    s_low: float  # the D zero, in sign * objective: the median feasible queryable objective, or the anchored shortcut's s_zero
    start: tuple
    seed: int
    excluded: int  # pool points dropped at build time for a margin within U of a limit
    digest: str
    public: bool  # a PUBLIC practice pool: its per-target values may be shown; a sealed pool's never are
    # The OOD shell of an EXTENDED target (T5/T6): {"mode": "designs" | "conditions", "inputs": ...} with rows
    # (train_lo, train_hi, ext_lo, ext_hi) = the TRAIN edges and the extension AMOUNTS the edge sign-off approved
    # beyond each (non-negative, design units; 0 = none approved). None for a registered-condition target.
    # "designs": every queryable point (the reference included) has an input in the OUTER half of that input's
    # extension, else the target STOPS. "conditions": the fixed conditions are checked once.
    shell: object = None
    # Where each kept point came from in the ORIGINAL pool (the exclusion drops some), and the original size: how the
    # runner's raw outputs per design (same order as the original designs) attach to the kept rows (`attach_raw`).
    origin: tuple = ()
    pool_size: int = 0
    raw: object = (
        None  # the kept rows' raw output rows, once attached (custody only, never in the digest)
    )
    # The neighbour-task variants (`attach_variants`; custody only, never in the digest): None until attached, then a
    # tuple of the valid variant specs, with the refused ones as ``((output, shift, code), ...)``: reference failures.
    variants: object = None
    variant_refusals: tuple = ()
    # The engineer's-shortcut zero of a NEW version's target (`checked_zero`), part of the identity; None = the median.
    zero: object = None
    # The near-limit rule of a NEW version's target (`OptimizerPolicy.near_limit`, part of the identity; None = today's
    # drop), each kept point's TRUE credit (custody) and the reference's value c x (s_ref - s_low).
    near_limit: object = None
    credit: tuple = ()
    v_ref: float | None = None
    # An ACCURACY-ONLY target (`build_accuracy_target`): every case is reserved for accuracy, there is no optimisation
    # problem (no objective, limits, reference, start or seed), so it never enters `grade_set`. False for every other.
    accuracy_only: bool = False
    # An ACCURACY-ONLY target declared out of range with no shell (`build_accuracy_target(extended=True)`): its cases
    # are past TRAIN but outside the OOD shell (Motor 1.8's inner-band H-1 rows, unshelled by a CV ruling: no
    # shell-mode check, the same range as the shelled targets of their class). Part of the identity. False for every other.
    declared_extended: bool = False

    @property
    def extended(self):
        return self.shell is not None or self.declared_extended


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def checked_zero(zero):
    """A target's engineer's-shortcut zero from the custody shortcut run, checked: ``{"kind": "engineer_shortcut", "budget": B,
    "status": one of `ZERO_STATUSES`, "s_zero": the shortcut's objective in the grader's sign x objective (``anchored`` only),
    "record_sha256": the custody run record's sha256, "pool_digest": the digest of THIS pool's body without the zero (the run
    names the pool it ran on; a zero from another pool refuses, Validator 21:30)}``; None for every registered version.
    """
    if zero is None:
        return None
    _require(type(zero) is dict, "zero_must_be_a_dict")
    status = zero.get("status")
    keys = {"kind", "budget", "status", "record_sha256", "pool_digest"} | (
        {"s_zero"} if status == "anchored" else set()
    )
    _require(
        set(zero) == keys
        and zero["kind"] == D_ZERO_KIND
        and type(zero["budget"]) is int
        and zero["budget"] >= 1
        and status in ZERO_STATUSES
        and _is_sha256(zero["record_sha256"])
        and type(zero["pool_digest"]) is str
        and zero["pool_digest"].startswith("sha256:")
        and (status != "anchored" or _finite(zero["s_zero"])),
        "zero_malformed",
    )
    return {k: (float(v) if k == "s_zero" else v) for k, v in zero.items()}


NEAR_LIMIT_INVALID = "near_limit_must_be_none_or_credit_ramp_with_a_registered_shape"


def valid_near_limit(rule):
    return (
        type(rule) is dict
        and set(rule) == {"kind", "shape"}
        and rule["kind"] in NEAR_LIMIT_KINDS
        and rule["shape"] in NEAR_LIMIT_SHAPES
    )


def credit(limits, values, u_of):
    """A point's near-limit credit (`OptimizerPolicy.near_limit`): 0 when any margin is negative, else the smallest
    min(1, margin / U) over the limits (U = ``u_of(output)``; an exactly computed output, U = 0, only needs margin >= 0).
    """
    c = 1.0
    for limit in limits:
        margin = limit.margin(values[limit.output])
        if margin < 0.0:
            return 0.0
        scale = u_of(limit.output)
        if scale > 0.0:
            c = min(c, margin / scale)
    return c


def check_near_limit(spec, optimizer):
    """The version's near-limit rule and its targets' agree: a pool built under another rule never grades silently."""
    _require(
        spec.near_limit == optimizer.near_limit,
        "target_near_limit_differs_from_the_registered_rule",
    )


def check_zero(spec, optimizer):
    """The version's registered zero and its targets' zeros agree: none on both sides (every registered version), or the
    same kind and budget on every target. A pool built under another zero never grades silently.
    """
    if optimizer.d_zero is None:
        _require(spec.zero is None, "target_zero_without_a_registered_d_zero")
        return
    _require(
        spec.zero is not None
        and spec.zero["kind"] == optimizer.d_zero["kind"]
        and spec.zero["budget"] == optimizer.d_zero["budget"],
        "target_zero_differs_from_the_registered_d_zero",
    )


def build_target(
    *,
    target_id,
    conditions,
    outputs,
    objective,
    sense,
    limits,
    u,
    box,
    designs,
    truths,
    agen,
    start,
    seed,
    public=False,
    shell=None,
    zero=None,
    near_limit=None,
):
    """Validate a target's sealed material and derive its reference.

    `agen` is the set of ORIGINAL pool indices reserved for accuracy only (never queried).
    `start` is the optimiser's private starting point in the unit box; `seed` its private seed.
    Pool points whose true margin is within U of any limit are excluded (spec section 1), so every
    kept point is clearly feasible or clearly infeasible."""
    _require(type(target_id) is str and target_id, "target_id_required")
    _require(type(conditions) is dict, "conditions_must_be_a_dict")
    outputs = tuple(outputs)
    _require(
        len(outputs) == len(set(outputs)) and outputs,
        "outputs_must_be_unique_and_non_empty",
    )
    _require(objective in outputs, "objective_must_be_an_output")
    _require(objective not in _WAVEFORMS, "a_waveform_output_is_never_the_objective")
    _require(sense in ("max", "min"), "sense_must_be_max_or_min")
    limits = tuple(limits)
    _require(
        all(
            isinstance(l, Limit)
            and l.kind in ("<=", ">=")
            and l.output in outputs
            and l.output not in _WAVEFORMS
            and _finite(l.bound)
            for l in limits
        ),
        "limits_must_name_outputs_with_a_kind_and_a_finite_bound",
    )
    _require(set(u) == set(outputs), "u_must_cover_exactly_the_outputs")
    # A U is a number >= 0, or {"relative": r} (r > 0): r times the ABSOLUTE true value of that output in that
    # pool row, as the exam applies it (e.g. a hydraulic power, r = 0.03). A relative U is never a scalar.
    # U = 0 marks an output Carbon computes exactly (an analytic quantity such as an energy or a mass formula),
    # never predicted by the model: it is held to equality, not to a tolerance, and does not enter the honesty
    # scale. At least one output must carry a real U or there is nothing for honesty to measure.
    _require(
        all(_valid_u(v) for v in u.values()),
        "u_must_be_non_negative_and_finite_or_relative",
    )
    _require(
        any(_is_relative(v) or v > 0 for v in u.values()),
        "u_needs_one_predicted_output",
    )
    _require(
        all(_finite(u[k]) and u[k] > 0 for k in outputs if k in _WAVEFORMS),
        "a_waveform_output_needs_an_absolute_u_above_zero",
    )
    box = tuple((float(lo), float(hi)) for lo, hi in box)
    _require(
        box
        and all(math.isfinite(lo) and math.isfinite(hi) and hi > lo for lo, hi in box),
        "box_must_be_finite_with_hi_above_lo",
    )
    _require(
        len(designs) == len(truths) and len(designs) >= 2,
        "pool_needs_matching_designs_and_truths",
    )
    for design, truth in zip(designs, truths):
        _require(
            len(design) == len(box) and all(_finite(x) for x in design),
            "design_must_match_the_box_and_be_finite",
        )
        _require(
            type(truth) is dict
            and set(truth) == set(outputs)
            and all(_value_ok(k, v) for k, v in truth.items()),
            "truth_must_give_every_output_finite",
        )
    _require(type(seed) is int, "seed_must_be_an_int")
    _require(
        len(start) == len(box) and all(_finite(x) and 0.0 <= x <= 1.0 for x in start),
        "start_must_be_in_the_unit_box",
    )
    agen = set(agen)
    _require(
        all(type(i) is int and 0 <= i < len(designs) for i in agen),
        "agen_index_out_of_range",
    )
    _require(near_limit is None or valid_near_limit(near_limit), NEAR_LIMIT_INVALID)
    keep, excluded = [], 0
    for index, truth in enumerate(truths):
        if near_limit is None and any(
            abs(limit.margin(truth[limit.output]))
            <= u_value(u[limit.output], truth[limit.output])
            for limit in limits
        ):
            excluded += 1
            continue
        keep.append(index)
    kept_designs = tuple(tuple(float(x) for x in designs[i]) for i in keep)
    kept_truths = tuple({k: _keep(k, v) for k, v in truths[i].items()} for i in keep)
    kept_agen = tuple(n for n, i in enumerate(keep) if i in agen)
    queryable = tuple(n for n, i in enumerate(keep) if i not in agen)
    norm = tuple(
        tuple((x - lo) / (hi - lo) for x, (lo, hi) in zip(design, box))
        for design in kept_designs
    )
    feasible = tuple(
        all(limit.margin(truth[limit.output]) >= 0.0 for limit in limits)
        for truth in kept_truths
    )
    sign = 1.0 if sense == "max" else -1.0
    scores = {n: sign * kept_truths[n][objective] for n in queryable if feasible[n]}
    credits = ()
    if near_limit is not None:
        credits = tuple(
            credit(limits, truth, lambda name, t=truth: u_value(u[name], t[name]))
            for truth in kept_truths
        )
        # s_low is the median over CLEAN feasible points (credit 1), as today's kept set was (Validator 22:01)
        clean = {n: v for n, v in scores.items() if credits[n] == 1.0}
        _require(
            len(clean) >= 2,
            "degenerate_reference_needs_two_clean_feasible_queryable_points",
        )
    _require(
        len(scores) >= 2, "degenerate_reference_needs_two_feasible_queryable_points"
    )
    reference = min(scores, key=lambda n: (-scores[n], n))
    if shell is not None:
        shell = _valid_shell(shell, len(box), conditions.get("fixed", {}))
        if shell["mode"] == "designs":
            _require(
                in_ood_shell(kept_designs[reference], shell["inputs"]),
                "reference_not_in_the_ood_shell",
            )
            # The sampler guarantees it; a point outside means the payload and the grader disagree: STOP.
            _require(
                all(in_ood_shell(kept_designs[n], shell["inputs"]) for n in queryable),
                "queryable_point_outside_the_ood_shell",
            )
        else:
            _require(
                conditions_in_ood_shell(conditions["fixed"], shell),
                "conditions_not_in_the_ood_shell",
            )
    s_ref, s_low = scores[reference], statistics.median(
        (clean if near_limit is not None else scores).values()
    )
    zero = checked_zero(zero)
    if zero is not None and zero["status"] == "anchored":
        # OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01: the shortcut's own objective scores 0. A target the shortcut already
        # solves leaves no design value to measure: refused here (reference failure, never a candidate's), and the
        # sampler redraws it (the owner's condition).
        _require(s_ref > zero["s_zero"], "degenerate_shortcut_reaches_the_reference")
        s_low = zero["s_zero"]
    else:
        _require(
            s_ref > s_low, "degenerate_reference_best_feasible_must_beat_the_median"
        )
    v_ref = None
    if near_limit is not None:
        # the reference is the best VALUE: credit x the objective's gain over the zero (a near-limit optimum wins only
        # when its margin earns it)
        values = {n: credits[n] * max(0.0, scores[n] - s_low) for n in scores}
        reference = min(values, key=lambda n: (-values[n], n))
        s_ref, v_ref = scores[reference], values[reference]
        _require(v_ref > 0.0, "degenerate_reference_no_credited_gain_over_the_zero")
        if shell is not None and shell["mode"] == "designs":
            _require(
                in_ood_shell(kept_designs[reference], shell["inputs"]),
                "reference_not_in_the_ood_shell",
            )
    body = {
        "target_id": target_id,
        "conditions": conditions,
        "outputs": list(outputs),
        "objective": objective,
        "sense": sense,
        "limits": [[l.output, l.kind, l.bound] for l in limits],
        "u": u,
        "box": [list(b) for b in box],
        "designs": [list(d) for d in kept_designs],
        "truths": list(kept_truths),
        "agen": list(kept_agen),
        "start": list(start),
        "seed": seed,
        "public": public,  # visibility is part of the identity: a sealed pool cannot be relabelled public
        "shell": _shell_json(shell),
    }
    if near_limit is not None:
        # only a new version's rule enters the identity: a registered version's digest is unchanged
        body["near_limit"] = dict(near_limit)
    if zero is not None:
        # the zero's run names THIS pool (the body without the zero): a zero from another pool refuses (Validator
        # 21:30). Only a new version's zero enters the identity: a registered version's digest is unchanged.
        _require(zero["pool_digest"] == _digest(body), "zero_is_not_this_pools")
        body["zero"] = zero
    _require(type(public) is bool, "public_must_be_a_bool")
    return TargetSpec(
        target_id=target_id,
        conditions=conditions,
        outputs=outputs,
        objective=objective,
        sign=sign,
        limits=limits,
        u=dict(u),
        box=box,
        designs=kept_designs,
        norm=norm,
        truths=kept_truths,
        feasible=feasible,
        queryable=queryable,
        agen=kept_agen,
        reference=reference,
        s_ref=s_ref,
        s_low=s_low,
        start=tuple(float(x) for x in start),
        seed=seed,
        excluded=excluded,
        digest=_digest(body),
        public=public,
        shell=shell,
        origin=tuple(keep),
        pool_size=len(designs),
        zero=zero,
        near_limit=None if near_limit is None else dict(near_limit),
        credit=credits,
        v_ref=v_ref,
    )


#: The identity marker of an accuracy-only target (`build_accuracy_target`).
ACCURACY_ONLY = "accuracy_only"
#: The optimisation fields an accuracy-only target never carries: present (in a pool source or a pool document) = refused.
ACCURACY_ONLY_ABSENT = frozenset(
    {
        "objective",
        "sense",
        "limits",
        "start",
        "seed",
        "zero",
        "near_limit",
        "variants",
        "excluded",
    }
)


def build_accuracy_target(
    *,
    target_id,
    conditions,
    outputs,
    u,
    box,
    designs,
    truths,
    public=False,
    shell=None,
    extended=False,
):
    """An ACCURACY-ONLY target (R1, a version whose D is the sealed menu and whose A is the physics score): its cases are
    scored for accuracy only, so EVERY design is in the reserved slice (``agen``) and none is queryable. There is no
    optimisation problem: no objective, sense, limits, reference, median, start, seed, zero, near-limit rule or variants,
    and no within-U exclusion (with no limits every case is kept). It needs >= 1 case. The box is required (it checks
    the designs' shape). An EXTENDED target (a shell) must have EVERY case in its out-of-range shell (``designs`` mode)
    or its fixed conditions in it (``conditions`` mode). Its identity body is marked ``accuracy_only``, so its digest
    never equals a multi-design target's. `grade_set` refuses it: it contributes accuracy only, never a pick D.
    """
    _require(type(target_id) is str and target_id, "target_id_required")
    _require(type(conditions) is dict, "conditions_must_be_a_dict")
    outputs = tuple(outputs)
    _require(
        len(outputs) == len(set(outputs)) and outputs,
        "outputs_must_be_unique_and_non_empty",
    )
    _require(set(u) == set(outputs), "u_must_cover_exactly_the_outputs")
    _require(
        all(_valid_u(v) for v in u.values()),
        "u_must_be_non_negative_and_finite_or_relative",
    )
    _require(
        any(_is_relative(v) or v > 0 for v in u.values()),
        "u_needs_one_predicted_output",
    )
    _require(
        all(_finite(u[k]) and u[k] > 0 for k in outputs if k in _WAVEFORMS),
        "a_waveform_output_needs_an_absolute_u_above_zero",
    )
    box = tuple((float(lo), float(hi)) for lo, hi in box)
    _require(
        box
        and all(math.isfinite(lo) and math.isfinite(hi) and hi > lo for lo, hi in box),
        "box_must_be_finite_with_hi_above_lo",
    )
    _require(
        len(designs) == len(truths) and len(designs) >= 1,
        "accuracy_only_target_needs_matching_designs_and_truths",
    )
    for design, truth in zip(designs, truths):
        _require(
            len(design) == len(box) and all(_finite(x) for x in design),
            "design_must_match_the_box_and_be_finite",
        )
        _require(
            type(truth) is dict
            and set(truth) == set(outputs)
            and all(_value_ok(k, v) for k, v in truth.items()),
            "truth_must_give_every_output_finite",
        )
    _require(type(public) is bool, "public_must_be_a_bool")
    # ``extended=True`` declares an UNSHELLED target out of range (its class's range, as the physics score reads it);
    # a shelled target is extended already, so the flag never rides with a shell (one form only)
    _require(type(extended) is bool, "extended_must_be_a_bool")
    _require(
        not (extended and shell is not None), "a_shelled_target_is_already_extended"
    )
    # its cases are sealed scored cases: never a public practice pool (Validator-2B N-1, fail closed)
    _require(public is False, "accuracy_only_target_is_never_public")
    kept_designs = tuple(tuple(float(x) for x in design) for design in designs)
    kept_truths = tuple({k: _keep(k, v) for k, v in truth.items()} for truth in truths)
    if shell is not None:
        shell = _valid_shell(shell, len(box), conditions.get("fixed", {}))
        if shell["mode"] == "designs":
            # every case, not only a queryable one: an accuracy-only target's cases are all scored
            _require(
                all(in_ood_shell(design, shell["inputs"]) for design in kept_designs),
                "accuracy_case_outside_the_ood_shell",
            )
        else:
            _require(
                conditions_in_ood_shell(conditions["fixed"], shell),
                "conditions_not_in_the_ood_shell",
            )
    body = {
        ACCURACY_ONLY: True,
        "target_id": target_id,
        "conditions": conditions,
        "outputs": list(outputs),
        "u": u,
        "box": [list(b) for b in box],
        "designs": [list(d) for d in kept_designs],
        "truths": list(kept_truths),
        "public": public,
        "shell": _shell_json(shell),
        # only when declared: every target without the flag keeps its identity byte for byte
        **({"extended": True} if extended else {}),
    }
    size = len(kept_designs)
    return TargetSpec(
        target_id=target_id,
        conditions=conditions,
        outputs=outputs,
        objective=None,
        sign=0.0,
        limits=(),
        u=dict(u),
        box=box,
        designs=kept_designs,
        norm=tuple(
            tuple((x - lo) / (hi - lo) for x, (lo, hi) in zip(design, box))
            for design in kept_designs
        ),
        truths=kept_truths,
        feasible=(),
        queryable=(),
        agen=tuple(range(size)),
        reference=None,
        s_ref=None,
        s_low=None,
        start=(),
        seed=None,
        excluded=0,
        digest=_digest(body),
        public=public,
        shell=shell,
        origin=tuple(range(size)),
        pool_size=size,
        accuracy_only=True,
        declared_extended=extended,
    )


def attach_variants(spec, rule, starts):
    """``spec`` with its neighbour-task variants built (custody; `OptimizerPolicy.variant_rule`).

    Each slot of `variant_slots` is the base target asked again on the SAME kept pool designs and truths, so the exam's
    one table of model answers already covers it (no new row, no new solve), with that limit's bound x (1 + shift).
    `build_target` re-derives the within-U exclusion, the reference and the median, and refuses a degenerate question.
    ``starts`` gives each slot its own private ``{"start": [...], "seed": int}``, derived in custody like a target's.

    A slot is REFUSED (dropped and counted, a reference failure, never scored, never refilled) when the target has no such
    limit, its bound (or its margin over the basis condition) is 0 so a relative shift moves nothing, the basis condition
    is not one of the target's fixed conditions, `build_target` refuses it, or no queryable point stays truly infeasible
    (the shifted question is no longer a choice)."""
    _require(not spec.accuracy_only, "accuracy_only_target_has_no_variants")
    slots = variant_slots(rule)
    over = _variant_basis(rule)
    fixed = spec.conditions.get("fixed")
    origin = 0.0 if over is None else (fixed.get(over) if type(fixed) is dict else None)
    _require(
        type(starts) in (list, tuple) and len(starts) == len(slots),
        "variant_starts_must_give_one_start_and_seed_per_slot",
    )
    variants, refusals = [], []
    for (name, shift), slot in zip(slots, starts, strict=True):
        # A base with an engineer's-shortcut zero needs each slot's own zero (Validator 21:40 (3)): the same shortcut rows
        # re-ranked under the shifted bound, in custody; a base without one takes none.
        _require(
            type(slot) is dict
            and set(slot) == ({"start", "seed"} | ({"zero"} if spec.zero else set())),
            "variant_start_must_be_a_start_and_a_seed",
        )
        # Bad sealed material is the exam's error, never a quiet reference failure that turns the rule off.
        _require(
            type(slot["seed"]) is int
            and type(slot["start"]) in (list, tuple)
            and len(slot["start"]) == len(spec.box)
            and all(_finite(x) and 0.0 <= x <= 1.0 for x in slot["start"]),
            "variant_start_must_be_in_the_unit_box_with_an_int_seed",
        )
        matching = [n for n, limit in enumerate(spec.limits) if limit.output == name]
        if not matching:
            refusals.append((name, shift, "variant_limit_not_on_target"))
            continue
        # A band (two limits on one output) needs the owner to say which bound moves and which way: refuse the rule.
        _require(len(matching) == 1, "variant_limit_is_a_band_name_the_bound")
        if not _finite(origin):
            refusals.append((name, shift, "variant_basis_not_a_fixed_condition"))
            continue
        if any(spec.limits[n].bound - origin == 0.0 for n in matching):
            refusals.append((name, shift, "variant_shift_moves_nothing"))
            continue
        limits = tuple(
            (
                replace(limit, bound=origin + (limit.bound - origin) * (1.0 + shift))
                if n in matching
                else limit
            )
            for n, limit in enumerate(spec.limits)
        )
        question = {
            "target_id": f"{spec.target_id}~{name}{shift:+g}",
            "conditions": spec.conditions,
            "outputs": spec.outputs,
            "objective": spec.objective,
            "sense": "max" if spec.sign > 0 else "min",
            "limits": limits,
            "u": spec.u,
            "box": spec.box,
            "designs": spec.designs,
            "truths": spec.truths,
            "agen": spec.agen,
            "start": slot["start"],
            "seed": slot["seed"],
            "public": spec.public,
            "shell": spec.shell,
            "near_limit": spec.near_limit,
        }
        try:
            variant = build_target(**question)
        except PoolRefused as refused:
            refusals.append((name, shift, str(refused)))
            continue
        if spec.zero is not None:
            # the slot's zero is sealed material: malformed, another pool's, or a status the base forbids refuses the EXAM
            zero = checked_zero(slot["zero"])
            _require(
                zero["kind"] == spec.zero["kind"]
                and zero["budget"] == spec.zero["budget"],
                "variant_zero_differs_from_its_targets",
            )
            _require(
                zero["pool_digest"] == variant.digest,
                "variant_zero_is_not_this_variants",
            )
            _require(
                spec.zero["status"] != "not_screened"
                or zero["status"] == "not_screened",
                "variant_zero_must_be_not_screened_like_its_target",
            )
            try:
                variant = build_target(**question, zero=zero)
            except PoolRefused as refused:
                # only the shortcut already solving the shifted question drops the slot (a reference failure, counted)
                _require(
                    str(refused) == "degenerate_shortcut_reaches_the_reference",
                    str(refused),
                )
                refusals.append((name, shift, str(refused)))
                continue
        if not any(not variant.feasible[n] for n in variant.queryable):
            refusals.append((name, shift, "variant_pool_has_no_infeasible_point"))
            continue
        variants.append(variant)
    return replace(spec, variants=tuple(variants), variant_refusals=tuple(refusals))


def _memoized(predict):
    """``predict`` with one answer per (conditions, design): a model's prediction at a pool point does not depend on the
    question asked about it, so the base and every variant share it (variants cost optimiser steps, not model calls).
    A malformed batch is passed through unchanged, for the grader to refuse as without the cache.
    """
    memo = {}

    def cached(conditions, designs):
        key = json.dumps(conditions, sort_keys=True, separators=(",", ":"))
        missing = [d for d in designs if (key, tuple(d)) not in memo]
        if missing:
            batch = predict(conditions, [list(d) for d in missing])
            if type(batch) is not list or len(batch) != len(missing):
                return batch
            for design, out in zip(missing, batch, strict=True):
                memo[(key, tuple(design))] = out
        answers = [memo[(key, tuple(d))] for d in designs]
        return [dict(a) if type(a) is dict else a for a in answers]

    return cached


@dataclass(frozen=True)
class TargetGrade:
    """Custody-only: never disclosed outside `SetGrade.public()`."""

    target_id: str
    digest: str
    d: float
    q: float
    h: float
    e: float
    feasible: bool
    pick: int | None
    queries: int
    reason: str
    reached_reference: bool
    #: Top-k only (custody): the k picks as ``(index, q_i, h_i)`` in the model's own rank order, the missing slots
    #: ``(None, 0.0, 0.0)``. Empty for the single pick.
    picks: tuple = ()
    #: With a variant rule (custody): the base target's own d (``d`` is then the aggregate), each graded variant as
    #: ``(variant id, d, reason)``, the count of refused variants (reference failures), and whether too few were valid,
    #: so that ``d`` is the base alone.
    base_d: float | None = None
    variants: tuple = ()
    variant_refusals: int = 0
    variant_fallback: bool = False


def graded_answer(prediction, outputs):
    """The prediction as a target grades it, or None when it is not a valid answer: a dict giving exactly ``outputs``,
    each finite (a waveform output: valid). A prediction may also carry REGISTERED waveform outputs another target grades
    (a version whose derive gives every target the same keys); they are dropped here. With no waveform output registered
    this is exactly the scalar check (the same dict, or None)."""
    if type(prediction) is not dict or not set(outputs) <= set(prediction):
        return None
    extra = set(prediction) - set(outputs)
    if extra - set(_WAVEFORMS):
        return None
    graded = {k: prediction[k] for k in outputs} if extra else prediction
    return graded if all(_value_ok(k, v) for k, v in graded.items()) else None


def _valid_prediction(prediction, outputs):
    return graded_answer(prediction, outputs) is not None


def _nearest(point, norm, candidates, taken):
    best, best_distance = None, None
    for index in candidates:
        if index in taken:
            continue
        distance = sum((a - b) ** 2 for a, b in zip(point, norm[index]))
        if best is None or distance < best_distance:
            best, best_distance = index, distance
    return best


def grade_target(spec, predict, optimizer, honesty):
    """Grade one target. `predict(conditions, designs)` returns one dict of outputs per design, in order. With a variant
    rule, D(target) is the mean over the base and its valid neighbour-task variants (`OptimizerPolicy.variant_rule`).
    """
    _check_policies(optimizer, honesty)
    check_zero(spec, optimizer)
    check_near_limit(spec, optimizer)
    rule = optimizer.variant_rule
    if rule is None:
        return _grade_one(spec, predict, optimizer, honesty)
    _require(spec.variants is not None, "variants_not_attached")
    predict = _memoized(predict)
    base = _grade_one(spec, predict, optimizer, honesty)
    for variant in spec.variants:
        check_near_limit(variant, optimizer)
        check_zero(
            variant, optimizer
        )  # each variant carries its own zero exactly when the version registers one
    graded = [
        (v.target_id, _grade_one(v, predict, optimizer, honesty)) for v in spec.variants
    ]
    fallback = not graded or len(graded) < rule["min_valid"]
    # A malformed answer zeroes the target, as it does without the rule: averaging never makes up for it.
    invalid = any(
        g.reason == "prediction_invalid" for g in (base, *(g for _v, g in graded))
    )
    if invalid:
        d = 0.0
    elif fallback:
        d = base.d
    else:
        d = statistics.fmean([base.d, *(g.d for _v, g in graded)])
    return replace(
        base,
        d=d,
        reason="prediction_invalid" if invalid else base.reason,
        base_d=base.d,
        variants=tuple((v, g.d, g.reason) for v, g in graded),
        variant_refusals=len(spec.variant_refusals),
        variant_fallback=fallback,
    )


def _grade_one(spec, predict, optimizer, honesty):
    """One question's grade (a target, or one of its variants): the single pick or the top-k rule."""
    taken = set()
    predictions = {}
    es = CmaEs(spec.start, optimizer.sigma0, spec.seed, optimizer.population)

    def refused(code):
        return TargetGrade(
            spec.target_id,
            spec.digest,
            0.0,
            0.0,
            0.0,
            math.inf,
            False,
            None,
            len(predictions),
            code,
            False,
        )

    def key(index):
        prediction = predictions[index]
        violation = exact = 0.0
        for limit in spec.limits:
            margin = limit.margin(prediction[limit.output])
            if margin < 0.0:
                scale = spec.u_at(index, limit.output)
                if scale > 0.0:
                    violation += -margin / scale
                else:
                    exact += (
                        -margin
                    )  # an exactly computed quantity: its raw excess ranks first
        loss = -spec.sign * prediction[spec.objective]
        if violation == 0.0 and exact == 0.0:
            return (0, loss)
        return (1, exact, violation, loss)

    while len(predictions) < optimizer.budget and len(taken) < len(spec.queryable):
        samples = es.ask()
        chosen = []
        for sample in samples:
            if len(predictions) + len(chosen) >= optimizer.budget:
                break
            point = [min(1.0, max(0.0, x)) for x in sample]
            index = _nearest(point, spec.norm, spec.queryable, taken)
            if index is None:
                break
            taken.add(index)
            chosen.append(index)
        if not chosen:
            break
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in chosen])
        if type(batch) is not list or len(batch) != len(chosen):
            return refused("prediction_invalid")
        for index, prediction in zip(chosen, batch):
            graded = graded_answer(prediction, spec.outputs)
            if graded is None:
                return refused("prediction_invalid")
            predictions[index] = {k: _keep(k, v) for k, v in graded.items()}
        if len(chosen) < len(samples):
            break  # the budget or the pool ended mid-generation: nothing left to adapt to
        es.tell([key(i) for i in chosen])
    feasible_predicted = [i for i in predictions if key(i)[0] == 0]
    if not feasible_predicted:
        return refused("no_predicted_feasible_pick")
    if pick_count(optimizer) > 1:
        return _top_k_grade(
            spec, predictions, feasible_predicted, key, optimizer, honesty
        )
    if spec.near_limit is None:
        pick = min(feasible_predicted, key=lambda i: (key(i), i))
    else:
        # the same credit on the model's own predictions (Validator 22:01): the best PREDICTED value, then today's order
        def predicted_value(i):
            c = credit(spec.limits, predictions[i], lambda name: spec.u_at(i, name))
            gain = spec.sign * predictions[i][spec.objective] - spec.s_low
            return c * max(0.0, gain)

        pick = min(feasible_predicted, key=lambda i: (-predicted_value(i), key(i), i))
    queries = len(predictions)
    if not spec.feasible[pick]:
        return TargetGrade(
            spec.target_id,
            spec.digest,
            0.0,
            0.0,
            0.0,
            _error(spec, pick, predictions[pick], honesty),
            False,
            pick,
            queries,
            "pick_infeasible",
            False,
        )
    s_pick = spec.sign * spec.truths[pick][spec.objective]
    if spec.near_limit is None:
        q = min(1.0, max(0.0, (s_pick - spec.s_low) / (spec.s_ref - spec.s_low)))
        reached = s_pick >= spec.s_ref
    else:
        value = spec.credit[pick] * max(0.0, s_pick - spec.s_low)
        q = min(1.0, value / spec.v_ref)
        reached = value >= spec.v_ref
    e = _error(spec, pick, predictions[pick], honesty)
    h = math.exp(-e / honesty.scale)
    return TargetGrade(
        spec.target_id,
        spec.digest,
        q * h,
        q,
        h,
        e,
        True,
        pick,
        queries,
        "graded",
        reached,
    )


def _top_k_grade(spec, predictions, feasible_predicted, key, optimizer, honesty):
    """The top-k design rule. The model's optimiser returns its k best DISTINCT feasible-predicted designs, ranked by its
    own predicted objective (the same ordering as the single pick). Then

    - q = the verified quality of the BEST pool truth among the k (an infeasible truth contributes 0 for ranking);
    - the honesty factor h = the mean over the k picks of exp(-e_i / s_h), with a missing slot (fewer than k feasible-
      predicted designs) counted as infeasible: q contribution 0 and h_i = 0 in the mean;
    - d = q * h.

    A wrong prediction among the k lowers h; a lucky single pick no longer carries the target alone.
    """
    k = pick_count(optimizer)
    ranked = sorted(feasible_predicted, key=lambda i: (key(i), i))[:k]
    queries = len(predictions)
    picks, qualities, factors, errors = [], [], [], []
    for index in ranked:
        e_i = _error(spec, index, predictions[index], honesty)
        h_i = math.exp(-e_i / honesty.scale)
        if spec.feasible[index]:
            s_i = spec.sign * spec.truths[index][spec.objective]
            q_i = min(1.0, max(0.0, (s_i - spec.s_low) / (spec.s_ref - spec.s_low)))
        else:
            q_i = 0.0
        picks.append((index, q_i, h_i))
        qualities.append(q_i)
        factors.append(h_i)
        errors.append(e_i)
    picks += [(None, 0.0, 0.0)] * (k - len(ranked))
    factors += [0.0] * (k - len(ranked))
    best = max(range(len(ranked)), key=lambda n: (qualities[n], -n))
    q = qualities[best]
    h = statistics.fmean(factors)
    best_index = ranked[best]
    if q == 0.0 and not any(spec.feasible[i] for i in ranked):
        return TargetGrade(
            spec.target_id,
            spec.digest,
            0.0,
            0.0,
            0.0,
            errors[best],
            False,
            best_index,
            queries,
            "pick_infeasible",
            False,
            tuple(picks),
        )
    s_best = spec.sign * spec.truths[best_index][spec.objective]
    return TargetGrade(
        spec.target_id,
        spec.digest,
        q * h,
        q,
        h,
        errors[best],
        True,
        best_index,
        queries,
        "graded",
        s_best >= spec.s_ref,
        tuple(picks),
    )


def _error(spec, index, prediction, honesty):
    ratios = []
    for k in spec.outputs:
        error = difference(k, prediction[k], spec.truths[index][k])
        scale = spec.u_at(index, k)
        if scale > 0.0:
            ratios.append(error / scale)
        elif not math.isclose(
            prediction[k], spec.truths[index][k], rel_tol=1e-9, abs_tol=1e-12
        ):
            return (
                math.inf
            )  # an exact output that does not match is a wiring fault: honesty 0
    if honesty.reduction == "max":
        return max(ratios)
    return math.sqrt(sum(r * r for r in ratios) / len(ratios))


@dataclass(frozen=True)
class SetGrade:
    d: float
    targets: tuple  # custody only
    #: ``((region class, mean d), ...)`` for a balanced set (custody; the per-region report), else empty.
    regions: tuple = ()

    def public(self):
        """All that may leave custody: the set's D and the closed reason codes seen. Never a pick, a
        per-target value, a pool point or a query."""
        return {
            "d": self.d,
            "reasons": sorted(
                (
                    {t.reason for t in self.targets}
                    | {r for t in self.targets for _v, _d, r in t.variants}
                )
                - {"graded"}
            ),
        }


def grade_set(specs, predict, optimizer, honesty):
    _require(len(specs) >= 1, "set_needs_targets")
    # an accuracy-only target has no optimisation problem: it is never asked for a pick D (fail closed)
    _require(
        not any(getattr(s, "accuracy_only", False) for s in specs),
        "accuracy_only_target_has_no_optimizer_pick",
    )
    _require(
        len({s.target_id for s in specs}) == len(specs), "target_ids_must_be_unique"
    )
    _check_policies(optimizer, honesty)
    plan = _set_plan(optimizer)
    # Every target's class first, so a target missing from the plan, or a set missing a registered class, refuses the set
    # before anything is graded.
    classes = _plan_classes(specs, plan)
    grades = tuple(grade_target(spec, predict, optimizer, honesty) for spec in specs)
    if optimizer.d_aggregate is None:
        return SetGrade(statistics.fmean(g.d for g in grades), grades)
    if classes is None:
        classes = tuple(region_class(spec) for spec in specs)
    regions = region_means(classes, [g.d for g in grades], class_order(plan))
    return SetGrade(statistics.fmean(d for _name, d in regions), grades, regions)


def _plan_classes(specs, plan):
    """Each target's class under `plan` (None without one). On the multi-class path a set must hold every registered class:
    a missing class is refused, never skipped (the 2-class fallback keeps its skip)."""
    if plan is None:
        return None
    classes = tuple(region_class(spec, plan) for spec in specs)
    _require(set(classes) == set(plan.classes), "set_missing_a_registered_class")
    return classes


def region_means(classes, values, order):
    """``((class, mean value), ...)`` in ``order``, over the classes that have a value."""
    by_region = {}
    for name, value in zip(classes, values, strict=True):
        by_region.setdefault(name, []).append(value)
    return tuple(
        (name, statistics.fmean(by_region[name])) for name in order if name in by_region
    )


def _valid_min_class_cases(aggregate, n):
    if aggregate != "ood_class_mean":
        return n is None
    return type(n) is int and n >= 1


def agen_buckets(specs, plan, min_class_cases):
    """The out-of-range A_gen classes of a set (``a_gen_aggregate == "ood_class_mean"``): ``(bucket per target or None,
    bucket order)``. A target's bucket is its plan class, or `OTHER_OOD` when that class holds fewer than
    ``min_class_cases`` reserved cases; None for a target without a slice. The order is the plan's out-of-range classes
    that keep their own bucket, then `OTHER_OOD`.

    Refused: an in-range target holding a reserved slice (A_gen is out of range only: min(A, A_gen) would otherwise
    compare in-range with a mix), a class mixing in-range and out-of-range targets, a plan class named `OTHER_OOD`, and
    a set with no out-of-range case at all, and a pooled `OTHER_OOD` class that still holds fewer than N cases.
    """
    _require(
        isinstance(plan, CoveragePlan),
        "a_gen_aggregate_needs_a_registered_coverage_plan",
    )
    _require(
        _valid_min_class_cases("ood_class_mean", min_class_cases),
        "a_gen_min_class_cases_must_be_a_positive_int_with_ood_class_mean_only",
    )
    _require(OTHER_OOD not in plan.classes, "coverage_plan_class_named_other_ood")
    classes = _plan_classes(specs, plan)
    kinds, cases = {}, {}
    for name, spec in zip(classes, specs, strict=True):
        kinds.setdefault(name, set()).add(spec.extended)
        cases[name] = cases.get(name, 0) + len(spec.agen)
        _require(spec.extended or not spec.agen, "a_gen_slice_on_an_in_range_target")
    _require(
        all(len(kind) == 1 for kind in kinds.values()),
        "a_gen_class_mixes_in_range_and_out_of_range_targets",
    )
    _require(any(cases.values()), "a_gen_has_no_out_of_range_case")
    own = tuple(
        name
        for name in plan.classes
        if kinds[name] == {True} and cases[name] >= min_class_cases
    )
    buckets = tuple(
        None if not spec.agen else (name if name in own else OTHER_OOD)
        for name, spec in zip(classes, specs, strict=True)
    )
    order = own + ((OTHER_OOD,) if OTHER_OOD in buckets else ())
    # The pooled class must itself reach N (Validator 4 Nov 21:59): the fix is the draw (more cases), never a weight.
    pooled = sum(
        len(s.agen) for s, b in zip(specs, buckets, strict=True) if b == OTHER_OOD
    )
    _require(
        OTHER_OOD not in order or pooled >= min_class_cases,
        "a_gen_other_ood_below_n_cases",
    )
    return buckets, order


def _target_agen(spec, predict, scales):
    """One target's A_gen on its reserved slice (None without one)."""
    if not spec.agen:
        return None
    _require(
        set(scales) >= set(spec.outputs)
        and all(_finite(scales[k]) and scales[k] > 0 for k in spec.outputs),
        "agen_scales_must_cover_the_outputs",
    )
    batch = predict(spec.conditions, [list(spec.designs[i]) for i in spec.agen])
    _require(
        type(batch) is list and len(batch) == len(spec.agen),
        "agen_prediction_invalid",
    )
    atoms = []
    for index, prediction in zip(spec.agen, batch):
        _require(_valid_prediction(prediction, spec.outputs), "agen_prediction_invalid")
        atoms += [
            benefit(difference(k, prediction[k], spec.truths[index][k]) / scales[k])
            for k in spec.outputs
        ]
    return statistics.fmean(atoms)


def agen_class_report(specs, predict, reference_predict, scales, optimizer):
    """CUSTODY report of OWNER-ACCURACY-OOD-MIN-01 item 4 (per-class floors REPORTED against the TRAIN-kernel; a hard
    floor is a later owner pick): for each out-of-range A_gen class of an ``ood_class_mean`` version, in the grade's
    order, ``{"class", "members" (the plan classes pooled into it), "cases", "a_gen", "reference_a_gen", "gap"}``, where
    ``reference_predict`` is the TRAIN-kernel's predictor on the same set. Report only: nothing here enters a grade.
    It names classes, so it stays in custody."""
    _check_policies_a_gen_report(optimizer)
    plan = optimizer.coverage_plan
    buckets, order = agen_buckets(specs, plan, optimizer.a_gen_min_class_cases)
    classes = _plan_classes(specs, plan)
    rows = []
    for bucket in order:
        members = [n for n, b in enumerate(buckets) if b == bucket]
        own = [_target_agen(specs[n], predict, scales) for n in members]
        ref = [_target_agen(specs[n], reference_predict, scales) for n in members]
        a_gen, reference = statistics.fmean(own), statistics.fmean(ref)
        rows.append(
            {
                "class": bucket,
                "members": sorted({classes[n] for n in members}),
                "cases": sum(len(specs[n].agen) for n in members),
                "a_gen": a_gen,
                "reference_a_gen": reference,
                "gap": a_gen - reference,
            }
        )
    return rows


def _check_policies_a_gen_report(optimizer):
    _require(
        optimizer.a_gen_aggregate == "ood_class_mean",
        "a_gen_class_report_needs_ood_class_mean",
    )
    _require(
        isinstance(optimizer.coverage_plan, CoveragePlan),
        "a_gen_aggregate_needs_a_registered_coverage_plan",
    )


def agen_accuracy(
    specs, predict, scales, *, aggregate=None, plan=None, min_class_cases=None
):
    """A_gen: accuracy on the reserved slice, atom form benefit(|error| / scale) = 1 / (1 + loss), the common
    benefit of `design_fidelity`, averaged over outputs, points and targets. `scales` is {output: scale} and
    required (OWNER). None when no target has a slice. The slice is never queried by the optimiser.

    `aggregate` (a NEW version's registered ``a_gen_aggregate``) None is the plain mean over the targets with a slice
    (every registered version). ``"balanced_region_mean"`` is the mean over `plan`'s classes (in the plan's order) of each
    class's mean target A_gen. It needs the registered `plan`. A target missing from the plan, a set missing a registered
    class, or (balanced) a class with no target holding a reserved slice is refused, never defaulted or skipped.
    ``"ood_class_mean"`` is the out-of-range form (`agen_buckets`, with ``min_class_cases`` = the registered N): the mean
    over the out-of-range classes, the small ones pooled, of each class's mean target A_gen.
    """
    _require(
        aggregate in A_GEN_AGGREGATES,
        "a_gen_aggregate_must_be_none_balanced_region_mean_or_ood_class_mean",
    )
    _require(
        aggregate is None or isinstance(plan, CoveragePlan),
        "a_gen_aggregate_needs_a_registered_coverage_plan",
    )
    if aggregate == "ood_class_mean":
        buckets, order = agen_buckets(specs, plan, min_class_cases)
        owned = [n for n, b in enumerate(buckets) if b is not None]
        values = [_target_agen(specs[n], predict, scales) for n in owned]
        regions = region_means([buckets[n] for n in owned], values, order)
        return statistics.fmean(value for _name, value in regions)
    _require(
        min_class_cases is None,
        "a_gen_min_class_cases_must_be_a_positive_int_with_ood_class_mean_only",
    )
    classes = _plan_classes(specs, plan)
    if aggregate is not None:
        _require(
            {c for c, spec in zip(classes, specs, strict=True) if spec.agen}
            == set(plan.classes),
            "a_gen_class_without_a_reserved_slice",
        )
    values, owners = [], []
    for position, spec in enumerate(specs):
        if not spec.agen:
            continue
        values.append(_target_agen(spec, predict, scales))
        owners.append(position)
    if not values:
        return None
    if aggregate is None:
        return statistics.fmean(values)
    regions = region_means([classes[i] for i in owners], values, plan.classes)
    return statistics.fmean(value for _name, value in regions)


def agen_predictions_valid(specs, predict):
    """Whether every A_gen slice prediction is valid (`_valid_prediction`). False when the Challenge's own validity
    gates refused a raw answer (`derive` gave None): the exam then gates the submission
    (GATE_FAILED, the slot counted) before `agen_accuracy`, which would otherwise refuse it untyped (Validator 01:40).
    """
    for spec in specs:
        if not spec.agen:
            continue
        batch = predict(spec.conditions, [list(spec.designs[i]) for i in spec.agen])
        if type(batch) is not list or len(batch) != len(spec.agen):
            return False
        if not all(_valid_prediction(p, spec.outputs) for p in batch):
            return False
    return True


def agen_for(specs, predict, scales, optimizer):
    """A set's A_gen under the version's registered aggregation (`optimizer.a_gen_aggregate` and the attached plan). A
    version with neither (every registered version) makes exactly the plain call `agen_accuracy(specs, predict, scales)`.
    """
    if optimizer.a_gen_aggregate is None and optimizer.coverage_plan is None:
        return agen_accuracy(specs, predict, scales)
    return agen_accuracy(
        specs,
        predict,
        scales,
        aggregate=optimizer.a_gen_aggregate,
        plan=optimizer.coverage_plan,
        min_class_cases=optimizer.a_gen_min_class_cases,
    )


def combine_a(a, a_gen, rule):
    """How A_gen enters A (OWNER): {"kind": "min"}, {"kind": "mean"} or {"kind": "weighted", "weight": w}."""
    if a_gen is None:
        return a
    kind = rule.get("kind")
    if kind == "min":
        return min(a, a_gen)
    if kind == "mean":
        return 0.5 * (a + a_gen)
    if kind == "weighted":
        w = rule.get("weight")
        _require(_finite(w) and 0.0 <= w <= 1.0, "weight_must_be_in_0_1")
        return (1.0 - w) * a + w * a_gen
    raise PoolRefused("a_gen_rule_must_be_min_mean_or_weighted")


def total(a, d, c, c_rule):
    """TOP = 0.5 A + 0.5 D with C as the safety floor (OWNER picks how): {"kind": "min"} takes D = min(D, C);
    {"kind": "gate", "floor": f} gives 0 when C < f. Mandatory gates are applied by the caller before this.
    """
    kind = c_rule.get("kind")
    if kind == "min":
        d = min(d, c)
    elif kind == "gate":
        _require(_finite(c_rule.get("floor")), "floor_must_be_finite")
        if c < c_rule["floor"]:
            return 0.0
    else:
        raise PoolRefused("c_rule_must_be_min_or_gate")
    return 0.5 * a + 0.5 * d


POOL_SCHEMA = "carbon.pool.v1"
PRACTICE_SCHEMA = "carbon.pool-grade.practice.v1"


def dump_pool(spec):
    """A target's pool as a JSON-ready document (layout `carbon.pool.v1`). `digest` is the identity to pin: the
    sha256 of the canonical body, so a pool's exact content is its identity. An accuracy-only target's document carries ``accuracy_only`` and none
    of the optimisation fields (`ACCURACY_ONLY_ABSENT`)."""
    if spec.accuracy_only:
        return {
            "schema": POOL_SCHEMA,
            ACCURACY_ONLY: True,
            "public": spec.public,
            "digest": spec.digest,
            "target_id": spec.target_id,
            "conditions": spec.conditions,
            "outputs": list(spec.outputs),
            "u": spec.u,
            "box": [list(b) for b in spec.box],
            "designs": [list(d) for d in spec.designs],
            "truths": list(spec.truths),
            "agen": list(spec.agen),
            "shell": _shell_json(spec.shell),
            "origin": list(spec.origin),
            "pool_size": spec.pool_size,
            **({"extended": True} if spec.declared_extended else {}),
        }
    return {
        "schema": POOL_SCHEMA,
        "public": spec.public,
        "digest": spec.digest,
        "target_id": spec.target_id,
        "conditions": spec.conditions,
        "outputs": list(spec.outputs),
        "objective": spec.objective,
        "sense": "max" if spec.sign > 0 else "min",
        "limits": [[l.output, l.kind, l.bound] for l in spec.limits],
        "u": spec.u,
        "box": [list(b) for b in spec.box],
        "designs": [list(d) for d in spec.designs],
        "truths": list(spec.truths),
        "agen": list(spec.agen),
        "start": list(spec.start),
        "seed": spec.seed,
        "excluded": spec.excluded,
        "shell": _shell_json(spec.shell),
        "origin": list(spec.origin),
        "pool_size": spec.pool_size,
        **({} if spec.zero is None else {"zero": dict(spec.zero)}),
        **({} if spec.near_limit is None else {"near_limit": dict(spec.near_limit)}),
    }


def load_pool(document):
    """Rebuild a target from `dump_pool`'s document, refusing one whose digest does not match its content."""
    _require(
        type(document) is dict and document.get("schema") == POOL_SCHEMA,
        "pool_schema_unknown",
    )
    if ACCURACY_ONLY in document:
        return _load_accuracy_only(document)
    # the declared-extended flag is an accuracy-only target's alone (CV-Motor-C E-1): never ignored on any other
    _require("extended" not in document, "extended_flag_is_for_accuracy_only_targets")
    spec = build_target(
        target_id=document["target_id"],
        conditions=document["conditions"],
        outputs=document["outputs"],
        objective=document["objective"],
        sense=document["sense"],
        limits=[Limit(*row) for row in document["limits"]],
        u=document["u"],
        box=document["box"],
        designs=document["designs"],
        truths=document["truths"],
        agen=document["agen"],
        start=document["start"],
        seed=document["seed"],
        public=document["public"],
        shell=document.get("shell"),
        zero=document.get("zero"),
        near_limit=document.get("near_limit"),
    )
    spec = replace(
        spec,
        origin=tuple(document.get("origin", spec.origin)),
        pool_size=document.get("pool_size", spec.pool_size),
    )
    _require(
        spec.digest == document["digest"] and spec.excluded == 0,
        "pool_digest_does_not_match_its_content",
    )
    return replace(spec, excluded=document["excluded"])


#: An accuracy-only pool document's exact keys (`dump_pool`).
_ACCURACY_ONLY_KEYS = frozenset(
    {
        "schema",
        ACCURACY_ONLY,
        "public",
        "digest",
        "target_id",
        "conditions",
        "outputs",
        "u",
        "box",
        "designs",
        "truths",
        "agen",
        "shell",
        "origin",
        "pool_size",
    }
)


def _load_accuracy_only(document):
    _require(
        document[ACCURACY_ONLY] is True
        and set(document) in (_ACCURACY_ONLY_KEYS, _ACCURACY_ONLY_KEYS | {"extended"})
        and document.get("extended", True) is True,
        "accuracy_only_pool_document_malformed",
    )
    spec = build_accuracy_target(
        target_id=document["target_id"],
        conditions=document["conditions"],
        outputs=document["outputs"],
        u=document["u"],
        box=document["box"],
        designs=document["designs"],
        truths=document["truths"],
        public=document["public"],
        shell=document.get("shell"),
        extended="extended" in document,
    )
    _require(
        spec.digest == document["digest"]
        and list(document["agen"]) == list(spec.agen)
        and list(document["origin"]) == list(spec.origin)
        and document["pool_size"] == spec.pool_size,
        "pool_digest_does_not_match_its_content",
    )
    return spec


def practice_report(
    specs,
    predict,
    optimizer,
    honesty,
    *,
    a,
    c,
    a_rule,
    agen_scales,
    c_rule,
    gates=(),
    minimums=None,
):
    """The practice result for a PUBLIC pool: the legs, the total, the gates and every target's values.

    `a` and `c` are the plugin's legs on the practice cases; A_gen and D_opt come from this module. Refuses any
    pool not marked public, so a sealed target's per-target values cannot be produced here. `gates` is the list
    of {"code", "passed"} the caller's mandatory gates give; any failed gate gives a total of 0. `minimums` is
    passed through as given (OWNER-PRACTICE-SHOWS-MINIMUMS-01 names what a miner sees).
    """
    _require(all(s.public for s in specs), "pool_not_public")
    grade = grade_set(specs, predict, optimizer, honesty)
    a_gen = agen_for(specs, predict, agen_scales, optimizer)
    a_total = combine_a(a, a_gen, a_rule)
    gated_out = any(not g["passed"] for g in gates)
    top = 0.0 if gated_out else total(a_total, grade.d, c, c_rule)
    return {
        "schema": PRACTICE_SCHEMA,
        "pool_digests": [s.digest for s in specs],
        "legs": {
            "A": a,
            "A_gen": a_gen,
            "A_combined": a_total,
            "D_opt": grade.d,
            "C": c,
        },
        "total": top,
        "gates": [dict(g) for g in gates],
        "minimums": minimums,
        "targets": [
            {
                "target_id": t.target_id,
                "d": t.d,
                "closeness": t.q,
                "honesty": t.h,
                "error_in_u": None if math.isinf(t.e) else t.e,
                "feasible": t.feasible,
                "queries": t.queries,
                "reached_reference": t.reached_reference,
                "reason": t.reason,
            }
            for t in grade.targets
        ],
    }
