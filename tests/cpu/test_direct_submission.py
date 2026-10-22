"""The direct client signs only for its pinned DEVELOPMENT recipe receiver."""

from __future__ import annotations

import json

import pytest

from carbon.battery import challenge as battery_challenge
from carbon.chain.models import ChainContext
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.development_session import direct_submission as client
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.reconstruction.served_recipe_contract import registered

_DIGEST = "sha256:" + "a" * 64
_CONTRACT = registered("synthetic-linear-field-2d", "1.3").digest
_RECEIVER = "validator-pinned"
_URL = "http://127.0.0.1:9080"
_CONTEXT = ChainContext(
    "testnet", "wss://chain.example", "fixture", "0x" + "1" * 64, 567
)
_PINNED = {
    "contract_digest": _CONTRACT,
    "rule_digest": "sha256:" + "b" * 64,
    "implementation_digest": "sha256:" + "c" * 64,
    "identities_digest": "sha256:" + "d" * 64,
}


def _recipe():
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": bundle_material_v5()["construction_kit"],
            "source": {"kind": "graph", "submission_digest": _DIGEST},
            "procedure": {
                "entrypoint": None,
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": bundle_material_v5()["construction_kit"][
                    "interface_digest"
                ],
            },
        }
    )


def _facts():
    return {
        "schema": client.PUBLIC_SCHEMA,
        "network": _CONTEXT.network,
        "genesis": _CONTEXT.genesis_hash,
        "netuid": _CONTEXT.netuid,
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
        "receiver": _RECEIVER,
        "snapshot": {"id": "snapshot-1"},
        "discovery_path": client.INFO_PATH,
        "path": client.SUBMIT_PATH,
        "tools": [client.SUBMIT_TOOL, client.STATUS_TOOL],
        "served_contracts": [{"level": 0, "digest": _CONTRACT}],
        "score_pack": None,
        "qualification": False,
        "reward": False,
    }


def _answer(state, *, task_id="task-1", **outcome_fields):
    outcome = {
        "schema": client.OUTCOME_SCHEMA,
        "submission_id": task_id,
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.3"},
        "state": state,
        "evidence": "DEVELOPMENT_PUBLIC_SYNTHETIC",
        "qualification": False,
        "reward": False,
        "task_id": task_id,
        **outcome_fields,
    }
    if state == "RECONSTRUCTED":
        outcome.setdefault("state_digest", "sha256:" + "e" * 64)
        outcome.setdefault("predictions_digest", "sha256:" + "f" * 64)
    return {
        "schema": client.RESULT_SCHEMA,
        "kind": "OUTCOME",
        "code": None,
        "pinned": dict(_PINNED),
        "outcome": outcome,
        "evidence": "DEVELOPMENT",
        "qualification": False,
        "reward": False,
    }


def test_client_accepts_only_registered_battery_evidence_label():
    contract = registered(
        battery_challenge.CHALLENGE.challenge_id,
        battery_challenge.CHALLENGE.version,
    )
    answer = _answer("ADMITTED")
    answer["pinned"]["contract_digest"] = contract.digest
    answer["outcome"]["challenge"] = {
        "id": battery_challenge.CHALLENGE.challenge_id,
        "version": battery_challenge.CHALLENGE.version,
    }
    answer["outcome"]["evidence"] = contract.evidence_label
    observed, _ = client._outcome(
        answer,
        contract_digest=contract.digest,
        challenge=battery_challenge.CHALLENGE,
        evidence_label=contract.evidence_label,
    )
    assert observed["state"] == "ADMITTED"
    answer["outcome"]["evidence"] = "DEVELOPMENT_PUBLIC_SYNTHETIC"
    with pytest.raises(client.DirectIntakeRefusal):
        client._outcome(
            answer,
            contract_digest=contract.digest,
            challenge=battery_challenge.CHALLENGE,
            evidence_label=contract.evidence_label,
        )


def test_signed_direct_submission_records_task_and_restart_only_polls(
    tmp_path, monkeypatch
):
    signed, sent = [], []

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER
            signed.append(json.loads(body))
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        assert url == _URL and headers == {"signed": "fixture"}
        request = json.loads(body)
        sent.append(request)
        if request["tool"] == client.SUBMIT_TOOL:
            assert request["fields"]["contract_digest"] == _CONTRACT
            assert json.loads(request["fields"]["strategy_json"]) == _recipe().to_dict()
            return 202, _answer("ADMITTED")
        return 200, _answer("RECONSTRUCTED")

    args = {
        "root": tmp_path,
        "epoch": 1,
        "recipe": _recipe(),
        "contract_digest": _CONTRACT,
        "receiver": _RECEIVER,
        "context": _CONTEXT,
        "read": lambda url: _facts(),
        "send": send,
    }
    first = client.submit_and_wait(_URL, "external-signer", **args)
    assert first["state"] == "RECONSTRUCTED"
    record = json.loads((tmp_path / "construction-intake-epoch-1.json").read_bytes())
    assert record["recipe_digest"] == _recipe().digest
    assert record["submission_id"] == "task-1"
    assert client.submit_and_wait(_URL, "external-signer", **args) == first
    assert [request["tool"] for request in sent] == [
        client.SUBMIT_TOOL,
        client.STATUS_TOOL,
        client.STATUS_TOOL,
    ]
    assert len(signed) == len(sent)


def test_zero_wait_retains_admitted_task_without_immediate_signed_status(
    tmp_path, monkeypatch
):
    signed, sent = [], []

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER
            signed.append(json.loads(body)["tool"])
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        assert url == _URL and headers == {"signed": "fixture"}
        tool = json.loads(body)["tool"]
        sent.append(tool)
        return (202 if tool == client.SUBMIT_TOOL else 200), _answer(
            "ADMITTED" if tool == client.SUBMIT_TOOL else "RECONSTRUCTED"
        )

    args = {
        "root": tmp_path,
        "epoch": 1,
        "recipe": _recipe(),
        "contract_digest": _CONTRACT,
        "receiver": _RECEIVER,
        "context": _CONTEXT,
        "read": lambda url: _facts(),
        "send": send,
    }
    for _ in range(2):
        with pytest.raises(
            client.DirectIntakeRefusal, match="construction_task_queued"
        ):
            client.submit_and_wait(_URL, "external-signer", wait_s=0, **args)
    assert sent == signed == [client.SUBMIT_TOOL]
    assert (
        json.loads((tmp_path / "construction-intake-epoch-1.json").read_bytes())[
            "submission_id"
        ]
        == "task-1"
    )
    assert (
        client.submit_and_wait(_URL, "external-signer", wait_s=30, **args)["state"]
        == "RECONSTRUCTED"
    )
    assert sent == signed == [client.SUBMIT_TOOL, client.STATUS_TOOL]


@pytest.mark.parametrize("wait_s", [0, 30])
@pytest.mark.parametrize("state", sorted(client.TERMINAL))
def test_retried_submit_preserves_an_already_terminal_idempotent_task(
    tmp_path, monkeypatch, wait_s, state
):
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    calls = []

    def send(url, body, headers):
        tool = json.loads(body)["tool"]
        calls.append(tool)
        assert tool == client.SUBMIT_TOOL
        fields = (
            {} if state == "RECONSTRUCTED" else {"failure": {"code": "fixture_failure"}}
        )
        return 202, _answer(state, task_id="same-task", **fields)

    result = client.submit_and_wait(
        _URL,
        "external-signer",
        root=tmp_path,
        epoch=1,
        recipe=_recipe(),
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        read=lambda url: _facts(),
        send=send,
        wait_s=wait_s,
    )
    expected_fields = (
        {} if state == "RECONSTRUCTED" else {"failure": {"code": "fixture_failure"}}
    )
    assert result == _answer(state, task_id="same-task", **expected_fields)["outcome"]
    assert calls == [client.SUBMIT_TOOL]
    assert (
        json.loads((tmp_path / "construction-intake-epoch-1.json").read_bytes())[
            "submission_id"
        ]
        == "same-task"
    )


@pytest.mark.parametrize(
    ("changed", "reason"),
    [
        ("missing_state_digest", "construction_intake_answer_unrecognised"),
        ("wrong_outcome_schema", "construction_intake_answer_unrecognised"),
        ("wrong_challenge", "construction_intake_answer_unrecognised"),
        ("wrong_task_identity", "construction_intake_answer_unrecognised"),
        ("wrong_pinned_identity", "construction_intake_identity_mismatch"),
        ("extra_private_field", "construction_intake_answer_unrecognised"),
    ],
)
def test_incomplete_or_different_terminal_result_never_becomes_success(
    tmp_path, monkeypatch, changed, reason
):
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        if json.loads(body)["tool"] == client.SUBMIT_TOOL:
            return 202, _answer("ADMITTED")
        result = _answer("RECONSTRUCTED")
        if changed == "missing_state_digest":
            del result["outcome"]["state_digest"]
        elif changed == "wrong_outcome_schema":
            result["outcome"]["schema"] = "other.outcome"
        elif changed == "wrong_challenge":
            result["outcome"]["challenge"]["version"] = "1.2"
        elif changed == "wrong_task_identity":
            result["outcome"]["submission_id"] = "another-task"
        elif changed == "wrong_pinned_identity":
            result["pinned"]["implementation_digest"] = "sha256:" + "1" * 64
        else:
            result["outcome"]["private_seed"] = "must-not-appear"
        return 200, result

    with pytest.raises(client.DirectIntakeRefusal, match=reason):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=send,
        )


def test_incomplete_terminal_submit_does_not_create_a_success_record(
    tmp_path, monkeypatch
):
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    incomplete = _answer("RECONSTRUCTED")
    del incomplete["outcome"]["predictions_digest"]
    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_intake_answer_unrecognised"
    ):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=lambda *_: (202, incomplete),
        )
    assert not (tmp_path / "construction-intake-epoch-1.json").exists()


def test_wrong_registered_contract_refuses_before_contact(tmp_path, monkeypatch):
    def unexpected_signer(_):
        raise AssertionError("nothing may be signed")

    monkeypatch.setattr(client, "BittensorMessageSigner", unexpected_signer)
    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_contract_binding_mismatch"
    ):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_DIGEST,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: pytest.fail("no intake read"),
            send=lambda *_: pytest.fail("no send"),
        )


def test_recorded_task_rejects_receiver_drift_without_contact(tmp_path):
    recipe = _recipe()
    path = tmp_path / "construction-intake-epoch-1.json"
    path.write_text(
        json.dumps(
            {
                **client._binding(_URL, recipe, _CONTRACT, _RECEIVER, _CONTEXT, 1),
                "submission_id": "task-1",
                "pinned": dict(_PINNED),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        client.DirectIntakeRefusal,
        match="construction_intake_changed_since_submission",
    ):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=recipe,
            contract_digest=_CONTRACT,
            receiver="another-receiver",
            context=_CONTEXT,
            read=lambda url: pytest.fail("no intake read"),
            send=lambda *_: pytest.fail("no send"),
        )


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            (503, {"kind": "UNAVAILABLE", "code": "served_recipe_source_changed"}),
            "served_recipe_source_changed",
        ),
        ((503, {}), "construction_intake_unavailable"),
    ],
)
def test_intake_unavailable_keeps_typed_receiver_reason(
    tmp_path, monkeypatch, response, expected
):
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    with pytest.raises(client.DirectIntakeRefusal, match=expected):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=lambda *_: response,
        )


@pytest.mark.parametrize(
    ("changed", "code"),
    [
        ({"receiver": "other-validator"}, "intake_receiver_mismatch"),
        ({"genesis": "0x" + "2" * 64}, "construction_intake_chain_mismatch"),
        (
            {"challenge": {"id": "battery", "version": "1.0"}},
            "construction_intake_challenge_mismatch",
        ),
        ({"served_contracts": []}, "construction_contract_not_served"),
        ({"score_pack": _DIGEST}, "construction_intake_contract_mismatch"),
    ],
)
def test_wrong_intake_facts_refuse_before_signing(tmp_path, monkeypatch, changed, code):
    def unexpected_signer(_):
        raise AssertionError("nothing may be signed")

    monkeypatch.setattr(client, "BittensorMessageSigner", unexpected_signer)
    facts = {**_facts(), **changed}
    with pytest.raises(client.DirectIntakeRefusal, match=code):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: facts,
            send=lambda *_: pytest.fail("nothing may be sent"),
        )


@pytest.mark.parametrize(
    "phase", ["admit_read", "admit_send", "status_read", "status_send"]
)
def test_rate_retry_preserves_task_and_refreshes_signed_exchange(
    tmp_path, monkeypatch, phase
):
    now, sleeps, signed, sent = [0.0], [], [], []
    reads = [0]
    refused = [False]

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER
            signed.append(json.loads(body)["tool"])
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def read(url):
        reads[0] += 1
        target = "admit_read" if not sent else "status_read"
        if phase == target and not refused[0]:
            refused[0] = True
            raise client.DirectIntakeRateLimit()
        return _facts()

    def send(url, body, headers):
        tool = json.loads(body)["tool"]
        sent.append(tool)
        target = "admit_send" if tool == client.SUBMIT_TOOL else "status_send"
        if phase == target and not refused[0]:
            refused[0] = True
            return 429, {"refused": "rate"}
        return (202 if tool == client.SUBMIT_TOOL else 200), _answer(
            "ADMITTED" if tool == client.SUBMIT_TOOL else "RECONSTRUCTED"
        )

    result = client.submit_and_wait(
        _URL,
        "external-signer",
        root=tmp_path,
        epoch=1,
        recipe=_recipe(),
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        read=read,
        send=send,
        clock=lambda: now[0],
        sleep=sleep,
        wait_s=10,
    )
    assert result["state"] == "RECONSTRUCTED" and result["task_id"] == "task-1"
    assert sleeps == [1.0, 1.05]
    assert signed == sent
    assert sent.count(client.SUBMIT_TOOL) == (2 if phase == "admit_send" else 1)
    assert sent.count(client.STATUS_TOOL) == (2 if phase == "status_send" else 1)
    record = json.loads((tmp_path / "construction-intake-epoch-1.json").read_bytes())
    assert record["submission_id"] == "task-1"


@pytest.mark.parametrize("code", ["rate", "IDENTITY_INVALID"])
def test_status_rate_deadline_or_auth_refusal_keeps_original_admission(
    tmp_path, monkeypatch, code
):
    now, sleeps, sent = [0.0], [], []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def send(url, body, headers):
        tool = json.loads(body)["tool"]
        sent.append(tool)
        if tool == client.SUBMIT_TOOL:
            return 202, _answer("ADMITTED")
        return (429 if code == "rate" else 401), {"refused": code}

    with pytest.raises(client.DirectIntakeRefusal, match=code):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=send,
            clock=lambda: now[0],
            sleep=sleep,
            wait_s=2,
        )
    assert sent.count(client.SUBMIT_TOOL) == 1
    assert sent.count(client.STATUS_TOOL) == 1
    assert sleeps == ([1.0, 1.0] if code == "rate" else [])
    assert (
        json.loads((tmp_path / "construction-intake-epoch-1.json").read_bytes())[
            "submission_id"
        ]
        == "task-1"
    )


@pytest.mark.parametrize("status", [200, 401, 500])
def test_non_429_rate_payload_never_replays_submission(tmp_path, monkeypatch, status):
    calls = []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        calls.append(json.loads(body)["tool"])
        return status, {"refused": "rate"}

    with pytest.raises(client.DirectIntakeRefusal, match="rate"):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=send,
            sleep=lambda seconds: pytest.fail("non-429 must not retry"),
        )
    assert calls == [client.SUBMIT_TOOL]
    assert not (tmp_path / "construction-intake-epoch-1.json").exists()


def test_observation_deadline_never_starts_a_late_exchange(tmp_path, monkeypatch):
    now, reads, signed, sent = [0.0], [], [], []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            signed.append(json.loads(body)["tool"])
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def read(url):
        reads.append(url)
        return _facts()

    def send(url, body, headers):
        tool = json.loads(body)["tool"]
        sent.append(tool)
        return (202 if tool == client.SUBMIT_TOOL else 200), _answer("ADMITTED")

    def sleep(seconds):
        now[0] += seconds

    with pytest.raises(client.DirectIntakeRefusal, match="construction_task_queued"):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=read,
            send=send,
            clock=lambda: now[0],
            sleep=sleep,
            wait_s=2,
        )
    assert now == [2.0]
    assert reads == [_URL, _URL]
    assert signed == sent == [client.SUBMIT_TOOL, client.STATUS_TOOL]
    assert (
        json.loads((tmp_path / "construction-intake-epoch-1.json").read_bytes())[
            "submission_id"
        ]
        == "task-1"
    )


@pytest.mark.parametrize(
    "error", [TimeoutError("fixture"), client.urllib.error.URLError("fixture")]
)
def test_ambiguous_send_failure_never_replays_submission(tmp_path, monkeypatch, error):
    sent = []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        sent.append(json.loads(body)["tool"])
        raise error

    with pytest.raises(type(error)):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=send,
            sleep=lambda seconds: pytest.fail("ambiguous send must not retry"),
        )
    assert sent == [client.SUBMIT_TOOL]
    assert not (tmp_path / "construction-intake-epoch-1.json").exists()


def test_one_token_per_second_receiver_does_not_starve_post_after_retry(
    tmp_path, monkeypatch
):
    now, tokens, updated = [0.0], [1.0], [0.0]
    accepted = []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def allow():
        tokens[0] = min(1.0, tokens[0] + now[0] - updated[0])
        updated[0] = now[0]
        if tokens[0] < 1:
            return False
        tokens[0] -= 1
        return True

    def read(url):
        if not allow():
            raise client.DirectIntakeRateLimit()
        return _facts()

    def send(url, body, headers):
        if not allow():
            return 429, {"refused": "rate"}
        tool = json.loads(body)["tool"]
        accepted.append(tool)
        return (202 if tool == client.SUBMIT_TOOL else 200), _answer(
            "ADMITTED" if tool == client.SUBMIT_TOOL else "RECONSTRUCTED"
        )

    def sleep(seconds):
        now[0] += seconds

    result = client.submit_and_wait(
        _URL,
        "external-signer",
        root=tmp_path,
        epoch=1,
        recipe=_recipe(),
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        read=read,
        send=send,
        clock=lambda: now[0],
        sleep=sleep,
        wait_s=10,
    )
    assert result["state"] == "RECONSTRUCTED"
    assert accepted == [client.SUBMIT_TOOL, client.STATUS_TOOL]
    assert now[0] < 10


@pytest.mark.parametrize("phase", ["admission", "observation"])
def test_discovery_exhausting_deadline_never_starts_signing(
    tmp_path, monkeypatch, phase
):
    now, signed, sent = [0.0], [], []

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            signed.append(json.loads(body)["tool"])
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        sent.append(json.loads(body)["tool"])
        return 202, _answer("ADMITTED")

    args = {
        "root": tmp_path,
        "epoch": 1,
        "recipe": _recipe(),
        "contract_digest": _CONTRACT,
        "receiver": _RECEIVER,
        "context": _CONTEXT,
        "send": send,
        "clock": lambda: now[0],
    }
    if phase == "observation":
        with pytest.raises(
            client.DirectIntakeRefusal, match="construction_task_queued"
        ):
            client.submit_and_wait(
                _URL, "external-signer", read=lambda url: _facts(), wait_s=0, **args
            )
        signed.clear()
        sent.clear()

    def read(url):
        now[0] = 30 if phase == "admission" else 2
        return _facts()

    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_request_deadline"
    ):
        client.submit_and_wait(_URL, "external-signer", read=read, wait_s=2, **args)
    assert signed == sent == []
    assert (tmp_path / "construction-intake-epoch-1.json").exists() == (
        phase == "observation"
    )


def test_remote_observation_requires_retained_admission_before_signing_or_contact(
    tmp_path, monkeypatch
):
    def forbidden(*_args, **_kwargs):
        pytest.fail("observation may not submit, sign, or contact without admission")

    monkeypatch.setattr(client, "BittensorMessageSigner", forbidden)
    with pytest.raises(client.DirectIntakeRefusal, match="admission_record_required"):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=forbidden,
            send=forbidden,
            observe_only=True,
            wait_s=10,
        )


def test_remote_observation_is_signed_status_only_and_keeps_original_pins(
    tmp_path, monkeypatch
):
    record = client._record_path(tmp_path, 1)
    record.write_text(
        json.dumps(
            {
                **client._binding(_URL, _recipe(), _CONTRACT, _RECEIVER, _CONTEXT, 1),
                "submission_id": "task-1",
                "pinned": _PINNED,
            }
        )
    )
    calls = []

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER
            calls.append(json.loads(body))
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, body, headers):
        assert url == _URL
        assert json.loads(body)["tool"] == client.STATUS_TOOL
        return 200, _answer("RECONSTRUCTED")

    args = {
        "root": tmp_path,
        "epoch": 1,
        "recipe": _recipe(),
        "contract_digest": _CONTRACT,
        "receiver": _RECEIVER,
        "context": _CONTEXT,
        "read": lambda _url: _facts(),
        "send": send,
        "observe_only": True,
        "wait_s": 10,
    }
    original = record.read_bytes()
    result = client.submit_and_wait(_URL, "external-signer", **args)
    assert result["state"] == "RECONSTRUCTED"
    assert [request["tool"] for request in calls] == [client.STATUS_TOOL]
    assert calls[0]["fields"] == {"submission_id": "task-1"}
    assert record.read_bytes() == original

    with pytest.raises(client.DirectIntakeRefusal, match="changed_since_submission"):
        client.submit_and_wait(
            _URL, "external-signer", **{**args, "receiver": "another-receiver"}
        )
    assert len(calls) == 1


@pytest.mark.parametrize("wait_s", [0, -1, 31, float("inf"), float("nan"), True])
def test_remote_observation_rejects_unbounded_wait_before_contact(tmp_path, wait_s):
    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid observation budget must refuse before contact")

    with pytest.raises(client.DirectIntakeRefusal, match="observation_wait_invalid"):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=forbidden,
            send=forbidden,
            observe_only=True,
            wait_s=wait_s,
        )


def test_remote_observation_cannot_submit_if_admission_disappears_after_preflight(
    tmp_path, monkeypatch
):
    from pathlib import Path

    record = client._record_path(tmp_path, 1)
    record.write_text("{}")
    exists = Path.exists
    monkeypatch.setattr(
        Path, "exists", lambda path: False if path == record else exists(path)
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("read-only observation reached a submission exchange")

    monkeypatch.setattr(client, "BittensorMessageSigner", forbidden)
    with pytest.raises(client.DirectIntakeRefusal, match="admission_record_required"):
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=forbidden,
            send=forbidden,
            observe_only=True,
            wait_s=10,
        )


@pytest.mark.parametrize("replacement", [{"submission_id": "task-swapped"}, {}])
def test_pending_observation_keeps_validated_id_after_journal_replacement(
    tmp_path, monkeypatch, replacement
):
    record = client._record_path(tmp_path, 1)
    record.write_text(
        json.dumps(
            {
                **client._binding(_URL, _recipe(), _CONTRACT, _RECEIVER, _CONTEXT, 1),
                "submission_id": "task-1",
                "pinned": _PINNED,
            }
        ),
        encoding="utf-8",
    )
    now = [0.0]
    calls = []

    class Signer:
        def __init__(self, _signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER
            calls.append(json.loads(body))
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(_url, body, _headers):
        request = json.loads(body)
        assert request["tool"] == client.STATUS_TOOL
        assert request["fields"] == {"submission_id": "task-1"}
        record.write_text(json.dumps(replacement), encoding="utf-8")
        now[0] = 10.0
        return 200, _answer("ADMITTED")

    with pytest.raises(client.DirectConstructionPending) as queued:
        client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=1,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda _url: _facts(),
            send=send,
            clock=lambda: now[0],
            observe_only=True,
            wait_s=10,
        )
    assert queued.value.code == "construction_task_queued"
    assert queued.value.task_id == "task-1"
    assert [call["tool"] for call in calls] == [client.STATUS_TOOL]


def test_same_recipe_refusal_returns_the_earlier_result_and_records_no_epoch(
    tmp_path, monkeypatch
):
    # Validator ruling (a): the receiver refuses a recipe it already graded for
    # this hotkey on its exam set, with the earlier result. The epoch gets no
    # admission record (its exam stays unused) and the refusal keeps its code.
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    earlier = _answer("RECONSTRUCTED", task_id="task-epoch-1")
    refused = {**earlier, "kind": "REFUSED", "code": "same_recipe_already_submitted"}
    sent = []

    def send(*arguments):
        sent.append(arguments)
        return 400, refused

    def submit(answer_send):
        return client.submit_and_wait(
            _URL,
            "external-signer",
            root=tmp_path,
            epoch=2,
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _facts(),
            send=answer_send,
        )

    with pytest.raises(client.DirectSameRecipeSubmitted) as caught:
        submit(send)
    assert caught.value.code == "same_recipe_already_submitted"
    assert isinstance(caught.value, client.DirectIntakeRefusal)
    assert caught.value.earlier == earlier["outcome"]
    assert len(sent) == 1
    assert not (tmp_path / "construction-intake-epoch-2.json").exists()
    # A refusal whose earlier result is not a valid outcome is never trusted.
    malformed = {**refused, "outcome": {**refused["outcome"], "task_id": ""}}
    with pytest.raises(
        client.DirectIntakeRefusal, match="construction_intake_answer_unrecognised"
    ):
        submit(lambda *_: (400, malformed))
