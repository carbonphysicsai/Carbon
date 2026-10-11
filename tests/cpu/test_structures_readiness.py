"""Synthetic registration/observer/ROM tests only; no reference solver calls."""

import copy
import hashlib

import pytest
from test_design_search_equal_budget import panel as toy_panel

from carbon.challenge_pipeline import structures_readiness as s
from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget, structures_budget


def registration():
    pins = {
        "image": s.IMAGE,
        "mesh_image": s.MESH_IMAGE,
        "material": s.tasks.digest(s.MATERIAL),
        "observer": "sha256:" + "a" * 64,
    }
    for k, filename in (("deck", "f08_deck.py"), ("proof", "f08_proof.py")):
        pins[k] = (
            "sha256:"
            + hashlib.sha256(
                (
                    s.ROOT / "scripts/dev/reference_packages/calculix" / filename
                ).read_bytes()
            ).hexdigest()
        )
    return s.seal(
        {
            "schema": s.SCHEMA,
            "family": "f08",
            "scope": "SYNTHETIC_FIXTURE",
            "authority": "toy registration, not an operator grant",
            "grammar": {
                k: {"min": lo, "max": hi, "step": step}
                for k, (lo, hi), step in zip(
                    s.FIELDS, s.BOUNDS, (10, 5, 0.5, 1, 0.5, 5)
                )
            },
            "P": {str(v): 1 / 3 for v in s.DAMPING},
            "Q": {str(v): w for v, w in zip(s.DAMPING, (0.5, 0.25, 0.25))},
            "w": {str(v): 1 / 3 for v in s.DAMPING},
            "pins": pins,
        }
    )


def coordinates():
    return dict(zip(s.FIELDS, (220, 80, 6, 12, 4, 40)))


def case():
    return s.case(registration(), coordinates(), 0.01)


def observation(c):
    grid = [80 + k / 10 for k in range(5201)]
    return {
        "case_digest": c["case_digest"],
        "phase": "exp(+i omega t)",
        "mass_kg": 0.3,
        "static_tip_mm_per_n": 0.02,
        "frequency_hz": grid,
        "tip_real": [0.1] * len(grid),
        "tip_imag": [0] * len(grid),
        "probe_real": [0.5] * len(grid),
        "probe_imag": [0] * len(grid),
        "eigen_hz": [100] + [1000 + i for i in range(47)],
    }


def uncertainty(c):
    return {
        "case_digest": c["case_digest"],
        "accepted_receipt_digest": "sha256:" + "b" * 64,
        "mass_kg": 0.001,
        "static_tip_mm_per_n": 0.001,
        "tip_peak_mm_per_n": 0.005,
    }


def test_deterministic_valid_actions_and_separate_condition_laws():
    r = registration()
    a = s.actions(r, seed=5, count=16)
    assert a == s.actions(r, seed=5, count=16)
    assert len({s.tasks.digest(v) for v in a}) == 16
    for v in a:
        assert s.action(r, v) == v
    assert s.conditions(r, seed=1, count=10) == s.conditions(r, seed=1, count=10)
    assert r["P"] != r["Q"] and r["P"] == r["w"]


@pytest.mark.parametrize(
    "field,value", [("scope", "EVAL"), ("grammar", {}), ("P", {"0.01": 1})]
)
def test_missing_law_or_hidden_scope_stays_closed(field, value):
    r = registration()
    r.pop("registration_digest")
    r[field] = value
    with pytest.raises(ValueError):
        s.validate(s.seal(r))


def test_lattice_rungs_pins_and_tampering_refused():
    r, a = registration(), coordinates()
    a["length_mm"] = 221
    with pytest.raises(ValueError):
        s.case(r, a, 0.01)
    with pytest.raises(ValueError):
        s.case(r, coordinates(), 0.03)
    with pytest.raises(ValueError):
        s.case(r, coordinates(), 0.01, modes=13)
    c = case()
    c["action"]["length_mm"] = 222
    with pytest.raises(ValueError):
        s.deck(c)


def test_reuse_does_not_renew_acquisition_when_sampling_registration_changes():
    c = case()
    other = copy.deepcopy(c)
    other["registration_digest"] = "sha256:" + "c" * 64
    other["case_digest"] = s.tasks.digest(
        {k: v for k, v in other.items() if k != "case_digest"}
    )
    p = s.panel([c, c, other], completed=[other], scheduled=[])
    assert len(p["tuples"]) == 1 and p["tuples"][0]["reuse"]
    assert not p["dispatch_allowed"]
    with pytest.raises(ValueError):
        s.panel([c], completed=None, scheduled=[])


def test_deck_wraps_actual_3D_source_without_docker_or_any_solver(monkeypatch):
    import subprocess

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: pytest.fail("runner called")
    )
    d = s.deck(case())
    compile(d["mesh_python"], "draft.py", "exec")
    assert "occ.cut" in d["mesh_python"] and "Mesh.ElementOrder" in d["mesh_python"]
    assert "*FREQUENCY,STORAGE=YES" in d["ccx_template"]
    assert "*MODAL DAMPING" in d["ccx_template"] and "*STATIC" in d["ccx_template"]
    assert "__CONSISTENT_TRI6" in d["ccx_template"]
    assert d["status"] == "DRAFT_UNVERIFIED_NOT_RUNNABLE" and not d["dispatch_allowed"]


def test_observer_tip_gate_not_probe_gate_and_close_call_unresolved():
    c, d = case(), observation(case())
    assert s.observe(c, d)["verdict"] == "UNRESOLVED"
    out = s.observe(c, d, uncertainty=uncertainty(c))
    assert out["verdict"] == "FEASIBLE" and out["probe_peak_mm_per_n"] == 0.5
    assert out["values"]["tip_peak_mm_per_n"] == 0.1 and not out["qualified"]
    d["tip_real"] = [0.15] * len(d["frequency_hz"])
    assert s.observe(c, d, uncertainty=uncertainty(c))["verdict"] == "UNRESOLVED"
    d["tip_real"] = [0.17] * len(d["frequency_hz"])
    assert s.observe(c, d, uncertainty=uncertainty(c))["verdict"] == "INFEASIBLE"


def test_coarse_peak_grid_wrong_phase_missing_probe_cannot_be_reference_truth():
    c, d = case(), observation(case())
    for key in ("frequency_hz", "tip_real", "tip_imag", "probe_real", "probe_imag"):
        d[key] = d[key][::10]
    assert s.observe(c, d, uncertainty=uncertainty(c))["verdict"] == "UNRESOLVED"
    assert not s.observe(c, d)["grid_resolved"]
    d["phase"] = "exp(-i omega t)"
    with pytest.raises(ValueError):
        s.observe(c, d)


def test_common_design_needs_all_damping_and_no_safe_curve_compensates_failure():
    rows = []
    for zeta in s.DAMPING:
        c = s.case(registration(), coordinates(), zeta)
        rows.append({"case": c, "data": observation(c), "uncertainty": uncertainty(c)})
    assert s.design_verdict(rows)["verdict"] == "FEASIBLE"
    assert s.design_verdict(rows[:2])["verdict"] == "UNRESOLVED"
    rows[0]["data"]["tip_real"] = [0.2] * len(rows[0]["data"]["frequency_hz"])
    assert s.design_verdict(rows)["verdict"] == "INFEASIBLE"
    rows[1] = rows[0]
    with pytest.raises(ValueError, match="duplicate"):
        s.design_verdict(rows)
    d = observation(c)
    d["probe_imag"].pop()
    with pytest.raises(ValueError):
        s.observe(c, d)


def test_whole_geometry_TRAIN_holdout_and_kit_full_domain_hook():
    r, c = registration(), case()
    renamed_rung = s.case(r, coordinates(), 0.02, h_mm=1.7, modes=24)
    assert s.train_plan([renamed_rung], [c])["cases"] == []
    kit = {
        "scope": r["scope"],
        "grammar": r["grammar"],
        "damping": list(s.DAMPING),
        "band_hz": [80, 600],
        "observables": list(s.OBSERVABLES),
        "pins": r["pins"],
    }
    assert s.kit_hook(r, [c], kit)["covered"]
    kit["damping"] = [0.01]
    with pytest.raises(ValueError):
        s.kit_hook(r, [c], kit)


def test_cubic_MMS_derived_body_force_and_zero_origin():
    zero = s.manufactured(0, 0, 0)
    assert zero["u_mm"] == [0, 0, 0]
    assert zero["body_force_n_mm3"] == [0, 0, 0]
    result = s.manufactured(1, 2, 3)
    assert result["u_mm"] == pytest.approx([0.0001, 0.0008, 0.0027])
    assert result["body_force_n_mm3"][1] == pytest.approx(
        2 * result["body_force_n_mm3"][0]
    )


def test_budget_keeps_historical_contract_and_reuses_shared_attempt_accounting():
    raw = structures_budget.proposal()
    accepted = structures_budget.validate(raw)
    with pytest.raises(br.BudgetRegistrationError):
        br.validate(raw)
    cap = accepted.cap("f08", "base")
    ledger = br.BudgetLedger(cap)
    assert ledger.charge_overhead({"wall_s": 5, "core_s": 5})
    for _ in range(8):
        assert ledger.charge_solver_attempt(
            {"wall_s": 10, "core_s": 10}, {"wall_s": 10, "core_s": 10}
        )
    assert not ledger.charge_solver_attempt(
        {"wall_s": 10, "core_s": 10}, {"wall_s": 10, "core_s": 10}
    )
    p = toy_panel("f08")
    p["registrations"]["cost_plan"] = structures_budget.ID
    p["budgets"] = [accepted.cap("f08", tier).time_compute for tier in br.TIERS]
    p["panel_digest"] = equal_budget._digest(
        {k: v for k, v in p.items() if k != "panel_digest"}
    )
    result = equal_budget.compare(
        p, registration=raw, bootstrap_replicates=100, confidence=0.9, seed=1
    )
    assert result["challenge"] == "f08"


def test_wrapper_uses_strong_cross_geometry_ROM_and_exports_query_ranking():
    from test_reduced_baselines import fixture

    export, body = fixture("f08")
    report = s.compare(export, operators=body)
    assert report["equal_budget_screening"]
    assert report["claims"]["tested_challenge"] is False
