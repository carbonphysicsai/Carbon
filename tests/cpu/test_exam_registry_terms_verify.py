"""Submission terms and the practice verify set of a new version come from its exam registry row; no live version moves.

The literals were read from main before the change. Every registry case runs in a fresh interpreter, synthetic rows only.
A terms row that cannot be read never reads as "no terms" (owner G-LEAD-50: no terms, no submission).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.challenge_kit import verify_practice
from carbon.challenge_registry import exam_registry
from carbon.challenge_validator import submission_terms as st

REPOSITORY = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
TERMS = "carbon-submission-terms-v0"
TERMS_SHA = "946244f64b9c8580010595822ad997eb22e7184dd4074dfca808868c30232faa"
SETS = {
    (MOTOR, "1.8"): (
        "kits/motor/verify_set.json",
        "e6179607b3790ac0b05658b1ee4019478a6aac9c2f3bb787a74f96cedc1c7327",
    ),
    ("chip-cold-plate", "1.8"): (
        "kits/cooling/verify_set.json",
        "59dabd83e1484cac28e3ad811aac2cba325d3d8ffc994e37b2e0c78063a15bb0",
    ),
}
LIVE = [
    (MOTOR, "1.8", None),
    (MOTOR, "1.9", TERMS),
    ("chip-cold-plate", "1.8", None),
    ("f08-ribbed-bracket", "1.7", None),
    ("f08-ribbed-bracket", "2.0", TERMS),
    ("f02", "2.5", None),
]
TEXT = b"Synthetic terms.\n"
TEXT_SHA = hashlib.sha256(TEXT).hexdigest()

_PROGRAM = r"""
import json, sys
from carbon.challenge_kit import verify_practice, version_overlay
from carbon.challenge_registry import exam_registry
from carbon.challenge_validator import submission_terms
version_overlay.install(path=sys.argv[1])
exam_registry.install(sys.argv[2])


def ask(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as refused:
        return "refused: " + type(refused).__name__


def door(text):
    terms = submission_terms.for_door("zz-synthetic", "0.1", text)
    return None if terms is None else [terms.version, terms.sha256, terms.ready]


def practice():
    found = verify_practice.source("zz-synthetic", "0.1", root=sys.argv[3])
    return None if found is None else [found.case_ids, found.sha256]


print(json.dumps({
    "required": ask(submission_terms.required_version, "zz-synthetic", "0.1"),
    "door": door(sys.argv[4]),
    "no_text": door(None),
    "registered": ask(verify_practice.registered, "zz-synthetic", "0.1"),
    "source": ask(practice),
    "live_terms": [
        submission_terms.required_version(c, v) for c, v in json.loads(sys.argv[5])
    ],
    "live_sets": [
        verify_practice.entry_of(c, v) for c, v in json.loads(sys.argv[5])
    ],
}))
"""


def _run(tmp_path, row):
    overlay = tmp_path / "overlay.json"
    entry = {
        "challenge_id": "zz-synthetic",
        "version": "0.1",
        "train": "zz-synthetic-train-v1",
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "zz-synthetic-normal-construction-development-1",
        "development_evaluation": None,
        "sealed_evaluation": "zz-synthetic-pool-sealed-v1",
        "campaign": "catalog",
    }
    document = {
        "schema": "carbon.challenge-kit.version-overlay.v1",
        "versions": {"zz-synthetic 0.1": entry},
    }
    overlay.write_text(json.dumps(document), encoding="utf-8")
    registry = tmp_path / "exam_registry.json"
    rows = {} if row is None else {"zz-synthetic 0.1": row}
    document = {"schema": exam_registry.SCHEMA, "source": "test", "exams": rows}
    registry.write_text(json.dumps(document), encoding="utf-8")
    text = tmp_path / "terms.md"
    text.write_bytes(TEXT)
    live = json.dumps([[c, v] for c, v, _ in LIVE])
    argv = [str(overlay), str(registry), str(tmp_path), str(text), live]
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM, *argv],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    out = json.loads(done.stdout.strip().splitlines()[-1])
    # whatever the row says, no live version's terms or verify set move
    assert out["live_terms"] == [terms for *_, terms in LIVE]
    assert out["live_sets"] == [
        list(SETS[(c, v)]) if (c, v) in SETS else None for c, v, _ in LIVE
    ]
    return out


def _set(tmp_path, designs):
    raw = json.dumps({"designs": designs}).encode()
    (tmp_path / "verify_set.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    return {"path": "verify_set.json", "sha256": digest}


DESIGN = {"case_id": "v-0", "inputs": {"a": 1, "b": 2.5}, "truth": {"y": [1.0, 2.0]}}


def test_every_live_version_answers_as_main_did():
    assert verify_practice.REGISTRY == SETS
    assert st.TERMS_BY_VERSION == {
        (MOTOR, "1.9"): TERMS,
        ("f08-ribbed-bracket", "2.0"): TERMS,
    }
    assert st.PINNED_SHA256 == {TERMS: TERMS_SHA}
    for challenge, version, terms in LIVE:
        assert st.required_version(challenge, version) == terms
        assert verify_practice.entry_of(challenge, version) == SETS.get(
            (challenge, version)
        )
        door = st.for_door(challenge, version, None)
        assert (door and (door.version, door.sha256)) == (
            None if terms is None else (TERMS, TERMS_SHA)
        )


def test_a_row_names_the_terms_and_the_door_serves_only_their_pinned_text(tmp_path):
    out = _run(tmp_path, {"terms": {"version": "zz-terms-v0", "sha256": TEXT_SHA}})
    assert out["required"] == "zz-terms-v0"
    assert out["door"] == ["zz-terms-v0", TEXT_SHA, True]
    assert out["no_text"] == ["zz-terms-v0", TEXT_SHA, False]


def test_a_row_without_terms_accepts_nothing_and_a_version_without_a_row_is_unchanged(
    tmp_path,
):
    out = _run(tmp_path, {"solver_seconds_per_design": {"value": 1, "source": "s"}})
    assert out["required"] == "refused: TermsUnavailable"
    assert out["door"] == out["no_text"] == [st.UNREADABLE, None, False]
    assert out["registered"] is False and out["source"] is None
    out = _run(tmp_path, None)
    assert out["required"] is None and out["door"] is None
    assert out["registered"] is False and out["source"] is None


@pytest.mark.parametrize(
    "terms",
    [
        {"version": "zz-terms-v0", "sha256": "short"},
        {"version": "zz-terms-v0"},
        # a terms version pinned in code keeps its one text
        {"version": TERMS, "sha256": "d" * 64},
    ],
)
def test_terms_that_cannot_be_read_refuse_every_submission(tmp_path, terms):
    out = _run(tmp_path, {"terms": terms})
    assert out["required"] == "refused: TermsUnavailable"
    assert out["door"] == out["no_text"] == [st.UNREADABLE, None, False]


def test_a_row_may_name_the_published_terms_at_their_own_pin(tmp_path):
    out = _run(tmp_path, {"terms": {"version": TERMS, "sha256": TERMS_SHA}})
    assert out["required"] == TERMS
    assert out["door"] == [TERMS, TERMS_SHA, False]  # another text: not ready


def test_a_rows_verify_set_loads_only_at_its_receipted_digest(tmp_path):
    entry = _set(tmp_path, [DESIGN, {**DESIGN, "case_id": "v-1"}])
    out = _run(tmp_path, {"verify_set": entry})
    assert out["registered"] is True
    assert out["source"] == [["v-0", "v-1"], entry["sha256"]]
    out = _run(tmp_path, {"verify_set": {**entry, "sha256": "0" * 64}})
    assert out["source"] == "refused: VerifyPracticeRefused"
    out = _run(tmp_path, {"verify_set": {**entry, "path": "absent.json"}})
    assert out["source"] == "refused: VerifyPracticeRefused"


@pytest.mark.parametrize(
    "designs",
    [
        [],
        [DESIGN, DESIGN],
        [DESIGN, {**DESIGN, "case_id": "v-1", "inputs": {"a": 1}}],
        [{**DESIGN, "inputs": {"a": True, "b": 1}}],
        [{**DESIGN, "inputs": {}}],
        [{**DESIGN, "inputs": [1]}],
        [{**DESIGN, "truth": {}}],
        [{**DESIGN, "truth": {"y": [float("nan")]}}],
        ["v-0"],
    ],
)
def test_a_malformed_verify_set_refuses(tmp_path, designs):
    out = _run(tmp_path, {"verify_set": _set(tmp_path, designs)})
    assert out["source"] == "refused: VerifyPracticeRefused"
