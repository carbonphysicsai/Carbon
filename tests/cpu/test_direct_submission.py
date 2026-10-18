"""The direct client signs only for its pinned DEVELOPMENT recipe receiver."""

from __future__ import annotations

import json

import pytest

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
            return 202, {
                "kind": "OUTCOME",
                "outcome": {"state": "ADMITTED", "task_id": "task-1"},
            }
        return 200, {
            "kind": "OUTCOME",
            "outcome": {
                "state": "RECONSTRUCTED",
                "task_id": "task-1",
                "qualification": False,
                "reward": False,
            },
        }

    args = dict(
        root=tmp_path,
        epoch=1,
        recipe=_recipe(),
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        read=lambda url: _facts(),
        send=send,
    )
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


def test_intake_unavailable_keeps_typed_receiver_reason(tmp_path, monkeypatch):
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    with pytest.raises(
        client.DirectIntakeRefusal, match="served_recipe_source_changed"
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
            send=lambda *_: (
                503,
                {"kind": "UNAVAILABLE", "code": "served_recipe_source_changed"},
            ),
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
