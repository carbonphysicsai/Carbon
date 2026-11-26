"""A door closed to new submissions (owner MOTOR18-CLOSE-NOT-REFRESH, 25 Nov 2026, verbatim: "approved: after the king
verdict, close Motor 1.8 to new submissions instead of refreshing it; 1.8 retires at the first 1.9 king."; v2 8306: a door
STATE, not a new version; live-ops 8300, door-code 8307).

Claims:
1. CONFIG: ``closed_to_new_submissions`` is optional and only ``true`` is accepted; absent, the config is as before.
2. REFUSAL: a closed door answers a submit and a source stage 410 ``version_closed`` with the fixed notice, after the
   signature check, and admits or stages nothing (so no build or grade round can start).
3. READS STAY OPEN: the caller's own status, feedback and withdraw answer exactly as on an open door.
4. OPEN DOOR: without the key, a source stage reaches staging as before.
5. INFO: the public intake facts say ``closed_to_new_submissions: true`` only on a closed door.

Every value is a SYNTHETIC fixture.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery.intake import Answer
from carbon.challenge_validator import direct_intake as di
from carbon.challenge_validator import direct_receiver as receiver

ROOT = Path(__file__).resolve().parents[2]
RECEIVER = "5" + "3" * 47
HOTKEY = "5" + "1" * 47


def _config(tmp_path):
    return {
        "schema": receiver.SCHEMA,
        "root": str(tmp_path / "receiver"),
        "runner_profile": str(tmp_path / "profile.json"),
        "host": "127.0.0.1",
        "port": 8767,
        "receiver_hotkey": RECEIVER,
        "lifetime_seconds": 30,
        "measure_query": True,
    }


# ---------------------------------------------------------------- 1. config


def test_the_key_is_optional_and_true_is_accepted(tmp_path, monkeypatch):
    closed = {**_config(tmp_path), "closed_to_new_submissions": True}
    for cfg in (_config(tmp_path), closed):
        monkeypatch.setattr(receiver, "private_json", lambda _, cfg=cfg: cfg)
        assert receiver.load_config(tmp_path / "config.json") == cfg


@pytest.mark.parametrize("value", [False, 1, "true", None, {}])
def test_any_other_value_refuses_the_start(tmp_path, monkeypatch, value):
    cfg = {**_config(tmp_path), "closed_to_new_submissions": value}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    with pytest.raises(ValueError):
        receiver.load_config(tmp_path / "config.json")


def test_the_receiver_sets_the_state_on_its_intake_at_start():
    source = (ROOT / "carbon/challenge_validator/direct_receiver.py").read_text(
        encoding="utf-8"
    )
    at = source.index("intake.version_closed = _version_closed(cfg)")
    assert 'cfg.get("closed_to_new_submissions") is True' in source[at : at + 600]


# ---------------------------------------------------------------- 2 to 4. the POST path


class _Gateway:
    received = None

    def __init__(self, *args, **kwargs):
        pass

    async def receive(self, body, headers, *, method, path):
        return _Gateway.received


def _received(tool, fields=()):
    return SimpleNamespace(
        call=SimpleNamespace(
            tool=tool,
            fields=[SimpleNamespace(name=n, value=v) for n, v in fields],
        ),
        receipt=SimpleNamespace(
            hotkey=HOTKEY,
            ref=SimpleNamespace(sequence=1, digest="sha256:" + "0" * 64),
            finalized_block=7200,
        ),
    )


class _Door:
    """A STAND-IN intake: records whatever would admit, stage or read."""

    def __init__(self, closed):
        self.calls = []
        if closed is not None:
            self.closed_to_new_submissions = closed
        self.window = SimpleNamespace(get=lambda snapshot: object())
        self.context = self.challenge = self.receiver = None
        self.verifier = self.journal = None
        self.clock_ns = lambda: 0
        self.submission_terms = None
        self.adapter = SimpleNamespace(contract_digest="sha256:" + "c" * 64)
        self.door = SimpleNamespace(
            outcome=lambda *a: self.calls.append("status") or {"state": "QUEUED"}
        )

    def _verified_charge(self, received):
        return True

    def _unverified(self, answer):
        return answer

    def _stage(self, received):
        self.calls.append("stage")
        return Answer(200, {"staged": True})

    def _admit(self, submitted):
        self.calls.append("admit")
        return {"kind": "OUTCOME"}

    def _feedback(self, hotkey, **kwargs):
        self.calls.append("feedback")
        return Answer(200, {"feedback": True})

    def _withdraw(self, hotkey, fields):
        self.calls.append("withdraw")
        return Answer(200, {"withdrawn": True})


@pytest.fixture
def post(monkeypatch):
    monkeypatch.setattr(di, "parse_message", lambda body: {"snapshot": "s"})
    monkeypatch.setattr(di, "AuthenticatedGateway", _Gateway)

    def run(door, received):
        _Gateway.received = received
        return asyncio.run(di.DirectRecipeIntake._post(door, {}, b"{}"))

    return run


SUBMIT = (
    di.SUBMIT_TOOL,
    (("strategy_json", "{}"), ("contract_digest", "sha256:" + "c" * 64)),
)
STAGE = (di.RESEARCH_NAMESPACE, (("call_base64", "AA=="),))


@pytest.mark.parametrize("tool,fields", [SUBMIT, STAGE])
def test_a_closed_door_refuses_a_submit_and_a_stage_and_admits_nothing(
    post, tool, fields
):
    door = _Door(True)
    answer = post(door, _received(tool, fields))
    assert answer.status == 410
    assert answer.body == {"refused": "version_closed", "message": di.CLOSED_NOTICE}
    assert door.calls == []
    # the words name no miner and no number
    assert HOTKEY not in json.dumps(answer.body)
    assert not any(ch.isdigit() for ch in di.CLOSED_NOTICE)


@pytest.mark.parametrize(
    "tool,fields,call",
    [
        (di.STATUS_TOOL, (("submission_id", "rtsk_1"),), "status"),
        (di.FEEDBACK_TOOL, (), "feedback"),
        (di.WITHDRAW_TOOL, (("submission_id", "rtsk_1"),), "withdraw"),
    ],
)
def test_the_callers_own_reads_answer_as_on_an_open_door(post, tool, fields, call):
    answers = []
    for closed in (True, None):
        door = _Door(closed)
        answers.append(post(door, _received(tool, fields)))
        assert door.calls == [call]
    assert answers[0].status == answers[1].status == 200
    assert answers[0].body == answers[1].body


def test_an_open_door_stages_as_before(post):
    for closed in (None, False):
        door = _Door(closed)
        answer = post(door, _received(*STAGE))
        assert answer.status == 200 and door.calls == ["stage"]


# ---------------------------------------------------------------- 5. the public facts


def test_the_public_facts_say_closed_only_on_a_closed_door():
    source = (ROOT / "carbon/challenge_validator/direct_intake.py").read_text(
        encoding="utf-8"
    )
    public = source[source.index("    def public(self):") :][:6000]
    assert '{"closed_to_new_submissions": True}' in public
    assert 'getattr(self, "closed_to_new_submissions", False)' in public
