"""Feedback v10-v12, the kit's side (miner-ux 6054; door-code a7d99b85; v2 FINAL 885): the kit asks for the newest reply the
door advertises, accepts back only its closed shape, and says in words what happened:

- v10 / v11: ``submission.failure_class`` = the closed public failure row (`infra_diagnosis.PUBLIC_ROW_KEYS`), Carbon's side on
  FAILED_INFRA, the recipe's side (v11) on RECONSTRUCTION_FAILED; on any other state it is None;
- v12: grade state RERUN + ``rerun_task_id`` (another id than the one asked) when the door re-ran the submission as a new task,
  else None; the kit prints 'Carbon re-ran this submission at no charge as <id>; read that id for its result' (v2 6069).

A reply of any other shape is refused whole, never trimmed. Synthetic replies only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.development_session import direct_submission as client
from carbon.development_session import infra_diagnosis
from scripts.dev.miner_launchpad import projection

SID = "rtsk_" + "a" * 64
NEW = "rtsk_" + "b" * 64
WORKER = {
    "cpu_model": "AMD EPYC",
    "cpu_count": 4,
    "memory_bytes": 16 * 1024**3,
    "gpu": False,
}
CARBON_ROW = infra_diagnosis.public_row(infra_diagnosis.UNCLASSIFIED)
YOURS_ROW = infra_diagnosis.recipe_spot_row()
FACTS = {
    "v2": client.FEEDBACK_V2_FACTS,
    "v3": client.FEEDBACK_V3_FACTS,
    "v4": client.FEEDBACK_V4_FACTS,
    "v5": client.FEEDBACK_V5_FACTS,
    "v6": client.FEEDBACK_V6_FACTS,
    "v7": client.FEEDBACK_V7_FACTS,
    "v8": client.FEEDBACK_V8_FACTS,
    "v9": client.FEEDBACK_V9_FACTS,
    "v10": client.FEEDBACK_V10_FACTS,
    "v11": client.FEEDBACK_V11_FACTS,
    "v12": client.FEEDBACK_V12_FACTS,
}
ALL = tuple(FACTS)
SCHEMAS = {
    "v9": client.FEEDBACK_REPLY_SCHEMA_V9,
    "v10": client.FEEDBACK_REPLY_SCHEMA_V10,
    "v11": client.FEEDBACK_REPLY_SCHEMA_V11,
    "v12": client.FEEDBACK_REPLY_SCHEMA_V12,
}


def _reply(version, grade_state, **extra):
    """A door reply body of ``version`` (v9..v12) for SID: v8's keys, then v10's / v12's."""
    submission = {
        "submission_id": SID,
        "grade_state": grade_state,
        "failure": None,
        "held_position": None,
        "gate_failures": None,
        "grade_worker": WORKER,
    }
    if version in ("v10", "v11", "v12"):
        submission["failure_class"] = None
    if version == "v12":
        submission["rerun_task_id"] = None
    submission.update(extra)
    return {
        "schema": SCHEMAS[version],
        "challenge": {"id": "electric-motor-magnetics", "version": "1.8"},
        "best": None,
        "latest": None,
        "submission": submission,
    }


def _kit(monkeypatch, reply, versions=ALL):
    """Read ``reply`` through `read_exam_feedback` against a door advertising ``versions``; returns (result, fields sent)."""
    sent = []
    recipe = object.__new__(client.ConstructionRecipe)
    monkeypatch.setattr(
        client.ConstructionRecipe,
        "to_dict",
        lambda self: {
            "challenge": {"id": "electric-motor-magnetics", "version": "1.8"}
        },
    )
    monkeypatch.setattr(client, "_body", lambda facts, **kw: {"fields": kw["fields"]})
    monkeypatch.setattr(
        client,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {}),
    )
    facts = {"exam_feedback": client.FEEDBACK_FACTS}
    facts.update({"exam_feedback_" + v: FACTS[v] for v in versions})

    def send(url, body, headers):
        sent.append(body["fields"])
        return 200, reply

    got = client.read_exam_feedback(
        "http://127.0.0.1:1",
        "external-signer",
        recipe=recipe,
        contract_digest="sha256:" + "c" * 64,
        receiver="validator",
        context=None,
        read=lambda url: facts,
        send=send,
        submission_id=SID,
    )
    return got, sent[-1]


def test_the_kit_pins_the_doors_v10_to_v12_values():
    assert client.FEEDBACK_REPLY_SCHEMA_V10 == direct_intake.FEEDBACK_REPLY_SCHEMA_V10
    assert client.FEEDBACK_REPLY_SCHEMA_V11 == direct_intake.FEEDBACK_REPLY_SCHEMA_V11
    assert client.FEEDBACK_REPLY_SCHEMA_V12 == direct_intake.FEEDBACK_REPLY_SCHEMA_V12
    assert client.RERUN_STATE == direct_intake.RERUN_STATE == "RERUN"
    assert client.FAILURE_CLASS_KEYS == infra_diagnosis.PUBLIC_ROW_KEYS
    assert client.GRADE_STATES_V12 == (*client.GRADE_STATES_V9, "RERUN")
    for name in ("v10", "v11", "v12"):
        assert FACTS[name] == {
            **client.FEEDBACK_FACTS,
            "fields": ["reply", "submission_id"],
            "reply_schema": SCHEMAS[name],
        }
        assert (
            direct_intake.feedback_reply({"reply": name, "submission_id": SID}) == name
        )


@pytest.mark.parametrize(
    ("versions", "asked"),
    [(ALL, "v12"), (ALL[:-1], "v11"), (ALL[:-2], "v10"), (ALL[:-3], "v9")],
)
def test_the_kit_asks_for_the_newest_reply_advertised(monkeypatch, versions, asked):
    got, sent = _kit(monkeypatch, _reply(asked, "QUEUED"), versions)
    assert sent == {"reply": asked, "submission_id": SID}
    assert got["submission"]["grade_state"] == "QUEUED"


def test_a_v12_rerun_names_the_new_id_and_the_kit_says_read_that_id(monkeypatch):
    got, _ = _kit(monkeypatch, _reply("v12", "RERUN", rerun_task_id=NEW))
    assert got["submission"]["rerun_task_id"] == NEW
    why = projection._grade(
        {"best": None, "latest": None, "submission": got["submission"]},
        submission="sha256:" + "d" * 64,
        task=SID,
    )["why"]
    assert why["grade_state"] == "RERUN" and why["rerun_task_id"] == NEW
    assert why["words"].startswith(
        "Carbon re-ran this submission at no charge as "
        + NEW
        + "; read that id for its result"
    )


def test_failure_class_rows_read_on_their_own_state_only(monkeypatch):
    got, _ = _kit(
        monkeypatch, _reply("v10", "FAILED_INFRA", failure_class=CARBON_ROW), ALL[:-2]
    )
    assert got["submission"]["failure_class"] == CARBON_ROW
    why = projection._grade(
        {"best": None, "latest": None, "submission": got["submission"]},
        submission="sha256:" + "d" * 64,
        task=SID,
    )["why"]
    assert why["failure_class"] == CARBON_ROW
    assert CARBON_ROW["what_happened"].rstrip(".") in why["words"]
    got, _ = _kit(
        monkeypatch,
        _reply("v11", "RECONSTRUCTION_FAILED", failure_class=YOURS_ROW),
        ALL[:-1],
    )
    assert got["submission"]["failure_class"]["side"] == "yours"
    # v10 has no recipe-side row; a Carbon row on the recipe's state (or the reverse) is refused whole
    for version, state, row, versions in (
        ("v10", "RECONSTRUCTION_FAILED", YOURS_ROW, ALL[:-2]),
        ("v11", "FAILED_INFRA", YOURS_ROW, ALL[:-1]),
        ("v11", "RECONSTRUCTION_FAILED", CARBON_ROW, ALL[:-1]),
        ("v11", "GRADED", CARBON_ROW, ALL[:-1]),
        ("v10", "FAILED_INFRA", {**CARBON_ROW, "host": "x"}, ALL[:-2]),
        ("v10", "FAILED_INFRA", {**CARBON_ROW, "what_happened": "a" * 401}, ALL[:-2]),
        ("v10", "FAILED_INFRA", {**CARBON_ROW, "charged": "no"}, ALL[:-2]),
    ):
        with pytest.raises(client.DirectIntakeRefusal):
            _kit(monkeypatch, _reply(version, state, failure_class=row), versions)


def test_every_row_the_door_can_send_passes_the_kits_check():
    """A future sentence over the kit's bound fails HERE, not as a refused live reply."""
    for name in sorted(infra_diagnosis.FAILURE_TABLE):
        row = infra_diagnosis.public_row(name)
        assert client._failure_class_v10("FAILED_INFRA", row, v11=False), name
    assert client._failure_class_v10("RECONSTRUCTION_FAILED", YOURS_ROW, v11=True)


@pytest.mark.parametrize(
    "submission",
    [
        {"grade_state": "RERUN", "rerun_task_id": None},  # RERUN without the new id
        {"grade_state": "QUEUED", "rerun_task_id": NEW},  # an id on another state
        {"grade_state": "RERUN", "rerun_task_id": SID},  # the asked id itself
        {"grade_state": "RERUN", "rerun_task_id": "not an id"},
        {"grade_state": "RERUN", "rerun_task_id": NEW, "extra": 1},
    ],
)
def test_a_v12_reply_of_any_other_shape_is_refused_whole(monkeypatch, submission):
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(monkeypatch, _reply("v12", **submission))


def test_an_older_schema_where_v12_was_asked_and_rerun_before_v12_are_refused(
    monkeypatch,
):
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(monkeypatch, _reply("v11", "QUEUED"))  # asked v12, answered v11
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(monkeypatch, _reply("v11", "RERUN"), ALL[:-1])  # RERUN is v12's state only
