"""recal_stats --crown-n N (OWNER-CROWN-MULTI-REBUILD-AVERAGE-01): the crown compares means of N rebuilds, so the seed
term of the margin is 2 x SD / sqrt(N): value = max(5 x sigma, 2 x seed_sd / sqrt(N)), spread rule `2sd_mean_n`.

The values are recomputed from the existing recal measurements (no new runs). The margins pinned here are the ones the
Validator tabled for N = 10 and N = 5 from today's registered 2-SD margins; the rule without --crown-n is unchanged."""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "recal_stats", Path(__file__).parents[2] / "scripts" / "dev" / "recal_stats.py"
)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

#: Today's registered 2-SD margins and the tabled `2 * SD / sqrt(N)` values (N = 10 and N = 5).
TABLE = {
    "Ribbed Bracket": (0.006062541759314569, {5: 0.00271, 10: 0.00192}),
    "Motor": (0.007923678234807158, {5: 0.00354, 10: 0.00251}),
    "Burst Thermal": (0.04726369864563663, {5: 0.02114, 10: 0.01495}),
    "Cooling": (0.01570813655321609, {5: 0.00702, 10: 0.00497}),
}


def H(c):
    return c * 64


def _seeds(two_sd, mean=0.5):
    """Ten per-seed totals whose SAMPLE standard deviation is two_sd / 2, so the registered 2-SD margin is two_sd."""
    sd = two_sd / 2
    d = sd * math.sqrt(
        9 / 10
    )  # +-d around the mean, five each: sample sd = d * sqrt(10 / 9)
    return [mean + d if i % 2 else mean - d for i in range(10)]


def _doc(name, seeds):
    member = {
        "reference_fingerprint": H("a"),
        "seed0_totals": [0.5] * 10,
        "state_digests": [H("1")] * 10,
        "within_noise": False,
    }
    return {
        "schema": rs.SCHEMA_IN,
        "challenges": {
            name: {
                "pack_digest": H("b"),
                "class_record_digest": H("c"),
                "control_basis_bit_identical": "ten bit-identical",
                "control_basis_within_noise": "smallest sigma within noise",
                "panel": ["FC"],
                "members": {"FC": member},
                "control_seed_totals": {"FC": seeds},
            }
        },
    }


@pytest.mark.parametrize("name", sorted(TABLE))
def test_the_engineered_seeds_reproduce_todays_registered_margin(name):
    today, _ = TABLE[name]
    out = rs.measure(_doc(name, _seeds(today)))["challenges"][name]
    assert statistics.stdev(_seeds(today)) == pytest.approx(today / 2)
    assert out["spread_rule"] == "2sd" and "crown_n" not in out
    assert out["value"] == pytest.approx(
        today
    )  # the rule without --crown-n is unchanged


@pytest.mark.parametrize("name", sorted(TABLE))
@pytest.mark.parametrize("n", [10, 5])
def test_2sd_mean_n_matches_the_tabled_margins(name, n):
    today, tabled = TABLE[name]
    out = rs.measure(_doc(name, _seeds(today)), crown_n=n)["challenges"][name]
    assert out["spread_rule"] == "2sd_mean_n" and out["crown_n"] == n
    assert out["sigma"] == 0.0  # the 5-sigma floor is 0 and does not bind
    assert out["value"] == pytest.approx(today / math.sqrt(n))
    assert round(out["value"], 5) == tabled[n]
    assert out["seed_sd"] == pytest.approx(
        today / 2
    )  # the SD itself is reported unchanged


def test_the_rebuild_noise_floor_still_binds_when_larger():
    doc = _doc("Cooling", _seeds(0.0157))
    doc["challenges"]["Cooling"]["members"]["FC"]["seed0_totals"] = [
        0.5 + 0.05 * (i % 2) for i in range(10)
    ]
    doc["challenges"]["Cooling"]["members"]["FC"]["state_digests"] = [
        H(str(i)) for i in range(10)
    ]
    doc["challenges"]["Cooling"]["members"]["FC"]["within_noise"] = True
    out = rs.measure(doc, crown_n=10)["challenges"]["Cooling"]
    assert out["sigma"] > 0.02
    assert out["value"] == pytest.approx(
        5 * out["sigma"]
    )  # 5 x sigma beats 2 SD / sqrt(N)


def test_crown_n_changes_the_measurement_digest_and_is_validated():
    doc = _doc("Motor", _seeds(0.0079))
    plain = rs.measure(doc)
    ten = rs.measure(doc, crown_n=10)
    five = rs.measure(doc, crown_n=5)
    assert (
        len(
            {
                plain["measurement_digest"],
                ten["measurement_digest"],
                five["measurement_digest"],
            }
        )
        == 3
    )
    for bad in (1, 0, -3, 1001, True, 2.5, "10"):
        with pytest.raises(rs.StatsError, match="crown_n"):
            rs.measure(doc, crown_n=bad)


def test_the_command_takes_crown_n(tmp_path, capsys):
    path = tmp_path / "in.json"
    path.write_text(json.dumps(_doc("Motor", _seeds(0.0079))))
    out = tmp_path / "out.json"
    assert rs.main([str(path), "--crown-n", "10", "--out", str(out)]) == 0
    result = json.loads(out.read_text())["challenges"]["Motor"]
    assert result["spread_rule"] == "2sd_mean_n" and result["crown_n"] == 10
    assert rs.main([str(path), "--crown-n", "1"]) == 2
    assert "crown-n" in capsys.readouterr().err
