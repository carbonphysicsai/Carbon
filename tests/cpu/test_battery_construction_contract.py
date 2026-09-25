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
    assert SESSION_BACKBONES == GPU_BACKBONES == ("fno", "deeponet")
    assert r.lane_families(BURGERS, "gpu_diagnostic") == GPU_BACKBONES
    # The default public projection is the historical Burgers one: no fields
    # were added to it.
    assert set(r.public_registry()) == {"schema", "status_meaning", "capabilities"}
    assert r.public_registry(BATTERY)["contract_digest"] == r.contract_digest(BATTERY)


def test_every_battery_consumer_derives_from_the_registry():
    from carbon.battery.contracts import battery_contracts

    contracts = battery_contracts()
    options = contracts.assembly.backbone_surface.options
    assert [o.selector_token for o in options] == ["knn", "mlp"]
    surfaces = {e.surface_id for e in contracts.catalog.entries}
    assert surfaces == {"strategy_backbone", *r.catalog_surfaces(BATTERY)}


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
    assert refusals(strategy(BATTERY, "mlp", n_modes=8)) == {
        ("parameter.unknown", "/parameters/n_modes")
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
    assert refusals(strategy(BATTERY, "mlp", lion=True, bogus=1)) == {
        ("parameter.not_rebuildable", "/parameters/lion"),
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

SMALL = {"width": 16, "depth": 1, "steps": 32}


@pytest.fixture(scope="module")
def material():
    return ch.PublicMaterial.load()


@pytest.fixture(scope="module")
def train(material):
    return material.train.subset(48)


def fit(material, train, family="mlp", seed=0, **parameters):
    base = dict(SMALL) if family == "mlp" else {}
    _, recipe = compile_recipe(strategy(BATTERY, family, **{**base, **parameters}))
    model, stats = rebuild(recipe, material, seed, train=train)
    predictions = model.predict(material.train.x[200:208])
    return stats, predictions


def differs(a, b):
    (sa, pa), (sb, pb) = a, b
    return sa["params_sha256"] != sb["params_sha256"] or any(
        not np.array_equal(pa[k], pb[k]) for k in pa
    )


#: Two values per surface; coverage must equal the battery surface set.
PAIRS = {
    "neighbours": ("knn", 3, 7),
    "width": ("mlp", 16, 24),
    "depth": ("mlp", 1, 2),
    "trajectory_components": ("mlp", 0, 4),
    "arrhenius_features": ("mlp", False, True),
    "steps": ("mlp", 32, 48),
    "learning_rate": ("mlp", 0.002, 0.01),
    "weight_decay": ("mlp", 0.0, 0.05),
    "ensemble_members": ("mlp", 1, 2),
    "bounded_voltage_head": ("mlp", True, False),
    "ocv_initial_voltage": ("mlp", True, False),
    "capacity_fade_head": ("mlp", True, False),
}


def test_the_controls_cover_every_battery_surface():
    assert set(PAIRS) == set(r.catalog_surfaces(BATTERY))


@pytest.mark.parametrize("surface", sorted(PAIRS))
def test_every_surface_changes_what_carbon_rebuilds(material, train, surface):
    family, a, b = PAIRS[surface]
    assert differs(
        fit(material, train, family, **{surface: a}),
        fit(material, train, family, **{surface: b}),
    )


def test_the_same_seed_gives_the_same_weights(material, train):
    first = fit(material, train, seed=5)
    assert not differs(first, fit(material, train, seed=5))
    assert differs(first, fit(material, train, seed=6))


def test_declared_initial_values_hold(material, train):
    _, predictions = fit(material, train)
    x = material.train.x[200:208]
    assert np.array_equal(predictions["t"][:, 0], x[:, 2])
    ocv = np.interp(x[:, 3], material.ocv_soc, material.ocv_v)
    assert np.array_equal(predictions["v"][:, 0], ocv)
    assert predictions["v"].shape == (8, ch.GRID_POINTS)
    assert predictions["q"].shape == (8, len(ch.CAPACITY_CYCLES))
    # The bounded head can never exceed the cycler limit; nothing is clamped.
    assert (predictions["v"] <= ch.V_MAX).all()


def test_promoted_recipes_match_the_campaign_recipes_bit_for_bit(material, train):
    """KEEP: Carbon's implementation is the campaign's math, not a rewrite."""
    from scripts.dev.exam_design import recipes as research

    data = research.Data(
        train.x, train.v, train.t, train.eta, train.q, np.zeros(48, bool), []
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
        assert ours["params_sha256"] == stats["params_sha256"], family
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
