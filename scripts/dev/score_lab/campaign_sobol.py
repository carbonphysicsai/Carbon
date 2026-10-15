"""Deterministic pick-and-freeze sensitivity on assumed synthetic axes.

This uses independent LHS A/B matrices, Saltelli first-order and Jansen total
estimators. Finite-sample estimates are intentionally not clipped to [0, 1].
No real Challenge or independent holdout is read here.
"""

from __future__ import annotations

import copy
import math
import statistics

from . import campaign_sweep, physics
from .core import LabRefused, canonical_sha

PLAN_SCHEMA = "carbon.dev.score-lab-sobol-plan.v1"
RESULT_SCHEMA = "carbon.dev.score-lab-sobol-results.v1"
SCOPES = ("in_range", "shifted", "extrapolated", "neighbourhood_blend")


def _sweep(plan, seed):
    return {
        "schema": campaign_sweep.SCHEMA,
        "seed": seed,
        "count": plan["count"],
        "base_config": plan["base_config"],
        "axes": plan["axes"],
    }


def validate(plan):
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != PLAN_SCHEMA
        or type(plan.get("seed")) is not int
        or plan["seed"] < 0
        or type(plan.get("count")) is not int
        or plan["count"] < 2
        or type(plan.get("switch_index")) is not int
        or plan["switch_index"] < 0
        or plan.get("scope") not in SCOPES
    ):
        raise LabRefused("sobol_plan")
    campaign_sweep.validate(_sweep(plan, plan["seed"]))
    if plan["switch_index"] >= len(plan["base_config"]["physics_sweep"]):
        raise LabRefused("sobol_switch")
    return plan


def prepare(plan, *, shard=0, shards=1):
    """Construct replayable A, B and A-with-one-B-axis hybrid toy configs."""
    validate(plan)
    a = list(campaign_sweep.sample(_sweep(plan, plan["seed"])))
    b = list(campaign_sweep.sample(_sweep(plan, plan["seed"] + 1)))
    if (
        type(shards) is not int
        or shards < 1
        or type(shard) is not int
        or not 0 <= shard < shards
    ):
        raise LabRefused("sobol_shard")
    rows = []
    for index in range(shard, plan["count"], shards):
        hybrids = {}
        for axis in plan["axes"]:
            path = axis["path"]
            config = copy.deepcopy(a[index]["config"])
            node, key = campaign_sweep._target(config, path)
            node[key] = campaign_sweep._value(b[index]["config"], path)
            try:
                physics.validate_config(config)
            except LabRefused:
                raise LabRefused("sobol_hybrid_invalid") from None
            hybrids[path] = config
        rows.append(
            {
                "index": index,
                "A": a[index]["config"],
                "B": b[index]["config"],
                "AB": hybrids,
            }
        )
    return {
        "schema": PLAN_SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": canonical_sha(plan),
        "plan": plan,
        "shard": shard,
        "shards": shards,
        "rows": rows,
    }


def evaluate(prepared, candidate_id, spec, *, candidates_sha256):
    """Evaluate one frozen candidate and one switch/scope on a complete shard."""
    if not isinstance(prepared, dict) or prepared.get("schema") != PLAN_SCHEMA:
        raise LabRefused("sobol_prepared")
    plan = prepared.get("plan")
    if canonical_sha(plan) != prepared.get("plan_sha256") or prepared != prepare(
        plan, shard=prepared.get("shard"), shards=prepared.get("shards")
    ):
        raise LabRefused("sobol_prepared_replay")
    if (
        not isinstance(candidate_id, str)
        or not candidate_id
        or not isinstance(spec, dict)
        or not callable(spec.get("rule"))
    ):
        raise LabRefused("sobol_candidate")
    rows = []

    def tau(config):
        result = physics.evaluate(config, {candidate_id: spec}, candidates_sha256)
        match = next(
            row
            for row in result["rows"]
            if row["candidate"] == candidate_id
            and row["switch_index"] == plan["switch_index"]
        )
        return match["tau"][plan["scope"]]

    for item in prepared["rows"]:
        rows.append(
            {
                "index": item["index"],
                "A": tau(item["A"]),
                "B": tau(item["B"]),
                "AB": {name: tau(config) for name, config in item["AB"].items()},
            }
        )
    return {
        "schema": RESULT_SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": prepared["plan_sha256"],
        "plan": plan,
        "candidate": candidate_id,
        "candidates_sha256": candidates_sha256,
        "shard": prepared["shard"],
        "shards": prepared["shards"],
        "rows": rows,
    }


def aggregate(shards):
    """Require every matched A/B/AB row before computing raw estimators."""
    if not isinstance(shards, list) or not shards:
        raise LabRefused("sobol_shards_missing")
    first = shards[0]
    if not isinstance(first, dict) or first.get("schema") != RESULT_SCHEMA:
        raise LabRefused("sobol_result_schema")
    plan = validate(first.get("plan"))
    identity = (
        first.get("plan_sha256"),
        first.get("candidate"),
        first.get("candidates_sha256"),
        first.get("shards"),
    )
    if (
        identity[0] != canonical_sha(plan)
        or type(identity[3]) is not int
        or identity[3] < 1
    ):
        raise LabRefused("sobol_identity")
    by_index = {}
    seen_shards = set()
    names = {axis["path"] for axis in plan["axes"]}
    for shard in shards:
        if (
            not isinstance(shard, dict)
            or shard.get("schema") != RESULT_SCHEMA
            or shard.get("scope") != "SYNTHETIC_DEVELOPMENT"
            or (
                shard.get("plan_sha256"),
                shard.get("candidate"),
                shard.get("candidates_sha256"),
                shard.get("shards"),
            )
            != identity
            or shard.get("plan") != plan
            or type(shard.get("shard")) is not int
            or not 0 <= shard["shard"] < identity[3]
            or shard["shard"] in seen_shards
            or not isinstance(shard.get("rows"), list)
        ):
            raise LabRefused("sobol_shard_identity")
        seen_shards.add(shard["shard"])
        expected = list(range(shard["shard"], plan["count"], identity[3]))
        if any(not isinstance(row, dict) for row in shard["rows"]):
            raise LabRefused("sobol_shard_rows")
        if [row.get("index") for row in shard["rows"]] != expected:
            raise LabRefused("sobol_shard_indices")
        for row in shard["rows"]:
            if not isinstance(row.get("AB"), dict) or set(row["AB"]) != names:
                raise LabRefused("sobol_hybrids_missing")
            by_index[row["index"]] = row
    if seen_shards != set(range(identity[3])) or set(by_index) != set(
        range(plan["count"])
    ):
        raise LabRefused("sobol_incomplete")
    rows = [by_index[index] for index in range(plan["count"])]
    values = [
        value for row in rows for value in (row["A"], row["B"], *row["AB"].values())
    ]
    if any(value is None for value in values):
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "unresolved_candidate_profile",
            "unresolved_values": sum(value is None for value in values),
        }
    if any(
        type(value) not in (int, float) or not math.isfinite(value) for value in values
    ):
        raise LabRefused("sobol_nonfinite")
    variance = statistics.variance(
        [row["A"] for row in rows] + [row["B"] for row in rows]
    )
    if variance == 0:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "zero_response_variance"}
    indices = {}
    for name in sorted(names):
        first_order = (
            statistics.fmean(row["B"] * (row["AB"][name] - row["A"]) for row in rows)
            / variance
        )
        total_order = statistics.fmean(
            (row["A"] - row["AB"][name]) ** 2 for row in rows
        ) / (2 * variance)
        indices[name] = {"first_order_raw": first_order, "total_order_raw": total_order}
    return {
        "status": "MEASURED_SYNTHETIC_DEVELOPMENT",
        "schema": "carbon.dev.score-lab-sobol-atlas.v1",
        "plan_sha256": identity[0],
        "candidate": identity[1],
        "candidates_sha256": identity[2],
        "scope": plan["scope"],
        "switch_index": plan["switch_index"],
        "matched_pairs": plan["count"],
        "response_variance": variance,
        "estimator": "SALTELLI_FIRST_ORDER_JANSEN_TOTAL_ORDER_RAW",
        "indices": indices,
    }
