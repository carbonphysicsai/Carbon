"""OWNER-CHALLENGE-ADMISSION-01 §6.1: every construction expansion is recorded.

Widening a construction contract needs no review in advance, but it must be
recorded: what widened, when, and under which contract version. This test is
what makes that true. It fails whenever any contract's live state differs
from its newest record. Each rule is shown failing on a deliberate specimen,
so a clean result means recorded, not unchecked.
"""

import dataclasses
import datetime
import json
import shutil

import pytest

from carbon.reconstruction import capability_registry as registry
from carbon.reconstruction import expansion_record as er


def test_every_construction_contract_is_recorded():
    missing = er.unrecorded()
    assert not missing, (
        "construction contract changed without a record (§6.1). Record it: "
        "python -m carbon.reconstruction.expansion_record record --challenge "
        "<token> --what '<what widened, and why>'. " + json.dumps(missing)
    )


def test_the_stored_records_are_a_well_formed_append_only_trail():
    assert er.problems() == []


def test_every_contract_has_a_record_and_the_records_cover_no_other():
    assert {p.name for p in er.ROOT.iterdir() if p.is_dir()} == set(registry.CONTRACTS)


@pytest.fixture
def copy(tmp_path):
    root = tmp_path / "expansions"
    shutil.copytree(er.ROOT, root)
    return root


def _widened(monkeypatch, token):
    """The live contract of `token`, with its worker deadline doubled."""
    live = registry.CONTRACTS[token]
    envelope = tuple(
        (k, v * 2 if k == "worker_deadline_seconds" else v) for k, v in live.envelope
    )
    wider = dataclasses.replace(live, envelope=envelope)
    monkeypatch.setitem(registry.CONTRACTS, token, wider)
    return wider


def test_an_unrecorded_widening_is_refused(copy, monkeypatch):
    """Specimen: widen a live contract without recording it. The same check
    the repository test makes reports exactly that Challenge."""
    token = registry.BATTERY_CHALLENGE
    _widened(monkeypatch, token)
    assert set(er.unrecorded(copy)) == {token}
    # Recording it is what clears it, and the record names the new digest.
    path = er.record(
        token,
        "Specimen: worker deadline doubled to test the record rule.",
        root=copy,
        today=datetime.date(2026, 10, 2),
    )
    assert er.unrecorded(copy) == {} and er.problems(copy) == []
    entry = json.loads(path.read_text())
    assert entry["sequence"] == 1
    assert entry["contract_digest"] == registry.contract(token).digest
    assert entry["contract_document"]["envelope"]["worker_deadline_seconds"] == 1200


def test_a_narrowing_is_recorded_too(copy, monkeypatch):
    """Locking down is part of the trail as well: any change to the pinned
    document needs a record, not only additions."""
    token = registry.BURGERS_CHALLENGE
    live = registry.CONTRACTS[token]
    narrower = dataclasses.replace(live, lanes=live.lanes[:1])
    monkeypatch.setitem(registry.CONTRACTS, token, narrower)
    assert set(er.unrecorded(copy)) == {token}


def test_a_tampered_or_reordered_record_is_found(copy):
    """Specimen for each well-formedness rule."""
    token = registry.BURGERS_CHALLENGE
    path = copy / token / "0000.json"
    entry = json.loads(path.read_text())

    entry["contract_document"]["envelope"]["worker_cpu"] = 64
    path.write_text(json.dumps(entry))
    assert any("digest does not match" in p for p in er.problems(copy))

    entry = json.loads((er.ROOT / token / "0000.json").read_text())
    entry["sequence"] = 3
    entry["what"] = "too short"
    path.write_text(json.dumps(entry))
    found = er.problems(copy)
    assert any("not contiguous" in p for p in found)
    assert any("says too little" in p for p in found)


def test_recording_nothing_or_saying_nothing_is_refused(copy, monkeypatch):
    with pytest.raises(ValueError, match="nothing to record"):
        er.record(registry.BURGERS_CHALLENGE, "x" * 40, root=copy)
    _widened(monkeypatch, registry.BURGERS_CHALLENGE)
    with pytest.raises(ValueError, match="say what"):
        er.record(registry.BURGERS_CHALLENGE, "widened", root=copy)


def test_the_record_uses_the_registry_digest_rule():
    for token in registry.CONTRACTS:
        live = registry.contract(token)
        assert er.digest_of(live.document()) == live.digest
