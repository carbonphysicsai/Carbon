"""The first R1 decisions on real hardware, re-derived from the committed records.

Two simulated validators per part - separate single-GPU pods of one part in one
datacenter, each running the pinned session on its own - on 2026-09-24:
L4 in EU-RO-1 and H100 SXM in US-NE-1. The records are the session output
exactly as each pod printed it. These tests recompute every outcome from them, so
the result cannot drift from its evidence.

Simulated validators are direct execution inside the pinned study image, not
validator_launch. The qualification applied is the owner's DEVELOPMENT one
(Amendment 10), on fixture_authoring 1.0.
"""

import json
from pathlib import Path

import pytest

from scripts.dev.gpu_determinism_study import r1_capture

EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/r1-simulated-validators-2026-09-24"
)
ONE_FLOAT32_ULP = 2.0**-24


def sessions(part: str, condition: str) -> list[tuple[str, dict]]:
    return [
        (f"{pod.name}/{path.name}", json.loads(path.read_text()))
        for pod in sorted(EVIDENCE.glob(f"{part}-v*"))
        for path in sorted(pod.glob(f"{condition}-*.json"))
    ]


@pytest.mark.parametrize("part", ["l4", "h100"])
def test_pinned_simulated_validators_are_reproducible(part: str) -> None:
    result = r1_capture.compare(sessions(part, "pinned"))
    assert result["outcome"] == "AGREE"
    assert len(result["units"]) == 2 and len(result["driver_builds"]) == 1
    assert result["r1"]["outcome"] == "REPRODUCIBLE"
    assert len(result["r1"]["pairs"]) == 9  # 3 sessions x 3 sessions across validators
    assert all(pair["max_absolute_delta"] == 0.0 for pair in result["r1"]["pairs"])
    assert all(not pair["r0_mismatched_fields"] for pair in result["r1"]["pairs"])


@pytest.mark.parametrize("part", ["l4", "h100"])
def test_unpinned_control_is_not_reproducible_by_one_ulp(part: str) -> None:
    """The positive control on real data: R1 refuses when pinning is absent."""
    result = r1_capture.compare(sessions(part, "unpinned"))
    assert result["r1"]["outcome"] == "NOT_REPRODUCIBLE"
    assert (
        max(p["max_absolute_delta"] for p in result["r1"]["pairs"]) == ONE_FLOAT32_ULP
    )


def test_identical_unpinned_weights_can_still_give_different_predictions() -> None:
    """Why R1 compares outputs, not weights: the inference pass diverges too."""
    first = json.loads((EVIDENCE / "h100-v1/unpinned-s2.json").read_text())
    second = json.loads((EVIDENCE / "h100-v2/unpinned-s1.json").read_text())
    assert first["runs"][0]["weights_sha256"] == second["runs"][0]["weights_sha256"]
    assert first["runs"][0]["predictions"] != second["runs"][0]["predictions"]


def test_the_pinned_digests_match_the_earlier_single_host_measurements() -> None:
    expected = {
        "l4": "83e523384fd44db6207583cede3294bd3f2f8b690802b11f661ade1eb825f10a",
        "h100": "961cc4df99c52ad4",
    }
    for part, digest in expected.items():
        for _, record in sessions(part, "pinned"):
            assert record["runs"][0]["weights_sha256"].startswith(digest)


def test_different_parts_are_stopped_before_r1() -> None:
    """L4 and H100 ran different driver builds, so the unit check refuses first."""
    mixed = sessions("l4", "pinned")[:1] + sessions("h100", "pinned")[:1]
    result = r1_capture.compare(mixed)
    assert result["outcome"] == "REFUSED_DRIVER_MISMATCH"
    assert result["r1"] is None
