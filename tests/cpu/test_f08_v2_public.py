"""RB 2.0's build module (`carbon.challenge_kit.f08_v2_public`).

Claims:
1. Everything that names the TRAIN refuses while `f08_v2_train` has an open ruling (as on main today): nothing is filled.
2. With a ruled SYNTHETIC TRAIN, the interface, limits, kit, trusted material and roles follow `f08_v2_train` alone, agree
   with each other, and carry 2.0's inputs and outputs, never 1.x's.
3. It serves only RB 2.0, and what 2.0 has no registered material for (a development bank, the limit and objective
   roles) is refused or absent, never 1.x's.
4. It offers every function of the build contract.

Every row and every "ruling" here is a synthetic fixture, never a value of record.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_f08_v2_train import _source

from carbon.challenge_kit import (
    f08_train,
    f08_v2_public,
    served_versions,
    version_registry,
)
from carbon.challenge_kit import f08_v2_train as rb
from carbon.development_session.profile import canonical, digest

KEY = (rb.CHALLENGE_ID, rb.CHALLENGE_VERSION)
#: The build contract (`exam_build.FUNCTIONS`, restated so this module's test does not need that one).
FUNCTIONS = (
    "construction_kit",
    "interface_document",
    "construction_limits_document",
    "trusted_material",
    "load_public_train",
    "development_bank",
    "physics_contract",
    "public_roles",
)
NEEDS_THE_TRAIN = tuple(
    name for name in FUNCTIONS if name not in ("development_bank", "physics_contract")
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def ruled(tmp_path, monkeypatch):
    """RB 2.0 with a synthetic TRAIN, synthetic rulings and a registry entry of its own."""
    monkeypatch.setattr(rb, "RULINGS", dict.fromkeys(rb.RULINGS, "synthetic fixture"))
    monkeypatch.setattr(
        rb,
        "OUTPUT_UNITS",
        {name: unit or "synthetic_unit" for name, unit in rb.OUTPUT_UNITS.items()},
    )
    source = _source()
    train, provenance = rb.derive_public_train(source)
    provenance_raw = rb.provenance_bytes(provenance)
    for suffix, raw, pin in (
        ("source.jsonl", source, "SOURCE_SHA256"),
        ("npz", train, "TRAIN_SHA256"),
        ("provenance.json", provenance_raw, "PROVENANCE_SHA256"),
    ):
        (tmp_path / f"{rb.TRAIN_NAME}.{suffix}").write_bytes(raw)
        monkeypatch.setattr(rb, pin, _sha(raw))
    monkeypatch.setattr(rb, "_DATA", tmp_path)
    monkeypatch.setitem(
        version_registry.VERSIONS,
        KEY,
        version_registry.Version(
            challenge_id=KEY[0],
            version=KEY[1],
            train=rb.TRAIN_NAME,
            allowlist="v8",
            step_caps=False,
            pack_version="synthetic-pack-1",
            development_evaluation=None,
            sealed_evaluation=None,
            campaign=None,
            rebuild_wall_seconds=version_registry.REBUILD_LIMIT_SECONDS,
        ),
    )
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    monkeypatch.setattr(served_versions, "step_caps", lambda *_: False)
    monkeypatch.setattr(served_versions, "serves_catalog", lambda *_: False)
    return train


def test_it_offers_every_function_of_the_build_contract_and_a_scope():
    assert all(callable(getattr(f08_v2_public, name)) for name in FUNCTIONS)
    assert type(f08_v2_public.SCOPE) is str


@pytest.mark.parametrize("name", NEEDS_THE_TRAIN)
def test_an_unruled_train_refuses_everything_that_names_it(name, monkeypatch):
    monkeypatch.setattr(rb, "RULINGS", {**rb.RULINGS, "mesh_statement": None})
    with pytest.raises(ValueError, match="HUMAN_INPUT"):
        getattr(f08_v2_public, name)(*KEY)


@pytest.mark.parametrize("name", FUNCTIONS)
@pytest.mark.parametrize(
    "key",
    [(KEY[0], "1.7"), (KEY[0], "2.1"), ("electric-motor-magnetics", KEY[1])],
)
def test_it_serves_only_rb_2_0(name, key, ruled):
    with pytest.raises(ValueError, match="unknown public RB 2.0 Challenge identity"):
        getattr(f08_v2_public, name)(*key)


def test_the_interface_is_the_train_module_s_never_1x(ruled):
    document = f08_v2_public.interface_document(*KEY)
    assert document["input"]["names"] == list(rb.INPUT_NAMES)
    assert document["input"]["units"] == list(rb.INPUT_UNITS)
    assert document["input"]["shape"] == [len(rb.INPUT_NAMES)]
    assert document["output"]["names"] == list(rb.GRADED_OUTPUTS)
    assert document["output"]["units"] == [
        rb.OUTPUT_UNITS[name] for name in rb.GRADED_OUTPUTS
    ]
    assert document["output"]["shape"] == [len(rb.GRADED_OUTPUTS)]
    slices = document["output"]["named_slices"]
    assert list(slices) == list(rb.GRADED_OUTPUTS)
    assert list(slices.values()) == [[i, i + 1] for i in range(len(rb.GRADED_OUTPUTS))]
    assert document["train_dtype"] == rb.interface_document()["dtype"]
    assert not set(rb.EXACT_OUTPUTS) & set(document["output"]["names"])
    assert document["input"]["names"] != list(f08_train.FIELDS)


def test_the_limits_bind_the_train_and_the_version_s_own_wall(ruled):
    document = f08_v2_public.construction_limits_document(*KEY)
    assert document["train_cases"] == rb.ROWS
    assert document["train_provenance_sha256"] == "sha256:" + rb.PROVENANCE_SHA256
    assert document["train_mesh"] == rb.RULINGS["mesh_statement"]
    policy = document["reconstruction_resource_policy"]
    wall = version_registry.REBUILD_LIMIT_SECONDS
    assert policy["build_wall_seconds_max"] == wall
    assert policy["inference_wall_seconds_max"] == wall
    assert policy["total_reconstruction_wall_seconds_max"] == (
        version_registry.task_wall_seconds(wall)
    )
    assert document["training_step_cap"] is None
    assert document["training_limit"] == "build_wall_seconds_max"
    assert "backbone_catalog" not in document
    assert "graph_training_adapter" not in document
    assert document["live_eligible"] is False


def test_the_kit_the_trusted_material_and_the_roles_agree(ruled):
    kit = f08_v2_public.construction_kit(*KEY)
    interface = f08_v2_public.interface_document(*KEY)
    limits = f08_v2_public.construction_limits_document(*KEY)
    assert kit == {
        "id": KEY[0],
        "version": KEY[1],
        "train_digest": "sha256:" + _sha(ruled),
        "interface_digest": digest(canonical(interface)),
        "construction_limits_digest": digest(canonical(limits)),
    }
    trusted = f08_v2_public.trusted_material(*KEY)
    assert trusted["limits_document"] == limits
    assert trusted["limits_schema"] == limits["schema"]
    assert trusted["scope"] == limits["scope"] == f08_v2_public.SCOPE
    assert trusted["resource_schema"] == (
        limits["reconstruction_resource_policy"]["schema"]
    )
    assert f08_v2_public.public_roles(*KEY) == {
        "construction_kit": canonical(kit),
        "interface": canonical(interface),
        "train": ruled,
    }


def test_what_2_0_has_no_material_for_is_refused_or_absent_never_1x(ruled):
    with pytest.raises(ValueError, match="no public RB 2.0 development bank"):
        f08_v2_public.development_bank(*KEY)
    assert f08_v2_public.physics_contract(*KEY) is None
    assert not {"important_limit_definition", "design_objective"} & set(
        f08_v2_public.public_roles(*KEY)
    )
