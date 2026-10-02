"""SR-2: the margin-aware component and its pre-registered grid.

The claims tested: `m` charges optimism at the contract's false-acceptance
cost and pessimism at its missed-opportunity cost, in the contract's band
units; an oracle scores 1; the grid is the pre-registered 286 profiles and
its m-free part is exactly SR-1; a prediction file that does not match its
digest is refused; the retained run follows its outcome rule.
"""

import gzip
import json
from pathlib import Path

import pytest

from carbon.battery.value import margins, ratios

REPO = Path(__file__).resolve().parents[2]
CONTRACT = json.loads(
    (
        REPO / "carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json"
    ).read_text()
)


def _outputs(margin_v, peak_c):
    return {
        "voltage_v": [3.5] * 121,
        "temperature_c": [25.0] * 120 + [peak_c],
        "plating_margin_v": margin_v,
        "capacity_ah": [4.9] * 4,
    }


def test_optimism_costs_more_than_pessimism_in_band_units():
    band = CONTRACT["reference"]["uncertainty"]["bands"]["plating_margin_v"]
    refs = {"c": {"outputs": _outputs(0.0, 40.0)}}
    oracle = margins.margin_component(CONTRACT, {"c": _outputs(0.0, 40.0)}, ["c"], refs)
    assert oracle["score"] == 1.0
    optimist = margins.margin_component(
        CONTRACT, {"c": _outputs(2 * band, 40.0)}, ["c"], refs
    )
    pessimist = margins.margin_component(
        CONTRACT, {"c": _outputs(-2 * band, 40.0)}, ["c"], refs
    )
    costs = CONTRACT["mistake_costs"]
    # Two constraints per case; only plating is off, by 2 bands.
    assert optimist["score"] == pytest.approx(
        1 / (1 + costs["false_acceptance"] * 2 / 2)
    )
    assert pessimist["score"] == pytest.approx(
        1 / (1 + costs["missed_opportunity"] * 2 / 2)
    )
    assert optimist["score"] < pessimist["score"]
    assert margins.margin_component(CONTRACT, {}, ["c"], refs) is None


def test_the_grid_is_286_profiles_and_its_m_free_part_is_sr1():
    grid = margins.profiles()
    assert len(grid) == 286 == len({p for p, _ in grid})
    sr1 = dict(ratios.profiles())
    results = json.loads(
        (REPO / "docs/development/evidence/ev2-2026-10-01/results.json").read_text()
    )
    for name, w in grid:
        if w[3]:
            continue
        a, r, g = (ratios._fmt(x) for x in w[:3])
        twin = f"sr-a{a}-r{r}-g{g}"
        for component in results["components"].values():
            assert margins.score(component, w) == ratios.score(component, sr1[twin])


def test_a_prediction_file_that_does_not_match_its_digest_is_refused(tmp_path):
    (tmp_path / "x.json.gz").write_bytes(
        gzip.compress(json.dumps({"member": "x", "predictions": {}}).encode())
    )
    (tmp_path / "manifest").write_text("0" * 64 + "  x.json.gz\n")
    with pytest.raises(ValueError, match="does not match"):
        margins.verified_predictions(tmp_path, tmp_path / "manifest")


def test_the_retained_run_follows_its_preregistered_outcome_rule():
    report = json.loads(
        (REPO / "docs/development/evidence/sr2-2026-10-02/results.json").read_text()
    )
    assert report["profiles_tried"] == 286
    assert report["chosen"] in report["admissible"]
    promote = all(report["outcome_checks"].values())
    assert report["outcome"] == (
        "PROMOTE_TO_CONFIRMATION" if promote else "NO_PROMOTION"
    )
    assert report["margin_component"]["control-oracle"]["score"] == 1.0
    optimist = report["margin_component"]["control-boundary_optimist"]
    assert optimist["mean_optimism_bands"] > optimist["mean_pessimism_bands"]
    assert report["claims"]["testnet_rule_changed"] is False
    assert report["ev4_replication"].startswith("NOT_RUN")
