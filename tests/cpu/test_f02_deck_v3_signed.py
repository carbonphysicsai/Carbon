"""F02 3.0's SIGNED production deck (f02_deck_v3.write_signed_case; Validator 11-01, before the Stage-2 pods).

Claims: a SIGNED deck requires all three owner-signed pins (production tables, the signed leakage law by its sha256, the signed box by
its canonical sha256) and refuses anything else, including a case outside the box; its physics is byte-identical to the test-mode deck
of the same inputs, and the two decks differ only in their label fields; the receipted payload files load under the real pins.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "codex-queue" / "reports" / "F02_V3_STAGE2_SIGNED_REV2_20261101"
POINTS = [[280.0, 1.0e6], [340.0, 3.0e6], [400.0, 9.0e6]]
CASE = {
    "peak_w": 80.0,
    "on_time_s": 6.0,
    "ramp_fraction": 0.0,
    "pulses": 1,
    "h_w_m2_k": 3000.0,
    "coolant_c": 30.0,
    "start_offset_c": 10.0,
    "left_source_fraction": 0.7,
    "tim_thickness_mm": 0.12,
}
BOX_INPUTS = {
    "coolant_c": [25, 35],
    "gap_s": [5, 15],
    "h_w_m2_k": [2500, 3500],
    "initial_c": [35, 55],
    "left_source_fraction": [0.5, 0.9],
    "on_time_s": [4, 8],
    "peak_w": [70, 90],
    "pulses": [1, 2],
    "ramp_fraction": [0, 1],
    "tim_thickness_mm": [0.1, 0.15],
}


def _leak_file(tmp_path, decision, name):
    doc = {
        "schema": v3.LEAKAGE_SCHEMA,
        "decision": decision,
        "source": "test fixture",
        "form": "table",
        "range_k": [280.0, 400.0],
        "points": POINTS,
    }
    path = tmp_path / name
    path.write_text(json.dumps(doc, sort_keys=True))
    return path


def _box_file(tmp_path, inputs=BOX_INPUTS, **over):
    doc = {
        "schema": v3.BOX_SCHEMA,
        "status": "OWNER_SIGNED",
        "record": "fixture",
        "basis": ["fixture"],
        "inputs": inputs,
        **over,
    }
    sha = hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "box.json"
    path.write_text(json.dumps({**doc, "box_sha256": sha}))
    return path, sha


@pytest.fixture
def signed(tmp_path, monkeypatch):
    leak = _leak_file(tmp_path, v3.SIGNED_LEAKAGE_DECISION, "leak-signed.json")
    box, box_sha = _box_file(tmp_path)
    monkeypatch.setattr(
        v3, "SIGNED_LEAKAGE_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(v3, "SIGNED_BOX_SHA256", box_sha)
    return leak, box


def _physics(directory):
    sif = (directory / "case.sif").read_text()
    return "".join(
        line for line in sif.splitlines(keepends=True) if not line.startswith("!")
    )


def test_the_signed_deck_is_the_test_mode_deck_but_for_its_labels(tmp_path, signed):
    leak, box = signed
    meta = v3.write_signed_case(
        CASE, tmp_path / "signed", leakage_path=leak, box_path=box
    )
    test_leak = v3.load_leakage(
        _leak_file(tmp_path, v3.LEAKAGE_TEST_ONLY, "leak-test.json"), test_mode=True
    )
    tables = v3.resolve_materials(production=True)[0]
    as_tables = {
        name: {prop: tables[name][prop] for prop in ("k", "cp")}
        for name in tables
        if name != "tim"
    }
    test_meta = v3.write_case(
        CASE, tmp_path / "test", tables=as_tables, test_mode=True, leakage=test_leak
    )
    # the physics text is byte-identical; the label lines (comments) are the only difference
    assert _physics(tmp_path / "signed") == _physics(tmp_path / "test")
    files = sorted(
        p.relative_to(tmp_path / "signed")
        for p in (tmp_path / "signed").rglob("*")
        if p.is_file()
    )
    assert files == sorted(
        p.relative_to(tmp_path / "test")
        for p in (tmp_path / "test").rglob("*")
        if p.is_file()
    )
    for rel in files:
        if rel.name not in ("case.sif", "deck.json"):
            assert (tmp_path / "signed" / rel).read_bytes() == (
                tmp_path / "test" / rel
            ).read_bytes(), rel
    label_fields = {"tables", "tables_source", "deck_label", "signed"}
    strip = lambda m: {
        k: v for k, v in m.items() if k not in label_fields | {"leakage"}
    }
    assert strip(meta) == strip(test_meta)
    leak_labels = {"decision", "label", "sha256"}
    assert {k: v for k, v in meta["leakage"].items() if k not in leak_labels} == {
        k: v for k, v in test_meta["leakage"].items() if k not in leak_labels
    }
    assert meta["deck_label"] == "SIGNED" and meta["tables"] == "PRODUCTION"
    assert (
        meta["leakage"]["label"] == "REGISTERED"
        and meta["leakage"]["decision"] == v3.SIGNED_LEAKAGE_DECISION
    )
    assert meta["signed"]["box"] == "sha256:" + v3.SIGNED_BOX_SHA256
    assert test_meta["tables"] == "TEST_ONLY" and "deck_label" not in test_meta
    assert "! SIGNED:" in (tmp_path / "signed" / "case.sif").read_text()


def test_a_signed_deck_refuses_anything_but_the_signed_pins(tmp_path, signed):
    leak, box = signed
    other = _leak_file(tmp_path, v3.SIGNED_LEAKAGE_DECISION, "leak-other.json")
    other.write_text(other.read_text().replace("9000000.0", "9000001.0"))
    with pytest.raises(v3.DeckRefused, match="leakage_file_digest_differs"):
        v3.write_signed_case(CASE, tmp_path / "a", leakage_path=other, box_path=box)
    test_only = _leak_file(tmp_path, v3.LEAKAGE_TEST_ONLY, "leak-test-only.json")
    with pytest.raises(v3.DeckRefused):
        v3.write_signed_case(CASE, tmp_path / "b", leakage_path=test_only, box_path=box)
    changed = json.loads(box.read_text())
    changed["inputs"]["peak_w"] = [70, 95]
    box.write_text(json.dumps(changed))
    with pytest.raises(v3.DeckRefused, match="box_changed_after_signing"):
        v3.write_signed_case(CASE, tmp_path / "c", leakage_path=leak, box_path=box)
    changed["box_sha256"] = "0" * 64
    box.write_text(json.dumps(changed))
    with pytest.raises(v3.DeckRefused, match="box_not_the_signed_one"):
        v3.write_signed_case(CASE, tmp_path / "d", leakage_path=leak, box_path=box)


@pytest.mark.parametrize(
    "change, code",
    [
        ({"peak_w": 120.0}, "case_outside_the_signed_box:peak_w"),
        ({"tim_thickness_mm": 0.3}, "case_outside_the_signed_box:tim_thickness_mm"),
        (
            {"start_offset_c": 30.0},
            "case_outside_the_signed_box:initial_c",
        ),  # the start is the coolant plus its offset
        ({"gap_s": 10.0}, "one_pulse_case_has_no_gap"),
    ],
)
def test_a_case_outside_the_signed_box_is_refused(tmp_path, signed, change, code):
    leak, box = signed
    with pytest.raises(v3.DeckRefused, match=code):
        v3.write_signed_case(
            {**CASE, **change}, tmp_path / "x", leakage_path=leak, box_path=box
        )
    missing = {k: v for k, v in CASE.items() if k != "tim_thickness_mm"}
    with pytest.raises(v3.DeckRefused, match="case_lacks_a_box_input:tim_thickness_mm"):
        v3.write_signed_case(missing, tmp_path / "y", leakage_path=leak, box_path=box)


def test_the_receipted_payload_files_load_under_the_real_pins():
    leak, box = (
        PAYLOAD / "leak_vth0_0p35_share2_SIGNED.json",
        PAYLOAD / "box-c6-signed.json",
    )
    if not (leak.is_file() and box.is_file()):
        pytest.skip(
            "the receipted F02 Stage-2 payload is custody-side, not in this checkout"
        )
    law = v3.load_leakage(leak, expect_sha256=v3.SIGNED_LEAKAGE_SHA256)
    assert (
        law["decision"] == v3.SIGNED_LEAKAGE_DECISION and law["label"] == "REGISTERED"
    )
    loaded = v3.load_signed_box(box)
    assert loaded["sha256"] == "sha256:" + v3.SIGNED_BOX_SHA256
    assert loaded["inputs"]["peak_w"] == (70.0, 90.0)
