"""No native solver execution: synthetic fields, source math and adapter grammar."""

import ast
import copy
import math
from pathlib import Path

import pytest

from scripts.dev.code_verification import (
    calculix_modes,
    elmer_helmholtz,
    getdp_mms,
    meep_mode,
    openfoam_periodic,
    pybamm_submodels,
)
from scripts.dev.code_verification import common as cv
from scripts.dev.code_verification import (
    criteria as criteria_source,
)

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "sha256:" + "a" * 64
PIN = "sha256:" + "b" * 64


def fixture():
    points = [[0.2, 0.3], [0.5, 0.6], [0.7, 0.8]]
    hs = [1 / 8, 1 / 16, 1 / 32]
    rows = [
        {
            "h": h,
            "t": 0,
            "points": points,
            "values": [cv.exact("getdp-a", p, 0) + h * h for p in points],
            "weights": [1, 1, 1],
        }
        for h in hs
    ]
    data = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "getdp-a",
        "family": "motor",
        "image_digest": IMAGE,
        "spec_digest": PIN,
        "adapter_digest": PIN,
        "rows": rows,
        "raw_outputs": [PIN] * 3,
    }
    criteria = {
        "kind": "getdp-a",
        "family": "motor",
        "spec_digest": PIN,
        "adapter_digest": PIN,
        "h": hs,
        "t": 0,
        "order_band": [1.7, 2.3],
        "status": "HUMAN_INPUT",
    }
    return data, criteria


def test_synthetic_second_order_is_not_scientific_acceptance():
    data, criteria = fixture()
    result = cv.verify(data, criteria, expected_image=IMAGE)
    assert result["orders"]["l2"] == pytest.approx([2, 2])
    assert result["recommendation_agrees"] is True
    assert result["accepted_development_pass"] is False
    assert result["state"] == "HUMAN_INPUT" and not result["qualified"]


def test_adopted_fixture_arithmetic_pass_reports_nonempty_basis():
    data, criteria = fixture()
    criteria["status"] = "ACCEPTED_DEVELOPMENT"
    result = cv.verify(data, criteria, expected_image=IMAGE)
    assert result["accepted_development_pass"]
    assert all(row["samples"] == 3 for row in result["norms"])
    assert result["metrics"]["l2_order"] == pytest.approx(2)


@pytest.mark.parametrize(
    "change",
    [
        "image",
        "adapter",
        "family",
        "rung",
        "time",
        "scope",
        "empty",
        "zero",
        "nan",
        "raw",
    ],
)
def test_missing_or_stale_basis_never_passes(change):
    data, criteria = fixture()
    if change == "image":
        data["image_digest"] = PIN
    if change == "adapter":
        data["adapter_digest"] = IMAGE
    if change == "family":
        data["family"] = "battery-v3"
    if change == "rung":
        data["rows"].pop()
    if change == "time":
        data["rows"][0]["t"] = 1
    if change == "scope":
        data["scope"] = "HIDDEN_EVAL"
    if change == "empty":
        data["rows"][0]["points"] = []
    if change == "zero":
        for row in data["rows"]:
            row["values"] = [cv.exact("getdp-a", p, 0) for p in row["points"]]
    if change == "nan":
        data["rows"][0]["values"][0] = math.nan
    if change == "raw":
        data["raw_outputs"] = []
    with pytest.raises(cv.VerificationError):
        cv.verify(data, criteria, expected_image=IMAGE)


def test_flat_nonconverging_error_is_reference_finding():
    data, criteria = fixture()
    for row in data["rows"]:
        row["values"] = [cv.exact("getdp-a", p, 0) + 0.01 for p in row["points"]]
    result = cv.verify(data, criteria, expected_image=IMAGE)
    assert (
        result["state"] == "REFERENCE_FINDING"
        and not result["accepted_development_pass"]
    )


def test_all_manufactured_fields_finite_and_known_boundary_data():
    for kind, point in [
        ("elmer-heat", [0, 0.3, 0.5]),
        ("getdp-a", [0, 0.5]),
        ("pybamm-particle", [0]),
        ("elmer-helmholtz", [0, 0.3, 0.5]),
        ("openfoam-scalar", [0, 0.3]),
        ("calculix-ux", [0, 0.3, 0.5]),
    ]:
        value = cv.exact(kind, point, 0)
        assert math.isfinite(value)
        assert value == pytest.approx(
            1 if kind in ("elmer-heat", "pybamm-particle", "openfoam-scalar") else 0
        )


def test_getdp_preserves_motor_discretisation_and_interior_quadrature():
    source = (ROOT / "carbon/motor/getdp.py").read_text()
    for token in ("Form1P", "BF_PerpendicularEdge", "Galerkin", "NumberOfPoints 3"):
        assert token in source and token in getdp_mms.PRO
    square = "ST(0,0,0,1,0,0,0,1,0){0,1,1};ST(1,0,0,1,1,0,0,1,0){1,2,1};"
    points, values, weights = getdp_mms.samples(square, 1)
    assert len(points) == 6 and sum(weights) == pytest.approx(1)
    assert all(v == pytest.approx(sum(p)) for p, v in zip(points, values))
    with pytest.raises(ValueError):
        getdp_mms.samples("ST(0,0,0,1,0,0,0,1,0){0,1,1};", 1)


def test_getdp_mesh_ladder_grammar_and_battery_source_no_import_time_solver():
    assert "Physical Surface(1)" in getdp_mms.GEO.format(h=1 / 16)
    source = Path(pybamm_submodels.__file__).read_text()
    assert 'coord_sys="spherical polar"' in source
    assert "7+21*r**2+r**4" in source.replace(" ", "")
    assert "IDAKLUSolver" in source and "1e-10" in source
    assert all(
        not isinstance(n, ast.Import) or all(a.name != "pybamm" for a in n.names)
        for n in ast.parse(source).body
    )


def test_order_uses_actual_refinement_ratio_not_assumed_two():
    assert cv.observed_orders(
        [1 / 3, 1 / 9, 1 / 27], [1 / 9, 1 / 81, 1 / 729]
    ) == pytest.approx([2, 2])
    with pytest.raises(cv.VerificationError):
        cv.observed_orders([1, 1, 0.5], [1, 0.5, 0.25])


def test_accepted_result_can_feed_readiness_metrics_but_does_not_adopt_band():
    data, criteria = fixture()
    original = copy.deepcopy(criteria)
    result = cv.verify(data, criteria, expected_image=IMAGE)
    assert result["kind"] == "code_verification" and result["family"] == "motor"
    assert criteria == original


def test_criteria_hashes_actual_files_and_never_adopts():
    import hashlib

    result = criteria_source.prepare("getdp-a")
    assert result["status"] == "HUMAN_INPUT"
    assert (
        result["adapter_digest"]
        == "sha256:" + hashlib.sha256(Path(getdp_mms.__file__).read_bytes()).hexdigest()
    )
    assert (
        result["spec_digest"]
        == "sha256:"
        + hashlib.sha256((ROOT / criteria_source.SPEC).read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError):
        criteria_source.prepare("elmer-heat")
    with pytest.raises(ValueError):
        criteria_source.prepare("unregistered")


def test_invalid_adoption_label_refused():
    data, criteria = fixture()
    criteria["status"] = "QUALIFIED"
    with pytest.raises(cv.VerificationError):
        cv.verify(data, criteria, expected_image=IMAGE)


def test_acoustic_native_ascii_parser_requires_both_components(tmp_path):
    path = tmp_path / "field.vtu"
    path.write_text("""<VTKFile><UnstructuredGrid><Piece>
    <Points><DataArray format="ascii">0 0 0 .5 .5 .5</DataArray></Points>
    <PointData><DataArray Name="pressure" NumberOfComponents="2" format="ascii">0 0 1 .5</DataArray></PointData>
    </Piece></UnstructuredGrid></VTKFile>""")
    points, fields = elmer_helmholtz.read_fields(path)
    assert points == [[0, 0, 0], [0.5, 0.5, 0.5]]
    assert fields == {"real": [0, 1], "imag": [0, 0.5]}
    path.write_text(
        path.read_text().replace('NumberOfComponents="2"', 'NumberOfComponents="1"')
    )
    with pytest.raises(ValueError):
        elmer_helmholtz.read_fields(path)
    assert "Pressure Source 2" in elmer_helmholtz.SIF


def test_calculix_native_rod_connectivity_and_frequency_table():
    deck = calculix_modes.deck(4)
    assert "C3D20R" in deck and "NALL,2,3" in deck and "ROOT,1,1" in deck
    element_text = (
        deck.split("*ELEMENT,TYPE=C3D20R,ELSET=ALL\n")[1].split("*NSET")[0].splitlines()
    )
    assert len(element_text) == 8
    for first, second in zip(element_text[::2], element_text[1::2], strict=True):
        tokens = [x for x in (first + second).split(",") if x]
        assert len(tokens) == 21 and len(set(tokens[1:])) == 20
    output = "E I G E N V A L U E   O U T P U T\n 1 2.4 1.5 .25 0\n 2 22.2 4.7 .75 0\n 3 61.7 7.8 1.25 0\n"
    assert calculix_modes.frequencies(output) == [0.25, 0.75, 1.25]
    with pytest.raises(ValueError):
        calculix_modes.frequencies(output.replace(" 2 22.2 4.7 .75 0\n", ""))


def test_openfoam_periodic_case_and_native_field_parser():
    case = openfoam_periodic.dictionaries(16)
    assert "(16 1 1)" in case["system/blockMeshDict"]
    assert "neighbourPatch right" in case["system/blockMeshDict"]
    assert "backward" in case["system/fvSchemes"]
    values = openfoam_periodic.scalar_values(case["0/T"], 16)
    assert values == pytest.approx(
        [cv.exact("openfoam-periodic", [(i + 0.5) / 16], 0) for i in range(16)]
    )
    with pytest.raises(ValueError):
        openfoam_periodic.scalar_values(case["0/T"], 32)
    with pytest.raises(ValueError):
        openfoam_periodic.scalar_values("internalField uniform 1;", 16)
    with pytest.raises(ValueError):
        openfoam_periodic.dictionaries(999)


def test_basic_analytic_modes_and_no_import_time_native_execution():
    assert cv.exact("meep-bloch-mode", [0.2], 0) == 0.2
    assert [cv.exact("calculix-rod-mode", [m], 0) for m in range(3)] == [
        0.25,
        0.75,
        1.25,
    ]
    for module in (meep_mode, calculix_modes, openfoam_periodic, elmer_helmholtz):
        tree = ast.parse(Path(module.__file__).read_text())
        assert all(
            not isinstance(node, ast.Import)
            or all(x.name != "meep" for x in node.names)
            for node in tree.body
        )
        assert all(
            not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call)
            for node in tree.body
        )
    # These unit tests inspect math/decks; they never invoke any native worker.
