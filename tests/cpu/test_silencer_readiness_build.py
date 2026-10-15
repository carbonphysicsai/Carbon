"""Public synthetic accounting/deck checks, never solver adequacy."""

import copy
import json
import math
from pathlib import Path

import pytest

from carbon.challenge_pipeline import silencer_readiness as s

ROOT = Path(__file__).resolve().parents[2]


def action():
    return dict(zip(s.FIELDS, (62.5, 62.5, 75, 75, 30, 12.5)))


def integrals(row, r=0j, t=1 + 0j):
    area, amplitude = s.S_PORT, s.AMPLITUDE
    output = []
    for f in row["frequencies_hz"]:
        pi, po = amplitude * (1 + r), amplitude * t
        output.append(
            {
                "f_hz": f,
                "in_real": pi.real * area,
                "in_imag": pi.imag * area,
                "out_real": po.real * area,
                "out_imag": po.imag * area,
                "in_abs2": abs(pi) ** 2 * area,
                "out_abs2": abs(po) ** 2 * area,
            }
        )
    return output


def test_generators_are_deterministic_bounded_and_law_is_registered_development():
    assert s.actions(12, 9) == s.actions(12, 9)
    assert all(s.geometry(a) == a for a in s.actions(12, 9))
    q = s.questions(12, 10)
    assert q == s.questions(12, 10)
    assert all(
        5 <= r["p10_floor_db"] <= 7
        and 240 <= r["package_length_cap_mm"] <= 300
        and 120 <= r["package_diameter_cap_mm"] <= 140
        and r["Q"] == "Q3=P"
        and r["w"] == 1.0
        and r["decision"] == "F13-SCIENCE-VALUES-01"
        for r in q
    )


@pytest.mark.parametrize("count,seed", [(0, 1), (4097, 1), (True, 1), (3, "x")])
def test_bad_generator_bounds(count, seed):
    with pytest.raises(ValueError):
        s.actions(count, seed)


@pytest.mark.parametrize(
    "field,value",
    [("radius1_mm", 54), ("neck_offset_mm", 26), ("length1_mm", float("nan"))],
)
def test_bad_geometry(field, value):
    a = action()
    a[field] = value
    with pytest.raises(ValueError):
        s.geometry(a)


def test_exact_reuse_and_physical_train_disjointness():
    a = action()
    row = s.case(a, 1)
    p = s.panel([a, a], [1, 2], completed=[row], scheduled=[])
    assert len(p["cases"]) == 2
    assert p["cases"][0]["reuse"] == "COMPLETED"
    assert p["cases"][1]["reuse"] == "NEW"
    assert not p["dispatchable"]
    train = s.train_plan([a, *s.actions(3, 10)], [s.case(a, 2)])
    assert train["excluded"] == 1 and len(train["cases"]) == 3
    with pytest.raises(ValueError):
        s.panel([a], [1], completed=[row], scheduled=[row])
    stale = copy.deepcopy(row)
    stale["pins"]["image"] = "sha256:" + "a" * 64
    with pytest.raises(ValueError):
        s.train_plan([a], [stale])


def test_deck_keeps_computational_and_buyer_planes_distinct():
    d = s.deck(s.case(action(), 1))
    assert d["computational_stub_mm"] == 60 and d["reference_stub_mm"] == 10
    assert d["frequency_systems"] == 201 and d["solver_processes"] == 1
    assert "Scanning Loops = 201" in d["files"]["case.sif"]
    assert "HelmholtzSolver" in d["files"]["case.sif"]
    assert not d["dispatchable"]


def test_deembedding_retains_power_and_reverses_lead_phase():
    f = 1000
    phase = math.tau * f / s.C * 0.05
    import cmath

    r, t = s.deembed(f, 0.3 * cmath.exp(-2j * phase), 0.7 * cmath.exp(-2j * phase))
    assert r == pytest.approx(0.3) and t == pytest.approx(0.7)


def test_straight_duct_observation_has_zero_tl_not_qualified():
    row = s.case(action(), 1)
    o = s.observe(row, integrals(row), uncertainty_db=0.25)
    assert o["status"] == "OBSERVED_NOT_QUALIFIED"
    assert o["p10_tl_db"] == pytest.approx(0)
    assert o["buyer_verdict"] == "UNRESOLVED" and not o["qualified"]
    assert len(o["rows"]) == 201


def test_power_findings_and_negative_variance_never_become_candidate_failure():
    row = s.case(action(), 1)
    assert s.observe(row, integrals(row, t=1.2))["status"] == "REFERENCE_FINDING"
    data = integrals(row)
    data[0]["out_abs2"] *= 0.5
    assert s.observe(row, data)["status"] == "REFERENCE_FINDING"


def test_no_sparse_or_reordered_quantile():
    row = s.case(action(), 1)
    data = integrals(row)
    with pytest.raises(ValueError):
        s.observe(row, data[:-1])
    data[0], data[1] = data[1], data[0]
    with pytest.raises(ValueError):
        s.observe(row, data)


def test_mms_source_is_independent_known_eigenvalue():
    o = s.manufactured_helmholtz(0.5, 0.5, 0.5, 2)
    assert o["pressure_real"] == pytest.approx(1)
    assert o["source_real"] == pytest.approx(4 - 3 * math.pi**2)


def test_kit_domain_and_existing_f13_budget():
    domain = {
        "action_bounds": dict(zip(s.FIELDS, s.BOUNDS)),
        "conditions": ["air-rigid-no-flow-500-2500"],
        "observables": list(s.OBSERVABLES),
        "observer": s.PINS["observer"],
    }
    assert s.kit_domain(domain, [s.case(action(), 1)])
    domain["observer"] = "old-heated-face"
    assert not s.kit_domain(domain, [s.case(action(), 1)])
    assert s.budget_registration(ROOT)["registration_id"] == "EQUAL-BUDGET-V1"


def test_cli_and_static_contracts(capsys):
    assert s.main(["actions", "--count", "2"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 2
    docs = ROOT / "docs/development/challenge_pipeline/silencer-readiness"
    spec = json.loads((docs / "verification.json").read_text())
    assert spec["status"] == "SPECIFIED_NOT_RUN"
    assert {r["kind"] for r in spec["checks"]} == {
        "code_verification",
        "conservation",
        "convergence",
    }
    pilot = json.loads((docs / "measurement-pilot.json").read_text())
    assert pilot["cap_eur"] == 10 and not pilot["run_authorized"]
    assert pilot["hypothesis_eur_low_base_high"][2] > 10


def test_comparators_require_matched_panel_planes_and_keep_missing_data_closed():
    from test_portfolio_baselines import acoustic_payloads, fixture

    from carbon.design_search import producer_panels, tasks

    export, _ = fixture("f13", acoustic_payloads())
    with pytest.raises(ValueError, match="panel-plane observer"):
        s.compare(export)
    task = export["questions"][0]["task"]
    task["identity"]["observer_version"] = s.PINS["observer"]
    task["task_digest"] = tasks.digest(
        {k: v for k, v in task.items() if k != "task_digest"}
    )
    export = producer_panels.seal_export(
        {k: v for k, v in export.items() if k != "export_digest"}
    )
    result = s.compare(export)
    assert result["V4"] == "NOT_DEMONSTRATED"
    assert result["plane_wave"]["held_out"]["status"].startswith("HOLD_")


def test_silencer_pilot_points_to_the_existing_all_in_plan_not_a_new_grant():
    from carbon.challenge_pipeline import pilot_caps

    proposal = json.loads(
        (
            ROOT
            / "docs/development/challenge_pipeline/silencer-readiness/measurement-pilot.json"
        ).read_text()
    )
    plan = pilot_caps.validate(
        json.loads((ROOT / proposal["lifecycle_plan"]).read_text())
    )
    entry = next(
        row for row in plan["families"] if row["family"] == proposal["lifecycle_family"]
    )
    assert entry["family"] == "f13"
    assert entry["proposal_source"].endswith(
        "silencer-readiness/measurement-pilot.json"
    )
    assert proposal["run_authorized"] is False
    assert plan["dispatch_allowed"] is False and plan["solver_runs_permitted"] is False
    host = pilot_caps.host(plan)
    assert pilot_caps.host_cost(host["probe_lifetime_s"], host) <= 100
    assert pilot_caps.host_cost(host["total_lifetime_s_including_probe"], host) == 980
    assert "terminate" in plan["deployment"]["end_state"].lower()
    assert proposal["frequency_systems"] == 1004
