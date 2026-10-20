"""A catalog recipe on Motor 1.2 (OWNER-BACKBONE-CATALOG-01; Validator option C):
`source: {kind: catalog, catalog_id, catalog_digest}` binds the exact catalog
the version serves, and runs as the Carbon bundle it names."""

from __future__ import annotations

import copy

import pytest

from carbon.backbone_catalog import pipeline, served
from carbon.backbone_catalog.entries import CatalogRefused
from carbon.challenge_kit import physical_public
from carbon.challenge_kit.served_versions import serves_catalog
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    bind_recipe,
)

MOTOR = "electric-motor-magnetics"


def kit(version="1.2"):
    return physical_public.construction_kit(MOTOR, version)


def recipe(catalog_id="neuralop.FNO", configuration=None, train_use=None, **source):
    k = kit()
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": k,
        "source": {
            "kind": "catalog",
            "catalog_id": catalog_id,
            "catalog_digest": served.digest(MOTOR, "1.2"),
            **source,
        },
        "procedure": {
            "entrypoint": None,
            "configuration": configuration or {},
            "train_use": train_use or {},
            "initial_state": None,
        },
        "output": {
            "format": "carbon.numeric-graph.v1",
            "interface_digest": k["interface_digest"],
        },
    }


def test_only_motor_1_2_serves_the_catalog_and_its_limits_bind_it():
    assert serves_catalog(MOTOR, "1.2")
    assert not serves_catalog(MOTOR, "1.0") and not serves_catalog(MOTOR, "1.1")
    limits = physical_public.construction_limits_document(MOTOR, "1.2")
    assert limits["backbone_catalog"] == {
        "schema": served.SCHEMA,
        "digest": served.digest(MOTOR, "1.2"),
    }
    assert limits["training_step_cap"] is None
    for version in ("1.0", "1.1"):
        assert "backbone_catalog" not in physical_public.construction_limits_document(
            MOTOR, version
        )


def test_the_served_catalog_lists_the_manifest_entries_and_their_settings():
    document = served.document(MOTOR, "1.2")
    assert set(document["entries"]) == {
        e["catalog_id"] for e in pipeline.entries(MOTOR, "1.2")
    }
    fno = document["entries"]["neuralop.FNO"]
    assert fno["settings"]["defaults"]["configuration"]["learning_rate"] == 0.002
    assert fno["settings"]["fixed"] == {"backbone": "neuralop.FNO"}


def test_a_catalog_recipe_binds_and_expands_to_its_tested_bundle():
    bound = bind_recipe(
        recipe(train_use={"steps": 1200}),
        **{
            "challenge_id": MOTOR,
            "challenge_version": "1.2",
            **{k: v for k, v in kit().items() if k.endswith("_digest")},
        },
    )
    expanded = served.expand(bound.to_dict())
    item = pipeline.entry("neuralop.FNO")
    assert expanded["source"] == {"kind": "bundle", "bundle_ref": item["bundle_ref"]}
    assert expanded["procedure"]["entrypoint"] == item["entrypoint"]
    assert expanded["procedure"]["configuration"] == {
        **item["defaults"]["configuration"],
        "backbone": "neuralop.FNO",
    }
    assert expanded["procedure"]["train_use"] == {"steps": 1200}
    assert expanded["challenge"] == kit()
    ConstructionRecipe.from_dict(expanded)  # a valid bundle recipe


@pytest.mark.parametrize(
    "change, code",
    [
        (
            lambda r: r["source"].update(catalog_digest="sha256:" + "1" * 64),
            "catalog_entry_unknown",
        ),
        (
            lambda r: r["source"].update(catalog_id="neuralop.SFNO"),
            "catalog_entry_unknown",
        ),
        (
            lambda r: r["procedure"]["configuration"].update(backbone="transolver"),
            "catalog_setting_unknown",
        ),
        (
            lambda r: r["procedure"]["train_use"].update(steps=-1),
            "catalog_setting_invalid",
        ),
        (
            lambda r: r["output"].update(format="carbon.numeric-rows.v1"),
            "catalog_settings_inconsistent",
        ),
    ],
)
def test_a_bad_catalog_recipe_is_refused_by_its_code(change, code):
    value = recipe()
    change(value)
    with pytest.raises(CatalogRefused) as refused:
        served.expand(ConstructionRecipe.from_dict(value).to_dict())
    assert refused.value.code == code


@pytest.mark.parametrize(
    "change, code",
    [
        (
            lambda r: r["procedure"].update(entrypoint={"module": "x", "name": "y"}),
            "construction_recipe_procedure_invalid",
        ),
        (
            lambda r: r["source"].update(bundle_ref={}),
            "construction_recipe_source_invalid",
        ),
        (
            lambda r: r["source"].update(catalog_id="../x"),
            "construction_recipe_source_invalid",
        ),
        (
            lambda r: r["procedure"].update(initial_state={"weights": 1}),
            "construction_recipe_pretrained_state_forbidden",
        ),
    ],
)
def test_the_recipe_shape_is_checked_before_the_catalog(change, code):
    value = copy.deepcopy(recipe())
    change(value)
    with pytest.raises(RecipeRefused) as refused:
        ConstructionRecipe.from_dict(value)
    assert refused.value.code == code


def test_a_catalog_recipe_for_another_version_is_refused_by_the_binding():
    value = recipe()
    value["challenge"] = kit("1.1")
    with pytest.raises(CatalogRefused):
        served.expand(ConstructionRecipe.from_dict(value).to_dict())


def test_the_screen_passes_every_catalog_code_to_the_miner():
    from carbon.backbone_catalog.entries import REFUSAL_CODES
    from carbon.challenge_validator.dispatch import RECIPE_SCREEN_REFUSALS

    assert set(REFUSAL_CODES) <= set(RECIPE_SCREEN_REFUSALS)
