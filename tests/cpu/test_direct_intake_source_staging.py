"""One signed receiver stages exact graph bytes for its construction provider.

No worker or model is run here. Admission/custody fixtures do not establish
container security, a scored Challenge, or an installed end-to-end result.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_c08_authenticated_miner_mcp import (
    CONTEXT,
    NOW,
    _headers,
    _snapshot,
    _Verifier,
)
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.battery.intake import SnapshotWindow
from carbon.chain.models import Participant
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.direct_intake import (
    INFO_PATH,
    SOURCE_REPLY_SCHEMA,
    SUBMIT_PATH,
    SUBMIT_TOOL,
    DirectRecipeIntake,
)
from carbon.development_session.construction_recipe import (
    RecipeRefused,
    graph_envelope_from_workspace,
)
from carbon.development_session.research_workspace import (
    ResearchWorkspace,
    WorkspaceFileMissing,
)
from carbon.development_session.library_bundles import bundle_ref
from carbon.development_session.library_environment_cache import (
    inspect_staged_bundle_material,
)
from carbon.level4 import staging, submission
from carbon.transport.models import MAX_BODY, message
from carbon.transport.store import ReceiptJournal


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    request, factory, discovery = _fixture(
        tmp_path / "direct", monkeypatch, material=bundle_material_v5()
    )
    provider = factory()
    attempts = tmp_path / "attempts"
    attempts.mkdir(mode=0o700)
    attempts.chmod(0o700)
    state = _snapshot()
    state = replace(
        state, participants=state.participants + (Participant(2, "other", "cold2", 2),)
    )
    window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
    window.add(state)
    intake = DirectRecipeIntake(
        context=CONTEXT,
        receiver="validator",
        journal=ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
        verifier=_Verifier(),
        window=window,
        discovery=discovery,
        provider_for=lambda owner: provider if owner == "miner" else None,
        attempt_ledger=AttemptLedger(attempts / "ledger.sqlite3"),
        clock_ns=lambda: NOW,
    )
    try:
        yield intake, request, provider, state
    finally:
        provider.close()


def _source(key, name, body, *, offset=0, chunk=None):
    return research.DirectStageSourceRequestV1(
        key,
        name,
        offset,
        len(body),
        submission.name(body),
        None,
        body if chunk is None else chunk,
    )


def _fields(call):
    return {
        "call_base64": base64.b64encode(research.canonical_bytes(call)).decode("ascii")
    }


def _send(receiver, call=None, *, fields=None, challenge=None, hotkey="miner", index=1):
    intake, request, _provider, state = receiver
    body = message(
        CONTEXT,
        state.snapshot_id,
        request.challenge_key if challenge is None else challenge,
        session="receiver-source-staging",
        request="source-stage-" + str(index).zfill(8),
        tool=research.RESEARCH_NAMESPACE,
        fields=_fields(call) if fields is None else fields,
    )
    headers = _headers(body, NOW + index, hotkey=hotkey)
    return intake.handle("POST", SUBMIT_PATH, headers, body, "127.0.0.1"), body, headers


def _reply(answer):
    assert answer.status == 200
    assert answer.body["schema"] == SOURCE_REPLY_SCHEMA
    return research.load_canonical(
        base64.b64decode(answer.body["protocol_reply_base64"], validate=True),
        research.ServiceReply,
    )


def test_signed_staging_and_construction_lookup_share_exact_owner_ledger(receiver):
    intake, request, provider, _state = receiver
    public = intake.handle("GET", INFO_PATH, {}, b"", "127.0.0.1")
    assert public.body["tools"] == [
        SUBMIT_TOOL,
        "construction_status",
        research.RESEARCH_NAMESPACE,
    ]
    assert public.body["source_staging"] == {
        "tool": research.RESEARCH_NAMESPACE,
        "operation": "stage_research_source",
        "request_schema": "direct_stage_source_request_v1",
        "reply_schema": SOURCE_REPLY_SCHEMA,
        "path": SUBMIT_PATH,
        "owner": "authenticated_hotkey",
    }
    document = b'{"untrusted":"inert source bytes"}'
    fingerprint = submission.name(document)
    name = staging.WORKSPACE_PREFIX + fingerprint[7:] + ".json"
    raw = json.dumps(
        {"documents": {"forward": fingerprint}}, separators=(",", ":")
    ).encode()
    call = lambda source: research.ServiceCall(
        research.RESEARCH_NAMESPACE, "stage_research_source", source
    )
    first, body, headers = _send(
        receiver,
        call(_source(request.challenge_key, name, document, chunk=document[:8])),
    )
    assert _reply(first).result.complete is False
    workspace = ResearchWorkspace(provider.ledger, provider.owner)
    with pytest.raises(WorkspaceFileMissing):
        workspace.get(name)
    replay = intake.handle("POST", SUBMIT_PATH, headers, body, "127.0.0.1")
    assert replay.status == 401 and replay.body["refused"] == "AUTH_REPLAY"
    # A fresh signed transmission may idempotently resume the same source bytes.
    answer, _, _ = _send(
        receiver,
        call(
            _source(request.challenge_key, name, document, offset=8, chunk=document[8:])
        ),
        index=2,
    )
    assert _reply(answer).result.complete is True
    answer, _, _ = _send(
        receiver,
        call(_source(request.challenge_key, staging.WORKSPACE_MANIFEST, raw)),
        index=3,
    )
    assert _reply(answer).result.complete is True
    assert not provider.queued_tasks()
    recipe_value = json.loads(json.dumps(request.recipe))
    recipe_value["source"] = {
        "kind": "graph",
        "submission_digest": submission.name(raw),
    }
    recipe_value["procedure"]["entrypoint"] = None
    recipe = intake.adapter.validate_strategy(recipe_value)
    # This is the same lookup invoked by adapter.evaluate, with the exact
    # receiver provider. No miner-local store or secondary source cache exists.
    assert intake.adapter._provider("miner") is provider
    envelope = graph_envelope_from_workspace(provider.ledger, provider.owner, recipe)
    assert staging.from_envelope(json.loads(envelope)) == (
        submission.name(raw),
        raw,
        {fingerprint: document},
    )
    with pytest.raises(RecipeRefused, match="graph_workspace_missing"):
        graph_envelope_from_workspace(provider.ledger, "other", recipe)
    wrong = json.loads(json.dumps(recipe_value))
    wrong["source"]["submission_digest"] = "sha256:" + "f" * 64
    with pytest.raises(RecipeRefused, match="graph_digest_mismatch"):
        graph_envelope_from_workspace(
            provider.ledger, provider.owner, intake.adapter.validate_strategy(wrong)
        )
    body = message(
        CONTEXT,
        _state.snapshot_id,
        request.challenge_key,
        session="receiver-source-staging",
        request="source-construct-0001",
        tool=SUBMIT_TOOL,
        fields={
            "strategy_json": json.dumps(recipe_value),
            "contract_digest": intake.adapter.contract_digest,
        },
    )
    admitted = intake.handle(
        "POST", SUBMIT_PATH, _headers(body, NOW + 4), body, "127.0.0.1"
    )
    assert admitted.status == 202
    assert admitted.body["outcome"]["state"] == "ADMITTED"
    queued = provider.queued_tasks()
    assert len(queued) == 1
    assert provider._source_envelope(queued[0].value, recipe) == envelope
    assert admitted.body["outcome"]["qualification"] is False


def test_staging_cannot_select_another_owner_or_challenge(receiver):
    _intake, request, provider, _state = receiver
    raw = b'{"documents":{}}'
    source = _source(request.challenge_key, staging.WORKSPACE_MANIFEST, raw)
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE, "stage_research_source", source
    )
    other, _, _ = _send(receiver, call, hotkey="other")
    assert other.status == 503
    assert other.body["refused"] == "direct_provider_binding_unavailable"
    spoofed, _, _ = _send(receiver, fields={**_fields(call), "owner": "other"}, index=2)
    assert spoofed.status == 400
    assert spoofed.body["refused"] == "source_staging_fields"
    wrong_key = replace(request.challenge_key, version="1.2")
    nested = replace(call, request=replace(source, challenge_key=wrong_key))
    bad, _, _ = _send(receiver, nested, index=3)
    assert bad.status == 400 and bad.body["refused"] == "source_staging_context"
    outer, _, _ = _send(receiver, call, challenge=wrong_key, index=4)
    assert outer.status == 400 and outer.body["refused"] == "TRANSPORT_CONTEXT"
    assert (
        ResearchWorkspace(provider.ledger, provider.owner).current_digest(
            staging.WORKSPACE_MANIFEST
        )
        is None
    )
    assert not provider.queued_tasks()


def test_staging_refuses_other_research_operations_and_bad_source_digest(receiver):
    _intake, request, provider, _state = receiver
    query = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(request.challenge_key),
    )
    refused, _, _ = _send(receiver, query)
    assert refused.status == 400 and refused.body["refused"] == "source_staging_context"
    raw = b'{"documents":{}}'
    source = _source(request.challenge_key, staging.WORKSPACE_MANIFEST, raw)
    source = replace(source, content_digest="sha256:" + "f" * 64)
    bad = research.ServiceCall(
        research.RESEARCH_NAMESPACE, "stage_research_source", source
    )
    answer, _, _ = _send(receiver, bad, index=2)
    reply = _reply(answer)
    assert reply.status is research.ReplyStatus.ERROR
    assert reply.result.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH
    assert not provider.queued_tasks()


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"call_base64": "not-base64"},
        {"call_base64": "AA=="},
        {"call_base64": 1},
        {"call_base64": "", "owner": "miner"},
    ],
)
def test_malformed_staging_never_reaches_workspace(receiver, fields):
    _intake, _request, provider, _state = receiver
    answer, _, _ = _send(receiver, fields=fields)
    assert answer.status == 400 and answer.body["refused"] == "source_staging_fields"
    assert not ResearchWorkspace(provider.ledger, provider.owner).inventory()
    assert not provider.queued_tasks()


def test_staging_transport_and_chunk_bounds_remain_enforced(receiver):
    intake, request, provider, _state = receiver
    oversized = intake.handle(
        "POST", SUBMIT_PATH, {}, b"x" * (MAX_BODY + 1), "127.0.0.1"
    )
    assert oversized.status == 400
    assert oversized.body["refused"] == "TRANSPORT_MALFORMED"
    with pytest.raises(ValueError, match="registered flat workspace name"):
        _source(request.challenge_key, "../source.tar.gz", b"{}")
    with pytest.raises(ValueError, match="bounded digest-bound"):
        _source(request.challenge_key, staging.WORKSPACE_MANIFEST, b"x" * 8193)
    assert not ResearchWorkspace(provider.ledger, provider.owner).inventory()


def test_signed_material_staging_promotes_only_full_owner_closure(receiver, tmp_path):
    from test_library_bundles import fixture

    intake, request, provider, _state = receiver
    cache = tmp_path / "owner-material-cache"
    cache.mkdir(mode=0o700)
    cache.chmod(0o700)
    provider.image_resolver = SimpleNamespace(
        cache_root=cache, material_cache_bytes=10 * 1024**2
    )
    manifest, archive, wheels, lock, license_text = fixture()
    selected = bundle_ref(manifest, archive, wheels, lock, license_text)
    public = intake.handle("GET", INFO_PATH, {}, b"", "127.0.0.1")
    assert public.body["material_staging"] == {
        "tool": research.RESEARCH_NAMESPACE,
        "operation": "stage_research_material",
        "request_schema": "direct_stage_material_request_v1",
        "reply_schema": SOURCE_REPLY_SCHEMA,
        "path": SUBMIT_PATH,
        "owner": "authenticated_hotkey",
    }
    files = [
        ("source.tar.gz", archive),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
        *wheels.items(),
        (
            "bundle.json",
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
        ),
    ]
    for index, (name, body) in enumerate(files, start=1):
        call = research.ServiceCall(
            research.RESEARCH_NAMESPACE,
            "stage_research_material",
            research.DirectStageMaterialRequestV1(
                request.challenge_key,
                selected.bundle_digest,
                name,
                0,
                len(body),
                "sha256:" + hashlib.sha256(body).hexdigest(),
                body,
            ),
        )
        answer, wire, headers = _send(receiver, call, index=index + 100)
        assert answer.status == 200
        reply = _reply(answer)
        assert reply.status is research.ReplyStatus.OK
        assert reply.result.complete
        assert reply.result.bundle_complete == (name == "bundle.json")
        replay = intake.handle("POST", SUBMIT_PATH, headers, wire, "127.0.0.1")
        assert replay.status == 401 and replay.body["refused"] == "AUTH_REPLAY"
    assert inspect_staged_bundle_material(cache, selected).is_dir()
    assert not provider.queued_tasks()
