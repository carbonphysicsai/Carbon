"""The catalog settings Schemas for the trainer v2 (`carbon-candidate-torch-v2`, `carbon-candidate-jax-v2`): the limits the v1
Schemas had are gone, the keep-list refusals stay, and v1 is unchanged."""

from __future__ import annotations

import pytest

from carbon.backbone_catalog import settings
from carbon.backbone_catalog.entries import CatalogRefused

MOTOR = {"id": "electric-motor-magnetics", "version": "1.3"}
N = 60


def item(schema, backbone="thuml.FNO", challenge=MOTOR):
    return {
        "catalog_id": backbone,
        "backbone": backbone,
        "settings_schema": schema.schema_id,
        "challenges": [challenge],
        "defaults": {
            "configuration": {"backbone": backbone, "learning_rate": 0.001},
            "train_use": {},
        },
    }


TORCH = item(settings.TORCH_V2)
JAX = item(settings.JAX_V2, "jno.fno1d")
V1 = item(settings.LEVERS, "neuralop.FNO")


def ok(entry, train_use=None, configuration=None):
    return settings.resolve(entry, configuration or {}, train_use or {})


def refused(entry, train_use=None, configuration=None, code=None):
    with pytest.raises(CatalogRefused) as caught:
        ok(entry, train_use, configuration)
    if code:
        assert caught.value.code == code
    return caught.value


def test_the_v2_schemas_pin_the_two_trainer_builds_and_are_registered():
    assert settings.SCHEMAS["carbon-candidate-torch-v2"] is settings.TORCH_V2
    assert settings.SCHEMAS["carbon-candidate-jax-v2"] is settings.JAX_V2
    assert (
        settings.schema_for_build(settings.TORCH_V2.build_sha256)
        == "carbon-candidate-torch-v2"
    )
    assert (
        settings.schema_for_build(settings.JAX_V2.build_sha256)
        == "carbon-candidate-jax-v2"
    )
    assert settings.TORCH_V2.seed_limit == 2**64 and settings.JAX_V2.seed_limit == 2**32
    builds = [schema.build_sha256 for schema in settings.SCHEMAS.values()]
    assert len(builds) == len(set(builds))


def test_the_v2_build_digests_are_the_trainer_files():
    import hashlib
    from pathlib import Path

    src = Path(settings.__file__).resolve().parent / "build_v2_src"
    for schema, name in (
        (settings.TORCH_V2, "build.py"),
        (settings.JAX_V2, "build_jax.py"),
    ):
        assert (
            schema.build_sha256
            == "sha256:" + hashlib.sha256((src / name).read_bytes()).hexdigest()
        )


# L1: per-output loss weights
def test_output_weights_one_per_output_and_not_all_zero():
    ok(TORCH, {"loss": {"output_weights": [1.0] * N}})
    ok(TORCH, {"loss": {"kind": "log_cosh", "output_weights": [0] * (N - 1) + [3]}})
    for bad in (
        [1.0] * (N - 1),
        [-1.0] + [1.0] * (N - 1),
        [0.0] * N,
        [float("nan")] + [1.0] * (N - 1),
        "x",
        [],
    ):
        refused(
            TORCH, {"loss": {"output_weights": bad}}, code="catalog_setting_invalid"
        )
    refused(V1, {"loss": {"output_weights": [1.0] * N}}, code="catalog_setting_unknown")


# L2/L3/L13: ensembles
def test_ensemble_members_may_take_output_subsets_that_cover_every_output():
    halves = [{"outputs": list(range(30))}, {"outputs": list(range(30, N))}]
    ok(TORCH, {"ensemble": {"members": halves, "combine": "best_per_output"}})
    ok(TORCH, {"ensemble": {"members": [{}, {"outputs": [0]}]}})
    refused(
        TORCH,
        {"ensemble": {"members": [{"outputs": [0, 1]}]}},
        code="catalog_settings_inconsistent",
    )
    refused(
        TORCH,
        {"ensemble": {"members": [{"outputs": [N]}]}},
        code="catalog_setting_invalid",
    )
    refused(
        TORCH,
        {"ensemble": {"members": [{"outputs": []}]}},
        code="catalog_setting_invalid",
    )
    refused(
        TORCH, {"ensemble": {"members": [{"bogus": 1}]}}, code="catalog_setting_unknown"
    )


def test_ensemble_members_are_uncapped_and_every_combine_kind_is_open():
    ok(TORCH, {"ensemble": {"members": 64}})
    for kind in settings.COMBINES:
        spec = {"members": 2, "combine": kind}
        if kind == "weights":
            spec["weights"] = [0.5, [1.0] * N]
        ok(TORCH, {"ensemble": spec})
    refused(
        TORCH,
        {"ensemble": {"members": 2, "combine": "magic"}},
        code="catalog_setting_invalid",
    )
    refused(
        TORCH,
        {"ensemble": {"members": 2, "combine": "weights"}},
        code="catalog_setting_invalid",
    )
    refused(
        TORCH,
        {"ensemble": {"members": 2, "combine": "weights", "weights": [1]}},
        code="catalog_setting_invalid",
    )
    refused(
        V1,
        {"ensemble": {"members": 2, "combine": "best_per_output"}},
        code="catalog_setting_invalid",
    )
    refused(
        V1,
        {"ensemble": {"members": [{"outputs": [0]}]}},
        code="catalog_setting_invalid",
    )


# L4/L5: choice lists
def test_the_added_choices_are_open_in_v2_and_closed_in_v1():
    for use in (
        {"optimizer": {"name": "adagrad"}},
        {"optimizer": {"name": "nadam"}},
        {"optimizer": {"name": "radam"}},
        {"schedule": {"name": "exponential", "gamma": 0.9}},
        {"schedule": {"name": "polynomial", "power": 2}},
        {"schedule": {"name": "cosine_restarts", "every": 10}},
        {"loss": {"kind": "log_cosh"}},
        {"precision": "float32"},
    ):
        ok(TORCH, use)
        ok(JAX, use)
        refused(V1, use)
    refused(TORCH, {"optimizer": {"name": "nope"}}, code="catalog_setting_invalid")
    refused(TORCH, {"precision": "float64"}, code="catalog_setting_invalid")


# L7: quantize bits
def test_quantize_bits_have_no_upper_bound_but_a_floor_of_two():
    ok(TORCH, {"quantize": {"bits": 24}})
    ok(TORCH, {"quantize": {"bits": 2}})
    for bad in (1, 0, 2.5, "8"):
        refused(TORCH, {"quantize": {"bits": bad}}, code="catalog_setting_invalid")
    refused(V1, {"quantize": {"bits": 24}}, code="catalog_setting_invalid")


# L8: seeds
def test_seed_candidates_follow_the_trainers_own_seed_range():
    ok(TORCH, {"seeds": {"candidates": [0, 2**63, 2**64 - 1]}})
    refused(TORCH, {"seeds": {"candidates": [2**64]}}, code="catalog_setting_invalid")
    refused(TORCH, {"seeds": {"candidates": [-1]}}, code="catalog_setting_invalid")
    ok(JAX, {"seeds": {"candidates": [2**32 - 1]}})
    refused(JAX, {"seeds": {"candidates": [2**32]}}, code="catalog_setting_invalid")
    refused(V1, {"seeds": {"candidates": [2**32]}}, code="catalog_setting_invalid")


# L6: arch keys
def test_library_entries_take_arch_keys_in_v2_only():
    ok(TORCH, configuration={"arch": {"n_hidden": 16, "n_layers": 2, "dropout": 0.1}})
    refused(TORCH, configuration={"arch": {"bogus": 1}}, code="catalog_setting_unknown")
    refused(
        TORCH, configuration={"arch": {"n_hidden": 0}}, code="catalog_setting_invalid"
    )
    refused(
        TORCH, configuration={"arch": {"dropout": 1.0}}, code="catalog_setting_invalid"
    )
    refused(item(settings.COVERAGE), configuration={"arch": {"n_hidden": 16}})
    ok(TORCH, {"search": {"candidates": [{"arch": {"n_hidden": 8}}]}})
    assert settings.document(TORCH)["arch"] == list(settings.LIBRARY_ARCH)
    assert settings.arch_keys("neuralop.FNO", "v2") == ("modes", "hidden", "layers")
    assert settings.arch_keys("jno.fno1d", "v2") == ()


def test_the_transolver_rule_is_kept_and_cited():
    entry = item(settings.TORCH_V2, "transolver")
    ok(entry, configuration={"arch": {"hidden": 32, "heads": 4}})
    refused(
        entry,
        configuration={"arch": {"hidden": 33, "heads": 4}},
        code="catalog_settings_inconsistent",
    )


def test_the_keep_list_still_refuses():
    refused(TORCH, {"steps": 0}, code="catalog_setting_invalid")
    refused(TORCH, {"bogus": 1}, code="catalog_setting_unknown")
    refused(TORCH, configuration={"learning_rate": 5}, code="catalog_setting_invalid")
    refused(
        TORCH,
        {"search": {"candidates": [{"backbone": "other"}]}},
        code="catalog_setting_invalid",
    )
    refused(
        TORCH,
        {"distill": {"teacher": {"backbone": "other"}}},
        code="catalog_setting_invalid",
    )


def test_hooked_library_entries_take_their_constructors_arguments():
    for backbone, keys in settings.HOOKED_ARCH.items():
        assert settings.arch_keys(backbone, "v2") == keys
    ok(
        item(settings.TORCH_V2, "neuralop.LocalNO"),
        configuration={"arch": {"modes": 3, "hidden": 8, "layers": 2}},
    )
    ok(
        item(settings.TORCH_V2, "physicsnemo.FullyConnected"),
        configuration={"arch": {"width": 16, "layers": 2}},
    )
    refused(
        item(settings.TORCH_V2, "physicsnemo.FullyConnected"),
        configuration={"arch": {"modes": 3}},
        code="catalog_setting_unknown",
    )


def test_the_output_count_is_the_interfaces_for_every_served_catalog_version():
    from carbon.challenge_kit import physical_material, served_versions

    versions = sorted(served_versions.CATALOG)
    assert versions
    for challenge_id, version in versions:
        shape = physical_material.bundle_material(challenge_id, version)[
            "expected_output_shape"
        ]
        assert settings.output_count(challenge_id, version) == shape[1], (
            challenge_id,
            version,
        )
    assert (
        settings.output_count("battery-fastcharge-ageing-development-v1", "2.2") == 247
    )
    assert settings.output_count("no-such-challenge", "1.0") is None
