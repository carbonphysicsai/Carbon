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
