"""The Launchpad's Level 4 envelope transport (LAUNCHPAD-LEVELS-01 S4).

A Level 4 candidate's frozen staging envelope is sent ahead of its
`battery_submit` as signed `battery_level4_part` calls (VALIDATOR-25 slice 4,
`carbon.battery.level4_parts`). Claims tested:

1. A fixture ladder intake serving Level 4 (its public `tools` list the part
   tools, its `served_contracts` the Level 4 variant) receives every part,
   then the submission; the parts it holds join back to the frozen bytes.
2. A resumed send uploads only the parts the intake lacks, and a replay of a
   whole send uploads none.
3. A part the intake holds with other bytes, or another part count, is a typed
   refusal with a next step, never retried; nothing is submitted.
4. An intake that takes no envelope parts still refuses
   `level4_envelope_transport_unavailable` before anything is signed: on the
   Launchpad's pre-sign check, in the campaign and in the transport itself.
5. Levels 0-3 send no part and need no part tools.

The intake is the real `BatteryIntake` part handler over a real
`Level4Parts` store, reached through the real message bytes; signing goes
through a stand-in, because Carbon never holds a key.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.battery import campaign
from carbon.battery import intake as ib
from carbon.battery import remote_submission as rs
from carbon.battery.challenge import CHALLENGE
from carbon.battery.level4_parts import (
    FIELD,
    MAX_PARTS,
    PART_BYTES,
    Level4Parts,
    PartRefused,
    split,
)
from carbon.development_session import construction_level as cl
from carbon.development_session.chain_onboarding import carbon_testnet_context
from carbon.transport.models import parse_message

URL = "http://127.0.0.1:9"
HOTKEY = "5MinerC"
SUBMISSION = "sha256:" + "ab" * 32
#: A frozen envelope of three parts (the staging envelope's JSON, opaque here).
ENVELOPE = b'{"documents":"' + b"x" * (2 * PART_BYTES + 100) + b'"}'
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE.challenge_id,
    "backbone": "mlp",
    "parameters": {"width": 16, FIELD: SUBMISSION},
}
PART_TOOLS = ["battery_level4_part", "battery_level4_status"]


def _level(level):
    return cl.resolve(CHALLENGE.challenge_id, level)


def _facts(found, tools=()):
    context = carbon_testnet_context()
    served = [{"level": 0, "digest": "sha256:" + "0" * 64}]
    if found is not None:
        served.append(
            {
                "level": found["level"],
                "variant": found["variant"],
                "digest": found["digest"],
            }
        )
    return {
        "network": context.network,
        "genesis": context.genesis_hash,
        "netuid": context.netuid,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "receiver": "5Validator",
        "snapshot": {"id": "snap-1"},
        "tools": ["battery_submit", "battery_status", *tools],
        "served_contracts": served,
    }


class LadderIntake:
    """A ladder intake as a fixture: the real part handler and store behind
    real message bytes; it records every request it was sent."""

    def __init__(self, tmp_path, found, *, serves_parts=True):
        store = tmp_path / "parts"
        self.parts = Level4Parts(store, [HOTKEY]) if serves_parts else None
        self.handler = object.__new__(ib.BatteryIntake)
        self.handler.level4_parts = self.parts
        self.facts = _facts(found, PART_TOOLS if serves_parts else ())
        self.sent = []
        #: Another sender's part, landing between the status and our part.
        self.race = None

    def read(self, url):
        assert url == URL
        return self.facts

    def post(self, url, body, headers):
        assert url == URL and headers == {"X-Fixture-Signed": "miner-signer"}
        message = parse_message(body)
        tool, fields = message["tool"], message["fields"]
        self.sent.append((tool, fields.get("part")))
        if tool == "battery_level4_part" and self.race is not None:
            self.parts.put(HOTKEY, SUBMISSION, *self.race)
            self.race = None
        if tool in ib.LEVEL4_TOOLS:
            answer = self.handler._level4(HOTKEY, tool, fields)
            return answer.status, answer.body
        if tool == "battery_submit":
            strategy = json.loads(fields["strategy_json"])
            refused = self.handler._level4_incomplete(
                SimpleNamespace(strategy=strategy)
            )
            if refused is not None:
                return refused.status, refused.body
            return 202, {"submission_id": "sub-1", "state": "RECEIVED"}
        return 200, {"submission_id": "sub-1", "state": "SCORED"}

    def tools(self):
        return [tool for tool, _ in self.sent]

    def parts_sent(self):
        return [part for tool, part in self.sent if tool == "battery_level4_part"]


@pytest.fixture(autouse=True)
def signed(monkeypatch):
    monkeypatch.setattr(
        rs, "_signed", lambda signer, facts, body: {"X-Fixture-Signed": signer}
    )


def _submit(tmp_path, intake, found, *, envelope=ENVELOPE, strategy=STRATEGY):
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700, exist_ok=True)
    digest = found["digest"] if found is not None else "sha256:" + "0" * 64
    return campaign.submit_through_intake(
        URL,
        "miner-signer",
        root=root,
        epoch=1,
        strategy=strategy,
        contract_digest=digest,
        read=intake.read,
        post=intake.post,
        construction_level=None if found is None else {**found},
        level4_envelope=envelope,
    )


def _send(intake, envelope=ENVELOPE):
    return rs.send_level4_envelope(
        URL,
        "miner-signer",
        submission=SUBMISSION,
        envelope=envelope,
        read=intake.read,
        post=intake.post,
    )


def test_split_is_the_format_the_store_joins_back(tmp_path):
    chunks = split(ENVELOPE)
    assert len(chunks) == 3 and all(len(c) <= PART_BYTES for c in chunks)
    store = Level4Parts(tmp_path / "s", [HOTKEY])
    for index, data in enumerate(chunks):
        store.put(HOTKEY, SUBMISSION, index, len(chunks), data)
    assert store.envelope(SUBMISSION) == ENVELOPE
    for bad in (b"", "text", b"x" * (PART_BYTES * MAX_PARTS + 1)):
        with pytest.raises(PartRefused) as refused:
            split(bad)
        assert refused.value.code == "level4_part_malformed"


def test_a_ladder_serving_level4_receives_every_part_then_the_submission(tmp_path):
    found = _level(4)
    intake = LadderIntake(tmp_path, found)
    status, answer, submission_id = _submit(tmp_path, intake, found)
    assert (status, answer["state"], submission_id) == (200, "SCORED", "sub-1")
    assert intake.tools() == [
        "battery_level4_status",
        *["battery_level4_part"] * 3,
        "battery_level4_status",
        "battery_submit",
        "battery_status",
    ]
    assert intake.parts_sent() == [0, 1, 2]
    # The intake holds the frozen bytes exactly.
    assert intake.parts.envelope(SUBMISSION) == ENVELOPE


def test_a_submit_without_the_envelope_is_answered_incomplete(tmp_path):
    """The specimen: without the transport the ladder never admits it."""
    found = _level(4)
    intake = LadderIntake(tmp_path, found)
    with pytest.raises(rs.IntakeRefusal) as refused:
        _submit(tmp_path, intake, found, envelope=None)
    assert refused.value.code == "level4_envelope_incomplete"


def test_a_resumed_send_uploads_only_the_missing_parts(tmp_path):
    found = _level(4)
    intake = LadderIntake(tmp_path, found)
    chunks = split(ENVELOPE)
    # An earlier send stopped after part 1.
    intake.parts.put(HOTKEY, SUBMISSION, 0, 3, chunks[0])
    intake.parts.put(HOTKEY, SUBMISSION, 1, 3, chunks[1])
    assert _send(intake) == 1
    assert intake.parts_sent() == [2]
    assert intake.parts.envelope(SUBMISSION) == ENVELOPE
    # A replay of the whole send uploads nothing.
    again = len(intake.sent)
    assert _send(intake) == 0
    assert intake.tools()[again:] == ["battery_level4_status"] * 2


@pytest.mark.parametrize(
    ("held", "code"),
    [
        ((0, 3, b"other"), "level4_part_conflict"),
        ((0, 5, b"x"), "level4_parts_mismatch"),
    ],
)
def test_a_conflict_is_typed_and_never_retried(tmp_path, held, code):
    from scripts.dev.miner_launchpad import supervisor

    found = _level(4)
    intake = LadderIntake(tmp_path, found)
    if code == "level4_part_conflict":
        # Other bytes for part 0 land after the status was read.
        intake.race = held
    else:
        intake.parts.put(HOTKEY, SUBMISSION, *held)
    with pytest.raises(rs.IntakeRefusal) as refused:
        _submit(tmp_path, intake, found)
    assert refused.value.code == code
    assert "battery_submit" not in intake.tools()
    assert intake.parts_sent() == ([0] if code == "level4_part_conflict" else [])
    # A typed refusal with its own next step, reported as the miner's to act on.
    assert campaign.intake_code(code) == code
    assert campaign.intake_outcome(code) == "REFUSED"
    assert supervisor.refusal(code, operation="submit")["code"] == code
    assert code in supervisor.NEXT_ACTIONS


def test_an_intake_without_part_tools_refuses_before_anything_is_signed(tmp_path):
    found = _level(4)
    intake = LadderIntake(tmp_path, found, serves_parts=False)
    with pytest.raises(rs.IntakeRefusal) as refused:
        _submit(tmp_path, intake, found)
    assert refused.value.code == "level4_envelope_transport_unavailable"
    assert intake.sent == []
    assert campaign.intake_code(refused.value.code) == refused.value.code


def test_the_launchpad_refuses_level4_where_no_part_tools_are_listed():
    from scripts.dev.miner_launchpad import levels, supervisor
    from scripts.dev.miner_launchpad.controller import Rejected

    found = _level(4)
    manifest = {
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "construction_level": found,
    }
    cfg = {"intakes": {CHALLENGE.challenge_id: URL}}
    with pytest.raises(Rejected) as refused:
        levels.require_served(cfg, manifest, read=lambda url: _facts(found))
    assert refused.value.code == "level4_envelope_transport_unavailable"
    assert refused.value.next_step == supervisor.next_action(refused.value.code)
    # A ladder listing the part tools passes: the campaign sends the parts.
    assert (
        levels.require_served(cfg, manifest, read=lambda url: _facts(found, PART_TOOLS))
        is None
    )


def _prepared(tmp_path, found):
    return SimpleNamespace(
        ledger=SimpleNamespace(root=tmp_path),
        args=None,
        manifest={"construction_level": found},
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key="miner-signer")),
    )


def _record(found):
    return {
        "strategy": STRATEGY,
        "contract_digest": found["digest"],
        "construction_level": {**found},
    }


def test_the_campaign_sends_nothing_to_an_intake_without_part_tools(
    tmp_path, monkeypatch
):
    from carbon.battery import intake_client
    from carbon.development_session.research_campaign import OperationRefused

    found = _level(4)
    monkeypatch.setattr(campaign, "_level4_envelope", lambda folder, record: ENVELOPE)
    monkeypatch.setattr(intake_client, "read_intake", lambda url, **_: _facts(found))
    sent = []
    monkeypatch.setattr(
        campaign, "submit_through_intake", lambda *a, **k: sent.append(k)
    )
    with pytest.raises(OperationRefused) as refused:
        asyncio.run(
            campaign._evaluate_through_intake(
                _prepared(tmp_path, found), 1, _record(found), URL
            )
        )
    assert refused.value.code == "level4_envelope_transport_unavailable"
    assert sent == []


def test_the_campaign_hands_the_frozen_envelope_to_the_transport(tmp_path, monkeypatch):
    from carbon.battery import intake_client

    found = _level(4)
    monkeypatch.setattr(campaign, "_level4_envelope", lambda folder, record: ENVELOPE)
    monkeypatch.setattr(
        intake_client, "read_intake", lambda url, **_: _facts(found, PART_TOOLS)
    )
    sent = []

    def submit(*args, **kwargs):
        sent.append(kwargs)
        return 200, {"submission_id": "sub-1", "state": "SCORED"}, "sub-1"

    monkeypatch.setattr(campaign, "submit_through_intake", submit)
    feedback = asyncio.run(
        campaign._evaluate_through_intake(
            _prepared(tmp_path, found), 1, _record(found), URL
        )
    )
    assert feedback["via"]["submission_id"] == "sub-1"
    assert [k["level4_envelope"] for k in sent] == [ENVELOPE]


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_levels_0_to_3_send_no_part_and_need_no_part_tools(tmp_path, level):
    from scripts.dev.miner_launchpad import levels

    found = _level(level)
    intake = LadderIntake(tmp_path, found, serves_parts=False)
    strategy = {**STRATEGY, "parameters": {"width": 16}}
    _, answer, _ = _submit(tmp_path, intake, found, envelope=None, strategy=strategy)
    assert answer["state"] == "SCORED"
    assert intake.tools() == ["battery_submit", "battery_status"]
    if found is not None:
        manifest = {
            "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
            "construction_level": found,
        }
        cfg = {"intakes": {CHALLENGE.challenge_id: URL}}
        assert levels.require_served(cfg, manifest, read=intake.read) is None
