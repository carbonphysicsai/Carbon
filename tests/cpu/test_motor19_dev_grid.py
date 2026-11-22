"""Motor 1.9's 241-wide development bank (`motor19_dev_grid`). Claims: each reference keeps 1.8's 240 development columns
and gains its case's magnet value at column 240, probes stay all-NaN 241 wide, nothing is served until the magnet file is
pinned, a malformed / other / incomplete magnet file refuses, and the adapter is 1.9's. Synthetic numbers only.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from carbon.motor import row18, row19
from carbon.scoring import motor19_dev_grid as m

IDS = ("practice-0000", "decision-d01-r01", "probe-01-d1m")


def _bank240():
    references = np.full((3, row18.WIDTH), np.nan)
    references[0] = np.linspace(1.0, 2.0, row18.WIDTH)
    references[1] = np.linspace(3.0, 4.0, row18.WIDTH)
    return {
        "case_ids": IDS,
        "cohorts": ("practice", "decision_sealed_grid", "probe_response"),
        "references": references,
        "reference_present": (True, True, False),
        "solver_evidence": b"base",
    }


def _file(cases):
    raw = json.dumps({"schema": m.SCHEMA, "cases": cases}, sort_keys=True).encode()
    return raw, hashlib.sha256(raw).hexdigest()


MAGNETS = {"practice-0000": 0.41, "decision-d01-r01": 0.37}


def test_each_reference_keeps_its_240_columns_and_gains_its_magnet_value():
    wide = m.widen(_bank240(), MAGNETS)
    refs = wide["references"]
    assert refs.shape == (3, row19.WIDTH) == (3, 241)
    base = _bank240()["references"]
    assert np.array_equal(refs[0, :240], base[0]) and refs[0, 240] == 0.41
    assert np.array_equal(refs[1, :240], base[1]) and refs[1, 240] == 0.37
    assert np.isnan(refs[2]).all()  # a probe row stays all-NaN
    assert wide["solver_evidence"].startswith(b"base|motor19-magnet:")
    assert not refs.flags.writeable


def test_a_reference_without_a_magnet_value_or_a_torque_only_base_refuses():
    with pytest.raises(m.DevBankUnavailable, match="case_without_magnet"):
        m.widen(_bank240(), {"practice-0000": 0.41})
    narrow = {**_bank240(), "references": np.zeros((3, 60))}
    with pytest.raises(m.DevBankUnavailable, match="not_1p8_wide"):
        m.widen(narrow, MAGNETS)


def test_the_magnet_file_is_read_only_at_its_pin():
    raw, sha = _file(MAGNETS)
    assert m.load_magnets(raw, pinned=sha) == MAGNETS
    with pytest.raises(m.DevBankUnavailable, match="differs"):
        m.load_magnets(raw + b" ", pinned=sha)
    for cases in ({}, {"x": float("nan")}, {"x": True}, {"x": "0.4"}, {"": 0.4}):
        bad, bad_sha = _file(cases) if cases != {"x": float("nan")} else (None, None)
        if bad is None:
            bad = b'{"schema": "%s", "cases": {"x": NaN}}' % m.SCHEMA.encode()
            bad_sha = hashlib.sha256(bad).hexdigest()
        with pytest.raises(m.DevBankUnavailable, match="invalid"):
            m.load_magnets(bad, pinned=bad_sha)


def test_nothing_is_served_until_the_magnet_file_is_pinned():
    assert m.MAGNET_SHA256 is None
    with pytest.raises(m.DevBankUnavailable, match="not_pinned"):
        m.load_magnets()
    with pytest.raises(m.DevBankUnavailable, match="not_pinned"):
        m.bank()
    with pytest.raises(m.DevBankUnavailable, match="1.9_only"):
        m.bank("1.8")


def test_the_dispatch_registers_this_bank_and_adapter():
    source = (m.MAGNET_FILE.parents[2] / "scoring" / "motor19_dual_pack.py").read_text(
        encoding="utf-8"
    )
    assert "bank=motor19_dev_grid.bank" in source
    assert "adapter=motor19_dev_grid.adapter" in source
