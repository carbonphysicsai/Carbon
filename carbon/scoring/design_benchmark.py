"""Pure DEVELOPMENT rich-Design projections through the existing dual core.

Inputs are already native-bound measurements, predictions and references. This
module constructs no model, reads no files and grants no reference acceptance.
It retains the original Physics leg, gates, outcome policy and combination. The
point projection is explicitly partial; only the registered projection requires
all coverage and accepted-interval evidence demanded by ``design_fidelity``.
Neither projection adopts a rule or creates official scoring authority.
"""

from __future__ import annotations

from copy import deepcopy

from carbon.scoring import design_fidelity, dual_score
from carbon.scoring.engine import ScoreEngine

PARTIAL_POINT_DIAGNOSTIC = "PARTIAL_POINT_DIAGNOSTIC"
REGISTERED_COMPONENTS_REQUIRED = "REGISTERED_COMPONENTS_REQUIRED"
_METRIC = "rich_design_benefit"


class DesignBenchmarkRefused(ValueError):
    """An inconsistent input binding, not a candidate's scientific failure."""


def _require(value, reason):
    if not value:
        raise DesignBenchmarkRefused(reason)


def _identity(value):
    # A typed input identity preserves nonfinite candidate/reference separation;
    # it is not the digest of the original prediction file's bytes.
    return design_fidelity.digest(design_fidelity.typed_identity(value))


def _project(policy, reduction, original_pack, original_benchmark, mode):
    measurement = {
        "algorithm": "rich-design-same-core-development-v1",
        "mode": mode,
        "policy": deepcopy(policy),
        "reference_coverage_digest": reduction["reference_coverage_digest"],
        "common_mask_digest": reduction["common_mask_digest"],
        "original_pack_digest": original_pack["pack_digest"],
        "reference_scope": "SUPPLIED_REFERENCE_NOT_QUALIFIED_BY_THIS_PROJECTION",
        "score_adopted": False,
    }
    contract_digest = design_fidelity.digest(measurement)
    body = deepcopy(original_pack)
    del body["pack_digest"]
    body["measurement_contract_digest"] = contract_digest
    body["legs"]["D"] = {
        "minimum": None,
        "components": [
            {
                "metric": _METRIC,
                "unit": "1",
                "transform": "unit_benefit",
                "scale": None,
                "weight": 1.0,
            }
        ],
    }
    pack = dual_score.register_pack(body)
    benchmark = deepcopy(original_benchmark)
    benchmark["measurement_contract_digest"] = contract_digest
    previous = [c["metric"] for c in original_pack["legs"]["D"]["components"]]
    reduced = {row["artifact_digest"]: row for row in reduction["models"]}
    for model in benchmark["models"]:
        row = reduced[model["artifact_digest"]]
        for metric in previous:
            del model["measurements"][metric]
        if row["candidate_issues"]:
            status, value = "CANDIDATE_INVALID", None
        elif row["candidate_selection_outcome"] == "SELECTED_PROVEN_INFEASIBLE":
            # The native gate/outcome remains the authority for inadmissibility.
            outcome = original_pack["decision_policy"].get(model["decision_outcome"])
            _require(
                "FAIL" in model["gates"].values()
                or (outcome is not None and not outcome["eligible"]),
                "unsafe_selection_missing_native_inadmissibility",
            )
            status, value = (
                ("RESOLVED", 0.0)
                if mode == PARTIAL_POINT_DIAGNOSTIC
                else ("NOT_MEASURED", None)
            )
        else:
            value = row[
                (
                    "point_estimate_D"
                    if mode == PARTIAL_POINT_DIAGNOSTIC
                    else "registered_D"
                )
            ]
            status = "RESOLVED" if value is not None else "REFERENCE_UNRESOLVED"
        model["measurements"][_METRIC] = {
            "status": status,
            "value": value,
            "unit": "1",
        }
    result = ScoreEngine.score_dual_benchmark_v4(benchmark, pack)
    if mode == REGISTERED_COMPONENTS_REQUIRED:
        for model in result["models"]:
            if reduced[model["artifact_digest"]]["registered_D"] is None:
                _require(
                    model["score"] is None,
                    "partial_coverage_cannot_produce_registered_score",
                )
    return {
        "label": mode,
        "diagnostic_only": mode == PARTIAL_POINT_DIAGNOSTIC,
        "measurement_contract": measurement,
        "score_pack": pack,
        "benchmark_input": benchmark,
        "score_result": result,
        "official_score": False,
        "score_adopted": False,
    }


def score_design_benchmark(
    policy,
    reference,
    models,
    original_pack,
    original_benchmark,
    *,
    provenance,
    original_result=None,
):
    """Reduce fixed Design evidence and produce both labelled core projections.

    ``provenance`` must bind ``original_pack_digest`` and
    ``original_benchmark_digest``. The latter is canonical typed JSON via
    ``design_fidelity.digest(design_fidelity.typed_identity(benchmark))``, not
    a file-byte hash. Additional source, artifact and full-workflow cost records
    are retained unchanged. If supplied, ``original_result`` must replay exactly.

    Models must match the native benchmark's exact artifact set (no implicit
    cohort intersection); callers may explicitly submit matching subsets of
    both lists. Fixed-reference projection pack identities do not depend on the
    compared model cohort. Input bindings are returned separately from those
    pack identities. The already registered 50/50 weight is required, with its
    original combination and native Physics/gate rules retained.
    """
    _require(type(provenance) is dict, "provenance_required")
    _require(type(original_pack) is dict, "original_pack_required")
    _require(type(original_benchmark) is dict, "original_benchmark_required")
    _require(
        provenance.get("original_pack_digest") == original_pack.get("pack_digest")
        and original_pack.get("pack_digest") is not None,
        "original_pack_binding",
    )
    _require(
        provenance.get("original_benchmark_digest") == _identity(original_benchmark),
        "original_benchmark_binding",
    )
    _require(original_pack.get("value_weight") == 0.5, "original_50_50_required")
    replay = ScoreEngine.score_dual_benchmark_v4(original_benchmark, original_pack)
    if original_result is not None:
        _require(replay == original_result, "original_result_replay")
    _require(type(models) is list and bool(models), "paired_model_identity")
    identities = [m.get("artifact_digest") for m in models if type(m) is dict]
    native = {m["artifact_digest"] for m in original_benchmark["models"]}
    _require(
        len(identities) == len(models)
        and all(type(key) is str for key in identities)
        and len(set(identities)) == len(identities)
        and set(identities) == native,
        "paired_model_identity",
    )
    _require(
        _METRIC not in {c["metric"] for c in original_pack["legs"]["A"]["components"]},
        "design_metric_collides_with_physics",
    )
    reduction = design_fidelity.reduce_design(policy, reference, models)
    projections = {
        mode: _project(policy, reduction, original_pack, original_benchmark, mode)
        for mode in (PARTIAL_POINT_DIAGNOSTIC, REGISTERED_COMPONENTS_REQUIRED)
    }
    return {
        "schema": "carbon.scoring.rich-design-benchmark.v1",
        "scope": original_pack["scope"],
        "reduction": reduction,
        "projections": projections,
        "original": {
            "score_pack": deepcopy(original_pack),
            "benchmark_input": deepcopy(original_benchmark),
            "score_result": replay,
        },
        "provenance": deepcopy(provenance),
        "input_bindings": {
            "policy_digest": reduction["policy_digest"],
            "reference_digest": reduction["reference_coverage_digest"],
            "models_digest": _identity(models),
            "original_pack_digest": original_pack["pack_digest"],
            "original_benchmark_digest": _identity(original_benchmark),
            "digest_basis": "CANONICAL_TYPED_INPUTS_NOT_RAW_FILES",
        },
        "official_score": False,
        "score_adopted": False,
    }
