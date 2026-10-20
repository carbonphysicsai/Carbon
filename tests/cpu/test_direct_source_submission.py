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


def test_bundle_uploader_refuses_graph_before_material_or_network(
    tmp_path, monkeypatch
):
    def unexpected(*_args, **_kwargs):
        pytest.fail("graph refusal must precede material access and network")

    monkeypatch.setattr(client, "load_pinned_bundle_directory", unexpected)
    monkeypatch.setattr(client, "BittensorMessageSigner", unexpected)
    with pytest.raises(DirectIntakeRefusal) as refused:
        client.stage_bundle(
            _URL,
            "external-signer",
            directory=tmp_path / "not-read",
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            read=unexpected,
            send=unexpected,
        )
    assert refused.value.code == "construction_bundle_source_required"


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
    args = {
        "directory": directory,
        "recipe": recipe,
        "contract_digest": _CONTRACT,
        "receiver": _RECEIVER,
        "context": _CONTEXT,
        "read": lambda url: facts,
        "send": send,
    }
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


def test_source_chunk_retries_only_explicit_http_rate_with_fresh_signature(monkeypatch):
    import time

    signed = []
    reads = []

    class Signer:
        def __init__(self, signer):
            assert signer == "external-signer"

        def sign(self, body, *, receiver, nonce_ns):
            signed.append((body, nonce_ns))
            return {"signed": str(len(signed))}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    body = b"{}"

    def read(url):
        reads.append(url)
        return _stage_facts()

    def send(url, wire, headers):
        if len(signed) == 1:
            return 429, {"refused": "rate"}
        request = research.load_canonical(
            base64.b64decode(json.loads(wire)["fields"]["call_base64"]),
            research.ServiceCall,
        ).request
        reply = research.ServiceReply(
            research.ReplyStatus.OK,
            research.DirectStageSourceResultV1(
                request.name, len(body), request.content_digest, True
            ),
        )
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    assert (
        client._stage_one(
            _URL,
            "external-signer",
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            name=staging.WORKSPACE_MANIFEST,
            body=body,
            expected_digest=None,
            read=read,
            send=send,
            deadline=time.monotonic() + 10,
            pacer=client._UploadPacer(),
        )
        == "sha256:" + hashlib.sha256(body).hexdigest()
    )
    assert len(reads) == len(signed) == 2
    assert signed[0] != signed[1]

    with pytest.raises(DirectIntakeRefusal, match="rate"):
        client._stage_one(
            _URL,
            "external-signer",
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            name=staging.WORKSPACE_MANIFEST,
            body=body,
            expected_digest=None,
            read=read,
            send=lambda *_: (403, {"refused": "rate"}),
            deadline=time.monotonic() + 10,
            pacer=client._UploadPacer(),
        )


@pytest.mark.parametrize("material", [False, True])
def test_signed_stage_resumes_at_receiver_acknowledged_offset(monkeypatch, material):
    import time

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    size = client.MATERIAL_CHUNK_BYTES if material else client.CHUNK_BYTES
    body = b"x" * (2 * size) + b"end"
    offsets = []
    facts = _stage_facts()
    facts["material_staging"] = {
        "tool": client.SOURCE_TOOL,
        "operation": client.MATERIAL_OPERATION,
        "request_schema": client.MATERIAL_REQUEST_SCHEMA,
        "reply_schema": client.STAGE_REPLY_SCHEMA,
        "path": client.SUBMIT_PATH,
        "owner": "authenticated_hotkey",
    }

    def send(url, wire, headers):
        request = research.load_canonical(
            base64.b64decode(json.loads(wire)["fields"]["call_base64"]),
            research.ServiceCall,
        ).request
        offsets.append(request.offset)
        received = 2 * size if len(offsets) == 1 else len(body)
        complete = received == len(body)
        result = (
            research.DirectStageMaterialResultV1(
                request.name, received, request.content_digest, complete, False
            )
            if material
            else research.DirectStageSourceResultV1(
                request.name, received, request.content_digest, complete
            )
        )
        reply = research.ServiceReply(research.ReplyStatus.OK, result)
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    common = {
        "recipe": _recipe(),
        "contract_digest": _CONTRACT,
        "receiver": _RECEIVER,
        "context": _CONTEXT,
        "name": (
            "source.tar.gz"
            if material
            else staging.WORKSPACE_PREFIX + "a" * 64 + ".json"
        ),
        "body": body,
        "read": lambda _: facts,
        "send": send,
        "deadline": time.monotonic() + 10,
        "pacer": client._UploadPacer(),
    }
    if material:
        result = client._stage_material_one(
            _URL,
            "external-signer",
            bundle_digest="sha256:" + "b" * 64,
            final=False,
            **common,
        )
    else:
        result = client._stage_one(
            _URL, "external-signer", expected_digest=None, **common
        )
    assert result == "sha256:" + hashlib.sha256(body).hexdigest()
    assert offsets == [0, 2 * size]


def _stage_fixture(monkeypatch, material):
    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    body = b"x" * 100
    facts = _stage_facts()
    facts["material_staging"] = {
        "tool": client.SOURCE_TOOL,
        "operation": client.MATERIAL_OPERATION,
        "request_schema": client.MATERIAL_REQUEST_SCHEMA,
        "reply_schema": client.STAGE_REPLY_SCHEMA,
        "path": client.SUBMIT_PATH,
        "owner": "authenticated_hotkey",
    }

    def accepted(wire):
        request = research.load_canonical(
            base64.b64decode(json.loads(wire)["fields"]["call_base64"]),
            research.ServiceCall,
        ).request
        result = (
            research.DirectStageMaterialResultV1(
                request.name, len(body), request.content_digest, True, False
            )
            if material
            else research.DirectStageSourceResultV1(
                request.name, len(body), request.content_digest, True
            )
        )
        reply = research.ServiceReply(research.ReplyStatus.OK, result)
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    def stage(send, pacer, deadline):
        common = {
            "recipe": _recipe(),
            "contract_digest": _CONTRACT,
            "receiver": _RECEIVER,
            "context": _CONTEXT,
            "name": (
                "source.tar.gz"
                if material
                else staging.WORKSPACE_PREFIX + "a" * 64 + ".json"
            ),
            "body": body,
            "read": lambda _: facts,
            "send": send,
            "deadline": deadline,
            "pacer": pacer,
        }
        if material:
            return client._stage_material_one(
                _URL,
                "external-signer",
                bundle_digest="sha256:" + "b" * 64,
                final=False,
                **common,
            )
        return client._stage_one(
            _URL, "external-signer", expected_digest=None, **common
        )

    return body, accepted, stage


@pytest.mark.parametrize("material", [False, True])
@pytest.mark.parametrize("failure", ["reset", "pipe", "aborted", "wrapped"])
def test_a_reset_on_a_chunk_post_is_paced_and_resumed_like_a_rate_refusal(
    monkeypatch, material, failure
):
    import time
    import urllib.error

    body, accepted, stage = _stage_fixture(monkeypatch, material)
    calls = []

    def send(url, wire, headers):
        calls.append(wire)
        if len(calls) == 1:
            if failure == "wrapped":
                raise urllib.error.URLError(ConnectionResetError(104, "reset"))
            raise {
                "reset": ConnectionResetError,
                "pipe": BrokenPipeError,
                "aborted": ConnectionAbortedError,
            }[failure]()
        return accepted(wire)

    pacer = client._UploadPacer()
    result = stage(send, pacer, time.monotonic() + 30)
    assert result == "sha256:" + hashlib.sha256(body).hexdigest()
    assert len(calls) == 2 and calls[0] != calls[1]  # re-signed, not replayed
    assert pacer.paced


def test_a_persistent_reset_ends_as_the_rate_refusal_and_other_errors_pass_through(
    monkeypatch,
):
    import time

    _, _accepted, stage = _stage_fixture(monkeypatch, True)

    def always_reset(url, wire, headers):
        raise ConnectionResetError(104, "reset")

    with pytest.raises(DirectIntakeRefusal, match="rate"):
        stage(always_reset, client._UploadPacer(), time.monotonic() + 3)

    def denied(url, wire, headers):
        raise PermissionError("not a connection fault")

    with pytest.raises(PermissionError):
        stage(denied, client._UploadPacer(), time.monotonic() + 30)
