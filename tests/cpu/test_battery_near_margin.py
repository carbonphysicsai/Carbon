"""SR-3: margin error near the decision boundary.

The claims tested: "near" is exactly the published important region; the
grid is the pre-registered 286 profiles and its n-free part is SR-1; the
retained run follows its outcome rule and records the near-case count.
"""

import json
from pathlib import Path

from carbon.battery.domain import is_important
from carbon.battery.value import near, ratios
from carbon.battery.value import scoring as sc

REPO = Path(__file__).resolve().parents[2]


def test_near_is_exactly_the_published_important_region():
    store, case_ids, _ = sc.scoring_set(REPO)
    chosen = set(near.near_cases(store, case_ids))
    assert chosen == {
        c
        for c in case_ids
        if store.refs[c].get("outputs") and is_important(store.refs[c])
    }
    assert 0 < len(chosen) < len(case_ids)


def test_the_grid_is_286_profiles_and_its_n_free_part_is_sr1():
    grid = near.profiles()
    assert len(grid) == 286 == len({p for p, _ in grid})
    sr1 = dict(ratios.profiles())
    results = json.loads(
        (REPO / "docs/development/evidence/ev2-2026-10-01/results.json").read_text()
    )
    for _, w in grid:
        if w[3]:
            continue
        a, r, g = (ratios._fmt(x) for x in w[:3])
        for component in results["components"].values():
            assert near.score(component, w) == ratios.score(
                component, sr1[f"sr-a{a}-r{r}-g{g}"]
            )


def test_the_retained_run_follows_its_preregistered_outcome_rule():
    report = json.loads(
        (REPO / "docs/development/evidence/sr3-2026-10-02/results.json").read_text()
    )
    assert report["profiles_tried"] == 286
    assert report["near_cases"] == 311 and report["scoring_cases"] == 1588
    assert report["chosen"] in report["admissible"]
    promote = all(report["outcome_checks"].values())
    assert report["outcome"] == (
        "PROMOTE_TO_CONFIRMATION" if promote else "NO_PROMOTION"
    )
    assert report["near_component"]["control-oracle"]["score"] == 1.0
    assert report["claims"]["testnet_rule_changed"] is False
