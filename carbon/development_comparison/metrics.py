"""Descriptive aggregation only; this module creates no scientific decision."""

from __future__ import annotations

import math
import statistics

from carbon.measurement_runtime.model import MEASUREMENT_IDS, PHYSICS_IDS
from carbon.orchestration.development_feedback import aggregate_development_feedback

REPORT_SCHEMA = "carbon.cw1.development-comparison-report.v1"
METRICS = (*MEASUREMENT_IDS, *PHYSICS_IDS)


def descriptive_metrics(baseline, challenger, *, expected_cases):
    # Reuse the disclosure owner's complete rectangular-cohort admission.
    for cohorts in (baseline, challenger):
        aggregate_development_feedback(cohorts, expected_cases=expected_cases)
    output = {}
    for role_index, role in enumerate(("EVAL", "STRESS")):
        matrices = []
        censoring = []
        for cohorts in (baseline, challenger):
            values = {metric: {} for metric in METRICS}
            counts = {
                "candidate_half_time_censored": 0,
                "reference_half_time_censored": 0,
            }
            for request, result in cohorts[role_index][1]:
                for item in result.measurements:
                    values[item.measurement_id][
                        (request.case_digest, request.candidate_replica_id)
                    ] = item.normalized_error
                for item in result.physics:
                    values[item.physics_id][
                        (request.case_digest, request.candidate_replica_id)
                    ] = item.normalized_defect
                diagnostics = dict(result.diagnostics)
                for key in counts:
                    if diagnostics.get(key) not in (0, 1):
                        raise ValueError(
                            "explicit half-time censor observations required"
                        )
                    counts[key] += diagnostics[key]
            if any(
                len(v) != 36
                or any(
                    type(x) is not float or not math.isfinite(x) or x < 0
                    for x in v.values()
                )
                for v in values.values()
            ):
                raise ValueError("complete finite normalized measurements required")
            matrices.append(values)
            censoring.append(counts)
        metrics = {}
        for metric in METRICS:
            summaries = []
            case_means = []
            for values in matrices:
                cells = values[metric]
                replica_means = [
                    math.fsum(
                        cells[(case, f"reconstruction-replica-{replica}")]
                        for case in sorted(expected_cases[role])
                    )
                    / 12
                    for replica in range(3)
                ]
                means = {
                    case: math.fsum(
                        cells[(case, f"reconstruction-replica-{replica}")]
                        for replica in range(3)
                    )
                    / 3
                    for case in expected_cases[role]
                }
                case_means.append(means)
                summaries.append(
                    {
                        "mean": math.fsum(replica_means) / 3,
                        "replica_means": replica_means,
                        "replica_mean_sample_sd": statistics.stdev(replica_means),
                        "case_mean_sample_sd": statistics.stdev(means.values()),
                    }
                )
            differences = [
                case_means[1][case] - case_means[0][case]
                for case in sorted(expected_cases[role])
            ]
            metrics[metric] = {
                "direction": "LOWER_OBSERVED_ERROR_OR_DEFECT",
                "baseline": summaries[0],
                "challenger": summaries[1],
                "difference_challenger_minus_baseline": summaries[1]["mean"]
                - summaries[0]["mean"],
                "paired_case_mean_difference_sample_sd": statistics.stdev(differences),
                "interval": None,
                "accepted_improvement": None,
            }
        output[role] = {
            "cases": 12,
            "replicas": 3,
            "metrics": metrics,
            "half_time": {
                "interpretation": "HORIZON_CLIPPED_DESCRIPTIVE_ERROR",
                "baseline_censor_counts": censoring[0],
                "challenger_censor_counts": censoring[1],
                "observation_count_per_source": 36,
            },
        }
    return output


def report_document(*, contract_digest, baseline, challenger, metrics):
    return {
        "schema": REPORT_SCHEMA,
        "contract_digest": contract_digest,
        "baseline": baseline,
        "challenger": challenger,
        "cohorts": metrics,
        "disposition": "INDETERMINATE_NO_ACCEPTANCE_RULE",
        "accepted_improvement": None,
        "equivalence": None,
        "score": None,
        "missing_decision": "AUTHORIZED_DEVELOPMENT_ADMISSIBILITY_IMPROVEMENT_AND_EQUIVALENCE_RULE",
        "limitations": [
            "SEEN_ADAPTIVE_DEVELOPMENT_SUBSET_NOT_CONFIRMATORY",
            "CASES_AND_RECONSTRUCTION_REPLICAS_ARE_DISTINCT_DEPENDENCE_DIMENSIONS",
            "THREE_REPLICAS_SUPPORT_LIMITED_DESCRIPTIVE_SPREAD_ONLY",
            "NO_QUALIFIED_UNCERTAINTY_OR_SCIENTIFIC_QUALIFICATION",
            "REPLICA_INDICES_ARE_NOT_PAIRED_RANDOM_SEEDS",
        ],
        "eligibility": {
            "official": False,
            "protected": False,
            "score": False,
            "settlement": False,
            "reward": False,
            "all_burn_publisher": False,
            "winner_weights": False,
        },
    }
