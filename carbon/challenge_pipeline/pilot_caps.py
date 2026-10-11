"""Pure all-in pilot planning. No provider access, solver or dispatch authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "carbon.pilot-cap-plan.v2"
RATE_CENTS = 120  # USD0.96/h * <=EUR1.25/USD including tax/FX/payment fees
EXTRAS_CENTS = 20
PROBE_SECONDS = 2400
LEASE_SECONDS = 8 * 3600
TAIL_SECONDS = 600  # export + confirmed termination 420, safety 180
HOST_BOUNDS = {
    "runpod-cpu-64": (120, 20, 60, 2400, 28800, 1500, 600, 32, 64000),
    "runpod-cpu-256": (220, 20, 60, 1260, 15600, 360, 600, 32, 256000),
    "hetzner-ccx43": (53, 40, 3600, 3600, 64800, 1500, 900, 16, 64000),
}


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name}: bounded integer required")
    return value


def billed_cost(
    seconds, *, rate_cents=RATE_CENTS, extras_cents=EXTRAS_CENTS, quantum_s=60
):
    """Cents rounded OUTWARD; allocation through confirmed termination/deletion.

    Minute rounding is conservative even when the provider meters seconds.
    The rate is a tax/FX/payment-inclusive EUR ceiling, not a USD spot quote.
    """
    integer(seconds, "lifetime", 1)
    integer(rate_cents, "inclusive hourly quote", 1)
    integer(extras_cents, "all other charges")
    integer(quantum_s, "billing quantum", 1)
    billed_seconds = ((seconds + quantum_s - 1) // quantum_s) * quantum_s
    return (billed_seconds * rate_cents + 3599) // 3600 + extras_cents


def host(plan, profile=None):
    profile = profile or plan["primary_host"]
    if profile not in HOST_BOUNDS or profile not in plan["hosts"]:
        raise ValueError("registered host profile required")
    return plan["hosts"][profile]


def host_cost(seconds, h):
    return billed_cost(
        seconds,
        rate_cents=h["inclusive_hourly_ceiling_cents"],
        extras_cents=h["all_other_charges_ceiling_cents"],
        quantum_s=h["billing_quantum_s"],
    )


def validate(plan):
    if (
        plan.get("schema") != SCHEMA
        or plan.get("dispatch_allowed") is not False
        or plan.get("solver_runs_permitted") is not False
    ):
        raise ValueError("plan-only schema required")
    if plan["primary_host"] != "runpod-cpu-64" or set(plan["hosts"]) != set(
        HOST_BOUNDS
    ):
        raise ValueError("RunPod primary and exact alternatives required")
    keys = (
        "inclusive_hourly_ceiling_cents",
        "all_other_charges_ceiling_cents",
        "billing_quantum_s",
        "probe_lifetime_s",
        "total_lifetime_s_including_probe",
        "single_probe_case_wall_cap_s",
        "tail_allowance_s",
        "host_vcpus",
        "host_ram_mb",
    )
    for profile, bounds in HOST_BOUNDS.items():
        h = host(plan, profile)
        if any(type(h[k]) is not int or h[k] != b for k, b in zip(keys, bounds)):
            raise ValueError("new host bound needs prospective plan revision")
        if (
            h["setup_allowance_s"]
            + h["single_probe_case_wall_cap_s"]
            + h["tail_allowance_s"]
            != h["probe_lifetime_s"]
        ):
            raise ValueError("complete probe lifecycle accounting required")
        if (
            host_cost(h["probe_lifetime_s"], h) != h["probe_upper_cents"]
            or host_cost(h["total_lifetime_s_including_probe"], h)
            != h["total_upper_cents"]
        ):
            raise ValueError("reported bound differs from arithmetic")
        if h["probe_upper_cents"] > 100 or h["total_upper_cents"] > 1000:
            raise ValueError("lifecycle cap proof fails")
    names = {p["family"] for p in plan["families"]}
    if len(names) != 6 or names != {
        "backward-facing-step",
        "metagrating-3d",
        "f13",
        "bolted-joint",
        "package-warpage",
        "f17",
    }:
        raise ValueError("exact six non-transferable family plans required")
    for p in plan["families"]:
        if p["scope"] not in ("PUBLIC_DEVELOPMENT", "REPRESENTATIVE"):
            raise ValueError("public/representative proposals only")
        if p["allocated_vcpus"] not in (1, 4) or p["rss_limit_mb"] > 48000:
            raise ValueError("serial CPU and bounded memory required")
        if not 1 <= p["probe_wall_hypothesis_s"] <= 1500:
            raise ValueError("single-case probe must fit its lifecycle")
        if p["exact_registered_manifest"] is not None:
            raise ValueError("this proposal does not earn registration")
        if p["retries"] != 0:
            raise ValueError("no unapproved retries")
        for job in p["follow_on"]:
            integer(job["probe_runtime_multiplier"], "hypothesis multiplier", 1)
    return plan


def size_from_probe(plan, family, receipt):
    """Ordered prefix only; a timeout is incomplete evidence, not cheap C1.

    Public measured receipt is a planning input, NOT authorization or verified
    store/host presence. No launch command is produced. Unknown fields refused.
    """
    validate(plan)
    fields = {
        "family",
        "scope",
        "outcome",
        "complete_task",
        "probe_wall_s",
        "lease_elapsed_s",
        "peak_rss_mb",
        "allocated_vcpus",
        "host_identity",
        "host_profile",
        "image_digest",
        "solver_tree_digest",
        "tuple_digest",
        "manifest_digest",
        "ledger_digest",
    }
    if type(receipt) is not dict or set(receipt) != fields:
        raise ValueError("closed public measured probe receipt required")
    p = next((p for p in plan["families"] if p["family"] == family), None)
    if p is None or receipt["family"] != family or receipt["scope"] != p["scope"]:
        raise ValueError("family/scope mismatch")
    if receipt["outcome"] != "COMPLETED" or receipt["complete_task"] is not True:
        raise ValueError("partial/failed probe cannot size a complete task")
    h = host(plan, receipt["host_profile"])
    for key in (
        "image_digest",
        "solver_tree_digest",
        "tuple_digest",
        "manifest_digest",
        "ledger_digest",
    ):
        value = receipt[key]
        if (
            type(value) is not str
            or not value.startswith("sha256:")
            or len(value) != 71
            or any(c not in "0123456789abcdef" for c in value[7:])
        ):
            raise ValueError("exact public pins and retained ledger required")
    if type(receipt["host_identity"]) is not str or not receipt["host_identity"]:
        raise ValueError("same-host identity required")
    elapsed = integer(receipt["lease_elapsed_s"], "elapsed", 1)
    runtime = integer(receipt["probe_wall_s"], "probe wall", 1)
    rss = integer(receipt["peak_rss_mb"], "peak RSS", 1)
    if (
        runtime > h["single_probe_case_wall_cap_s"]
        or elapsed < runtime
        or elapsed > h["probe_lifetime_s"] - h["tail_allowance_s"]
        or rss > p["rss_limit_mb"]
        or receipt["allocated_vcpus"] != p["allocated_vcpus"]
    ):
        raise ValueError("probe resource/lifecycle bound exceeded")
    remaining = h["total_lifetime_s_including_probe"] - elapsed - h["tail_allowance_s"]
    selected = []
    for job in p["follow_on"]:
        # 2x measured runtime is conservative PLANNING, not an observed quantile.
        wall_cap = runtime * 2 * job["probe_runtime_multiplier"]
        if wall_cap > remaining:
            break
        selected.append({**job, "wall_cap_s": wall_cap})
        remaining -= wall_cap
    last_end = elapsed + sum(j["wall_cap_s"] for j in selected) + h["tail_allowance_s"]
    return {
        "family": family,
        "scope": p["scope"],
        "dispatch_allowed": False,
        "status": (
            "PLAN_ONLY" if len(selected) == len(p["follow_on"]) else "PARTIAL_PLAN"
        ),
        "same_host_and_pins_required": {
            k: receipt[k]
            for k in (
                "host_identity",
                "host_profile",
                "allocated_vcpus",
                "image_digest",
                "solver_tree_digest",
                "manifest_digest",
            )
        },
        "selected_ordered_jobs": selected,
        "omitted_jobs": p["follow_on"][len(selected) :],
        "all_in_upper_cents": host_cost(last_end, h),
        "lease_deadline_s_from_allocation": h["total_lifetime_s_including_probe"],
        "termination_required": True,
        "p95_cost_status": "NOT_ESTIMATED_FROM_ONE_CASE",
        "release_holds": plan["release_holds"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--family")
    parser.add_argument("--probe", type=Path)
    args = parser.parse_args()
    plan = validate(json.loads(args.plan.read_text(encoding="utf-8")))
    if args.family and args.probe:
        output = size_from_probe(plan, args.family, json.loads(args.probe.read_text()))
    elif args.family or args.probe:
        parser.error("--family and --probe are required together")
    else:
        output = {
            "families": len(plan["families"]),
            "dispatch_allowed": False,
            "primary_host": plan["primary_host"],
            "host_bounds": {
                profile: {
                    "probe_upper_cents": h["probe_upper_cents"],
                    "total_upper_cents": h["total_upper_cents"],
                }
                for profile, h in plan["hosts"].items()
            },
        }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
