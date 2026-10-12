"""The battery screening grain file (SCREENING-GRAIN-01): per-rule entries,
each its measured SE rounded up to a 0.5 % step (floor 0.5 %), with a display
convention that never overstates."""

import json
import math
from pathlib import Path

D = (
    Path(__file__).resolve().parents[2]
    / "docs/development/evidence/battery-screening-grain"
)
MEASUREMENTS = {
    "v2-bank-sched": "measurement-v2-bank-sched.json",
    "v3-bank-sched": "measurement-v3-bank-sched.json",
}


def doc():
    return json.loads((D / "screening-grain-v1.json").read_text())


def up(se):
    return max(math.ceil(round(100 * se, 9) / 0.5) * 0.5, 0.5) / 100


def test_each_rule_has_one_entry_with_its_measured_grain():
    entries = doc()["entries"]
    rules = [e["match"]["rule"] for e in entries]
    assert sorted(rules) == ["v2-bank-sched", "v3-bank-sched"]
    assert len({json.dumps(e["match"], sort_keys=True) for e in entries}) == len(
        entries
    )
    for e in entries:
        measured = json.loads((D / MEASUREMENTS[e["match"]["rule"]]).read_text())
        assert e["measured_se"] == round(measured["measured_se"], 6)
        assert e["grain"] == up(e["measured_se"]) == measured["grain"]
        assert math.isclose(e["grain_pct"], 100 * e["grain"])
        assert e["sense"] in ("lower_is_better", "higher_is_better")
    v3 = next(e for e in entries if e["match"]["rule"] == "v3-bank-sched")
    assert v3["sense"] == "higher_is_better"
    assert v3["match"]["score_candidate"] == "G-FEAS/A-Q>@0.05"
    assert "SEALED_UNTIL_GRAIN" in doc()["lookup"]
    assert "before it goes live" in doc()["new_rule"]
    assert "not a new threshold" in doc()["convention"]


def test_the_display_never_overstates_in_either_sense():
    for e in doc()["entries"]:
        g = e["grain"]
        for score in (0.0123, 0.05, 0.1234, 0.5, 0.8, 1.0, 2.7):
            k = math.log(score) / math.log(1 + g)
            if e["sense"] == "lower_is_better":
                shown = (1 + g) ** math.ceil(k)
                assert shown >= score * (1 - 1e-12)
            else:
                shown = (1 + g) ** math.floor(k)
                assert shown <= score * (1 + 1e-12)
        ex = e["worked_example"]
        rounding = math.ceil if e["sense"] == "lower_is_better" else math.floor
        assert ex["k"] == rounding(math.log(ex["score"]) / math.log(1 + g))
        assert math.isclose(ex["displayed"], (1 + g) ** ex["k"], rel_tol=1e-5)


def test_v2_adds_the_per_coldkey_noise_floor_and_keeps_the_grids():
    v1 = doc()
    v2 = json.loads((D / "screening-grain-v2.json").read_text())
    assert v2["version"] == 2 and "highest-numbered" in v2["file_lookup"]
    assert v2["entries"] == v1["entries"]  # the median grids are kept
    nf = v2["noise_floor"]
    assert nf["min_cases"] == 294 and nf["min_design_questions"] == 24
    assert set(nf["own_se"]) == {"v2-bank-sched", "v3-bank-sched"}
    assert "max(grain, own_se_rounded)" in nf["step"]
    # The step never falls below the grain, and own SE rounds up.
    grain = 0.025
    for own in (0.001, 0.0249, 0.026, 0.11):
        rounded = math.ceil(round(100 * own, 9) / 0.5) * 0.5 / 100
        step = max(grain, rounded)
        assert step >= grain and step >= own
