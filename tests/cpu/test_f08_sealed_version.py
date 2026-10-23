"""F08's sealed exam batch builds under its own evaluation version (Validator,
2026-10-20), with 1.2's measurement unchanged and exact version dispatch."""

from __future__ import annotations

from carbon.scoring import f08_dual_pack as f08


def test_the_sealed_adapter_names_its_own_evaluation_version():
    sealed = f08.sealed_adapter("1.2")
    graded = f08.adapter(version="1.2")
    assert sealed.EVALUATION_VERSION == "f08-dual-sealed-batch-8-v1"
    assert graded.EVALUATION_VERSION == "f08-dual-near-limit-bank-8-v2"
    assert sealed.VERSION == graded.VERSION == "1.2"
    assert sealed.CASE_ID == graded.CASE_ID
    assert sealed.MINIMUM_LEGS == graded.MINIMUM_LEGS
    assert sealed.input_names() == graded.input_names()
    assert sealed.measure is graded.measure


def test_no_other_version_has_a_sealed_adapter():
    # 1.5 is graph route v2 (1.4's sealed exam); 1.6 is unregistered.
    for version in ("1.0", "1.1", "1.6", None):
        assert f08.sealed_adapter(version) is None


def test_the_v7_catalog_version_serves_the_same_sealed_batches():
    assert f08.sealed_adapter("1.3").EVALUATION_VERSION == "f08-dual-sealed-batch-8-v1"
    assert f08.sealed_adapter("1.3").VERSION == "1.3"
