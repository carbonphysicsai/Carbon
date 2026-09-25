"""Battery construction contract (OWNER-BATTERY-TESTNET-01, M1; OD-1 and OD-8).

Claims tested:
- construction contracts are per Challenge: one registry, one compiler, and
  each Challenge resolves only its own contract. A Burgers family under battery
  is refused by name, and the reverse;
- "can I submit this?" names every refusal for every Challenge: an unknown
  Challenge, family or field, a research-only item and an inapplicable field;
- submissions stay declarative: code, weights, datasets and seeds are refused;
- the contract digest is per Challenge version, changes when the vocabulary
  changes, and a mismatch is refused by name;
- a compiled recipe cannot be built from raw values;
- every battery surface changes what Carbon rebuilds, the same seed gives the
  same weights, and the promoted math is bit-identical to the campaign's
  research recipes;
- Burgers keeps its vocabulary and lanes.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import challenge as ch
from carbon.battery.compile import BatteryRecipe, compile_recipe, rebuild
from carbon.development_session.design_check import check_design
from carbon.development_session.research_catalog import RecipeRejected
from carbon.reconstruction import capability_registry as r
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    check_contract_digest,
    compile_submission,
    validate_for_challenge,
)

BATTERY, BURGERS = r.BATTERY_CHALLENGE, r.BURGERS_CHALLENGE


def strategy(challenge=BATTERY, backbone="mlp", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": challenge,
        "backbone": backbone,
        "parameters": parameters,
    }


def refusals(value):
    return {(i.code, i.path) for i in validate_for_challenge(value).errors}


# --- Per-Challenge contracts (OD-8). ---


def test_each_challenge_has_its_own_contract_and_digest():
    assert set(r.CONTRACTS) == {BURGERS, BATTERY}
    assert r.contract(BATTERY).identity == (
        "carbon.battery-fastcharge-ageing-development.v1"
    )
    assert r.contract_digest(BATTERY) != r.contract_digest(BURGERS)
    assert r.contract_digest(BATTERY) == r.contract(BATTERY).digest  # stable
    assert dict(r.rebuildable_families(BATTERY)) == {
        "knn": "battery_knn",
        "mlp": "battery_mlp",
        "deeponet": "battery_deeponet",
    }
    # The same capability id carries a status per Challenge.
    assert r.status_map("model_family.fno") == {
        BURGERS: "rebuildable_development",
        BATTERY: "research_only",
    }
    assert r.status_map("model_family.mlp") == {BATTERY: "rebuildable_development"}
    with pytest.raises(r.UnknownChallenge):
        r.contract("battery-charge-degradation")


def test_the_digest_pins_the_vocabulary():
    item = r.contract(BATTERY)
    widened = tuple(
        (
            replace(c, surface=replace(c.surface, high=1024))
            if c.capability_id == "architecture.width"
            else c
        )
        for c in item.capabilities
    )
    assert replace(item, capabilities=widened).digest != item.digest
    assert replace(item, envelope=()).digest != item.digest


def test_a_contract_cannot_claim_what_it_does_not_rebuild():
    item = r.contract(BATTERY)
    with pytest.raises(ValueError):  # a lane of a family it does not rebuild
        replace(item, lanes=(("gpu", ("fno",)),))
    with pytest.raises(ValueError):  # a field for a family it lacks
        replace(
            item,
            capabilities=tuple(
                c for c in item.capabilities if c.capability_id != "model_family.knn"
            ),
        )
    with pytest.raises(ValueError):  # duplicate ids
        replace(item, capabilities=item.capabilities + item.capabilities[:1])
    assert replace(item, lanes=(("gpu", ("mlp",)),)).lanes  # specimen


def test_burgers_keeps_its_vocabulary_and_lanes():
    from carbon.development_session.contracts import SESSION_BACKBONES
    from carbon.development_session.gpu_research import GPU_BACKBONES

    assert r.REGISTRY is r.contract(BURGERS).capabilities
    assert SESSION_BACKBONES == ("fno", "deeponet")
    # The GPU lane offers every family Carbon rebuilds for Burgers.
    assert GPU_BACKBONES == tuple(s for s, _ in r.rebuildable_families(BURGERS))
    assert r.lane_families(BURGERS, "gpu_diagnostic") == GPU_BACKBONES
    # The default public projection is the historical Burgers one: no fields
    # were added to it.
    assert set(r.public_registry()) == {"schema", "status_meaning", "capabilities"}
    assert r.public_registry(BATTERY)["contract_digest"] == r.contract_digest(BATTERY)


def test_every_battery_consumer_derives_from_the_registry():
    from carbon.battery.contracts import battery_contracts

    contracts = battery_contracts()
    options = contracts.assembly.backbone_surface.options
    assert [o.selector_token for o in options] == ["knn", "mlp", "deeponet"]
    surfaces = {e.surface_id for e in contracts.catalog.entries}
    assert surfaces == {"strategy_backbone", *r.catalog_surfaces(BATTERY)}


def test_every_reviewed_capability_has_a_battery_status():
    """Research time: the whole construction review is answered for battery."""
    statuses = {}
    for c in r.REGISTRY:
        found = r.realizer(c.capability_id, BATTERY)
        assert found is not None, c.capability_id
        statuses[c.capability_id] = found.status
    rebuildable = [
        i for i, s in statuses.items() if s is r.Status.REBUILDABLE_DEVELOPMENT
    ]
    assert len(statuses) == 92 and len(rebuildable) >= 45
    for optimizer in ("lion", "lamb", "adafactor", "muon", "prodigy", "sam"):
        assert (
            r.status_map("optimizer." + optimizer)[BATTERY] == "rebuildable_development"
        )
    assert r.status_map("schedule.sgdr")[BATTERY] == "rebuildable_development"
    assert r.status_map("inference.precision")[BATTERY] == "rebuildable_development"
    # Validation is JAX-only: the other backends and the PyBaMM reference are
    # excluded for battery, not merely pending.
    for name in (
        "model_family.pytorch_backend",
        "model_family.julia_backend",
        "training_data.label_method",
        "hybrid.reference_solver_reuse",
        "model_family.pretrained_weights",
        "training_data.submitted_datasets",
        "objective.loss_expressions",
        "hybrid.composition_graphs",
        "inference.final_label_selection",
    ):
        assert statuses[name] is r.Status.EXCLUDED, name
    # Every research-only battery entry says why.
    for c in r.contract(BATTERY).capabilities:
        if c.status is r.Status.RESEARCH_ONLY:
            assert len(c.summary) > 20, c.capability_id


def test_a_realized_id_is_not_also_registered():
    item = r.contract(BATTERY)
    lion = r.Capability(
        "optimizer.lion",
        r.Dimension.OPTIMIZER,
        "Lion",
        r.Status.RESEARCH_ONLY,
        r.Blocker.ENGINEERING,
    )
    with pytest.raises(ValueError):
        replace(item, capabilities=item.capabilities + (lion,))
    with pytest.raises(ValueError):  # only a rebuildable entry realizes
        r.Capability(
            "optimizer.example",
            r.Dimension.OPTIMIZER,
            "x",
            r.Status.RESEARCH_ONLY,
            r.Blocker.ENGINEERING,
            realizes=("optimizer.lion",),
        )


def test_check_design_answers_a_realized_capability():
    design = {"strategy": strategy(BATTERY, "mlp"), "capabilities": ["optimizer.lion"]}
    result = check_design(design)
    assert result["requested"][0]["verdict"] == "supported"
    assert result["requested"][0]["realized_by"] == "optimizer.optimizer_family"
    burgers = check_design(
        {"strategy": strategy(BURGERS, "fno"), "capabilities": ["optimizer.lion"]}
    )
    assert burgers["requested"][0]["verdict"] == "not_yet_rebuildable"


@pytest.mark.parametrize(
    "parameters,path",
    [
        ({"optimizer_family": "adafactor", "beta1": 0.8}, "beta1"),
        ({"optimizer_family": "lion", "adam_epsilon": 1e-6}, "adam_epsilon"),
        (
            {"learning_rate_curve": "constant", "min_learning_rate_ratio": 0.1},
            "min_learning_rate_ratio",
        ),
        ({"learning_rate_curve": "one_cycle", "warmup_steps": 10}, "warmup_steps"),
        (
            {"optimizer_family": "free_adamw", "learning_rate_curve": "constant"},
            "learning_rate_curve",
        ),
        (
            {"optimizer_family": "sam", "learning_rate_curve": "train_loss_plateau"},
            "learning_rate_curve",
        ),
        ({"weight_decay_mask": "matrices"}, "weight_decay_mask"),
        ({"ema_decay": 0.9}, "ema_decay"),
        ({"inference_weights": "ema", "tail_averaging": 0.5}, "tail_averaging"),
        ({"optimizer_family": "sam", "tail_averaging": 0.5}, "tail_averaging"),
        ({"steps": 100, "warmup_steps": 100}, "warmup_steps"),
        ({"steps": 100, "polish_steps": 90}, "polish_steps"),
        ({"train_fraction": 0.5, "batch_size": 300}, "batch_size"),
        ({"batch_size": 30, "microbatches": 4}, "microbatches"),
    ],
)
def test_an_ignored_or_inconsistent_field_is_refused_by_name(parameters, path):
    with pytest.raises(RecipeRejected) as rejected:
        compile_recipe(strategy(BATTERY, "mlp", **parameters))
    assert ("/parameters/" + path) in {i.path for i in rejected.value.rejected.issues}


# --- Refused by name, in both directions. ---


def test_a_burgers_family_under_battery_is_refused_by_name_and_the_reverse():
    assert refusals(strategy(BATTERY, "fno")) == {
        ("backbone.not_rebuildable", "/backbone")
    }
    assert refusals(strategy(BATTERY, "transolver")) == {
        ("backbone.not_rebuildable", "/backbone")
    }
    assert refusals(strategy(BURGERS, "mlp")) == {
        ("backbone.not_in_contract", "/backbone")
    }
    assert refusals(strategy(BURGERS, "knn")) == {
        ("backbone.not_in_contract", "/backbone")
    }
    # A field one Challenge owns is unknown to the other.
    # n_modes is registered for battery, as not applicable (research-only).
    assert refusals(strategy(BATTERY, "mlp", n_modes=8)) == {
        ("parameter.not_rebuildable", "/parameters/n_modes")
    }
    assert refusals(strategy(BURGERS, "fno", ensemble_members=2)) == {
        ("parameter.unknown", "/parameters/ensemble_members")
    }
    # Specimens: each is accepted under its own Challenge.
    assert validate_for_challenge(strategy(BATTERY, "mlp", ensemble_members=2)).ok
    assert validate_for_challenge(strategy(BURGERS, "fno", n_modes=8)).ok


def test_unknown_and_unrebuildable_items_are_refused_by_name():
    assert refusals(strategy("battery-charge-degradation")) == {
        ("challenge.unknown", "/challenge_id")
    }
    assert refusals(strategy(BATTERY, "uno")) == {
        ("backbone.not_in_contract", "/backbone")
    }
    # Lion is a value of optimizer_family for battery, not a field of its own.
    assert refusals(strategy(BATTERY, "mlp", remat=True, lion=True, bogus=1)) == {
        ("parameter.not_rebuildable", "/parameters/remat"),
        ("parameter.unknown", "/parameters/lion"),
        ("parameter.unknown", "/parameters/bogus"),
    }
    assert refusals(strategy(BATTERY, "knn", width=16)) == {
        ("parameter.not_applicable", "/parameters/width")
    }
    assert refusals(strategy(BATTERY, "mlp", neighbours=3)) == {
        ("parameter.not_applicable", "/parameters/neighbours")
    }
    # Burgers' legacy structural names are refused by its contract too.
    assert refusals(strategy(BURGERS, "uno")) == {
        ("backbone.not_in_contract", "/backbone")
    }


@pytest.mark.parametrize(
    "key", ["code", "model_weights", "checkpoint", "training_dataset", "seed"]
)
def test_submissions_stay_declarative(key):
    found = refusals(strategy(BATTERY, "mlp", **{key: "x"}))
    assert ("capability.forbidden", "/parameters/" + key) in found
    with pytest.raises(SubmissionRefused):
        compile_submission(strategy(BATTERY, "mlp", **{key: "x"}))


def test_the_contract_digest_is_checked_by_name():
    value = strategy(BATTERY, "knn", neighbours=3)
    good = compile_submission(value, contract_digest=r.contract_digest(BATTERY))
    assert good.contract_digest == r.contract_digest(BATTERY)
    for wrong in (r.contract_digest(BURGERS), "sha256:" + "0" * 64):
        with pytest.raises(SubmissionRefused) as refused:
            compile_submission(value, contract_digest=wrong)
        assert [(i.code, i.path) for i in refused.value.issues] == [
            ("contract.digest_mismatch", "/contract_digest")
        ]
    with pytest.raises(SubmissionRefused):
        check_contract_digest("nope", r.contract_digest(BATTERY))


def test_backend_rules_are_named():
    with pytest.raises(RecipeRejected) as rejected:
        compile_recipe(strategy(steps=100, ensemble_members=3))
    assert [(i.code, i.path) for i in rejected.value.rejected.issues] == [
        ("parameter.dependency_unsatisfied", "/parameters/ensemble_members")
    ]
    with pytest.raises(RecipeRejected) as rejected:
        compile_recipe(strategy(steps=32, ensemble_members=4))
    assert rejected.value.rejected.issues[0].path == "/parameters/steps"
    with pytest.raises(RecipeRejected):  # B-02B range, by the same compiler
        compile_recipe(strategy(width=4096))


def test_a_recipe_exists_only_as_compiler_output():
    _, recipe = compile_recipe(strategy(width=64))
    assert recipe.settings["width"] == 64
    assert recipe.supplied == {"width"}
    with pytest.raises(TypeError):
        BatteryRecipe(
            recipe.family,
            recipe.values,
            recipe.supplied,
            recipe.strategy_hash,
            recipe.plan_digest,
        )
    with pytest.raises(TypeError):
        rebuild(dict(recipe.values), None, 0)


def test_check_design_answers_per_challenge():
    result = check_design({"strategy": strategy(BATTERY, "mlp", width=64)})
    assert result["verdict"] == "submittable"
    assert result["contract"] == {
        "challenge": BATTERY,
        "digest": r.contract_digest(BATTERY),
    }
    assert result["rebuild"]["canonical"]["width"] == {
        "value": 64,
        "source": "selected",
    }
    assert result["rebuild"]["canonical"]["depth"]["source"] == "defaulted"
    wrong = check_design({"strategy": strategy(BATTERY, "fno")})
    assert wrong["verdict"] == "not_yet_rebuildable"
    assert "rebuild" not in wrong
    unknown = check_design({"strategy": strategy("battery", "mlp")})
    assert unknown["verdict"] == "refused"
    assert unknown["challenge"]["reason"] == "unrecognized"
    assert set(unknown["challenge"]["nearest"]) <= set(r.CONTRACTS)


# --- Rebuild behaviour (JAX, small bounded fits). ---

jax = pytest.importorskip("jax")

SMALL = {
    "mlp": {"width": 16, "depth": 1, "steps": 32},
    "deeponet": {"width": 16, "deeponet_depth": 1, "basis_functions": 4, "steps": 32},
    "knn": {},
}


@pytest.fixture(scope="module")
def material():
    return ch.PublicMaterial.load()


@pytest.fixture(scope="module")
def train(material):
    return material.train.subset(48)


_FITS = {}


def fit(material, train, family="mlp", seed=0, cached=True, **parameters):
    """Rebuild and predict. Fits are cached by the resolved recipe, so a
    baseline shared by many controls trains once (compilation dominates)."""
    _, recipe = compile_recipe(
        strategy(BATTERY, family, **{**SMALL[family], **parameters})
    )
    key = (recipe.family, seed, recipe.values)
    if cached and key in _FITS:
        return _FITS[key]
    model, stats = rebuild(recipe, material, seed, train=train)
    result = stats, model.predict(material.train.x[200:208])
    if cached:
        _FITS[key] = result
    return result


def differs(a, b):
    (sa, pa), (sb, pb) = a, b
    return sa["params_sha256"] != sb["params_sha256"] or any(
        not np.array_equal(pa[k], pb[k]) for k in pa
    )


#: (surface, family, value a, value b, other fields): one full rebuild per
#: surface. Every value of every choice surface is covered as well, here or by
#: the fast transform and network tests below.
CONTROLS = [
    ("neighbours", "knn", 3, 7, {}),
    ("train_fraction", "knn", 1.0, 0.5, {}),
    ("width", "mlp", 16, 24, {}),
    ("depth", "mlp", 1, 2, {}),
    ("deeponet_depth", "deeponet", 1, 2, {}),
    ("basis_functions", "deeponet", 4, 8, {}),
    ("trajectory_components", "mlp", 0, 4, {}),
    ("arrhenius_features", "mlp", False, True, {}),
    ("bounded_voltage_head", "mlp", True, False, {}),
    ("ocv_initial_voltage", "mlp", True, False, {}),
    ("capacity_fade_head", "mlp", True, False, {}),
    ("steps", "mlp", 32, 48, {}),
    ("batch_size", "mlp", 400, 16, {}),
    ("microbatches", "mlp", 1, 2, {"batch_size": 16}),
    ("optimizer_family", "mlp", "adam", "lion", {}),
    ("learning_rate", "mlp", 0.002, 0.01, {}),
    ("weight_decay", "mlp", 0.0, 0.05, {}),
    ("weight_decay_mask", "mlp", "all", "matrices", {"weight_decay": 0.05}),
    ("clip_norm", "mlp", 0.0, 0.01, {}),
    ("beta1", "mlp", 0.9, 0.5, {}),
    ("beta2", "mlp", 0.999, 0.9, {}),
    ("adam_epsilon", "mlp", 1e-8, 1e-3, {}),
    ("learning_rate_curve", "mlp", "cosine", "constant", {}),
    ("warmup_steps", "mlp", 0, 8, {}),
    ("min_learning_rate_ratio", "mlp", 0.0, 0.5, {}),
    ("relative_loss", "mlp", False, True, {}),
    ("time_weighting", "mlp", "uniform", "early", {}),
    ("time_weighting", "mlp", "uniform", "late", {}),
    ("h1_weight", "mlp", 0.0, 1.0, {}),
    ("h2_weight", "mlp", 0.0, 1.0, {}),
    ("spectral_weight", "mlp", 0.0, 1.0, {}),
    ("polish_steps", "mlp", 0, 4, {}),
    ("ensemble_members", "mlp", 1, 2, {}),
    ("tail_averaging", "mlp", 0.0, 0.5, {}),
    ("inference_weights", "mlp", "params", "ema", {}),
    ("ema_decay", "mlp", 0.99, 0.5, {"inference_weights": "ema"}),
    ("precision", "mlp", "float32", "float64", {}),
    ("train_fraction", "mlp", 1.0, 0.5, {}),
    ("important_region_weight", "mlp", 1.0, 0.1, {}),
    ("curriculum", "mlp", "none", "low_rate_first", {}),
    ("curriculum", "mlp", "none", "high_rate_first", {}),
    ("hard_example_weight", "mlp", 0.0, 1.0, {}),
    ("activation", "mlp", "gelu", "tanh", {}),
    ("normalization", "mlp", "none", "layer_norm", {}),
    ("initialization", "mlp", "he_normal", "glorot_normal", {}),
]
#: Choice values checked without a model fit, by the tests below.
UNIT_CHOICES = {
    "optimizer_family",
    "learning_rate_curve",
    "activation",
    "initialization",
}


def test_the_controls_cover_every_battery_surface_and_choice():
    surfaces = r.catalog_surfaces(BATTERY)
    assert {c[0] for c in CONTROLS} == set(surfaces)
    for name, (_, kind, choices, _, default, _) in surfaces.items():
        if kind == "choice" and name not in UNIT_CHOICES:
            tested = {c[3] for c in CONTROLS if c[0] == name} | {default}
            assert tested == set(choices), name


def _settings(**overrides):
    defaults = {n: v[4] for n, v in r.catalog_surfaces(BATTERY).items()}
    return {**defaults, "learning_rate": 0.01, **overrides}


def _run_transform(tx, value_fn=None, updates=4):
    """A few updates of a fixed, non-uniform toy problem (no model fit)."""
    import jax.numpy as jnp
    import optax

    rng = np.random.default_rng(3)
    params = {
        "w": jnp.asarray(rng.normal(size=(3, 2)), jnp.float32),
        "b": jnp.asarray(rng.normal(size=(2,)), jnp.float32),
    }
    state = tx.init(params)
    for i in range(updates):
        grads = {
            "w": jnp.asarray(rng.normal(size=(3, 2)) * (i + 1), jnp.float32),
            "b": jnp.asarray(rng.normal(size=(2,)), jnp.float32),
        }
        extra = {} if value_fn is None else {"value": value_fn(i)}
        step, state = tx.update(grads, state, params, **extra)
        params = optax.apply_updates(params, step)
    return np.concatenate([np.asarray(params["w"]).ravel(), np.asarray(params["b"])])


def test_every_optimizer_is_its_own_transform():
    import jax
    import optax

    from carbon.battery.training import optimizer

    choices = r.catalog_surfaces(BATTERY)["optimizer_family"][2]
    results = {
        name: _run_transform(
            optimizer(jax, optax, _settings(optimizer_family=name), 20)
        )
        for name in choices
    }
    assert len(results) == 11
    for name, value in results.items():
        assert np.isfinite(value).all(), name
    distinct = {tuple(np.round(v, 12)) for v in results.values()}
    assert len(distinct) == len(results)


def test_every_learning_rate_curve_is_its_own_schedule():
    import jax
    import optax

    from carbon.battery.training import curve, optimizer

    choices = r.catalog_surfaces(BATTERY)["learning_rate_curve"][2]
    steps = np.arange(100)
    curves = {
        name: tuple(
            np.round(
                [
                    float(curve(optax, _settings(learning_rate_curve=name), 100)(i))
                    for i in steps
                ],
                12,
            )
        )
        for name in choices
    }
    # The plateau curve is the constant rate until TRAIN loss stalls; its
    # difference is in the transform, driven by the loss value.
    assert curves["train_loss_plateau"] == curves["constant"]
    assert len(set(curves.values())) == len(choices) - 1
    stalled = lambda i: 1.0
    constant = _run_transform(
        optimizer(jax, optax, _settings(learning_rate_curve="constant"), 20),
        updates=30,
    )
    plateau = _run_transform(
        optimizer(jax, optax, _settings(learning_rate_curve="train_loss_plateau"), 20),
        stalled,
        updates=30,
    )
    assert not np.array_equal(constant, plateau)


def test_every_activation_and_initialization_builds_a_different_network():
    import jax
    import jax.numpy as jnp

    from carbon.battery.training import apply_stack, dense_stack

    x = jnp.linspace(-1.0, 1.0, 12).reshape(3, 4)
    outputs = {}
    for act in r.catalog_surfaces(BATTERY)["activation"][2]:
        for init in r.catalog_surfaces(BATTERY)["initialization"][2]:
            _, params = dense_stack(
                jax, jax.random.PRNGKey(0), [4, 8, 2], init, jnp.float32
            )
            outputs[(act, init)] = tuple(
                np.round(
                    np.asarray(apply_stack(jax, params, x, act, "none")).ravel(), 7
                )
            )
    assert len(set(outputs.values())) == len(outputs) == 15


@pytest.mark.parametrize(
    "surface,family,a,b,extra",
    CONTROLS,
    ids=[f"{c[0]}-{c[1]}-{c[3]}" for c in CONTROLS],
)
def test_every_surface_changes_what_carbon_rebuilds(
    material, train, surface, family, a, b, extra
):
    first = fit(material, train, family, **extra, **{surface: a})
    second = fit(material, train, family, **extra, **{surface: b})
    assert differs(first, second)
    assert all(np.isfinite(v).all() for v in second[1].values())


def test_the_same_seed_gives_the_same_weights(material, train):
    # The campaign's written-out loop (mlp) and the general optax loop
    # (deeponet, minibatched Lion).
    for family, extra in (
        ("mlp", {}),
        ("deeponet", {"optimizer_family": "lion", "batch_size": 16}),
    ):
        first = fit(material, train, family, seed=5, cached=False, **extra)
        again = fit(material, train, family, seed=5, cached=False, **extra)
        assert not differs(first, again)
        assert differs(first, fit(material, train, family, seed=6, **extra))


def test_declared_initial_values_hold(material, train):
    x = material.train.x[200:208]
    ocv = np.interp(x[:, 3], material.ocv_soc, material.ocv_v)
    for family in ("mlp", "deeponet"):
        _, predictions = fit(material, train, family)
        assert np.array_equal(predictions["t"][:, 0], x[:, 2])
        assert np.array_equal(predictions["v"][:, 0], ocv)
        assert predictions["v"].shape == (8, ch.GRID_POINTS)
        assert predictions["q"].shape == (8, len(ch.CAPACITY_CYCLES))
        # The bounded head can never exceed the cycler limit; nothing is clamped.
        assert (predictions["v"] <= ch.V_MAX).all()


def test_the_important_region_is_the_published_one(material):
    import gzip
    import json

    from scripts.dev.exam_design import scoring

    body = gzip.decompress(Path(ch.TRAIN_V1_PATH).read_bytes())
    records = [json.loads(line) for line in body.splitlines() if line.strip()]
    assert (ch.PLATING_BAND_V, ch.T_IMPORTANT_C) == (
        scoring.PLATING_BAND_V,
        scoring.T_IMPORTANT_C,
    )
    expected = [scoring.is_important(rec) for rec in records]
    assert list(material.train.important) == expected
    assert 0 < sum(expected) < len(expected)


def test_promoted_recipes_match_the_campaign_recipes_bit_for_bit(material, train):
    """KEEP: Carbon's implementation is the campaign's math, not a rewrite."""
    from scripts.dev.exam_design import recipes as research

    data = research.Data(
        train.x,
        train.v,
        train.t,
        train.eta,
        train.q,
        train.important,
        list(train.case_ids),
    )
    structure = research.Structure(material.ocv_soc, material.ocv_v)
    x = material.train.x[200:208]
    cases = [
        (research.KNN(5), "knn", {"neighbours": 5}),
        (research.MLP("mlp", 16, 1, 32, 0.002), "mlp", {}),
        (
            research.MLP("mlp_plus", 16, 1, 32, 0.002, 1e-4, True, 4),
            "mlp",
            {
                "weight_decay": 1e-4,
                "arrhenius_features": True,
                "trajectory_components": 4,
            },
        ),
        (
            research.MLP("mlp_raw", 16, 1, 32, 0.002, bounded_v=False),
            "mlp",
            {"bounded_voltage_head": False},
        ),
        (
            research.MLP("mlp_localized", 16, 1, 32, 0.002, important_weight=0.1),
            "mlp",
            {"important_region_weight": 0.1},
        ),
        (
            research.MLP("mlp_half", 16, 1, 32, 0.002, train_fraction=0.5),
            "mlp",
            {"train_fraction": 0.5},
        ),
        (
            research.Ensemble(
                "mlp_ens3", {"width": 16, "depth": 1, "steps": 48, "lr": 0.002}, 3
            ),
            "mlp",
            {"steps": 48, "ensemble_members": 3},
        ),
    ]
    for model, family, parameters in cases:
        stats = model.fit(data, structure, seed=2)
        ours, predictions = fit(material, train, family, seed=2, **parameters)
        assert ours["params_sha256"] == stats["params_sha256"], model.name
        theirs = model.predict(x)
        assert all(np.array_equal(theirs[k], predictions[k]) for k in theirs)


def test_challenge_constants_restate_the_pinned_reference():
    from scripts.dev.exam_design.battery_reference import SPEC, time_grid

    assert {k: tuple(v) for k, v in SPEC["input_bounds"].items()} == ch.INPUT_BOUNDS
    assert (SPEC["v_min"], SPEC["v_max"]) == (ch.V_MIN, ch.V_MAX)
    assert len(time_grid()) == ch.GRID_POINTS


def test_public_material_is_refused_unless_it_is_the_pinned_bytes(tmp_path):
    material = ch.PublicMaterial.load()
    assert len(material.train.case_ids) == ch.TRAIN_V1_CASES
    (tmp_path / ch.OCV_TABLE_PATH).parent.mkdir(parents=True)
    (tmp_path / ch.OCV_TABLE_PATH).write_text("{}")
    with pytest.raises(ch.MaterialMismatch):
        ch.PublicMaterial.load(tmp_path)
