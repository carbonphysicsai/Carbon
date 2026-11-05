"""M2, the ruled amendment (Validator 5 Nov 06:49): a carried owner's manifest migrates across a grading-path change ONLY
under a declared exam change whose revisions are OLD..NEW and whose paths EQUAL the computed changed grading paths.

Claims: declared == computed migrates and logs ``owner_manifest_migration_declared``; one path off, other revisions, or
no record refuses exactly as before (``owner_manifest_migration_refused``); an unknown change never migrates; the record
is closed and checked in the receiver configuration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_owner_manifest_migration import (
    NEW,
    OLD,
    Ledger,
    _manifest,
    _migrate,
    served,  # noqa: F401 - fixture
)

from carbon.challenge_validator import direct_receiver as dr

TOUCHED = ("carbon/battery/pool_store.py", "carbon/scoring/pool_exam.py")


def _declared(**changes):
    return {
        "from_revision": OLD,
        "to_revision": NEW,
        "paths": list(TOUCHED),
        "reason": "new pool versions only, off by default: grades nothing on these doors",
        "evidence_sha256": "sha256:" + "e" * 64,
        **changes,
    }


@pytest.fixture
def changed(monkeypatch, served):  # noqa: F811
    monkeypatch.setattr(dr, "_grading_change", lambda old, new, root=None: TOUCHED)
    monkeypatch.setattr(dr, "DECLARED_EXAM_CHANGE", None)
    return served


def _event(capsys):
    return json.loads(capsys.readouterr().err.strip().splitlines()[-1])


def test_a_declaration_equal_to_the_computed_change_migrates_and_says_so(
    tmp_path, changed, capsys
):
    dr.install_declared_change({"declared_exam_change": _declared()})
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(tmp_path, frozen, [changed])
    assert _migrate(ledger, frozen, candidate) is True
    assert ledger.manifest() == candidate
    said = json.loads(capsys.readouterr().err.strip().splitlines()[0])
    assert said["event"] == "owner_manifest_migration_declared"
    assert (
        said["paths"] == list(TOUCHED)
        and said["evidence_sha256"] == "sha256:" + "e" * 64
    )


@pytest.mark.parametrize(
    "declared",
    [
        None,
        _declared(paths=[TOUCHED[0]]),  # one path off
        _declared(
            paths=[*TOUCHED, "carbon/scoring/pool_grader.py"]
        ),  # one path too many
        _declared(to_revision="c" * 40),  # another migration
    ],
)
def test_anything_but_an_exact_declaration_refuses_as_before(
    tmp_path, changed, capsys, declared
):
    dr.install_declared_change(
        {} if declared is None else {"declared_exam_change": declared}
    )
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(tmp_path, frozen, [changed])
    assert _migrate(ledger, frozen, candidate) is False
    assert ledger.manifest() == frozen
    said = _event(capsys)
    assert (
        said["event"] == "owner_manifest_migration_refused"
        and said["reason"] == "grading_path_changed"
    )


def test_an_unknown_change_never_migrates_even_when_declared(
    tmp_path, changed, monkeypatch, capsys
):
    monkeypatch.setattr(dr, "_grading_change", lambda old, new, root=None: None)
    dr.install_declared_change({"declared_exam_change": _declared()})
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    assert _migrate(Ledger(tmp_path, frozen, [changed]), frozen, candidate) is False
    assert _event(capsys)["reason"] == "grading_change_unknown"


@pytest.mark.parametrize(
    "bad",
    [
        {k: v for k, v in _declared().items() if k != "reason"},
        {**_declared(), "extra": 1},
        _declared(from_revision="a" * 12),
        _declared(paths=[]),
        _declared(paths=[TOUCHED[0], TOUCHED[0]]),
        _declared(reason=" "),
        _declared(evidence_sha256="e" * 64),
        "declared",
    ],
)
def test_the_record_is_closed(bad, monkeypatch):
    monkeypatch.setattr(dr, "DECLARED_EXAM_CHANGE", None)
    with pytest.raises(ValueError, match="invalid declared_exam_change"):
        dr.install_declared_change({"declared_exam_change": bad})
    with pytest.raises(ValueError, match="invalid declared_exam_change"):
        dr._check_declared_change(bad)
