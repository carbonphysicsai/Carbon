"""Battery's Level-3 development variant: training-time numerics, a menu.

BATTERY-CLIMB-1-REVIEW. The Test Lead's conditions: determinism (R1 on CPU),
a loss decrease from a fixed battery checkpoint, and default equivalence (the
default is today's polish, byte for byte). No test claims a paper's reported
improvement. Each attack-review guard has a mutation test.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")

from carbon.battery import level3, level3_numerics, level3_training, level3_worker
from carbon.battery import training as level0_training
from carbon.battery.worker import DirectBackend, WorkerFailure
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
SMALL = {"width": 16, "depth": 1, "steps": 48, "polish_steps": 6}


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {**SMALL, **parameters},
    }


def variant():
    return dv.variant(BATTERY, 3)


def compiled(**parameters):
    return dv.compile_development(strategy(**parameters), variant())


@pytest.fixture(scope="module")
def backend():
    return DirectBackend(REPOSITORY)


def rebuild(backend, **parameters):
    found = compiled(**parameters)
    record = level3_worker.numerics_record(found.reconstruction)
    state, stats = backend.reconstruct(None, found.construction, 7, record)
    return state, stats


# -- the variant -------------------------------------------------------------------


def test_the_variant_is_registered_recorded_and_built_from_the_code():
    found = variant()
    assert found.level == 3 and found.version == level3.VERSION
    assert found.document() == level3.variant_document(
        base={
            "digest": found.base_contract_digest,
            "record_sequence": found.base_record_sequence,
        }
    )
    assert dv.newest_record(found, None, None) is not None
    surfaces = {w.capability_id: w.surface for w in found.widened}
    assert {s.kind for s in surfaces.values()} == {"choice"}
    assert surfaces[level3.QUASI_NEWTON].low == level3_numerics.ROUTINES
    assert surfaces[level3.LINE_SEARCH].low == level3_numerics.SEARCHES


def test_miner_surfaces_never_resolve_level_3():
    with pytest.raises(SubmissionRefused):
        compile_submission(strategy(quasi_newton_family="bfgs"))
    with pytest.raises(SubmissionRefused):
        compile_submission(strategy(), contract_digest=variant().digest)
    assert BATTERY in cr.CONTRACTS and variant().digest not in {
        c.digest for c in cr.CONTRACTS.values()
    }


SIGNATURE = (
    "def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order):\n"
)
DOC_END = "    cases for the curriculum. All arrays are in the requested precision.\n"
POLISH = (
    "        p = polish(\n"
    '            jax, optax, p, lambda q: loss(q, everything, steps), s["polish_steps"]\n'
    "        )\n"
)


def _level3_train_source(source):
    """`training.train`'s source with the two Level-3 edits applied."""
    assert source.count(SIGNATURE) == 1 and source.count(POLISH) == 1
    source = source.replace(
        SIGNATURE,
        "def train(*, init, apply, f, z, sw, gw, trajectory, settings, seed, order, numerics):\n",
    )
    source = source.replace(
        DOC_END,
        DOC_END + "\n"
        "    Level 3: the polish stage runs the recipe's quasi-Newton routine and line\n"
        "    search (`level3_numerics.polish`). Everything else is `training.train`,\n"
        "    line for line.\n",
    )
    return source.replace(
        POLISH,
        "        p = level3_numerics.polish(\n"
        "            jax,\n"
        "            optax,\n"
        "            p,\n"
        "            lambda q: loss(q, everything, steps),\n"
        '            s["polish_steps"],\n'
        "            numerics,\n"
        "        )\n",
    )


def test_the_level3_trainer_is_the_general_trainer_with_two_edits():
    expected = _level3_train_source(inspect.getsource(level0_training.train))
    assert inspect.getsource(level3_training.train) == expected
    own = set(vars(level3_training.NumericsMLP)) - {"__module__", "__doc__", "__init__"}
    assert own == {"_classic", "fit", "parameter_count", "_fit_general"}


# -- default equivalence -----------------------------------------------------------


@pytest.mark.parametrize(
    "parameters",
    [{}, {"quasi_newton_family": "lbfgs"}, {"line_search": "strong_wolfe"}],
)
def test_the_default_menu_is_level_0_byte_for_byte(parameters):
    from carbon.challenge_validator import scoring as challenge_scoring

    scoring = challenge_scoring.scoring_for(BATTERY)
    found = compiled(**parameters)
    assert level3_worker.numerics_record(found.reconstruction) is None
    level0, _files0, program0 = scoring.built_from(
        compile_submission(strategy()), 7, REPOSITORY
    )
    built, _files, program = scoring.built_from(found, 7, REPOSITORY)
    assert program == program0 and built["staged"] == level0["staged"]
    assert "rebuild" not in built


def test_the_default_polish_is_todays_polish():
    calls = []

    def spy(jax, optax, params, objective, count):
        calls.append(count)
        return params

    original = level0_training.polish
    level0_training.polish = spy
    try:
        level3_numerics.polish(None, None, {"w": 1}, None, 3, level3_numerics.DEFAULT)
    finally:
        level0_training.polish = original
    assert calls == [3]


# -- determinism and descent -------------------------------------------------------


def test_a_dense_routine_rebuilds_the_same_parameters_twice(backend):
    first = rebuild(backend, quasi_newton_family="bfgs", line_search="backtracking")
    second = rebuild(backend, quasi_newton_family="bfgs", line_search="backtracking")
    assert first[0] == second[0]
    assert first[1]["trainer"] == "level3"


def _objective_after(backend, **parameters):
    found = compiled(**parameters)
    record = level3_worker.numerics_record(found.reconstruction) or dict(
        level3_numerics.DEFAULT, schema=level3_worker.SCHEMA
    )
    model = level3_worker.build_in_process(found.construction, record)
    from carbon.battery.recipes import Structure

    material = backend.material
    stats = model.fit(material.train, Structure(material.ocv_soc, material.ocv_v), 7)
    return stats["final_loss"]


@pytest.mark.parametrize(
    "menu",
    [
        {"quasi_newton_family": "bfgs"},
        {"quasi_newton_family": "ssbfgs"},
        {"quasi_newton_family": "ssbroyden"},
        {"quasi_newton_family": "bfgs", "line_search": "backtracking"},
        {"quasi_newton_family": "ssbroyden", "line_search": "backtracking"},
        {"quasi_newton_family": "lbfgs", "line_search": "backtracking"},
    ],
)
def test_each_routine_lowers_the_loss_from_a_fixed_checkpoint(backend, menu):
    """The same main training (a fixed checkpoint), then 6 polish steps with a
    line search: the training loss falls below the unpolished checkpoint's.
    `line_search: none` takes the unit step at the miner's own risk; no
    descent is claimed for it."""
    unpolished = _objective_after(backend, polish_steps=0, steps=SMALL["steps"] - 6)
    assert _objective_after(backend, **menu) < unpolished


# -- guards ------------------------------------------------------------------------


def check_dense_memory_is_refused_at_compile(monkeypatch):
    monkeypatch.setattr(level3, "memory_bound", lambda: 1024)
    with pytest.raises(dv.VariantRefused) as refused:
        compiled(quasi_newton_family="bfgs")
    assert (
        "development.inverse_hessian_too_large",
        "/parameters/quasi_newton_family",
    ) in [tuple(i) for i in refused.value.issues]


def test_dense_memory_is_refused_at_compile(monkeypatch):
    check_dense_memory_is_refused_at_compile(monkeypatch)


def test_the_dense_record_states_its_size_against_the_worker_bound():
    record = compiled(quasi_newton_family="ssbfgs").reconstruction[level3.QUASI_NEWTON]
    assert record["dense"] and record["lane"] == level3_worker.LANE
    assert record["inverse_hessian_bytes"] == record["parameters"] ** 2 * 4
    assert record["memory_bound_bytes"] == 4 * 1024**3


def check_line_search_evaluations_are_capped_and_counted():
    for search in level3_numerics.SEARCHES:
        record = compiled(
            quasi_newton_family="bfgs", line_search=search
        ).reconstruction[level3.LINE_SEARCH]
        cap = level3_numerics.LINE_SEARCH_STEPS[search]
        assert record["line_search_steps_cap"] == cap
        assert record["evaluations_per_polish_step"] == 1 + cap
    assert level3_numerics.LINE_SEARCH_STEPS == {
        "strong_wolfe": 20,
        "backtracking": 15,
        "none": 0,
    }


def test_line_search_evaluations_are_capped_and_counted():
    check_line_search_evaluations_are_capped_and_counted()


@pytest.mark.parametrize("field", ["quasi_newton_family", "line_search"])
def test_a_menu_choice_without_a_polish_stage_is_refused(field):
    value = "bfgs" if field == "quasi_newton_family" else "none"
    with pytest.raises(dv.VariantRefused) as refused:
        compiled(polish_steps=0, **{field: value})
    assert ("development.no_polish_stage", "/parameters/" + field) in [
        tuple(i) for i in refused.value.issues
    ]


def test_pytorch_and_other_families_are_refused():
    with pytest.raises(dv.VariantRefused):
        compiled(quasi_newton_family="bfgs", backend="pytorch")


def check_a_non_cpu_device_is_carbons_environment(monkeypatch, backend):
    import jax

    monkeypatch.setattr(jax, "default_backend", lambda: "gpu")
    with pytest.raises(WorkerFailure) as failed:
        rebuild(backend, quasi_newton_family="bfgs")
    assert failed.value.candidate is False
    assert "level3_cpu_only_dev" in failed.value.code


def test_a_non_cpu_device_is_carbons_environment(monkeypatch, backend):
    check_a_non_cpu_device_is_carbons_environment(monkeypatch, backend)


def test_the_staged_program_refuses_a_non_cpu_device_as_environment():
    from carbon.battery.worker import RECONSTRUCT_PROGRAM

    program = level3_worker.program(RECONSTRUCT_PROGRAM)
    assert 'raise ImportError("level3_cpu_only_dev")' in program
    assert "except ImportError as missing" in program  # stage "environment"


def check_divergence_is_the_candidates_own(monkeypatch, backend):
    """A non-finite polish trains to non-finite predictions, which the exam's
    finite-shape gate fails: the candidate's own fault, never FAILED_INFRA."""
    import jax.numpy as jnp

    def diverge(jax, optax, params, objective, count, numerics):
        return jax.tree_util.tree_map(lambda a: a * jnp.nan, params)

    monkeypatch.setattr(level3_numerics, "polish", diverge)
    state, _stats = rebuild(backend, quasi_newton_family="bfgs", line_search="none")
    from carbon.battery.challenge import INPUTS

    inputs = {"c": {k: 0.5 for k in INPUTS}}
    predictions = backend.infer(None, state, inputs)
    assert not np.all(np.isfinite(np.asarray(list(_numbers(predictions)), float)))


def _numbers(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _numbers(item)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield value


def test_divergence_is_the_candidates_own(monkeypatch, backend):
    check_divergence_is_the_candidates_own(monkeypatch, backend)


# -- mutations: switching a guard off fails its test ---------------------------------

MUTATIONS = {
    "dense_memory": (
        lambda m: m.setattr(level3_numerics, "hessian_bytes", lambda p, i: 0),
        lambda m, b: check_dense_memory_is_refused_at_compile(m),
    ),
    "evaluation_cap": (
        lambda m: m.setitem(level3_numerics.LINE_SEARCH_STEPS, "strong_wolfe", 10**6),
        lambda m, b: check_line_search_evaluations_are_capped_and_counted(),
    ),
    "cpu_lane": (
        lambda m: m.setattr(level3_worker, "build_in_process", _unguarded_build),
        check_a_non_cpu_device_is_carbons_environment,
    ),
}


def _unguarded_build(recipe, record):
    return level3_training.build(
        recipe.family, recipe.settings, level3_worker._menu(record)
    )


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_guard_off_fails_its_test(name, monkeypatch, backend):
    disable, guard = MUTATIONS[name]
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(monkeypatch, backend)
