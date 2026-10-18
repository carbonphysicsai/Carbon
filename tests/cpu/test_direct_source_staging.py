"""Bounded source upload without a worker, signer, or official evaluation."""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

from carbon import research
from carbon.development_session.direct_source_staging import stage_source
from carbon.development_session.research_ledger import VERSION, CampaignLedger
from carbon.development_session.research_workspace import (
    ResearchWorkspace,
    WorkspaceBoundExceeded,
    WorkspaceFileMissing,
)
from carbon.level4 import staging, submission


def _ledger(tmp_path):
    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "direct-source-staging-test",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "alice",
        }
    )
    return ledger


def _request(name, body, offset, chunk, *, expected=None):
    return research.DirectStageSourceRequestV1(
        research.ChallengeKey("synthetic-linear-field-2d", "1.2"),
        name,
        offset,
        len(body),
        submission.name(body),
        expected,
        chunk,
    )


def test_chunks_publish_only_verified_complete_owner_file(tmp_path):
    ledger = _ledger(tmp_path)
    body = b'{"documents":{}}'
    workspace = ResearchWorkspace(ledger, "alice")
    first = _request(staging.WORKSPACE_MANIFEST, body, 0, body[:8])
    result = stage_source(ledger, "alice", first)
    assert result.received_bytes == 8 and not result.complete
    with pytest.raises(WorkspaceFileMissing):
        workspace.get(staging.WORKSPACE_MANIFEST)
    assert stage_source(ledger, "alice", first) == result
    last = _request(staging.WORKSPACE_MANIFEST, body, 8, body[8:])
    assert stage_source(ledger, "alice", last).complete
    assert stage_source(ledger, "alice", first).complete
    assert workspace.get(staging.WORKSPACE_MANIFEST) == body
    with pytest.raises(WorkspaceFileMissing):
        ResearchWorkspace(ledger, "bob").get(staging.WORKSPACE_MANIFEST)


def test_wrong_bytes_offset_digest_and_compare_swap_fail_closed(tmp_path):
    ledger = _ledger(tmp_path)
    body = b'{"documents":{}}'
    name = staging.WORKSPACE_MANIFEST
    first = _request(name, body, 0, body[:8])
    stage_source(ledger, "alice", first)
    with pytest.raises(research.ResearchTaskProviderError) as changed_total:
        stage_source(ledger, "alice", replace(first, total_bytes=8))
    assert (
        changed_total.value.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH
    )
    assert ResearchWorkspace(ledger, "alice").current_digest(name) is None
    with pytest.raises(research.ResearchTaskProviderError) as wrong_chunk:
        stage_source(ledger, "alice", _request(name, body, 0, b"different"))
    assert (
        wrong_chunk.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    )
    with pytest.raises(research.ResearchTaskProviderError):
        stage_source(ledger, "alice", _request(name, body, 9, body[9:]))
    with pytest.raises(research.ResearchTaskProviderError) as wrong_digest:
        stage_source(ledger, "alice", _request(name, body, 8, b"x" * len(body[8:])))
    assert (
        wrong_digest.value.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH
    )
    assert ResearchWorkspace(ledger, "alice").current_digest(name) is None
    stage_source(ledger, "alice", _request(name, body, 8, body[8:]))
    replacement = b'{"documents":{"forward":"sha256:' + b"0" * 64 + b'"}}'
    with pytest.raises(research.ResearchTaskProviderError) as cas:
        stage_source(ledger, "alice", _request(name, replacement, 0, replacement))
    assert cas.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT


def test_document_name_must_match_bytes_and_call_bounds(tmp_path):
    ledger = _ledger(tmp_path)
    body = b"{}"
    name = staging.WORKSPACE_PREFIX + submission.name(body)[7:] + ".json"
    assert stage_source(ledger, "alice", _request(name, body, 0, body)).complete
    with pytest.raises(research.ResearchTaskProviderError) as wrong_name:
        stage_source(
            ledger,
            "bob",
            _request(staging.WORKSPACE_PREFIX + "0" * 64 + ".json", body, 0, body),
        )
    assert wrong_name.value.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH
    with pytest.raises(ValueError, match="registered flat workspace name"):
        _request("../level4-manifest.json", body, 0, body)
    with pytest.raises(ValueError, match="bounded digest-bound"):
        _request(name, b"x" * 8193, 0, b"x" * 8193)


def test_source_reads_refuse_oversized_existing_object_and_legacy_blob(tmp_path):
    ledger = _ledger(tmp_path)
    workspace = ResearchWorkspace(ledger, "alice")
    name = staging.WORKSPACE_MANIFEST
    oversized = b"x" * 20_000
    fingerprint = workspace.put(name, oversized)
    with pytest.raises(WorkspaceBoundExceeded):
        workspace.get_bounded(name, 16)
    request = _request(name, b'{"documents":{}}', 0, b'{"documents":{}}')
    with pytest.raises(research.ResearchTaskProviderError) as target:
        stage_source(
            ledger,
            "alice",
            replace(request, content_digest=fingerprint),
        )
    assert target.value.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED
    with ledger.db() as db:
        db.execute(
            "INSERT INTO workspace VALUES(?,?,?,?)",
            ("alice", "legacy", oversized, fingerprint),
        )
    with pytest.raises(WorkspaceBoundExceeded):
        workspace.get_bounded("legacy", 16)


def test_source_reads_refuse_oversized_partial_before_resuming(tmp_path):
    ledger = _ledger(tmp_path)
    workspace = ResearchWorkspace(ledger, "alice")
    body = b'{"documents":{}}'
    first = _request(staging.WORKSPACE_MANIFEST, body, 0, body[:8])
    stage_source(ledger, "alice", first)
    partial = next(
        item["name"]
        for item in workspace.inventory()
        if item["name"].startswith("upload-")
    )
    workspace.put(
        partial,
        b"x" * (len(body) + 1),
        expected_digest=workspace.current_digest(partial),
    )
    with pytest.raises(research.ResearchTaskProviderError) as resumed:
        stage_source(
            ledger, "alice", _request(staging.WORKSPACE_MANIFEST, body, 8, body[8:])
        )
    assert resumed.value.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED
    assert workspace.current_digest(staging.WORKSPACE_MANIFEST) is None


def test_preexisting_malformed_manifest_cannot_take_complete_fast_path(tmp_path):
    ledger = _ledger(tmp_path)
    workspace = ResearchWorkspace(ledger, "alice")
    workspace.put(staging.WORKSPACE_MANIFEST, b"{")
    with pytest.raises(research.ResearchTaskProviderError) as malformed:
        stage_source(
            ledger, "alice", _request(staging.WORKSPACE_MANIFEST, b"{", 0, b"{")
        )
    assert malformed.value.code is research.ResearchServiceErrorCode.REFERENCE_MISMATCH


def test_direct_service_round_trip_and_owner_binding(tmp_path):
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v4
    from carbon.development_session.research_service import DirectFixtureDiscovery

    discovery = DirectFixtureDiscovery(bundle_material_v4(), task_admission=True)

    class Discovery:
        def get_challenge_info(self, key):
            return discovery.get_challenge_info(key)

        def get_interaction_manifest(self, key):
            return replace(
                discovery.get_interaction_manifest(key),
                supported_operations=research.DIRECT_RECIPE_SOURCE_TASK_OPERATIONS,
            )

    class Tasks:
        def __init__(self, ledger, owner):
            self.ledger, self.owner = ledger, owner

        def start_research_task(self, request):
            raise AssertionError("staging must not start a task")

        def get_research_result(self, request):
            raise AssertionError("staging must not observe a task")

        def cancel_research_task(self, request):
            raise AssertionError("staging must not cancel a task")

    ledger = _ledger(tmp_path)
    pair = Discovery()
    alice = research.LocalResearchService(
        research.DirectPublicResearchContext(pair, pair, Tasks(ledger, "alice"))
    )
    bob = research.LocalResearchService(
        research.DirectPublicResearchContext(pair, pair, Tasks(ledger, "bob"))
    )
    body = b'{"documents":{}}'
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "stage_research_source",
        _request(staging.WORKSPACE_MANIFEST, body, 0, body),
    )
    wire = research.canonical_bytes(call)
    assert research.load_canonical(wire, research.ServiceCall) == call
    first = research.load_canonical(alice.call_bytes(wire), research.ServiceReply)
    assert first.status is research.ReplyStatus.OK
    assert first.result.complete
    assert ResearchWorkspace(ledger, "alice").get(staging.WORKSPACE_MANIFEST) == body
    assert (
        ResearchWorkspace(ledger, "bob").current_digest(staging.WORKSPACE_MANIFEST)
        is None
    )
    assert bob.call(call).status is research.ReplyStatus.OK
    assert ResearchWorkspace(ledger, "bob").get(staging.WORKSPACE_MANIFEST) == body


def test_graph_adapter_selector_is_closed_to_registered_new_kit():
    from carbon.challenge_kit import synthetic_linear_field_2d as kit
    from carbon.development_session.research_service import DirectFixtureDiscovery

    old = DirectFixtureDiscovery(kit.bundle_material_v4(), task_admission=True)
    assert old.graph_adapter_for(old.info.challenge_key) is None
    assert old.manifest.supported_operations == research.DIRECT_RECIPE_TASK_OPERATIONS
    unknown = research.ChallengeKey(old.info.challenge_key.challenge_id, "1.3")
    assert old.graph_adapter_for(unknown) is None
    if not hasattr(kit, "bundle_material_v5"):
        pytest.skip("prospective 1.3 material is tested on the combined tree")
    new = DirectFixtureDiscovery(kit.bundle_material_v5(), task_admission=True)
    assert (
        new.manifest.supported_operations
        == research.DIRECT_RECIPE_SOURCE_TASK_OPERATIONS
    )
    assert new.graph_adapter_for(new.info.challenge_key) == (
        "synthetic-linear-field-2d-public-jax-graph-v1"
    )
    assert new.graph_adapter_for(old.info.challenge_key) is None
    new._material["construction_limits_document"]["graph_training_adapter"][
        "id"
    ] = "unregistered"
    with pytest.raises(ValueError, match="fixed public TRAIN differs|material differs"):
        new.graph_adapter_for(new.info.challenge_key)


@pytest.mark.skipif(os.name == "nt", reason="durable task store uses Linux fcntl")
def test_historical_frozen_task_reopens_with_original_manifest_identity(
    tmp_path, monkeypatch
):
    from test_direct_v3_durable_tasks import _fixture

    request, provider, discovery = _fixture(tmp_path, monkeypatch)
    assert (
        discovery.manifest.supported_operations
        == research.DIRECT_RECIPE_TASK_OPERATIONS
    )
    assert request.manifest_digest == research.canonical_digest(discovery.manifest)
    tasks = provider()
    try:
        service = research.LocalResearchService(
            research.DirectPublicResearchContext(discovery, discovery, tasks)
        )
        source = b'{"documents":{}}'
        refused = service.call(
            research.ServiceCall(
                research.RESEARCH_NAMESPACE,
                "stage_research_source",
                replace(
                    _request(staging.WORKSPACE_MANIFEST, source, 0, source),
                    challenge_key=discovery.info.challenge_key,
                ),
            )
        )
        assert refused.status is research.ReplyStatus.ERROR
        assert (
            refused.result.code
            is research.ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
        )
        assert (
            ResearchWorkspace(tasks.ledger, tasks.owner).current_digest(
                staging.WORKSPACE_MANIFEST
            )
            is None
        )
        created = tasks.start_research_task(request)
        task_id = created.task.task_id
        assert created.created
    finally:
        tasks.close()
    reopened = provider()
    try:
        replay = reopened.start_research_task(request)
        assert not replay.created
        assert replay.task.task_id == task_id
        assert replay.task.immutable_bindings.manifest_digest == request.manifest_digest
    finally:
        reopened.close()
