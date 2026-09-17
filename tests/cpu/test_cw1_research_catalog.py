"""D4 construction controls cannot select scientific or network authority."""

import json
from dataclasses import replace

import pytest

from carbon import construction as c
from carbon.development_session.contracts import build_contracts
from carbon.development_session.research_catalog import (
    compile_recipe,
    research_contracts,
)


def recipe(backbone="fno", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": backbone,
        "parameters": parameters,
    }


def test_old_catalog_stays_bounded_and_new_identity_is_distinct():
    old = build_contracts()
    assert type(old.compile(recipe(steps=512))) is c.CompileRejected
    compiled, profile = compile_recipe(recipe(steps=512, enforce_mean=True))
    assert type(compiled) is c.CompileAccepted
    assert json.loads(profile.train_config_json)["steps"] == 512
    assert json.loads(profile.task_config_json)["enforce_mean"] is True
    assert old.assembly.to_ref() != research_contracts().assembly.to_ref()


@pytest.mark.parametrize(
    "field,value",
    [
        ("weight_decay", 0.002),
        ("h1_weight", 0.1),
        ("pde_weight", 0.01),
        ("inference_weights", "ema"),
    ],
)
def test_training_weight_controls_map_only_to_train(field, value):
    _, profile = compile_recipe(recipe(**{field: value}))
    assert json.loads(profile.train_config_json)[field] == value
    assert field not in json.loads(profile.task_config_json)
    assert field not in json.loads(profile.model_config_json)


@pytest.mark.parametrize(
    "name",
    [
        "score_weights",
        "weight",
        "gate",
        "official_seed",
        "scoring_weights",
        "publish_weights",
    ],
)
def test_scientific_and_network_controls_remain_rejected(name):
    with pytest.raises(ValueError):
        compile_recipe(recipe(**{name: 0.5}))


@pytest.mark.parametrize(
    "consumer,field,surface",
    [
        ("scorer", "h1_weight", "h1_weight"),
        ("carbon_jax_lab_train", "scoring_weights", "scoring_weights"),
        ("carbon_jax_lab_train", "h1_weight", "score_weights"),
        ("carbon_jax_lab_train", "weight", "weight"),
    ],
)
def test_training_exception_cannot_change_owner_or_field(consumer, field, surface):
    contracts = research_contracts()
    entry = next(e for e in contracts.catalog.entries if e.surface_id == "h1_weight")
    with pytest.raises(c.ConstructionValidationError):
        altered = replace(
            entry, surface_id=surface, consumer_target=c.ConsumerTarget(consumer, field)
        )
        entries = tuple(altered if e is entry else e for e in contracts.catalog.entries)
        replace(contracts.catalog, entries=entries)


@pytest.mark.parametrize(
    "backbone,parameters",
    [
        ("deeponet", {"depth": 2}),
        ("deeponet", {"n_modes": 8}),
        ("fno", {"branch_points": 16}),
        ("fno", {"n_modes": 7}),
        ("fno", {"width": 7}),
        ("fno", {"steps": 5, "warmup_steps": 5}),
        ("fno", {"steps": True}),
        ("fno", {"learning_rate": float("nan")}),
    ],
)
def test_ignored_or_invalid_controls_fail_before_execution(backbone, parameters):
    with pytest.raises(ValueError):
        compile_recipe(recipe(backbone, **parameters))


def test_catalog_pins_every_selected_control_into_reconstruction():
    parameters = {
        "steps": 100,
        "width": 32,
        "depth": 3,
        "n_modes": 24,
        "remat": True,
        "hard_initial_condition": False,
        "enforce_mean": True,
        "batch_size": 4,
        "microbatches": 2,
        "learning_rate": 0.001,
        "min_learning_rate_ratio": 0.2,
        "warmup_steps": 10,
        "weight_decay": 0.003,
        "clip_norm": 2.0,
        "beta1": 0.8,
        "beta2": 0.99,
        "adam_epsilon": 1e-7,
        "ema_decay": 0.9,
        "relative_loss": True,
        "h1_weight": 0.2,
        "pde_weight": 0.1,
        "physics_warmup_steps": 20,
        "inference_weights": "ema",
    }
    _, profile = compile_recipe(recipe(**parameters))
    actual = {}
    for document in (
        profile.model_config_json,
        profile.task_config_json,
        profile.train_config_json,
    ):
        actual.update(json.loads(document))
    for key, value in parameters.items():
        assert actual[key] == value
