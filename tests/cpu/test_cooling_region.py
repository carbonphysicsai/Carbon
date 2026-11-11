"""B5: Cooling's official derive inside the SIGNED extended region (Carbon Validator-B 11 Nov, W1-W5).

Claims:
- W4 an in-box row derives BYTE-EQUAL to today's official derive; a row inside the region but past the TRAIN box derives
  finite and EQUAL to the receipted widen() derive (`pfr_cool_prep.widen`: INPUT_BOUNDS.update(region["extended"]))
  on the same row; a row past the region derives None;
- W2 every law gate stays (a gate-failing answer derives None inside the region too);
- W1 the grade never writes the process-wide INPUT_BOUNDS; the region is the sealed document whose canonical sha256 the
  registration names (a region not registered, a registered one missing, or another document refuses);
- W3 only a version registering ``physics.region_sha256`` gets it (Cooling 1.8, HUMAN_INPUT until the seal); every other
  version's binding is the one it had (1.7 unchanged);
- the copied steps' sources (domain.check_inputs, exam.die_peak_c, exam.feasibility, customer_decision.quantities,
  pool_adapters._cooling) are pinned by sha: a change there is a change to re-check here.

Every region, case and output row is SYNTHETIC (no drawn input, no signed bound).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import random

import numpy as np
import pytest

# registers the overlay versions (Cooling 1.8 among them) before any binding is built
import carbon.challenge_kit.version_registry  # noqa: F401
from carbon.cold_plate import customer_decision, domain, exam, output_encoding
from carbon.scoring import cooling_region, pool_adapters, pool_exam, pool_version

PINNED_SOURCES = {
    "domain.check_inputs": (
        domain.check_inputs,
        "3db92549bbc1f571cb2110a2a09238dd01af5dc076983689f1abf0cf40ee18e2",
    ),
    "exam.die_peak_c": (
        exam.die_peak_c,
        "8904179857c12d7af1e887b09d84e6e45d7c1f1b9ae563e2e915786e2cbeae74",
    ),
    "exam.feasibility": (
        exam.feasibility,
        "7e15353852621fd967bcd9b7449397a75c9c702a485cc814abc95e86fc6c0437",
    ),
    "customer_decision.quantities": (
        customer_decision.quantities,
        "6704ba4cfcba2636e46ba2a50b13fd866f2a441c402f9e7f2308076e2a263ddb",
    ),
    "pool_adapters._cooling": (
        pool_adapters._cooling,
        "9b3da0e70bda8af642f5dd14ab0a09881d3a6bf60c807f36ba757732bba73693",
    ),
}

TRAIN = dict(domain.INPUT_BOUNDS)
#: A SYNTHETIC region: three inputs extended past the TRAIN box, the others as TRAIN.
EXTENDED = {
    "flow_lpm_per_kw": [1.0, 2.5],
    "heat_load_w": [400.0, 2000.0],
    "inlet_c": [25.0, 50.0],
}
REGION = {
    "challenge": "chip-cold-plate",
    "base": {k: list(v) for k, v in TRAIN.items()},
    "extended": EXTENDED,
}


def _row(case, *, pressure=5000.0):
    """A synthetic encoded 32-value answer that passes every law gate for ``case`` (pressure <= 0 fails one)."""
    profile = [case["inlet_c"] + 10.0 + 0.2 * i for i in range(30)]
    native = [max(profile) + 1.0, *profile, pressure]
    encoded = output_encoding.encode_targets(np.asarray([native], dtype=float))[0]
    return [float(v) for v in encoded]


def _cases(rng, box, n):
    return [{name: rng.uniform(*box[name]) for name in domain.INPUTS} for _ in range(n)]


def _official():
    return pool_version.official_binding("cooling", "1.8")


def _bounded():
    return pool_version.official_binding("cooling", "1.8", region=REGION)


def _widened(monkeypatch):
    """The receipted widen(): INPUT_BOUNDS updated in place with the region's extended bounds (test-local only)."""
    for name, pair in EXTENDED.items():
        monkeypatch.setitem(domain.INPUT_BOUNDS, name, tuple(pair))


# ---------------------------------------------------------------- the copied steps are pinned


def test_the_copied_steps_sources_are_pinned():
    for name, (fn, sha) in PINNED_SOURCES.items():
        source = inspect.getsource(fn)
        assert hashlib.sha256(source.encode()).hexdigest() == sha, name


# ---------------------------------------------------------------- W4


def test_an_in_box_row_derives_byte_equal_to_todays_derive():
    rng = random.Random(7)
    official, bounded = _official(), _bounded()
    for case in _cases(rng, TRAIN, 200):
        row = _row(case)
        today = official.derive(case, row)
        assert today is not None
        assert bounded.derive(case, row) == today  # dict of floats: equal bit for bit


def test_a_row_inside_the_region_past_the_train_box_equals_the_widen_derive(
    monkeypatch,
):
    rng = random.Random(11)
    box = {**TRAIN, **{k: tuple(v) for k, v in EXTENDED.items()}}
    official, bounded = _official(), _bounded()
    rows = []
    for case in _cases(rng, box, 300):
        if all(TRAIN[k][0] <= case[k] <= TRAIN[k][1] for k in domain.INPUTS):
            continue  # in the TRAIN box: covered above
        row = _row(case)
        assert official.derive(case, row) is None  # today: refused past the TRAIN box
        got = bounded.derive(case, row)
        assert got is not None and all(np.isfinite(v) for v in got.values())
        rows.append((case, row, got))
    assert len(rows) >= 100
    _widened(monkeypatch)
    for case, row, got in rows:
        assert (
            official.derive(case, row) == got
        )  # the receipted widen() derive, bit for bit


def _native(case, *, pressure=5000.0, face_offset=10.0):
    profile = [case["inlet_c"] + face_offset + 0.2 * i for i in range(30)]
    return [max(profile) + 1.0, *profile, pressure]


def test_every_law_gate_stays_inside_the_region():
    """W2, on Cooling's native-output derive (1.0: the same steps without the decode; an encoded answer cannot carry a
    gate failure, the encoding is law-safe): inside the region a sound answer derives, and an answer failing any law
    gate derives None, exactly as the TRAIN-box derive does in the TRAIN box."""
    box = cooling_region.bounds(REGION)
    derive = cooling_region.bounded_derive("1.0", box)
    centre = {k: (lo + hi) / 2 for k, (lo, hi) in TRAIN.items()}
    for case in (centre, {**centre, "inlet_c": 48.0, "heat_load_w": 1900.0}):
        assert derive(case, _native(case)) is not None
        assert (
            derive(case, _native(case, pressure=-1.0)) is None
        )  # pressure_drop_positive
        assert derive(case, _native(case, face_offset=-5.0)) is None  # face_above_inlet
        bad_peak = _native(case)
        bad_peak[0] = min(bad_peak[1:31]) - 1.0
        assert derive(case, bad_peak) is None  # peak_bounds_profile
        assert derive(case, _native(case)[:31]) is None  # schema: not 32 values
        assert derive(case, [*_native(case)[:31], float("nan")]) is None  # not finite


def test_a_row_past_the_region_derives_none():
    bounded = _bounded()
    centre = {k: (lo + hi) / 2 for k, (lo, hi) in TRAIN.items()}
    for name, (low, high) in {**TRAIN, **EXTENDED}.items():
        for value in (
            low - 1e-6 * max(1.0, abs(low)),
            high + 1e-6 * max(1.0, abs(high)),
        ):
            case = {**centre, name: value}
            assert bounded.derive(case, _row(case)) is None, (name, value)


def test_the_grade_never_writes_the_process_wide_bounds():
    before = dict(domain.INPUT_BOUNDS)
    identity = id(domain.INPUT_BOUNDS)
    bounded = _bounded()
    rng = random.Random(3)
    box = {**TRAIN, **{k: tuple(v) for k, v in EXTENDED.items()}}
    for case in _cases(rng, box, 50):
        bounded.derive(case, _row(case))
    assert id(domain.INPUT_BOUNDS) == identity and domain.INPUT_BOUNDS == before


# ---------------------------------------------------------------- W1 + W3: the registered, sealed region


def test_the_region_document_is_checked():
    for bad, code in (
        ([], "region_document_must_be_a_dict"),
        ({"base": {}}, "region_has_no_extended_bounds"),
        ({"extended": {}}, "region_has_no_extended_bounds"),
        ({"extended": {"not_an_input": [0, 1]}}, "region_extends_an_unknown_input"),
        ({"extended": {"inlet_c": [50.0, 25.0]}}, "region_bounds_malformed"),
        ({"extended": {"inlet_c": [25.0]}}, "region_bounds_malformed"),
        ({"extended": {"inlet_c": [True, 50.0]}}, "region_bounds_malformed"),
        ({"extended": {"inlet_c": [25.0, float("inf")]}}, "region_bounds_malformed"),
    ):
        with pytest.raises(pool_exam.ExamRefused) as caught:
            pool_version.official_binding("cooling", "1.8", region=bad)
        assert caught.value.code == code, bad


def test_only_cooling_takes_a_region_and_no_region_leaves_every_binding_as_it_was():
    from types import SimpleNamespace

    with pytest.raises(cooling_region.RegionRefused) as caught:
        cooling_region.bounded_binding(
            SimpleNamespace(kind="motor", version="1.8"), REGION
        )
    assert caught.value.code == "region_binding_is_cooling_only"
    for version in ("1.7", "1.8"):
        plain = pool_version.official_binding("cooling", version)
        # the derive is pool_adapters' own, as before this change
        assert plain.derive.__qualname__ == "_cooling.<locals>.derive"
        assert plain.derive.__module__ == "carbon.scoring.pool_adapters"


def _policies(sha):
    from types import SimpleNamespace

    return SimpleNamespace(physics=SimpleNamespace(region_sha256=sha))


def test_the_sealed_region_must_be_the_registered_one_both_ways():
    sha = cooling_region.canonical_sha256(REGION)
    assert (
        sha
        == hashlib.sha256(
            json.dumps(REGION, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert pool_version.sealed_region(_policies(sha), {"region": REGION}) is REGION
    assert pool_version.sealed_region(_policies(None), {}) is None
    assert pool_version.sealed_region(type("P", (), {"physics": None})(), {}) is None
    for policies, material, code in (
        (_policies(None), {"region": REGION}, "region_not_registered"),
        (_policies(sha), {}, "region_missing_from_the_sealed_pack"),
        (_policies("0" * 64), {"region": REGION}, "region_sha256_mismatch"),
        (
            _policies(sha),
            {"region": {**REGION, "extended": {"inlet_c": [25.0, 51.0]}}},
            "region_sha256_mismatch",
        ),
    ):
        with pytest.raises(pool_exam.ExamRefused) as caught:
            pool_version.sealed_region(policies, material)
        assert caught.value.code == code


def _constants(tmp_path, physics):
    path = tmp_path / "pool_constants.json"
    entry = {} if physics is None else {"physics": physics}
    path.write_text(
        json.dumps(
            {"schema": pool_version.SCHEMA, "versions": {"chip-cold-plate 9.9": entry}}
        )
    )
    return path


def test_a_builder_checks_the_region_against_the_raw_registration(tmp_path):
    sha = cooling_region.canonical_sha256(REGION)
    check = pool_version.checked_region
    assert (
        check(
            "chip-cold-plate",
            "9.9",
            REGION,
            path=_constants(tmp_path, {"region_sha256": sha}),
        )
        is REGION
    )
    assert check("chip-cold-plate", "9.9", None, path=_constants(tmp_path, {})) is None
    with pytest.raises(pool_version.PoolConstantsNotRegistered, match="not_registered"):
        check(
            "chip-cold-plate",
            "9.9",
            REGION,
            path=_constants(tmp_path, {"region_sha256": pool_version.HUMAN_INPUT}),
        )
    with pytest.raises(pool_version.PoolConstantsNotRegistered, match="not_registered"):
        check(
            "chip-cold-plate",
            "9.9",
            REGION,
            path=_constants(tmp_path, {"region_sha256": None}),
        )
    with pytest.raises(pool_exam.ExamRefused, match="region_not_registered"):
        check("chip-cold-plate", "9.9", REGION, path=_constants(tmp_path, {}))


def test_the_region_sha_registers_with_no_default():
    block = {
        "scoring": "headroom",
        "cells_sha256": "c" * 64,
        "gate_statistic": "p90",
        "gate_threshold": {"die_peak_c": 1.0},
        "gate_cases": "agen",
        "enters": "a",
        "ad_split": 0.5,
        "total_rule": "half_a_half_d",
        "skill_form": "log",
        "h_min": 4,
        "h_lo": 2.5,
        "n_min": 12,
    }
    assert pool_version._physics(block).region_sha256 is None
    assert (
        pool_version._physics({**block, "region_sha256": "a" * 64}).region_sha256
        == "a" * 64
    )
    with pytest.raises(pool_version.PoolConstantsNotRegistered, match="not_registered"):
        pool_version._physics({**block, "region_sha256": pool_version.HUMAN_INPUT})
    for bad in ("c1fbc07f", "A" * 64, 1):
        with pytest.raises(pool_version.PoolConstantsNotRegistered, match="malformed"):
            pool_version._physics({**block, "region_sha256": bad})


def test_only_cooling_1_8_registers_a_region_and_it_waits_for_the_seal():
    rows = json.loads(pool_version.CONSTANTS.read_bytes())["versions"]
    registering = {
        key: row["physics"]["region_sha256"]
        for key, row in rows.items()
        if "region_sha256" in (row.get("physics") or {})
    }
    # HUMAN_INPUT until the seal names the signed region of record (W1: never typed here)
    assert registering == {"chip-cold-plate 1.8": pool_version.HUMAN_INPUT}
