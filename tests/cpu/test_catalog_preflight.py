"""A catalog recipe the door would refuse is refused before it is signed, with the fix named."""

from __future__ import annotations

import copy

import pytest

from carbon.challenge_registry.motor import catalog_recipe
from carbon.development_session import catalog_preflight
from carbon.development_session.catalog_preflight import (
    CatalogPreflightRefused,
    check,
)
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.direct_submission import (
    DirectIntakeRefusal,
    _preflight_catalog,
)


def _facts(recipe):
    return {"catalog_digest": recipe["source"]["catalog_digest"]}


def test_a_matching_recipe_passes_with_and_without_the_doors_digest():
    recipe = catalog_recipe("neuralop.TFNO")
    check(recipe)
    check(recipe, _facts(recipe))


def test_a_stale_digest_says_the_catalog_changed():
    recipe = catalog_recipe("neuralop.TFNO")
    stale = copy.deepcopy(recipe)
    stale["source"]["catalog_digest"] = "sha256:" + "0" * 64
    with pytest.raises(CatalogPreflightRefused) as refused:
        check(stale, _facts(recipe))
    assert refused.value.code == catalog_preflight.CATALOG_CHANGED
    assert "update the app" in refused.value.fix
    # The door moved on while this app and recipe agree: still caught.
    with pytest.raises(CatalogPreflightRefused) as moved:
        check(recipe, {"catalog_digest": "sha256:" + "1" * 64})
    assert moved.value.code == catalog_preflight.CATALOG_CHANGED


def test_an_unknown_id_names_the_ids_on_offer():
    recipe = catalog_recipe("neuralop.TFNO")
    recipe["source"]["catalog_id"] = "v2.no.such.entry"
    with pytest.raises(CatalogPreflightRefused) as refused:
        check(recipe, _facts(recipe))
    assert refused.value.code == "catalog_entry_unknown"
    assert "v2.no.such.entry" in refused.value.fix
    assert "choose one of" in refused.value.fix


def test_a_setting_the_entry_does_not_take_is_named():
    recipe = catalog_recipe("neuralop.TFNO")
    recipe["procedure"]["configuration"] = {"no_such_setting": 1}
    with pytest.raises(CatalogPreflightRefused) as refused:
        check(recipe, _facts(recipe))
    assert refused.value.code == "catalog_setting_unknown"
    assert "no_such_setting" in refused.value.fix
    assert "not accepted by entry 'neuralop.TFNO'" in refused.value.fix


def test_a_recipe_of_another_source_kind_is_left_alone():
    recipe = catalog_recipe("neuralop.TFNO")
    recipe["source"] = {"kind": "graph"}
    check(recipe, {"catalog_digest": "sha256:" + "2" * 64})


def test_the_submit_path_turns_it_into_a_direct_refusal_with_the_fix():
    recipe = catalog_recipe("neuralop.TFNO")
    recipe["source"]["catalog_id"] = "v2.no.such.entry"
    construction = ConstructionRecipe.from_dict(recipe)
    with pytest.raises(DirectIntakeRefusal) as refused:
        _preflight_catalog(construction, _facts(recipe))
    assert refused.value.code == "catalog_entry_unknown"
    assert "choose one of" in refused.value.fix
