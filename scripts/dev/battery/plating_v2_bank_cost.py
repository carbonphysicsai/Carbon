"""Public development arithmetic for a prospective v2 Track A bank.

This is not a bank registration, a cost grant, or a reference solve. The caller
supplies the future action-condition count and the public PDD denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from scripts.dev.battery.plating_rereference import CHECK_SHARE, V2_RULES, v2_label

ROOT = Path(__file__).resolve().parents[3]
D3 = ROOT / "docs/development/evidence/plating-rereference-01/d3-results"
INPUT_SHA256 = {
    "labels-v2-r1.json": "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069",
    "records.jsonl": "ef8c6260b866a106aa88351079e1789b653e652630e996bfb19ae863cab2bc02",
}


class CostRefused(ValueError):
    """The source or proposed cost arithmetic is not established."""


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def plan_cost(labels, records, *, pdd_total, action_condition_solves, base_cpu_s=None):
    """Estimate additional v2 refinement CPU using measured public D3 means.

    `pdd_total` is explicit because the full PDD population denominator is not
    registered by the D3 label file. The estimate is never an approved figure.
    """
    if (
        type(pdd_total) is not int
        or type(action_condition_solves) is not int
        or pdd_total <= 0
        or action_condition_solves <= 0
        or (base_cpu_s is not None and (not _finite(base_cpu_s) or base_cpu_s <= 0))
        or labels.get("schema") != "carbon.battery.plating-v2-labels.v1"
        or labels.get("version") != "battery-plating-ref-v2"
        or labels.get("decision") != "VALIDATOR-PLATING-REF-V2-02"
    ):
        raise CostRefused("input_contract")
    rows = labels["rows"]
    ids = [row["case_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise CostRefused("duplicate_case_id")
    sources = Counter()
    solved_ids = set()
    pending_ids = set()
    for row in rows:
        if row.get("rule") not in V2_RULES or row.get("source") not in ("pdd", "ev4"):
            raise CostRefused("v2_rule_or_source")
        m20, m160 = row.get("m20_mv"), row.get("m160_mv")
        if not _finite(m20) or (m160 is not None and not _finite(m160)):
            raise CostRefused("nonfinite_margin")
        if v2_label(m20 * 1e-3, None if m160 is None else m160 * 1e-3) != {
            "label": row.get("label"),
            "rule": row["rule"],
        }:
            raise CostRefused("v2_label_mismatch")
        if row["rule"] == "m160-d3-r1":
            solved_ids.add(row["case_id"])
        elif row["rule"] == "pending-m160-r1":
            pending_ids.add(row["case_id"])
        else:
            raise CostRefused("unexpected_outside_window_row")
        sources[(row["source"], row["rule"])] += 1
    if pdd_total < sum(n for (source, _), n in sources.items() if source == "pdd"):
        raise CostRefused("pdd_denominator_too_small")
    cpu_by_mesh = {40: [], 80: [], 160: []}
    ids_by_mesh = {40: set(), 80: set(), 160: set()}
    for row in records:
        mesh = row.get("mesh")
        if (
            mesh not in cpu_by_mesh
            or row.get("status") != "OK"
            or not _finite(row.get("cpu_s"))
            or row["cpu_s"] <= 0
            or row.get("case_id") in ids_by_mesh[mesh]
        ):
            raise CostRefused("cost_record_contract")
        ids_by_mesh[mesh].add(row["case_id"])
        cpu_by_mesh[mesh].append(row["cpu_s"])
    if (
        ids_by_mesh[160] != solved_ids
        or not ids_by_mesh[40]
        or ids_by_mesh[40] != ids_by_mesh[80]
        or not ids_by_mesh[40] <= solved_ids
    ):
        raise CostRefused("cost_coverage")
    share = sum(n for (source, _), n in sources.items() if source == "pdd") / pdd_total
    fine_cpu_s = statistics.fmean(cpu_by_mesh[160])
    trigger_cpu_s = CHECK_SHARE * (
        statistics.fmean(cpu_by_mesh[40]) + statistics.fmean(cpu_by_mesh[80])
    )
    per_window_cpu_s = fine_cpu_s + trigger_cpu_s
    return {
        "schema": "carbon.dev.plating-v2-bank-cost.v1",
        "status": "DEVELOPMENT_ARITHMETIC_NOT_AN_APPROVED_BUDGET",
        "source_counts": {
            "pdd_solved": sources[("pdd", "m160-d3-r1")],
            "pdd_pending": sources[("pdd", "pending-m160-r1")],
            "ev4_solved": sources[("ev4", "m160-d3-r1")],
            "ev4_pending": sources[("ev4", "pending-m160-r1")],
        },
        "source_denominator": pdd_total,
        "full_v2_window_share": share,
        "action_condition_solves": action_condition_solves,
        "trigger_share": CHECK_SHARE,
        "measured_mean_cpu_s": {
            str(mesh): statistics.fmean(values) for mesh, values in cpu_by_mesh.items()
        },
        "measured_count": {
            str(mesh): len(values) for mesh, values in cpu_by_mesh.items()
        },
        "incremental_plating_cpu_h_at_observed_share": action_condition_solves
        * share
        * per_window_cpu_s
        / 3600,
        "incremental_plating_cpu_h_if_all_in_window": action_condition_solves
        * per_window_cpu_s
        / 3600,
        "base_reference_cpu_h_if_supplied": (
            action_condition_solves * base_cpu_s / 3600
            if base_cpu_s is not None
            else None
        ),
        "cost_basis": "public D3 observed means and explicit PDD denominator; future bank mix and host throughput unmeasured",
        "public_source_sha256": INPUT_SHA256,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdd-total", type=int, required=True)
    parser.add_argument("--action-condition-solves", type=int, required=True)
    parser.add_argument("--base-cpu-s", type=float)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    inputs = {}
    for name, digest in INPUT_SHA256.items():
        raw = (D3 / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise CostRefused("public_d3_digest_mismatch")
        inputs[name] = (
            [json.loads(line) for line in raw.splitlines()]
            if name.endswith(".jsonl")
            else json.loads(raw)
        )
    result = plan_cost(
        inputs["labels-v2-r1.json"],
        inputs["records.jsonl"],
        pdd_total=args.pdd_total,
        action_condition_solves=args.action_condition_solves,
        base_cpu_s=args.base_cpu_s,
    )
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_bytes(output.encode("utf-8"))
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
