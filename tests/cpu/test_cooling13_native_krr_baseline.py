"""Cooling 1.3's practice baseline is the registered learned-krr-v1, in a
1.3-native bundle (Validator, 2026-10-23).

Cooling 1.3 serves the law-safe output encoding (`cold_plate.output_encoding`),
so the 1.0-1.2 KRR bundle, which takes log(slot 0 - inlet), cannot train on
its TRAIN. The bundle in docs/development/evidence/cooling13-native-krr-baseline-v1
decodes TRAIN, fits the same KRR and returns its outputs encoded again. Its
practice-dual total through `cooling_encoded_dual_pack` must equal the 1.2 KRR's
total through `cooling_dual_pack` on 1.2's TRAIN, before Cooling 1.3 registers a
practice baseline line.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/development/evidence/cooling13-native-krr-baseline-v1"
BUNDLE_DIGEST = (
    "sha256:2c918acd1432b3920fa673e8d0097882ed016eed8d9bd91b23a87415da849d67"
)
RECIPE_DIGEST = (
    "sha256:ffde968a02665765afb346307b9ce1935bde838d67a3c2ace5273521778629d1"
)
#: The totals differ only through slot 0's floor (the law's own tolerance unit,
#: 32 float32 eps relative to the hottest segment mean, `exam._ulp`), which moves
#: a decoded peak by at most ~3.8e-6 relative; the accuracy leg averages it over
#: the bank. Measured: 1.5e-10. Stated bound: 1e-8 absolute on the total.
TOTAL_TOLERANCE = 1e-8


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def test_the_packet_is_the_receipted_bundle():
    bundle = json.loads((PACKET / "bundle.json").read_bytes())
    recipe = json.loads((PACKET / "recipe.json").read_bytes())
    source = (PACKET / "source.tar.gz").read_bytes()
    assert _sha(source) == bundle["source_sha256"]
    assert len(source) == bundle["source_bytes"]
    assert _sha(_canonical(bundle)) == BUNDLE_DIGEST
    assert recipe["source"]["bundle_ref"]["bundle_digest"] == BUNDLE_DIGEST
    assert _sha(_canonical(recipe)) == RECIPE_DIGEST
    assert recipe["challenge"]["id"] == "chip-cold-plate"
    assert recipe["challenge"]["version"] == "1.3"


def _native_build(tmp_path):
    with tarfile.open(
        fileobj=io.BytesIO((PACKET / "source.tar.gz").read_bytes())
    ) as tar:
        (member,) = [
            m for m in tar.getmembers() if m.name.endswith("carbon_candidate/build.py")
        ]
        path = tmp_path / "build.py"
        path.write_bytes(tar.extractfile(member).read())
    spec = importlib.util.spec_from_file_location("cooling13_native_krr_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_its_practice_dual_total_equals_the_1_2_krr_total(tmp_path):
    torch = pytest.importorskip("torch")
    from carbon.challenge_kit import physical_public_train
    from carbon.cold_plate import output_encoding
    from carbon.scoring import (
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        practice_dual,
    )

    native = practice_dual.versioned(cooling_dual_pack, "1.2")
    encoded = practice_dual.versioned(cooling_encoded_dual_pack, "1.3")
    _bank, public, names, rows = practice_dual._rows(native)
    krr_1_2 = cooling_dual_pack._baseline_outputs(
        rows, cooling_dual_pack._train_records(public["train"], names)
    )
    before = practice_dual.from_rows(native, krr_1_2)

    train = physical_public_train.load_public_train("chip-cold-plate")
    model = _native_build(tmp_path).build(
        np.asarray(train["inputs"], float),
        output_encoding.encode_targets(np.asarray(train["targets"], float)),
        seed=0,
        configuration=json.loads((PACKET / "recipe.json").read_bytes())["procedure"][
            "configuration"
        ],
        train_use={"cases": "all"},
    )
    queried = np.asarray(practice_dual.query_inputs(encoded, np.zeros(1)), float)
    outputs = model["apply"](model["parameters"], torch.from_numpy(queried))
    after = practice_dual.from_rows(encoded, outputs.numpy().tolist())

    assert before["available"] and after["available"]
    assert before["gates"] == after["gates"]
    assert before["eligible"] and after["eligible"]
    assert before["design_value"] == after["design_value"]
    assert abs(after["total"] - before["total"]) <= TOTAL_TOLERANCE
