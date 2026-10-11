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
        "lease_elapsed_s": 2500,
        "peak_rss_mb": 1000,
        "allocated_vcpus": entry["allocated_vcpus"],
        "host_identity": "toy-host",
        **{
            k: "sha256:" + "a" * 64
            for k in (
                "image_digest",
                "tuple_digest",
                "manifest_digest",
                "ledger_digest",
            )
        },
    }


def test_round_whole_lifetime_including_probe_and_all_other_charges():
    assert p.billed_cost(1) == 93
    assert p.billed_cost(3600) == 93
    assert p.billed_cost(3601) == 146
    assert p.billed_cost(64800) == 994
    assert p.billed_cost(64801) > 1000
    assert p.billed_cost(1, rate_cents=137, extras_cents=0) > 100
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
