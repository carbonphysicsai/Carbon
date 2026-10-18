"""Native build proof and registered TRAIN bytes stay evidence, not physics acceptance."""

import json
from pathlib import Path

import pytest
from test_public_bundle_model_custody import _fixture, _json, _sha

from scripts.dev.score_lab import public_unbound_custody as custody
from scripts.dev.score_lab import public_unbound_entry as entry


def _native_fixture(tmp_path, *, values=None, dtype="float32", shape=None):
    root, path, originals = _fixture(tmp_path)
    manifest = json.loads(path.read_bytes())
    native_name = "build/output/native-predictions.json"
    native = _json([[[[0.25]]]] if values is None else values)
    (root / native_name).write_bytes(native)
    manifest["roles"]["native_predictions"] = {"file": native_name, "codec": "json"}
    manifest["retained_files"][native_name] = _sha(native)
    build_name = manifest["roles"]["build_receipt"]["file"]
    build = json.loads(originals[build_name])
    build.update(
        schema="carbon.development.bundle-build.v2",
        example_digest=_sha(originals["stage/example.npz"]),
        native_predictions_digest=_sha(native),
        native_dtype=dtype,
        native_shape=[1, 1, 1, 1] if shape is None else shape,
    )
    _write_build(root, path, manifest, build)
    return root, path, manifest, build


def _write_build(root, path, manifest, build):
    name = manifest["roles"]["build_receipt"]["file"]
    raw = _json(build)
    (root / name).write_bytes(raw)
    manifest["retained_files"][name] = _sha(raw)
    path.write_bytes(_json(manifest))


def test_build_v2_retains_native_predictions_without_fidelity_or_score_claim(tmp_path):
    root, path, manifest, build = _native_fixture(tmp_path)
    receipt = custody.prepare_custody_v5(root, path)
    assert receipt["roles"]["native_predictions"] == {
        **manifest["roles"]["native_predictions"],
        "sha256": build["native_predictions_digest"],
    }
    assert receipt["custody_state"] == "PUBLIC_BYTES_REHASHED"
    assert receipt["score_state"] == "NOT_COMPUTED"
    assert receipt["official_eligible"] is False
    saved = tmp_path / "custody.json"
    saved.write_bytes(_json(receipt))
    records = tmp_path / "entries"
    records.mkdir()
    retained = entry.create_entry_v5(root, path, saved, records)["entry"]
    assert (
        retained["roles"]["native_predictions"]
        == receipt["roles"]["native_predictions"]
    )
    assert retained["score_state"] == "NOT_COMPUTED"


def test_legacy_build_has_no_new_role_or_native_requirement(tmp_path):
    root, path, _ = _fixture(tmp_path)
    receipt = custody.prepare_custody_v5(root, path)
    assert "native_predictions" not in receipt["roles"]
    assert receipt["source_schema"] == custody.BUNDLE_STATE_SCHEMA


@pytest.mark.parametrize(
    "field", ["example_digest", "native_predictions_digest", "allowlist_digest"]
)
def test_native_build_requires_exact_retained_probe_prediction_and_allowlist(
    tmp_path, field
):
    root, path, manifest, build = _native_fixture(tmp_path)
    build[field] = _sha(b"wrong original")
    _write_build(root, path, manifest, build)
    with pytest.raises(custody.CustodyRefused):
        custody.prepare_custody_v5(root, path)


def test_v2_requires_native_role_and_v1_cannot_claim_unbound_native_role(tmp_path):
    root, path, manifest, build = _native_fixture(tmp_path)
    role = manifest["roles"].pop("native_predictions")
    path.write_bytes(_json(manifest))
    with pytest.raises(custody.CustodyRefused, match="bundle_native_build_receipt"):
        custody.prepare_custody_v5(root, path)
    manifest["roles"]["native_predictions"] = role
    build["schema"] = "carbon.development.bundle-build.v1"
    _write_build(root, path, manifest, build)
    with pytest.raises(
        custody.CustodyRefused, match="native_predictions_require_build_v2"
    ):
        custody.prepare_custody_v5(root, path)


@pytest.mark.parametrize(
    ("values", "dtype", "shape"),
    [
        ([[True]], "float32", [1, 1]),
        ([[256]], "uint8", [1, 1]),
        ([[1]], "complex64", [1, 1]),
        ([[0.25]], "float32", [1, 2]),
        ([[0.25]], "float32", [True, 1]),
        ([[0.25]], "float32", [1] * 17),
        ([[0.25]], "float64", [1, 16 * 1024 * 1024]),
    ],
)
def test_native_numeric_contract_refuses_invalid_values_and_bounds(
    tmp_path, values, dtype, shape
):
    root, path, _, _ = _native_fixture(
        tmp_path, values=values, dtype=dtype, shape=shape
    )
    with pytest.raises(custody.CustodyRefused):
        custody.prepare_custody_v5(root, path)


def test_one_million_comparison_limit_does_not_reject_valid_native_artifact(tmp_path):
    count = 1_000_001
    root, path, _, _ = _native_fixture(
        tmp_path, values=[[0] * count], dtype="uint8", shape=[1, count]
    )
    assert (
        custody.prepare_custody_v5(root, path)["custody_state"]
        == "PUBLIC_BYTES_REHASHED"
    )


def test_battery_raw_train_reuses_exact_registered_public_gzip_decoder():
    from carbon.battery import challenge

    raw = (Path(__file__).resolve().parents[2] / challenge.TRAIN_V1_PATH).read_bytes()
    binding = {
        "id": challenge.CHALLENGE.challenge_id,
        "version": challenge.CHALLENGE.version,
        "train_digest": "sha256:" + challenge.TRAIN_V1_SHA256,
    }
    arrays = custody._inspect_retained_train(raw, "raw_bytes", binding)
    assert arrays == {
        "inputs": {"shape": [400, 4], "dtype": "float64"},
        "targets": {"shape": [400, 247], "dtype": "float64"},
    }
    with pytest.raises(custody.CustodyRefused, match="battery_train_identity"):
        custody._inspect_retained_train(raw + b"changed", "raw_bytes", binding)
    with pytest.raises(custody.CustodyRefused, match="battery_train_identity"):
        custody._inspect_retained_train(
            raw, "raw_bytes", {**binding, "version": "wrong"}
        )
    with pytest.raises(custody.CustodyRefused, match="battery_train_identity"):
        custody._inspect_retained_train(
            raw, "raw_bytes", {**binding, "id": "synthetic"}
        )


def test_raw_train_exception_does_not_widen_other_role_codecs():
    assert custody._train_codec_matches("train", "raw_bytes", "numeric_npz")
    assert not custody._train_codec_matches("inputs", "raw_bytes", "numeric_npz")
    assert not custody._train_codec_matches("train", "untrusted_pickle", "numeric_npz")
