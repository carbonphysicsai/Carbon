"""OWNER-BATTERY-GATE-PLATING-V2-01: the plating-v2 gate beside a frozen EV5."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from carbon.battery import plating_v2
from carbon.battery.value import decision as d
from carbon.battery.value import false_acceptance as fa
from carbon.battery.value import gate_plating_v2 as gate

ROOT = Path(__file__).resolve().parents[2]
EV5 = ROOT / "docs/development/evidence/ev5-2026-10-03"
CONTRACT = json.loads(
    (
        ROOT / "carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json"
    ).read_bytes()
)
SCENARIO = {"conditions": [{}]}
#: An ev4 case the v2 record re-solved at mesh 160 (m160 0.834 mV, so
#: m160-d3-r1 UNRESOLVED; m20 2.257 mV).
M160_CASE = "ev4:D-0000:c1=0.75,c2=0.6:0"


@pytest.fixture(scope="module")
def ev5_refs():
    with gzip.open(EV5 / "decision-references.jsonl.gz") as stream:
        rows = [json.loads(line) for line in stream]
    return {r["case_id"]: r for r in rows}


def _record(ev5_refs, margin_v):
    record = copy.deepcopy(next(iter(ev5_refs.values())))
    record["outputs"]["plating_margin_v"] = margin_v
    return record


def _candidates(n):
    return [{"id": f"k{i}", "c1": 1.0, "c2": float(i)} for i in range(n)]


def test_unresolved_plating_is_never_counted_safe(ev5_refs):
    margins = [2.0e-3, 0.5e-3, 4.0e-3, -1.0e-3]  # all inside the v2 window
    candidates = _candidates(len(margins))
    refs = {(c["id"], 0): _record(ev5_refs, m) for c, m in zip(candidates, margins)}
    out = gate.assess_reference(CONTRACT, SCENARIO, candidates, refs)
    for c in candidates:
        assert out[c["id"]]["plating_v2"][0]["rule"] == "pending-m160-r1"
        assert out[c["id"]]["checks"][0][gate.PLATING] == d.UNRESOLVED
        assert out[c["id"]]["status"] != d.FEASIBLE
    assert d.best_in_set(candidates, out) is None
    # EV5's own gate would have called the 2 and 4 mV cases plating PASS.
    ev5 = d.assess_reference(CONTRACT, SCENARIO, candidates, refs)
    assert ev5["k0"]["checks"][0][gate.PLATING] == d.PASS


def test_unresolved_enters_no_plating_measure_and_is_counted(ev5_refs):
    margins = {"a": 2.0e-3, "b": -10.0e-3, "c": 20.0e-3, "d": 4.6e-3}
    refs = {k: _record(ev5_refs, m) for k, m in margins.items()}
    predictions = {k: copy.deepcopy(refs[k]["outputs"]) for k in refs}
    for outputs in predictions.values():  # a model that always says "no plating"
        outputs["plating_margin_v"] = 0.05
    result = gate.false_acceptance(CONTRACT, predictions, list(refs), refs)
    row = result["constraints"][gate.PLATING]
    # a: pending UNRESOLVED; b: below window, FAIL; c: no v2 claim, mesh-20 PASS;
    # d: above window, FEASIBLE.
    assert row["reference_unresolved"] == 1
    assert row["reference_fail"] == 1 and row["false_acceptance"] == 1
    assert row["reference_pass"] == 2
    counts = gate.label_counts(CONTRACT, refs, list(refs))
    assert counts["unresolved_case_ids"] == ["a"]
    assert counts["counts"] == {
        "m20-above-window-r1:FEASIBLE": 1,
        "m20-below-window:INFEASIBLE": 1,
        "mesh20-no-v2-claim": 1,
        "pending-m160-r1:UNRESOLVED": 1,
    }


def test_no_v2_claim_keeps_the_mesh20_verdict(ev5_refs):
    bands = CONTRACT["reference"]["uncertainty"]["bands"]
    for margin in (15.0e-3, 40.0e-3, -15.0e-3, -0.2):
        q = d.measure(CONTRACT, _record(ev5_refs, margin)["outputs"])
        label = gate.plating_label(plating_v2.reader(str(ROOT)), margin)
        assert label is None
        assert gate.check(CONTRACT, q, bands, label) == d.check(CONTRACT, q, bands)


def test_a_mesh160_case_uses_its_resolve(ev5_refs):
    candidates = _candidates(1)
    refs = {("k0", 0): _record(ev5_refs, 2.25729267758314e-3)}
    out = gate.assess_reference(
        CONTRACT, SCENARIO, candidates, refs, {("k0", 0): M160_CASE}
    )
    assert out["k0"]["plating_v2"][0] == {"label": "UNRESOLVED", "rule": "m160-d3-r1"}
    assert gate.m160_by_case(str(ROOT))[M160_CASE][1] == pytest.approx(
        0.834e-3, rel=1e-3
    )


def test_an_id_match_with_a_different_m20_refuses(ev5_refs):
    """A case id alone is not a physics key: the record's m20 must equal the
    measured margin, or the binding refuses (never falls back to pending)."""
    candidates = _candidates(1)
    refs = {("k0", 0): _record(ev5_refs, 2.0e-3)}  # record m20 is 2.2573 mV
    with pytest.raises(gate.M160BindingRefused, match="plating_v2_m20_mismatch"):
        gate.assess_reference(
            CONTRACT, SCENARIO, candidates, refs, {("k0", 0): M160_CASE}
        )
    with pytest.raises(gate.M160BindingRefused):
        gate.false_acceptance(
            CONTRACT,
            {M160_CASE: refs[("k0", 0)]["outputs"]},
            [M160_CASE],
            {M160_CASE: refs[("k0", 0)]},
        )
    with pytest.raises(gate.M160BindingRefused):
        gate.label_counts(CONTRACT, {M160_CASE: refs[("k0", 0)]}, [M160_CASE])
    # Inside the tolerance it binds.
    entry = gate.m160_by_case(str(ROOT))[M160_CASE]
    assert gate.bound_m160(entry, entry[0] / 1000.0) == entry[1]


def test_reader_unavailable_fails_closed(ev5_refs, monkeypatch):
    plating_v2.reader.cache_clear()
    monkeypatch.setattr(plating_v2, "READER", (plating_v2.READER[0], "0" * 64))
    try:
        refs = {("k0", 0): _record(ev5_refs, 20.0e-3)}
        with pytest.raises(plating_v2.ReaderUnavailable):
            gate.assess_reference(CONTRACT, SCENARIO, _candidates(1), refs)
        with pytest.raises(plating_v2.ReaderUnavailable):
            gate.false_acceptance(CONTRACT, {}, [], {})
    finally:
        plating_v2.reader.cache_clear()


def test_a_changed_label_record_fails_closed(monkeypatch):
    gate.m160_by_case.cache_clear()
    monkeypatch.setattr(gate, "LABELS", (gate.LABELS[0], "0" * 64))
    try:
        with pytest.raises(plating_v2.ReaderUnavailable):
            gate.m160_by_case(str(ROOT))
    finally:
        gate.m160_by_case.cache_clear()


def test_ev5_is_byte_unchanged(ev5_refs):
    """EV5's pinned code and frozen evidence are the bytes its run record
    pinned, and running the v2 gate leaves EV5's verdicts unchanged."""
    record = json.loads((EV5 / "run-record.json").read_bytes())
    for path in (
        "carbon/battery/value/decision.py",
        "carbon/battery/value/false_acceptance.py",
        "carbon/battery/value/margins.py",
        "carbon/battery/value/admissibility.py",
        "carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json",
        "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
    ):
        digest = "sha256:" + hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert record["files"][path] == digest, path
    manifest = (ROOT / record["freeze_manifest"]["path"]).read_bytes()
    assert "sha256:" + hashlib.sha256(manifest).hexdigest() == (
        record["freeze_manifest"]["sha256"]
    )
    gate_record = json.loads((EV5 / "gate.json").read_bytes())
    results = (EV5 / "results.json").read_bytes()
    assert gate_record["results_sha256"].removeprefix("sha256:") == (
        hashlib.sha256(results).hexdigest()
    )
    ids = sorted(ev5_refs)[:120]
    contract = copy.deepcopy(CONTRACT)
    refs = {k: ev5_refs[k] for k in ids}
    predictions = {k: refs[k]["outputs"] for k in ids}
    before = json.dumps(fa.component(contract, predictions, ids, refs), sort_keys=True)
    gate.false_acceptance(contract, predictions, ids, refs)
    gate.label_counts(contract, refs, ids)
    after = json.dumps(fa.component(contract, predictions, ids, refs), sort_keys=True)
    assert before == after
    assert contract == CONTRACT
