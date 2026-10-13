"""Deterministic Latin-hypercube plans for the synthetic Score Lab tranche.

Axes and ranges are supplied by the caller as toy ASSUMPTION settings. This
module generates configs only; it never runs a solver or opens a holdout.
"""

from __future__ import annotations

import copy
import hashlib
import math
import random

from . import physics
from .core import LabRefused, canonical_sha

SCHEMA = "carbon.dev.score-lab-synthetic-sweep.v1"


def _rng(seed, path):
    key = hashlib.sha256(f"{seed}:{path}".encode()).digest()
    return random.Random(int.from_bytes(key[:8], "big"))


def _target(config, path):
    if type(path) is not str or not path or path.startswith("."):
        raise LabRefused("sweep_axis_path")
    parts = path.split(".")
    node = config
    for part in parts[:-1]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdecimal() and int(part) < len(node):
            node = node[int(part)]
        else:
            raise LabRefused("sweep_axis_path")
    key = parts[-1]
    if isinstance(node, dict) and key in node:
        return node, key
    if isinstance(node, list) and key.isdecimal() and int(key) < len(node):
        return node, int(key)
    raise LabRefused("sweep_axis_path")


def _value(config, path):
    node, key = _target(config, path)
    return node[key]


def validate(plan):
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != SCHEMA
        or type(plan.get("seed")) is not int
        or plan["seed"] < 0
        or type(plan.get("count")) is not int
        or plan["count"] < 1
        or not isinstance(plan.get("base_config"), dict)
        or not isinstance(plan.get("axes"), list)
        or not plan["axes"]
    ):
        raise LabRefused("sweep_plan")
    physics.validate_config(plan["base_config"])
    names = []
    for axis in plan["axes"]:
        if not isinstance(axis, dict):
            raise LabRefused("sweep_axis")
        path, kind = axis.get("path"), axis.get("kind")
        _target(plan["base_config"], path)
        names.append(path)
        if kind == "choices":
            values = axis.get("values")
            if not isinstance(values, list) or not values:
                raise LabRefused("sweep_axis_values")
        elif kind in ("linear", "log"):
            low, high = axis.get("low"), axis.get("high")
            if (
                type(low) not in (int, float)
                or type(high) not in (int, float)
                or not math.isfinite(low)
                or not math.isfinite(high)
                or not low < high
                or (kind == "log" and low <= 0)
            ):
                raise LabRefused("sweep_axis_range")
        else:
            raise LabRefused("sweep_axis_kind")
    if len(set(names)) != len(names):
        raise LabRefused("sweep_axis_duplicate")
    return plan


def sample(plan, *, shard=0, shards=1):
    """Yield deterministic disjoint shard rows, one stratum per axis and draw."""
    validate(plan)
    if (
        type(shard) is not int
        or type(shards) is not int
        or shards < 1
        or not 0 <= shard < shards
    ):
        raise LabRefused("sweep_shard")
    count = plan["count"]
    streams = []
    for axis in plan["axes"]:
        rng = _rng(plan["seed"], axis["path"])
        order = list(range(count))
        rng.shuffle(order)
        streams.append((axis, [(cell + rng.random()) / count for cell in order]))
    for index in range(shard, count, shards):
        config = copy.deepcopy(plan["base_config"])
        for axis, quantiles in streams:
            u = quantiles[index]
            if axis["kind"] == "choices":
                choices = axis["values"]
                value = choices[min(len(choices) - 1, int(u * len(choices)))]
            elif axis["kind"] == "linear":
                value = axis["low"] + u * (axis["high"] - axis["low"])
            else:
                value = math.exp(
                    math.log(axis["low"])
                    + u * (math.log(axis["high"]) - math.log(axis["low"]))
                )
            node, key = _target(config, axis["path"])
            node[key] = value
        try:
            physics.validate_config(config)
        except LabRefused:
            raise LabRefused("sweep_sample_invalid") from None
        yield {"index": index, "config_sha256": canonical_sha(config), "config": config}


def summary(plan, *, shard=0, shards=1):
    rows = list(sample(plan, shard=shard, shards=shards))
    return {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": canonical_sha(plan),
        "plan": plan,
        "seed": plan["seed"],
        "count": plan["count"],
        "shard": shard,
        "shards": shards,
        "axes": plan["axes"],
        "rows": rows,
    }


def evaluate(plan, specs, digest, *, shard=0, shards=1, component_spec=None):
    """Measure a disjoint synthetic shard; no real panel or held-out input."""
    return evaluate_summary(
        summary(plan, shard=shard, shards=shards),
        specs,
        digest,
        component_spec=component_spec,
    )


def evaluate_summary(prepared, specs, digest, *, component_spec=None):
    """Consume only digest-checked prepared toy configs from campaign-plan."""
    if (
        not isinstance(prepared, dict)
        or prepared.get("schema") != SCHEMA
        or prepared.get("scope") != "SYNTHETIC_DEVELOPMENT"
        or type(prepared.get("count")) is not int
        or prepared["count"] < 1
        or type(prepared.get("shard")) is not int
        or type(prepared.get("shards")) is not int
        or prepared["shards"] < 1
        or not 0 <= prepared["shard"] < prepared["shards"]
        or not isinstance(prepared.get("plan_sha256"), str)
        or not isinstance(prepared.get("plan"), dict)
        or not isinstance(prepared.get("axes"), list)
        or not isinstance(prepared.get("rows"), list)
    ):
        raise LabRefused("sweep_prepared_invalid")
    if canonical_sha(prepared["plan"]) != prepared["plan_sha256"]:
        raise LabRefused("sweep_prepared_plan_digest")
    if prepared["count"] != prepared["plan"].get("count"):
        raise LabRefused("sweep_prepared_count")
    if prepared["axes"] != prepared["plan"].get("axes"):
        raise LabRefused("sweep_prepared_axes")
    expected = list(range(prepared["shard"], prepared["count"], prepared["shards"]))
    if any(not isinstance(item, dict) for item in prepared["rows"]):
        raise LabRefused("sweep_prepared_rows")
    if [item.get("index") for item in prepared["rows"]] != expected:
        raise LabRefused("sweep_prepared_indices")
    if prepared["rows"] != list(
        sample(
            prepared["plan"],
            shard=prepared["shard"],
            shards=prepared["shards"],
        )
    ):
        raise LabRefused("sweep_prepared_replay")
    rows = []
    for item in prepared["rows"]:
        physics.validate_config(item["config"])
        outcome = physics.evaluate(
            item["config"], specs, digest, component_spec=component_spec
        )
        rows.append(
            {
                "index": item["index"],
                "config_sha256": item["config_sha256"],
                "axes": {
                    axis["path"]: _value(item["config"], axis["path"])
                    for axis in prepared["axes"]
                },
                "measured_rows": outcome["measured_rows"],
                "rows": outcome["rows"],
            }
        )
    return {
        "schema": "carbon.dev.score-lab-synthetic-sweep-results.v1",
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": prepared["plan_sha256"],
        "candidates_sha256": digest,
        "component_spec_sha256": (
            canonical_sha(component_spec) if component_spec is not None else None
        ),
        "shard": prepared["shard"],
        "shards": prepared["shards"],
        "rows": rows,
    }
