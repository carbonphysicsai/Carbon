"""Common bundle-model bytes get custody without replay or score authority."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import struct
import zipfile

import pytest

from carbon.level4 import staging
from scripts.dev.score_lab import public_unbound_custody as custody
from scripts.dev.score_lab import public_unbound_entry as entry


def _json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _npy(descr, raw, shape):
    header = repr({"descr": descr, "fortran_order": False, "shape": shape}).encode(
        "ascii"
    )
    header += b" " * ((16 - (10 + len(header) + 1) % 16) % 16) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + raw


def _npz(**arrays):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, (descr, raw, shape) in arrays.items():
            archive.writestr(f"{name}.npy", _npy(descr, raw, shape))
    return out.getvalue()


def _fixture(tmp_path, *, physics=True, seed=True, fixture=True, predictions=True):
    root = tmp_path / "producer"
    root.mkdir()
    train = _npz(
        inputs=("<f4", struct.pack("<f", 1.0), (1,)),
        targets=("<f4", struct.pack("<f", 0.25), (1,)),
    )
    interface = _sha(b"synthetic-2d-interface")
    bundle_digest = _sha(b"synthetic-source-bundle")
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": "synthetic-linear-field-2d",
            "version": "1.0",
            "train_digest": _sha(train),
            "interface_digest": interface,
            "construction_limits_digest": _sha(b"synthetic-2d-limits"),
        },
        "source": {
            "kind": "bundle",
            "bundle_ref": {
                "schema": "carbon.library-bundle-ref.v1",
                "bundle_digest": bundle_digest,
                "language": "python",
                "runtime_profile_id": "synthetic-fixture-only",
                "environment_digest": _sha(b"synthetic-environment"),
            },
        },
        "procedure": {
            "entrypoint": {"module": "toy", "name": "build"},
            "configuration": {},
            "train_use": {},
            "initial_state": None,
        },
        "output": {"format": "carbon.numeric-graph.v1", "interface_digest": interface},
    }
    graph = _json({"entry": "main", "graphs": {"main": {"inputs": [], "outputs": []}}})
    header = {
        "schema": custody.BUNDLE_STATE_SCHEMA,
        "recipe_digest": _sha(_json(recipe)),
        "bundle_digest": bundle_digest,
        "train_digest": _sha(train),
        "interface_digest": interface,
        "graph_digest": _sha(graph),
        "allowlist_digest": _sha(b"synthetic-allowlist"),
        "parameter_count": 3,
    }
    state = _npz(
        __header__=("|u1", _json(header), (len(_json(header)),)),
        graph=("|u1", graph, (len(graph),)),
        parameter0000=("<f4", struct.pack("<ff", 1.0, 2.0), (2,)),
        parameter0001=("<f4", struct.pack("<f", 0.25), (1,)),
        parameter0002=("<i4", struct.pack("<i", 3), (1,)),
    )
    artifacts = {
        "stage/recipe.json": _json(recipe),
        "stage/train.npz": train,
        "stage/example.npz": _npz(inputs=("<f4", struct.pack("<f", 1.0), (1,))),
        "build/output/state.npz": state,
        "infer/output/predictions.json": _json([[[[0.25]]]]),
        "stage/source.tar.gz": b"synthetic source bytes; never executed by custody",
        "stage/environment.json": _json({"profile": "synthetic fixture"}),
        "stage/image.json": _json({"image": "synthetic fixture"}),
        "stage/seed.json": _json({"seed": 7}),
        "build/output/receipt.json": _json(
            {
                "schema": "carbon.development.bundle-build.v1",
                "recipe_digest": _sha(_json(recipe)),
                "bundle_digest": bundle_digest,
                "train_digest": _sha(train),
                "state_digest": _sha(state),
                "allowlist_digest": header["allowlist_digest"],
                "framework": "jax",
            }
        ),
    }
    roles = {
        "recipe": ("stage/recipe.json", "json"),
        "train": ("stage/train.npz", "numeric_npz"),
        "fixture": ("stage/example.npz", "numeric_npz"),
        "state": ("build/output/state.npz", "bundle_graph_npz"),
        "predictions": ("infer/output/predictions.json", "json"),
        "source": ("stage/source.tar.gz", "raw_bytes"),
        "environment": ("stage/environment.json", "raw_bytes"),
        "image": ("stage/image.json", "json"),
        "seed": ("stage/seed.json", "json"),
        "build_receipt": ("build/output/receipt.json", "json"),
    }
    if not seed:
        del artifacts["stage/seed.json"]
        del roles["seed"]
    if not fixture:
        del artifacts["stage/example.npz"]
        del roles["fixture"]
    if not predictions:
        del artifacts["infer/output/predictions.json"]
        del roles["predictions"]
    for name, body in artifacts.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    contract = {
        "version": "synthetic-linear-field-2d-v1",
        "definition": {
            "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
            "relation": "target = forcing / 4",
            "units": "dimensionless",
        },
    }
    manifest = {
        "schema": custody.BUNDLE_ROLE_SCHEMA_V2,
        "scope": custody.BUNDLE_SCOPE,
        "source_schema": custody.BUNDLE_STATE_SCHEMA,
        "roles": {
            role: {"file": name, "codec": codec}
            for role, (name, codec) in roles.items()
        },
        "retained_files": {name: _sha(body) for name, body in artifacts.items()},
        "physics_contract": contract if physics else None,
    }
    manifest_path = tmp_path / "roles.json"
    manifest_path.write_bytes(_json(manifest))
    return root, manifest_path, artifacts


def _graph_fixture(tmp_path):
    """Inert original graph bytes, including both original worker receipts."""
    root, manifest_path, artifacts = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    recipe = json.loads(artifacts["stage/recipe.json"])
    raw_manifest = _json({"schema": "toy-level4-manifest", "documents": []})
    raw_document = _json({"schema": "toy-level4-document"})
    envelope = staging.envelope(raw_manifest, {_sha(raw_document): raw_document})
    submission_digest = envelope["submission"]
    recipe["source"] = {"kind": "graph", "submission_digest": submission_digest}
    recipe["procedure"]["entrypoint"] = None
    recipe_raw = _json(recipe)
    graph = _json({"entry": "main", "graphs": {"main": {"inputs": [], "outputs": []}}})
    allowlist = _json({"toy": "allowlist-only"})
    header = {
        "schema": custody.GRAPH_SOURCE_STATE_SCHEMA,
        "recipe_digest": _sha(recipe_raw),
        "submission_digest": submission_digest,
        "train_digest": _sha(artifacts["stage/train.npz"]),
        "interface_digest": recipe["challenge"]["interface_digest"],
        "graph_digest": _sha(graph),
        "allowlist_digest": _sha(allowlist),
        "parameter_count": 0,
    }
    state = _npz(
        __header__=("|u1", _json(header), (len(_json(header)),)),
        graph=("|u1", graph, (len(graph),)),
    )
    build_receipt = {
        "schema": "carbon.development.graph-build.v1",
        "recipe_digest": _sha(recipe_raw),
        "submission_digest": submission_digest,
        "train_digest": _sha(artifacts["stage/train.npz"]),
        "state_digest": _sha(state),
        "allowlist_digest": _sha(allowlist),
        "framework": "jax",
        "fit": {"toy_only": 1.0},
    }
    inputs = _npz(inputs=("<f4", struct.pack("<f", 1.0), (1, 1, 1, 1)))
    predictions = _json([[[[0.25]]]])
    inference_receipt = {
        "schema": "carbon.development.bundle-inference.v2",
        "recipe_digest": _sha(recipe_raw),
        "state_digest": _sha(state),
        "inputs_digest": _sha(inputs),
        "predictions_digest": _sha(predictions),
        "measurement": {
            "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
            "timing_s": {
                "preprocess": 0.1,
                "inference": 0.2,
                "postprocess": 0.1,
                "export": 0.1,
            },
            "input_shape": [1, 1, 1, 1],
            "input_dtype": "float32",
            "output_shape": [1, 1, 1, 1],
            "output_dtype": "float32",
        },
    }
    image_digest = _sha(b"toy-worker-image")
    image = {
        name: (
            image_digest
            if name in {"image_id", "config_digest"}
            else _sha(name.encode())
        )
        for name in (
            "image_id",
            "config_digest",
            "source_tree_digest",
            "wheel_digest",
            "lock_digest",
            "base_image_digest",
            "build_recipe_digest",
            "entrypoint_digest",
        )
    }
    worker_evidence = {
        "schema": "carbon.direct-private-attempt.graph.v1",
        "image_id": image_digest,
        "parent_image_id": image_digest,
        "inference_image_id": image_digest,
        "build_operation": "operation-" + "a" * 64,
        "inference_operation": "operation-" + "b" * 64,
        "build_controls_digest": _sha(b"toy-build-controls"),
        "inference_controls_digest": _sha(b"toy-inference-controls"),
        "state_digest": _sha(state),
        "predictions_digest": _sha(predictions),
        "build_receipt": build_receipt,
        "inference_receipt": inference_receipt,
        "predictions_raw_base64": base64.b64encode(predictions).decode("ascii"),
        "submission_digest": submission_digest,
    }
    kit = {"id": recipe["challenge"]["id"], "version": recipe["challenge"]["version"]}
    kit.update(
        {
            key: recipe["challenge"][key]
            for key in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        }
    )
    del artifacts["stage/source.tar.gz"]
    (root / "stage/source.tar.gz").unlink()
    del artifacts["stage/environment.json"]
    (root / "stage/environment.json").unlink()
    artifacts.update(
        {
            "stage/recipe.json": recipe_raw,
            "stage/source-envelope.json": _json(envelope),
            "stage/construction-kit.json": _json(kit),
            "stage/allowlist.json": allowlist,
            "stage/image.json": _json(image),
            "build/output/state.npz": state,
            "build/output/receipt.json": _json(build_receipt),
            "infer/inputs.npz": inputs,
            "infer/output/predictions.json": predictions,
            "infer/output/receipt.json": _json(inference_receipt),
            "stage/worker-evidence.json": _json(worker_evidence),
        }
    )
    for name, raw in artifacts.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest.update(
        {
            "schema": custody.GRAPH_ROLE_SCHEMA_V3,
            "source_schema": custody.GRAPH_SOURCE_STATE_SCHEMA,
            "roles": {
                **{
                    role: row
                    for role, row in manifest["roles"].items()
                    if role != "environment"
                },
                "source": {"file": "stage/source-envelope.json", "codec": "json"},
                "construction_kit": {
                    "file": "stage/construction-kit.json",
                    "codec": "json",
                },
                "allowlist": {"file": "stage/allowlist.json", "codec": "json"},
                "inputs": {"file": "infer/inputs.npz", "codec": "numeric_npz"},
                "inference_receipt": {
                    "file": "infer/output/receipt.json",
                    "codec": "json",
                },
                "worker_evidence": {
                    "file": "stage/worker-evidence.json",
                    "codec": "json",
                },
            },
            "retained_files": {name: _sha(raw) for name, raw in artifacts.items()},
        }
    )
    manifest_path.write_bytes(_json(manifest))
    return root, manifest_path, artifacts


def _graph_retain_mutation(root, manifest_path, role, changed):
    manifest = json.loads(manifest_path.read_bytes())
    name = manifest["roles"][role]["file"]
    (root / name).write_bytes(changed)
    manifest["retained_files"][name] = _sha(changed)
    manifest_path.write_bytes(_json(manifest))


def test_v4_raw_train_and_optional_fit_survive_v5_registration(tmp_path):
    """A historical V4 role map keeps its raw TRAIN codec after V5 is loaded."""
    root = tmp_path / "v4-originals"
    root.mkdir()
    train = gzip.compress(b'{"fixture_case":"v4-original-train"}\n', mtime=0)
    graph_digest = _sha(b"v4-fixture-graph")
    image_id = _sha(b"v4-fixture-image")
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": "v4-custody-fixture",
            "version": "development",
            "train_digest": _sha(train),
            "interface_digest": _sha(b"fixture-interface"),
            "construction_limits_digest": _sha(b"fixture-limits"),
        },
        "source": {"kind": "graph", "submission_digest": graph_digest},
    }
    state = _npz(
        __header__=("|u1", b"{}", (2,)),
        parameter0000=("<f4", struct.pack("<f", 2.0), (1,)),
    )
    originals = {
        "recipe.json": _json(recipe),
        "train.jsonl.gz": train,
        "source.json": _json(
            {"schema": "carbon.level4.staging-bundle.v1", "submission": graph_digest}
        ),
        "image.json": _json(
            {"schema": "carbon.c03.worker-image.v1", "image_id": image_id}
        ),
        "state.npz": state,
        "inputs.json": _json({"cases": [{"case_id": "fixture-case", "inputs": [1.0]}]}),
        "predictions.json": _json({"fixture-case": [2.0]}),
    }
    for name, raw in originals.items():
        (root / name).write_bytes(raw)
    lineage = {
        "schema": custody.GRAPH_LINEAGE_SCHEMA,
        "scope": custody.GRAPH_HTTP_SCOPE,
        "official_eligible": False,
        "graph_digest": graph_digest,
        "image_id": image_id,
        "recipe_digest": _sha(originals["recipe.json"]),
        "state_digest": _sha(state),
        "train_digest": _sha(train),
        "retained_files": {name: _sha(raw) for name, raw in originals.items()},
    }
    (root / "lineage.json").write_bytes(_json(lineage))
    roles = {
        role: {"file": name, "codec": codec}
        for role, name, codec in (
            ("recipe", "recipe.json", "json"),
            ("train", "train.jsonl.gz", "raw_bytes"),
            ("source", "source.json", "json"),
            ("image", "image.json", "json"),
            ("state", "state.npz", "numeric_npz"),
            ("inputs", "inputs.json", "json"),
            ("predictions", "predictions.json", "json"),
        )
    }
    manifest_path = tmp_path / "v4.roles.json"
    manifest_path.write_bytes(
        _json(
            {
                "schema": custody.GRAPH_ROLE_SCHEMA_V1,
                "source_schema": lineage["schema"],
                "scope": lineage["scope"],
                "roles": roles,
            }
        )
    )
    receipt = custody.prepare_custody_v4(root, manifest_path)
    assert receipt["train_digest"] == _sha(train)
    assert receipt["state_digest"] == _sha(state)
    assert receipt["evidence_state"] == {
        "build": "INCOMPLETE",
        "inference": "INCOMPLETE",
        "receiver_replay": "NOT_ATTEMPTED",
    }
    assert receipt["score_state"] == "NOT_COMPUTED"
    assert receipt["official_eligible"] is False
    receipt_path = tmp_path / "v4.custody.json"
    receipt_path.write_bytes(_json(receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    first = entry.create_entry_v4(root, manifest_path, receipt_path, entries)
    retry = entry.create_entry_v4(root, manifest_path, receipt_path, entries)
    assert first["status"] == "CREATED"
    assert retry["status"] == "ALREADY_PRESENT_IDENTICAL"
    assert retry["entry"] == first["entry"]
    assert {name: (root / name).read_bytes() for name in originals} == originals


def test_graph_v3_retains_original_procedure_and_measured_worker_bytes(tmp_path):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    receipt = custody.prepare_custody_v5(root, manifest_path)
    assert receipt["schema"] == custody.BUNDLE_CUSTODY_SCHEMA_V5
    assert receipt["source_schema"] == custody.GRAPH_SOURCE_STATE_SCHEMA
    assert receipt["source_kind"] == "graph"
    assert receipt["role_schema"] == custody.GRAPH_ROLE_SCHEMA_V3
    assert receipt["bundle_digest"] is None
    assert receipt["environment_ref_digest"] is None
    assert receipt["environment_digest"] is None
    assert "environment" not in receipt["roles"]
    assert "stage/environment.json" not in receipt["original_files"]
    assert (
        receipt["submission_digest"]
        == json.loads(originals["stage/source-envelope.json"])["submission"]
    )
    assert receipt["roles"]["worker_evidence"]["sha256"] == _sha(
        originals["stage/worker-evidence.json"]
    )
    assert receipt["roles"]["inference_receipt"]["sha256"] == _sha(
        originals["infer/output/receipt.json"]
    )
    assert receipt["score_state"] == "NOT_COMPUTED"
    assert receipt["official_eligible"] is False
    receipt_path = tmp_path / "custody.json"
    receipt_path.write_bytes(_json(receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    created = entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    assert created["status"] == "CREATED"
    assert created["entry"]["submission_digest"] == receipt["submission_digest"]
    assert created["entry"]["environment_digest"] is None
    assert created["entry"]["environment_ref_digest"] is None
    assert "environment" not in created["entry"]["roles"]
    assert created["entry"]["score_state"] == "NOT_COMPUTED"
    assert {name: (root / name).read_bytes() for name in originals} == originals


def test_graph_v3_hashes_cannot_replace_missing_original_bytes(tmp_path):
    root, manifest_path, _ = _graph_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    source_path = root / manifest["roles"]["source"]["file"]
    source_path.unlink()
    with pytest.raises(custody.CustodyRefused, match="graph_file"):
        custody.prepare_custody_v5(root, manifest_path)


def test_graph_v3_refuses_supplied_or_undeclared_environment_original(tmp_path):
    root, manifest_path, _ = _graph_fixture(tmp_path)
    environment_path = root / "stage/environment.json"
    environment_path.write_bytes(b"synthetic environment that graph v3 does not bind")
    with pytest.raises(
        custody.CustodyRefused, match="graph_undeclared_or_missing_file"
    ):
        custody.prepare_custody_v5(root, manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["retained_files"]["stage/environment.json"] = _sha(
        environment_path.read_bytes()
    )
    manifest["roles"]["environment"] = {
        "file": "stage/environment.json",
        "codec": "raw_bytes",
    }
    manifest_path.write_bytes(_json(manifest))
    with pytest.raises(custody.CustodyRefused, match="graph_roles"):
        custody.prepare_custody_v5(root, manifest_path)


def test_graph_v3_refuses_missing_required_role_and_procedure_entrypoint(tmp_path):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    del manifest["roles"]["worker_evidence"]
    manifest_path.write_bytes(_json(manifest))
    with pytest.raises(custody.CustodyRefused, match="graph_roles"):
        custody.prepare_custody_v5(root, manifest_path)
    manifest["roles"]["worker_evidence"] = {
        "file": "stage/worker-evidence.json",
        "codec": "json",
    }
    manifest_path.write_bytes(_json(manifest))
    recipe = json.loads(originals["stage/recipe.json"])
    recipe["procedure"]["entrypoint"] = {"module": "toy", "name": "build"}
    _graph_retain_mutation(root, manifest_path, "recipe", _json(recipe))
    with pytest.raises(custody.CustodyRefused, match="graph_recipe_kit_identity"):
        custody.prepare_custody_v5(root, manifest_path)


@pytest.mark.parametrize(
    "role,cause",
    [
        ("source", "graph_source_envelope"),
        ("construction_kit", "graph_recipe_kit_identity"),
        ("worker_evidence", "graph_worker_lineage"),
    ],
)
def test_graph_v3_original_lineage_mismatch_refused(tmp_path, role, cause):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    changed = json.loads(
        originals[json.loads(manifest_path.read_bytes())["roles"][role]["file"]]
    )
    if role == "source":
        changed["submission"] = _sha(b"wrong-submission")
    elif role == "construction_kit":
        changed["train_digest"] = _sha(b"wrong-train")
    else:
        changed["image_id"] = _sha(b"wrong-image")
    _graph_retain_mutation(root, manifest_path, role, _json(changed))
    with pytest.raises(custody.CustodyRefused, match=cause):
        custody.prepare_custody_v5(root, manifest_path)


def test_graph_v3_measured_inference_receipt_is_bound_not_a_cached_label(tmp_path):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    inference = json.loads(originals["infer/output/receipt.json"])
    del inference["measurement"]["timing_s"]["export"]
    _graph_retain_mutation(root, manifest_path, "inference_receipt", _json(inference))
    with pytest.raises(
        custody.CustodyRefused, match="graph_measured_inference_receipt"
    ):
        custody.prepare_custody_v5(root, manifest_path)


@pytest.mark.parametrize(
    "mutation,cause",
    [
        ("huge_build_fit", "graph_build_receipt"),
        ("overflowing_timing_total", "graph_measured_inference_receipt"),
        ("nonstring_output_dtype", "graph_measured_inference_receipt"),
        ("fractional_integer_dtype", "graph_measured_inference_receipt"),
    ],
)
def test_graph_v3_malformed_numeric_or_dtype_refuses_before_entry(
    tmp_path, mutation, cause
):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    valid_receipt = custody.prepare_custody_v5(root, manifest_path)
    receipt_path = tmp_path / "prior-custody.json"
    receipt_path.write_bytes(_json(valid_receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    worker = json.loads(originals["stage/worker-evidence.json"])
    if mutation == "huge_build_fit":
        role, embedded = "build_receipt", "build_receipt"
        changed = json.loads(originals["build/output/receipt.json"])
        changed["fit"]["toy_only"] = int("9" * 400)
    else:
        role, embedded = "inference_receipt", "inference_receipt"
        changed = json.loads(originals["infer/output/receipt.json"])
        measurement = changed["measurement"]
        if mutation == "overflowing_timing_total":
            measurement["timing_s"]["preprocess"] = 1e308
            measurement["timing_s"]["inference"] = 1e308
        elif mutation == "fractional_integer_dtype":
            measurement["output_dtype"] = "int8"
        else:
            measurement["output_dtype"] = []
    worker[embedded] = changed
    _graph_retain_mutation(root, manifest_path, role, _json(changed))
    _graph_retain_mutation(root, manifest_path, "worker_evidence", _json(worker))
    with pytest.raises(custody.CustodyRefused, match=cause):
        custody.prepare_custody_v5(root, manifest_path)
    with pytest.raises(entry.EntryRefused, match=f"custody_v5_{cause}"):
        entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    assert not list(entries.iterdir())


@pytest.mark.parametrize("dtype,value", [("float16", 1e-25), ("float32", 1e-100)])
def test_graph_v3_refuses_predictions_below_declared_dtype_range(
    tmp_path, dtype, value
):
    root, manifest_path, originals = _graph_fixture(tmp_path)
    predictions = _json([[[[value]]]])
    inference = json.loads(originals["infer/output/receipt.json"])
    inference["predictions_digest"] = _sha(predictions)
    inference["measurement"]["output_dtype"] = dtype
    worker = json.loads(originals["stage/worker-evidence.json"])
    worker["predictions_digest"] = _sha(predictions)
    worker["predictions_raw_base64"] = base64.b64encode(predictions).decode("ascii")
    worker["inference_receipt"] = inference
    _graph_retain_mutation(root, manifest_path, "predictions", predictions)
    _graph_retain_mutation(root, manifest_path, "inference_receipt", _json(inference))
    _graph_retain_mutation(root, manifest_path, "worker_evidence", _json(worker))
    with pytest.raises(
        custody.CustodyRefused, match="graph_measured_inference_receipt"
    ):
        custody.prepare_custody_v5(root, manifest_path)


def test_graph_v3_entry_refuses_forged_custody_receipt(tmp_path):
    root, manifest_path, _ = _graph_fixture(tmp_path)
    receipt = custody.prepare_custody_v5(root, manifest_path)
    receipt["submission_digest"] = _sha(b"forged-submission")
    receipt_path = tmp_path / "forged-custody.json"
    receipt_path.write_bytes(_json(receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    with pytest.raises(entry.EntryRefused, match="custody_receipt_mismatch"):
        entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    assert not list(entries.iterdir())


@pytest.mark.parametrize("physics,seed", [(True, True), (False, True), (True, False)])
def test_bundle_original_bytes_get_pending_create_only_entry(tmp_path, physics, seed):
    root, manifest_path, originals = _fixture(tmp_path, physics=physics, seed=seed)
    receipt = custody.prepare_custody_v5(root, manifest_path)
    assert receipt["challenge"] == "synthetic-linear-field-2d"
    assert receipt["physics_contract"]["authenticity"] == (
        "DECLARED_UNVERIFIED" if physics else "PENDING"
    )
    if physics:
        contract = json.loads(manifest_path.read_bytes())["physics_contract"]
        assert receipt["physics_contract"]["definition_digest"] == _sha(_json(contract))
    assert receipt["seed_provenance"] == ("DECLARED_UNVERIFIED" if seed else "PENDING")
    assert set(receipt["state_members"]) == {
        "__header__",
        "graph",
        "parameter0000",
        "parameter0001",
        "parameter0002",
    }
    assert receipt["score_state"] == "NOT_COMPUTED"
    assert receipt["fixture_evidence"] == "BYTE_BOUND_UNVERIFIED"
    assert receipt["prediction_evidence"] == "BYTE_BOUND_UNVERIFIED"
    assert receipt["receiver_ack_state"] == "RECEIVER_ACK_PENDING"
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(_json(receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    first = entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    assert first["status"] == "CREATED"
    assert first["entry"]["official_eligible"] is False
    assert (
        entry.create_entry_v5(root, manifest_path, receipt_path, entries)["status"]
        == "ALREADY_PRESENT_IDENTICAL"
    )
    assert {name: (root / name).read_bytes() for name in originals} == originals


@pytest.mark.parametrize(
    "fixture,predictions", [(False, False), (True, False), (False, True)]
)
def test_built_state_is_retained_while_fixture_or_predictions_are_pending(
    tmp_path, fixture, predictions
):
    root, manifest_path, originals = _fixture(
        tmp_path, fixture=fixture, predictions=predictions
    )
    receipt = custody.prepare_custody_v5(root, manifest_path)
    assert receipt["state_digest"] == _sha(originals["build/output/state.npz"])
    assert receipt["fixture_evidence"] == (
        "BYTE_BOUND_UNVERIFIED" if fixture else "PENDING"
    )
    assert receipt["prediction_evidence"] == (
        "BYTE_BOUND_UNVERIFIED" if predictions else "PENDING"
    )
    assert receipt["prediction_digest"] == (
        _sha(originals["infer/output/predictions.json"]) if predictions else None
    )
    assert receipt["score_state"] == "NOT_COMPUTED"
    assert receipt["replay_state"] == "UNAVAILABLE_PENDING_FIXTURE_OR_PREDICTIONS"
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(_json(receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    result = entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    assert result["entry"]["replay_state"] == receipt["replay_state"]
    assert result["entry"]["prediction_evidence"] == receipt["prediction_evidence"]
    assert {name: (root / name).read_bytes() for name in originals} == originals


def test_bundle_custody_refuses_state_and_original_byte_mismatch(tmp_path):
    root, manifest_path, _ = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["retained_files"]["build/output/state.npz"] = _sha(b"wrong")
    manifest_path.write_bytes(_json(manifest))
    with pytest.raises(custody.CustodyRefused, match="graph_retained_digest_or_size"):
        custody.prepare_custody_v5(root, manifest_path)
    manifest["retained_files"]["build/output/state.npz"] = _sha(
        (root / "build/output/state.npz").read_bytes()
    )
    manifest["roles"]["state"]["codec"] = "numeric_npz"
    manifest_path.write_bytes(_json(manifest))
    with pytest.raises(custody.CustodyRefused, match="bundle_role_codec"):
        custody.prepare_custody_v5(root, manifest_path)


def test_bundle_custody_refuses_unlisted_original_and_wrong_receipt(tmp_path):
    root, manifest_path, _ = _fixture(tmp_path)
    (root / "extra.json").write_text("{}")
    with pytest.raises(
        custody.CustodyRefused, match="graph_undeclared_or_missing_file"
    ):
        custody.prepare_custody_v5(root, manifest_path)
    (root / "extra.json").unlink()
    receipt = custody.prepare_custody_v5(root, manifest_path)
    receipt["score_state"] = "SCORED"
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(_json(receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    with pytest.raises(entry.EntryRefused, match="custody_receipt_mismatch"):
        entry.create_entry_v5(root, manifest_path, receipt_path, entries)
    assert not list(entries.iterdir())


def test_bundle_cli_keeps_receipt_and_index_outside_originals(tmp_path):
    root, manifest_path, originals = _fixture(tmp_path, seed=False)
    receipt_path = tmp_path / "receipt.json"
    assert (
        custody.main(
            [
                "prepare-bundle-v5",
                "--roles",
                str(manifest_path),
                "--artifacts",
                str(root),
                "--out",
                str(receipt_path),
            ]
        )
        == 0
    )
    entries = tmp_path / "entries"
    entries.mkdir()
    assert (
        entry.main(
            [
                "--bundle-roles",
                str(manifest_path),
                "--artifacts",
                str(root),
                "--custody-receipt",
                str(receipt_path),
                "--entry-directory",
                str(entries),
            ]
        )
        == 0
    )
    assert len(list(entries.iterdir())) == 1
    assert {name: (root / name).read_bytes() for name in originals} == originals
    with pytest.raises(SystemExit):
        custody.main(
            [
                "prepare-bundle-v5",
                "--roles",
                str(manifest_path),
                "--artifacts",
                str(root),
                "--out",
                str(root / "receipt.json"),
            ]
        )
    inside = root / "entries"
    inside.mkdir()
    with pytest.raises(
        entry.EntryRefused, match="entry_directory_inside_original_artifacts"
    ):
        entry.create_entry_v5(root, manifest_path, receipt_path, inside)
