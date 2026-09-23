"""D4 construction controls cannot select scientific or network authority."""

import json
from dataclasses import replace

import pytest

from carbon import construction as c
from carbon.development_session.contracts import build_contracts
from carbon.development_session.research_catalog import (
    RecipeRejected,
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


def test_resolved_plan_training_exception_rejects_altered_consumer():
    compiled, _ = compile_recipe(recipe(h1_weight=0.1))
    plan = compiled.construction_plan
    surface = next(s for s in plan.resolved_surfaces if s.surface_id == "h1_weight")
    with pytest.raises(c.ConstructionValidationError):
        changed = replace(
            surface, consumer_target=c.ConsumerTarget("scorer", "h1_weight")
        )
        replace(
            plan,
            resolved_surfaces=tuple(
                changed if s is surface else s for s in plan.resolved_surfaces
            ),
        )


def named(parameters, backbone="fno"):
    """The (code, path) pairs a rejected recipe names."""
    with pytest.raises(RecipeRejected) as caught:
        compile_recipe(recipe(backbone, **parameters))
    return {(i.code, i.path) for i in caught.value.rejected.issues}


@pytest.mark.parametrize(
    "refused,accepted,issue",
    [
        # The physics ramp multiplies only the PDE term.
        (
            {"physics_warmup_steps": 5},
            {"physics_warmup_steps": 5, "pde_weight": 0.1},
            ("parameter.dependency_unsatisfied", "/parameters/physics_warmup_steps"),
        ),
        # EMA weights reach predictions only through EMA inference.
        (
            {"ema_decay": 0.9},
            {"ema_decay": 0.9, "inference_weights": "ema"},
            ("parameter.dependency_unsatisfied", "/parameters/ema_decay"),
        ),
        (
            {"ema_decay": 0.9, "inference_weights": "params"},
            {"ema_decay": 0.9, "inference_weights": "ema"},
            ("parameter.dependency_unsatisfied", "/parameters/ema_decay"),
        ),
    ],
)
def test_a_supplied_field_that_would_be_ignored_is_refused_by_name(
    refused, accepted, issue
):
    """Specimen for each refusal: the same value is accepted where it acts."""
    assert named(refused) == {issue}
    compile_recipe(recipe(**accepted))


def test_the_defaults_are_not_refused_for_what_the_miner_did_not_supply():
    """Defaulted values with no effect are Carbon's choice, not the miner's."""
    _, profile = compile_recipe(recipe())
    train = json.loads(profile.train_config_json)
    assert train["pde_weight"] == 0 and train["inference_weights"] == "params"


@pytest.mark.parametrize(
    "parameters,issue",
    [
        ({"n_modes": 7}, ("parameter.domain_mismatch", "/parameters/n_modes")),
        ({"width": 7}, ("parameter.domain_mismatch", "/parameters/width")),
    ],
)
def test_backend_rules_name_their_field(parameters, issue):
    assert named(parameters) == {issue}


def test_every_rebuild_issue_is_reported_at_once():
    assert named({"n_modes": 7, "width": 7, "ema_decay": 0.5}) == {
        ("parameter.domain_mismatch", "/parameters/n_modes"),
        ("parameter.domain_mismatch", "/parameters/width"),
        ("parameter.dependency_unsatisfied", "/parameters/ema_decay"),
    }


def test_a_rejected_recipe_reaches_the_miner_as_named_issues_not_a_failure():
    """The research protocol's compile result carries each issue's code and path."""
    from carbon import research
    from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
    from carbon.development_session.contracts import strategy_limits
    from carbon.development_session.profile import CHALLENGE
    from carbon.development_session.research_service import Compiler

    contracts = research_contracts()
    compiler = Compiler(
        candidate_assembly=contracts.assembly,
        candidate_assembly_ref=contracts.assembly.to_ref(),
        parameter_catalog=contracts.catalog,
        parameter_catalog_ref=contracts.catalog.to_ref(
            candidate_assembly=contracts.assembly
        ),
        authoring_origin=contracts.origin,
        authoring_artifacts=contracts.artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )

    def compile_(strategy):
        return compiler.compile_strategy(
            research.CompileStrategyRequest(
                CHALLENGE, strategy, contracts.assembly.training_support_ref
            )
        )

    result = compile_(recipe(ema_decay=0.9))
    assert result.accepted is False
    assert [(i.code, i.path) for i in result.issues] == [
        ("parameter.dependency_unsatisfied", ("parameters", "ema_decay"))
    ]
    # B-02B's own rejections arrive the same way.
    unknown = compile_(recipe(curriculum=1))
    assert unknown.accepted is False
    assert [i.code for i in unknown.issues] == ["parameter.unknown"]
    # Specimen: the repaired recipe compiles.
    assert compile_(recipe(ema_decay=0.9, inference_weights="ema")).accepted


def test_physics_attention_is_rebuilt_with_every_field_it_accepts():
    parameters = {
        "width": 32,
        "depth": 3,
        "heads": 4,
        "slices": 8,
        "expansion": 3,
        "remat": True,
    }
    _, profile = compile_recipe(recipe("physics_attention", **parameters))
    model = json.loads(profile.model_config_json)
    assert model["kind"] == "physics_attention1d"
    for key, value in parameters.items():
        assert model[key] == value


@pytest.mark.parametrize(
    "backbone,field",
    [
        ("fno", "heads"),
        ("fno", "slices"),
        ("deeponet", "expansion"),
        ("physics_attention", "n_modes"),
        ("physics_attention", "branch_points"),
    ],
)
def test_a_field_of_another_family_is_refused_by_name(backbone, field):
    assert named({field: 4}, backbone) == {
        ("parameter.not_applicable", f"/parameters/{field}")
    }


def test_attention_width_must_split_across_its_heads():
    assert named({"width": 30, "heads": 4}, "physics_attention") == {
        ("parameter.dependency_unsatisfied", "/parameters/heads")
    }
    # Specimen: the same heads with a divisible width compiles.
    compile_recipe(recipe("physics_attention", width=32, heads=4))


def test_widening_the_research_catalog_leaves_the_other_catalogs_unchanged():
    """The session and GPU catalogs keep their own backbones; the research one
    is the only one that offers attention."""
    from carbon.development_session.gpu_research import gpu_catalog, gpu_contracts

    def backbones(contracts):
        entry = next(
            e for e in contracts.catalog.entries if e.surface_id == "strategy_backbone"
        )
        return tuple(entry.domain.allowed_ids), {
            o.selector_token for o in contracts.assembly.backbone_surface.options
        }

    assert backbones(build_contracts()) == (
        ("fno", "deeponet"),
        {"fno", "deeponet"},
    )
    assert backbones(gpu_contracts())[1] == {"fno", "deeponet"}
    assert gpu_catalog()["backbones"] == ["fno", "deeponet"]
    assert "heads" not in gpu_catalog()["surfaces"]
    # Specimen: the research catalog does offer it, and its fields.
    assert "physics_attention" in backbones(research_contracts())[0]
    from carbon.development_session.research_catalog import public_catalog

    assert public_catalog()["surfaces"]["heads"]["architecture"] == "physics_attention"
