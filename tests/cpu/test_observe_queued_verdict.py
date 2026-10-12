"""LA-F18: observe reads a queued submission's verdict, read-only.

Held here:
- the signer's read-only kind, `status_read`, signs one `battery_status` read
  of one submission id on testnet 567 only (refused, never prompted,
  elsewhere), built by Carbon's own `intake_client`, and nothing
  else: never a submission, a Level 4 part, a body its payload does not
  cover, another target, or a commitment, with or without the testnet
  auto-confirm allow-list;
- the read goes through that kind, and only that kind;
- observe polls at most once per chain epoch (tempo), only with a recorded
  submission and no verdict, and stores a verdict exactly as a replayed
  submit stores it, so observe shows it;
- observe never asks the signer for a commitment or a plain `sign`, on any
  path, including every failure.

The signer is the real `carbon_miner_signer` on a real socket holding a
public development key; the intake is a fixture answering in its documented
shapes. Engineering evidence only.
"""

from __future__ import annotations

import dataclasses
import io
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_launchpad_truthful_refusals import (
    frozen_campaign,
    journey,  # noqa: F401 - fixture
    root_of,
)
from test_miner_signer_autoconfirm import _auto
from test_miner_signer_commit import (
    FINNEY,
    GENESIS,
    POLICY,
    _keypair,
    _refusal,
    _request,
)

from carbon.battery import campaign as battery
from carbon.battery import intake_client
from carbon.battery import remote_submission as rs
from carbon.battery.challenge import CHALLENGE
from carbon.battery.intake import PUBLIC_SCHEMA
from carbon.chain import external_signer
from carbon.development_session.chain_onboarding import (
    carbon_testnet_context,
)
from carbon.development_session.profile import canonical
from carbon_miner_signer import SignerServer
from carbon_miner_signer import signer as signer_module
from scripts.dev.miner_launchpad.journey_fixture import FIXTURE_CHALLENGE
from scripts.dev.miner_launchpad.operations import perform
from tests.cpu._signer_harness import in_thread_signer

URL = "https://validator.example/intake"
#: The well-known development account: a public ss58 address, no key.
RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
SUBMISSION = "bsub-" + "0123456789abcdef" * 2
#: Another public ss58 address (a development account), never the intake's.
OTHER_RECEIVER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
#: The signer's clock in these tests, so nonces are fresh by construction.
NOW = 1_800_000_000 * 10**9
_CONTEXT = carbon_testnet_context()
FACTS = {
    "schema": PUBLIC_SCHEMA,
    "network": _CONTEXT.network,
    "genesis": _CONTEXT.genesis_hash,
    "netuid": _CONTEXT.netuid,
    "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
    "snapshot": {"id": "snap-1", "finalized_block": 7_200},
    "receiver": RECEIVER,
    "path": "/carbon/v1/mcp",
}
SCORED = {"submission_id": SUBMISSION, "state": "SCORED"}
QUEUED = {"submission_id": SUBMISSION, "state": "ADMITTED", "waiting": "QUEUED"}


def _payload(body, *, hotkey, nonce, path="/carbon/v1/mcp", receiver=RECEIVER):
    from bittensor.http_auth import build_payload

    return build_payload(
        scheme="sr25519",
        method="POST",
        path=path,
        body=body,
        nonce_ns=nonce,
        sender_ss58=hotkey,
        receiver_ss58=receiver,
    )


def _status_read(body, payload=None, **extra):
    hotkey = _keypair().ss58_address
    payload = payload or _payload(body, hotkey=hotkey, nonce=NOW)
    return {
        "protocol": signer_module.PROTOCOL,
        "op": "status_read",
        "payload": payload.decode("ascii"),
        "body": body.decode("ascii"),
        **extra,
    }


def _server(directory, **options):
    return SignerServer(
        _keypair(),
        Path(directory) / "s.sock",
        log=io.StringIO(),
        clock=lambda: NOW,
        **options,
    )


def _status_body(submission=SUBMISSION):
    return intake_client.status_message(FACTS, submission)


# The signer's read-only kind -------------------------------------------------


def test_the_read_only_kind_signs_one_status_read_built_by_carbon(tmp_path):
    from bittensor.sp_core import verify

    server = _server(tmp_path)
    body = _status_body()
    request = _status_read(body)
    response = server.answer(request)
    assert response["ok"] is True
    signature = bytes.fromhex(response["signature"][2:])
    assert verify(request["payload"].encode(), signature, server.hotkey, 1)
    assert "read-only status read of " + SUBMISSION in server._log.getvalue()


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            intake_client.submission_message(FACTS, {"x": 1}, "sha256:" + "c" * 64),
            id="a submission (admission)",
        ),
        pytest.param(
            intake_client._body(
                FACTS, "battery_level4_part", {"submission_id": SUBMISSION}, None
            ),
            id="a Level 4 part tool",
        ),
        pytest.param(
            intake_client._body(
                FACTS, "battery_level4_status", {"submission": SUBMISSION}, None
            ),
            id="a Level 4 status tool",
        ),
        pytest.param(
            intake_client._body(
                FACTS,
                "battery_status",
                {"submission_id": SUBMISSION, "extra": "x"},
                None,
            ),
            id="an extra field",
        ),
        pytest.param(_status_body("not-a-submission"), id="a malformed id"),
        pytest.param(
            json.dumps(json.loads(_status_body()), indent=1).encode(),
            id="a non-canonical body",
        ),
        pytest.param(b'{"tool":"battery_status"}', id="not a Carbon request"),
    ],
)
def test_the_read_only_kind_signs_nothing_but_a_status_read(tmp_path, body):
    server = _server(tmp_path)
    assert _refusal(server.answer(_status_read(body))) == "NOT_A_STATUS_READ"


def test_the_read_only_kind_signs_only_the_body_its_payload_covers(tmp_path):
    server = _server(tmp_path)
    hotkey = server.hotkey
    submit = intake_client.submission_message(FACTS, {"x": 1}, "sha256:" + "c" * 64)
    # A submission's payload sent beside an innocent status body is refused:
    # the signature would cover the submission.
    payload = _payload(submit, hotkey=hotkey, nonce=NOW)
    refused = server.answer(_status_read(_status_body(), payload))
    assert _refusal(refused) == "NOT_A_STATUS_READ"


def test_the_read_only_kind_keeps_every_sign_check(tmp_path):
    body = _status_body()
    hotkey = _keypair().ss58_address
    narrow = _server(tmp_path, receivers=[OTHER_RECEIVER])
    assert _refusal(narrow.answer(_status_read(body))) == "RECEIVER_NOT_ALLOWED"
    server = _server(tmp_path)
    stale = _payload(body, hotkey=hotkey, nonce=NOW - 60 * 10**9)
    assert _refusal(server.answer(_status_read(body, stale))) == "STALE_NONCE"
    # Never the answer-key target, even on a signer started for it.
    keys = _server(tmp_path, receivers=[RECEIVER], requests=("mcp", "answer-key"))
    fetch = _payload(body, hotkey=hotkey, nonce=NOW, path="/carbon/v1/answer-key")
    assert _refusal(keys.answer(_status_read(body, fetch))) == "NOT_A_CARBON_REQUEST"
    answer_key_only = _server(tmp_path, receivers=[RECEIVER], requests=("answer-key",))
    assert (
        _refusal(answer_key_only.answer(_status_read(body))) == "NOT_A_CARBON_REQUEST"
    )
    # Extra request fields are malformed, never ignored.
    assert _refusal(server.answer(_status_read(body, extra=1))) == "MALFORMED_REQUEST"


def test_the_signer_refuses_to_auto_confirm_a_commitment_through_that_kind(tmp_path):
    """A testnet signer that auto-confirms allow-listed commitments still
    signs no commitment through `status_read`: not the commit request's
    fields, not its extrinsic payload. Nothing is recorded or shown."""
    log = io.StringIO()
    server = SignerServer(
        _keypair(),
        Path(tmp_path) / "s.sock",
        log=log,
        clock=lambda: NOW,
        commit_policy=POLICY,
        confirm=lambda text, expected: pytest.fail("the terminal was asked"),
        auto_confirm=_auto(tmp_path),
    )
    commit = _request()
    as_read = {**commit, "op": "status_read"}
    assert _refusal(server.answer(as_read)) == "MALFORMED_REQUEST"
    from carbon_miner_signer import commitment as cm

    payload = cm.check_request(POLICY, commit)["payload"]
    smuggled = {
        "protocol": signer_module.PROTOCOL,
        "op": "status_read",
        "payload": "0x" + payload.hex(),
        "body": _status_body().decode(),
    }
    assert _refusal(server.answer(smuggled)) == "NOT_A_CARBON_REQUEST"
    assert server.ledger.entries() == []
    assert "AUTO-CONFIRMED" not in log.getvalue()
    # The allow-list still covers exactly what it covered: a commit is signed.
    assert server.answer(commit)["ok"] is True


def test_the_signer_shape_matches_carbons_request_builder():
    from carbon.battery.intake import STATUS_TOOL
    from carbon.transport.models import PROTOCOL
    from carbon_miner_signer import status_read as sr

    assert (sr.BODY_PROTOCOL, sr.STATUS_TOOL) == (PROTOCOL, STATUS_TOOL)
    assert set(json.loads(_status_body())) == sr.BODY_FIELDS
    assert "NOT_A_STATUS_READ" in external_signer.SIGNER_REFUSALS
    assert external_signer.STATUS_READ_OP == sr.OP


def _on_chain(genesis, netuid=567, submission=SUBMISSION):
    """A canonical status read naming another chain: Carbon's builder serves
    only testnet 567, so it is built here, in the same canonical form."""
    from carbon.transport.models import canonical as transport_canonical

    document = json.loads(_status_body(submission))
    return transport_canonical({**document, "genesis": genesis, "netuid": netuid})


@pytest.mark.parametrize(
    ("genesis", "netuid"),
    [
        pytest.param(FINNEY, 567, id="mainnet genesis"),
        pytest.param("0x" + "1" * 64, 567, id="another genesis"),
        pytest.param(GENESIS, 1, id="testnet, another netuid"),
    ],
)
def test_the_read_only_kind_is_auto_signed_only_on_testnet_567(
    tmp_path, genesis, netuid
):
    """Off testnet 567 a status read fails closed: refused at once, never
    put to the terminal, nothing recorded. `sign` is unchanged."""
    log = io.StringIO()
    server = SignerServer(
        _keypair(),
        Path(tmp_path) / "s.sock",
        log=log,
        clock=lambda: NOW,
        commit_policy=POLICY,
        confirm=lambda text, expected: pytest.fail("the terminal was asked"),
    )
    body = _on_chain(genesis, netuid)
    refused = server.answer(_status_read(body))
    assert _refusal(refused) == "STATUS_READ_NOT_TESTNET"
    assert "signature" not in refused and server.ledger.entries() == []
    # The same payload through the unchanged `sign` op is signed as before.
    plain = _status_read(body)
    plain = {k: v for k, v in plain.items() if k != "body"}
    assert server.answer({**plain, "op": "sign"})["ok"] is True


def test_testnet_567_is_the_auto_confirm_genesis_and_carbons_chain():
    from carbon_miner_signer import autoconfirm as ac

    assert ac.TESTNET_GENESIS == GENESIS == _CONTEXT.genesis_hash
    assert ac.TESTNET_NETUID == _CONTEXT.netuid == 567
    body = json.loads(_status_body())
    assert (body["genesis"], body["netuid"]) == (GENESIS, 567)


def test_a_read_refused_off_testnet_sends_nothing_and_stores_nothing(
    tmp_path, ops, monkeypatch
):
    """Observe's read when the signer will not auto-sign it: the read fails
    closed at once, nothing is posted or stored, and only the read-only kind
    was asked for."""
    mainnet = _on_chain(FINNEY)  # built before Carbon's builder is replaced
    monkeypatch.setattr(
        rs.intake_client, "status_message", lambda facts, submission: mainnet
    )
    _battery_epoch(tmp_path)
    _recorded(tmp_path)
    intake = Intake()
    with in_thread_signer(_keypair()) as signer:
        with pytest.raises(external_signer.SignerFailure) as failed:
            rs.read_status_once(
                URL, signer, root=tmp_path, epoch=1, read=intake.read, post=intake.post
            )
        assert failed.value.refusal == "STATUS_READ_NOT_TESTNET"
        assert _verdict(tmp_path, intake, now=1.0, connect=lambda: signer) is None
    assert intake.sent == []
    assert not (tmp_path / "epoch-1" / "permitted-final-feedback.json").exists()
    assert set(ops) == {"identity", "status_read"}


# Carbon's side: the read uses that kind, and only it --------------------------


class Intake:
    """The validator's intake, as a fixture: it records what it was sent."""

    def __init__(self, *answers, block=7_200):
        self.answers = list(answers) or [(200, SCORED)]
        self.sent, self.bodies = [], []
        #: The intake's finalized block; None reports none.
        self.block = block

    def read(self, url):
        assert url == URL
        snapshot = {"id": "snap-1"}
        if self.block is not None:
            snapshot["finalized_block"] = self.block
        return {**FACTS, "snapshot": snapshot}

    def post(self, url, body, headers):
        self.sent.append((json.loads(body)["tool"], headers))
        self.bodies.append(body)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def ops(monkeypatch):
    """Every request Carbon sends the signer, by op, at the signer boundary."""
    sent = []
    real = external_signer._exchange

    def recording(path, request, timeout):
        sent.append(request.get("op"))
        return real(path, request, timeout)

    monkeypatch.setattr(external_signer, "_exchange", recording)
    return sent


def _recorded(root, epoch=1, url=URL):
    root.chmod(0o700)
    path = rs._record_path(root, epoch)
    path.write_text(
        json.dumps({"url": url, "epoch": epoch, "submission_id": SUBMISSION})
    )
    return path


def test_the_read_uses_the_read_only_kind(tmp_path, ops):
    from bittensor.http_auth import HEADER_NONCE, HEADER_SIGNATURE
    from bittensor.sp_core import verify

    _recorded(tmp_path)
    intake = Intake()
    with in_thread_signer(_keypair()) as signer:
        status, answer, submission = rs.read_status_once(
            URL, signer, root=tmp_path, epoch=1, read=intake.read, post=intake.post
        )
    assert (status, answer, submission) == (200, SCORED, SUBMISSION)
    assert ops == ["identity", "status_read"]
    ((tool, headers),) = intake.sent
    assert tool == "battery_status"
    (body,) = intake.bodies
    assert json.loads(body)["fields"] == {"submission_id": SUBMISSION}
    # The headers verify over exactly the status read that was sent.
    payload = _payload(
        body, hotkey=signer.ss58_address, nonce=int(headers[HEADER_NONCE])
    )
    signature = bytes.fromhex(headers[HEADER_SIGNATURE][2:])
    assert verify(payload, signature, signer.ss58_address, 1)


def test_a_read_needs_a_recorded_submission_for_the_same_intake(tmp_path, ops):
    intake = Intake()
    assert (
        rs.read_status_once(
            URL, "unused", root=tmp_path, epoch=1, read=intake.read, post=intake.post
        )
        is None
    )
    _recorded(tmp_path, url="https://another.example")
    with pytest.raises(rs.IntakeRefusal, match="intake_changed_since_submission"):
        rs.read_status_once(
            URL, "unused", root=tmp_path, epoch=1, read=intake.read, post=intake.post
        )
    assert intake.sent == [] and ops == []


def test_a_mismatched_receiver_is_refused_before_anything_is_signed(tmp_path, ops):
    _recorded(tmp_path)
    intake = Intake()
    with pytest.raises(rs.IntakeRefusal, match="intake_receiver_mismatch"):
        rs.read_status_once(
            URL,
            "unused",
            root=tmp_path,
            epoch=1,
            read=intake.read,
            post=intake.post,
            receiver=OTHER_RECEIVER,
        )
    assert intake.sent == [] and ops == []


# The battery's queued-verdict read: bounded --------------------------------


class Args:
    def __init__(self, intake=URL, validators=None):
        self.intakes = {CHALLENGE.challenge_id: intake} if intake else {}
        self.validators = validators or {}
        self.receivers = {}


def _battery_epoch(root, epoch=1, record=None, manifest=None):
    root.chmod(0o700)
    folder = root / ("epoch-" + str(epoch))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "selected-recipe.json").write_text(
        json.dumps(record or {"strategy": {"x": 1}})
    )
    (root / "campaign-manifest.json").write_text(json.dumps(manifest or {}))
    return folder


def _verdict(root, intake, *, now, connect=None, args=None, floor=rs.READ_FLOOR_S):
    return battery.queued_verdict(
        args or Args(),
        root,
        1,
        connect or (lambda: pytest.fail("the signer was reached")),
        now=now,
        read=intake.read,
        post=intake.post,
        floor=floor,
    )


def test_a_verdict_is_read_once_and_built_as_a_submit_builds_it(tmp_path, ops):
    _battery_epoch(tmp_path)
    _recorded(tmp_path)
    intake = Intake()
    with in_thread_signer(_keypair()) as signer:
        feedback = _verdict(tmp_path, intake, now=100.0, connect=lambda: signer)
    assert feedback == battery.intake_feedback(1, URL, 200, SCORED, SUBMISSION)
    assert [tool for tool, _ in intake.sent] == ["battery_status"]
    assert ops == ["identity", "status_read"]
    mark = rs._read_mark_path(tmp_path, 1)
    assert json.loads(mark.read_bytes())["polled_unix"] == 100.0
    assert mark.stat().st_mode & 0o777 == 0o600


def test_at_most_one_poll_per_chain_epoch(tmp_path, ops):
    """No read sooner than one tempo of nominal blocks after the last, and
    never two in the tempo of the intake's finalized block."""
    _battery_epoch(tmp_path)
    _recorded(tmp_path)
    floor = rs.READ_FLOOR_S
    assert floor == 360 * 12 and rs.TEMPO_BLOCKS == 360
    intake = Intake((200, QUEUED), block=7_200)
    with in_thread_signer(_keypair()) as signer:

        def poll(now):
            return _verdict(tmp_path, intake, now=now, connect=lambda: signer)

        for now in (100.0, 100.0, 100.0 + floor / 2, 100.0 + floor - 0.1):
            assert poll(now) is None
        assert len(intake.sent) == 1
        # The floor has passed, but the chain is still in tempo 20.
        intake.block = 7_200 + 359
        assert poll(100.0 + floor) is None
        assert len(intake.sent) == 1
        # The next tempo, after the next floor: one more read.
        intake.block = 7_560
        assert poll(100.0 + 2 * floor) is None
        assert len(intake.sent) == 2
        mark = json.loads(rs._read_mark_path(tmp_path, 1).read_bytes())
        assert mark["tempo"] == 21 and mark["polled_unix"] == 100.0 + 2 * floor
        # Facts without a finalized block leave the time floor alone.
        intake.block = None
        assert poll(100.0 + 2 * floor + 1) is None
        assert poll(100.0 + 3 * floor) is None
    assert len(intake.sent) == 3
    assert set(ops) == {"identity", "status_read"}


def test_no_poll_without_a_recorded_submission_or_once_a_verdict_exists(tmp_path):
    folder = _battery_epoch(tmp_path)
    intake = Intake()
    assert _verdict(tmp_path, intake, now=100.0) is None
    _recorded(tmp_path)
    (folder / "permitted-final-feedback.json").write_text("{}")
    assert _verdict(tmp_path, intake, now=100.0) is None
    assert intake.sent == []
    assert not rs._read_mark_path(tmp_path, 1).exists()


def test_no_poll_for_a_local_deployment_a_missing_intake_or_level_4(tmp_path):
    intake = Intake()
    _battery_epoch(tmp_path)
    _recorded(tmp_path)
    local = Args(validators={CHALLENGE.challenge_id: "/a/deployment.json"})
    assert _verdict(tmp_path, intake, now=1.0, args=local) is None
    assert _verdict(tmp_path, intake, now=1.0, args=Args(intake=None)) is None
    level = {"level": 4, "digest": "sha256:" + "d" * 64}
    _battery_epoch(
        tmp_path,
        record={
            "strategy": {"x": 1},
            "contract_digest": level["digest"],
            "construction_level": level,
        },
        manifest={"construction_level": level},
    )
    assert _verdict(tmp_path, intake, now=1.0) is None
    assert intake.sent == []


@pytest.mark.parametrize(
    "answer",
    [
        (200, QUEUED),
        (200, {"submission_id": SUBMISSION, "state": "REFUSED", "failure": {}}),
        (200, {"submission_id": SUBMISSION, "state": "FAILED_INFRA_EXHAUSTED"}),
        (200, {"submission_id": SUBMISSION, "state": "VOID"}),
        (404, {"refused": "not_found"}),
        OSError("connection refused"),
    ],
)
def test_anything_but_a_verdict_stores_nothing_and_signs_only_reads(
    tmp_path, ops, answer
):
    _battery_epoch(tmp_path)
    _recorded(tmp_path)
    intake = Intake(answer)
    with in_thread_signer(_keypair()) as signer:
        assert _verdict(tmp_path, intake, now=1.0, connect=lambda: signer) is None
    assert set(ops) == {"identity", "status_read"}
    assert not (tmp_path / "epoch-1" / "permitted-final-feedback.json").exists()


# Through observe: the campaign host -----------------------------------------


@pytest.fixture
def reading(journey, monkeypatch):  # noqa: F811
    """The journey host whose fixture Challenge reads a queued verdict as the
    battery Challenge does (`battery.queued_verdict`, `record_verdict`), from
    a fixture intake, signed by the real signer."""
    from carbon.challenge_registry import campaigns
    from scripts.dev.miner_launchpad.journey_fixture import reference_burgers_campaign

    state = {"now": 1_000.0, "intake": Intake((200, QUEUED))}

    def queued(args, root, epoch, connect):
        args.intakes = {CHALLENGE.challenge_id: URL}
        args.validators = {}
        return battery.queued_verdict(
            args,
            root,
            epoch,
            connect,
            now=state["now"],
            read=state["intake"].read,
            post=state["intake"].post,
        )

    validated = dataclasses.replace(
        reference_burgers_campaign(),
        feedback_schema="fixture.permitted-feedback.v1",
        queued_verdict=queued,
        record_verdict=battery.record_verdict,
    )
    mapping = campaigns._campaigns
    monkeypatch.setattr(
        campaigns,
        "_campaigns",
        lambda: {**mapping(), FIXTURE_CHALLENGE["id"]: lambda: validated},
    )
    with in_thread_signer(_keypair()) as signer:
        journey.verdict_signer = lambda cfg: signer
        yield journey, state


def observe(host, identity):
    return perform(host, "observe", {"campaign": identity})


def test_a_queued_verdict_arrives_through_observe(reading, ops):
    host, state = reading
    identity = frozen_campaign(host)
    root = root_of(host, identity)
    _recorded(root)
    host._refused(identity, "evaluation_queued", "submit")
    view = observe(host, identity)
    assert view["journey"]["submitted_epochs"] == []
    assert view["last_refusal"]["code"] == "evaluation_queued"
    state["now"] += rs.READ_FLOOR_S
    state["intake"] = Intake((200, SCORED), block=7_560)
    view = observe(host, identity)
    feedback = root / "epoch-1" / "permitted-final-feedback.json"
    # Stored exactly as a replayed submit stores it.
    expected = battery.intake_feedback(1, URL, 200, SCORED, SUBMISSION)
    assert feedback.read_bytes() == canonical(expected)
    assert view["journey"]["submitted_epochs"] == [1]
    assert [r["epoch"] for r in view["final_results"]] == [1]
    assert view["last_refusal"] is None
    assert view["state"] == "READY"
    # The fixture's signer was connected before `ops` recorded; observe sent
    # only the read-only kind.
    assert ops == ["status_read", "status_read"]
    # Once the verdict exists, observe asks nothing more.
    state["now"] += 10 * rs.READ_FLOOR_S
    state["intake"].block = 9_000
    before = len(state["intake"].sent)
    observe(host, identity)
    assert len(state["intake"].sent) == before


def test_observe_polls_at_most_once_per_chain_epoch(reading, ops):
    host, state = reading
    identity = frozen_campaign(host)
    _recorded(root_of(host, identity))
    for _ in range(5):
        observe(host, identity)
    assert len(state["intake"].sent) == 1
    # One tempo of time, but the same chain epoch: still one read.
    state["now"] += rs.READ_FLOOR_S
    observe(host, identity)
    assert len(state["intake"].sent) == 1
    state["now"] += rs.READ_FLOOR_S
    state["intake"].block = 7_560
    observe(host, identity)
    assert len(state["intake"].sent) == 2


def test_observe_does_not_poll_without_a_recorded_submission(reading, ops):
    host, state = reading
    identity = frozen_campaign(host)
    observe(host, identity)
    assert state["intake"].sent == [] and ops == []


def test_the_last_epochs_verdict_completes_the_campaign_as_a_submit_does(reading, ops):
    host, state = reading
    identity = frozen_campaign(host)
    root = root_of(host, identity)
    (root / "epoch-1").mkdir(exist_ok=True)
    (root / "epoch-1" / "permitted-final-feedback.json").write_bytes(
        canonical(battery.intake_feedback(1, URL, 200, SCORED, SUBMISSION))
    )
    (root / "epoch-2").mkdir(exist_ok=True)
    (root / "epoch-2" / "selected-recipe.json").write_bytes(
        (root / "epoch-1" / "selected-recipe.json").read_bytes()
    )
    _recorded(root, epoch=2)
    state["intake"] = Intake((200, SCORED))
    view = observe(host, identity)
    assert (root / "epoch-2" / "permitted-final-feedback.json").exists()
    assert (root / "campaign-complete.json").exists()
    assert view["state"] == "COMPLETED"


@pytest.mark.parametrize(
    "failure",
    ["queued", "intake_refused", "intake_down", "signer_refuses", "signer_down"],
)
def test_observe_never_produces_a_commitment_signature(
    reading, ops, monkeypatch, failure
):
    """At the signer boundary: on the observe path Carbon asks the signer for
    its identity and the read-only kind, never `commit` and never a plain
    `sign`, whatever happens; and no commitment is requested at all."""
    host, state = reading

    def never(*args, **kwargs):
        raise AssertionError("observe requested a commitment")

    monkeypatch.setattr(external_signer, "request_commitment", never)
    identity = frozen_campaign(host)
    _recorded(root_of(host, identity))
    if failure == "intake_refused":
        state["intake"] = Intake((404, {"refused": "not_found"}))
    elif failure == "intake_down":
        state["intake"] = Intake(OSError("down"))
    elif failure == "signer_down":

        def down(cfg):
            raise external_signer.SignerFailure(external_signer.SignerCode.NOT_RUNNING)

        host.verdict_signer = down
    with in_thread_signer(_keypair(), receivers=[OTHER_RECEIVER]) as narrow:
        if failure == "signer_refuses":
            # A signer whose allow-list excludes the intake's receiver.
            host.verdict_signer = lambda cfg: narrow
        view = observe(host, identity)
    assert view["journey"]["submitted_epochs"] == []
    assert view["state"] == "READY"
    assert "commit" not in ops and "sign" not in ops
    assert set(ops) <= {"identity", "status_read"}
    if failure != "signer_down":
        assert ops[-1] == "status_read"
