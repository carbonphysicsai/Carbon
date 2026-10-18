"""Explicit signed retry preserves the failed parent and ordinary submission.

Real development-key Bittensor signatures, receipt authentication, adapter and
retained provider records are used. The bound image is made unavailable before
execution to exercise infrastructure failure; no model or Docker worker runs.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture
from test_direct_v3_user_door import _sdk

from carbon import research
from carbon.battery.intake import SnapshotWindow
from carbon.chain.auth import BittensorHotkeyVerifier
from carbon.chain.models import ChainContext, MetagraphSnapshot, Participant
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger, direct_intake
from carbon.development_session import direct_submission as client
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal
from tests.cpu._signer_harness import in_thread_signer

_URL = "http://127.0.0.1:9080"
_UNKNOWN = "rtsk_" + "f" * 64
_CAPABILITY = {
    "schema": "carbon.construction.infrastructure-retry.v1",
    "field": "retry_of_submission_id",
    "eligible_state": "FAILED_INFRA",
    "idempotency": "ONE_CHILD_PER_FAILED_TASK",
}


@pytest.fixture
def signed_receiver(tmp_path, monkeypatch):
    keypair = _sdk()
    miner = keypair.create_from_uri("//Alice")
    validator = keypair.create_from_uri("//Bob")
    context = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)
    request, factory, discovery = _fixture(
        tmp_path / "provider", monkeypatch, material=bundle_material_v5()
    )
    provider = [factory(miner.ss58_address)]
    now = time.time_ns()
    snapshot = MetagraphSnapshot(
        context,
        10,
        "0x" + "2" * 64,
        now // 1_000_000,
        (
            Participant(0, validator.ss58_address, "validator-cold", 1),
            Participant(1, miner.ss58_address, "miner-cold", 2),
        ),
    )
    window = SnapshotWindow()
    window.add(snapshot)
    attempts = tmp_path / "attempts"
    attempts.mkdir(mode=0o700)
    attempts.chmod(0o700)
    intake = direct_intake.DirectRecipeIntake(
        context=context,
        receiver=validator.ss58_address,
        journal=ReceiptJournal(tmp_path / "transport.sqlite3", context),
        verifier=BittensorHotkeyVerifier(),
        window=window,
        discovery=discovery,
        provider_for=lambda owner: provider[0] if owner == miner.ss58_address else None,
        attempt_ledger=AttemptLedger(attempts / "ledger.sqlite3"),
    )
    cleanup_probes = []

    class TrustedDocker:
        def run(self, argv, *, timeout):
            assert argv == [
                "ps",
                "-aq",
                "--filter",
                "label=org.carbonphysicsai.overlay-uv-intent",
            ]
            assert timeout == 10
            cleanup_probes.append(tuple(argv))
            return SimpleNamespace(stdout=b"")

    monkeypatch.setattr(
        "carbon.reconstruction.worker.docker_runtime.DockerCLI", TrustedDocker
    )
    root = tmp_path / "client"
    root.mkdir(mode=0o700)
    wires = []

    def send(url, body, headers):
        assert url == _URL
        wires.append(json.loads(body))
        answer = intake.handle(
            "POST", direct_intake.SUBMIT_PATH, headers, body, "127.0.0.1"
        )
        return answer.status, answer.body

    with in_thread_signer(miner) as external:
        args = {
            "root": root,
            "epoch": 1,
            "recipe": ConstructionRecipe.from_dict(request.recipe),
            "contract_digest": intake.adapter.contract_digest,
            "receiver": validator.ss58_address,
            "context": context,
            "read": lambda url: intake.public().body,
            "send": send,
        }
        fixture = SimpleNamespace(
            intake=intake,
            provider=lambda: provider[0],
            args=args,
            signer=external,
            miner=miner,
            snapshot=snapshot,
            wires=wires,
            cleanup_probes=cleanup_probes,
        )

        def reopen():
            provider[0].close()
            provider[0] = factory(miner.ss58_address)

        fixture.reopen = reopen
        try:
            yield fixture
        finally:
            provider[0].close()


def _admit(fixture, **changes):
    with pytest.raises(client.DirectConstructionPending) as pending:
        client.submit_and_wait(
            _URL, fixture.signer, **{**fixture.args, "wait_s": 0, **changes}
        )
    return research.ResearchTaskId(pending.value.task_id)


def _failed_parent(fixture, monkeypatch, *, parent=None):
    parent = _admit(fixture) if parent is None else parent

    def unavailable(_request):
        raise FileNotFoundError("fixture bound image unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(fixture.provider(), "_resolved_image", unavailable)
        view = fixture.provider().run_queued_task(parent)
    assert view.state is research.DirectTaskStateV3.FAILED_INFRA
    assert all(
        fixture.provider().ledger.operation_state(
            identity, owner=fixture.miner.ss58_address
        )
        is None
        for identity in fixture.provider()._children(parent)
    )
    return parent.value, research.canonical_bytes(view)


def test_public_retry_capability_preserves_existing_tools(signed_receiver):
    facts = signed_receiver.intake.public().body
    assert facts["construction_retry"] == _CAPABILITY
    assert facts["tools"] == [
        client.SUBMIT_TOOL,
        client.STATUS_TOOL,
        research.RESEARCH_NAMESPACE,
    ]
    assert client.RETRY_CAPABILITY == _CAPABILITY
    assert facts["qualification"] is False and facts["reward"] is False


def test_ordinary_signed_submission_retains_legacy_fields_and_journal(signed_receiver):
    fixture = signed_receiver
    facts = fixture.intake.public().body
    facts.pop("construction_retry")
    task_id = _admit(fixture, read=lambda _: facts)
    fields = fixture.wires[0]["fields"]
    assert set(fields) == {"strategy_json", "contract_digest"}
    record = json.loads(
        (fixture.args["root"] / "construction-intake-epoch-1.json").read_bytes()
    )
    assert "retry_of_submission_id" not in record
    assert record["submission_id"] == task_id.value
    assert fixture.provider().queued_tasks() == (task_id,)
    assert fixture.cleanup_probes == []


def test_real_signed_retry_response_loss_restart_and_observation_keep_one_child(
    signed_receiver, monkeypatch
):
    fixture = signed_receiver
    parent, original = _failed_parent(fixture, monkeypatch)
    normal_send = fixture.args["send"]
    attempts = []

    def lost_response(url, body, headers):
        status, answer = normal_send(url, body, headers)
        attempts.append(answer["outcome"]["task_id"])
        assert status == 202
        raise OSError("fixture response lost after durable admission")

    with pytest.raises(OSError, match="response lost"):
        _admit(fixture, retry_of=parent, send=lost_response)
    retry_path = (
        fixture.args["root"] / f"construction-intake-epoch-1-retry-{parent}.json"
    )
    assert not retry_path.exists()
    assert len(fixture.cleanup_probes) == 1
    fixture.reopen()
    child = _admit(fixture, retry_of=parent)
    assert child.value == attempts[0] and child.value != parent
    assert fixture.wires[1]["request"] != fixture.wires[2]["request"]
    assert fixture.wires[1]["fields"] == fixture.wires[2]["fields"]
    assert fixture.provider().queued_tasks() == (child,)
    assert len(fixture.cleanup_probes) == 1
    record_path = retry_path
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes)
    assert record["retry_of_submission_id"] == parent
    assert record["submission_id"] == child.value
    assert _admit(fixture, retry_of=parent) == child
    assert len(fixture.wires) == 3  # ordinary submit, response loss, idempotent replay
    fixture.provider().cancel_research_task(
        research.DirectCancelTaskRequestV3(
            fixture.provider().discovery.info.challenge_key, child, "retry-test-stop"
        )
    )
    terminal = client.submit_and_wait(
        _URL,
        fixture.signer,
        **{**fixture.args, "retry_of": parent, "wait_s": 30, "observe_only": True},
    )
    assert terminal["task_id"] == child.value
    assert terminal["state"] == "FAILED_INFRA"
    assert fixture.wires[-1]["tool"] == client.STATUS_TOOL
    assert fixture.wires[-1]["fields"] == {"submission_id": child.value}
    assert record_path.read_bytes() == record_bytes
    retained = (
        fixture.provider()
        .get_research_result(
            research.DirectGetTaskRequestV3(
                fixture.provider().discovery.info.challenge_key,
                research.ResearchTaskId(parent),
            )
        )
        .task
    )
    assert research.canonical_bytes(retained) == original
    assert all(
        wire["fields"].get("retry_of_submission_id") == parent
        for wire in fixture.wires[1:-1]
    )


@pytest.mark.parametrize(
    "capability",
    [
        None,
        {},
        {**_CAPABILITY, "schema": "carbon.construction.infrastructure-retry.v2"},
        {**_CAPABILITY, "field": "retry_of"},
        {**_CAPABILITY, "eligible_state": "CANCELLED"},
        {**_CAPABILITY, "idempotency": "NEW_CHILD_EVERY_CALL"},
        {**_CAPABILITY, "extra": True},
    ],
)
def test_explicit_retry_requires_exact_receiver_capability_before_signing(
    signed_receiver, monkeypatch, capability
):
    fixture = signed_receiver
    facts = fixture.intake.public().body
    facts.pop("construction_retry")
    if capability is not None:
        facts["construction_retry"] = capability

    def forbidden(*args, **kwargs):
        pytest.fail("unsupported retry must not reach signing")

    monkeypatch.setattr(client, "BittensorMessageSigner", forbidden)
    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_retry_unavailable"
    ):
        _admit(fixture, epoch=2, retry_of=_UNKNOWN, read=lambda _: facts)
    assert not fixture.wires and not fixture.provider().queued_tasks()


@pytest.mark.parametrize(
    "predecessor", [True, 1, {}, [], "", "rtsk_short", "rtsk_" + "A" * 64]
)
def test_bad_client_retry_id_is_refused_before_discovery_or_signing(
    signed_receiver, monkeypatch, predecessor
):
    fixture = signed_receiver

    def forbidden(*args, **kwargs):
        pytest.fail("malformed retry must stop before network and signing")

    monkeypatch.setattr(client, "BittensorMessageSigner", forbidden)
    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_retry_predecessor_invalid"
    ):
        _admit(fixture, epoch=2, retry_of=predecessor, read=forbidden, send=forbidden)
    assert not fixture.provider().queued_tasks()


def test_same_epoch_retry_has_distinct_journal_and_preserves_predecessor_binding(
    signed_receiver, monkeypatch
):
    fixture = signed_receiver
    parent, _original = _failed_parent(fixture, monkeypatch)
    ordinary_path = fixture.args["root"] / "construction-intake-epoch-1.json"
    ordinary = ordinary_path.read_bytes()
    child = _admit(fixture, retry_of=parent)
    retry_path = (
        fixture.args["root"] / f"construction-intake-epoch-1-retry-{parent}.json"
    )
    record = json.loads(retry_path.read_bytes())
    assert record["retry_of_submission_id"] == parent
    assert record["submission_id"] == child.value
    assert child.value != parent
    assert ordinary_path.read_bytes() == ordinary
    assert _admit(fixture).value == parent
    assert len(fixture.wires) == 2
    # A copied child record cannot bind a different predecessor, even if its
    # filename is chosen to match that other explicit attempt.
    wrong_path = (
        fixture.args["root"] / f"construction-intake-epoch-1-retry-{_UNKNOWN}.json"
    )
    wrong_path.write_bytes(retry_path.read_bytes())
    with pytest.raises(client.DirectIntakeRefusal, match="changed_since_submission"):
        _admit(fixture, retry_of=_UNKNOWN)
    assert len(fixture.wires) == 2


@pytest.mark.parametrize(
    "predecessor", [None, True, {}, [], "", "rtsk_short", "rtsk_" + "A" * 64]
)
def test_real_signed_intake_rejects_malformed_retry_fields(
    signed_receiver, predecessor
):
    fixture = signed_receiver
    import bittensor as bt

    body = message(
        fixture.args["context"],
        fixture.snapshot.snapshot_id,
        fixture.provider().discovery.info.challenge_key,
        session="retry-malformed",
        request="retry-malformed-1",
        tool=client.SUBMIT_TOOL,
        fields={
            "strategy_json": fixture.args["recipe"].canonical_bytes.decode(),
            "contract_digest": fixture.args["contract_digest"],
            "retry_of_submission_id": predecessor,
        },
    )
    headers = bt.http_auth.sign(
        fixture.miner,
        method="POST",
        path=direct_intake.SUBMIT_PATH,
        body=body,
        receiver_ss58=fixture.args["receiver"],
    )
    status, answer = fixture.args["send"](_URL, body, headers)
    assert status == 400 and answer["refused"] == "submission_fields"
    assert fixture.provider().queued_tasks() == ()


def test_real_signature_binds_predecessor_and_unknown_field_refuses(signed_receiver):
    fixture = signed_receiver
    import bittensor as bt

    fields = {
        "strategy_json": fixture.args["recipe"].canonical_bytes.decode(),
        "contract_digest": fixture.args["contract_digest"],
    }

    def wire(values, request):
        return message(
            fixture.args["context"],
            fixture.snapshot.snapshot_id,
            fixture.provider().discovery.info.challenge_key,
            session="retry-auth",
            request=request,
            tool=client.SUBMIT_TOOL,
            fields=values,
        )

    original = wire(fields, "retry-auth-1")
    headers = bt.http_auth.sign(
        fixture.miner,
        method="POST",
        path=direct_intake.SUBMIT_PATH,
        body=original,
        receiver_ss58=fixture.args["receiver"],
    )
    changed = wire({**fields, "retry_of_submission_id": _UNKNOWN}, "retry-auth-1")
    status, answer = fixture.args["send"](_URL, changed, headers)
    assert status == 401 and answer["refused"] == "AUTH_BAD_SIGNATURE"
    unknown = wire(
        {**fields, "retry_of_submission_id": _UNKNOWN, "attempt": 2}, "retry-auth-2"
    )
    headers = bt.http_auth.sign(
        fixture.miner,
        method="POST",
        path=direct_intake.SUBMIT_PATH,
        body=unknown,
        receiver_ss58=fixture.args["receiver"],
    )
    status, answer = fixture.args["send"](_URL, unknown, headers)
    assert status == 400 and answer["refused"] == "submission_fields"
    assert fixture.provider().queued_tasks() == ()


def test_explicit_retry_cannot_record_or_poll_a_parent_returned_as_child(
    signed_receiver, monkeypatch
):
    fixture = signed_receiver
    parent, _original = _failed_parent(fixture, monkeypatch)
    normal_send = fixture.args["send"]

    def altered_response(url, body, headers):
        status, answer = normal_send(url, body, headers)
        assert status == 202
        answer = json.loads(json.dumps(answer))
        answer["outcome"]["submission_id"] = parent
        answer["outcome"]["task_id"] = parent
        return status, answer

    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_retry_child_invalid"
    ):
        _admit(fixture, retry_of=parent, send=altered_response)
    assert not (
        fixture.args["root"] / f"construction-intake-epoch-1-retry-{parent}.json"
    ).exists()
    assert len(fixture.provider().queued_tasks()) == 1
    assert all(wire["tool"] == client.SUBMIT_TOOL for wire in fixture.wires)


def test_real_signed_retry_of_unknown_parent_refuses_without_admission(signed_receiver):
    fixture = signed_receiver
    with pytest.raises(client.DirectIntakeRefusal) as refused:
        client.submit_and_wait(
            _URL,
            fixture.signer,
            **{**fixture.args, "wait_s": 0, "retry_of": _UNKNOWN},
        )
    assert not isinstance(refused.value, client.DirectConstructionPending)
    assert fixture.provider().queued_tasks() == ()
    assert len(fixture.wires) == 1
    assert fixture.cleanup_probes == []
    assert not (
        fixture.args["root"] / f"construction-intake-epoch-1-retry-{_UNKNOWN}.json"
    ).exists()


def test_real_gateway_lost_ordinary_admission_then_explicit_retry_is_one_task_each(
    signed_receiver, monkeypatch
):
    fixture = signed_receiver
    normal_send = fixture.args["send"]
    admitted = []

    def lose_ordinary_response(url, body, headers):
        status, answer = normal_send(url, body, headers)
        assert status == 202
        admitted.append(answer["outcome"]["task_id"])
        raise OSError("fixture lost ordinary admission response")

    with pytest.raises(OSError, match="lost ordinary admission"):
        _admit(fixture, send=lose_ordinary_response)
    assert not (fixture.args["root"] / "construction-intake-epoch-1.json").exists()
    fixture.reopen()
    parent = _admit(fixture)
    assert parent.value == admitted[0]
    assert fixture.provider().queued_tasks() == (parent,)
    assert fixture.wires[0]["request"] != fixture.wires[1]["request"]
    assert fixture.wires[0]["fields"] == fixture.wires[1]["fields"]
    failed_id, original = _failed_parent(fixture, monkeypatch, parent=parent)
    assert failed_id == parent.value
    child = _admit(fixture, retry_of=failed_id)
    assert child.value != parent.value
    assert len(fixture.provider()._requests) == 2
    assert fixture.provider().queued_tasks() == (child,)
    assert research.canonical_bytes(fixture.provider()._views[parent.value]) == original
    assert len(fixture.wires) == 3
