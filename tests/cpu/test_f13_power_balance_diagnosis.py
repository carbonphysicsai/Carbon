"""Toy algebra/specification checks only; no Elmer, fields or physical evidence."""

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/development/challenge_pipeline/round1"
SHEET = json.loads((DOCS / "f13-power-balance-diagnosis.json").read_text("utf-8"))


def test_no_reference_execution_or_earned_adequacy():
    assert SHEET["solver_runs"] == SHEET["spend"] == 0
    assert SHEET["maturity"] == "SPECIFIED"
    assert not SHEET["package_changed"]
    assert not SHEET["historical_rescore"]
    report = SHEET["report"]
    assert report["status"] == "REFERENCE_UNRESOLVED"
    for name in (
        "raw_signed_residual",
        "worst_frequency_hz",
        "offset_mesh_convergence",
    ):
        assert report[name] is None
    assert SHEET["diagnostic"]["measured_variance_identity_match"] is None


def test_existing_safety_and_custody_boundaries_stay_fixed():
    physics = SHEET["physics"]
    assert physics["closure_limit"] == 0.01
    assert physics["p10_buyer_target_db"] == 5
    assert physics["physical_package_max_mm"] == 300
    assert physics["physical_stub_m"] == 0.01
    assert SHEET["diagnostic"]["solver_systems"] == 0
    assert SHEET["diagnostic"]["does_not_qualify_physical_ports"]


def test_offset_mode_cutoff_and_decay_are_analytic_not_residual_bounds():
    p, a = SHEET["physics"], SHEET["analytic"]
    radius, c, f = p["port_radius_m"], p["c_m_s"], a["at_frequency_hz"]
    mu = a["roots"][0]
    cutoff = c * mu / (2 * math.pi * radius)
    alpha = math.sqrt((mu / radius) ** 2 - (2 * math.pi * f / c) ** 2)
    assert cutoff == pytest.approx(4020.411362233)
    assert alpha == pytest.approx(57.6771509121)
    assert math.exp(-2 * alpha * 0.01) == pytest.approx(0.315516904551)
    assert math.exp(-2 * alpha * 0.06) < 0.001
    assert math.exp(-2 * alpha * 0.10) < 0.00001
    assert not a["is_residual_bound"]


def test_toy_mixed_projection_residual_equals_omitted_variance():
    # Synthetic two-equal-patch field; S=1, 2*rho*c=1, incident A=1.
    # Not a circular-duct solve, measured row or calibrated reference witness.
    incident, mean, q = 1.0, 1 + math.sqrt(0.2), 1j * math.sqrt(0.047)
    samples = (mean + q, mean - q)
    integral = sum(samples) / 2
    h_in = sum(abs(x) ** 2 for x in samples) / 2
    variance = h_in - abs(integral) ** 2
    reflection_pw = abs(integral - incident) ** 2
    transmission_all = 0.753
    old_residual = incident**2 - reflection_pw - transmission_all
    reflection_all = h_in - 2 * incident * integral.real + incident**2
    assert variance == pytest.approx(0.047)
    assert old_residual == pytest.approx(variance)
    assert old_residual - variance == pytest.approx(0)
    assert incident**2 - reflection_all - transmission_all == pytest.approx(0)


def test_negative_variance_is_a_finding_not_clamped():
    # Deliberately inconsistent area/product quadrature. Preserve its sign.
    h_bad, integral, area, twice_z = 0.5, 1.0, 1.0, 1.0
    variance = (h_bad - abs(integral) ** 2 / area) / twice_z
    assert variance == -0.5


def test_proposed_minimal_verification_counts_systems_not_just_processes():
    v = SHEET["verification_proposal"]
    assert sum(row["systems"] for row in v["stages"]) == 7
    assert v["systems_if_baseline_retained"] == 7
    assert v["processes_if_control_pairs_scanned"] == 5
    assert 7 + v["additional_system_if_baseline_missing"] == 8
    assert not v["approved"] and not v["full_band_adequacy"]
    assert v["resource_caps"] is None
    assert v["lead_tl_tolerance_db"]["registered"] is None
