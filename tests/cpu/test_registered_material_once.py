"""Live 116, 19 Nov 2026 (py-spy 18:28Z: 4-7 source-upload threads each re-derived Motor 1.8's public TRAIN and development
bank inside `get_challenge_info`): the registered public material is derived ONCE per process per (Challenge, version,
family) (`research_service._registered_once`, single-flight per key); every call still checks the served material
against it as before. Fixture derivations only.
"""

from __future__ import annotations

import threading
import time

import pytest

from carbon.development_session import research_service as rs


@pytest.fixture(autouse=True)
def clean():
    saved = dict(rs._REGISTERED)
    rs._REGISTERED.clear()
    yield
    rs._REGISTERED.clear()
    rs._REGISTERED.update(saved)


def test_many_concurrent_calls_derive_the_material_once():
    calls = []

    def derive():
        calls.append(1)
        time.sleep(0.2)  # the CPU-bound public TRAIN + bank derivation
        return {"challenge_key": "k", "train": b"t"}

    key = ("electric-motor-magnetics", "1.8", False, False, True)
    out = []
    threads = [
        threading.Thread(target=lambda: out.append(rs._registered_once(key, derive)))
        for _ in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert len(calls) == 1 and len(out) == 20 and all(o == out[0] for o in out)
    assert rs._registered_once(key, derive) == out[0] and len(calls) == 1


def test_each_version_and_family_is_its_own_entry_and_a_failure_is_not_kept():
    a = rs._registered_once(("c", "1.8", False, False, True), lambda: {"v": "1.8"})
    b = rs._registered_once(("c", "1.9", False, False, True), lambda: {"v": "1.9"})
    assert a == {"v": "1.8"} and b == {"v": "1.9"}

    def broken():
        raise ValueError("derivation failed")

    with pytest.raises(ValueError):
        rs._registered_once(("c", "2.0", False, False, True), broken)
    assert rs._registered_once(
        ("c", "2.0", False, False, True), lambda: {"v": "2.0"}
    ) == {"v": "2.0"}


def test_mutating_a_returned_value_never_changes_the_next_calls_check():
    """V2 on 5a226278: each caller gets its own copy of the cached material, nested values and arrays included."""
    import numpy as np

    key = ("electric-motor-magnetics", "1.8", False, False, True)

    def derive():
        return {
            "construction_kit": {"id": "m", "nested": [1, 2]},
            "example": np.zeros(3),
            "train": b"t",
        }

    first = rs._registered_once(key, derive)
    first["construction_kit"]["id"] = "changed"
    first["construction_kit"]["nested"].append(3)
    first["example"][0] = 9.0
    first["train"] = b"other"
    again = rs._registered_once(key, derive)
    assert again["construction_kit"] == {"id": "m", "nested": [1, 2]}
    assert np.array_equal(again["example"], np.zeros(3)) and again["train"] == b"t"
