"""Two validators' exam copies score byte-identically (traceable copies, c';
Validator ruling, E9).

A copy differs from another only in row order and opaque ids. This builds, for
each Challenge's dual producer, the same model's answers on one bank in its own
order and in a shuffled order, and requires the measurement documents to be
byte-identical. The answers are tied to each case's content (not its position or
id), as a real model's are."""

from __future__ import annotations

import hashlib
import importlib
import json
import random

import numpy as np
import pytest

from carbon.challenge_kit import physical_pack
from carbon.scoring import copy_derivation
from carbon.scoring import physical_dual_pack as physical

CHALLENGES = ("motor", "cooling", "f08", "f02", "battery")
#: The ids a copy renames. F02's action names and Battery's registered EV4
#: candidates carry meaning (their manifests declare it), so those keep theirs.
OPAQUE_IDS = {
    "motor": copy_derivation.OPAQUE,
    "cooling": copy_derivation.OPAQUE,
    "f08": copy_derivation.OPAQUE,
    "f02": (),
    "battery": (),
}
KEYS = (b"validator-one-key-0123456789", b"validator-two-key-9876543210")


def _adapter(name):
    return importlib.import_module(f"carbon.scoring.{name}_dual_pack")


def _content_noise(inputs, width, scale=0.002):
    """Deterministic per-case noise from the case's inputs only."""
    seed = hashlib.sha256(
        json.dumps(sorted(inputs.items()), sort_keys=True).encode()
    ).digest()
    rng = np.random.default_rng(int.from_bytes(seed[:8], "big"))
    return 1.0 + scale * rng.standard_normal(width)


PER_ROW = (
    "case_ids",
    "cohorts",
    "inputs",
    "references",
    "reference_records",
    "reference_present",
)
#: What enters the dual benchmark input: the graded numbers, gates and outcome.
#: Diagnostic fields name cases (opaque per copy) and are not compared.
GRADED = ("A", "D", "gates", "decision_outcome")


def _permuted(bank, order):
    """The same bank with its rows listed in ``order`` (a copy's file order)."""
    return {
        key: ([value[i] for i in order] if key in PER_ROW else value)
        for key, value in bank.items()
    }


def _graded(name, order=None, key=None):
    adapter = _adapter(name)
    bank = physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION)
    if order is not None:
        bank = _permuted(bank, order)
    public = physical_pack.public_roles(adapter.CHALLENGE, adapter.VERSION)
    objective = json.loads(public["design_objective"])
    if key is not None:
        bank, objective = copy_derivation.derive_copy(
            bank, objective, key=key, opaque=OPAQUE_IDS[name]
        )
    names = physical.input_names(adapter)
    rows = physical.bank_rows(bank, names)
    refs = np.asarray(bank["references"], dtype=float)
    # Unmeasured rows (the probes) take one valid row, chosen by id and not by
    # position, so the stand-in model answers the same whatever the copy's order.
    valid = [i for i in range(len(refs)) if not np.isnan(refs[i]).any()]
    fill = refs[min(valid, key=lambda i: rows[i]["case_id"])]
    outputs = []
    for row, ref in zip(rows, refs, strict=True):
        base = fill if np.isnan(ref).any() else ref
        # Battery's exam gates are tight (millivolts), so its noise is smaller.
        scale = 1e-6 if name == "battery" else 0.002
        outputs.append(
            (base * _content_noise(row["inputs"], len(base), scale)).tolist()
        )
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "scope": "PUBLIC_PRACTICE_FEEDBACK",
    }
    measured = adapter.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=json.loads(public["important_limit_definition"]),
        objective=objective,
        train_raw=public["train"],
        names=names,
    )
    return json.dumps(
        {key: measured.get(key) for key in GRADED}, sort_keys=True, allow_nan=False
    ).encode(), len(rows)


@pytest.mark.parametrize("name", CHALLENGES)
def test_a_shuffled_copy_scores_byte_identically(name):
    original, n = _graded(name)
    graded = json.loads(original)
    # A real comparison: scored numbers and passing gates, not two refusals.
    assert 0 < graded["A"] <= 1 and 0 <= graded["D"] <= 1, graded
    for seed in (1, 2, 3):
        order = list(range(n))
        random.Random(seed).shuffle(order)
        assert order != list(range(n))
        shuffled, _ = _graded(name, order)
        assert shuffled == original, f"{name} depends on row order (seed {seed})"


def _bank(name):
    adapter = _adapter(name)
    return physical_pack.development_bank(
        adapter.CHALLENGE, adapter.VERSION
    ), physical_pack.public_roles(adapter.CHALLENGE, adapter.VERSION)


@pytest.mark.parametrize("name", CHALLENGES)
def test_two_validators_copies_score_byte_identically(name):
    """The E9 requirement: copies built from two validators' keys score the same
    bytes as the original (and each other), while the copies themselves differ."""
    original, _ = _graded(name)
    assert json.loads(original)["A"] is not None
    for key in KEYS:
        derived, _ = _graded(name, key=key)
        assert derived == original, f"{name} copy scores differently"


@pytest.mark.parametrize("name", CHALLENGES)
def test_the_copies_differ_but_have_one_identity(name):
    bank, public = _bank(name)
    objective = json.loads(public["design_objective"])
    opaque = OPAQUE_IDS[name]
    copies = [
        copy_derivation.derive_copy(bank, objective, key=key, opaque=opaque)
        for key in KEYS
    ]
    one, two = copies[0][0], copies[1][0]
    # Different row order for different validators (and from the original).
    assert one["case_ids"] != two["case_ids"] != list(bank["case_ids"])
    assert [list(map(float, r)) for r in one["inputs"]] != [
        list(map(float, r)) for r in bank["inputs"]
    ]
    if opaque:
        # No original id survives in a record, the id lists or the case ids.
        old = set(bank["case_ids"])
        assert not old & set(one["case_ids"])
        assert not old & set(two["case_ids"])
        assert set(one["case_ids"]) != set(two["case_ids"])
        text = json.dumps(copies[0][1])
        assert all(
            f'"{design}"' not in text for design in objective.get("design_ids", [])
        )
    # One identity over the canonical form, whichever copy is read.
    identity = copy_derivation.content_digest(bank, opaque=opaque)
    assert copy_derivation.content_digest(one, opaque=opaque) == identity
    assert copy_derivation.content_digest(two, opaque=opaque) == identity
    # A copy is a deterministic function of the exam and the key.
    again = copy_derivation.derive_copy(bank, objective, key=KEYS[0], opaque=opaque)
    assert json.dumps(again[1], sort_keys=True) == json.dumps(
        copies[0][1], sort_keys=True
    )
    assert again[0]["case_ids"] == one["case_ids"]


def test_a_short_key_is_refused():
    bank, public = _bank("motor")
    with pytest.raises(copy_derivation.CopyRefused, match="copy_key_invalid"):
        copy_derivation.derive_copy(bank, {}, key=b"short")
    with pytest.raises(copy_derivation.CopyRefused, match="copy_key_invalid"):
        copy_derivation.derive_copy(bank, {}, key="not bytes")
