"""The F08 2.0 code-verification harness: the pure-Python C3D10 box mesh, the manufactured field and its body force, the
deck, and the comparison. The solver is NOT run here; a fabricated .dat holding the exact answer must pass and a
perturbed one must fail."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2] / "scripts/dev/reference_packages/calculix"
)
sys.path.insert(0, str(CALCULIX))

import f08_mms_v2 as mms

SIZE = (10.0, 8.0, 6.0)
E, NU = 70000.0, 0.33


def test_the_box_mesh_is_conforming_positive_and_fills_the_box():
    nodes, elements = mms.box_mesh(2, SIZE)
    assert len(elements) == 2 * 2 * 2 * 6
    assert (
        len(nodes) == (2 * 2 + 1) ** 3
    )  # corners and every midside lie on the half-step grid
    total = sum(mms._volume(nodes, c) for c in elements)
    assert total == pytest.approx(SIZE[0] * SIZE[1] * SIZE[2])
    assert all(mms._volume(nodes, c) > 0 for c in elements)
    for conn in elements:
        for slot, (a, b) in zip(range(4, 10), mms.MIDSIDE, strict=True):
            mid = [(nodes[conn[a]][k] + nodes[conn[b]][k]) / 2 for k in range(3)]
            assert list(nodes[conn[slot]]) == pytest.approx(mid), "midside off its edge"


def test_a_mesh_needs_a_cell():
    with pytest.raises(mms.Refused, match="mesh_needs_a_cell"):
        mms.box_mesh(0)


def test_the_field_gradient_matches_finite_differences():
    x = [3.0, 2.0, 1.0]
    grad = mms.field_grad(x)
    h = 1e-5
    for j in range(3):
        up, down = list(x), list(x)
        up[j] += h
        down[j] -= h
        for i in range(3):
            numeric = (mms.field_u(up)[i] - mms.field_u(down)[i]) / (2 * h)
            assert grad[i][j] == pytest.approx(numeric, rel=1e-6, abs=1e-9)


def test_the_patch_field_has_constant_stress_and_no_body_force():
    q = ({}, {}, {})
    one = mms.sigma([1.0, 1.0, 1.0], E, NU, mms.DEFAULT_A, q)
    two = mms.sigma([7.0, 3.0, 5.0], E, NU, mms.DEFAULT_A, q)
    assert one == pytest.approx(two)
    assert mms.body_force(E, NU, mms.DEFAULT_A, q) == pytest.approx(
        [0.0, 0.0, 0.0], abs=1e-9
    )


def test_the_quadratic_field_needs_a_uniform_body_force_that_balances_the_stress_divergence():
    bf = mms.body_force(E, NU)
    assert any(abs(b) > 1e-6 for b in bf)
    h = 1e-3
    for point in ([2.0, 3.0, 1.0], [8.0, 1.0, 5.0]):
        total = []
        for i in range(3):
            divergence = 0.0
            for j in range(3):
                up, down = list(point), list(point)
                up[j] += h
                down[j] -= h
                index = mms._tensor_index(i, j)
                divergence += (
                    mms.sigma(up, E, NU)[index] - mms.sigma(down, E, NU)[index]
                ) / (2 * h)
            total.append(-divergence)
        assert total == pytest.approx(bf, rel=1e-6)  # uniform: the same at every point


def test_the_case_files_prescribe_every_boundary_node_and_load_only_the_mms_case(
    tmp_path,
):
    info = mms.write_case(tmp_path / "mms", n=2, degree=2, size=SIZE)
    assert info == {"nodes": 125, "elements": 48, "boundary": 125 - 27}
    deck = (tmp_path / "mms/case.inp").read_text()
    assert "EALL,GRAV," in deck and "tables=TEST_ONLY" in deck
    boundary_lines = deck.split("*BOUNDARY\n")[1].split("*STEP")[0].strip().splitlines()
    assert len(boundary_lines) == 3 * info["boundary"]
    assert "*EL PRINT,ELSET=EALL\nS" in deck
    mms.write_case(tmp_path / "patch", n=2, degree=1, size=SIZE)
    assert "GRAV" not in (tmp_path / "patch/case.inp").read_text()
    with pytest.raises(mms.Refused, match="degree_is_1_or_2"):
        mms.write_case(tmp_path / "bad", degree=3)


def test_every_static_step_of_the_patch_and_mms_decks_names_the_pastix_solver(
    tmp_path,
):
    assert mms.v2.SOLVER == "PASTIX"
    for degree in (1, 2):
        mms.write_case(tmp_path / str(degree), n=2, degree=degree, size=SIZE)
        lines = (tmp_path / str(degree) / "case.inp").read_text().splitlines()
        steps = [line for line in lines if line.startswith(("*STATIC", "*FREQUENCY"))]
        assert steps == ["*STATIC,SOLVER=PASTIX"], degree


def _fabricated_dat(expected, nodes, perturb=0.0):
    interior = {int(i): u for i, u in expected["interior"].items()}
    rows = ["\n S T E P       1\n"]
    rows.append(" displacements (vx,vy,vz) for set NALL and time  0.1000000E+01\n\n")
    for i, u in sorted(interior.items()):
        shifted = [u[0] * (1 + perturb), u[1], u[2]]
        rows.append(f"{i:10d}  {shifted[0]:.9E}  {shifted[1]:.9E}  {shifted[2]:.9E}\n")
    rows.append(
        "\n stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set EALL and time  0.1E+01\n\n"
    )
    for element, s in sorted(
        expected["mean_stress"].items(), key=lambda kv: int(kv[0])
    ):
        for ip in (1, 2, 3, 4):
            rows.append(
                f"{int(element):10d}{ip:4d}  " + "  ".join(f"{x:.9E}" for x in s) + "\n"
            )
    return "".join(rows)


def test_the_comparison_passes_the_exact_answer_and_fails_a_perturbed_one(tmp_path):
    mms.write_case(tmp_path, n=2, degree=2, size=SIZE)
    expected = json.loads((tmp_path / "expected.json").read_text())
    nodes, _ = mms.box_mesh(2, SIZE)
    exact = mms.compare(expected, _fabricated_dat(expected, nodes))
    assert (
        exact["ok"]
        and exact["worst_displacement_rel"] < 1e-7
        and exact["tables"] == "TEST_ONLY"
    )
    off = mms.compare(expected, _fabricated_dat(expected, nodes, perturb=1e-3))
    assert not off["ok"] and off["worst_displacement_rel"] > 1e-5
    with pytest.raises(mms.Refused, match="no_displacement_block"):
        mms.compare(expected, "nothing here")
