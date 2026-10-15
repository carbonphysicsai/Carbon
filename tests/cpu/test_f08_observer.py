"""f08 observer: the buyer objective is worst-band TIP compliance; the probe is a
diagnostic (F08-READINESS-REUSE-01). Synthetic modal data only, no solver."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "scripts/dev/reference_packages/calculix"


def _load(name):
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deck = _load("f08_deck")
freeze = _load("f08_freeze")

TIP, PROBE = 1, 2
#: (Hz, tip phi, probe phi): mode 1 barely moves the tip but swings the probe.
MODES = ((150.0, 0.5, 40.0), (420.0, 3.0, 0.1), (1500.0, 1.0, 0.2))


def _response(f_hz, zeta, node):
    w = 2 * math.pi * f_hz
    total = 0j
    for hz, tip, probe in MODES:
        wj = 2 * math.pi * hz
        total += (
            (tip if node == TIP else probe)
            * tip
            / (wj * wj - w * w + 2j * zeta * wj * w)
        )
    return total


def _steps():
    eigen = [
        {
            "mode": i + 1,
            "eigenvalue": (2 * math.pi * hz) ** 2,
            "rad": 2 * math.pi * hz,
            "hz": hz,
        }
        for i, (hz, _, _) in enumerate(MODES)
    ]
    shapes = [
        ("disp", {TIP: (0, 0, tip), PROBE: (0, 0, probe)}) for _, tip, probe in MODES
    ]
    steps = [{"eigen": eigen, "events": shapes}]
    for zeta in deck.ZETAS:
        events = []
        for f in (80.0, 150.0, 420.0, 600.0):
            u = {n: _response(f, zeta, n) for n in (TIP, PROBE)}
            events += [
                ("freq", f, []),
                ("disp", {n: (0, 0, v.real) for n, v in u.items()}),
                ("disp", {n: (0, 0, v.imag) for n, v in u.items()}),
            ]
        steps.append({"eigen": [], "events": events})
    static = sum(t * t / (2 * math.pi * hz) ** 2 for hz, t, _ in MODES) * 1.001
    steps.append(
        {"eigen": [], "events": [("disp", {TIP: (0, 0, static), PROBE: (0, 0, 0.0)})]}
    )
    return steps


def _observe():
    deck_json = {
        "case": {"label": "synthetic"},
        "h_mm": 3.0,
        "modes": 3,
        "loads": {str(TIP): 1.0},
    }
    coords = {
        "10": (0, 0, 0),
        "11": (2, 0, 0),
        "12": (0, 2, 0),
        str(TIP): (1, 1, 0),
        str(PROBE): (5, 5, 0),
    }
    meta = {"nodes": 5, "elements": 1, "mesh_volume_mm3": 1.0e5, "cad_volume_mm3": 1.0e5,
            "tip_node": TIP, "probe_node": PROBE, "probe_tri6": [[10, 11, 12, PROBE, PROBE, PROBE]],
            "pad_tri6": [], "coords": coords}  # fmt: skip
    return deck.observe_data(deck_json, meta, _steps())


def test_worst_dynamic_is_tip_only_and_probe_is_a_separate_diagnostic():
    obs = _observe()
    assert obs["probe_diagnostic_worst_mm_per_n"] > 10 * obs["worst_dynamic_mm_per_n"]
    for key, row in obs["damping"].items():
        zeta = float(key.split("_")[1])
        tip_crest = max(abs(_response(f / 10, zeta, TIP)) for f in range(800, 6001))
        assert row["worst_mm_per_n"] == pytest.approx(tip_crest, rel=1e-3)
        assert row["worst_mm_per_n"] < row["probe_diagnostic_mm_per_n"]
    assert obs["worst_dynamic_mm_per_n"] == max(
        r["worst_mm_per_n"] for r in obs["damping"].values()
    )
    margin = deck.LIMITS["dynamic_mm_per_n"] - obs["worst_dynamic_mm_per_n"]
    assert obs["diagnostic_margins"]["dynamic_mm_per_n"] == margin
    assert "TIP" in obs["objective"]


def test_refined_crest_is_at_least_the_grid_crest_and_projection_matches_ccx():
    obs = _observe()
    for row in obs["damping"].values():
        tip = row["dense"]["modes_3"]["tip"]
        assert tip["mm_per_n"] >= tip["grid_mm_per_n"]
        assert 0 <= tip["sampling_loss_rel"] <= deck.BANDS["sampling_loss_rel"]
        assert row["ccx_vs_projection_max_err_over_peak"] < 1e-12
        # Collocated residual-flexibility bound: 0.1 % static residual, 1500 Hz cutoff.
        assert row["truncation_bound_rel"] > 0


def test_bands_are_the_registered_development_values():
    assert deck.DECISION == "F08-SCIENCE-VALUES-01"
    b = deck.BANDS
    assert (b["eigen_rel"], b["peak_rel"], b["static_rel"], b["mass_rel"]) == (
        0.01,
        0.05,
        0.02,
        0.005,
    )
    assert (b["location_hz"], b["location_rel"], b["phase_deg"]) == (2.0, 0.01, 5.0)
    assert b["grid_bandwidth_fraction"] == 0.1 and b["mode_cutoff_hz"] == 900.0
    assert deck.location_ok(100.9, 100.0) and not deck.location_ok(101.1, 100.0)
    assert deck.location_ok(301.9, 300.0) and not deck.location_ok(302.1, 300.0)
    assert deck.wrapped_deg(179.0, -179.0) == pytest.approx(2.0)


def test_rung_comparison_flags_a_peak_shift_beyond_the_band():
    fine = _observe()
    coarse = _observe()
    coarse["static_tip_mm_per_n"] *= 1.03
    verdict = deck.compare_rungs(coarse, fine)
    assert not verdict["static_ok"] and verdict["verdict"] == "FAIL"
    assert deck.compare_rungs(fine, _observe())["verdict"] == "PASS"


def test_euler_bernoulli_series_reproduces_its_own_static_compliance():
    theory = deck.beam_theory()
    assert theory["modal_static_over_static"] == pytest.approx(1.0, abs=2e-3)
    assert theory["f2_hz"] / theory["f1_hz"] == pytest.approx(
        (4.6940911330 / 1.8751040687) ** 2
    )


def test_cgroup_counters_parse_v1_and_v2():
    v2 = "/sys/fs/cgroup/cpu.stat:usage_usec 2500000\n/sys/fs/cgroup/memory.peak:1048576\n"
    v1 = "/sys/fs/cgroup/cpuacct/cpuacct.usage:3000000000\n/sys/fs/cgroup/memory/memory.max_usage_in_bytes:2097152\n"
    assert freeze.cgroup_counters(v2) == {
        "cgroup_cpu_s": 2.5,
        "cgroup_memory_peak_mib": 1.0,
    }
    assert freeze.cgroup_counters(v1) == {
        "cgroup_cpu_s": 3.0,
        "cgroup_memory_peak_mib": 2.0,
    }
    assert freeze.cgroup_counters("") == {
        "cgroup_cpu_s": None,
        "cgroup_memory_peak_mib": None,
    }


def test_manifest_cost_estimates_grow_with_mesh_and_carry_bulk_runner_fields():
    small, large = deck.estimate(25_000), deck.estimate(240_000)
    assert set(small) == {"estimate_cpu_s", "estimate_wall_s", "estimate_mem_mib"}
    assert all(0 < small[k] < large[k] for k in small)
    assert large["estimate_wall_s"] >= large["estimate_cpu_s"]


def test_bank_draws_are_nested_disjoint_and_beyond_one_actions_call():
    bank = _load("f08_bank")
    reg = bank.registration()
    big = bank.draw(reg, 7, 1200)
    digests = [bank.s.tasks.digest(r) for r in big]
    assert len(set(digests)) == 1200
    assert bank.draw(reg, 7, 64) == big[:64]  # nested TRAIN ladder prefixes
    other = bank.draw(reg, 8, 64, frozenset(digests[:500]))
    assert not {bank.s.tasks.digest(r) for r in other} & set(digests[:500])
