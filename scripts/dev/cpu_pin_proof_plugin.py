"""A pytest plugin that records the numbers the CPU-dispatch pin must make identical across hosts.

    pytest -p scripts.dev.cpu_pin_proof_plugin tests/cpu/test_cooling_dual_pack.py ...

The file is $CPU_PIN_PROOF_OUT, else .carbon-artifacts/cpu-pin-proof.jsonl in the checkout (git-ignored; delete it first).

It wraps (never edits) two functions the proof tests already call and appends one JSON line per call:

- ``physical_dual_pack.single_threaded`` (the rebuilt baselines of Cooling, Motor and F08): the target, the sha256 of the
  canonical JSON result and every float in it as ``float.hex`` (exact bits);
- ``physical_public_train.derive_encoded_public_train`` (the Cooling 1.3 re-derived TRAIN): the sha256 of the npz bytes.

It also records the host facts (numpy version, the pin variables, the CPU features NumPy reports) on the first line.
Public numbers only; the tests' own assertions are untouched. Compare the files from the Targon VM, runner2 and the
validator: they must be identical line for line (except the ``host`` line's CPU-feature fields).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

_OUT = None


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _hexed(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, list | tuple):
        return [_hexed(item) for item in value]
    if isinstance(value, dict):
        return {key: _hexed(item) for key, item in sorted(value.items())}
    return value


def _write(record) -> None:
    with Path(_OUT).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def pytest_configure(config):
    global _OUT
    # canonical.sh forwards no extra environment, so the default is an ignored file in the checkout.
    _OUT = os.environ.get("CPU_PIN_PROOF_OUT") or str(
        Path(__file__).resolve().parents[2]
        / ".carbon-artifacts"
        / "cpu-pin-proof.jsonl"
    )
    Path(_OUT).parent.mkdir(parents=True, exist_ok=True)
    import numpy as np
    from numpy._core._multiarray_umath import __cpu_dispatch__, __cpu_features__

    _write(
        {
            "kind": "host",
            "numpy": np.__version__,
            "pin": {
                name: os.environ.get(name)
                for name in ("OPENBLAS_CORETYPE", "NPY_DISABLE_CPU_FEATURES")
            },
            "dispatch": list(__cpu_dispatch__),
            "avx512_on": sorted(
                k for k, v in __cpu_features__.items() if v and k.startswith("AVX512")
            ),
        }
    )
    from carbon.challenge_kit import physical_public_train
    from carbon.scoring import physical_dual_pack

    single = physical_dual_pack.single_threaded

    def single_threaded(target, **kwargs):
        result = single(target, **kwargs)
        _write(
            {
                "kind": "baseline",
                "target": target,
                "kwargs_sha256": hashlib.sha256(_canonical(kwargs)).hexdigest(),
                "result_sha256": hashlib.sha256(_canonical(result)).hexdigest(),
                "result_hex": _hexed(result),
            }
        )
        return result

    physical_dual_pack.single_threaded = single_threaded

    derive = physical_public_train.derive_encoded_public_train

    def derive_encoded_public_train(challenge_id):
        raw, provenance = derive(challenge_id)
        _write(
            {
                "kind": "encoded_train",
                "challenge": challenge_id,
                "npz_sha256": hashlib.sha256(raw).hexdigest(),
                "train_sha256": provenance.get("train_sha256"),
            }
        )
        return raw, provenance

    physical_public_train.derive_encoded_public_train = derive_encoded_public_train
