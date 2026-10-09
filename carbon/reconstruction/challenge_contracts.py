"""Per-Challenge submission admission: "can I submit this?" for every Challenge.

Strategy schema 1.0's `dry_validate` stays the structural, registry-free layer
that strategy identity is built on. This module adds what it deliberately does
not know: the construction contract of the Challenge a submission names
(OWNER-BATTERY-TESTNET-01, OD-8). Every door that accepts a design - compile,
check-design, the Launchpad and the validator's admission - goes through
`validate_for_challenge`, so an unknown Challenge, a family that Challenge does
not rebuild, and an unknown or inapplicable field are each refused by name.

The compiler resolves only the named Challenge's contract: a Burgers family
submitted under battery is refused, and the reverse.

A development-only contract variant (OWNER-GRAPHITE-TEST-WAVE-03 §1) is never
served here: a submission naming one, as its contract digest or its
Challenge, is refused by name (`development_variant_not_served`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from carbon.reconstruction.capability_registry import (
    CONTRACTS,
    DEVELOPMENT_VARIANT_NOT_SERVED,
    Dimension,
    Status,
    catalog_surfaces,
    is_development_variant,
    rebuildable_families,
)
from carbon.schema.strategy import (
    ValidationIssue,
    ValidationResult,
    _child_path,
    dry_validate,
)

ISSUE_MESSAGES = {
    "challenge.unknown": "No construction contract is registered for this Challenge.",
    "backbone.not_in_contract": "This family is not registered for this Challenge.",
    "backbone.not_rebuildable": "Carbon does not rebuild this family for this Challenge yet.",
    "parameter.unknown": "This field is not in this Challenge's vocabulary.",
    "parameter.not_rebuildable": "Carbon does not rebuild this field for this Challenge yet.",
    "parameter.not_applicable": "This field does not apply to the selected family.",
    "contract.digest_mismatch": "The contract digest is not this Challenge's current contract.",
    DEVELOPMENT_VARIANT_NOT_SERVED: (
        "This names a development-only contract variant, which is never served "
        "to miners."
    ),
    "budget.over_compute_budget": (
        "This recipe's calculated compute cost is over the Challenge's compute budget."
    ),
    "budget.cost_unmeasurable": (
        "This recipe's compute cost cannot be calculated in the budget's unit."
    ),
}
#: The contract envelope key a Challenge declares its compute budget under
#: (OWNER-COMPUTE-BUDGET-01): `{"unit": <cost report key>, "value": <ceiling>}`.
#: No live contract declares one yet; a Challenge switches on only after the
#: owner's decision on its study (TRAINING-BUDGET-01).
COMPUTE_BUDGET = "compute_budget"


def _issue(code, path):
    return ValidationIssue(code, path, ISSUE_MESSAGES[code])


def validate_for_challenge(strategy, *, contract_digest=None) -> ValidationResult:
    """Structural validation, then the named Challenge's own contract. When the
    caller passes the contract digest the submission was written against, a
    development-only variant's digest is refused by name."""
    base = dry_validate(strategy)
    issues = list(base.errors)
    if is_development_variant(contract_digest):
        issues.append(_issue(DEVELOPMENT_VARIANT_NOT_SERVED, "/contract_digest"))
        base = _result(issues)
    if type(strategy) is not dict:
        return base
    flagged = {i.path for i in issues}
    challenge = strategy.get("challenge_id")
    if type(challenge) is not str or "/challenge_id" in flagged:
        return base
    item = CONTRACTS.get(challenge)
    if item is None:
        issues.append(
            _issue(
                (
                    DEVELOPMENT_VARIANT_NOT_SERVED
                    if is_development_variant(challenge)
                    else "challenge.unknown"
                ),
                "/challenge_id",
            )
        )
        return _result(issues)
    families = dict(rebuildable_families(challenge))
    registered = {c.capability_id: c for c in item.capabilities}
    backbone = strategy.get("backbone")
    if (
        type(backbone) is str
        and "/backbone" not in flagged
        and backbone not in families
    ):
        entry = registered.get("model_family." + backbone)
        issues.append(
            _issue(
                (
                    "backbone.not_in_contract"
                    if entry is None
                    else "backbone.not_rebuildable"
                ),
                "/backbone",
            )
        )
    parameters = strategy.get("parameters")
    if type(parameters) is dict:
        surfaces = catalog_surfaces(challenge)
        by_name = {
            c.capability_id.partition(".")[2]: c
            for c in item.capabilities
            if c.dimension is not Dimension.MODEL_FAMILY
        }
        for key in sorted(k for k in parameters if type(k) is str):
            path = _child_path("/parameters", key)
            if path in flagged:
                continue  # already refused as a forbidden capability
            if key not in surfaces:
                entry = by_name.get(key)
                issues.append(
                    _issue(
                        (
                            "parameter.not_rebuildable"
                            if entry is not None
                            and entry.status is not Status.REBUILDABLE_DEVELOPMENT
                            else "parameter.unknown"
                        ),
                        path,
                    )
                )
            elif (
                surfaces[key][5] is not None
                and type(backbone) is str
                and backbone in families
                and backbone not in surfaces[key][5]
            ):
                issues.append(_issue("parameter.not_applicable", path))
    return _result(issues)


def _result(issues):
    errors = tuple(sorted(issues, key=lambda i: (i.path, i.code)))
    return ValidationResult(ok=not errors, errors=errors)


class SubmissionRefused(ValueError):
    """A submission refused with every reason named by code and path."""

    def __init__(self, issues, *, budget=None):
        self.issues = tuple(issues)
        if not self.issues or not all(type(i) is ValidationIssue for i in self.issues):
            raise TypeError("named ValidationIssue reasons required")
        #: For a compute budget refusal: `{unit, used, allowed}`; else None.
        self.budget = budget
        super().__init__(
            "submission refused: " + ",".join(f"{i.code}@{i.path}" for i in self.issues)
        )


def check_contract_digest(challenge, digest):
    """Refuse, by name, a submission recorded against a different contract,
    and first one recorded against a development-only variant."""
    if is_development_variant(digest):
        raise SubmissionRefused(
            (_issue(DEVELOPMENT_VARIANT_NOT_SERVED, "/contract_digest"),)
        )
    item = CONTRACTS.get(challenge)
    if item is None:
        raise SubmissionRefused((_issue("challenge.unknown", "/challenge_id"),))
    if digest != item.digest:
        raise SubmissionRefused(
            (_issue("contract.digest_mismatch", "/contract_digest"),)
        )
    return item


@dataclass(frozen=True)
class CompiledSubmission:
    """One submission compiled against exactly its Challenge's contract."""

    challenge: str
    contract_digest: str
    compiled: object
    #: The named Challenge's guarded reconstruction recipe/profile.
    construction: object


def compile_submission(strategy, *, contract_digest=None):
    """Validate against the named Challenge's contract, then compile with its
    own catalog through B-02B. Raises `SubmissionRefused` (contract-level
    issues) or `RecipeRejected` (compiler and backend issues), each naming
    every reason. A development-only variant's digest is refused by name;
    Graphite's development compile path is
    `development_variants.compile_development`, never this one."""
    result = validate_for_challenge(strategy, contract_digest=contract_digest)
    if not result.ok:
        raise SubmissionRefused(result.errors)
    challenge = strategy["challenge_id"]
    item = CONTRACTS[challenge]
    if contract_digest is not None:
        check_contract_digest(challenge, contract_digest)
    from carbon.challenge_registry.registry import compiler_for

    try:
        compiled, construction = compiler_for(challenge)(strategy)
    except LookupError:
        # A registered construction contract without a compiler is a repository
        # defect, not a candidate refusal or a fallback to another Challenge.
        raise RuntimeError("no compiler for a registered contract") from None
    check_compute_budget(item, strategy)
    return CompiledSubmission(challenge, item.digest, compiled, construction)


#: Whether a recipe is inside its Challenge's compute budget, as every door
#: shows it (LAUNCHPAD-COMPUTE-BUDGET-STATUS-01). `budget_status` gives it and
#: `check_compute_budget` admits by it, so a display and a refusal cannot
#: disagree on the same recipe.
BUDGET_STATUS_SCHEMA = "carbon.compute-budget-status.v1"
#: No declared budget: no number is shown, and admission computes nothing.
BUDGET_NOT_SET = "NOT_SET"
#: A declared budget and the recipe's cost in its unit: `used`, `allowed` and
#: `within` are all known.
BUDGET_SET = "SET"
#: A declaration that is not `{"unit": <str>, "value": <number above 0>}`: a
#: repository defect, never a recipe's.
BUDGET_MALFORMED = "MALFORMED"
#: The calculator refused this recipe, or gave no number in the budget's unit.
BUDGET_UNMEASURABLE = "UNMEASURABLE"
#: The Challenge has no training budget adapter, so no cost can be calculated.
BUDGET_NO_ADAPTER = "NO_ADAPTER"
#: The budget's unit needs factors the Challenge's study has not fitted yet
#: (`HUMAN_INPUT`).
BUDGET_UNIT_NOT_CALIBRATED = "UNIT_NOT_CALIBRATED"
#: A declared budget the recipe's cost cannot be compared with: admission
#: refuses each `budget.cost_unmeasurable`, never lets it through.
BUDGET_UNMEASURED = frozenset(
    {BUDGET_UNMEASURABLE, BUDGET_NO_ADAPTER, BUDGET_UNIT_NOT_CALIBRATED}
)


def declared_compute_budget(item):
    """`(status, budget)` for a contract's envelope: `(NOT_SET, None)`,
    `(MALFORMED, None)` or `(SET, {"unit", "value"})`. The one parse of the
    declaration every reader uses; no budget is ever invented here."""
    envelope = dict(item.document()["envelope"])
    budget = envelope.get(COMPUTE_BUDGET)
    if budget is None:
        return BUDGET_NOT_SET, None
    if not (
        type(budget) is dict
        and set(budget) == {"unit", "value"}
        and type(budget["unit"]) is str
        and type(budget["value"]) in (int, float)
        and math.isfinite(budget["value"])
        and budget["value"] > 0
    ):
        return BUDGET_MALFORMED, None
    return BUDGET_SET, {"unit": budget["unit"], "value": budget["value"]}


def _measured_budget(item, strategy):
    """`(status, report)`: the budget status and the calculator's report (None
    when nothing was calculated)."""
    if type(item) is str:
        # No construction contract, so no envelope declares a budget.
        item = CONTRACTS.get(item)
    status = {
        "schema": BUDGET_STATUS_SCHEMA,
        "status": BUDGET_NOT_SET,
        "unit": None,
        "used": None,
        "allowed": None,
        "within": None,
    }
    if item is None:
        return status, None
    state, budget = declared_compute_budget(item)
    if state != BUDGET_SET:
        return {**status, "status": state}, None
    status = {
        **status,
        "status": BUDGET_SET,
        "unit": budget["unit"],
        "allowed": budget["value"],
    }
    from carbon.training_budget import cost as calculator
    from carbon.training_budget.adapter import NoAdapter

    try:
        report = calculator.cost(strategy["challenge_id"], strategy)
    except NoAdapter:
        return {**status, "status": BUDGET_NO_ADAPTER}, None
    except calculator.CostRefused:
        return {**status, "status": BUDGET_UNMEASURABLE}, None
    value = report.get(budget["unit"])
    if value == calculator.HUMAN_INPUT:
        return {**status, "status": BUDGET_UNIT_NOT_CALIBRATED}, report
    if type(value) not in (int, float) or not math.isfinite(value):
        return {**status, "status": BUDGET_UNMEASURABLE}, report
    return {**status, "used": value, "within": value <= budget["value"]}, report


def budget_status(item, strategy):
    """Whether `strategy` is inside the compute budget of `item` (a contract,
    or a Challenge id): `{schema, status, unit, used, allowed, within}`.

    NOT_SET (no declared budget) and MALFORMED carry no number and compute
    nothing. With a declared budget the cost is the training budget
    calculator's (`carbon.training_budget.cost`) on this host's image, and
    `within` is `used <= allowed`; the validator's figure on its pinned image
    decides. Admission (`check_compute_budget`) refuses by this same status."""
    return _measured_budget(item, strategy)[0]


def check_compute_budget(item, strategy):
    """Refuse a recipe over the contract's declared compute budget.

    Only a contract whose envelope declares `compute_budget` is checked; the
    others keep their per-setting caps and nothing is computed. The verdict is
    `budget_status`'s, so the doors that show it and this check agree. A cost
    that cannot be calculated in the budget's unit is refused, never let
    through. A refusal carries `budget`: the unit, the cost (None when it
    could not be calculated) and the ceiling."""
    status, report = _measured_budget(item, strategy)
    if status["status"] == BUDGET_NOT_SET:
        return None
    if status["status"] == BUDGET_MALFORMED:
        # A malformed declaration is a repository defect, not a refusal.
        raise RuntimeError("malformed compute budget declaration")
    detail = {key: status[key] for key in ("unit", "used", "allowed")}
    if status["status"] in BUDGET_UNMEASURED:
        raise SubmissionRefused(
            (_issue("budget.cost_unmeasurable", "/parameters"),), budget=detail
        )
    if not status["within"]:
        raise SubmissionRefused(
            (_issue("budget.over_compute_budget", "/parameters"),), budget=detail
        )
    return report
