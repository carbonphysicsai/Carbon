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
"""

from __future__ import annotations

from dataclasses import dataclass

from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    BURGERS_CHALLENGE,
    CONTRACTS,
    Dimension,
    Status,
    catalog_surfaces,
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
}


def _issue(code, path):
    return ValidationIssue(code, path, ISSUE_MESSAGES[code])


def validate_for_challenge(strategy) -> ValidationResult:
    """Structural validation, then the named Challenge's own contract."""
    base = dry_validate(strategy)
    issues = list(base.errors)
    if type(strategy) is not dict:
        return base
    flagged = {i.path for i in issues}
    challenge = strategy.get("challenge_id")
    if type(challenge) is not str or "/challenge_id" in flagged:
        return base
    item = CONTRACTS.get(challenge)
    if item is None:
        issues.append(_issue("challenge.unknown", "/challenge_id"))
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

    def __init__(self, issues):
        self.issues = tuple(issues)
        if not self.issues or not all(type(i) is ValidationIssue for i in self.issues):
            raise TypeError("named ValidationIssue reasons required")
        super().__init__(
            "submission refused: " + ",".join(f"{i.code}@{i.path}" for i in self.issues)
        )


def check_contract_digest(challenge, digest):
    """Refuse, by name, a submission recorded against a different contract."""
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
    #: The Burgers reconstruction profile, or the battery recipe.
    construction: object


def compile_submission(strategy, *, contract_digest=None):
    """Validate against the named Challenge's contract, then compile with its
    own catalog through B-02B. Raises `SubmissionRefused` (contract-level
    issues) or `RecipeRejected` (compiler and backend issues), each naming
    every reason."""
    result = validate_for_challenge(strategy)
    if not result.ok:
        raise SubmissionRefused(result.errors)
    challenge = strategy["challenge_id"]
    item = CONTRACTS[challenge]
    if contract_digest is not None:
        check_contract_digest(challenge, contract_digest)
    if challenge == BURGERS_CHALLENGE:
        from carbon.development_session.research_catalog import compile_recipe

        compiled, construction = compile_recipe(strategy)
    elif challenge == BATTERY_CHALLENGE:
        from carbon.battery.compile import compile_recipe

        compiled, construction = compile_recipe(strategy)
    else:  # a registered contract with no compiler is a defect, not a refusal
        raise RuntimeError("no compiler for a registered contract")
    return CompiledSubmission(challenge, item.digest, compiled, construction)
