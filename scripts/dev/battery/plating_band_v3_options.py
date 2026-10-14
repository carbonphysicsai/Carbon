"""Aggregate public D3 evidence for a prospective plating-reference v3 choice.

Read-only development analysis: no solver call, proposed band, new label or
reference-method adoption. Only the three exact committed public D3 files are
accepted by the CLI. Results never expose case IDs or per-case margins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from scripts.dev.battery.plating_rereference import V2_RULES, v2_label

ROOT = Path(__file__).resolve().parents[3]
D3 = ROOT / "docs/development/evidence/plating-rereference-01/d3-results"
INPUT_SHA256 = {
    "labels-v2-r1.json": "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069",
    "labels.json": "dc1566085226710ed2c729ddc3e77bd5817142b6a12e0f9aa3b04c4c9609fbc6",
    "records.jsonl": "ef8c6260b866a106aa88351079e1789b653e652630e996bfb19ae863cab2bc02",
}


class AnalysisRefused(ValueError):
    """A public-source or evidence-boundary mismatch."""


def _finite(value, *, positive=False):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def _unique(rows):
    ids = [row["case_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AnalysisRefused("duplicate_case_id")
    return {row["case_id"]: row for row in rows}


def analyze(v2, draft, records, *, sensitivity_bands_mv):
    """Return aggregates and explicit unknowns from public development rows."""
    if (
        v2.get("schema") != "carbon.battery.plating-v2-labels.v1"
        or v2.get("version") != "battery-plating-ref-v2"
        or v2.get("decision") != "VALIDATOR-PLATING-REF-V2-02"
        or draft.get("schema") != "carbon.battery.plating-rereference.v1"
        or not isinstance(sensitivity_bands_mv, list)
        or not sensitivity_bands_mv
        or not all(_finite(value) for value in sensitivity_bands_mv)
        or len(sensitivity_bands_mv) != len(set(sensitivity_bands_mv))
    ):
        raise AnalysisRefused("source_or_sensitivity_contract")
    sealed = _unique(v2["rows"])
    old = _unique(draft["rows"])
    if not sealed or any(row["rule"] not in V2_RULES for row in sealed.values()):
        raise AnalysisRefused("unregistered_v2_rule")
    solved = {}
    pending = {}
    for case_id, row in sealed.items():
        if row.get("source") not in ("ev4", "pdd") or row.get("label") not in (
            "FEASIBLE",
            "INFEASIBLE",
            "UNRESOLVED",
        ):
            raise AnalysisRefused("v2_row_contract")
        m160 = row.get("m160_mv")
        if not (
            type(row.get("m20_mv")) in (int, float) and math.isfinite(row["m20_mv"])
        ):
            raise AnalysisRefused("nonfinite_mesh20")
        if m160 is not None and not (
            type(m160) in (int, float) and math.isfinite(m160)
        ):
            raise AnalysisRefused("nonfinite_mesh160")
        expected = v2_label(
            row["m20_mv"] * 1e-3,
            None if m160 is None else m160 * 1e-3,
        )
        if expected != {"rule": row["rule"], "label": row["label"]}:
            raise AnalysisRefused("v2_label_mismatch")
        if row["rule"] == "m160-d3-r1":
            if m160 is None:
                raise AnalysisRefused("missing_mesh160")
            solved[case_id] = row
        elif row["rule"] == "pending-m160-r1":
            pending[case_id] = row
        else:
            raise AnalysisRefused("outside_d3_window")
    if set(old) != set(solved):
        raise AnalysisRefused("draft_solved_identity")
    for case_id, row in solved.items():
        prior = old[case_id]
        if (
            prior["source"] != row["source"]
            or not math.isclose(prior["m160_mv"], row["m160_mv"], abs_tol=1e-9)
            or prior["new_label"] != row["draft_label"]
        ):
            raise AnalysisRefused("draft_solved_mismatch")
    lost = {
        case_id: row
        for case_id, row in solved.items()
        if row["draft_label"] == "FEASIBLE" and row["label"] == "UNRESOLVED"
    }
    sample = _unique(draft["convergence_check"]["rows"])
    orders = []
    for case_id, row in sample.items():
        if case_id not in solved or any(
            type(row.get(key)) not in (int, float) or not math.isfinite(row[key])
            for key in (
                "m40_mv",
                "m80_mv",
                "m160_mv",
                "d80_160_mv",
                "extrapolated_mv",
            )
        ):
            raise AnalysisRefused("convergence_sample_contract")
        p = row.get("observed_order")
        delta = row["m80_mv"] - row["m160_mv"]
        first = row["m40_mv"] - row["m80_mv"]
        if (
            not _finite(p, positive=True)
            or delta <= 0
            or first <= 0
            or not math.isclose(
                row["m160_mv"], solved[case_id]["m160_mv"], abs_tol=1e-9
            )
            or not math.isclose(row["d80_160_mv"], delta, abs_tol=1e-9)
            or not math.isclose(p, math.log2(first / delta), abs_tol=1e-9)
        ):
            raise AnalysisRefused("convergence_sample_mismatch")
        extrapolated = row["m160_mv"] - delta / (2**p - 1)
        if not math.isclose(row.get("extrapolated_mv"), extrapolated, abs_tol=1e-9):
            raise AnalysisRefused("convergence_extrapolation_mismatch")
        orders.append(p)
    if not orders:
        raise AnalysisRefused("no_convergence_sample")
    p_low, p_high = min(orders), max(orders)
    sensitivity = []
    sampled_lost = [sample[case_id] for case_id in lost if case_id in sample]
    for band in sensitivity_bands_mv:
        observed = sum(row["extrapolated_mv"] >= band for row in sampled_lost)
        all_orders = sum(
            row["m160_mv"] - row["d80_160_mv"] / (2**p_low - 1) >= band
            for row in sampled_lost
        )
        sensitivity.append(
            {
                "assumed_extrapolated_band_mv": band,
                "sample_lost_recovered_at_observed_order": observed,
                "sample_lost_recovered_at_worst_observed_order": all_orders,
                "full_46_recovered": None,
            }
        )
    rows_by_mesh = {mesh: [] for mesh in (40, 80, 160, 320)}
    record_ids = {mesh: set() for mesh in rows_by_mesh}
    for row in records:
        mesh = row.get("mesh")
        if (
            mesh not in rows_by_mesh
            or row.get("status") != "OK"
            or not _finite(row.get("cpu_s"), positive=True)
            or row.get("case_id") in record_ids[mesh]
        ):
            raise AnalysisRefused("cost_record_contract")
        record_ids[mesh].add(row["case_id"])
        rows_by_mesh[mesh].append(row["cpu_s"])
    if (
        record_ids[160] != set(solved)
        or record_ids[80] != set(sample)
        or record_ids[40] != set(sample)
        or record_ids[320]
    ):
        raise AnalysisRefused("cost_record_coverage")
    cpu80 = statistics.fmean(rows_by_mesh[80])
    remaining80 = len(solved) - len(sample)
    spread = [
        row["d80_160_mv"] * (1 / (2**p_low - 1) - 1 / (2**p_high - 1))
        for row in sample.values()
    ]
    return {
        "schema": "carbon.dev.plating-band-v3-options.v1",
        "status": "INSUFFICIENT_EVIDENCE_FOR_V3_BAND",
        "basis": "PUBLIC_D3_DEVELOPMENT_ONLY",
        "source_counts": dict(
            sorted(Counter(row["source"] for row in sealed.values()).items())
        ),
        "v2_label_counts": dict(
            sorted(Counter(row["label"] for row in sealed.values()).items())
        ),
        "mesh160_solved": len(solved),
        "mesh160_pending": len(pending),
        "draft_feasible_lost_under_v2": len(lost),
        "lost_with_40_80_160_rungs": len(sampled_lost),
        "lost_without_mesh80": len(lost) - len(sampled_lost),
        "richardson": {
            "observed_order_min": p_low,
            "observed_order_max": p_high,
            "max_extrapolate_interval_width_mv_in_67": max(spread),
            "sensitivity": sensitivity,
            "achievable_band_mv": None,
            "recovered_of_46": None,
            "additional_mesh80_needed_for_solved": remaining80,
            "additional_mesh80_if_pending_103_solved": len(pending),
            "measured_mesh80_mean_cpu_s_in_67": cpu80,
            "measured_mesh80_cpu_h_in_67": sum(rows_by_mesh[80]) / 3600,
            "indicative_additional_mesh80_cpu_h_solved": remaining80 * cpu80 / 3600,
            "indicative_additional_mesh80_cpu_h_all": (remaining80 + len(pending))
            * cpu80
            / 3600,
            "cost_basis": "67 public mesh80 CPU records; extrapolated arithmetic, not a Data Collection estimate or approval",
            "approved_cost": None,
        },
        "mesh320": {
            "successful_public_rungs": len(rows_by_mesh[320]),
            "achievable_band_mv": None,
            "recovered_of_46": None,
            "measured_cpu_h": None,
            "approved_cost": None,
            "memory_requirement": "UNMEASURED; mesh160 reached about 6.3 GB and mesh320 ran out of memory",
        },
        "owner_decision": "HUMAN_INPUT: reference method, route, spend and v3 band",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sensitivity-band-mv",
        type=float,
        action="append",
        required=True,
        help="illustrative extrapolated band in mV; never a registered value",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    inputs = {}
    for name, digest in INPUT_SHA256.items():
        raw = (D3 / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise AnalysisRefused("public_d3_digest_mismatch")
        inputs[name] = (
            [json.loads(line) for line in raw.splitlines()]
            if name.endswith(".jsonl")
            else json.loads(raw)
        )
    report = analyze(
        inputs["labels-v2-r1.json"],
        inputs["labels.json"],
        inputs["records.jsonl"],
        sensitivity_bands_mv=args.sensitivity_band_mv,
    )
    report["public_source_sha256"] = INPUT_SHA256
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_bytes(output.encode("utf-8"))
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
