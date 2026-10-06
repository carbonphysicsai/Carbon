"""Battery construction Level 1: loss expressions (GRAPHITE-L1-BUILD-01).

Claims tested:
- the two registered variants are exactly the documents `carbon.battery.level1`
  builds, pinned by digest, recorded, and name the Test Lead's review record;
- the version-2 language: two sorts, the new operations, the signed arm, and
  version-1 documents unchanged;
- each Level-1 permission is ablatable: removing a family refuses every
  expression that uses it;
- Q3: degenerate losses run, flagged as a diagnostic, scored as the
  candidate's own result and never refunded;
- Q5: JAX only, mlp and deeponet only; other backends and families refused by
  code;
- Q6: every Level-1 built record and trial carries `rebuild: CPU-verified only`;
- R1: non-finite training is GATE_FAILED, never FAILED_INFRA;
- R2: the rebuild is JAX against JAX, never numpy, and two fresh processes
  rebuild the same parameters;
- R3: every compile refusal is typed and raised on Carbon's host before any
  pod is launched;
- WAVE-04 §1: nothing is keyed on the expression digest.
Each of R1, R2, R3 and Q3 has a mutation that makes its test fail.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from carbon.agent_campaign.attack.adapters import battery_level1 as atk
from carbon.agent_campaign.graphite import experiment as ex
from carbon.battery import level1, level1_worker, loss_terms
from carbon.challenge_validator.scoring import scoring_for
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction import loss_expressions as le

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
SCORING = scoring_for(BATTERY)
FULL = {level1.CORE, *level1.FAMILIES}
REVIEW = (
    REPOSITORY
    / "docs/development/graphite/reviews/L1_LOSS_EXPRESSIONS_TEST_LEAD_REVIEW.md"
)


def _admit(expression, arm=None, **parameters):
    return ex.admit(
        atk.strategy(expression, **parameters),
        7,
        scoring=SCORING,
        variant=dv.variant(BATTERY, 1, arm),
    )


# --- the registered variants ----------------------------------------------------------
def test_the_variants_are_registered_recorded_and_built_from_the_code():
    registry = dv.load()
    valid = registry.current[(BATTERY, 1)]
    signed = registry.arms[(BATTERY, 1, atk.SIGNED_ARM)]
    folder = Path(cr.DEVELOPMENT_VARIANT_DIR)
    for found in (valid, signed):
        document = json.loads((folder / f"{found.version}.json").read_text())
        assert document == level1.variant_document(found.version)
        assert found.status == dv.REGISTERED and found.level == 1
        assert document["participant_code"] is False
        assert document["review"]["reviewer"] == "Test Lead"
        assert document["review"]["record"].startswith(
            str(REVIEW.relative_to(REPOSITORY))
        )
    assert valid.permissions() == (level1.CORE, *level1.FAMILIES)
    assert signed.permissions() == (level1.CORE, level1.SIGNED)
    assert dv.dev_unrecorded() == {} and dv.dev_problems() == []
    assert dv.recorded_variant(signed)["development_variant"] == signed.digest
    assert dv.arm_of(signed) == atk.SIGNED_ARM and dv.arm_of(valid) is None
    # The review record holds the Test Lead's review verbatim.
    text = REVIEW.read_text()
    assert (
        "APPROVED to build" in text and "battery-l1-loss-expressions-signed-v1" in text
    )
    # A variant is never a miner-facing contract.
    for found in (valid, signed):
        assert cr.is_development_variant(found.digest)
        assert cr.is_development_variant(found.version)
        with pytest.raises(cr.DevelopmentVariantNotServed):
            cr.contract(found.version)


def test_an_arm_is_named_once_and_selected_only_by_name(tmp_path):
    registry = json.loads(
        (Path(cr.DEVELOPMENT_VARIANT_DIR) / "registry.json").read_text()
    )
    for bad in ("Signed", "", "x" * 40, 1):
        broken = json.loads(json.dumps(registry))
        broken["current"][1]["arm"] = bad
        (tmp_path / "registry.json").write_text(json.dumps(broken))
        with pytest.raises(RuntimeError):
            cr.development_variant_registry(tmp_path)
    assert dv.DEV_VARIANTS[(BATTERY, 1)].version == level1.VERSION
    with pytest.raises(dv.VariantRefused) as refused:
        dv.variant(BATTERY, 1, "unknown")
    assert refused.value.code == dv.UNREGISTERED


# --- the version-2 language -----------------------------------------------------------
def test_version_one_sets_keep_their_documents():
    from carbon.battery import level1_draft

    assert level1_draft.OPERATIONS.document()["schema"] == le.OPERATION_SET_SCHEMA
    assert not level1_draft.OPERATIONS.version2
    full = level1.operation_set(FULL)
    assert full.version2 and full.expression_schema == le.SCHEMA_V2
    assert le.OperationSet.from_document(full.document()) == full
    for broken in (
        {**full.document(), "extra": 1},
        {**full.document(), "schema": le.OPERATION_SET_SCHEMA},
        {**full.document(), "terms": "sq_error"},
    ):
        with pytest.raises(ValueError):
            le.OperationSet.from_document(broken)


@pytest.mark.parametrize(
    "expression, code",
    [
        ({"term": "err_sq_t"}, "loss_is_per_case"),
        (
            {"op": "add", "args": [{"term": "sq_error"}, {"term": "err_sq_t"}]},
            "mixed_sorts",
        ),
        (
            {"op": "mean_t", "over": "both", "arg": {"term": "sq_error"}},
            "reduction_needs_time",
        ),
        (
            {"op": "mean_t", "over": "pressure", "arg": {"term": "err_sq_t"}},
            "over_not_registered",
        ),
        ({"op": "mean_t", "arg": {"term": "err_sq_t"}}, "node_fields"),
        ({"op": "cap", "at": 1e5, "arg": {"term": "sq_error"}}, "at_outside_bounds"),
        ({"op": "expm1", "cap": 17, "arg": {"term": "sq_error"}}, "cap_outside_bounds"),
        ({"op": "neg", "arg": {"term": "sq_error"}}, "operation_not_in_the_set"),
        ({"const": 1.0}, "operation_not_in_the_set"),
        ({"op": "const", "args": []}, "operation_not_in_the_set"),
    ],
)
def test_the_valid_surface_refuses_by_code(expression, code):
    with pytest.raises(le.ExpressionRefused) as refused:
        level1.compile_for(expression, FULL)
    assert refused.value.code == code


def test_time_terms_restate_the_menu_ramps_and_reductions_follow_over():
    rng = np.random.default_rng(3)
    zhat, zt = rng.normal(size=(5, 9)), rng.normal(size=(5, 9))
    gw = rng.uniform(0.5, 1.5, size=9)

    def trajectory(z):
        return z[:, :4], z[:, 4:8]

    groups = (
        ("voltage", 0, 4),
        ("temperature", 4, 8),
        ("plating", 8, 9),
        ("capacity", 9, None),
    )
    case = loss_terms.case_terms(np, zhat, zt, gw, trajectory, groups)
    times = loss_terms.time_terms(np, zhat, zt, trajectory)
    late = level1.compile_for(
        {
            "op": "mean_t",
            "over": "both",
            "arg": {
                "op": "scale",
                "by": 2,
                "arg": {
                    "op": "mul",
                    "args": [{"term": "time_t"}, {"term": "err_sq_t"}],
                },
            },
        },
        FULL,
    )
    np.testing.assert_allclose(
        le.evaluate(late, case, np, times), case["traj_ramp_late"], rtol=1e-12
    )
    parts = sum(case["sq_error_" + g] for g in loss_terms.GROUPS)
    np.testing.assert_allclose(parts, case["sq_error"], rtol=1e-12)
    worst = level1.compile_for(
        {"op": "max_t", "over": "voltage", "arg": {"term": "err_sq_t"}}, FULL
    )
    np.testing.assert_array_equal(
        le.evaluate(worst, case, np, times),
        np.max((zhat[:, :4] - zt[:, :4]) ** 2, axis=1),
    )


def test_the_signed_arm_evaluates_its_operations():
    signed = level1.operation_set({level1.CORE, level1.SIGNED})
    case = {t: np.array([1.0, 4.0]) for t in signed.terms}
    for expression, expected in (
        ({"op": "neg", "arg": {"term": "sq_error"}}, [-1.0, -4.0]),
        ({"op": "sub", "args": [{"term": "sq_error"}, {"const": 2.0}]}, [-1.0, 2.0]),
        ({"op": "exp", "arg": {"term": "sq_error"}}, [math.e, math.e**4]),
        ({"const": -3.0}, [-3.0, -3.0]),
    ):
        got = le.evaluate(le.compile_expression(expression, signed), case, np)
        np.testing.assert_allclose(got, expected)
    with pytest.raises(le.ExpressionRefused) as refused:
        le.compile_expression({"const": 1000.0}, signed)
    assert refused.value.code == "const_outside_bounds"


# --- Q2: every permission is ablatable ------------------------------------------------
def test_removing_a_family_refuses_every_expression_that_uses_it():
    for name, expression in atk.VALID.items():
        used = level1.families_used(level1.compile_for(expression, FULL).expression)
        assert used == level1.raw_families(expression), name
        for permission in sorted(FULL):
            gate = atk.l1_gate(atk.strategy(expression), without=[permission])
            assert (gate["status"] == "OK") == (permission not in used), (
                name,
                permission,
            )
    # Every family is used by some valid construction, so each ablation bites.
    covered = set().union(*(level1.raw_families(e) for e in atk.VALID.values()))
    assert covered == FULL


# --- Q3, Q5, Q6, R3 ---------------------------------------------------------------------
def check_degenerate_losses_run_as_the_candidates_own():
    construction = atk.strategy(
        {"op": "mean_t", "over": "both", "arg": {"term": "time_t"}}
    )
    gate = atk.l1_gate(construction)
    assert gate["status"] == "OK" and gate["diagnostics"] == ["no_error_term"]
    result = atk.trial(construction)
    assert result["exit"] == 0 and result["failed_infra"] == 0
    assert result["rebuild"] == level1_worker.REBUILD_LABEL
    assert atk.candidate_owned(result)


def test_degenerate_losses_run_as_the_candidates_own():
    atk._trial.cache_clear()
    check_degenerate_losses_run_as_the_candidates_own()


def test_only_jax_mlp_and_deeponet_take_an_expression():
    expression = {"term": "sq_error"}
    for parameters, code in (
        ({"backend": "pytorch"}, "development.backend_not_served"),
        ({"backbone": "knn"}, "development.not_applicable"),
        ({"backbone": "fno"}, "development.not_applicable"),
        ({"relative_loss": True}, "development.menu_and_expression"),
    ):
        backbone = parameters.pop("backbone", "mlp")
        gate = atk.l1_gate(atk.strategy(expression, backbone=backbone, **parameters))
        assert gate["status"] == "REFUSED" and code in gate["codes"], (parameters, gate)
    assert atk.l1_gate(atk.strategy(expression, backbone="deeponet"))["status"] == "OK"
    from carbon.battery import level1_training
    from carbon.battery.compile import compile_recipe

    for family in ("knn", "fno"):
        with pytest.raises(ValueError):
            level1_training.build(family, {"ensemble_members": 1}, object())
    _, recipe = compile_recipe(atk.strategy(backend="pytorch"))
    model = level1_training.build(recipe.family, recipe.settings, object())
    with pytest.raises(ValueError):
        model.fit(None, None, 7)


def test_every_level1_record_says_its_rebuild_is_cpu_verified_only():
    built = _admit(atk.VALID["valid_late_voltage"])
    assert built["rebuild"] == "rebuild: CPU-verified only"
    assert "rebuild" not in ex.admit(atk.strategy(), 7, scoring=SCORING)
    assert "rebuild" not in _admit(None)  # a Level-1 job with no expression
    assert set(level1_worker.STAGED_MODULES) | {
        level1_worker.EXPRESSION_FILE,
        level1_worker.OPERATION_SET_FILE,
    } <= set(built["staged"])


def check_refusals_are_typed_on_the_host():
    for name, (_value, _violation, judge) in atk.ATTACKS.items():
        if judge != "gate":
            continue
        with pytest.raises(ex.Unrebuildable) as refused:
            ex.admit(
                atk.attack_strategy(name),
                7,
                scoring=SCORING,
                variant=dv.variant(BATTERY, 1),
            )
        assert refused.value.code in (
            dv.PARAMETER_REFUSED,
            "contract_refused",
            "recipe_rejected",
        ), name
        assert refused.value.issues, name
        result = atk.trial(atk.attack_strategy(name))
        assert result["stage"] == "host_compile" and result["refused"], name


def test_refusals_are_typed_on_the_host_before_any_pod(monkeypatch):
    from carbon.agent_campaign.graphite import pod_phase

    def no_pod(*args, **kwargs):
        raise AssertionError("a refused construction reached the pod phase")

    atk._trial.cache_clear()
    monkeypatch.setattr(pod_phase, "run", no_pod)
    check_refusals_are_typed_on_the_host()


# --- R1, R2 ------------------------------------------------------------------------------
def check_nonfinite_training_is_gate_failed():
    construction = atk.strategy(atk.SIGNED_ATTACKS["signed_exp_overflow"])
    result = atk.trial(construction, atk.SIGNED_ARM)
    assert result["exit"] == 0, result
    assert result["nonfinite_predictions"] and not result["eligible"]
    assert result["failed_infra"] == 0
    assert set(result["states"]) == {"GATE_FAILED"}
    assert atk.candidate_owned(result)


def test_nonfinite_training_is_gate_failed_never_failed_infra():
    atk._trial.cache_clear()
    check_nonfinite_training_is_gate_failed()


def check_the_rebuild_is_jax_only():
    compiled = level1.compile_for({"term": "sq_error"}, {level1.CORE})
    loss = loss_terms.factory(le, compiled)
    with pytest.raises(TypeError):
        loss(np, None, ())
    import jax.numpy as jnp

    assert callable(loss(jnp, lambda z: (z[:, :2], z[:, 2:4]), ()))


def test_the_rebuild_is_jax_against_jax_never_numpy():
    check_the_rebuild_is_jax_only()


def test_two_fresh_processes_rebuild_the_same_parameters():
    script = REPOSITORY / "scripts/dev/l1_rebuild_measure.py"
    digests = []
    for _ in range(2):
        done = subprocess.run(
            [sys.executable, str(script), "fit", "128", "0", "32"],
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": "/tmp",
                "JAX_PLATFORMS": "cpu",
                "PYTHONPATH": str(REPOSITORY),
            },
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        )
        digests.append(
            json.loads(done.stdout.strip().splitlines()[-1])["params_sha256"]
        )
    assert digests[0] == digests[1]


# --- Level 0 is byte for byte main's --------------------------------------------------------
#: Level-0 identities computed on origin/main (74ef52882) before Level 1 was
#: wired. `recipes.py` and `training.py` are battery's implementation modules:
#: their bytes enter every Level-0 recipe digest, so Level 1 must not touch
#: them (invariant 10: past evidence is never silently reinterpreted).
LEVEL0_PINS = {
    "implementation": "sha256:e4c4f12958ba4cbbe5e088190eaeba19cc4a8e23378c8b119ca2bbaae96cc417",
    "scaffold_recipe": "sha256:79fbc4875ba6006b7f1a6c9a88879d0fa535281cfea54be51dc956403d7498f9",
    "scaffold_built_record": "sha256:4fec51cd8a27ea005361602067c86af4625e1c9b037ef56a9eeec00b4637f6e1",
    "program": "sha256:264413438e3456605279d89aa3f066386bbf0dfaa497198a0957bdf912a9746a",
}
#: The same identities under battery implementation 2.0 (TORCH-GPU-01, the
#: PyTorch CUDA rebuild device), beside the 1.0 set above. 1.0's stay its own:
#: a record made under 1.0 recompiles and rebuilds from its read-only
#: snapshot, from main (`carbon.battery.implementation_versions`).
LEVEL0_PINS_V2 = {
    "implementation": "sha256:3d8e14542bb9a1471881dc0d5854d47f8cb01999e63a609e5e0b82a02f1b2739",
    "scaffold_recipe": "sha256:0404ce21fa5412133c5fabca74fc01a2beb5ad1983220dd5d0f5fff61d25a9ac",
    "scaffold_built_record": "sha256:ef9e89fe41027fb558c745a431c8dfff0e92fd14ada870274ba8fb1161c18374",
    "program": "sha256:264413438e3456605279d89aa3f066386bbf0dfaa497198a0957bdf912a9746a",
}
LEVEL0_PINS_BY_VERSION = {"1.0": LEVEL0_PINS, "2.0": LEVEL0_PINS_V2}


def _canonical_digest(value):
    import hashlib

    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("version", sorted(LEVEL0_PINS_BY_VERSION))
def test_level0_rebuild_artifacts_are_mains(version):
    from carbon.battery import contracts
    from carbon.battery.compile import compile_recipe
    from carbon.battery.research import SCAFFOLD
    from carbon.battery.value import panel

    pins = LEVEL0_PINS_BY_VERSION[version]
    assert contracts.implementation_digest(version) == pins["implementation"]
    scaffold = compile_recipe(SCAFFOLD, implementation=version)[1]
    assert scaffold.recipe_digest == pins["scaffold_recipe"]
    run5 = {label: s for label, s, _ in panel.PANELS["graphite-run5"]}
    baseline = compile_recipe(run5["graphite-run5-baseline"], implementation=version)[1]
    assert baseline.recipe_digest == pins["scaffold_recipe"]
    record, files, _program = SCORING.built_record(
        SCAFFOLD,
        cr.contract(BATTERY).digest,
        7,
        str(REPOSITORY),
        implementation=version,
    )
    assert _canonical_digest(record) == pins["scaffold_built_record"]
    assert record["program"] == pins["program"]
    # No Level-1 field or file appears at Level 0, not even as null.
    assert not {"development", "rebuild"} & set(record)
    assert not set(level1_worker.STAGED_MODULES) & set(files)
    assert level1_worker.EXPRESSION_FILE not in files


def _level1_train_source(train_source):
    """`training.train`'s source with the one Level-1 edit applied: the
    signature takes `case_loss`, and the per-case loss is the expression's."""
    signature = (
        "def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order):\n"
    )
    assert train_source.count(signature) == 1
    source = train_source.replace(
        signature,
        "def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order, "
        "case_loss):\n",
    )
    doc_end = (
        "    cases for the curriculum. All arrays are in the requested precision.\n"
    )
    source = source.replace(
        doc_end,
        doc_end + "\n"
        "    Level 1: `case_loss(zhat, zt, gw)` is the compiled loss expression's\n"
        "    per-case loss, which replaces the objective menu's. Everything else is\n"
        "    `training.train`, line for line.\n",
    )
    start = source.index("    def ramp(length):\n")
    end = source.index("        return base + extra\n") + len(
        "        return base + extra\n"
    )
    return (
        source[:start]
        + "    expression = case_loss\n\n"
        + "    def case_loss(p, idx):\n"
        + "        # The Level-1 loss replaces the objective menu's per-case loss.\n"
        + "        return expression(apply(p, f[idx]), z[idx], gw)\n"
        + source[end:]
    )


def test_the_level1_trainer_is_the_general_trainer_with_one_edit():
    import inspect

    from carbon.battery import level1_training, training

    expected = _level1_train_source(inspect.getsource(training.train))
    assert inspect.getsource(level1_training.train) == expected
    # The model classes override only what reads the loss.
    from carbon.battery import recipes

    assert issubclass(level1_training.LossMLP, recipes.MLP)
    assert issubclass(level1_training.LossEnsemble, recipes.Ensemble)
    own = set(vars(level1_training.LossMLP)) - {"__module__", "__doc__", "__init__"}
    assert own == {"_classic", "_groups", "fit", "_fit_general"}


# --- WAVE-04 §1 ----------------------------------------------------------------------------
def test_nothing_is_keyed_on_the_expression_digest():
    """The expression digest is a diagnostic: only the reconstruction record
    carries it, and no module reads it back."""
    readers = []
    for path in (REPOSITORY / "carbon").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "expression_digest" in text:
            readers.append(str(path.relative_to(REPOSITORY)))
    assert readers == ["carbon/battery/level1.py"]
    assert level1.IDENTITY.startswith("OWNER-GRAPHITE-TEST-WAVE-04 section 1")


# --- mutations: switching a guard off fails its test --------------------------------------
def _unchecked_reconstruct(value, admitted, granted):
    return {"canonical": json.dumps(value), "operation_set_document": {}}


def _refusing_reconstruct(value, admitted, granted):
    record = level1.reconstruct(value, admitted, granted)
    if record["diagnostics"]:
        raise dv.VariantRefused(
            dv.PARAMETER_REFUSED, issues=[("development.noop", "/")]
        )
    return record


def _numpy_tolerant(xp):
    return None


def _nan_dropping_program():
    return level1_worker._program().replace(
        "json.dumps(predictions)", "json.dumps(predictions, allow_nan=False)"
    )


MUTATIONS = {
    "r3_host_compile": (
        lambda m: m.setitem(
            dv.RECONSTRUCTIONS, (BATTERY, level1.CORE), _unchecked_reconstruct
        ),
        check_refusals_are_typed_on_the_host,
    ),
    "q3_degenerate_runs": (
        lambda m: m.setitem(
            dv.RECONSTRUCTIONS, (BATTERY, level1.CORE), _refusing_reconstruct
        ),
        check_degenerate_losses_run_as_the_candidates_own,
    ),
    "r2_jax_only": (
        lambda m: m.setattr(loss_terms, "jax_only", _numpy_tolerant),
        check_the_rebuild_is_jax_only,
    ),
    "r1_worker_keeps_nonfinite": (
        lambda m: m.setattr(level1_worker, "program", _nan_dropping_program),
        check_nonfinite_training_is_gate_failed,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_guard_off_fails_its_test(name, monkeypatch):
    disable, guard = MUTATIONS[name]
    atk._trial.cache_clear()
    disable(monkeypatch)
    try:
        with pytest.raises((AssertionError, pytest.fail.Exception)):
            guard()
    finally:
        atk._trial.cache_clear()
