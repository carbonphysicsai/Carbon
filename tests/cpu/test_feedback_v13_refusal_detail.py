"""The closed detail code of a refused graph build (owner G-LEAD-78, 24 Nov 2026): kept in that task's record, shown to its own
miner in feedback v13, and nothing else added.

Claims: only a registered candidate refusal of the closed build table is kept; it is bound to its task and its receipt; a task
refused before the code was kept, or refused another way, has none; v13 is opt-in and every older reply is unchanged.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake, lean_recipe
from carbon.development_session import build_refusal_v2
from carbon.development_session import research_tasks as rt
from carbon.research import DirectTaskStateV3

CODE = "graph_route_nonfinite_state"


@dataclasses.dataclass(frozen=True)
class _View:
    task_id: object
    state: object
    revision: int = 1
    updated_at_micros: int = 1
    terminal_receipt: object = None


@pytest.fixture
def provider(monkeypatch):
    """A task provider holding one view and the evidence table alone."""
    monkeypatch.setattr(rt, "canonical_bytes", lambda value: repr(value).encode())
    found = rt.DirectDevelopmentTasksV3.__new__(rt.DirectDevelopmentTasksV3)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE direct_evidence (id TEXT PRIMARY KEY, body BLOB)")
    view = _View(SimpleNamespace(value="rtsk_a"), DirectTaskStateV3.RUNNING)
    found._views = {"rtsk_a": view}
    found._requests = {"rtsk_a": object()}
    found.saved = []

    def save(request, updated, cancellation, *, failure_evidence, infra_diagnosis):
        del request, cancellation
        found._views["rtsk_a"] = updated
        found.saved.append((failure_evidence, infra_diagnosis))
        if failure_evidence is not None:
            db.execute(
                "INSERT INTO direct_evidence VALUES(?,?)",
                ("rtsk_a", json.dumps(failure_evidence).encode()),
            )

    @contextlib.contextmanager
    def opened():
        yield db

    found._save, found._db, found.db = save, opened, db
    return found


def _refuse(provider, detail, receipt="receipt"):
    return provider._transition(
        provider._views["rtsk_a"],
        DirectTaskStateV3.REFUSED,
        receipt=receipt,
        refusal_detail=detail,
    )


# -- what is kept ---------------------------------------------------------------------------------------------------------------


def test_only_a_registered_candidate_refusal_is_a_detail_code():
    assert rt.closed_refusal_detail(CODE) == CODE
    refused = [
        c for c, o in build_refusal_v2.CODES.items() if o == build_refusal_v2.REFUSED
    ]
    assert refused and all(rt.closed_refusal_detail(c) == c for c in refused)
    gaps = [
        c for c, o in build_refusal_v2.CODES.items() if o != build_refusal_v2.REFUSED
    ]
    for other in (
        *gaps,
        "not_a_registered_code",
        "graph_route_nonfinite_state_at_row_7",
        "",
        None,
        7,
        ["graph_route_nonfinite_state"],
    ):
        assert rt.closed_refusal_detail(other) is None


def test_the_record_is_the_code_bound_to_its_task_and_receipt_and_nothing_else(
    provider,
):
    _refuse(provider, CODE)
    ((evidence, diagnosis),) = provider.saved
    assert diagnosis is None
    assert set(evidence) == {"schema", "task_id", "receipt_digest", "detail_code"}
    assert (evidence["detail_code"], evidence["task_id"]) == (CODE, "rtsk_a")
    assert provider.refusal_detail(SimpleNamespace(value="rtsk_a")) == CODE
    # the bundle refusal reader does not read it as its own
    assert provider.private_refusal(SimpleNamespace(value="rtsk_a")) is None


def test_a_refusal_with_no_code_or_another_refusal_has_none(provider):
    _refuse(provider, None)
    assert provider.saved == [(None, None)]
    assert provider.refusal_detail(SimpleNamespace(value="rtsk_a")) is None
    provider.db.execute(
        "INSERT INTO direct_evidence VALUES(?,?)",
        ("rtsk_a", json.dumps({"schema": "carbon.direct-build-refusal.v1"}).encode()),
    )
    assert provider.refusal_detail(SimpleNamespace(value="rtsk_a")) is None


@pytest.mark.parametrize(
    "state", [s for s in DirectTaskStateV3 if s is not DirectTaskStateV3.REFUSED]
)
def test_no_other_state_has_a_detail_code(provider, state):
    _refuse(provider, CODE)
    provider._views["rtsk_a"] = dataclasses.replace(
        provider._views["rtsk_a"], state=state
    )
    assert provider.refusal_detail(SimpleNamespace(value="rtsk_a")) is None
    assert provider.refusal_detail(SimpleNamespace(value="unknown")) is None


def test_a_detail_code_needs_a_terminal_refusal(provider):
    view = provider._views["rtsk_a"]
    for state, receipt in (
        (DirectTaskStateV3.CANCELLED, "receipt"),
        (DirectTaskStateV3.REFUSED, None),
    ):
        with pytest.raises(ValueError, match="terminal refusal receipt"):
            provider._transition(view, state, receipt=receipt, refusal_detail=CODE)
    assert provider.saved == []


@pytest.mark.parametrize(
    "change",
    [
        {"task_id": "rtsk_b"},
        {"receipt_digest": "sha256:" + "0" * 64},
        {"detail_code": "not_a_registered_code"},
        {"tail": "worker text"},
    ],
)
def test_a_record_that_is_not_this_tasks_own_refuses(provider, change):
    _refuse(provider, CODE)
    ((evidence, _diagnosis),) = provider.saved
    provider.db.execute(
        "UPDATE direct_evidence SET body=?",
        (json.dumps({**evidence, **change}).encode(),),
    )
    with pytest.raises(ValueError, match="custody differs"):
        provider.refusal_detail(SimpleNamespace(value="rtsk_a"))


def test_the_build_path_keeps_the_code_only_for_a_refused_graph():
    text = Path(rt.__file__).read_text(encoding="utf-8")
    assert "closed_refusal_detail(graph_decision.detail_code)" in text
    kept = text.split("refusal_detail=(", 1)[1][:260]
    assert "graph_decision is not None" in kept
    assert "state is DirectTaskStateV3.REFUSED" in kept


# -- what a miner sees ------------------------------------------------------------------------------------------------------------


def _intake(reader):
    door = direct_intake.DirectRecipeIntake.__new__(direct_intake.DirectRecipeIntake)
    door.adapter = SimpleNamespace(refusal_detail=reader)
    return door


def test_the_door_serves_the_closed_code_or_nothing():
    asked = []

    def kept(submission_id):
        asked.append(submission_id)
        return CODE

    assert _intake(kept)._refusal_detail("rtsk_a") == CODE
    assert asked == ["rtsk_a"]

    def failing(submission_id):
        raise ValueError("custody differs")

    for reader in (lambda s: None, lambda s: "worker text", failing):
        assert _intake(reader)._refusal_detail("rtsk_a") is None
    bare = direct_intake.DirectRecipeIntake.__new__(direct_intake.DirectRecipeIntake)
    bare.adapter = SimpleNamespace()
    assert bare._refusal_detail("rtsk_a") is None


def test_the_adapter_reads_only_the_owners_own_task():
    seen = []
    adapter = lean_recipe.LeanRecipeAdapter.__new__(lean_recipe.LeanRecipeAdapter)
    adapter.owner = lambda submission_id: None
    assert adapter.refusal_detail("rtsk_" + "a" * 64) is None
    adapter.owner = lambda submission_id: "owner"
    adapter._provider = lambda owner: SimpleNamespace(
        refusal_detail=lambda task_id: seen.append((owner, task_id.value)) or CODE
    )
    assert adapter.refusal_detail("rtsk_" + "a" * 64) == CODE
    assert seen == [("owner", "rtsk_" + "a" * 64)]
    adapter._provider = lambda owner: SimpleNamespace()
    assert adapter.refusal_detail("rtsk_" + "a" * 64) is None


def test_v13_is_opt_in_advertised_and_every_older_reply_is_unchanged():
    for reply in ("v3", "v12", "v13", "v14"):
        fields = {"reply": reply, "submission_id": "t"}
        assert direct_intake.feedback_reply(fields) == reply
    assert direct_intake.feedback_reply({"reply": "v15", "submission_id": "t"}) is None
    assert direct_intake.FEEDBACK_REPLY_SCHEMA_V13.endswith(".v13")
    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v13"' in text
    assert 'v13=reply in ("v13", "v14")' in text
    assert '**({"refusal_detail": refusal_detail} if v13 else {})' in text
