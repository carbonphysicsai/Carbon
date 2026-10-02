"""SR-1 (pre-registered scoring ratios): the grid and the combination.

The claims tested: the grid is the pre-registered 66 profiles; the
combination is Carbon's registered weight-profile combination, so every
overlapping published EV2/EV4 profile is reproduced exactly; gates are never
rescued; the selection admits only profiles that catch the boundary optimist.
"""

import json
from pathlib import Path

from carbon.battery.value import ratios

REPO = Path(__file__).resolve().parents[2]
PUBLISHED = {
    "dar-p0-r100-a0": "sr-a0-r0-g1",
    "dar-p0-r50-a50": "sr-a0.5-r0-g0.5",
    "dar-p0-r30-a70": "sr-a0.7-r0-g0.3",
    "p0-r20-a80": "sr-a0.8-r0.2-g0",
    "p0-r30-a70": "sr-a0.7-r0.3-g0",
    "p0-r40-a60": "sr-a0.6-r0.4-g0",
}


def test_the_grid_is_the_preregistered_66_profiles():
    grid = ratios.profiles()
    assert len(grid) == 66 == len({p for p, _ in grid})
    assert all(abs(sum(w) - 1.0) < 1e-9 for _, w in grid)


def test_overlapping_published_profiles_are_reproduced_exactly():
    weights = dict(ratios.profiles())
    for name in ("ev2-2026-10-01", "ev4-2026-10-01"):
        results = json.loads(
            (REPO / "docs/development/evidence" / name / "results.json").read_text()
        )
        for member, component in results["components"].items():
            for old, new in PUBLISHED.items():
                published = results["rule_scores"][member][old]
                assert abs(ratios.score(component, weights[new]) - published) < 1e-12


def test_gates_are_never_rescued_and_unmeasured_legs_are_not_guessed():
    w = (0.5, 0.1, 0.4)
    assert ratios.score({"eligible": False, "E": 0.0}, w) == 0.0
    assert ratios.score({"eligible": True, "E": 0.1, "E_important": 0.1}, w) is None
    assert ratios.score({"eligible": True, "E": 0.1}, (1.0, 0.0, 0.0)) == 1 / 1.1


def test_selection_admits_only_profiles_that_catch_the_optimist():
    rows = {
        p: {
            "optimist": {"below_every_eligible_member": p == "sr-a0-r0-g1"},
            "tau_development": 0.9 if p == "sr-a1-r0-g0" else 0.1,
            "divergence": {"development": 0, "verification": 0},
        }
        for p, _ in ratios.profiles()
    }
    chosen, admissible = ratios.choose(rows)
    assert admissible == ["sr-a0-r0-g1"] and chosen == "sr-a0-r0-g1"


def test_the_retained_run_matches_its_preregistered_outcome_rule():
    report = json.loads(
        (REPO / "docs/development/evidence/sr1-2026-10-02/results.json").read_text()
    )
    assert report["profiles_tried"] == 66
    assert report["chosen"] in report["admissible_on_ev4"]
    promote = all(report["outcome_checks"].values())
    assert report["outcome"] == (
        "PROMOTE_TO_CONFIRMATION" if promote else "NO_PROMOTION"
    )
    assert report["claims"]["testnet_rule_changed"] is False
