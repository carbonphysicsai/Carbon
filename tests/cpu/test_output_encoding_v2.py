"""DRAFT tests for carbon/cold_plate/output_encoding_v2.py (intended path
tests/cpu/test_output_encoding_v2.py). Written, not run. Fixtures are synthetic,
non-production values."""

import numpy as np
import pytest

from carbon.cold_plate import output_encoding as v1
from carbon.cold_plate import output_encoding_v2 as v2
from carbon.cold_plate.domain import FIXED


def _natives(n=8, seed=0):
    rng = np.random.default_rng(seed)
    profile = 50.0 + np.cumsum(rng.uniform(0.1, 1.0, (n, 30)), axis=1)
    peak = profile.max(axis=1) + rng.uniform(0.5, 3.0, n)
    pressure = rng.uniform(100.0, 5000.0, n)
    outlet = rng.uniform(30.0, 60.0, n)
    peak_x = rng.uniform(0.5, FIXED["footprint_mm"] - 0.5, n)
    return np.column_stack([peak, profile, pressure, outlet, peak_x])


def test_encoding_names_and_v1_untouched():
    assert v2.ENCODING == "carbon.cold-plate.law-safe-output-encoding.v2"
    assert v1.ENCODING == "carbon.cold-plate.law-safe-output-encoding.v1"
    assert v2.WIDTH == 34


def test_round_trip():
    native = _natives()
    encoded = v2.encode_targets(native)
    assert encoded.shape == (len(native), 34)
    for row, want in zip(encoded, native):
        np.testing.assert_allclose(v2.decode_flat(row), want, rtol=1e-9, atol=1e-9)


def test_first_32_slots_are_v1_bytes():
    native = _natives()
    encoded = v2.encode_targets(native)
    np.testing.assert_array_equal(encoded[:, :32], v1.encode_targets(native[:, :32]))


def test_v1_decode_of_first_32_equals_v2_first_four_outputs():
    encoded = v2.encode_targets(_natives())
    for row in encoded:
        old = v1.decode_row(row[:32])
        new = v2.decode_row(row)
        assert old["peak_c"] == new["peak_c"]
        assert old["profile_c"] == new["profile_c"]
        assert old["pressure_drop_pa"] == new["pressure_drop_pa"]
        assert v1.decode_flat(row[:32]) == v2.decode_flat(row)[:32]


def test_laws_hold_for_any_raw_row():
    rng = np.random.default_rng(1)
    for _ in range(200):
        raw = rng.normal(0.0, 50.0, 34)
        out = v2.decode_row(raw)
        assert out["peak_c"] >= max(out["profile_c"])
        assert out["pressure_drop_pa"] >= 0.0
        assert 0.0 <= out["peak_x_mm"] <= FIXED["footprint_mm"]


def test_peak_x_is_strictly_inside_for_moderate_slots():
    for z in (-30.0, -1.0, 0.0, 1.0, 30.0):
        row = np.zeros(34)
        row[33] = z
        assert 0.0 < v2.decode_row(row)["peak_x_mm"] < FIXED["footprint_mm"]


def test_outlet_slot_is_plain():
    row = np.zeros(34)
    for value in (-5.0, 0.0, 41.5):
        row[32] = value
        assert v2.decode_row(row)["outlet_c"] == value


@pytest.mark.parametrize("bad", [0.0, FIXED["footprint_mm"], -1.0, 31.0])
def test_peak_x_outside_open_footprint_refused(bad):
    native = _natives(1)
    native[0, 33] = bad
    with pytest.raises(ValueError):
        v2.encode_targets(native)


def test_shape_and_finite_validation():
    with pytest.raises(ValueError):
        v2.encode_targets(_natives()[:, :32])
    with pytest.raises(ValueError):
        v2.decode_row(np.zeros(32))
    bad = _natives(1)
    bad[0, 32] = np.nan
    with pytest.raises(ValueError):
        v2.encode_targets(bad)


def test_v1_laws_still_refused_through_v2_encode():
    native = _natives(1)
    native[0, 31] = -1.0
    with pytest.raises(ValueError):
        v2.encode_targets(native)


# -- review 19 Nov: fail-closed token lookup -------------------------------------------------------


def test_token_lookup_is_exact_and_fails_closed():
    assert v2.encoding_for_token(v2.TOKEN_V1) is v1
    assert v2.encoding_for_token(v2.TOKEN_V2) is v2
    assert v2.width_for_token(v2.TOKEN_V1) == 32
    assert v2.width_for_token(v2.TOKEN_V2) == 34
    for bad in (
        None,
        "",
        "cooling-law-safe-output-encoding-v3",
        "anything",
        1,
        True,
        b"x",
    ):
        with pytest.raises(ValueError):
            v2.encoding_for_token(bad)
        with pytest.raises(ValueError):
            v2.width_for_token(bad)


def test_registry_v1_token_matches_the_literal_here():
    from carbon.challenge_kit import version_registry

    assert version_registry.COOLING_LAW_SAFE == v2.TOKEN_V1


# -- review 19 Nov: decode-side refusal -----------------------------------------------------------


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_decode_refuses_non_finite_new_slots(bad):
    for slot in (32, 33):
        row = np.zeros(34)
        row[slot] = bad
        with pytest.raises(ValueError):
            v2.decode_row(row)


def test_decode_peak_x_always_inside_closed_footprint_or_refused():
    for z in (-1e6, -800.0, 0.0, 800.0, 1e6):
        row = np.zeros(34)
        row[33] = z
        out = v2.decode_row(row)["peak_x_mm"]
        assert 0.0 <= out <= FIXED["footprint_mm"]


# -- review 19 Nov BLOCKING: no existing producer file may move ------------------------------------
# A producer digest hashes the BYTES of its FILES (physical_dual_pack.producer_digest, CRLF read as LF), so any
# edit to a listed file re-pins every version that lists it. Pinned at ref mcexam-c/cool18-on-main (5d35751b9e);
# every Cooling and F08 producer file, shared files included. Run from the repo root of the candidate tree.

PRODUCER_SHA256 = {
    "physical_dual_pack.py": "92fdc8966118816a03d28258c72ad9b8e6b8a74ea0ed2bfa1636f198cfb48660",
    "private_evaluation_source.py": "8a067f5a298281ee68726c64dfacfcddaba5d3d65918fab9576d01f538a4530a",
    "inference_pair_evidence.py": "2bda24782fd87512c8a4e3a287f5c0ee6fb75e0f2a3f17ed4a39c5cd55dc94ba",
    "sealed_batch_source.py": "438aae83e7d0231e1feeecec1e8c4248d23899164e722e1e01450228a862ec3f",
    "copy_package.py": "4f1a4fb47b0bcc0a0ed966a8f42178167e3d3ab8e362672021b1ff00b9e02d4e",
    "copy_derivation.py": "af634b29cb6fbb8508a893c2e2b28ded8b4b9d5d7d5561713081413d3589e7ef",
    "cooling_dual_pack.py": "9e4eef3caeee8e34b9dcc691756492667ba34a4f2e197574c57c47e8d82b5002",
    "cooling_dual_measurement.py": "3c8a031f611744b1b7b7c4de0ff603943a1b4a1662090cb474d9ef63bdb8d325",
    "critical_fidelity.py": "4a04f7ac3683e19f71bc6aba31b7aab882cc5d37714c5a667badf86fce159f25",
    "design_fidelity.py": "d7915c4b3ece4e2c917c99d0d1343abf35b290c41d4d2b8bba3fa45eac8dfd14",
    "physics_half.py": "9974953199e68767c70747e5f159d472595c6db51b63507836b52b43a24c4e6d",
    "probe_design.py": "10d81ba6b485030923ce1486b761b1b7f8ecaa3a0d87ac76273ebdc87cb1a2c0",
    "cooling_physics.py": "24dea8c100d68b2b907ca167cfe456dbc945de0edd3ba943470de1f2dec9ad82",
    "cooling_encoded_dual_pack.py": "b5e87c3b1a89893ae8e58c103655ba2196e5c006ccd9a13d17261b37e8523fc4",
    "cooling_hotspot_dual_pack.py": "bc8d8c9d78bbed58c8295e43177d9a71313f3815cf2cd7f4fa90c578b8153478",
    "cooling_pool_baseline_dual_pack.py": "ecec59067bc3d5acffe3efffcb876a481d599594bdc30159cd5fafdfc54b852a",
    "physical_adapters.py": "e263d48a65e0b78ff940a92cb8b8d140d65b5dfd7d777b7fdd0c5566d316378e",
    "f08_dual_pack.py": "5a1238e81d28df0ee65743a548de253101d3bfa17214f5aea65474f4e5d5139c",
    "f08_dual_measurement.py": "3ff418455214944c0a9210a23f7e9e12583f2b4332a95a546f843c85581f5fcf",
    "sealed_grid_common.py": "2467b37fe5115fc9f8319dcab7224b708b282aa49acb86fedc148dc635dbb79d",
    "sealed_pack_writer.py": "21c36523707928031e39fa9278db71bd25a433afc88bb8b2d6f0f2dca9dd6cea",
    "f08_critical.py": "85eb3c7edf030f5facca83d493070daba60b32a6a3d34ba6e031581f49f7e562",
    "f08_physics.py": "05e0dba253d28340cf5fbb4d52c45e53715ac4669185275a356e5ebeda01704f",
    "f08_sealed_dual_pack.py": "5f19c9145f28cd02749882271f5931f8f05ece53a157414258bc673d5bb0f72a",
    "f08_sanity_dual_pack.py": "e20cea6812e234b03288af200813a9473286d95d9edc94b80afaee042377c204",
    "pool_adapters.py": "dae8469be734d7ee866a5b17b8a5794e839b108edcc32a30baf9ac1fd9def004",
    "cooling18_dual_pack.py": "2bb46a0d5262725febec26280a7e50012b43acc6bd2dfec8c98b19dc6a2f8f52",
}
# (cooling_region.py 53c2ef7c..., not a producer FILE; pinned only as informational, touchpoint row 22.)


def _scoring_dir():
    import pathlib

    from carbon import scoring

    return pathlib.Path(scoring.__file__).parent


def _producer_files_from_imports():
    """The file list is BUILT by importing each producer FILES tuple (never hand-typed): the Cooling chain
    (cooling_dual_pack, encoded, hotspot, pool baseline, 1.8), the F08 chain (f08_dual_pack, sealed, sanity: its
    FILES include pool_adapters.py) and the shared physical list."""
    from carbon.scoring import (
        cooling18_dual_pack,
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        cooling_hotspot_dual_pack,
        cooling_pool_baseline_dual_pack,
        f08_dual_pack,
        f08_sanity_dual_pack,
        f08_sealed_dual_pack,
        physical_dual_pack,
    )

    names = set(physical_dual_pack._SHARED_FILES)
    for adapter in (
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        cooling_hotspot_dual_pack,
        cooling_pool_baseline_dual_pack,
        cooling18_dual_pack,
        f08_dual_pack,
        f08_sealed_dual_pack,
        f08_sanity_dual_pack,
    ):
        names |= set(adapter.FILES)
    return sorted(names)


def test_every_existing_cooling_and_f08_producer_file_is_byte_unchanged():
    import hashlib

    base = _scoring_dir()
    built = _producer_files_from_imports()
    # the built list and the pinned digests name the same paths (a new FILES entry without a pin fails)
    assert set(built) == set(PRODUCER_SHA256), set(built) ^ set(PRODUCER_SHA256)
    for name in built:
        raw = (base / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(raw).hexdigest() == PRODUCER_SHA256[name], name


def test_new_v2_pack_does_not_enter_any_existing_files_tuple():
    from carbon.scoring import cooling18_dual_pack, cooling18_v2_dual_pack

    assert "cooling18_v2_dual_pack.py" not in cooling18_dual_pack.FILES
    assert cooling18_v2_dual_pack.FILES[-1] == "cooling18_v2_dual_pack.py"
    assert set(cooling18_v2_dual_pack.FILES) - {"cooling18_v2_dual_pack.py"} <= set(
        PRODUCER_SHA256
    )


def test_v2_pack_refuses_human_input_values():
    from carbon.scoring import cooling18_v2_dual_pack as pack

    with pytest.raises(pack.V2Refused):
        pack.raw_u()
    with pytest.raises(pack.V2Refused):
        pack.measure()
    with pytest.raises(pack.V2Refused):
        pack.derive("1.7")


def test_arm_refuses_bad_tokens_through_the_single_resolver(monkeypatch):
    from carbon.challenge_kit import version_registry

    class _Entry:
        output_encoding = None

    monkeypatch.setattr(version_registry, "entry", lambda *_a: _Entry)
    for bad in (None, "mistyped", v2.TOKEN_V1):
        _Entry.output_encoding = bad
        with pytest.raises(ValueError):
            v2.arm()
    _Entry.output_encoding = v2.TOKEN_V2
    assert v2.arm() is v2


def test_v2_pack_has_no_token_string_compare():
    import inspect

    from carbon.scoring import cooling18_v2_dual_pack as pack

    assert "ENCODING_TOKEN" not in inspect.getsource(pack)
    assert "arm(" in inspect.getsource(pack._require_v2_token)


def test_region_bound_registered_for_18_and_derives_34_wide(monkeypatch):
    from carbon.challenge_kit import version_registry
    from carbon.scoring import cooling18_v2_dual_pack as pack
    from carbon.scoring import pool_version

    class _Entry:  # the 1.8 entry as the overlay arms it: it carries the v2 token
        output_encoding = v2.TOKEN_V2

    monkeypatch.setattr(version_registry, "entry", lambda *_a: _Entry)
    saved = dict(pool_version._REGION_BOUNDS)
    saved_bindings = dict(pool_version._BINDINGS)
    try:
        pool_version._REGION_BOUNDS.clear()
        pack.dispatch({})
        assert pool_version._REGION_BOUNDS[("cooling", "1.8")] is pack.bounded_binding
        pack.dispatch({})  # same fn again: no-op
        with pytest.raises(ValueError):
            pool_version.register_region_bound("cooling", "1.8", lambda b, r: b)
        # with a region, the registered 1.8 bound is the one applied and it derives a 34-wide row
        # (synthetic non-production region document and inputs: shape per cooling_region.bounds / check_inputs)
        import dataclasses

        from carbon.scoring import cooling_region

        marker = {}

        def fake_bounds(_document):
            marker["called"] = True
            from carbon.cold_plate import domain

            return dict(domain.INPUT_BOUNDS)

        monkeypatch.setattr(cooling_region, "bounds", fake_bounds)

        @dataclasses.dataclass
        class _B:
            version: str = "1.8"
            derive: object = None

        bound = pool_version._REGION_BOUNDS[("cooling", "1.8")](_B(), object())
        assert marker["called"]
        from carbon.cold_plate import domain

        row = [0.0] * 34
        # rev 7: a FULL synthetic in-bound case (domain.NOMINAL, inlet_c 40.0). The 34 zeros decode to a 0.0 C
        # profile, below inlet_c, so face_above_inlet FAILS and the row derives None (not an exception) at width 34;
        # width 32 is refused on width. An empty case is not passed: exam.gates reads case["inlet_c"] and the
        # 32-wide mirror (cooling_region.bounded_derive) raises KeyError on it the same way.
        case = dict(domain.NOMINAL)
        assert bound.derive(case, row) is None
        assert bound.derive(case, row[:32]) is None
    finally:
        pool_version._REGION_BOUNDS.clear()
        pool_version._REGION_BOUNDS.update(saved)
        pool_version._BINDINGS.clear()
        pool_version._BINDINGS.update(saved_bindings)
