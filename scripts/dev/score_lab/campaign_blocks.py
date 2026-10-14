"""Synthetic, equal-size value blocks for the existing crossed bootstrap.

Block independence is a caller-supplied toy assumption, not a qualification.
The scorer still receives the original score side; only value resampling changes.
"""

from __future__ import annotations

import copy
import math
import statistics

from .core import LabRefused, analyze, canonical_sha, validate_panel

SCHEMA = "carbon.dev.score-lab-value-blocks.v1"
POLICIES = frozenset({"REQUIRE_COMPLETE", "EXCLUDE_COMPLETE_BLOCKS"})


def prepare(panel, spec):
    """Construct equal-size complete-block means without changing score inputs."""
    if type(panel) is not dict or panel.get("scope") != "SYNTHETIC_DEVELOPMENT":
        raise LabRefused("value_blocks_require_synthetic")
    validate_panel(panel)
    if (
        type(spec) is not dict
        or set(spec) != {"schema", "label", "groups", "missing_policy"}
        or spec["schema"] != SCHEMA
        or type(spec["label"]) is not str
        or not spec["label"].startswith("ASSUMPTION:")
        or type(spec["groups"]) is not dict
        or not 3 <= len(spec["groups"]) <= 30
        or type(spec["missing_policy"]) is not str
        or spec["missing_policy"] not in POLICIES
    ):
        raise LabRefused("value_blocks_spec")
    groups = spec["groups"]
    if any(
        type(name) is not str
        or not name
        or type(questions) is not list
        or not questions
        or any(type(q) is not str or not q for q in questions)
        for name, questions in groups.items()
    ):
        raise LabRefused("value_blocks_partition")
    flat = [q for questions in groups.values() for q in questions]
    if len(flat) != len(set(flat)) or set(flat) != set(panel["value_questions"]):
        raise LabRefused("value_blocks_partition")
    sizes = {len(questions) for questions in groups.values()}
    if len(sizes) != 1:
        raise LabRefused("value_blocks_unequal_sizes")
    size = next(iter(sizes))
    for member in panel["members"]:
        for value in member["value_losses"].values():
            if value is not None and (
                type(value) not in (int, float) or not math.isfinite(value)
            ):
                raise LabRefused("value_blocks_nonfinite_loss")
    unresolved = {
        q
        for q in panel["value_questions"]
        if any(m["value_losses"][q] is None for m in panel["members"])
    }
    complete = {
        "BLOCK-V-" + canonical_sha(sorted(questions)): sorted(questions)
        for questions in groups.values()
        if not unresolved.intersection(questions)
    }
    if set(complete).intersection(panel["score_questions"]):
        raise LabRefused("value_blocks_identity_collision")
    view = copy.deepcopy(panel)
    view["value_questions"] = {
        block: {"source_questions": questions} for block, questions in complete.items()
    }
    for member in view["members"]:
        original = member["value_losses"]
        member["value_losses"] = {
            block: statistics.fmean(original[q] for q in questions)
            for block, questions in complete.items()
        }
    oracle = panel.get("exact_oracle_losses")
    if oracle is not None:
        if type(oracle) is not dict or any(
            value is not None
            and (type(value) not in (int, float) or not math.isfinite(value))
            for value in oracle.values()
        ):
            raise LabRefused("value_blocks_nonfinite_oracle")
        view["exact_oracle_losses"] = {
            block: (
                statistics.fmean(oracle[q] for q in questions)
                if all(oracle.get(q) is not None for q in questions)
                else None
            )
            for block, questions in complete.items()
        }
    offered = len(flat)
    retained = size * len(complete)
    receipt = {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "spec_sha256": canonical_sha(spec),
        "input_panel_sha256": canonical_sha(panel),
        "analysis_panel_sha256": canonical_sha(view),
        "missing_policy": spec["missing_policy"],
        "offered_questions": offered,
        "questions_per_block": size,
        "offered_blocks": len(groups),
        "complete_blocks_available": len(complete),
        "unresolved_questions": len(unresolved),
        "incomplete_blocks": len(groups) - len(complete),
        "complete_block_questions_available": retained,
        "resolved_questions_in_incomplete_blocks": offered - retained - len(unresolved),
        "complete_question_mask_sha256": canonical_sha(
            sorted(q for questions in complete.values() for q in questions)
        ),
        "estimand": "uniform_questions_conditional_on_complete_equal_size_blocks",
        "independence": "supplied synthetic block assumption; not established",
        "bootstrap_unit": "complete_value_block",
        "scoring_cases": "fixed (conditional)",
    }
    return view, receipt


def evaluate(panel, rule, spec, *, bootstrap=200, seed=20261013):
    """Reuse core analysis: one loss column per complete block, not per case."""
    view, receipt = prepare(panel, spec)
    if not callable(rule):
        raise LabRefused("value_blocks_rule_missing")
    if receipt["complete_blocks_available"] < 3 or (
        spec["missing_policy"] == "REQUIRE_COMPLETE" and receipt["incomplete_blocks"]
    ):
        result = {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": (
                "value_blocks_below_planned_range"
                if receipt["complete_blocks_available"] < 3
                else "value_blocks_incomplete"
            ),
            "source": "SYNTHETIC_DEVELOPMENT",
        }
    else:
        result = analyze(view, rule, bootstrap=bootstrap, seed=seed)
    measured = result["status"] == "MEASURED_DEVELOPMENT"
    receipt["scored_blocks"] = receipt["complete_blocks_available"] if measured else 0
    receipt["scored_questions"] = (
        receipt["complete_block_questions_available"] if measured else 0
    )
    if measured:
        result["value_resampling_units"] = result["value_questions"]
        result["value_questions"] = receipt["scored_questions"]
        result["value_questions_offered"] = receipt["offered_questions"]
    return {**result, "value_block_measurement": receipt}
