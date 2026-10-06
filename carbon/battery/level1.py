"""Battery construction Level 1: loss expressions, as development-only variants.

The Level-1 build after the Test Lead's review
(`docs/development/graphite/reviews/L1_LOSS_EXPRESSIONS_TEST_LEAD_REVIEW.md`;
packet `docs/development/graphite/L1_LOSS_EXPRESSIONS_REVIEW_PACKET.md`).
Two registered development-only variants
(`carbon/reconstruction/development_variant_policies/`), never served to a
miner:
- `battery-l1-loss-expressions-v1`, the valid surface: the GA-D6 core
  (`objective.loss_expressions`, the one field a strategy supplies) and one
  capability per operation family, each a permission without a field, so the
  climb can ablate each one (Test Lead Q2):
  - `objective.loss_time_reductions`: the time terms and `mean_t`/`max_t`;
  - `objective.loss_robust_operations`: `max`, `min`, `cap`, `excess`;
  - `objective.loss_expm1`: `expm1` with a capped argument;
  - `objective.loss_component_terms`: the per-output-group terms;
  - `objective.loss_wide_constants`: `scale` up to 100, exponents 0.25 to 4;
- `battery-l1-loss-expressions-signed-v1`, the signed arm (arm `signed`): the
  core plus `objective.loss_signed_operations` (`sub`, `neg`, `exp` and
  constant leaves). It is used in the ATTACK panel only, never as a valid
  surface, to prove that non-finite training is the candidate's own failure.

An expression compiles against the operation set its profile grants
(`operation_set`), so removing a family's permission makes every expression
that uses the family refused by code. Degenerate losses run (Q3): statically
detectable no-ops are a diagnostic, never a refusal. `div` stays general
(Q4). JAX only (Q5): the `mlp` and `deeponet` families on the JAX backend.
Until GPU identity is measured (Q6), every Level-1 result carries
`rebuild: CPU-verified only`.

Identity (OWNER-GRAPHITE-TEST-WAVE-04 §1): nothing counts, limits,
deduplicates or rewards constructions by the expression's digest. The
reconstruction record carries it as a diagnostic only; distinct
constructions are identified by their rebuilt artifact.
"""

from __future__ import annotations

from carbon.battery.loss_terms import (
    CASE_TERMS,
    COMPONENT_TERMS,
    REBUILD_LABEL,
    TIME_TERMS,
)
from carbon.reconstruction import loss_expressions as le
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

CHALLENGE = BATTERY_CHALLENGE
LEVEL = 1
CORE = "objective.loss_expressions"
FIELD = "loss_expressions"
VERSION = "battery-l1-loss-expressions-v1"
SIGNED_VERSION = "battery-l1-loss-expressions-signed-v1"
SIGNED_ARM = "signed"
TIME = "objective.loss_time_reductions"
ROBUST = "objective.loss_robust_operations"
EXPM1 = "objective.loss_expm1"
COMPONENTS = "objective.loss_component_terms"
WIDE = "objective.loss_wide_constants"
SIGNED = "objective.loss_signed_operations"
#: The valid surface's operation families, in the order they are documented.
FAMILIES = (TIME, ROBUST, EXPM1, COMPONENTS, WIDE)
#: The structural bounds (Test Lead Q1: depth 32, 512 nodes; arity 16).
MAX_DEPTH, MAX_NODES, MAX_ARITY = 32, 512, 16
EPSILON = 1e-6
CORE_SCALE, CORE_EXPONENT = (0.0, 10.0), (0.5, 2.0)
WIDE_SCALE, WIDE_EXPONENT = (0.0, 100.0), (0.25, 4.0)
CAP_AT = EXCESS_OVER = (0.0, 1.0e4)
EXPM1_CAP = (0.0, 16.0)
SIGNED_CONST = (-100.0, 100.0)
APPLIES_TO = ("deeponet", "mlp")
BACKENDS = ("jax",)
#: The objective menu an expression replaces: supplying one beside an
#: expression is refused, because it would change nothing Carbon rebuilds.
MENU = ("h1_weight", "h2_weight", "relative_loss", "spectral_weight", "time_weighting")
IDENTITY = (
    "OWNER-GRAPHITE-TEST-WAVE-04 section 1: distinct constructions are "
    "identified by the rebuilt artifact's digest; the expression digest is a "
    "diagnostic only and nothing counts, limits, deduplicates or rewards by it"
)
#: Error-bearing terms: every term but the target energies and the time
#: coordinates depends on the prediction.
_PARAMETER_FREE = frozenset(
    {"target_energy", "time_t", "time_rev_t"}
    | {t for t in COMPONENT_TERMS if t.startswith("target_energy_")}
)
_CORE_OPERATIONS = le.OPERATIONS
_FAMILY_OPERATIONS = {
    TIME: ("mean_t", "max_t"),
    ROBUST: ("max", "min", "cap", "excess"),
    EXPM1: ("expm1",),
    SIGNED: ("sub", "neg", "exp", "const"),
}


def operation_set(granted):
    """Battery's operation set for the Level-1 permissions `granted`."""
    granted = frozenset(granted)
    if CORE not in granted:
        raise ValueError("the core loss-expression permission is required")
    unknown = granted - {CORE, SIGNED, *FAMILIES}
    if unknown:
        raise ValueError("unknown Level-1 permissions: " + ", ".join(sorted(unknown)))
    allowed = set(_CORE_OPERATIONS)
    for family, operations in _FAMILY_OPERATIONS.items():
        if family in granted:
            allowed |= set(operations)
    operations = tuple(o for o in le.OPERATIONS_V2 if o in allowed)
    wide = WIDE in granted
    names = sorted(g.partition(".")[2] for g in granted - {CORE})
    return le.OperationSet(
        name="battery-l1" + "".join("+" + n for n in names),
        terms=CASE_TERMS + (COMPONENT_TERMS if COMPONENTS in granted else ()),
        max_depth=MAX_DEPTH,
        max_nodes=MAX_NODES,
        max_arity=MAX_ARITY,
        scale=WIDE_SCALE if wide else CORE_SCALE,
        exponent=WIDE_EXPONENT if wide else CORE_EXPONENT,
        epsilon=EPSILON,
        operations=operations,
        time_terms=TIME_TERMS if TIME in granted else (),
        cap_at=CAP_AT if ROBUST in granted else (0.0, 0.0),
        excess_over=EXCESS_OVER if ROBUST in granted else (0.0, 0.0),
        expm1_cap=EXPM1_CAP if EXPM1 in granted else (0.0, 0.0),
        const=SIGNED_CONST if SIGNED in granted else (0.0, 0.0),
    )


def families_used(expression):
    """The Level-1 permissions a canonical expression needs."""
    operations, terms = le.uses(expression)
    needed = {CORE}
    for family, family_operations in _FAMILY_OPERATIONS.items():
        if operations & set(family_operations):
            needed.add(family)
    if terms & set(TIME_TERMS):
        needed.add(TIME)
    if terms & set(COMPONENT_TERMS):
        needed.add(COMPONENTS)
    for node in le.walk(expression):
        if node.get("op") == "scale" and not (
            CORE_SCALE[0] <= node["by"] <= CORE_SCALE[1]
        ):
            needed.add(WIDE)
        if node.get("op") == "pow" and not (
            CORE_EXPONENT[0] <= node["exponent"] <= CORE_EXPONENT[1]
        ):
            needed.add(WIDE)
    return needed


def raw_families(value, _depth=0):
    """The Level-1 permissions an expression names, read without compiling
    (for a construction Carbon may refuse): operation and term names, and
    constants outside the core ranges. Bounded in depth; never raises."""
    needed = {CORE}
    if _depth > 2 * MAX_DEPTH:
        return needed
    if isinstance(value, list):
        for item in value:
            needed |= raw_families(item, _depth + 1)
        return needed
    if not isinstance(value, dict):
        return needed
    op, term = value.get("op"), value.get("term")
    for family, operations in _FAMILY_OPERATIONS.items():
        if op in operations or (family == SIGNED and "const" in value):
            needed.add(family)
    if term in TIME_TERMS:
        needed.add(TIME)
    if term in COMPONENT_TERMS:
        needed.add(COMPONENTS)
    for field, (low, high) in (("by", CORE_SCALE), ("exponent", CORE_EXPONENT)):
        number = value.get(field)
        if (
            op in ("scale", "pow")
            and le._number(number)
            and not low <= number <= high
            and WIDE_SCALE[0] <= number <= max(WIDE_SCALE[1], WIDE_EXPONENT[1])
        ):
            needed.add(WIDE)
    for key in ("arg", "args"):
        if key in value:
            needed |= raw_families(value[key], _depth + 1)
    return needed


def climb_plan(*, panel, attacks, attack_budget, combined, promising, arm=None):
    """Battery's Level-1 climb plan over the registered variant (or its
    named arm), for the Challenge-neutral harness. The previous profile is
    Level 0; the new permissions are the variant's; the plan names the
    variant, so the climb continues past a finding and tags what follows."""
    from carbon.agent_campaign import climb
    from carbon.reconstruction import development_variants as dv
    from carbon.reconstruction.capability_registry import Status
    from carbon.reconstruction.capability_registry import contract as _contract

    base = _contract(CHALLENGE)
    level0 = frozenset(
        c.capability_id
        for c in base.capabilities
        if c.status is Status.REBUILDABLE_DEVELOPMENT
    )
    found = dv.variant(CHALLENGE, LEVEL, arm)
    return climb.ClimbPlan(
        challenge=CHALLENGE,
        level=LEVEL,
        previous=climb.profile("level-0", base=base.digest, permissions=level0),
        expanded=climb.profile(
            "level-1" if arm is None else "level-1-" + arm,
            base=base.digest,
            permissions=level0 | set(found.permissions()),
            extra=found.digest,
        ),
        new_permissions=tuple(found.permissions()),
        panel=tuple(panel),
        attacks=tuple(attacks),
        attack_budget=attack_budget,
        combined=tuple(combined),
        promising=promising,
        development_variant=found.digest,
    )


def diagnostics(expression):
    """Statically detectable degenerate losses (Q3): flagged, never refused."""
    found = []
    _operations, terms = le.uses(expression)
    if not terms - _PARAMETER_FREE:
        found.append("no_error_term")
    for node in le.walk(expression):
        op = node.get("op")
        if op == "cap" and node["at"] == 0.0:
            found.append("cap_at_zero")
        elif op == "expm1" and node["cap"] == 0.0:
            found.append("expm1_cap_zero")
        elif op == "scale" and node["by"] == 0.0:
            found.append("scale_by_zero")
    return sorted(set(found))


def _refused(issues):
    from carbon.reconstruction import development_variants as dv

    return dv.VariantRefused(dv.PARAMETER_REFUSED, issues=issues)


def compile_for(value, granted):
    """The compiled expression under `granted`, or `ExpressionRefused`."""
    return le.compile_expression(value, operation_set(granted))


def reconstruct(value, admitted, granted):
    """Carbon's reconstruction of `objective.loss_expressions`
    (`development_variants.RECONSTRUCTIONS`): the expression compiled,
    canonicalized and pinned under the granted operation set, on Carbon's
    host. Every refusal is a typed `VariantRefused` (R3)."""
    path = "/parameters/" + FIELD
    recipe = admitted.construction
    issues = []
    if recipe.family not in APPLIES_TO:
        issues.append(("development.not_applicable", path))
    if recipe.settings.get("backend", "jax") not in BACKENDS:
        issues.append(("development.backend_not_served", "/parameters/backend"))
    for name in sorted(set(MENU) & set(recipe.supplied)):
        issues.append(("development.menu_and_expression", "/parameters/" + name))
    if issues:
        raise _refused(issues)
    try:
        compiled = compile_for(value, granted)
    except le.ExpressionRefused as refused:
        where = path + ("" if refused.path == "/" else refused.path.rstrip("/"))
        raise _refused(
            [("development.loss_expression." + refused.code, where)]
        ) from None
    opset = compiled.operation_set
    return {
        "canonical": compiled.canonical_bytes().decode("utf-8"),
        "expression_digest": compiled.digest,
        "operation_set": opset.digest,
        "operation_set_document": opset.document(),
        "families": sorted(families_used(compiled.expression)),
        "diagnostics": diagnostics(compiled.expression),
        "identity": IDENTITY,
        "rebuild": REBUILD_LABEL,
    }


def permission_only(capability_id):
    """The reconstruction of a family permission: it has no field, so a value
    supplied under its name is refused by code."""

    def reconstruct_permission(value, admitted, granted):
        raise _refused(
            [("development.permission_only", "/parameters/" + capability_id[10:])]
        )

    return reconstruct_permission


# -- the variant documents ------------------------------------------------------
REVIEW = {
    "reviewer": "Test Lead",
    "record": (
        "docs/development/graphite/reviews/L1_LOSS_EXPRESSIONS_TEST_LEAD_REVIEW.md "
        "(2026-10-05)"
    ),
}
AUTHORITY = (
    "OWNER-GRAPHITE-TEST-WAVE-03 section 1; OWNER-GRAPHITE-DEV-LEVELS-01 F1; "
    "OWNER-GRAPHITE-TEST-WAVE-04 sections 1 and 2; the Test Lead's review of the "
    "Level-1 packet; engineering choices GRAPHITE-L1-BUILD-01"
)
_LIMITS = {"max_arity": MAX_ARITY, "max_depth": MAX_DEPTH, "max_nodes": MAX_NODES}
_SUMMARIES = {
    CORE: (
        "The per-case training loss as a bounded, declarative expression over "
        "battery's registered loss terms, in place of the fixed objective menu "
        "(the GA-D6 core). Carbon validates, canonicalizes and pins it, and "
        "builds the loss with its own code."
    ),
    TIME: "Adds the per-time terms and the time reductions mean_t and max_t.",
    ROBUST: "Adds the operations max, min, cap and excess.",
    EXPM1: "Adds expm1 with a capped argument.",
    COMPONENTS: "Adds each output group's share of the squared error and target energy.",
    WIDE: "Widens scale to [0, 100] and the pow exponent to [0.25, 4].",
    SIGNED: (
        "Adds sub, neg, exp and constant leaves, which can make a loss negative "
        "or non-finite. Attack panel only, never a valid surface."
    ),
}


def _bounds(capability_id, granted):
    """A widened capability's stated bounds."""
    if capability_id == CORE:
        core = operation_set({CORE})
        full = operation_set(granted)
        return {
            "field": FIELD,
            "operations": list(core.operations),
            "terms": list(core.terms),
            "scale": list(CORE_SCALE),
            "exponent": list(CORE_EXPONENT),
            "epsilon": EPSILON,
            "limits": dict(_LIMITS),
            "backends": list(BACKENDS),
            "replaces": ["objective." + m for m in MENU],
            "operation_set_all_granted": full.digest,
            "expression_schema": full.expression_schema,
            "reconstruction": (
                "Carbon recompiles the expression from its canonical bytes "
                "against the operation set its profile grants and evaluates it "
                "with its own code in its JAX trainer (carbon.battery.level1, "
                "carbon.battery.loss_terms); nothing the strategy supplies is "
                "executed"
            ),
            "identity": IDENTITY,
            "rebuild": REBUILD_LABEL,
            "degenerate_losses": "run; statically detectable no-ops are a diagnostic",
        }
    bounds = {"field": None, "permission_only": True}
    operations = _FAMILY_OPERATIONS.get(capability_id)
    if operations:
        bounds["adds_operations"] = list(operations)
    if capability_id == TIME:
        bounds["adds_time_terms"] = list(TIME_TERMS)
        bounds["over"] = sorted(le.OVER)
    if capability_id == ROBUST:
        bounds["cap_at"] = list(CAP_AT)
        bounds["excess_over"] = list(EXCESS_OVER)
    if capability_id == EXPM1:
        bounds["expm1_cap"] = list(EXPM1_CAP)
    if capability_id == COMPONENTS:
        bounds["adds_terms"] = list(COMPONENT_TERMS)
    if capability_id == WIDE:
        bounds["scale"] = list(WIDE_SCALE)
        bounds["exponent"] = list(WIDE_EXPONENT)
    if capability_id == SIGNED:
        bounds["const"] = list(SIGNED_CONST)
        bounds["use"] = "attack panel only"
    return bounds


def variant_document(version=VERSION, *, base=None):
    """A Level-1 variant's registered document, built from this module's
    bounds so the registered policy and the code cannot drift apart."""
    from carbon.reconstruction import expansion_record
    from carbon.reconstruction.capability_registry import contract

    widened = (CORE, *FAMILIES) if version == VERSION else (CORE, SIGNED)
    if base is None:
        records = expansion_record.records(CHALLENGE)
        base = {
            "digest": contract(CHALLENGE).digest,
            "record_sequence": records[-1]["sequence"],
        }
    granted = frozenset(widened)
    return {
        "schema": "carbon.construction-development-variant.v1",
        "version": version,
        "challenge": CHALLENGE,
        "level": LEVEL,
        "scope": "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS",
        "status": "REGISTERED_DEVELOPMENT_POLICY",
        "authority": AUTHORITY,
        "review": dict(REVIEW),
        "base_contract": dict(base),
        "participant_code": False,
        "widened": [
            {
                "id": capability_id,
                "summary": _SUMMARIES[capability_id],
                "surface": None,
                "applies_to": list(APPLIES_TO),
                "bounds": _bounds(capability_id, granted),
            }
            for capability_id in widened
        ],
    }


RECONSTRUCTIONS = {
    (CHALLENGE, CORE): reconstruct,
    **{(CHALLENGE, f): permission_only(f) for f in (*FAMILIES, SIGNED)},
}
