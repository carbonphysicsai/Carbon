"""Per-validator copies of a Motor sealed grid (traceable copies, c'; Validator
rulings): one generic derivation, Motor's 5 x 6 grid first.

A copy lists the grid's rows in its own order under its own opaque ids (derived
from a Carbon-held per-validator key). The receiver canonicalizes a copy by
content alone (no permutation or id map travels with it) and the unchanged Motor
sealed grader then scores the canonical form. Two validators' copies must
canonicalize to one bank and score byte-identically."""

from __future__ import annotations

import json

import numpy as np
import pytest
from test_motor_sealed_grading import (
    CONDITIONS,
    DESIGNS,
    MOTOR,
    _grid_bank,
)

from carbon.challenge_kit import physical_pack
from carbon.scoring import copy_derivation as cd
from carbon.scoring import motor_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

KEYS = (b"validator-one-key-0123456789", b"validator-two-key-9876543210")


@pytest.fixture(scope="module")
def world():
    bank = _grid_bank(probes=False)
    public = physical_pack.public_roles(MOTOR, "1.3")
    objective = {
        "design_ids": [f"design-{d}" for d in range(DESIGNS)],
        "condition_ids": [f"condition-{c}" for c in range(CONDITIONS)],
    }
    return bank, public, objective


def _normal(bank):
    """Everything that must be equal between two canonical banks, as bytes."""
    return json.dumps(
        {
            "ids": list(bank["case_ids"]),
            "cohorts": list(bank["cohorts"]),
            "inputs": np.asarray(bank["inputs"]).tolist(),
            "references": np.asarray(bank["references"]).tolist(),
            "records": bank["reference_records"],
        },
        sort_keys=True,
    ).encode()


def _graded(bank, public):
    """The unchanged Motor sealed grader on ``bank`` (answers tied to content)."""
    names = physical.input_names(sealed)
    rows = physical.bank_rows(bank, names)
    outputs = []
    for row in rows:
        noise = cd._canonical(sorted(row["inputs"].items()))
        scale = 1.0 + 0.003 * (int.from_bytes(noise[:2], "big") / 65535 - 0.5)
        outputs.append([float(v) * scale for v in row["reference"]])
    definition = sealed.definition(bank=bank, train_raw=public["train"])
    measured = sealed.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=json.loads(public["important_limit_definition"]),
        objective=json.loads(public["design_objective"]),
        train_raw=public["train"],
        names=names,
    )
    return json.dumps(
        {k: measured[k] for k in ("A", "D", "gates", "decision_outcome")},
        sort_keys=True,
    ).encode()


def test_a_copy_has_its_own_order_and_ids_and_recovers_the_canonical_bank(world):
    bank, _public, objective = world
    canonical = cd.canonicalize(bank)
    copies = [cd.derive_copy(canonical, objective, key=key)[0] for key in KEYS]
    one, two = copies
    # Different from each other and from the canonical bank: order and ids.
    assert one["case_ids"] != two["case_ids"] != list(canonical["case_ids"])
    assert not set(one["case_ids"]) & set(canonical["case_ids"])
    assert not set(one["case_ids"]) & set(two["case_ids"])
    ids = {r["design_id"] for r in one["reference_records"]}
    assert len(ids) == DESIGNS and not ids & {f"d{d}" for d in range(DESIGNS)}
    # Canonicalizing by content alone gives the same bank from either copy.
    assert _normal(cd.canonicalize(one)) == _normal(canonical)
    assert _normal(cd.canonicalize(two)) == _normal(canonical)
    # And the original bank (any order, any ids) canonicalizes to it too.
    assert _normal(cd.canonicalize(bank)) == _normal(canonical)


def test_two_validators_copies_score_byte_identically(world):
    bank, public, objective = world
    original = _graded(cd.canonicalize(bank), public)
    assert 0 < json.loads(original)["A"] <= 1
    for key in KEYS:
        copy_bank, _ = cd.derive_copy(cd.canonicalize(bank), objective, key=key)
        assert _graded(cd.canonicalize(copy_bank), public) == original
    # The grader is order-free too: the raw original bank scores the same.
    assert _graded(bank, public) == original


def test_the_canonical_form_is_a_fixed_point(world):
    bank, _public, _objective = world
    canonical = cd.canonicalize(bank)
    assert _normal(cd.canonicalize(canonical)) == _normal(canonical)
    assert list(canonical["case_ids"]) == [
        f"c{i:04d}" for i in range(DESIGNS * CONDITIONS)
    ]


def test_a_derivation_is_deterministic_and_a_key_changes_it(world):
    bank, _public, objective = world
    canonical, objective = cd.canonicalize(bank, objective=objective)
    first = cd.derive_copy(canonical, objective, key=KEYS[0])
    again = cd.derive_copy(canonical, objective, key=KEYS[0])
    assert _normal(first[0]) == _normal(again[0]) and first[1] == again[1]
    other = cd.derive_copy(canonical, objective, key=KEYS[1])
    assert _normal(other[0]) != _normal(first[0])
    # The design objective follows the same renaming.
    renamed = set(first[1]["design_ids"])
    assert renamed == {r["design_id"] for r in first[0]["reference_records"]}
    # Canonicalizing the copy and its objective restores the canonical pair.
    restored, restored_objective = cd.canonicalize(first[0], objective=first[1])
    assert _normal(restored) == _normal(canonical)
    assert restored_objective == objective


def test_a_bank_with_two_identical_rows_is_not_canonicalizable(world):
    bank, _public, _objective = world
    broken = dict(bank)
    broken["reference_records"] = [dict(r) for r in bank["reference_records"]]
    inputs = np.array(bank["inputs"])
    refs = np.array(bank["references"])
    inputs[1] = inputs[0]
    refs[1] = refs[0]
    broken["inputs"], broken["references"] = inputs, refs
    broken["reference_records"][1] = dict(
        broken["reference_records"][0],
        case_id=broken["reference_records"][1]["case_id"],
        design_id=broken["reference_records"][0]["design_id"],
        condition_id=broken["reference_records"][0]["condition_id"],
    )
    with pytest.raises(cd.CopyRefused, match="copy_rows_not_distinct"):
        cd.canonicalize(broken)


def test_the_private_probes_survive_copy_derivation_in_place(world):
    """The probes follow the cells in every copy and canonicalize to the same
    bank: a copy never changes where (or what) the probes are."""
    _bank, public, objective = world
    probed = _grid_bank(probes=True)
    canonical = cd.canonicalize(probed)
    assert list(canonical["cohorts"]).count("probe_response") == 76
    assert list(canonical["cohorts"][:30]) != ["decision_sealed_grid"] * 30
    for key in KEYS:
        copy_bank, _ = cd.derive_copy(canonical, objective, key=key)
        again = cd.canonicalize(copy_bank)
        assert list(again["cohorts"]) == list(canonical["cohorts"])
        assert np.array_equal(
            np.asarray(again["inputs"]), np.asarray(canonical["inputs"])
        )
