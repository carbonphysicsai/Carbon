"""Optional synthetic value-outcome availability; never a production policy.

The scoring half and candidate decisions remain unchanged. Missing value
outcomes affect a shared measurement mask, not scientific candidate merit.
"""

from __future__ import annotations

import copy
import math

from .core import LabRefused, analyze, canonical_sha, validate_panel

SCHEMA = "carbon.dev.score-lab-value-reference-failures.v1"
POLICIES = frozenset({"REQUIRE_COMPLETE", "EXCLUDE_COMMON"})


def validate(spec):
    """Require explicit toy inputs within the existing plan's 0-5% range."""
    if (
        type(spec) is not dict
        or set(spec) != {"schema", "label", "fraction", "seed", "policy"}
        or spec["schema"] != SCHEMA
        or type(spec["label"]) is not str
        or not spec["label"].startswith("ASSUMPTION:")
        or type(spec["fraction"]) not in (int, float)
        or not math.isfinite(spec["fraction"])
        or not 0 <= spec["fraction"] <= 0.05
        or type(spec["seed"]) is not int
        or spec["seed"] < 0
        or type(spec["policy"]) is not str
        or spec["policy"] not in POLICIES
    ):
        raise LabRefused("value_reference_failure_spec")
    return spec


def prepare(panel, spec):
    """Copy a synthetic panel, inject model-independent whole-question outages."""
    validate(spec)
    if type(panel) is not dict or panel.get("scope") != "SYNTHETIC_DEVELOPMENT":
        raise LabRefused("value_reference_failure_requires_synthetic")
    validate_panel(panel)
    if not panel["value_questions"] or any(
        type(q) is not str or not q for q in panel["value_questions"]
    ):
        raise LabRefused("value_reference_failure_question_ids")
    questions = sorted(panel["value_questions"])
    members = panel["members"]
    for member in members:
        for loss in member["value_losses"].values():
            if loss is not None and (
                type(loss) not in (int, float) or not math.isfinite(loss)
            ):
                raise LabRefused("value_reference_failure_nonfinite_loss")
    preexisting = {
        q for q in questions if any(m["value_losses"][q] is None for m in members)
    }
    count = math.floor(spec["fraction"] * len(questions))
    ordered = sorted(questions, key=lambda q: (canonical_sha([spec["seed"], q]), q))
    injected = set(ordered[:count])
    missing = preexisting | injected
    common = sorted(set(questions) - missing)
    masked = copy.deepcopy(panel)
    for member in masked["members"]:
        for q in injected:
            member["value_losses"][q] = None
    if "exact_oracle_losses" in masked:
        for q in injected:
            masked["exact_oracle_losses"][q] = None
    receipt = {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "spec": copy.deepcopy(spec),
        "spec_sha256": canonical_sha(spec),
        "input_panel_sha256": canonical_sha(panel),
        "offered_questions": len(questions),
        "injected_unresolved": len(injected),
        "preexisting_unresolved": len(preexisting),
        "overlap_unresolved": len(preexisting & injected),
        "common_unresolved": len(missing),
        "common_resolved_available": len(common),
        "realized_injected_fraction": len(injected) / len(questions),
        "rounding": "floor(fraction * offered_questions)",
        "common_resolved_mask_sha256": canonical_sha(common),
        "estimand": (
            "conditional_on_common_resolved_value_questions"
            if spec["policy"] == "EXCLUDE_COMMON"
            else "complete_offered_value_questions_required"
        ),
    }
    return masked, receipt


def evaluate(panel, rule, spec, *, bootstrap=200):
    """Reuse the score lab's analysis, with explicit shared value accounting."""
    masked, receipt = prepare(panel, spec)
    if not callable(rule):
        raise LabRefused("value_reference_failure_rule_missing")
    if receipt["common_resolved_available"] == 0 or (
        spec["policy"] == "REQUIRE_COMPLETE" and receipt["common_unresolved"]
    ):
        result = {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": (
                "no_common_resolved_value_questions"
                if receipt["common_resolved_available"] == 0
                else "value_reference_incomplete"
            ),
            "source": "SYNTHETIC_DEVELOPMENT",
        }
    else:
        result = analyze(masked, rule, bootstrap=bootstrap)
    receipt["scored_value_questions"] = (
        result["value_questions"] if result["status"] == "MEASURED_DEVELOPMENT" else 0
    )
    return {**result, "value_reference_measurement": receipt}
