"""Synthetic policy/identity tests; never authenticated model outcomes."""

import math
from copy import deepcopy
from dataclasses import asdict, replace

import pytest
from cryptography.exceptions import InvalidSignature

from carbon.audit.derivation import (
    DevelopmentDerivation,
    sign_derivation,
    verify_derivation,
)
from carbon.audit.model import AuditFailure
from carbon.audit.signing import DevelopmentReceiptSigner
from carbon.development_comparison import simulation
from carbon.development_comparison.acceptance import DevelopmentAcceptanceRef
from carbon.measurement_runtime.development import METRICS, VERSION, crossing
from carbon.rewards.core import DAY_MS, Q12
from carbon.scoring.development import RULE, compare, rule_digest, summarize


def rows(field=0.2, energy=0.01):
    return tuple(
        {
            "role": role,
            "case": f"{role}-{case}",
            "replica": replica,
            "measurement": {
                "version": VERSION,
                "metrics": dict(
                    zip(
                        METRICS,
                        (
                            float(field),
                            float(energy),
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            float(energy),
                        ),
                        strict=True,
                    )
                ),
                "reference_balance_discretization_indicator": 0.0,
                "diagnostics": {
                    "candidate_half_time": {"status": "RIGHT_CENSORED", "time": None}
                },
            },
        }
        for role in ("EVAL", "STRESS")
        for case in range(12)
        for replica in range(3)
    )


def decide(b, c, **kw):
    return compare(
        b,
        c,
        prospective=kw.pop("prospective", True),
        reference_field_indicator=kw.pop("field", 0.0),
        reference_energy_indicator=kw.pop("energy", 0.0),
        **kw,
    )


def test_geometric_score_independent_formula():
    value = summarize(rows())
    expected = (1 / 1.01) ** 0.25 * (1 / 1.2) ** 0.75
    assert value["score"] == pytest.approx(expected, abs=1e-15)
    assert 0 <= value["score"] <= 1


def test_accept_regress_equivalent_and_not_a_tie():
    assert decide(rows(), rows(0.1, 0.005)).accepted_improvement
    assert decide(rows(0.1, 0.005), rows()).disposition == "DEVELOPMENT_REGRESSION"
    assert decide(rows(), rows()).disposition == "DEVELOPMENT_EQUIVALENT"
    c = list(deepcopy(rows(0.19, 0.01)))
    for r in c:
        if r["replica"] == 2:
            r["measurement"]["metrics"]["field_time_rms"] = 0.4
    assert (
        decide(rows(), tuple(c)).disposition
        == "INDETERMINATE_REPLICA_OR_EFFECT_RESOLUTION"
    )


@pytest.mark.parametrize("metric", list(RULE["hard_limits"]))
def test_every_case_gate_cannot_be_compensated(metric):
    c = list(deepcopy(rows(0.0, 0.0)))
    c[-1]["measurement"]["metrics"][metric] = RULE["hard_limits"][metric]
    d = decide(rows(), tuple(c))
    assert d.disposition == "REJECTED_MANDATORY" and not d.accepted_improvement
    assert d.challenger["score"] > d.baseline["score"]


def test_reference_resolution_is_separate_from_practical_margin():
    assert (
        decide(rows(), rows(0.1, 0.005), field=0.0026).disposition
        == "INDETERMINATE_REFERENCE_RESOLUTION"
    )
    c = list(deepcopy(rows(0.1, 0.005)))
    c[0]["measurement"]["reference_balance_discretization_indicator"] = 0.026
    assert decide(rows(), tuple(c)).accepted_improvement
    assert not decide(rows(), rows(0.1, 0.005), prospective=False).accepted_improvement


def test_hidden_case_regression_and_stress_protection():
    c = list(deepcopy(rows(0.05, 0.01)))
    c[-1]["measurement"]["metrics"]["energy_path_rms"] = 0.04
    c[-1]["measurement"]["metrics"]["energy_path_max"] = 0.04
    assert decide(rows(), tuple(c)).disposition == "DEVELOPMENT_TRADEOFF"
    for r in c:
        if r["role"] == "STRESS":
            r["measurement"]["metrics"]["field_time_rms"] = 0.9
    assert summarize(tuple(c))["score"] < summarize(rows())["score"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "version",
        "nan",
        "negative",
        "overlap",
        "bool_replica",
        "extra",
        "cohort",
    ],
)
def test_invalid_rectangles_and_versions(mutation):
    c = list(deepcopy(rows()))
    if mutation == "missing":
        c.pop()
    elif mutation == "duplicate":
        c[-1] = c[0]
    elif mutation == "version":
        c[0]["measurement"]["version"] = "v0"
    elif mutation == "nan":
        c[0]["measurement"]["metrics"]["field_time_rms"] = math.nan
    elif mutation == "negative":
        c[0]["measurement"]["metrics"]["field_time_rms"] = -1.0
    elif mutation == "overlap":
        for r in c:
            if r["role"] == "STRESS":
                r["case"] = r["case"].replace("STRESS", "EVAL")
    elif mutation == "bool_replica":
        c[0]["replica"] = True
    elif mutation == "extra":
        c[0]["miner_claim"] = True
    elif mutation == "cohort":
        c[0]["case"] = "wrong"
    with pytest.raises(ValueError):
        decide(rows(), tuple(c))


def test_censored_timing_does_not_become_score_input():
    c = deepcopy(rows())
    c[0]["measurement"]["diagnostics"]["candidate_half_time"] = {
        "status": "OBSERVED",
        "time": 0.5,
    }
    assert summarize(c)["score"] == summarize(rows())["score"]
    assert crossing([1.0, 0.8, 0.7], [0.0, 1.0, 2.0], 0.5)["time"] is None


def test_signed_derivation_separate_from_original_receipt_and_tamper():
    signer = DevelopmentReceiptSigner(
        key_id="test-derived",
        private_key=b"x" * 32,
        valid_from_micros=1,
        valid_until_micros=100,
    )
    d = DevelopmentDerivation(
        rule_digest(),
        ("sha256:" + "1" * 64, "sha256:" + "2" * 64),
        "sha256:" + "3" * 64,
        5,
        signer.verification_key.key_id,
        signer.verification_key.public_key_digest,
        "DERIVED_COMPARISON",
    )
    sig = sign_derivation(signer, d)
    verify_derivation(d, sig, signer.verification_key, now_micros=6)
    with pytest.raises(InvalidSignature):
        verify_derivation(
            replace(d, artifact_digest="sha256:" + "4" * 64),
            sig,
            signer.verification_key,
            now_micros=6,
        )
    with pytest.raises(ValueError):
        verify_derivation(
            d, sig, replace(signer.verification_key, revoked_at_micros=6), now_micros=7
        )
    with pytest.raises(AuditFailure):
        signer.sign(d)


def fake_report(bscore, cscore, bref, cref, bart, cart, hotkey="alice"):
    def source(ref, artifact):
        return {
            "receipt_digest": "sha256:" + ref * 64,
            "authenticated_hotkey": hotkey,
            "binding": {
                "sampling_plan_digest": "sha256:" + "9" * 64,
                "training_data_commitment": "sha256:" + "8" * 64,
                "strategy_digest": "sha256:" + artifact * 64,
            },
        }

    d = asdict(decide(rows(), rows(0.1, 0.005)))
    d["baseline"]["score"] = bscore
    d["challenger"]["score"] = cscore
    return {
        "rule_digest": rule_digest(),
        "prospective": True,
        "decision": d,
        "baseline": source(bref, bart),
        "challenger": source(cref, cart),
    }


def test_simulation_real_adapter_with_explicit_synthetic_authentication_fixture(
    monkeypatch, tmp_path
):
    # Only resolver is replaced. These are synthetic adapter tests, never real accepted reports.
    refs = tuple(
        DevelopmentAcceptanceRef(
            tmp_path, "sha256:" + "a" * 64, "sha256:" + str(i) * 64
        )
        for i in range(1, 4)
    )
    docs = [
        fake_report(0.8, 0.9, "1", "2", "a", "b"),
        fake_report(0.9, 0.95, "2", "3", "b", "c"),
        fake_report(0.95, 0.99, "3", "4", "c", "d", "bob"),
    ]
    monkeypatch.setattr(
        simulation, "resolve_acceptance", lambda ref: docs[refs.index(ref)]
    )
    first = simulation.simulate((refs[0],), clock_ms=0, activation_ms=(0,))
    assert first.targets.winners[0][1] == Q12 // 2
    replay = simulation.simulate(
        (refs[0], refs[0]), clock_ms=DAY_MS, activation_ms=(0, 0)
    )
    assert replay.state.anchor_ms == 0 and replay.targets.winners[0][1] == Q12 // 4
    improved = simulation.simulate(refs[:2], clock_ms=1000, activation_ms=(0, 1000))
    assert (
        improved.state.holder.hotkey == "alice"
        and improved.state.gain_at_anchor > first.state.gain_at_anchor
    )
    takeover = simulation.simulate(refs, clock_ms=2000, activation_ms=(0, 1000, 2000))
    assert takeover.state.holder.hotkey == "bob"
    docs[1]["challenger"]["binding"]["strategy_digest"] = docs[0]["challenger"][
        "binding"
    ]["strategy_digest"]
    with pytest.raises(ValueError, match="copy"):
        simulation.simulate(refs[:2], clock_ms=1000, activation_ms=(0, 1000))
    docs[0]["decision"]["disposition"] = "DEVELOPMENT_REGRESSION"
    with pytest.raises(ValueError, match="improvement"):
        simulation.simulate(refs[:1], clock_ms=0, activation_ms=(0,))


def test_physical_tolerance_and_reference_indicator_are_not_interchangeable():
    c = list(deepcopy(rows(0.1, 0.01)))
    c[0]["measurement"]["metrics"]["energy_path_max"] = 0.049
    assert decide(rows(), tuple(c), energy=0.0015).disposition == "REJECTED_MANDATORY"
    assert decide(rows(), tuple(c), energy=0.0001).accepted_improvement


def test_projection_never_exports_source_or_case_material(monkeypatch):
    from carbon.development_comparison import acceptance
    from carbon.orchestration.development_feedback import (
        development_objective,
        project_development_acceptance,
    )

    d = asdict(decide(rows(), rows(0.1, 0.01)))
    secret = {
        "rule_digest": rule_digest(),
        "decision": d,
        "case_seed": "DO_NOT_EXPORT",
        "baseline_source": "/private/evaluator",
        "labels": [999],
    }
    monkeypatch.setattr(acceptance, "resolve_acceptance", lambda ref: secret)
    result = project_development_acceptance(object())
    assert "DO_NOT_EXPORT" not in str(result) and "/private" not in str(result)
    assert set(result["cohorts"]["baseline"]) == {"EVAL", "STRESS"}
    assert result["official_eligible"] is False
    public = development_objective()
    public["rule"]["weights"]["physics"] = 9
    assert development_objective()["rule"]["weights"]["physics"] == 0.25


@pytest.fixture
def sealed_comparison(tmp_path, monkeypatch):
    """Synthetic signed adapter fixture; the source resolver is explicitly mocked."""
    from types import SimpleNamespace

    from carbon.development_comparison import acceptance
    from carbon.development_session.profile import canonical

    template = SimpleNamespace(
        bindings={"profile": "test", "worker_image_digest": "test-image"},
        manifest={"cases": []},
    )
    monkeypatch.setattr(acceptance, "resolve_source", lambda *args, **kwargs: template)
    pin = acceptance.register(
        tmp_path,
        template_source=tmp_path / "template.json",
        quarantine_journal=tmp_path / "c10.sqlite3",
        reference_root=tmp_path,
        sessions={str(tmp_path): {}},
    )
    acceptance.registration(tmp_path, pin)
    sources = {}
    for label, number in (("baseline", "1"), ("challenger", "2")):
        sources[label] = SimpleNamespace(
            identity={
                "receipt_digest": "sha256:" + number * 64,
                "source_digest": "sha256:" + number * 64,
                "binding": {
                    "submission_id": label,
                    "strategy_digest": "sha256:" + number * 64,
                },
                "authenticated_hotkey": "synthetic",
            },
            strategy={"test": label},
        )
    monkeypatch.setattr(
        acceptance,
        "_resolve",
        lambda path, reg: (sources[path.stem], reg["created_at_micros"] + 10),
    )
    monkeypatch.setattr(acceptance, "_bundle", lambda source, path: [])
    monkeypatch.setattr(
        acceptance,
        "run_numerical",
        lambda *args, **kwargs: {
            "sources": [rows(), rows(0.1, 0.01)],
            "reference_checks": {
                "test": {"field_indicator": 0.0, "energy_indicator": 0.0}
            },
        },
    )
    ref = acceptance.create_report(
        tmp_path,
        pin,
        tmp_path / "baseline.json",
        tmp_path / "challenger.json",
        image=SimpleNamespace(image_id="test-image"),
    )
    assert acceptance.resolve_acceptance(ref)["decision"]["accepted_improvement"]
    return acceptance, ref, sources, canonical


@pytest.mark.parametrize(
    "failure", ["quarantine", "revoked_source", "superseded", "altered_artifact"]
)
def test_downstream_rechecks_source_eligibility(
    sealed_comparison, monkeypatch, failure
):
    acceptance, ref, _, _ = sealed_comparison

    def fail(*args, **kwargs):
        raise ValueError(failure)

    monkeypatch.setattr(
        acceptance, "_resolve" if failure != "altered_artifact" else "_bundle", fail
    )
    with pytest.raises(ValueError, match=failure):
        acceptance.resolve_acceptance(ref)


def test_source_identity_and_prospective_binding(sealed_comparison):
    acceptance, ref, sources, _ = sealed_comparison
    sources["challenger"].identity["source_digest"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="association"):
        acceptance.resolve_acceptance(ref)


def test_report_tamper_and_conflicting_pin(sealed_comparison):
    import json

    from carbon.development_session.profile import digest

    acceptance, ref, _, canonical = sealed_comparison
    p = ref.root / "development-acceptance.json"
    body = json.loads(p.read_bytes())
    body["payload"]["decision"]["challenger"]["score"] = 1.0
    p.write_bytes(canonical(body))
    with pytest.raises(ValueError, match="altered"):
        acceptance.resolve_acceptance(ref)
    # Updating the caller's hash does not repair a C-06 signature.
    with pytest.raises(ValueError, match="derivation"):
        acceptance.resolve_acceptance(
            replace(ref, report_digest=digest(p.read_bytes()))
        )


def test_derivation_revocation_withholds_use(sealed_comparison):
    acceptance, ref, _, _ = sealed_comparison
    (ref.root / "derivation-revoked.json").write_text("{}")
    with pytest.raises(ValueError, match="revoked"):
        acceptance.resolve_acceptance(ref)


def test_replay_cannot_change_activation(monkeypatch, tmp_path):
    ref = DevelopmentAcceptanceRef(tmp_path, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
    monkeypatch.setattr(
        simulation,
        "resolve_acceptance",
        lambda ref: fake_report(0.8, 0.9, "1", "2", "a", "b"),
    )
    with pytest.raises(ValueError, match="clock"):
        simulation.simulate((ref, ref), clock_ms=1000, activation_ms=(0, 1000))


def test_final_analytic_controls_as_repository_regression():
    from carbon.measurement_runtime.development_controls import controls

    result = controls("verification-v2")
    assert result["passed"] and len(result["checks"]) == 21
