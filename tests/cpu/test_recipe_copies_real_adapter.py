"""Recipe-once with the REAL `LeanRecipeAdapter` (V2B condition (3), RB door rs33, 9 Nov): no stand-in owner().

The live adapter's `owner()` reads the attempt ledger itself (`AttemptLedger.owned_outcome`: its own connection and
BEGIN IMMEDIATE on the same rollback-journal file), then checks the owner's provider still holds the retained request.
Called inside an open ledger transaction it waited out the busy timeout ('database is locked') and every submission
admitted after the release jammed the grade round. Here a NEW submission is admitted through the real signed door
(`Validator.evaluate`, a real durable task provider, a real on-disk ledger, real connections), after the rule's
activation, and both recipe-once paths that call the adapter run for real: the admission note and the grade-time
decision on a cache miss. Fixture material only (synthetic Challenge).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from test_direct_v3_durable_tasks import _fixture

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import (
    Adapters,
    AttemptLedger,
    Submission,
    Validator,
    direct_intake,
    recipe_copies,
)
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.development_session.construction_recipe import ConstructionRecipe

EXAM = "sha256:" + "e" * 64


def _admitted_door(tmp_path, monkeypatch):
    request, provider_factory, discovery = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    provider = provider_factory()
    attempt_root = tmp_path / "attempts"
    attempt_root.mkdir(mode=0o700)
    attempt_root.chmod(0o700)
    ledger = AttemptLedger(attempt_root / "ledger.sqlite3")
    adapter = LeanRecipeAdapter(
        discovery, lambda owner: provider if owner == "miner" else None, ledger
    )
    # the release step at the grader's first start: everything admitted from here on is under the rule
    recipe_copies.activate(ledger, adapter.contract_digest)
    door = Validator(Adapters([adapter]), ledger)
    submission = Submission(
        "miner",
        {"sequence": 1, "digest": "0" * 64},
        adapter.challenge_id,
        adapter.challenge_version,
        json.dumps(request.recipe, sort_keys=True),
        adapter.contract_digest,
    )
    result = door.evaluate(submission)
    assert result["kind"] == "OUTCOME"
    return request, adapter, ledger, result


def _decide(adapter, ledger, submission_id):
    return recipe_copies.decide(
        adapter=adapter,
        ledger=ledger,
        marker=lambda _sid: None,
        submission_id=submission_id,
        challenge_id=adapter.challenge_id,
        challenge_version=adapter.challenge_version,
        exam_key=EXAM,
    )


def test_a_new_submission_is_noted_and_decided_with_the_real_adapter(
    tmp_path, monkeypatch, capsys
):
    request, adapter, ledger, result = _admitted_door(tmp_path, monkeypatch)
    sid = result["outcome"]["submission_id"]
    assert adapter.owner(sid) == "miner"  # the real lookup, through the ledger
    # the admission note (real owner(), real connections): the digest is stored, nothing is said
    intake = SimpleNamespace(adapter=adapter)
    assert direct_intake.DirectRecipeIntake._note_recipe_digest(intake, result) is None
    expected = ConstructionRecipe.from_dict(request.recipe).digest
    assert recipe_copies.stored_digest(ledger, sid) == expected
    assert "recipe_digest_note_failed" not in capsys.readouterr().err
    # the grade-time decision: a lone first submission grades
    assert _decide(adapter, ledger, sid) == (recipe_copies.GRADE, None)


def test_the_grade_time_lookup_on_a_cache_miss_uses_the_real_adapter(
    tmp_path, monkeypatch
):
    """The exact rs33 path: the digest was never noted (the swallowed failure), so the decision itself must ask the
    real adapter for it; before the fix this raised OperationalError after the busy timeout."""
    request, adapter, ledger, result = _admitted_door(tmp_path, monkeypatch)
    sid = result["outcome"]["submission_id"]
    assert recipe_copies.stored_digest(ledger, sid) is None  # nothing noted
    assert _decide(adapter, ledger, sid) == (recipe_copies.GRADE, None)
    assert (
        recipe_copies.stored_digest(ledger, sid)
        == ConstructionRecipe.from_dict(request.recipe).digest
    )


def test_a_failing_note_is_said_never_silent(tmp_path, monkeypatch, capsys):
    _request, adapter, _ledger, result = _admitted_door(tmp_path, monkeypatch)

    def broken(_sid):
        raise RuntimeError("owner lookup failed")

    monkeypatch.setattr(adapter, "owner", broken)
    intake = SimpleNamespace(adapter=adapter)
    assert direct_intake.DirectRecipeIntake._note_recipe_digest(intake, result) is None
    assert "recipe_digest_note_failed" in capsys.readouterr().err  # the journal (stderr)
