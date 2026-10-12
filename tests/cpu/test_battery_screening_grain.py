"""The battery screening grain value file (SCREENING-GRAIN-01) obeys the
owner's rule: the measured SE rounded up to a 0.5 % step, floor 0.5 %."""

import json
import math
from pathlib import Path

D = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-screening-grain"
)


def test_the_grain_is_the_measured_se_rounded_up_to_half_a_percent():
    value = json.loads((D / "screening-grain-v1.json").read_text())
    measured = json.loads((D / "measurement.json").read_text())
    se = value["measured_se"]
    assert se == round(measured["measured_se"], 6)
    expected = max(math.ceil(round(100 * se, 9) / 0.5) * 0.5, 0.5) / 100
    assert value["grain"] == expected == 0.035
    assert value["grain"] >= se and value["grain"] >= 0.005
    assert value["pooled_screening_cases"] == 294


def test_the_display_grid_is_geometric_and_never_overstates():
    value = json.loads((D / "screening-grain-v1.json").read_text())
    g = value["grain"]
    assert math.isclose(value["grain_pct"], 100 * g) and value["grain_pct"] == 3.5
    assert value["display_grid"] == "geometric"
    assert value["sense"] == "lower_is_better" and value["rule"] == "v2-bank-sched"
    assert "not a new threshold" in value["convention"]
    # k toward the worse side: for lower-is-better, the shown error >= the true one.
    for score in (0.0123, 0.05, 0.1234, 0.5, 1.0, 2.7):
        k = math.ceil(math.log(score) / math.log(1 + g))
        shown = (1 + g) ** k
        assert shown >= score * (1 - 1e-12)
        assert shown / (1 + g) < score * (1 + 1e-12)
    ex = value["worked_example"]
    assert ex["k"] == math.ceil(math.log(ex["score"]) / math.log(1 + g))
    assert math.isclose(ex["displayed"], (1 + g) ** ex["k"], rel_tol=1e-5)
