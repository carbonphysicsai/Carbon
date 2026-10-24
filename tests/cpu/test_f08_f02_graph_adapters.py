"""F08 1.4 / F02 2.3 graph training adapters (the Validator's rulings, 2026-10-20).

`codex-queue/reports/LAUNCHPAD_F08_F02_GRAPH_ADAPTER_SPEC_DRAFT_20261020.md`:
DEVELOPMENT surfaces copied from registered rows, a closed refusal when
`batch_size` exceeds the selected TRAIN rows, one generic pinned trainer whose
digest is in the construction identity, graphs on F08 1.4 / F02 2.3 only.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon import research
from carbon.backbone_catalog import served
from carbon.challenge_kit import (
    f02_public,
    f02_train,
    f08_public,
    f08_train,
    physical_material,
)
from carbon.challenge_kit import served_versions as sv
from carbon.development_session import (
    build_refusal,
    bundle_construction_worker,
    direct_graph_construction_worker,
)
from carbon.development_session import physical_graph_adapter as adapter
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module

ROOT = Path(__file__).resolve().parents[2]
F08, F02 = sv.F08, sv.F02
PUBLIC = {F08: f08_public, F02: f02_public}
TRAIN = {F08: f08_train, F02: f02_train}
SERVED = ((F08, "1.4"), (F02, "2.3"))
#: Construction limits digests of every earlier F08/F02 version, recorded
#: before this change: their bytes must never move.
EARLIER = {
    (F08, "1.0"): "88f56b8af03054a6002e92590784257df52580782b59c7a6bc019c17197725c3",
    (F08, "1.1"): "28a77a5beaf259a73acfa5b807fb5fd683353ee2c7de20ddb5ee155c94c7fb78",
    (F08, "1.2"): "039ec28de20975f0391707bf4cdf5153dacbed65f0bd247f07ab76321879c2ca",
    (F08, "1.3"): "58a1fceb1941bb249e6d32aa516de9e3890565830265e94c52b9e160e6b7dac7",
    (F02, "2.0"): "df88cb39b0213803cf7c6ad0a7cdc60f9ee55a3418f054d17776e433391dae99",
    (F02, "2.1"): "00f7675fa6600a4c172b8e037b415bea9bcdb5ce5d77cc113d1fe6910b506eb3",
    (F02, "2.2"): "1d6894f7880550b0d06c1ebd9cb1e093fc5ec4af21925cd88cd2ca95106a9b91",
}
#: The synthetic 1.3 adapter's build program and the plain inference program,
#: recorded before this change: they keep their bytes.
SYNTHETIC_BUILD_PROGRAM_SHA256 = (
    "7c97aabcbf7a00298455a4266931b2a49147e015d6616825ab86944cb2b3211e"
)
INFER_PROGRAM_SHA256 = (
    "7de52787eb9d0af81fb1bcb21e2ff2213970107a9c1306f1c35070b7cad92bff"
)
#: The judge's per-case grading tolerance for a direct graph adapter's
#: isolated-versus-batched predictions (tests/cpu/test_battery_direct_graph.py).
ISOLATED_RTOL = ISOLATED_ATOL = 1e-5


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _recipe(key, training=None, *, fraction=1.0, use=None, output=None, digest=None):
    kit = PUBLIC[key[0]].construction_kit(*key)
    spec = adapter.SPECS.get(key)
    train_use = (
        {"dataset": spec.train_use if spec else "x", "train_fraction": fraction}
        if use is None
        else use
    )
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": dict(
                zip(
                    (
                        "id",
                        "version",
                        "train_digest",
                        "interface_digest",
                        "construction_limits_digest",
                    ),
                    (
                        kit["id"],
                        kit["version"],
                        kit["train_digest"],
                        kit["interface_digest"],
                        kit["construction_limits_digest"],
                    ),
                )
            ),
            "source": {
                "kind": "graph",
                "submission_digest": digest or "sha256:" + "0" * 64,
            },
            "procedure": {
                "entrypoint": None,
                "configuration": {"training": dict(training or {})},
                "train_use": train_use,
                "initial_state": None,
            },
            "output": {
                "format": output or adapter.OUTPUT_FORMAT,
                "interface_digest": kit["interface_digest"],
            },
        }
    )


def _refused(recipe):
    with pytest.raises(RecipeRefused) as caught:
        adapter.training_settings(recipe)
    return caught.value.code


# --- Versions, identity and limits ---------------------------------------------------


def test_the_trainer_digest_is_pinned_and_in_each_construction_identity():
    raw = (ROOT / adapter.TRAINER_PATH).read_bytes()
    assert _sha(raw) == adapter.TRAINER_SHA256
    assert adapter.trainer_source() == raw
    assert adapter.TRAINER_PIN == (adapter.TRAINER_PATH, adapter.TRAINER_SHA256)
    for key in SERVED:
        limits = PUBLIC[key[0]].construction_limits_document(*key)
        trainer = limits["graph_training_adapter"]["trainer"]
        assert trainer["sha256"] == "sha256:" + adapter.TRAINER_SHA256
        assert trainer["module"] == adapter.TRAINER_MODULE


def test_f08_1_4_and_f02_2_3_register_as_v7_catalog_versions():
    v7 = allowlist_module.v7_bytes()
    for key in SERVED:
        assert key in sv.CATALOG and key in sv.V7
        assert sv.serves_catalog(*key) and sv.serves_v7(*key)
        assert sv.is_step2(*key) and not sv.step_caps(*key)
        assert sv.graph_allowlist_bytes(*key) == v7
        assert adapter.served_allowlist_bytes(*key) == v7
        assert physical_material.is_registered(*key)
        assert key[1] in TRAIN[key[0]].CHALLENGE_VERSIONS
    assert f08_train.load_public_train("1.4")["train"] == (
        f08_train.load_public_train("1.3")["train"]
    )
    assert f02_train.load_public_train("2.3")["train"] == (
        f02_train.load_public_train("2.2")["train"]
    )
    # 1.5 / 2.4 are graph route v2 (`version_registry`); 1.6 / 2.5 are not.
    for key in ((F08, "1.6"), (F02, "2.5")):
        with pytest.raises(sv.UnregisteredVersion):
            sv.graph_allowlist_bytes(*key)


def test_only_1_4_and_2_3_carry_the_catalog_and_the_graph_adapter():
    for key in SERVED:
        limits = PUBLIC[key[0]].construction_limits_document(*key)
        assert limits["backbone_catalog"] == {
            "schema": served.SCHEMA,
            "digest": served.digest(*key),
        }
        assert limits["graph_training_adapter"] == adapter.adapter_block(*key)
        assert limits["training_step_cap"] is None
        block = limits["graph_training_adapter"]
        spec = adapter.SPECS[key]
        assert block["id"] == spec.adapter_id
        assert block["source_kind"] == "graph"
        assert block["train_use_dataset"] == spec.train_use
        assert block["output_format"] == "carbon.numeric-graph.v1"
        assert block["train_surfaces"]["batch_size"] == {
            "kind": "uint",
            "low": 1,
            "high": 64,
            "default": 8,
        }
        # Apart from the two blocks and the version, 1.4 / 2.3 are 1.3 / 2.2.
        before = "1.3" if key[0] == F08 else "2.2"
        old = PUBLIC[key[0]].construction_limits_document(key[0], before)
        limits.pop("backbone_catalog")
        limits.pop("graph_training_adapter")
        limits["challenge"]["version"] = before
        assert limits == old
    for (challenge_id, version), expected in EARLIER.items():
        public = PUBLIC[challenge_id]
        limits = public.construction_limits_document(challenge_id, version)
        assert "graph_training_adapter" not in limits
        assert "backbone_catalog" not in limits
        kit = public.construction_kit(challenge_id, version)
        assert kit["construction_limits_digest"] == "sha256:" + expected


def test_the_adapter_constants_equal_the_challenge_modules():
    for key, spec in adapter.SPECS.items():
        train = TRAIN[key[0]]
        loaded = train.load_public_train(key[1])
        assert "sha256:" + spec.train_sha256 == loaded["provenance"]["train_sha256"]
        assert spec.rows == len(loaded["case_ids"]) == loaded["inputs"].shape[0]
        assert (spec.inputs, spec.outputs) == (len(train.FIELDS), len(train.TARGETS))
        interface = PUBLIC[key[0]].interface_document(*key)
        assert interface["train_dtype"] == "<f4"
        assert interface["input"]["shape"] == [spec.inputs]
        assert interface["output"]["shape"] == [spec.outputs]
        graph = adapter.graph_interface(spec)
        assert graph.inputs == (("inputs/features", "float32", (spec.inputs,)),)
        assert graph.outputs == (("float32", (spec.outputs,)),)
    assert adapter.SPECS[(F08, "1.4")].train_sha256 == f08_train.TRAIN_V2_SHA256
    assert adapter.SPECS[(F02, "2.3")].train_sha256 == f02_train.TRAIN_SHA256
    assert adapter.SPECS[(F02, "2.3")].rows == 40


def test_the_surfaces_are_the_registered_rows_the_spec_copies():
    from carbon.reconstruction import capability_registry as registry

    rows = {
        c.capability_id.partition(".")[2]: c.surface
        for c in registry.REGISTRY
        if c.surface is not None and c.surface.group == "train"
    }
    battery = {
        c.capability_id.partition(".")[2]: c.surface
        for c in registry.BATTERY_REGISTRY
        if c.surface is not None and c.surface.group == "train"
    }
    for name, (kind, low, high, default) in adapter.TRAIN_SURFACES.items():
        if name == "precision":
            assert (kind, low, high, default) == (
                "choice",
                ("float32",),
                None,
                "float32",
            )
            continue
        row = rows[name]
        assert (kind, low, default) == (row.kind, row.low, row.default), name
        # steps and warmup_steps keep no fixed cap (OWNER-REBUILD-TIME-LIMIT-01).
        assert high == (None if name in ("steps", "warmup_steps") else row.high)
    fraction = battery["train_fraction"]
    assert adapter.TRAIN_FRACTION == (
        fraction.kind,
        fraction.low,
        fraction.high,
        fraction.default,
    )
    registered = set(rows) | set(battery)
    assert adapter.UNSERVED_SURFACES == registered - set(adapter.TRAIN_SURFACES) - {
        "train_fraction"
    }


def test_every_adapter_code_is_registered_with_its_class():
    for prefix in ("f08", "f02"):
        for suffix in adapter.REFUSED_SUFFIXES:
            assert build_refusal.CODES[f"{prefix}_graph_{suffix}"] == (
                build_refusal.REFUSED
            )
        for suffix in adapter.GAP_SUFFIXES:
            assert build_refusal.CODES[f"{prefix}_graph_{suffix}"] == build_refusal.GAP
    for code in (
        "decoded_graph_state_decoder_invalid",
        "decoded_graph_state_output_invalid",
    ):
        assert build_refusal.CODES[code] == build_refusal.REFUSED


def test_f02_2_3_and_f08_1_4_material_serve_the_adapter():
    # Both versions have their pack labels (physical_pack, the packs lane's:
    # the predecessor's exam under their own pack version), so each material
    # loads with v7 and the adapter block.
    material = physical_material.bundle_material(F02, "2.3")
    assert material["allowlist_bytes"] == allowlist_module.v7_bytes()
    limits = material["construction_limits_document"]
    assert limits["graph_training_adapter"] == adapter.adapter_block(F02, "2.3")
    assert material["construction_kit"] == f02_public.construction_kit(F02, "2.3")
    material = physical_material.bundle_material(F08, "1.4")
    assert material["allowlist_bytes"] == allowlist_module.v7_bytes()
    limits = material["construction_limits_document"]
    assert limits["graph_training_adapter"] == adapter.adapter_block(F08, "1.4")


# --- Training surfaces ---------------------------------------------------------------


@pytest.mark.parametrize("key", SERVED)
def test_the_default_recipe_resolves_every_surface_default(key):
    values = adapter.training_settings(_recipe(key))
    assert values == {
        **{name: row[3] for name, row in adapter.TRAIN_SURFACES.items()},
        "train_fraction": 1.0,
    }


OUT_OF_BOUNDS = [
    ("steps", 1),
    ("steps", 2.0),
    ("steps", True),
    ("batch_size", 0),
    ("batch_size", 65),
    ("learning_rate", 0.0),
    ("learning_rate", 0.0500001),
    ("learning_rate", "0.002"),
    ("weight_decay", -0.1),
    ("weight_decay", 0.2),
    ("beta1", 1.0),
    ("beta2", 1.0),
    ("adam_epsilon", 0.0),
    ("adam_epsilon", 0.02),
    ("warmup_steps", -1),
    ("warmup_steps", 1.5),
    ("precision", "float64"),
    ("precision", "bfloat16"),
]


@pytest.mark.parametrize("key", SERVED)
@pytest.mark.parametrize("name, value", OUT_OF_BOUNDS)
def test_every_surface_refuses_out_of_bounds_values(key, name, value):
    prefix = adapter.SPECS[key].prefix
    assert _refused(_recipe(key, {name: value})) == (
        f"{prefix}_graph_training_value_invalid"
    )


@pytest.mark.parametrize("key", SERVED)
def test_steps_and_warmup_have_no_fixed_cap(key):
    values = adapter.training_settings(
        _recipe(key, {"steps": 10**9, "warmup_steps": 10**9})
    )
    assert values["steps"] == values["warmup_steps"] == 10**9


@pytest.mark.parametrize("key", SERVED)
@pytest.mark.parametrize("fraction", [0.05, 1.5, True, "1.0"])
def test_train_fraction_refuses_out_of_bounds(key, fraction):
    prefix = adapter.SPECS[key].prefix
    assert _refused(_recipe(key, fraction=fraction)) == (
        f"{prefix}_graph_training_value_invalid"
    )


@pytest.mark.parametrize("key", SERVED)
def test_unknown_fields_refuse_and_unserved_surfaces_are_gaps(key):
    prefix = adapter.SPECS[key].prefix + "_graph_"
    for training in ({"momentum": 0.9}, {"train_fraction": 0.5}, {"seed": 1}):
        assert _refused(_recipe(key, training)) == prefix + "training_field_invalid"
    for name in ("ensemble_members", "ema_decay", "h1_weight", "curriculum"):
        assert _refused(_recipe(key, {name: 1})) == prefix + "surface_unserved"
    # An unknown name beside an unserved one is the candidate's.
    assert _refused(_recipe(key, {"ensemble_members": 2, "momentum": 0.9})) == (
        prefix + "training_field_invalid"
    )


@pytest.mark.parametrize("key", SERVED)
def test_the_procedure_and_output_must_be_the_adapters(key):
    spec = adapter.SPECS[key]
    prefix = spec.prefix + "_graph_"
    for use in (
        {"dataset": spec.train_use},
        {"dataset": "another-train", "train_fraction": 1.0},
        {"dataset": spec.train_use, "train_fraction": 1.0, "curriculum": "none"},
    ):
        assert _refused(_recipe(key, use=use)) == prefix + "procedure_invalid"
    assert _refused(_recipe(key, output="carbon.other.v1")) == (
        prefix + "output_unsupported"
    )


@pytest.mark.parametrize("key", [(F08, "1.3"), (F02, "2.2"), (F02, "2.1")])
def test_earlier_versions_have_no_graph_adapter(key):
    prefix = adapter.PREFIXES[key[0]]
    assert _refused(_recipe(key)) == f"{prefix}_graph_challenge_version_unregistered"


def test_batch_size_above_the_selected_train_rows_is_refused():
    # F02 has 40 TRAIN rows; 0.1 of them is 4.
    f02, f08 = (F02, "2.3"), (F08, "1.4")
    assert adapter.training_settings(_recipe(f02, {"batch_size": 40}))
    for batch in (41, 64):
        assert _refused(_recipe(f02, {"batch_size": batch})) == (
            "f02_graph_batch_exceeds_train"
        )
    assert adapter.training_settings(_recipe(f02, {"batch_size": 4}, fraction=0.1))
    assert _refused(_recipe(f02, fraction=0.1)) == "f02_graph_batch_exceeds_train"
    # F08: 287 rows; 0.1 of them is 28.
    assert adapter.selected_rows(adapter.SPECS[f08], 0.1) == 28
    assert adapter.training_settings(_recipe(f08, {"batch_size": 28}, fraction=0.1))
    assert _refused(_recipe(f08, {"batch_size": 29}, fraction=0.1)) == (
        "f08_graph_batch_exceeds_train"
    )


# --- Receiver selection --------------------------------------------------------------


def _discovery(key, limits):
    return SimpleNamespace(
        info=SimpleNamespace(challenge_key=key),
        _checked=lambda selected: None,
        _material={"construction_limits_document": limits},
    )


def test_the_receiver_selects_the_adapter_only_on_1_4_and_2_3():
    from carbon.challenge_kit import synthetic_linear_field_2d
    from carbon.development_session.research_service import DirectFixtureDiscovery

    select = DirectFixtureDiscovery.graph_adapter_for
    for key in SERVED:
        challenge_key = research.ChallengeKey(*key)
        limits = PUBLIC[key[0]].construction_limits_document(*key)
        assert select(_discovery(challenge_key, limits), challenge_key) == (
            adapter.SPECS[key].adapter_id
        )
        altered = json.loads(json.dumps(limits))
        altered["graph_training_adapter"]["trainer"]["sha256"] = "sha256:" + "1" * 64
        assert select(_discovery(challenge_key, altered), challenge_key) is None
        other = research.ChallengeKey(key[0], "1.3" if key[0] == F08 else "2.2")
        assert select(_discovery(other, limits), challenge_key) is None
    for key in ((F08, "1.3"), (F02, "2.2")):
        challenge_key = research.ChallengeKey(*key)
        limits = PUBLIC[key[0]].construction_limits_document(*key)
        assert select(_discovery(challenge_key, limits), challenge_key) is None
    synthetic = research.ChallengeKey(
        synthetic_linear_field_2d.CHALLENGE.challenge_id, "1.3"
    )
    limits = synthetic_linear_field_2d.construction_limits_document_v3()
    assert select(_discovery(synthetic, limits), synthetic) == (
        direct_graph_construction_worker.SYNTHETIC_ADAPTER_ID
    )
    # Battery 2.2's adapter is registered beside these (its own tests:
    # test_battery_graph_adapter.py), and graph route v2's.
    from carbon.development_session import (
        battery_graph_adapter,
        physical_graph_adapter_v2,
    )

    assert direct_graph_construction_worker.graph_adapter_ids() == {
        direct_graph_construction_worker.SYNTHETIC_ADAPTER_ID,
        *adapter.ADAPTER_IDS,
        *battery_graph_adapter.ADAPTER_IDS,
        *physical_graph_adapter_v2.ADAPTER_IDS,
    }


def test_the_synthetic_path_and_the_plain_inference_program_keep_their_bytes():
    worker = direct_graph_construction_worker
    assert _sha(worker.BUILD_PROGRAM.encode()) == SYNTHETIC_BUILD_PROGRAM_SHA256
    assert _sha(bundle_construction_worker.INFER_PROGRAM.encode()) == (
        INFER_PROGRAM_SHA256
    )
    assert worker.STAGED_MODULES[-1] == (
        "carbon.development_session.synthetic_graph_adapter"
    )
    assert not any("physical" in name for name in worker.STAGED_MODULES)
    assert "synthetic_graph_adapter" not in repr(worker.PHYSICAL_STAGED_MODULES)
    # The decoded program is the plain one plus the decoder, nothing else.
    decoded = worker.PHYSICAL_INFER_PROGRAM
    assert decoded != bundle_construction_worker.INFER_PROGRAM
    assert "* decoder_sd + decoder_mu" in decoded
    assert "physical_graph_state import load" in decoded


def test_the_receiver_refuses_a_physical_stage_off_its_served_identity():
    key = (F08, "1.4")
    kit = f08_public.construction_kit(*key)
    binding = {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }
    limits = f08_public.construction_limits_document(*key)
    stage = direct_graph_construction_worker._physical_stage
    spec, _allowed, files = stage(binding, limits, allowlist_module.v7_bytes())
    assert spec.adapter_id == adapter.SPECS[key].adapter_id
    assert set(files) == {
        name + ".py"
        for name in direct_graph_construction_worker.PHYSICAL_STAGED_MODULES
    }
    with pytest.raises(RecipeRefused, match="direct_graph_allowlist_unregistered"):
        stage(binding, limits, allowlist_module.served_bytes())
    altered = json.loads(json.dumps(limits))
    altered["graph_training_adapter"]["id"] = "another"
    with pytest.raises(RecipeRefused, match="direct_graph_adapter_identity_invalid"):
        stage(binding, altered, allowlist_module.v7_bytes())


# --- Training and inference (JAX; the G3 parser needs POSIX rlimits) -----------------

posix = pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")


def _graph(key, batch):
    """A small MLP graph of the Challenge's interface at `batch` cases."""
    pytest.importorskip("jax")
    import jax.numpy as jnp

    from carbon.level4 import graph, initializers, intake, staging, submission
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[key]
    allowed = allowlist_module.Allowlist(allowlist_module.v7_bytes())
    width = 16

    def forward(w1, b1, w2, b2, x):
        return jnp.tanh(x @ w1 + b1) @ w2 + b2

    _, document, _ = through_bprime(
        forward,
        (
            jnp.zeros((spec.inputs, width), jnp.float32),
            jnp.zeros((width,), jnp.float32),
            jnp.zeros((width, spec.outputs), jnp.float32),
            jnp.zeros((spec.outputs,), jnp.float32),
            jnp.ones((batch, spec.inputs), jnp.float32),
        ),
        role="forward",
        allowlist=allowed,
        input_names=[
            "params/0",
            "params/1",
            "params/2",
            "params/3",
            adapter.INPUT_NAME,
        ],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "glorot_normal",
                "fan_in_axes": [0],
                "fan_out_axes": [1],
            },
            {
                "input": "params/1",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            },
            {
                "input": "params/2",
                "initializer": "glorot_normal",
                "fan_in_axes": [0],
                "fan_out_axes": [1],
            },
            {
                "input": "params/3",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            },
        ],
    }
    manifest, files = submission.build(
        challenge=spec.challenge_id,
        interface=adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    raw_manifest = submission.canonical(manifest)
    return raw_manifest, files, submission.digest(manifest), staging


def _case(key, training=None, *, fraction=1.0):
    batch = (training or {}).get("batch_size", 8)
    raw_manifest, files, submission_digest, staging = _graph(key, batch)
    recipe = _recipe(key, training, fraction=fraction, digest=submission_digest)
    return recipe, raw_manifest, files, staging


def _train(key):
    loaded = TRAIN[key[0]].load_public_train(key[1])
    return loaded["train"], np.asarray(loaded["inputs"]), np.asarray(loaded["targets"])


def _model(key, recipe, raw_manifest, files):
    return adapter.build_validated_graph(
        recipe,
        raw_manifest,
        files,
        allowlist_bytes=adapter.served_allowlist_bytes(*key),
        train_cases=adapter.SPECS[key].rows,
    )


@posix
@pytest.mark.parametrize("key", SERVED)
def test_the_default_recipe_trains_and_two_seeded_rebuilds_are_bit_identical(key):
    recipe, raw_manifest, files, _staging = _case(key)
    _raw, inputs, targets = _train(key)
    first, second = (_model(key, recipe, raw_manifest, files) for _ in range(2))
    fit = first.fit(inputs, targets, seed=7)
    assert fit == second.fit(inputs, targets, seed=7)
    assert fit["steps"] == 512 and fit["train_cases"] == adapter.SPECS[key].rows
    assert fit["trainer_sha256"] == "sha256:" + adapter.TRAINER_SHA256
    assert np.isfinite(fit["train_loss"])
    for a, b in zip(first.params, second.params):
        assert a.dtype == np.float32 and a.tobytes() == b.tobytes()
    assert first.mu.tobytes() == second.mu.tobytes()
    assert first.frozen_state() == second.frozen_state()
    # Standardisation statistics come from the selected TRAIN rows only.
    np.testing.assert_array_equal(first.mu, targets.mean(axis=0).astype(np.float32))
    other = _model(key, recipe, raw_manifest, files)
    other.fit(inputs, targets, seed=8)
    assert any(a.tobytes() != b.tobytes() for a, b in zip(first.params, other.params))


@posix
@pytest.mark.parametrize("key", SERVED)
def test_isolated_predict_matches_batched_and_the_interface(key):
    recipe, raw_manifest, files, _staging = _case(key, {"steps": 32})
    _raw, inputs, targets = _train(key)
    model = _model(key, recipe, raw_manifest, files)
    model.fit(inputs, targets, seed=3)
    rows = inputs[:11]
    batched = model.predict(rows)
    isolated = model.predict(rows, isolated=True)
    spec = adapter.SPECS[key]
    assert batched.dtype == isolated.dtype == np.float32
    assert batched.shape == isolated.shape == (11, spec.outputs)
    np.testing.assert_allclose(
        isolated, batched, rtol=ISOLATED_RTOL, atol=ISOLATED_ATOL
    )
    with pytest.raises(RecipeRefused, match=f"{spec.prefix}_graph_input_invalid"):
        model.predict(rows.astype(np.float64))
    with pytest.raises(RecipeRefused, match=f"{spec.prefix}_graph_seed_invalid"):
        model.fit(inputs, targets, seed=-1)


@posix
def test_a_train_fraction_subset_standardises_on_its_rows_only():
    from carbon.development_session import physical_graph_trainer

    key = (F08, "1.4")
    recipe, raw_manifest, files, _staging = _case(
        key, {"steps": 4, "batch_size": 8}, fraction=0.5
    )
    _raw, inputs, targets = _train(key)
    model = _model(key, recipe, raw_manifest, files)
    fit = model.fit(inputs, targets, seed=5)
    rows = physical_graph_trainer.selected_rows(len(inputs), 0.5, 5)
    assert fit["train_cases"] == len(rows) == 143
    np.testing.assert_array_equal(
        model.mu, targets[rows].mean(axis=0).astype(np.float32)
    )


@posix
def test_a_graph_batch_other_than_batch_size_is_refused():
    from carbon.level4.graph import GraphRefused

    key = (F02, "2.3")
    raw_manifest, files, submission_digest, _staging = _graph(key, 8)
    recipe = _recipe(key, {"batch_size": 16}, digest=submission_digest)
    with pytest.raises(GraphRefused):
        _model(key, recipe, raw_manifest, files)


def _local_runner():
    count = itertools.count()

    def runner(ledger, *, source, files, output_validator, **_kwargs):
        name = f"operation-{next(count):064x}"
        home = ledger.root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        done = subprocess.run(
            [sys.executable, "-c", source],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-4000:]
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        return {
            "operation": name,
            "files": {
                path.name: "sha256:" + _sha(path.read_bytes())
                for path in snapshot.iterdir()
            },
        }

    return runner


def _image():
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    return WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8))


def _binding(key):
    kit = PUBLIC[key[0]].construction_kit(*key)
    return {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }


@posix
@pytest.mark.parametrize("key", SERVED)
def test_the_receiver_rebuilds_then_infers_one_isolated_case_per_call(key, tmp_path):
    from carbon.development_session.profile import canonical

    recipe, raw_manifest, files, staging = _case(key, {"steps": 16})
    raw_train, inputs, targets = _train(key)
    query = np.ascontiguousarray(inputs[:5])
    envelope = canonical(staging.envelope(raw_manifest, files))
    spec = adapter.SPECS[key]
    result = direct_graph_construction_worker.reconstruct_and_infer_graph_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        image=_image(),
        recipe=recipe,
        challenge_binding=_binding(key),
        limits_document=PUBLIC[key[0]].construction_limits_document(*key),
        source_envelope=envelope,
        train=raw_train,
        inputs=query,
        expected_output_shape=(5, spec.outputs),
        allowlist_bytes=adapter.served_allowlist_bytes(*key),
        seed=0,
        runner=_local_runner(),
        adapter_id=spec.adapter_id,
    )
    assert result.execution_boundary == "TEST_ONLY_LOCAL_RUNNER"
    assert result.build.receipt["fit"]["adapter_id"] == spec.adapter_id
    predictions = np.asarray(result.inference.predictions, dtype=np.float32)
    assert predictions.shape == (5, spec.outputs)
    # The separate inference child decodes exactly as the in-worker model does.
    model = _model(key, recipe, raw_manifest, files)
    model.fit(inputs, targets, seed=0)
    np.testing.assert_allclose(
        predictions,
        model.predict(query, isolated=True),
        rtol=ISOLATED_RTOL,
        atol=ISOLATED_ATOL,
    )
    state = result.build.state_path.read_bytes()
    with pytest.raises(RecipeRefused):
        # The plain loader refuses a decoded state.
        from carbon.development_session import bundle_graph_state

        bundle_graph_state.load(
            state,
            recipe,
            allowlist_module.Allowlist(allowlist_module.v7_bytes()),
        )


@posix
def test_the_build_program_settles_refusals_and_gaps_by_their_class(tmp_path):
    from carbon.development_session.profile import canonical

    key = (F02, "2.3")
    cases = (
        ({"ensemble_members": 2}, "UNRESOLVED", "f02_graph_surface_unserved"),
        ({"momentum": 0.9}, "REFUSED", "f02_graph_training_field_invalid"),
        ({"batch_size": 41}, "REFUSED", "f02_graph_batch_exceeds_train"),
    )
    raw_manifest, files, submission_digest, staging = _graph(key, 8)
    raw_train, _inputs, _targets = _train(key)
    envelope = canonical(staging.envelope(raw_manifest, files))
    for index, (training, state, detail) in enumerate(cases):
        recipe = _recipe(key, training, digest=submission_digest)
        with pytest.raises(
            direct_graph_construction_worker.GraphConstructionDecision
        ) as caught:
            direct_graph_construction_worker.reconstruct_public_graph(
                SimpleNamespace(root=tmp_path / str(index)),
                owner="test",
                identity="test",
                image=_image(),
                recipe=recipe,
                challenge_binding=_binding(key),
                limits_document=f02_public.construction_limits_document(*key),
                source_envelope=envelope,
                train=raw_train,
                allowlist_bytes=adapter.served_allowlist_bytes(*key),
                seed=0,
                seconds=600,
                runner=_local_runner(),
                adapter_id=adapter.SPECS[key].adapter_id,
            )
        decision = caught.value
        assert (decision.state, decision.detail_code) == (state, detail)
        assert decision.reason_code == (
            "graph_submission_invalid"
            if state == "REFUSED"
            else "carbon_graph_adapter_unavailable"
        )
