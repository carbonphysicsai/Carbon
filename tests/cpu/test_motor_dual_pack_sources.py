"""Motor's score values come from their committed sources, never a copy.

The applied definition (MOTOR_APPLIED_SCORE_DEFINITION_20261018) is read at
its pinned bytes; its leg minimums are the G1 gate policy's baseline legs at
full precision. A changed byte in either source is refused, not absorbed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.scoring import motor_dual_pack as pack

DATA = Path(__file__).resolve().parents[2] / "carbon/challenge_kit/data"


def _load(name):
    raw = (DATA / name).read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest(), json.loads(raw)


def test_the_definition_file_is_the_pinned_one_and_supplies_every_value():
    digest, definition = _load("motor-applied-score-definition-20261018.json")
    assert digest == pack.SOURCE_DEFINITION_SHA256
    values = pack._definition_values()
    assert values["losses"] == definition["A"]["losses"]
    assert values["f0_scale"] == definition["A"]["f0_scale"]
    assert values["signed_margin_scale"] == definition["A"]["signed_margin_scale"]
    assert values["D_scale"] == definition["D"]["scale"]
    assert values["signed_margin_cell"] == {
        "mean_torque_nm": 4.0,
        "ripple_fraction": 0.30,
    }
    applied = definition["applied_score_pack"]
    assert pack._applied_pack() == {
        k: v
        for k, v in applied.items()
        if k
        not in ("pack_digest", "physics_contract_digest", "measurement_contract_digest")
    }


def test_leg_minimums_are_the_g1_baseline_legs_at_full_precision():
    digest, g1 = _load("motor-applied-g1-measurement-contract-20261018.json")
    assert digest == pack.G1_MEASUREMENT_CONTRACT_SHA256
    legs = pack._applied_pack()["legs"]
    assert legs["A"]["minimum"] == g1["baseline_binding"]["baseline_legs"]["A"]
    assert legs["D"]["minimum"] == g1["baseline_binding"]["baseline_legs"]["D"]
    _, definition = _load("motor-applied-score-definition-20261018.json")
    assert definition["minimums"] == g1["baseline_binding"]["baseline_legs"]


def test_a_changed_definition_byte_is_refused(tmp_path, monkeypatch):
    changed = tmp_path / "definition.json"
    raw = pack.DEFINITION_FILE.read_bytes()
    changed.write_bytes(raw.replace(b'"f0_scale":0.17', b'"f0_scale":0.18'))
    assert changed.read_bytes() != raw
    pack.applied_definition.cache_clear()
    monkeypatch.setattr(pack, "DEFINITION_FILE", changed)
    try:
        with pytest.raises(ValueError, match="differs from its pin"):
            pack.applied_definition()
    finally:
        pack.applied_definition.cache_clear()
