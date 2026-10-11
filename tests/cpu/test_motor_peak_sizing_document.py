"""Independent arithmetic checks for an analysis, never a physical verdict."""

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/development/challenge_pipeline/round1"
SHEET = json.loads((PACKET / "motor-peak-feasibility.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", SHEET["screen_rows"], ids=lambda r: r["label"])
def test_recompute_polygon_area_and_sizing(row):
    magnet, coverage, gap, tooth, opening, bottom = row["geometry"]
    bore, pitch = 25.6 + gap, 2 * math.pi / 12
    body, width = bore + 0.94, tooth * pitch * bore

    def edge(radius, side):
        angle = pitch / 2 + side * pitch / 2 - side * math.asin(width / (2 * radius))
        return radius * math.cos(angle), radius * math.sin(angle)

    polygon = [edge(body, -1), edge(bottom, -1), edge(bottom, 1), edge(body, 1)]
    area = (
        abs(
            sum(
                polygon[i][0] * polygon[i - 1][1] - polygon[i - 1][0] * polygon[i][1]
                for i in range(4)
            )
        )
        / 2
    )
    assert area == pytest.approx(row["whole_slot_area_mm2"])
    ratio = opening * pitch * bore / gap
    carter = pitch * bore / (pitch * bore - ratio**2 / (5 + ratio) * gap)
    b1 = (
        4
        / math.pi
        * 1.2
        * magnet
        / (magnet + carter * gap)
        * math.sin(math.pi * coverage / 2)
    )
    kw = (2 + math.sqrt(3)) / 4
    scale = kw * (51.2 + gap) * 1e-3 * 0.035 * 15 * 12 * area / 4
    assert scale * b1 == pytest.approx(row["linear_nm"])
    tooth_coefficient = 12 * math.sin(5 * math.pi / 12) / (5 * math.pi)
    for marker, expected in zip(SHEET["marker_t"], row["marker_nm"], strict=True):
        effective = min(
            b1, marker * tooth / tooth_coefficient, marker * 5 * (46 - bottom) / bore
        )
        assert scale * effective == pytest.approx(expected)


def test_skew_is_an_average_not_a_threefold_torque_gain():
    for span, expected in SHEET["skew_fundamental_factors"].items():
        actual = (1 + 2 * math.cos(math.radians(5 * float(span) / 2))) / 3
        assert actual == pytest.approx(expected)
        assert actual <= 1


def test_screen_cannot_claim_feasibility_or_change_requirements():
    assert SHEET["solver_runs"] == SHEET["spend"] == 0
    assert not SHEET["adopted_requirement_change"]
    assert not SHEET["global_maximum_proven"]
    assert SHEET["physical_feasibility"] == "NOT_DEMONSTRATED"
    assert not SHEET["missing_peak_coverage"]["null_is_zero_torque"]
    assert SHEET["larger_envelope"]["buyer_requirement_nm"] == 12
    assert (
        SHEET["larger_envelope"]["gross_v2_after_usd_assumption_ceiling"]
        <= SHEET["larger_envelope"]["gross_v2_before_usd_assumption"]
    )
