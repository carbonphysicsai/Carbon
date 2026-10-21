"""F02's adapter grades a sealed exam batch (Validator, 2026-10-20): no response
pairs (margin and decision only), the whole batch is the near block, its own
solver evidence is the reference receipt, and its own evaluation version."""

from __future__ import annotations

import copy
import hashlib

import pytest
from test_f02_sealed_pack import batch

from carbon.challenge_kit import f02_sealed_pack as sealed
from carbon.challenge_kit import f02_train, physical_pack
from carbon.scoring import design_fidelity
from carbon.scoring import f02_dual_pack as adapter
from carbon.scoring import physical_dual_pack as physical

LIMIT = f02_train.LIMIT_C


def _sealed_bank():
    """Data Collection's fixture batch, its synthetic (non-production) peaks
    moved within 1 C of the limit on both sides so the margin coverage holds."""
    document, records = batch()
    for i, record in enumerate(records):
        peak = LIMIT + (0.6 if i % 2 else -0.4) + 0.01 * i
        record["outputs"]["peak_top_c"] = peak
        record["rung_peaks_c"] = {"primary": peak, "mesh2": peak + 0.003, "dt0.5": peak}
        record["rung_comparison"] = {"pass": True, "primary_peak_c": peak}
    return sealed.sealed_bank(document, records)


def _rows(bank):
    return physical.bank_rows(bank, adapter.input_names())


def _measure(bank, outputs, definition=None):
    definition = definition or adapter.definition(bank=bank, train_raw=b"")
    return adapter.measure(
        bank_rows=_rows(bank),
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits={},
        objective={},
        train_raw=b"",
        names=adapter.input_names(),
    )


def _truth(bank):
    return [[row["record"]["rung_peaks_c"]["primary"]] for row in _rows(bank)]


def test_a_sealed_definition_registers_margin_only_and_its_own_receipt():
    bank = _sealed_bank()
    definition = adapter.definition(bank=bank, train_raw=b"")
    adapter.validate_definition(definition)
    assert definition["bank_kind"] == "sealed_batch"
    assert definition["reference_interval"]["receipt"] == (
        "sha256:" + hashlib.sha256(bank["solver_evidence"]).hexdigest()
    )
    kinds = [c["kind"] for c in definition["policy"]["components"]]
    assert kinds == ["margin"]
    design_fidelity.validate_policy(definition["policy"])


def test_the_development_bank_keeps_its_response_pairs_and_judgement():
    bank = physical_pack.development_bank("f02", "2.0")
    definition = adapter.definition(bank=bank, train_raw=b"")
    assert definition["bank_kind"] == "development"
    assert [c["kind"] for c in definition["policy"]["components"]] == [
        "margin",
        "response",
    ]
    assert definition["reference_interval"]["receipt"] == (
        "sha256:" + physical_pack._F02_JUDGEMENT[1]
    )


def test_a_model_equal_to_the_sealed_references_earns_full_a_and_d():
    bank = _sealed_bank()
    measured = _measure(bank, _truth(bank))
    assert measured["A"] == 1.0 and measured["D"] == 1.0
    assert all(measured["gates"].values())
    assert measured["reduction"]["full_credit_eligible"] is True


def test_a_sealed_batch_is_wholly_the_near_block_so_its_loss_is_the_worst_error():
    bank = _sealed_bank()
    truth, outputs = _truth(bank), _truth(bank)
    outputs[3] = [outputs[3][0] + 0.2]
    std = f02_train.load_public_train(adapter.VERSION)["train_peak_std_c"]
    worst = abs(outputs[3][0] - truth[3][0]) / std
    assert _measure(bank, outputs)["A"] == 1 / (1 + worst)


def test_response_pairs_naming_cases_not_in_the_bank_refuse():
    bank = _sealed_bank()
    definition = adapter.definition(bank=bank, train_raw=b"")
    # The development policy on a sealed bank: its 84-87 W pairs name cases
    # this bank does not hold, which used to pass silently.
    definition["policy"] = adapter.policy(_rows(bank), "development")
    with pytest.raises(adapter.Refused) as refused:
        adapter.validate_definition(definition)
    assert refused.value.code in ("f02_policy_invalid", "f02_policy_case_absent")


def test_a_bank_of_an_unregistered_population_refuses():
    bank = {**_sealed_bank(), "population": "SOMETHING_ELSE"}
    with pytest.raises(adapter.Refused) as refused:
        adapter.definition(bank=bank, train_raw=b"")
    assert refused.value.code == "f02_bank_kind_unregistered"


def test_the_sealed_adapter_names_its_own_evaluation_version():
    assert adapter.sealed_adapter("2.1").EVALUATION_VERSION == (
        "f02-dual-sealed-batch-8-v1"
    )
    assert adapter.sealed_adapter("2.1").VERSION == "2.1"
    assert adapter.sealed_adapter("9.9") is None


def test_a_definition_whose_sealed_receipt_is_malformed_refuses():
    bank = _sealed_bank()
    definition = copy.deepcopy(adapter.definition(bank=bank, train_raw=b""))
    definition["reference_interval"]["receipt"] = "not-a-digest"
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(definition)


def test_only_the_graded_version_has_a_sealed_adapter():
    assert adapter.sealed_adapter("2.0") is None
    assert adapter.sealed_adapter(None) is None


def test_the_v7_catalog_version_serves_the_same_sealed_batches():
    assert adapter.sealed_adapter("2.2").EVALUATION_VERSION == (
        "f02-dual-sealed-batch-8-v1"
    )
    assert adapter.sealed_adapter("2.3") is None
