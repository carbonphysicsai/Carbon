"""CPU-only C-02 plan mapping, provenance, and optional-import tests."""

from __future__ import annotations

import gc
import importlib
import json
import sys
from pathlib import Path

import pytest
from c02_fixtures import compile_c02_plan

from carbon.reconstruction import ReconstructionFailure, compile_development_profile
from carbon.reconstruction.profile import UPSTREAM_WHEEL_DIGEST


@pytest.mark.parametrize(
    ("selector", "kind"), (("fno", "fno1d"), ("deeponet", "deeponet1d"))
)
def test_compiler_plan_maps_two_real_families_exactly(
    tmp_path: Path, selector: str, kind: str
) -> None:
    profile = compile_development_profile(compile_c02_plan(tmp_path, backbone=selector))

    assert profile.backbone_kind == kind
    assert profile.profile_version == "2.0"
    assert '"steps":2' in profile.train_config_json
    assert '"seed":0' in profile.train_config_json
    assert "runtime DerivedSeed bytes" in profile.mapping_receipt_json


def test_non_plan_input_fails_closed() -> None:
    with pytest.raises(ReconstructionFailure) as caught:
        compile_development_profile(object())  # type: ignore[arg-type]

    assert caught.value.code == "reconstruction.plan.type_invalid"


@pytest.mark.parametrize(
    ("overrides", "code"),
    (
        (
            {"wheel_digest": "sha256:" + "0" * 64},
            "reconstruction.backbone.digest_mismatch",
        ),
        (
            {"environment_digest": "sha256:" + "0" * 64},
            "reconstruction.environment.pin_mismatch",
        ),
    ),
)
def test_verified_plan_with_wrong_exact_pin_fails_closed(
    tmp_path: Path, overrides: dict[str, str], code: str
) -> None:
    plan = compile_c02_plan(tmp_path, **overrides)

    with pytest.raises(ReconstructionFailure) as caught:
        compile_development_profile(plan)

    assert caught.value.code == code


def test_public_reconstruction_import_is_jax_and_numpy_free() -> None:
    for name in tuple(sys.modules):
        if name == "carbon.reconstruction" or name.startswith("carbon.reconstruction."):
            sys.modules.pop(name)
    before = set(sys.modules)

    importlib.import_module("carbon.reconstruction")

    loaded = set(sys.modules) - before
    assert not any(name == "jax" or name.startswith("jax.") for name in loaded)
    assert not any(name == "numpy" or name.startswith("numpy.") for name in loaded)


def test_vendored_provenance_and_notices_are_present() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "carbon/reconstruction/_vendor/carbon_jax_lab"
    )
    notice = (root / "licenses/NOTICE.md").read_text(encoding="utf-8")
    transolver = (root / "licenses/third_party/TRANSOLVER_LICENSE.txt").read_text(
        encoding="utf-8"
    )
    neuraloperator = (
        root / "licenses/third_party/NEURALOPERATOR_LICENSE.txt"
    ).read_text(encoding="utf-8")
    source = json.loads(
        (root / "licenses/third_party/TRANSOLVER_SOURCE.json").read_text(
            encoding="utf-8"
        )
    )

    assert UPSTREAM_WHEEL_DIGEST.endswith(
        "3941af49fb7441b9ee37408db2b759bdc65088f0bda089f2a774adc3506935db"
    )
    assert "Transolver" in notice
    assert "MIT License" in transolver
    assert "MIT License" in neuraloperator
    assert source["revision"] == "75e0f67643806a81cd1d3f6adc88dd8c02416fe7"
    assert (
        source["source_sha256"]
        == "f7feffd40e21863a2bd5809d9548a3417a7221a817f9e675ea969712c1d45a36"
    )
    assert (
        source["license_sha256"]
        == "2c919cd03fa823bf7eefc00a957ff8324c865cd22aa5285e563dc4b558084f25"
    )


def test_equal_verified_plans_keep_independent_identity_lifetimes(
    tmp_path: Path,
) -> None:
    first = compile_c02_plan(tmp_path / "first", backbone="fno")
    second = compile_c02_plan(tmp_path / "second", backbone="fno")
    expected = second.to_ref()
    del first
    gc.collect()

    assert second.to_ref() == expected
