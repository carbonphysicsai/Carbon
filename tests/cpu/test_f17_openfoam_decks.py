"""f17 OpenFOAM deck tooling: geometry convention, STL, determinism, reader.

CPU only; no container or solver runs.
"""

import hashlib
import importlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_pipeline import micromixer_readiness as m

PKG = Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/openfoam"
sys.path.insert(0, str(PKG))
geo = importlib.import_module("f17_geometry")
deck = importlib.import_module("f17_deck")
foam = importlib.import_module("f17_foam")
controls = importlib.import_module("f17_controls")
freeze = importlib.import_module("f17_freeze")

PANEL = [(20, 100, 6), (40, 250, 10), (30, 175, 8), (40, 100, 6), (20, 250, 10),
         (20, 100, 10), (40, 250, 6), (30, 100, 8)]  # fmt: skip


def design(d, p, r):
    return {"depth_um": float(d), "pitch_um": float(p), "reversal": r}


@pytest.mark.parametrize("params", PANEL)
def test_mesher_and_recipe_share_the_frozen_convention(params):
    gs = geo.grooves(**design(*params))
    recipe = m.geometry_recipe(m.action(*params))
    assert [g["apex_x_um"] for g in gs] == pytest.approx(recipe["groove_stations_um"])
    assert [g["half_cycle"] for g in gs] == recipe["half_cycles"]
    report = geo.check(design(*params))
    assert report["min_web_um"] >= geo.MIN_WEB_UM
    assert report["first_tip_x_um"] == 250.0
    assert report["last_footprint_end_x_um"] <= 9750.0
    surf = geo.surface_check(design(*params))
    assert surf["groove_bottom_area_um2"] == pytest.approx(report["groove_area_um2"])


def test_whole_action_support_is_valid_and_reversal_spacing_prevents_overlap():
    for d in (20, 40):
        for p in np.linspace(100, 250, 31):
            for r in range(6, 11):
                assert geo.check(design(d, float(p), r))["min_web_um"] >= 20.7
    # spacing p (not p + 100) across a reversal would put the continuing arm
    # family on one line at p = 100: the convention exists to prevent that
    a, b = geo.chevron(1000, 100), geo.chevron(1100, 200)
    assert a[4][0] - a[4][1] == pytest.approx(b[4][0] - b[4][1])


def test_volume_is_box_plus_recesses_and_residence_range():
    shallow = geo.check(design(20, 250, 6))["fluid_volume_um3"] * 1e-18 / (1e-9 / 60)
    deep = geo.check(design(40, 100, 10))["fluid_volume_um3"] * 1e-18 / (1e-9 / 60)
    assert 18.8 < shallow < 18.9 and 22.0 < deep < 22.1
    assert m.REGISTERED["question_law"]["P"]["residence_cap_s"] == [19.0, 20.0]


def _hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(root).rglob("*"))
        if p.is_file()
    }


def test_deck_is_deterministic_and_binds_retained_phi(tmp_path):
    for name in ("a", "b"):
        deck.write_case(tmp_path / name, design(40, 100, 6), 10.0, label="deep-dense")
    assert _hashes(tmp_path / "a") == _hashes(tmp_path / "b")
    funcs = (tmp_path / "a" / "functions.sh").read_text()
    assert "REFUSED flow key mismatch" in funcs and "PHI_CHANGED" in funcs
    assert "REFUSED phi hash mismatch" in funcs
    keys = (tmp_path / "a" / "keys.sh").read_text()
    assert keys.count("cat mesh/mesh.sha256") == 3 and deck.IMAGE in keys
    schemes = (tmp_path / "a" / "scalar_q5_d0.5" / "system" / "fvSchemes").read_text()
    assert "bounded Gauss linearUpwind grad(T)" in schemes
    assert m.REGISTERED["scalar_scheme"] in schemes
    allrun = (tmp_path / "a" / "Allrun").read_text()
    assert allrun.count("run_scalar ") == 9 and allrun.count("run_flow ") == 3


def test_triage_manifest_is_runner_schema(tmp_path):
    manifest = freeze.triage(tmp_path)
    assert manifest["schema"] == "carbon.reference-triage.frozen-decks.v1"
    assert manifest["counts"] == {"primary": 8, "witness_studies": 2, "controls": 2,
                                  "cold_repeat": 1}  # fmt: skip
    assert manifest["image"] == m.IMAGE_DIGEST
    for case in manifest["cases"]:
        assert case["command"].startswith("bash /case/Allrun")
        root = tmp_path / "f17" / case["case"]
        assert _hashes(root) == case["files"]


def test_bank_freeze_needs_operator_seed_and_is_reproducible(tmp_path):
    seed = tmp_path / "seed"
    seed.write_text("0x1234\n")
    a = freeze.bank(seed, tmp_path / "a", count=2)
    b = freeze.bank(seed, tmp_path / "b", count=2)
    assert [c["files"] for c in a["cases"]] == [c["files"] for c in b["cases"]]
    assert "0x1234" not in json.dumps(a) and a["seed_sha256"]


def test_binary_field_reader(tmp_path):
    values = [0.25, -1.5, 3.0]
    blob = (
        b"FoamFile\n{\n    format binary;\n    class volScalarField;\n}\n"
        b"dimensions [0 0 0 0 0 0 0];\ninternalField nonuniform List<scalar> 3("
        + struct.pack("<3d", *values)
        + b");\nboundaryField\n{\n    outlet\n    {\n        type fixedValue;\n"
        b"        value nonuniform List<scalar> 2("
        + struct.pack("<2d", 7.0, 8.0)
        + b");\n    }\n    walls\n    {\n        type zeroGradient;\n    }\n}\n"
    )
    path = tmp_path / "T"
    path.write_bytes(blob)
    field = foam.read_field(path, ["outlet", "walls"])
    assert list(field["internal"]) == values
    assert list(field["patch"]["outlet"]) == [7.0, 8.0]
    assert field["patch"]["walls"] is None


def test_independent_controls():
    assert controls.marching_mixing(5e-9 / 60, 0.0) == 0.0
    q = 5e-9 / 60
    assert controls.developed_gradient_pa_m(q) * 0.01 == pytest.approx(
        m.rectangular_pressure_pa(q), rel=1e-6
    )
    assert math.isfinite(controls.series_velocity(np.array(1.5e-4), np.array(5e-5)))
