"""The OWNER-PROVISIONAL Motor 1.8 crown values (Graphite-C template, committed WITH the values; no number is pinned here).

The committed registries must say exactly what the tracked record says: provisional, not measured, citing the owner's words,
registered under the "electric-motor-magnetics 1.8" version key (Motor 1.5's entries untouched), found only for the exact
exam, and the crown hold off only where the record says so. A measured replacement changes the values and the record, never
this structure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.challenge_validator import crown_average, crown_hold, koth_registry

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "scripts/validator_host_classes/records/crown_provisional_motor18.json"
#: The owner's later line (14 Nov, speed bundle): N = 3 rebuilds and margin_3; it supplements the first record (floor, noise, hold-off).
RECORD_N3 = (
    ROOT / "scripts/validator_host_classes/records/crown_provisional_motor18_n3.json"
)
CHALLENGE, VERSION = "electric-motor-magnetics", "1.8"
KEY = f"{CHALLENGE} {VERSION}"


def _record():
    return json.loads(RECORD.read_bytes())


def _sha():
    return "sha256:" + hashlib.sha256(RECORD.read_bytes()).hexdigest()


def _record_n3():
    return json.loads(RECORD_N3.read_bytes())


def _sha_n3():
    return "sha256:" + hashlib.sha256(RECORD_N3.read_bytes()).hexdigest()


def _exam(record=None, **changes):
    record = record or _record()
    return {
        "version": record["version"],
        "epoch": record["menu_epoch"],
        "evaluation_pack_digest": record["evaluation_pack_digest"],
        **changes,
    }


def test_the_record_says_provisional_not_measured_and_carries_the_owner_words():
    record = _record()
    assert record["kind"] == "OWNER_PROVISIONAL_NOT_MEASURED"
    assert (record["challenge"], record["version"]) == (CHALLENGE, VERSION)
    assert "FORWARD-ONLY" in record["replacement_rule"]
    words = record["owner_words_verbatim"]
    assert words.strip()
    digest = "sha256:" + hashlib.sha256(words.encode("utf-8")).hexdigest()
    assert record["owner_words_sha256"] == digest
    assert record["typed_in"] and record["typed_at"]


def test_the_record_is_canonical_lf_json():
    for path in (RECORD, RECORD_N3):
        raw = path.read_bytes()
        assert b"\r" not in raw and raw.endswith(b"\n")
        assert (
            json.dumps(json.loads(raw), indent=2, sort_keys=True).encode() + b"\n"
            == raw
        )


def test_the_n3_record_says_provisional_not_measured_forward_only_and_carries_the_words():
    record = _record_n3()
    first = _record()
    assert record["kind"] == "OWNER_PROVISIONAL_NOT_MEASURED"
    assert (record["challenge"], record["version"]) == (CHALLENGE, VERSION)
    assert (record["menu_epoch"], record["evaluation_pack_digest"]) == (
        first["menu_epoch"],
        first["evaluation_pack_digest"],
    )
    assert record["supplements"] == RECORD.name
    assert record["values"] == {"crown_n": 3, "crown_margin_3": 0.0129}
    assert "FORWARD-ONLY" in record["replacement_rule"]
    words = record["owner_words_verbatim"]
    assert (
        "N = 3" in words
        and "0.0129" in words
        and "no decided crown is re-decided" in words
    )
    digest = "sha256:" + hashlib.sha256(words.encode("utf-8")).hexdigest()
    assert record["owner_words_sha256"] == digest
    assert record["typed_in"] and record["typed_at"]


def test_every_1_8_entry_cites_the_record_by_its_sha():
    sha = _sha()
    rule = crown_average.load_rule()
    # the margin is the N = 3 record's (the owner's later line); the floor and the noise stay the first record's
    assert rule.margin_digest_for(CHALLENGE, VERSION) == _sha_n3()
    floors = [f for f in koth_registry._load_floors() if f["version"] == VERSION]
    assert len(floors) == 1 and floors[0]["measurement_digest"] == sha
    noise = koth_registry.rebuild_noise(CHALLENGE, version=VERSION)
    if _record()["values"]["rebuild_noise"] == "kept_registered_value":
        assert (
            noise["measurement_digest"] != sha
        )  # the existing registered noise, labelled kept
    else:
        assert (
            noise["measurement_digest"] == sha
            and noise["value"] == _record()["values"]["rebuild_noise"]
        )
    assert floors[0]["rebuild_noise_measurement_digest"] == noise["measurement_digest"]
    assert floors[0]["crown_margin_measurement_digest"] == _sha_n3()


def test_the_margin_and_the_floor_are_the_records():
    record = _record()
    rule = crown_average.load_rule()
    n3 = _record_n3()["values"]
    assert rule.margin_for(CHALLENGE, VERSION) == n3["crown_margin_3"]
    assert rule.n_for(CHALLENGE, VERSION) == n3["crown_n"] == 3
    assert (
        koth_registry.registered_floor(CHALLENGE, _exam(record))
        == record["values"]["crown_floor"]
    )


def test_the_floor_is_found_for_the_exact_exam_only():
    record = _record()
    assert koth_registry.registered_floor(CHALLENGE, _exam(record)) is not None
    for other in (
        {"evaluation_pack_digest": "sha256:" + "0" * 64},
        {"epoch": record["menu_epoch"] + "-other"},
        {"version": "1.7"},
    ):
        assert koth_registry.registered_floor(CHALLENGE, _exam(record, **other)) is None


def test_motor_1_5_keeps_its_own_registered_values():
    """The version key leaves every other version on the Challenge's entry (no 1.5 value is overwritten)."""
    sha = _sha()
    rule = crown_average.load_rule()
    assert rule.margin_digest_for(CHALLENGE) not in (sha, _sha_n3())
    assert rule.n_for(CHALLENGE, "1.5") == rule.n_for(CHALLENGE) == 10
    assert rule.margin_for(CHALLENGE, "1.5") == rule.margin_for(CHALLENGE)
    assert koth_registry.rebuild_noise(
        CHALLENGE, version="1.5"
    ) == koth_registry.rebuild_noise(CHALLENGE)


def test_the_crown_hold_is_off_only_where_the_record_says_so():
    record = _record()
    entry = crown_hold.registered_off(CHALLENGE, VERSION)
    if record["crown_hold"] == "OFF_REGISTERED":
        assert entry == {
            "menu_epoch": record["menu_epoch"],
            "evaluation_pack_digest": record["evaluation_pack_digest"],
        }
        document = json.loads(crown_hold.REGISTRY.read_bytes())
        (held,) = [
            h
            for h in document["holds"]
            if (h["challenge"], h["version"]) == (CHALLENGE, VERSION)
        ]
        assert held["authority"] == record["owner_words_sha256"]
    else:
        assert record["crown_hold"] == "ON_UNCHANGED" and entry is None
