"""Known-bad controls exercise live checkers, never host or solver acceptance."""

import copy
import dataclasses

import pytest

from carbon.challenge_pipeline import __main__ as cli
from carbon.challenge_pipeline.readiness import checks, controls, model, runner

PIN = "sha256:" + "a" * 64
NOISE_PIN = "sha256:" + "b" * 64


def item(name):
    return next(row for row in model.load_items() if row["id"] == name)


def ctx():
    return checks.Context("example-challenge", 0, data={"validator_adapter": "valid"})


def discriminating(item, context):
    if context.challenge == "negative-control-unregistered":
        return model.Result(model.FAIL, controls.CONTROLS[item["id"]].reason)
    if "validator_adapter" not in context.data:
        return model.Result(model.FAIL, controls.CONTROLS[item["id"]].reason)
    return model.Result(model.PASS, "positive fixture")


def accept_all(*args):
    return model.Result(model.PASS, "vacuous fixture")


def reject_all(item, context):
    return model.Result(model.FAIL, controls.CONTROLS[item["id"]].reason)


def wrong_refusal(*args):
    return model.Result(model.FAIL, "missing unrelated infrastructure")


def broken(*args):
    raise RuntimeError("fixture check failed, not detection")


@pytest.mark.parametrize("name", list(controls.CONTROLS))
def test_both_signs_run_and_context_is_not_mutated(name):
    context = ctx()
    before = copy.deepcopy(dataclasses.asdict(context))
    result = controls.evaluate(item(name), context, discriminating)
    assert result["status"] == controls.CONTROL_OK
    assert result["checked_count"] == 2
    assert result["positive"]["status"] == model.PASS
    assert result["negative"]["status"] == model.FAIL
    assert all(
        result[key].startswith("sha256:")
        for key in ("checker_digest", "spec_digest", "specimen_digest")
    )
    assert dataclasses.asdict(context) == before
    assert result["measurement"]["noise_estimate"] is None
    assert result["measurement"]["minimum"] is None


def test_checker_data_mutation_cannot_escape_control_context():
    context = ctx()
    before = copy.deepcopy(context.data)

    def mutating_checker(item, actual):
        actual.data["control_local_marker"] = True
        return discriminating(item, actual)

    assert (
        controls.evaluate(item("P2"), context, mutating_checker)["status"]
        == controls.CONTROL_OK
    )
    assert context.data == before


@pytest.mark.parametrize("function", [accept_all, wrong_refusal, broken])
@pytest.mark.parametrize("name", list(controls.CONTROLS))
def test_known_bad_must_fail_for_the_specific_reason(name, function):
    result = controls.evaluate(item(name), ctx(), function)
    assert result["status"] == controls.CONTROL_FAILED
    assert controls.controlled_status(model.PASS, result) != model.PASS


@pytest.mark.parametrize("name", list(controls.CONTROLS))
def test_always_rejecting_checker_has_no_positive_witness(name):
    result = controls.evaluate(item(name), ctx(), reject_all)
    assert result["status"] == controls.UNCONTROLLED
    assert "NO_POSITIVE_WITNESS" in result["detail"]


def test_missing_control_binding_and_missing_callable_never_pass():
    assert (
        controls.evaluate(item("S3"), ctx(), accept_all)["status"]
        == controls.UNCONTROLLED
    )
    changed = {**item("P1"), "check": "scoring_registered"}
    assert (
        controls.evaluate(changed, ctx(), accept_all)["status"]
        == controls.CONTROL_FAILED
    )
    assert (
        controls.evaluate(item("P1"), ctx(), None)["status"] == controls.CONTROL_FAILED
    )


def test_actual_adapter_checker_detects_missing_adapter_without_a_host():
    # The scoring registry and adapter are real public code, not an accept stub.
    challenge = "battery-fastcharge-ageing-development-v1"
    context = checks.Context(challenge, 0, data=checks.load_challenge_data(challenge))
    result = controls.evaluate(item("P2"), context, checks.CHECKS["scoring_registered"])
    assert result["status"] == controls.CONTROL_OK
    assert "no Interface v1 validator adapter" in result["negative"]["detail"]


def test_actual_controller_checker_refuses_missing_designation(monkeypatch):
    from carbon.challenge_pipeline import admission_controllers as ac

    # Only the public metadata source is substituted; the checker is untouched.
    monkeypatch.setattr(
        ac,
        "designation",
        lambda challenge, level: (
            None
            if challenge == "negative-control-unregistered"
            else {"name": "synthetic-controller", "identity": "synthetic-identity"}
        ),
    )
    monkeypatch.setattr(ac, "pending", lambda entry: False)
    result = controls.evaluate(item("A4"), ctx(), checks.CHECKS["admission_controller"])
    assert result["status"] == controls.CONTROL_OK
    # A vacuous implementation, not just malformed metadata, must now fail.
    result = controls.evaluate(item("A4"), ctx(), accept_all)
    assert result["status"] == controls.CONTROL_FAILED


def test_registry_bindings_match_roster_and_specimen_cannot_be_hidden():
    for name, spec in controls.CONTROLS.items():
        assert item(name)["check"] == spec.check
    context = ctx()
    context.evidence_paths = {"H4": "must-never-be-opened"}
    context.cache = {"private": "must-never-be-read"}

    def check(item, actual):
        assert not actual.evidence_paths and not actual.cache
        return discriminating(item, actual)

    assert (
        controls.evaluate(item("P2"), context, check)["status"] == controls.CONTROL_OK
    )


def test_runner_invokes_live_registry_and_reports_control_count(monkeypatch, tmp_path):
    monkeypatch.setitem(checks.CHECKS, "scoring_registered", discriminating)
    monkeypatch.setattr(checks, "load_challenge_data", lambda _: ctx().data)
    report = runner.run_gate("example-challenge", only=["P2"], root=tmp_path)
    assert report["control_summary"]["passing_items"] == 1
    assert report["control_summary"]["checked_items"] == 1
    assert not report["controlled_ready"]  # subset, never all 42
    monkeypatch.setitem(checks.CHECKS, "scoring_registered", accept_all)
    report = runner.run_gate("example-challenge", only=["P2"], root=tmp_path)
    assert report["items"][0]["status"] == model.PASS  # original result remains visible
    assert report["items"][0]["controlled_status"] == controls.CONTROL_FAILED
    assert report["control_summary"]["passing_items"] == 0
    assert "CONTROL_FAILED" in runner.render_text(report)


def test_missing_controls_make_an_all_primary_pass_tree_unready(monkeypatch, tmp_path):
    for key in checks.CHECKS:
        monkeypatch.setitem(checks.CHECKS, key, accept_all)
    monkeypatch.setattr(
        runner, "load_review", lambda *args: model.Result(model.PASS, "fixture review")
    )
    monkeypatch.setattr(runner, "load_conditions", lambda *args: [])
    report = runner.run_gate("example-challenge", root=tmp_path)
    assert report["green"] is True  # legacy meaning, not rewritten
    assert report["launch_ready"] is True
    assert report["controlled_ready"] is False
    assert report["control_summary"]["passing_items"] == 0
    assert report["control_summary"]["control_failed_items"] == 3
    assert report["control_summary"]["uncontrolled_items"] == 39


def test_report_digest_binds_control_outcomes(monkeypatch, tmp_path):
    monkeypatch.setitem(checks.CHECKS, "scoring_registered", discriminating)
    monkeypatch.setattr(checks, "load_challenge_data", lambda _: ctx().data)
    report = runner.run_gate("example-challenge", only=["P2"], root=tmp_path)
    claimed = report.pop("report_digest")
    assert model.digest(report) == claimed
    report["items"][0]["control"]["negative"]["status"] = model.PASS
    assert model.digest(report) != claimed


def test_cli_cannot_return_success_for_legacy_pass_without_controls(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        runner, "run_gate", lambda *args, **kwargs: {"launch_ready": True}
    )
    monkeypatch.setattr(runner, "render_text", lambda report: "legacy pass only")
    assert cli.main(["readiness", "--challenge", "example", "--no-history"]) == 1
    assert "legacy pass" in capsys.readouterr().out


def test_cli_positive_control_is_not_an_always_refusing_route(monkeypatch):
    # A synthetic report-factory result tests only CLI routing, never 42-item
    # coverage. Paired with the legacy-only refusal above, this fails if the
    # CLI ignores controlled_ready or always returns 1.
    monkeypatch.setattr(
        runner,
        "run_gate",
        lambda *args, **kwargs: {
            "launch_ready": True,
            "controlled_ready": True,
        },
    )
    monkeypatch.setattr(runner, "render_text", lambda report: "synthetic CLI control")
    assert cli.main(["readiness", "--challenge", "example", "--no-history"]) == 0


def test_margins_are_reported_beside_same_unit_noise_not_a_qualification():
    result = controls.measurement_summary(
        {
            "scope": "SYNTHETIC_FIXTURE",
            "margins": [0.13, 1.0, 2.0],
            "unit": "mV",
            "noise_estimate": 0.359,
            "noise_unit": "mV",
            "source_digest": PIN,
            "noise_source_digest": NOISE_PIN,
        }
    )
    assert result["checked_count"] == 3
    assert result["minimum"] == 0.13
    assert result["p01"] == pytest.approx(0.1474)
    assert result["noise_estimate"] == 0.359
    assert result["status"] == "WITHIN_NOISE"
    assert "qualified" not in result


@pytest.mark.parametrize(
    "mutation",
    [
        {"noise_unit": "V"},
        {"noise_estimate": -1},
        {"noise_estimate": float("nan")},
        {"scope": "HIDDEN"},
        {"margins": []},
        {"margins": [True]},
        {"noise_source_digest": None},
    ],
)
def test_malformed_or_hidden_measurements_refuse(mutation):
    document = {
        "scope": "SYNTHETIC_FIXTURE",
        "margins": [1.0],
        "unit": "mV",
        "noise_unit": "mV",
        "noise_estimate": 0.1,
        "source_digest": PIN,
        "noise_source_digest": NOISE_PIN,
    }
    document.update(mutation)
    with pytest.raises(ValueError):
        controls.measurement_summary(document)


def test_missing_noise_remains_human_input_not_zero_noise():
    result = controls.measurement_summary(
        {
            "scope": "PUBLIC_DEVELOPMENT",
            "margins": [1.0],
            "unit": "mV",
            "source_digest": PIN,
        }
    )
    assert result["minimum"] == 1.0 and result["noise_estimate"] is None
    assert result["status"] == "HUMAN_INPUT"


def test_noise_margin_is_consumed_by_controlled_count(monkeypatch, tmp_path):
    monkeypatch.setitem(checks.CHECKS, "scoring_registered", discriminating)
    monkeypatch.setattr(checks, "load_challenge_data", lambda _: ctx().data)
    measurement = {
        "scope": "SYNTHETIC_FIXTURE",
        "margins": [0.13, 1.0],
        "unit": "mV",
        "noise_unit": "mV",
        "noise_estimate": 0.359,
        "source_digest": PIN,
        "noise_source_digest": NOISE_PIN,
    }
    report = runner.run_gate(
        "example-challenge",
        only=["P2"],
        root=tmp_path,
        public_measurements={"P2": measurement},
    )
    assert report["items"][0]["status"] == model.PASS
    assert report["items"][0]["controlled_status"] == "WITHIN_NOISE"
    assert report["control_summary"]["passing_items"] == 0
    assert "noise=0.359 mV" in runner.render_text(report)
    measurement["noise_estimate"] = 0.01
    report = runner.run_gate(
        "example-challenge",
        only=["P2"],
        root=tmp_path,
        public_measurements={"P2": measurement},
    )
    assert report["control_summary"]["passing_items"] == 1
    measurement.pop("noise_estimate")
    report = runner.run_gate(
        "example-challenge",
        only=["P2"],
        root=tmp_path,
        public_measurements={"P2": measurement},
    )
    assert report["items"][0]["controlled_status"] == "HUMAN_INPUT"
    assert report["control_summary"]["passing_items"] == 0


def test_real_p1_checker_detects_unregistered_identity(monkeypatch):
    from carbon.challenge_registry import campaigns, registry
    from carbon.reconstruction import capability_registry

    # Metadata substitutions are explicit fixtures; no real Launchpad claim.
    entry = type(
        "Entry",
        (),
        {
            "challenge_id": "example-challenge",
            "status": registry.IMPLEMENTED,
            "version": "fixture",
        },
    )()
    monkeypatch.setattr(registry, "entries", lambda: [entry])
    monkeypatch.setattr(campaigns, "campaign_for_id", lambda _: object())
    monkeypatch.setattr(
        capability_registry,
        "contract",
        lambda _: type("Contract", (), {"digest": "fixture"})(),
    )
    result = controls.evaluate(item("P1"), ctx(), checks.CHECKS["registered_l0"])
    assert result["status"] == controls.CONTROL_OK
    assert result["negative"]["detail"] == "the challenge is not in the registry"


def test_failed_primary_and_review_only_never_become_controlled_pass():
    control = controls.evaluate(item("P2"), ctx(), discriminating)
    assert controls.controlled_status(model.FAIL, control) == model.FAIL
    assert (
        controls.controlled_status(model.PASS_BY_REVIEW, control)
        == model.PASS_BY_REVIEW
    )


def test_invalid_noise_refuses_coverage_without_aborting_other_items():
    result = controls.evaluate(
        item("P2"), ctx(), discriminating, {"scope": "HIDDEN", "margins": [1.0]}
    )
    assert result["status"] == controls.CONTROL_FAILED
    assert result["checked_count"] == 0
    assert controls.controlled_status(model.PASS, result) != model.PASS


@pytest.mark.parametrize("measurement", [[], {"UNKNOWN": {}}, {"P1": {}}])
def test_measurement_subset_mismatch_fails_closed(measurement, tmp_path):
    with pytest.raises(runner.ReadinessRefused, match="control_measurement_item_scope"):
        runner.run_gate(
            "example-challenge",
            only=["P2"],
            root=tmp_path,
            public_measurements=measurement,
        )


def test_numerical_control_cannot_inherit_structural_no_noise_exemption(monkeypatch):
    monkeypatch.setitem(
        controls.CONTROLS,
        "P2",
        dataclasses.replace(controls.CONTROLS["P2"], measurement_kind="NUMERICAL"),
    )
    result = controls.evaluate(item("P2"), ctx(), discriminating)
    assert result["status"] == controls.CONTROL_OK
    assert result["measurement"]["status"] == "HUMAN_INPUT"
    assert controls.controlled_status(model.PASS, result) == "HUMAN_INPUT"
    with pytest.raises(ValueError, match="measurement_kind"):
        dataclasses.replace(controls.CONTROLS["P2"], measurement_kind="UNSPECIFIED")


def test_malformed_result_is_not_successful_detection():
    def malformed(*args):
        return model.Result(model.FAIL, None)

    result = controls.evaluate(item("P2"), ctx(), malformed)
    assert result["status"] == controls.CONTROL_FAILED
    assert result["negative"]["status"] == "ERROR"


def test_finite_extreme_values_do_not_overflow_quantile():
    summary = controls.measurement_summary(
        {
            "scope": "SYNTHETIC_FIXTURE",
            "margins": [-1e308, 1e308],
            "unit": "synthetic",
            "source_digest": PIN,
        }
    )
    assert summary["p01"] == pytest.approx(-0.98e308)
    assert summary["status"] == "HUMAN_INPUT"


@pytest.mark.parametrize(
    "challenge",
    [
        "battery-fastcharge-ageing-development-v1",
        "electric-motor-magnetics",
        "chip-cold-plate",
    ],
)
@pytest.mark.parametrize("name", ["P1", "P2"])
def test_existing_public_registration_paths_discriminate(challenge, name):
    context = checks.Context(challenge, 0, data=checks.load_challenge_data(challenge))
    result = controls.evaluate(item(name), context, checks.CHECKS[item(name)["check"]])
    assert result["status"] == controls.CONTROL_OK
