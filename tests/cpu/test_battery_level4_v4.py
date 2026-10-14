"""Prospective field refusal, with the live v3 interpretation preserved."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.battery import level4, level4_v4
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

REPOSITORY = Path(__file__).resolve().parents[2]
BASE = "29fa548c45ad7fe7cf71d871c0c1bddc400497e8"
DIGEST = "sha256:" + "ab" * 32


def _variant():
    return dv.variant(BATTERY_CHALLENGE, 4, arm=level4_v4.ARM)


def _strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "mlp",
        "parameters": {"steps": 16, level4.FIELD: DIGEST, **parameters},
    }


@pytest.mark.parametrize(
    "parameters", [{"width": 64}, {"depth": 3}, {"width": 64, "depth": 3}]
)
def test_v4_refuses_every_present_dead_control_with_named_issues(parameters):
    with pytest.raises(dv.VariantRefused) as refused:
        dv.compile_development(_strategy(**parameters), _variant())
    names = [name for name in level4_v4.INERT_FIELDS if name in parameters]
    assert refused.value.code == "level4_field_inert:" + names[0]
    assert refused.value.issues == tuple(
        ("level4_field_inert:" + name, "/parameters/" + name) for name in names
    )


def test_omitted_fields_compile_v4_graph_and_preserve_catalog_defaults():
    compiled = dv.compile_development(_strategy(), _variant())
    assert compiled.variant_digest == _variant().digest
    assert compiled.reconstruction[level4.CAPABILITY]["submission"] == DIGEST
    assert compiled.reconstruction[level4.CAPABILITY]["loss_override"] == "graph"
    # Defaults are still the existing compiler's; no pinned recipe was edited.
    assert compiled.construction.settings["width"] == 256
    assert compiled.construction.settings["depth"] == 3


def test_non_graph_recipe_keeps_width_and_depth_on_v4():
    strategy = _strategy(width=16, depth=1)
    del strategy["parameters"][level4.FIELD]
    compiled = dv.compile_development(strategy, _variant())
    assert compiled.construction.settings["width"] == 16
    assert compiled.construction.settings["depth"] == 1
    assert not compiled.reconstruction


def test_default_v3_is_still_resolvable_and_accepts_historical_fields():
    prior = dv.variant(BATTERY_CHALLENGE, 4)
    assert prior.version == level4.VERSION == "battery-l4-graph-v3"
    assert (
        prior.digest
        == "sha256:ad15d6a8ef135a961f15dcb4a682e58ccdbdc7c99926de0f1ef6d5da4325cfa2"
    )
    assert dv.registered(prior.digest) == prior
    assert dv.registered(_variant().digest) == _variant()
    compiled = dv.compile_development(_strategy(width=64, depth=3), prior)
    assert compiled.construction.settings["width"] == 64
    assert compiled.construction.settings["depth"] == 3


def test_v4_policy_copies_every_v3_containment_bound_and_is_recorded():
    prior = dv.variant(BATTERY_CHALLENGE, 4)
    current = _variant()
    old_bounds = json.loads(prior.widened[0].bounds_json)
    new_bounds = json.loads(current.widened[0].bounds_json)
    assert new_bounds.pop("inert_recipe_fields") == ["width", "depth"]
    assert new_bounds == old_bounds
    assert current.document() == level4_v4.variant_document(
        base=current.document()["base_contract"]
    )
    assert dv.recorded_variant(current) is not None
    assert not dv.dev_problems()
    assert not dv.dev_unrecorded()


def test_v4_starter_drops_fields_without_changing_v3_starter():
    before = level4.level0_strategies()["scaffold_mlp"]
    starter = level4_v4.starter_recipe()
    assert not set(level4_v4.INERT_FIELDS) & starter["parameters"].keys()
    expected = json.loads(json.dumps(before))
    for name in level4_v4.INERT_FIELDS:
        del expected["parameters"][name]
    assert starter == expected
    assert level4.level0_strategies()["scaffold_mlp"] == before


def test_v4_remains_refused_at_miner_facing_contract():
    with pytest.raises(SubmissionRefused):
        compile_submission(_strategy(), contract_digest=_variant().digest)


def test_variant_leaf_import_does_not_initialize_numerical_runtime():
    code = (
        "import sys; from carbon.battery import level4_v4; "
        "assert not {'numpy','jax','torch'} & sys.modules.keys()"
    )
    subprocess.run([sys.executable, "-c", code], cwd=REPOSITORY, check=True)


@pytest.mark.parametrize(
    "relative",
    [
        "carbon/battery/level4.py",
        "carbon/battery/domain.py",
        "carbon/battery/recipes.py",
        "carbon/battery/training.py",
        "carbon/battery/torch_training.py",
        "carbon/battery/torch_families.py",
        "carbon/battery/implementation_versions.py",
        "carbon/reconstruction/development_variant_policies/battery-l4-graph-v3.json",
    ],
)
def test_historical_v3_and_pinned_implementation_bytes_stay_identical(relative):
    original = subprocess.run(
        ["git", "-C", str(REPOSITORY), "show", f"{BASE}:{relative}"],
        capture_output=True,
        check=True,
    ).stdout
    assert (REPOSITORY / relative).read_bytes() == original
