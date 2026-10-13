"""PLT-09 batch 4 synthetic known answers and boundary mutations only."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from carbon.challenge_pipeline.readiness import checks, model, runner
from carbon.challenge_pipeline.readiness import evidence_checks as ec
from carbon.challenge_pipeline.readiness import scoring_checks as sc
from scripts.dev import readiness_panels as producer

CID = "synthetic-scoring-fixture"


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)


def commit(ctx):
    git(ctx.repository, "add", ".")
    if subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ctx.repository, check=False
    ).returncode:
        git(
            ctx.repository,
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "synthetic fixture",
        )


def write(ctx, name, value):
    path = ctx.repository / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")
    return path


def record(ctx, item):
    return ctx.data["scoring_by_level"][item][str(ctx.level)]


def registration(ctx, item):
    return json.loads((ctx.repository / record(ctx, item)["registration"]).read_bytes())


def update(ctx, item, value):
    write(ctx, record(ctx, item)["registration"], value)
    commit(ctx)


@pytest.fixture(params=[2, 3, 4])
def ctx(tmp_path, request, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    data = {"scoring_by_level": {}}
    context = checks.Context(CID, request.param, repository=root, data=data)
    adapter = types.ModuleType("_synthetic_scoring_adapter")
    adapter.__file__ = str(write(context, "adapter.py", {"synthetic": True}))
    adapter.CHALLENGE = CID
    adapter.rule = {
        "comparison": {"n_min": 2, "n_boot": 3, "alpha": 0.1, "important_min": 1},
        "equivalence_margin_rel": 0.01,
    }
    adapter.promotion_rule = lambda: {"key": "synthetic", "rule": adapter.rule}
    adapter.roster = {
        "toy-a": {"unit": "toy", "scope": "EXAM"},
        "toy-b": {"unit": "toy", "scope": "EXAM"},
    }
    adapter.gate_roster = lambda repository: adapter.roster
    monkeypatch.setitem(sys.modules, adapter.__name__, adapter)
    for item in ("S1", "S3", "H2", "H4"):
        named = {
            "challenge": CID,
            "levels": sc.LEVELS,
            "basis": "synthetic only",
            "adapter": adapter.__name__,
            "code": [],
        }
        if item == "S1":
            named["measurement"] = None
        else:
            named["registration"] = item + ".json"
            schema = {
                "S3": ec.MARGIN_REGISTRATION_SCHEMA,
                "H2": ec.OVERLAP_REGISTRATION_SCHEMA,
                "H4": sc.AUDIT_REGISTRATION_SCHEMA,
            }[item]
            value = {
                "schema": schema,
                "challenge": CID,
                "levels": sc.LEVELS,
                "basis": "synthetic only",
                "panel_digest": None,
            }
            if item == "H2":
                value.update(
                    tuning_role="toy-tuning",
                    sealed_roles=["toy-sealed"],
                    unsealed_roles=["toy-public"],
                )
            else:
                value["gates"] = [
                    dict(
                        name=name,
                        **metadata,
                        **({"fragile_below": 0.2} if item == "S3" else {}),
                    )
                    for name, metadata in adapter.roster.items()
                ]
            write(context, named["registration"], value)
        data["scoring_by_level"][item] = {
            str(level): copy.deepcopy(named) for level in sc.LEVELS
        }
    directory = "carbon/challenge_validator/confirmation_sets/"
    registry = {}
    from carbon.challenge_validator.interface import digest

    for role in ("toy-tuning", "toy-sealed", "toy-public"):
        document = {"role": role, "challenge_id": CID, "synthetic": True}
        write(context, directory + role + ".json", document)
        registry[role] = digest(document)
    write(context, directory + "registry.json", {"sets": registry})
    commit(context)
    return context


def panel(ctx, item):
    schema = {
        "S3": ec.MARGIN_PANEL_SCHEMA,
        "H2": ec.OVERLAP_PANEL_SCHEMA,
        "H4": sc.AUDIT_PANEL_SCHEMA,
    }[item]
    value = {"schema": schema, "challenge": CID, "levels": sc.LEVELS}
    if item == "S3":
        value["margins"] = {"toy-a": [0.1, 0.3], "toy-b": [1, 2]}
    elif item == "H2":
        value["groups"] = {
            role: [{"synthetic_input": i}]
            for i, role in enumerate(
                sorted({"toy-tuning", "toy-sealed", *ec.PUBLIC_PRIORS})
            )
        }
    else:
        value["populations"] = {
            population: {
                "toy-a": [
                    {"passed": True, "margin": 1},
                    {"passed": False, "margin": -0.2},
                ]
            }
            for population in sc.POPULATIONS
        }
    return value


def pin(ctx, item, value):
    path = ctx.repository.parent / (item + "-private.json")
    path.write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")
    ctx.evidence_paths[item] = str(path)
    reg = registration(ctx, item)
    reg["panel_digest"] = model.file_digest(path)
    update(ctx, item, reg)
    return path


def run(ctx, item):
    return {
        "S1": sc.promotion_margin,
        "S3": sc.gate_margin_study,
        "H2": sc.tuning_overlap,
        "H4": sc.gate_audit,
    }[item]({"id": item}, ctx)


def measurement(ctx):
    rule = sys.modules[record(ctx, "S1")["adapter"]].rule
    value = {
        "schema": sc.MEASUREMENT_RUN_SCHEMA,
        "challenge": CID,
        "levels": sc.LEVELS,
        "noise_source": "synthetic fixture noise",
        "rule_digest": model.digest(rule),
        "equivalence_margin_rel": rule["equivalence_margin_rel"],
        "method": "synthetic known answer",
        "observations": [0.01, 0.02],
    }
    path = write(ctx, "noise-run.json", value)
    measured = {k: v for k, v in value.items() if k not in ("method", "observations")}
    measured.update(
        schema=sc.MEASUREMENT_SCHEMA,
        rule_key="synthetic",
        run={"path": "noise-run.json", "sha256": model.file_digest(path)},
    )
    write(ctx, "measurement.json", measured)
    record(ctx, "S1")["measurement"] = "measurement.json"
    commit(ctx)
    return measured, value


def test_s1_structure_is_review_required_until_bound_measurement(ctx):
    assert run(ctx, "S1").status == model.REVIEW_REQUIRED
    measurement(ctx)
    result = run(ctx, "S1")
    assert result.status == model.PASS
    assert len([v for v in result.evidence if v.startswith("sha256:")]) == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("rule_key", "wrong"),
        ("rule_digest", "sha256:wrong"),
        ("equivalence_margin_rel", 0.9),
        ("noise_source", "HUMAN_INPUT"),
        ("levels", [0, 1]),
        ("challenge", "wrong"),
    ],
)
def test_s1_rejects_measurement_binding_mutations(ctx, field, value):
    measured, _ = measurement(ctx)
    measured[field] = value
    write(ctx, "measurement.json", measured)
    commit(ctx)
    assert run(ctx, "S1").status == model.FAIL


@pytest.mark.parametrize(
    "field,value",
    [
        ("observations", []),
        ("observations", [True]),
        ("method", ""),
        ("noise_source", "wrong"),
    ],
)
def test_s1_rejects_malformed_run_even_with_matching_file_pin(ctx, field, value):
    measured, value_run = measurement(ctx)
    value_run[field] = value
    path = write(ctx, "noise-run.json", value_run)
    measured["run"]["sha256"] = model.file_digest(path)
    write(ctx, "measurement.json", measured)
    commit(ctx)
    assert run(ctx, "S1").status == model.FAIL


def test_s1_rejects_missing_rule_fields_and_uncommitted_measurement(ctx):
    adapter = sys.modules[record(ctx, "S1")["adapter"]]
    del adapter.rule["comparison"]["n_min"]
    assert run(ctx, "S1").status == model.FAIL
    adapter.rule["comparison"]["n_min"] = 2
    measurement(ctx)
    write(ctx, "measurement.json", {"private_path": "secret-never-echo"})
    result = run(ctx, "S1")
    assert result.status == model.FAIL
    assert "secret-never-echo" not in repr(result)


def test_s3_known_answer_and_owner_values_remain_explicit(ctx):
    pin(ctx, "S3", panel(ctx, "S3"))
    result = run(ctx, "S3")
    assert result.status == model.PASS
    rows = json.loads(result.evidence[-1])
    assert rows[0]["minimum"] == 0.1
    assert rows[0]["p01"] == pytest.approx(0.102)
    assert rows[0]["fragile"] is True
    reg = registration(ctx, "S3")
    reg["gates"][0]["fragile_below"] = None
    update(ctx, "S3", reg)
    assert run(ctx, "S3").status == model.NOT_BUILT


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "unit", "scope", "boundary", "new-gate"]
)
def test_s3_gate_roster_mutations_fail_before_panel_absence(ctx, mutation):
    reg = registration(ctx, "S3")
    if mutation == "missing":
        reg["gates"].pop()
    elif mutation == "duplicate":
        reg["gates"].append(reg["gates"][0])
    elif mutation == "new-gate":
        sys.modules[record(ctx, "S3")["adapter"]].roster["new-owner-gate"] = {
            "unit": None,
            "scope": "EXAM",
        }
    else:
        reg["gates"][0][{"boundary": "fragile_below"}.get(mutation, mutation)] = {
            "unit": "wrong",
            "scope": "wrong",
            "boundary": True,
        }[mutation]
    update(ctx, "S3", reg)
    assert run(ctx, "S3").status == model.FAIL


@pytest.mark.parametrize("item", ["S3", "H2", "H4"])
@pytest.mark.parametrize(
    "mutation", ["digest", "level", "challenge", "inside", "duplicate-json"]
)
def test_private_panels_refuse_binding_scope_and_repository_mutations(
    ctx, item, mutation
):
    value = panel(ctx, item)
    if mutation in ("level", "challenge"):
        value["levels" if mutation == "level" else "challenge"] = (
            [0, 1] if mutation == "level" else "wrong"
        )
    path = pin(ctx, item, value)
    if mutation == "digest":
        path.write_bytes(b"{}")
    elif mutation == "inside":
        ctx.evidence_paths[item] = str(
            ctx.repository / record(ctx, item)["registration"]
        )
    elif mutation == "duplicate-json":
        path.write_bytes(b'{"private":"secret-never-echo","private":1}')
        reg = registration(ctx, item)
        reg["panel_digest"] = model.file_digest(path)
        update(ctx, item, reg)
    result = run(ctx, item)
    assert result.status == model.FAIL
    assert "secret-never-echo" not in repr(result)
    assert str(path) not in repr(result)


def test_h2_classification_missing_and_overlap_refusal(ctx):
    value = panel(ctx, "H2")
    pin(ctx, "H2", value)
    result = run(ctx, "H2")
    assert result.status == model.PASS
    assert not any("synthetic_input" in str(v) for v in result.evidence)
    value["groups"]["toy-sealed"] = value["groups"]["toy-tuning"]
    pin(ctx, "H2", value)
    assert run(ctx, "H2").status == model.FAIL
    reg = registration(ctx, "H2")
    reg["sealed_roles"] = "HUMAN_INPUT"
    update(ctx, "H2", reg)
    assert run(ctx, "H2").status == model.NOT_BUILT
    reg["unsealed_roles"] = 7
    update(ctx, "H2", reg)
    assert run(ctx, "H2").status == model.FAIL


def test_h2_rejects_incomplete_classification_and_role_digest(ctx):
    reg = registration(ctx, "H2")
    reg["unsealed_roles"] = []
    update(ctx, "H2", reg)
    assert run(ctx, "H2").status == model.FAIL
    reg["unsealed_roles"] = ["toy-public"]
    update(ctx, "H2", reg)
    write(
        ctx,
        "carbon/challenge_validator/confirmation_sets/toy-public.json",
        {"role": "wrong"},
    )
    commit(ctx)
    assert run(ctx, "H2").status == model.FAIL


def test_h4_known_answer_neutral_aggregate_and_bound_framing(ctx):
    assert run(ctx, "H4").status == model.NOT_BUILT
    path = pin(ctx, "H4", panel(ctx, "H4"))
    result = run(ctx, "H4")
    assert result.status == model.PASS
    aggregate = json.loads(result.evidence[-1])[0]["populations"]
    assert aggregate["hidden"] == {
        "checked": 2,
        "pass": 1,
        "fail": 1,
        "minimum": -0.2,
        "p01": pytest.approx(-0.188),
    }
    review_path = "carbon/challenge_pipeline/readiness/" + CID + "/reviews/H4.json"
    review = {
        "schema": runner.REVIEW_SCHEMA,
        "challenge": CID,
        "level": sc.LEVELS,
        "item": "H4",
        "reviewer": "Test Lead",
        "date": "2026-10-13",
        "decision": "PASS",
        "evidence": [{"kind": "file", "ref": "synthetic aggregate"}],
        "binding": {
            "panel_digest": model.file_digest(path),
            "registration_digest": model.file_digest(
                ctx.repository / record(ctx, "H4")["registration"]
            ),
        },
    }
    write(ctx, review_path, review)
    commit(ctx)
    assert run(ctx, "H4").status == model.PASS
    item = next(item for item in model.load_items() if item["id"] == "H4")
    review_root = ctx.repository / "carbon/challenge_pipeline/readiness"
    assert runner.evaluate_item(item, ctx, root=review_root)["status"] == model.PASS
    review["binding"]["panel_digest"] = "sha256:stale"
    write(ctx, review_path, review)
    commit(ctx)
    assert run(ctx, "H4").status == model.FAIL


@pytest.mark.parametrize(
    "mutation",
    [
        "practice-only",
        "empty-population",
        "unknown-gate",
        "extra-id",
        "nan",
        "empty-rows",
        "contradictory",
    ],
)
def test_h4_mutations_fail_closed(ctx, mutation):
    value = panel(ctx, "H4")
    populations = value["populations"]
    if mutation == "practice-only":
        populations["practice"]["toy-b"] = [{"passed": True, "margin": 1}]
    elif mutation == "empty-population":
        populations["hidden"] = {}
    elif mutation == "unknown-gate":
        populations["tuning"]["unregistered"] = [{"passed": True, "margin": 1}]
    elif mutation == "empty-rows":
        populations["hidden"]["toy-a"] = []
    else:
        row = populations["hidden"]["toy-a"][0]
        if mutation == "extra-id":
            row["case_id"] = "secret-never-echo"
        else:
            row["margin"] = float("nan") if mutation == "nan" else -1
    pin(ctx, "H4", value)
    result = run(ctx, "H4")
    assert result.status == model.FAIL
    assert "secret-never-echo" not in repr(result)


def test_missing_population_gate_is_explicit_zero_checked_not_passing(ctx):
    value = panel(ctx, "H4")
    value["populations"]["tuning"] = {"toy-b": [{"passed": True, "margin": 1}]}
    pin(ctx, "H4", value)
    result = run(ctx, "H4")
    assert result.status == model.PASS
    aggregate = json.loads(result.evidence[-1])
    assert aggregate[0]["populations"]["tuning"] == {
        "checked": 0,
        "pass": 0,
        "fail": 0,
        "minimum": None,
        "p01": None,
    }


def test_producer_refuses_unknown_custody_and_incomplete_groups_before_export(
    ctx, monkeypatch
):
    def forbidden(*args):
        pytest.fail("must refuse before any private export/read")

    monkeypatch.setattr(producer, "_export_pool", forbidden)
    monkeypatch.setattr(producer, "_private_prior", forbidden)
    reg = registration(ctx, "H2")
    with pytest.raises(ec.EvidenceInvalid):
        producer.overlap_panel(
            ctx, reg, {}, pool_config=ctx.repository.parent / "config.json"
        )
    reg["sealed_roles"] = "HUMAN_INPUT"
    with pytest.raises(ec.EvidenceInvalid):
        producer.overlap_panel(
            ctx, reg, {}, pool_config=ctx.repository.parent / "config.json"
        )


def test_s3_producer_uses_only_committed_public_source_and_exclusive_out(ctx):
    reg = registration(ctx, "S3")
    value = panel(ctx, "S3")
    value["schema"] = producer.PUBLIC_MARGINS_SCHEMA
    path = write(ctx, "toy-public-margins.json", value)
    reg["public_reference_margins"] = {
        "path": "toy-public-margins.json",
        "sha256": model.file_digest(path),
    }
    commit(ctx)
    produced = producer.margin_panel(ctx, reg, record(ctx, "S3"))
    destination = ctx.repository.parent / "produced.json"
    sha = producer.write_panel(produced, destination, ctx.repository)
    assert sha == model.file_digest(destination)
    assert destination.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        producer.write_panel(produced, destination, ctx.repository)
    with pytest.raises(ec.EvidenceInvalid):
        producer.write_panel(produced, ctx.repository / "leak.json", ctx.repository)
    reg["public_reference_margins"]["sha256"] = "sha256:wrong"
    with pytest.raises(ec.EvidenceInvalid):
        producer.margin_panel(ctx, reg, record(ctx, "S3"))


def test_unlisted_level_never_inherits_and_wrong_scope_fails(ctx):
    for item in ("S1", "S3", "H2", "H4"):
        del ctx.data["scoring_by_level"][item][str(ctx.level)]
        assert run(ctx, item).status == model.NOT_BUILT
        ctx.data["scoring_by_level"][item][str(ctx.level)] = {
            "challenge": "other",
            "levels": sc.LEVELS,
            "basis": "synthetic",
        }
        assert run(ctx, item).status == model.FAIL


def test_producer_argument_error_does_not_echo_private_paths(capsys):
    with pytest.raises(SystemExit):
        producer.main(
            [
                "S3",
                "--challenge",
                CID,
                "--level",
                "secret-never-echo",
                "--out",
                "/private",
            ]
        )
    assert "secret-never-echo" not in capsys.readouterr().err


def test_actual_battery_roster_has_separate_optional_and_study_scopes(
    tmp_path, monkeypatch
):
    from carbon.battery import readiness_evidence as adapter

    repository = Path(__file__).resolve().parents[2]
    roster = adapter.gate_roster(repository)
    assert roster["physics_gate_b15"] == {"unit": "degC", "scope": "OPT_IN_B15"}
    assert roster["near_optimism_bands"]["scope"] == "VALUE_STUDY_ONLY"
    assert roster["schema_finite"]["unit"] is None
    assert roster["paired_repeat"]["unit"] is None
    contract_path = tmp_path / adapter.physics_gate.CONTRACT
    contract_path.parent.mkdir(parents=True)
    document = json.loads((repository / adapter.physics_gate.CONTRACT).read_bytes())
    for law in document["laws"]:
        if law["id"] == "B15":
            law["adoption"] = "MEASUREMENT_ONLY"
    contract_path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
    assert "physics_gate_b15" not in adapter.gate_roster(tmp_path)
    monkeypatch.setattr(
        adapter.exam,
        "GATES",
        (*adapter.exam.GATES, types.SimpleNamespace(gate_id="new-gate")),
    )
    assert adapter.gate_roster(repository)["new-gate"]["unit"] is None


def test_h2_producer_only_calls_mock_export_after_explicit_complete_classification(
    ctx, monkeypatch
):
    value = panel(ctx, "H2")
    groups = {}
    for role, inputs in value["groups"].items():
        if role == "rotating_pool":
            continue
        path = ctx.repository.parent / (role + ".json")
        path.write_text(
            json.dumps({"cases": [{"inputs": x} for x in inputs]}),
            encoding="utf-8",
            newline="\n",
        )
        path.chmod(0o600)
        groups[role] = path
    calls = []

    def synthetic_export(config, out):
        calls.append(config)
        out.write_text(
            json.dumps(
                {"cases": [{"inputs": x} for x in value["groups"]["rotating_pool"]]}
            ),
            encoding="utf-8",
            newline="\n",
        )
        out.chmod(0o600)

    monkeypatch.setattr(producer, "_export_pool", synthetic_export)
    config = ctx.repository.parent / "synthetic-config.json"
    produced = producer.overlap_panel(
        ctx, registration(ctx, "H2"), groups, pool_config=config
    )
    assert produced == value
    assert calls == [config]
    link = ctx.repository.parent / "symlink.json"
    link.symlink_to(next(iter(groups.values())))
    with pytest.raises(ec.EvidenceInvalid):
        producer._private_prior(link, ctx.repository)


@pytest.mark.parametrize("mutation", ["empty", "nan", "missing-gate"])
def test_s3_malformed_margin_rows_fail(ctx, mutation):
    value = panel(ctx, "S3")
    if mutation == "missing-gate":
        value["margins"].pop("toy-b")
    else:
        value["margins"]["toy-a"] = [] if mutation == "empty" else [float("nan")]
    pin(ctx, "S3", value)
    assert run(ctx, "S3").status == model.FAIL


def test_audit_cli_requires_no_history_and_outside_report(capsys):
    from carbon.challenge_pipeline import __main__ as cli

    args = ["readiness", "--challenge", CID, "--audit-panel", "never-read.json"]
    assert cli.main(args) == 2
    assert "requires --no-history" in capsys.readouterr().out
    assert (
        cli.main(
            [
                *args,
                "--no-history",
                "--json",
                str(model.REPOSITORY / "never-write.json"),
            ]
        )
        == 2
    )
    assert "outside repository" in capsys.readouterr().out


@pytest.mark.parametrize("item", ["S3", "H2"])
def test_owner_input_gap_never_hides_malformed_supplied_panel(ctx, item):
    value = panel(ctx, item)
    value["margins" if item == "S3" else "groups"] = {}
    pin(ctx, item, value)
    reg = registration(ctx, item)
    if item == "S3":
        reg["gates"][0]["fragile_below"] = None
    else:
        reg["sealed_roles"] = "HUMAN_INPUT"
    update(ctx, item, reg)
    assert run(ctx, item).status == model.FAIL


def test_unexpected_adapter_error_cannot_disclose_private_path(ctx):
    def fail():
        raise RuntimeError("secret-never-echo")

    sys.modules[record(ctx, "S1")["adapter"]].promotion_rule = fail
    result = run(ctx, "S1")
    assert result.status == model.FAIL
    assert "secret-never-echo" not in repr(result)


def test_s1_boolean_margin_cannot_equal_numeric_zero(ctx):
    sys.modules[record(ctx, "S1")["adapter"]].rule["equivalence_margin_rel"] = 0
    measured, _ = measurement(ctx)
    measured["equivalence_margin_rel"] = False
    write(ctx, "measurement.json", measured)
    commit(ctx)
    assert run(ctx, "S1").status == model.FAIL
