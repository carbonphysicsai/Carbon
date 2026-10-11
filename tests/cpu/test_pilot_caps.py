import copy
import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline import pilot_caps as p

PLAN = Path("docs/development/challenge_pipeline/pilot-caps/plans.json")


def plan():
    return json.loads(PLAN.read_text())


def receipt(family="f13", runtime=1000):
    entry = next(v for v in plan()["families"] if v["family"] == family)
    return {
        "family": family,
        "scope": entry["scope"],
        "outcome": "COMPLETED",
        "complete_task": True,
        "probe_wall_s": runtime,
        "lease_elapsed_s": 1700,
        "peak_rss_mb": 1000,
        "allocated_vcpus": entry["allocated_vcpus"],
        "host_identity": "toy-host",
        "host_profile": "runpod-cpu-64",
        **{
            k: "sha256:" + "a" * 64
            for k in (
                "image_digest",
                "solver_tree_digest",
                "tuple_digest",
                "manifest_digest",
                "ledger_digest",
            )
        },
    }


def test_round_whole_lifetime_including_probe_and_all_other_charges():
    assert p.billed_cost(1) == 22
    assert p.billed_cost(2400) == 100
    assert p.billed_cost(2401) > 100
    assert p.billed_cost(28800) == 980
    assert p.billed_cost(28801) == 982
    assert p.billed_cost(64800, rate_cents=53, extras_cents=40, quantum_s=3600) == 994
    assert p.billed_cost(64801, rate_cents=53, extras_cents=40, quantum_s=3600) > 1000
    assert p.billed_cost(1, rate_cents=137, extras_cents=0, quantum_s=3600) > 100
    assert p.validate(plan())["dispatch_allowed"] is False


@pytest.mark.parametrize("family", [v["family"] for v in plan()["families"]])
def test_all_six_size_only_from_complete_measured_same_host_receipt(family):
    report = p.size_from_probe(plan(), family, receipt(family))
    assert report["all_in_upper_cents"] <= 1000
    assert report["dispatch_allowed"] is False
    assert report["same_host_and_pins_required"]["host_identity"] == "toy-host"
    assert report["p95_cost_status"] == "NOT_ESTIMATED_FROM_ONE_CASE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("complete_task", False),
        ("outcome", "TIMEOUT"),
        ("scope", "EVAL"),
        ("lease_elapsed_s", 4000),
        ("probe_wall_s", 1501),
        ("peak_rss_mb", 999999),
        ("allocated_vcpus", 16),
        ("host_profile", "unquoted-pod"),
        ("solver_tree_digest", "mutable-tree"),
        ("image_digest", "mutable:latest"),
        ("host_identity", ""),
        ("probe_wall_s", True),
    ],
)
def test_failed_partial_hidden_unpinned_or_oversized_probes_refused(field, value):
    r = receipt()
    r[field] = value
    with pytest.raises(ValueError):
        p.size_from_probe(plan(), "f13", r)


def test_no_extra_payload_or_hypothesis_may_masquerade_as_measured_probe():
    r = receipt()
    r["hidden_draw_id"] = "do-not-echo"
    with pytest.raises(ValueError, match="closed"):
        p.size_from_probe(plan(), "f13", r)
    with pytest.raises(ValueError):
        p.size_from_probe(plan(), "f13", {"wall_hypothesis": 10})


def test_ordered_prefix_and_no_cheap_replacement_or_cap_transfer():
    raw = copy.deepcopy(plan())
    jobs = next(v for v in raw["families"] if v["family"] == "f13")["follow_on"]
    jobs[1]["probe_runtime_multiplier"] = 1000
    report = p.size_from_probe(raw, "f13", receipt())
    assert len(report["selected_ordered_jobs"]) == 1
    assert report["omitted_jobs"] == jobs[1:]
    assert report["status"] == "PARTIAL_PLAN"
    assert report["all_in_upper_cents"] <= 1000


@pytest.mark.parametrize("profile", list(p.HOST_BOUNDS))
def test_selected_host_is_bound_and_high_memory_probe_is_not_extrapolated(profile):
    raw = plan()
    h = raw["hosts"][profile]
    assert p.host_cost(h["probe_lifetime_s"], h) <= 100
    assert p.host_cost(h["total_lifetime_s_including_probe"], h) <= 1000
    r = receipt(runtime=300)
    r["host_profile"] = profile
    r["lease_elapsed_s"] = 600
    report = p.size_from_probe(raw, "f13", r)
    assert report["same_host_and_pins_required"]["host_profile"] == profile
    assert report["termination_required"] is True
    assert (
        report["lease_deadline_s_from_allocation"]
        == h["total_lifetime_s_including_probe"]
    )
    if profile == "runpod-cpu-256":
        r["probe_wall_s"] = 361
        with pytest.raises(ValueError, match="bound exceeded"):
            p.size_from_probe(raw, "f13", r)


@pytest.mark.parametrize(
    "field",
    [
        "billing_quantum_s",
        "inclusive_hourly_ceiling_cents",
        "all_other_charges_ceiling_cents",
        "total_upper_cents",
        "setup_allowance_s",
    ],
)
def test_no_unproven_quote_rounding_or_missing_setup_bound(field):
    raw = plan()
    raw["hosts"]["runpod-cpu-64"][field] += 1
    with pytest.raises(ValueError):
        p.validate(raw)
