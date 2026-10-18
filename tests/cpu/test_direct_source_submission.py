"""Signed remote graph staging uses the receiver's canonical research call."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from test_direct_submission import _CONTEXT, _CONTRACT, _RECEIVER, _URL, _facts, _recipe

from carbon import research
from carbon.development_session import direct_source_submission as client
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.development_session.direct_submission import DirectIntakeRefusal
from carbon.level4 import staging


def test_bundle_material_uses_normal_signed_gateway_and_promotes_closure(
    tmp_path, monkeypatch
):
    from test_direct_material_staging import _provider
    from test_library_bundles import fixture

    from carbon.development_session.direct_material_staging import stage_material
    from carbon.development_session.library_bundles import bundle_ref

    manifest, archive, wheels, lock, license_text = fixture()
    directory = tmp_path / "bundle"
    directory.mkdir()
    (directory / "wheels").mkdir()
    (directory / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, body in [
        ("source.tar.gz", archive),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
    ]:
        (directory / name).write_bytes(body)
    for name, body in wheels.items():
        (directory / "wheels" / name).write_bytes(body)
    selected = bundle_ref(manifest, archive, wheels, lock, license_text)
    definition = _recipe().to_dict()
    definition["source"] = {"kind": "bundle", "bundle_ref": selected.to_dict()}
    definition["procedure"]["entrypoint"] = {
        "module": "carbon_candidate.build",
        "name": "build",
    }
    recipe = ConstructionRecipe.from_dict(definition)
    provider = _provider(tmp_path)
    observed = []

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER and len(body) <= client.MAX_BODY
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, wire, headers):
        assert url == _URL and headers == {"signed": "fixture"}
        outer = json.loads(wire)
        assert outer["tool"] == research.RESEARCH_NAMESPACE
        call = research.load_canonical(
            base64.b64decode(outer["fields"]["call_base64"]), research.ServiceCall
        )
        assert call.operation == "stage_research_material"
        observed.append(call.request.name)
        result = stage_material(provider, call.request)
        reply = research.ServiceReply(research.ReplyStatus.OK, result)
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    facts = {
        **_facts(),
        "tools": ["construction_submit", "construction_status", client.SOURCE_TOOL],
        "material_staging": {
            "tool": client.SOURCE_TOOL,
            "operation": client.MATERIAL_OPERATION,
            "request_schema": client.MATERIAL_REQUEST_SCHEMA,
            "reply_schema": client.STAGE_REPLY_SCHEMA,
            "path": client.SUBMIT_PATH,
            "owner": "authenticated_hotkey",
        },
    }
    args = dict(
        directory=directory,
        recipe=recipe,
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        read=lambda url: facts,
        send=send,
    )
    result = client.stage_bundle(_URL, "external-signer", **args)
    assert result["bundle_ref"] == selected.to_dict()
    assert result["complete"] and not result["official_eligible"]
    assert observed[-1] == "bundle.json"
    assert client.stage_bundle(_URL, "external-signer", **args) == result


def _source():
    document = b"{" + b" " * 9000 + b"}"
    document_digest = "sha256:" + hashlib.sha256(document).hexdigest()
    manifest = json.dumps(
        {"documents": {"forward": document_digest}}, sort_keys=True
    ).encode()
    envelope = staging.envelope(manifest, {document_digest: document})
    definition = _recipe().to_dict()
    definition["source"]["submission_digest"] = envelope["submission"]
    return ConstructionRecipe.from_dict(definition), envelope


def _stage_facts():
    return {
        **_facts(),
        "tools": ["construction_submit", "construction_status", client.SOURCE_TOOL],
        "source_staging": {
            "tool": client.SOURCE_TOOL,
            "operation": client.STAGE_OPERATION,
            "request_schema": client.STAGE_REQUEST_SCHEMA,
            "reply_schema": client.STAGE_REPLY_SCHEMA,
            "path": client.SUBMIT_PATH,
            "owner": "authenticated_hotkey",
        },
    }


def test_graph_files_stage_documents_then_manifest_on_same_signed_receiver(monkeypatch):
    recipe, envelope = _source()
    observed = []

    def local_graph(ledger, owner, actual):
        assert ledger is local_ledger and owner == "owner-hotkey" and actual == recipe
        return json.dumps(envelope).encode()

    local_ledger = object()
    monkeypatch.setattr(client, "graph_envelope_from_workspace", local_graph)

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            assert receiver == _RECEIVER
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)

    def send(url, wire, headers):
        assert url == _URL and headers == {"signed": "fixture"}
        outer = json.loads(wire)
        assert outer["tool"] == research.RESEARCH_NAMESPACE
        assert outer["challenge_id"] == "synthetic-linear-field-2d"
        assert outer["challenge_version"] == "1.3"
        assert set(outer["fields"]) == {"call_base64"}
        call = research.load_canonical(
            base64.b64decode(outer["fields"]["call_base64"]),
            research.ServiceCall,
        )
        assert call.namespace == research.RESEARCH_NAMESPACE
        assert call.operation == "stage_research_source"
        request = call.request
        assert type(request) is research.DirectStageSourceRequestV1
        assert request.challenge_key.challenge_id == recipe.to_dict()["challenge"]["id"]
        assert request.challenge_key.version == recipe.to_dict()["challenge"]["version"]
        observed.append(request)
        reply = research.ServiceReply(
            research.ReplyStatus.OK,
            research.DirectStageSourceResultV1(
                request.name,
                request.offset + len(request.chunk),
                request.content_digest,
                request.offset + len(request.chunk) == request.total_bytes,
            ),
        )
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    result = client.stage_graph(
        _URL,
        "external-signer",
        ledger=local_ledger,
        owner="owner-hotkey",
        recipe=recipe,
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        expected_manifest_digest="sha256:" + "b" * 64,
        read=lambda url: _stage_facts(),
        send=send,
    )
    assert [request.name for request in observed] == [
        staging.WORKSPACE_PREFIX + next(iter(envelope["documents"]))[7:] + ".json",
        staging.WORKSPACE_PREFIX + next(iter(envelope["documents"]))[7:] + ".json",
        staging.WORKSPACE_MANIFEST,
    ]
    assert observed[0].offset == 0 and observed[1].offset == client.CHUNK_BYTES
    assert observed[0].expected_digest is None
    assert observed[-1].expected_digest == "sha256:" + "b" * 64
    assert (
        result["submission_digest"] == recipe.to_dict()["source"]["submission_digest"]
    )
    assert result["files"] == 2 and result["complete"] is True
    assert result["official_eligible"] is False


def test_nested_error_refuses_even_when_http_succeeds(monkeypatch):
    recipe, envelope = _source()
    monkeypatch.setattr(
        client,
        "graph_envelope_from_workspace",
        lambda *_: json.dumps(envelope).encode(),
    )

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    reply = research.ServiceReply(
        research.ReplyStatus.ERROR,
        research.public_error(research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT),
    )
    wrapped = {
        "schema": client.STAGE_REPLY_SCHEMA,
        "protocol_reply_base64": base64.b64encode(
            research.canonical_bytes(reply)
        ).decode(),
    }
    with pytest.raises(
        DirectIntakeRefusal, match="construction_source_idempotency_conflict"
    ):
        client.stage_graph(
            _URL,
            "external-signer",
            ledger=object(),
            owner="owner-hotkey",
            recipe=recipe,
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: _stage_facts(),
            send=lambda *_: (200, wrapped),
        )


def test_complete_receiver_file_skips_remaining_replay_chunks(monkeypatch):
    recipe, envelope = _source()
    monkeypatch.setattr(
        client,
        "graph_envelope_from_workspace",
        lambda *_: json.dumps(envelope).encode(),
    )

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    names = []

    def send(url, wire, headers):
        outer = json.loads(wire)
        call = research.load_canonical(
            base64.b64decode(outer["fields"]["call_base64"]), research.ServiceCall
        )
        request = call.request
        names.append(request.name)
        # The receiver already holds the full file and verifies this chunk.
        reply = research.ServiceReply(
            research.ReplyStatus.OK,
            research.DirectStageSourceResultV1(
                request.name, request.total_bytes, request.content_digest, True
            ),
        )
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    client.stage_graph(
        _URL,
        "external-signer",
        ledger=object(),
        owner="owner-hotkey",
        recipe=recipe,
        contract_digest=_CONTRACT,
        receiver=_RECEIVER,
        context=_CONTEXT,
        read=lambda url: _stage_facts(),
        send=send,
    )
    assert len(names) == 2  # one check per already complete document and manifest
    assert names[-1] == staging.WORKSPACE_MANIFEST


def test_wrong_receiver_staging_capability_refuses_before_signing(monkeypatch):
    recipe, envelope = _source()
    monkeypatch.setattr(
        client,
        "graph_envelope_from_workspace",
        lambda *_: json.dumps(envelope).encode(),
    )

    def unexpected_signer(_):
        raise AssertionError("nothing may be signed")

    monkeypatch.setattr(client, "BittensorMessageSigner", unexpected_signer)
    wrong = _stage_facts()
    wrong["source_staging"] = {**wrong["source_staging"], "owner": "caller_selected"}
    with pytest.raises(
        DirectIntakeRefusal, match="construction_source_staging_unavailable"
    ):
        client.stage_graph(
            _URL,
            "external-signer",
            ledger=object(),
            owner="owner-hotkey",
            recipe=recipe,
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=lambda url: wrong,
            send=lambda *_: pytest.fail("no send"),
        )
