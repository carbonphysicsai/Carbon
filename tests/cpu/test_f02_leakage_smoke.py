"""The F02 leakage smoke driver (scripts/dev/reference_packages/elmer/f02_leakage_smoke.py), offline: fixtures, deck build and the
pass checks on synthetic solver output. No solver and no docker run here; the rented pod runs those.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ELMER = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dev"
    / "reference_packages"
    / "elmer"
)
sys.path.insert(0, str(ELMER))

import f02_deck_v3 as v3
import f02_leakage_smoke as smoke


def _log(directory, steps=3, iterations=4, final=1e-10):
    lines = []
    for _ in range(steps):
        for i in range(1, iterations + 1):
            change = final if i == iterations else 10.0**-i
            lines.append(
                f"ComputeChange: NS (ITER={i}) (NRM,RELC): ( 3.4E+02  {change:.3E} ) :: heat equation"
            )
    (directory / "solver.log").write_text("\n".join(lines) + "\n")


def _transient(directory, peaks):
    rows = "\n".join(f"{t!r} {k!r}" for t, k in peaks)
    (directory / "scalars.dat").write_text(rows + "\n")
    (directory / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n"
    )
    _log(directory)


def _lumped(directory, scale=1.0):
    meta = json.loads((directory / "deck.json").read_text())
    h, tc = meta["case"]["h_w_m2_k"], meta["case"]["coolant_c"] + 273.15
    area = (2 * v3.LAYERS["copper"][0] * v3.MM) ** 2
    heat = v3.BASE_W + 5.0e6 * v3.die_volume_m3()
    integral = (tc + heat / (h * area)) * area * scale
    (directory / "scalars.dat").write_text(f"0.0 330.0 {integral!r}\n")
    (directory / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n   3: boundary int: temperature bc 1\n"
    )
    _log(directory, steps=1)


@pytest.fixture
def built(tmp_path):
    manifest = smoke.build(tmp_path)
    return tmp_path, manifest


def test_the_fixtures_are_deterministic_test_only_files_the_deck_loads(tmp_path):
    first = smoke.fixtures(tmp_path / "a")
    second = smoke.fixtures(tmp_path / "b")
    assert first == second and set(first) == set(smoke.FIXTURES)
    for name in first:
        leak = v3.load_leakage(tmp_path / "a" / name, test_mode=True)
        assert leak["label"] == "TEST_ONLY"
        with pytest.raises(v3.DeckRefused, match="refuse_production"):
            v3.load_leakage(tmp_path / "a" / name)


def test_the_build_is_deterministic_and_makes_the_three_decks_of_steps_1_and_2(
    built, tmp_path
):
    out, manifest = built
    assert set(manifest["decks"]) == {"s1-lumped", "s2-off", "s2-zero"}
    assert smoke.build(tmp_path / "again") == manifest
    off = (out / "decks" / "s2-off" / "case.sif").read_text()
    zero = (out / "decks" / "s2-zero" / "case.sif").read_text()
    assert "Body Force" not in off and "Body Force = 1" in zero
    assert "Steady State" in (out / "decks" / "s1-lumped" / "case.sif").read_text()
    assert "Transient" in off and "Transient" in zero
    # leakage off here is the receipted deck with TEST tables: nonlinear in both decks of step 2
    assert "Nonlinear System Max Iterations = 50" in off


def test_step_3_is_built_only_when_a_case_is_given(tmp_path):
    case = tmp_path / "c3.json"
    case.write_text(json.dumps({**smoke.CASE, "peak_w": 140.0}))
    manifest = smoke.build(tmp_path / "o", case)
    assert {"s3-off", "s3-exp"} <= set(manifest["decks"])


def test_solve_refuses_a_host_whose_image_is_not_the_pinned_one(built, monkeypatch):
    out, _ = built
    monkeypatch.setenv("CARBON_F02_IMAGE", "sha256:" + "0" * 64)
    with pytest.raises(SystemExit, match="pinned F02 image"):
        smoke.solve(out)
    monkeypatch.delenv("CARBON_F02_IMAGE")
    with pytest.raises(SystemExit):
        smoke.solve(out)


def test_solve_refuses_a_deck_that_changed_after_the_build(built, monkeypatch):
    out, _ = built
    monkeypatch.setenv("CARBON_F02_IMAGE", smoke.readiness.IMAGE)
    (out / "decks" / "s2-off" / "case.sif").write_text("tampered\n")
    with pytest.raises(SystemExit, match="differs from the built manifest"):
        smoke.solve(out)


def test_the_checks_pass_on_a_consistent_run_and_stop_on_any_mismatch(built, capsys):
    out, _ = built
    decks = out / "decks"
    _lumped(decks / "s1-lumped")
    peaks = [(0.0, 303.15), (20.0, 330.123456789), (120.0, 311.5)]
    _transient(decks / "s2-off", peaks)
    _transient(decks / "s2-zero", peaks)
    assert smoke.check(out) == 0
    report = json.loads((out / "smoke-report.json").read_text())
    assert report["verdict"] == "PASS" and report["tolerance_status"].startswith(
        "PROPOSAL"
    )
    assert abs(report["steps"]["1_lumped"]["residual_rel"]) < 1e-12
    assert report["steps"]["2_zero_law"]["rows_differing"] == 0
    # one printed digit of the peak differs: STOP
    _transient(
        decks / "s2-zero", [(0.0, 303.15), (20.0, 330.123456788), (120.0, 311.5)]
    )
    assert smoke.check(out) == 3
    assert (
        json.loads((out / "smoke-report.json").read_text())["steps"]["2_zero_law"][
            "rows_differing"
        ]
        == 1
    )
    _transient(decks / "s2-zero", peaks)
    # the lumped balance off by 0.1 %: STOP, with the residual printed
    _lumped(decks / "s1-lumped", scale=1.001)
    assert smoke.check(out) == 3
    step = json.loads((out / "smoke-report.json").read_text())["steps"]["1_lumped"]
    assert step["pass"] is False and abs(step["residual_rel"]) > 1e-4
    capsys.readouterr()


def test_missing_solver_output_is_a_stop_not_a_pass(built):
    out, _ = built
    assert smoke.check(out) == 3
    report = json.loads((out / "smoke-report.json").read_text())
    assert report["verdict"] == "STOP"
    assert all(not s["pass"] for s in report["steps"].values())


def test_a_runaway_log_stops_the_lumped_step(built):
    out, _ = built
    decks = out / "decks"
    _lumped(decks / "s1-lumped")
    _log(
        decks / "s1-lumped", steps=1, iterations=v3.NONLINEAR_MAX_ITERATIONS, final=1e-3
    )
    _transient(decks / "s2-off", [(0.0, 303.15)])
    _transient(decks / "s2-zero", [(0.0, 303.15)])
    assert smoke.check(out) == 3
    step = json.loads((out / "smoke-report.json").read_text())["steps"]["1_lumped"]
    assert step["reference"]["reason"] == "thermal_runaway"
