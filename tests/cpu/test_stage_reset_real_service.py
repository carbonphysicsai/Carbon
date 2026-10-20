"""A reset after the receiver stored a chunk is safe to resend (real material staging).

The client cannot tell a lost 429 from a lost 200, so it sends the same chunk again.
This pins that property against the actual staging service, not a fake.
"""

import base64
import json

import pytest
from test_direct_material_staging import _files, _provider
from test_direct_source_submission import (
    _CONTEXT,
    _CONTRACT,
    _RECEIVER,
    _URL,
    _recipe,
    _stage_facts,
)

from carbon import research
from carbon.development_session import direct_source_submission as client
from carbon.development_session.direct_material_staging import stage_material
from carbon.development_session.library_environment_cache import (
    inspect_staged_bundle_material,
)


def test_replayed_chunk_after_a_lost_reply_completes_the_real_closure(
    tmp_path, monkeypatch
):
    import time

    class Signer:
        def __init__(self, signer):
            pass

        def sign(self, body, *, receiver, nonce_ns):
            return {"signed": "fixture"}

    monkeypatch.setattr(client, "BittensorMessageSigner", Signer)
    # Small chunks so each file takes several POSTs.
    monkeypatch.setattr(client, "MATERIAL_CHUNK_BYTES", 64)
    provider = _provider(tmp_path)
    ref, files = _files()
    facts = _stage_facts()
    facts["material_staging"] = {
        "tool": client.SOURCE_TOOL,
        "operation": client.MATERIAL_OPERATION,
        "request_schema": client.MATERIAL_REQUEST_SCHEMA,
        "reply_schema": client.STAGE_REPLY_SCHEMA,
        "path": client.SUBMIT_PATH,
        "owner": "authenticated_hotkey",
    }
    posts = []
    lost = {"count": 0}

    def send(url, wire, headers):
        request = research.load_canonical(
            base64.b64decode(json.loads(wire)["fields"]["call_base64"]),
            research.ServiceCall,
        ).request
        # The staging service really applies the chunk ...
        result = stage_material(provider, request)
        posts.append((request.name, request.offset))
        # ... and on the second POST of the first file the reply is lost to a reset.
        if len(posts) == 2 and not lost["count"]:
            lost["count"] += 1
            raise ConnectionResetError(104, "connection reset by peer")
        reply = research.ServiceReply(research.ReplyStatus.OK, result)
        return 200, {
            "schema": client.STAGE_REPLY_SCHEMA,
            "protocol_reply_base64": base64.b64encode(
                research.canonical_bytes(reply)
            ).decode(),
        }

    pacer = client._UploadPacer()
    for name, body in files:
        client._stage_material_one(
            _URL,
            "external-signer",
            recipe=_recipe(),
            contract_digest=_CONTRACT,
            receiver=_RECEIVER,
            context=_CONTEXT,
            bundle_digest=ref.bundle_digest,
            name=name,
            body=body,
            final=name == "bundle.json",
            read=lambda _: facts,
            send=send,
            deadline=time.monotonic() + 60,
            pacer=pacer,
        )
    assert lost["count"] == 1 and pacer.paced
    # The second POST (offset 64) was applied, its reply lost, and the same offset resent.
    first = files[0][0]
    assert posts[:3] == [(first, 0), (first, 64), (first, 64)]
    # The closure the receiver holds is the exact, validated bundle.
    staged = inspect_staged_bundle_material(provider.image_resolver.cache_root, ref)
    assert staged is not None


def test_replay_with_different_bytes_is_still_refused_by_the_real_service(tmp_path):
    from test_direct_material_staging import _request

    from carbon.research.errors import ResearchServiceErrorCode
    from carbon.research.lifecycle import ResearchTaskProviderError

    provider = _provider(tmp_path)
    ref, files = _files()
    name, body = files[0]
    first = _request(ref.bundle_digest, name, body, 0, body[:64])
    stage_material(provider, first)
    forged = _request(ref.bundle_digest, name, body, 0, b"y" * 64)
    with pytest.raises(ResearchTaskProviderError) as refused:
        stage_material(provider, forged)
    assert refused.value.code is not None
    assert isinstance(refused.value.code, ResearchServiceErrorCode)
