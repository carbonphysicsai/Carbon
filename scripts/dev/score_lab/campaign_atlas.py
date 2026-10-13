"""Pure descriptive aggregation of complete synthetic Score Lab LHS shards.

LHS associations are not Sobol indices and cannot establish causal effects.
No rule is selected from development profiles here.
"""

from __future__ import annotations

import math
import statistics

from .core import LabRefused

SCHEMA = "carbon.dev.score-lab-synthetic-sweep-results.v1"


def _median(values):
    return statistics.median(values) if values else None


def _worst_tenth(values):
    if not values:
        return None
    n = max(1, math.ceil(len(values) / 10))
    return statistics.fmean(sorted(values)[:n])


def aggregate(shards):
    """Require all expected profiles exactly once before reporting an atlas."""
    if not isinstance(shards, list) or not shards:
        raise LabRefused("atlas_shards_missing")
    first = shards[0]
    keys = ("plan_sha256", "candidates_sha256", "component_spec_sha256", "count")
    if (
        not isinstance(first, dict)
        or first.get("schema") != SCHEMA
        or first.get("scope") != "SYNTHETIC_DEVELOPMENT"
        or type(first.get("count")) is not int
        or first["count"] < 1
    ):
        raise LabRefused("atlas_schema")
    identity = tuple(first.get(key) for key in keys)
    by_index = {}
    for shard in shards:
        if (
            not isinstance(shard, dict)
            or shard.get("schema") != SCHEMA
            or shard.get("scope") != "SYNTHETIC_DEVELOPMENT"
            or tuple(shard.get(key) for key in keys) != identity
            or not isinstance(shard.get("rows"), list)
        ):
            raise LabRefused("atlas_identity")
        for row in shard["rows"]:
            if not isinstance(row, dict) or type(row.get("index")) is not int:
                raise LabRefused("atlas_row")
            index = row["index"]
            if index in by_index:
                raise LabRefused("atlas_duplicate_index")
            by_index[index] = row
    if set(by_index) != set(range(first["count"])):
        raise LabRefused("atlas_incomplete")
    rows = [by_index[index] for index in range(first["count"])]
    candidate_rows = {}
    for profile in rows:
        if not isinstance(profile.get("rows"), list):
            raise LabRefused("atlas_profile")
        for outcome in profile["rows"]:
            if (
                not isinstance(outcome, dict)
                or not isinstance(outcome.get("candidate"), str)
                or type(outcome.get("switch_index")) is not int
                or not isinstance(outcome.get("tau"), dict)
                or not isinstance(outcome.get("top1_regret"), dict)
                or not isinstance(outcome.get("gamer_top_half"), dict)
                or type(outcome.get("good_wrongly_excluded")) is not int
            ):
                raise LabRefused("atlas_outcome")
            key = (outcome["candidate"], outcome["switch_index"])
            if key in candidate_rows and any(
                recorded_index == profile["index"]
                for recorded_index, _ in candidate_rows[key]
            ):
                raise LabRefused("atlas_duplicate_outcome")
            candidate_rows.setdefault(key, []).append((profile["index"], outcome))
    if not candidate_rows:
        raise LabRefused("atlas_outcome_missing")
    summaries = []
    for (candidate, switch), observations in sorted(candidate_rows.items()):
        if len(observations) != first["count"]:
            raise LabRefused("atlas_outcome_incomplete")
        scopes = ("in_range", "shifted", "extrapolated", "neighbourhood_blend")
        try:
            scope_stats = {
                scope: {
                    "measured_tau": len(
                        [
                            value
                            for _, outcome in observations
                            if (value := outcome["tau"][scope]) is not None
                        ]
                    ),
                    "median_tau": _median(
                        [
                            value
                            for _, outcome in observations
                            if (value := outcome["tau"][scope]) is not None
                        ]
                    ),
                    "worst_tenth_tau": _worst_tenth(
                        [
                            value
                            for _, outcome in observations
                            if (value := outcome["tau"][scope]) is not None
                        ]
                    ),
                    "median_top1_regret": _median(
                        [
                            value
                            for _, outcome in observations
                            if (value := outcome["top1_regret"][scope]) is not None
                        ]
                    ),
                }
                for scope in scopes
            }
        except KeyError:
            raise LabRefused("atlas_scope_missing") from None
        summaries.append(
            {
                "candidate": candidate,
                "switch_index": switch,
                "profiles": len(observations),
                "scope_stats": scope_stats,
                "gamer_top_half_profiles": sum(
                    bool(outcome["gamer_top_half"]["neighbourhood_blend"])
                    for _, outcome in observations
                ),
                "good_wrongly_excluded_total": sum(
                    outcome["good_wrongly_excluded"] for _, outcome in observations
                ),
            }
        )
    return {
        "schema": "carbon.dev.score-lab-synthetic-atlas.v1",
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": first["plan_sha256"],
        "candidates_sha256": first["candidates_sha256"],
        "component_spec_sha256": first["component_spec_sha256"],
        "profiles": len(rows),
        "sobol_indices": None,
        "sobol_reason": "LHS sample lacks independent Saltelli A/B matrices",
        "candidate_switch_summaries": summaries,
        "selection": None,
    }
