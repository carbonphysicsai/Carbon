"""Trusted codecs preserve original TRAIN and work in the staged worker closure."""

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import challenge, construction_kit, construction_material
from carbon.challenge_kit import synthetic_linear_field_2d as fixture
from carbon.development_session import construction_tensor_codec as codec

ROOT = Path(__file__).resolve().parents[2]


def _binding(kit):
    return {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        **{
            name: kit[name]
            for name in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        },
    }


def _digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _npz(**arrays):
    out = io.BytesIO()
    np.savez(out, **arrays)
    return out.getvalue()


def test_battery_original_gzip_reaches_existing_raw_float64_codec():
    raw = (ROOT / challenge.TRAIN_V1_PATH).read_bytes()
    binding = _binding(construction_kit.construction_kit())
    x, y = codec.train_tensors(raw, binding)
    expected_x, expected_y = construction_material.train_tensors(raw)
    np.testing.assert_array_equal(x, expected_x)
    np.testing.assert_array_equal(y, expected_y)
    assert x.dtype == y.dtype == np.dtype("float64")
    assert codec.requires_x64(x, y)
    assert _digest(raw) == binding["train_digest"]
    # A derived NPZ is data, never a replacement for the registered gzip pin.
    with pytest.raises(codec.TensorCodecError, match="bytes differ"):
        codec.train_tensors(_npz(inputs=x, targets=y), binding)


def test_existing_numeric_fixture_keeps_npz_values_dtypes_and_identity():
    material = fixture.bundle_material_v5()
    raw = material["train"]
    binding = _binding(material["construction_kit"])
    x, y = codec.train_tensors(raw, binding)
    with np.load(io.BytesIO(raw), allow_pickle=False) as expected:
        np.testing.assert_array_equal(x, expected["inputs"])
        np.testing.assert_array_equal(y, expected["targets"])
    assert x.dtype == y.dtype == np.dtype("float32")
    assert not codec.requires_x64(x, y)
    assert _digest(raw) == binding["train_digest"]


def test_codec_choice_uses_checked_binding_not_recipe_configuration():
    raw = (ROOT / challenge.TRAIN_V1_PATH).read_bytes()
    binding = _binding(construction_kit.construction_kit())
    with pytest.raises(codec.TensorCodecError, match="binding required"):
        codec.train_tensors(raw, {**binding, "codec": "npz"})
    with pytest.raises(codec.TensorCodecError, match="Battery TRAIN binding differs"):
        codec.train_tensors(raw, {**binding, "challenge_version": "unregistered"})
    # Every served Battery construction version serves TRAIN v1 and decodes it
    # (Test Lead's B22b: a 2.2 build died here when only 1.0 was accepted).
    from carbon.battery import construction_bundle_material

    assert codec._BATTERY_VERSIONS == construction_bundle_material.VERSIONS
    expected = codec.train_tensors(raw, binding)
    for version in construction_bundle_material.VERSIONS:
        decoded = codec.train_tensors(raw, {**binding, "challenge_version": version})
        assert all(np.array_equal(a, b) for a, b in zip(decoded, expected, strict=True))


def test_example_and_inference_codec_accept_only_exact_input_bytes():
    x = np.arange(8, dtype=np.float64).reshape(2, 4)
    raw = _npz(inputs=x)
    np.testing.assert_array_equal(codec.input_tensor(raw, _digest(raw)), x)
    assert codec.requires_x64("float64", np.dtype("int32"))
    assert not codec.requires_x64("float32", "complex64")
    for bad in (_npz(inputs=x, targets=x), _npz(inputs=np.asarray([[np.nan]]))):
        with pytest.raises(codec.TensorCodecError):
            codec.input_tensor(bad, _digest(bad))
    with pytest.raises(codec.TensorCodecError, match="bytes differ"):
        codec.input_tensor(raw, _digest(b"different"))


def test_explicit_module_closure_decodes_battery_without_checkout_imports(tmp_path):
    binding = _binding(construction_kit.construction_kit())
    files = codec.worker_module_files(binding)
    assert "carbon.registry.__init__.py" in files
    assert "carbon.battery.construction_material.py" in files
    assert all(name.endswith(".py") for name in files)
    for name, raw in files.items():
        module = name.removesuffix(".py")
        target = tmp_path.joinpath(*module.split(".")).with_suffix(".py")
        target.parent.mkdir(parents=True, exist_ok=True)
        parent = target.parent
        while parent != tmp_path:
            init = parent / "__init__.py"
            if not init.exists():
                init.write_text("")
            parent = parent.parent
        target.write_bytes(raw)
        assert raw == (ROOT / (module.replace(".", "/") + ".py")).read_bytes()
    raw_train = (ROOT / challenge.TRAIN_V1_PATH).read_bytes()
    (tmp_path / "train.gz").write_bytes(raw_train)
    (tmp_path / "binding.json").write_text(json.dumps(binding))
    script = """
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from carbon.development_session import construction_tensor_codec as codec
root=Path(sys.argv[1])
x,y=codec.train_tensors((root/'train.gz').read_bytes(),json.loads((root/'binding.json').read_bytes()))
assert x.shape==(400,4) and y.shape==(400,247)
assert str(x.dtype)==str(y.dtype)=='float64'
assert codec.requires_x64(x,y)
print('BATTERY_CODEC_CLOSURE_OK')
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script, str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "BATTERY_CODEC_CLOSURE_OK"


def test_inference_stage_omits_battery_training_module_closure():
    binding = _binding(construction_kit.construction_kit())
    files = codec.worker_module_files(binding, training=False)
    assert "carbon.development_session.construction_tensor_codec.py" in files
    assert not any(name.startswith("carbon.battery.") for name in files)
    assert "carbon.reconstruction.capability_registry.py" not in files
