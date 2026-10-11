"""Pure all-in pilot planning. No provider access, solver or dispatch authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "carbon.pilot-cap-plan.v1"
RATE_CENTS = 53
EXTRAS_CENTS = 40
PROBE_SECONDS = 3600
LEASE_SECONDS = 18 * 3600
TAIL_SECONDS = 900  # retained export/deletion 600 + safety 300


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name}: bounded integer required")
    return value


def billed_cost(seconds, *, rate_cents=RATE_CENTS, extras_cents=EXTRAS_CENTS):
    """Cents rounded OUTWARD; lifetime includes setup, idle and deletion."""
    integer(seconds, "lifetime", 1)
    integer(rate_cents, "inclusive hourly quote", 1)
    integer(extras_cents, "all other charges")
    return ((seconds + 3599) // 3600) * rate_cents + extras_cents


def validate(plan):
    if (
        plan.get("schema") != SCHEMA
        or plan.get("dispatch_allowed") is not False
        or plan.get("solver_runs_permitted") is not False
    ):
        raise ValueError("plan-only schema required")
    if plan["host"]["inclusive_hourly_ceiling_cents"] != RATE_CENTS:
        raise ValueError("new quote ceiling needs prospective plan revision")
    if plan["host"]["all_other_charges_ceiling_cents"] != EXTRAS_CENTS:
        raise ValueError("all charges must be bounded")
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
    if billed_cost(PROBE_SECONDS) > 100 or billed_cost(LEASE_SECONDS) > 1000:
        raise ValueError("lifecycle cap proof fails")
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
        "image_digest",
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
    for key in ("image_digest", "tuple_digest", "manifest_digest", "ledger_digest"):
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
        runtime > 1500
        or elapsed < runtime
        or elapsed > PROBE_SECONDS - TAIL_SECONDS
        or rss > p["rss_limit_mb"]
        or receipt["allocated_vcpus"] != p["allocated_vcpus"]
    ):
        raise ValueError("probe resource/lifecycle bound exceeded")
    remaining = LEASE_SECONDS - elapsed - TAIL_SECONDS
    selected = []
    for job in p["follow_on"]:
        # 2x measured runtime is conservative PLANNING, not an observed quantile.
        wall_cap = runtime * 2 * job["probe_runtime_multiplier"]
        if wall_cap > remaining:
            break
        selected.append({**job, "wall_cap_s": wall_cap})
        remaining -= wall_cap
    last_end = elapsed + sum(j["wall_cap_s"] for j in selected) + TAIL_SECONDS
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
                "allocated_vcpus",
                "image_digest",
                "manifest_digest",
            )
        },
        "selected_ordered_jobs": selected,
        "omitted_jobs": p["follow_on"][len(selected) :],
        "all_in_upper_cents": billed_cost(last_end),
        "lease_deadline_s_from_creation": LEASE_SECONDS,
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
            "probe_upper_cents": billed_cost(PROBE_SECONDS),
            "total_upper_cents": billed_cost(LEASE_SECONDS),
        }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
