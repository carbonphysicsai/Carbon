"""The shared core's reference mask (REFERENCE_PRESENT_MASK_INTERFACE_20261020,
Validator's conditions): a masked row never enters a measure, a NaN in a present
row refuses, and unmasked banks keep their exact bytes."""

import json
import math

import pytest

from carbon.challenge_kit import physical_pack
from carbon.scoring import benchmark_evidence
from carbon.scoring import physical_dual_pack as physical

NAN = math.nan


def _bank(references, present=None):
    bank = {
        "case_ids": tuple(f"c{i}" for i in range(len(references))),
        "cohorts": ("practice",) * len(references),
        "inputs": [[float(i)] for i in range(len(references))],
        "references": references,
        "reference_records": [{"status": "OK"} for _ in references],
    }
    if present is not None:
        bank["reference_present"] = present
    return bank


def test_a_masked_row_carries_no_truth_and_flattens_to_null():
    bank = _bank([[1.0, 2.0], [NAN, NAN], [3.0, 4.0]], (True, False, True))
    rows = physical.bank_rows(bank, ["x"])
    assert [row["reference"] for row in rows] == [[1.0, 2.0], None, [3.0, 4.0]]
    assert [row["reference_present"] for row in rows] == [True, False, True]
    assert physical.flat_references(bank) == [1.0, 2.0, None, None, 3.0, 4.0]


@pytest.mark.parametrize(
    "references, present",
    [
        ([[1.0, NAN]], (True,)),  # a NaN in a present row
        ([[1.0, 2.0]], (False,)),  # a value where there is no reference
        ([[NAN, 2.0]], (False,)),  # partly filled
        ([[1.0, 2.0]], (1,)),  # not a bool
        ([[1.0, 2.0], [3.0, 4.0]], (True,)),  # wrong length
    ],
)
def test_a_reference_never_filled_or_guessed_refuses(references, present):
    with pytest.raises(ValueError, match="reference_invalid"):
        physical.bank_rows(_bank(references, present), ["x"])


def test_an_unmasked_bank_with_a_nan_refuses_too():
    with pytest.raises(ValueError, match="reference_invalid"):
        physical.reference_mask(_bank([[1.0, NAN]]))


def test_only_a_masked_bank_adds_the_mask_to_its_digest():
    plain = _bank([[1.0], [2.0]])
    assert physical.bank_digest(plain) == physical.bank_digest(
        {**plain, "references": [[9.0], [9.0]]}
    )
    masked = _bank([[1.0], [NAN]], (True, False))
    unmasked_view = {k: v for k, v in masked.items() if k != "reference_present"}
    assert physical.bank_digest(masked) != physical.bank_digest(unmasked_view)


@pytest.mark.parametrize(
    "challenge, version",
    [
        ("electric-motor-magnetics", "1.0"),
        ("chip-cold-plate", "1.0"),
        ("f08-ribbed-bracket", "1.1"),
        ("f02", "2.0"),
    ],
)
def test_existing_banks_carry_no_mask_and_keep_their_rows(challenge, version):
    bank = physical_pack.development_bank(challenge, version)
    assert "reference_present" not in bank
    assert all(physical.reference_mask(bank))
    assert physical.flat_references(bank) == [
        float(v) for row in bank["references"] for v in row
    ]


def test_the_descriptive_reducer_reads_null_only_where_masked():
    assert benchmark_evidence._masked_outputs(
        [1.0, 2.0, None, None], 4, [True, False]
    ) == [1.0, 2.0, None, None]
    for values, mask in (
        ([1.0, 2.0, 3.0, None], [True, False]),  # a value in a masked case
        ([1.0, None, None, None], [True, False]),  # a null in a present case
        ([1.0, 2.0, 3.0, 4.0], [True, True]),  # a mask that masks nothing
    ):
        with pytest.raises(benchmark_evidence.BenchmarkRefused):
            benchmark_evidence._masked_outputs(values, 4, mask)
    assert json.dumps(None) == "null"
