"""Authenticated material bytes stay private until their full closure validates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_direct_source_staging import _ledger
from test_library_bundles import fixture

from carbon import research
from carbon.development_session.direct_material_staging import stage_material
from carbon.development_session.library_bundles import (
    bundle_ref,
    load_pinned_bundle_directory,
)
from carbon.development_session.library_environment_cache import (
    inspect_staged_bundle_material,
)


def _sha(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _provider(tmp_path, owner="alice"):
    cache = tmp_path / "private-cache"
    cache.mkdir(mode=0o700, exist_ok=True)
    cache.chmod(0o700)
    return SimpleNamespace(
        owner=owner,
        ledger=_ledger(tmp_path),
        image_resolver=SimpleNamespace(
            cache_root=cache, material_cache_bytes=10 * 1024**2
        ),
    )


def _request(bundle, name, body, offset=0, chunk=None):
    if chunk is None:
        chunk = body[offset:]
    return research.DirectStageMaterialRequestV1(
        research.ChallengeKey("synthetic-linear-field-2d", "1.3"),
        bundle,
        name,
        offset,
        len(body),
        _sha(body),
        chunk,
    )


def _files():
    manifest, source, wheels, lock, license_text = fixture()
    ref = bundle_ref(manifest, source, wheels, lock, license_text)
    files = [
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
        *wheels.items(),
        (
            "bundle.json",
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
        ),
    ]
    return ref, files


def test_signed_material_chunks_promote_only_validated_complete_closure(tmp_path):
    provider = _provider(tmp_path)
    ref, files = _files()
    with pytest.raises(FileNotFoundError, match="not staged"):
        inspect_staged_bundle_material(provider.image_resolver.cache_root, ref)
    first_name, first_body = files[0]
    first = _request(ref.bundle_digest, first_name, first_body, 0, first_body[:16])
    partial = stage_material(provider, first)
    assert partial.received_bytes == 16 and not partial.complete
    assert stage_material(provider, first) == partial
    with pytest.raises(FileNotFoundError):
        inspect_staged_bundle_material(provider.image_resolver.cache_root, ref)
    last = _request(ref.bundle_digest, first_name, first_body, 16, first_body[16:])
    assert stage_material(provider, last).complete
    for name, body in files[1:]:
        result = stage_material(provider, _request(ref.bundle_digest, name, body))
        assert result.complete
        assert result.bundle_complete == (name == "bundle.json")
    staged = inspect_staged_bundle_material(provider.image_resolver.cache_root, ref)
    assert bundle_ref(*load_pinned_bundle_directory(staged)) == ref
    assert stage_material(provider, first).bundle_complete
    assert stage_material(
        provider, _request(ref.bundle_digest, *files[-1])
    ).bundle_complete
    assert not list(provider.image_resolver.cache_root.rglob("*.image.json"))
    assert not (
        provider.image_resolver.cache_root
        / "material-uploads"
        / hashlib.sha256(b"alice").hexdigest()
        / ref.bundle_digest[7:]
    ).exists()


def test_material_offset_digest_and_owner_boundary_fail_closed(tmp_path):
    provider = _provider(tmp_path)
    ref, files = _files()
    name, body = files[0]
    first = _request(ref.bundle_digest, name, body, 0, body[:8])
    stage_material(provider, first)
    with pytest.raises(research.ResearchTaskProviderError) as offset:
        stage_material(provider, _request(ref.bundle_digest, name, body, 9, body[9:]))
    assert offset.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    with pytest.raises(research.ResearchTaskProviderError) as different:
        stage_material(provider, replace(first, chunk=b"different"))
    assert (
        different.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    )
    with pytest.raises(research.ResearchTaskProviderError) as missing:
        stage_material(provider, _request(ref.bundle_digest, *files[-1]))
    assert missing.value.code is research.ResearchServiceErrorCode.REFERENCE_NOT_FOUND
    bob = SimpleNamespace(
        owner="bob", ledger=provider.ledger, image_resolver=provider.image_resolver
    )
    with pytest.raises(research.ResearchTaskProviderError) as isolated:
        stage_material(bob, _request(ref.bundle_digest, *files[-1]))
    assert isolated.value.code is research.ResearchServiceErrorCode.REFERENCE_NOT_FOUND
    with pytest.raises(ValueError, match="bounded pinned material"):
        _request(ref.bundle_digest, "../source.tar.gz", body)
    with pytest.raises(ValueError, match="bounded pinned material"):
        _request(ref.bundle_digest, name, b"x" * 24577)
    empty_license = stage_material(
        provider, _request(ref.bundle_digest, "LICENSE", b"")
    )
    assert empty_license.complete and empty_license.received_bytes == 0


def test_direct_research_service_routes_material_without_task_or_image(tmp_path):
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.development_session.research_service import DirectFixtureDiscovery

    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    provider = _provider(tmp_path)

    class Discovery:
        def get_challenge_info(self, key):
            return discovery.get_challenge_info(key)

        def get_interaction_manifest(self, key):
            return discovery.get_interaction_manifest(key)

    pair = Discovery()

    class Tasks:
        def __init__(self, wrapped):
            self.owner = wrapped.owner
            self.ledger = wrapped.ledger
            self.image_resolver = wrapped.image_resolver

        def start_research_task(self, request):
            raise AssertionError("material staging must not run a task")

        def get_research_result(self, request):
            raise AssertionError("material staging must not observe a task")

        def cancel_research_task(self, request):
            raise AssertionError("material staging must not cancel a task")

    service = research.LocalResearchService(
        research.DirectPublicResearchContext(pair, pair, Tasks(provider))
    )
    ref, files = _files()
    name, body = files[0]
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "stage_research_material",
        _request(ref.bundle_digest, name, body),
    )
    reply = research.load_canonical(
        service.call_bytes(research.canonical_bytes(call)), research.ServiceReply
    )
    assert reply.status is research.ReplyStatus.OK
    assert reply.result.complete and not reply.result.bundle_complete
    assert not list(provider.image_resolver.cache_root.rglob("*.image.json"))


def test_uncommitted_partial_file_can_restart_from_zero(tmp_path):
    from carbon.development_session.direct_material_staging import _item

    provider = _provider(tmp_path)
    ref, files = _files()
    name, body = files[0]
    first = _request(ref.bundle_digest, name, body, 0, body[:8])
    assert not stage_material(provider, first).complete
    with provider.ledger.db() as db:
        db.execute(
            "DELETE FROM direct_material_uploads WHERE owner=? AND bundle=? AND name=?",
            (provider.owner, ref.bundle_digest, name),
        )
    root = (
        provider.image_resolver.cache_root
        / "material-uploads"
        / hashlib.sha256(provider.owner.encode()).hexdigest()
        / ref.bundle_digest[7:]
    )
    assert _item(root, name, _sha(body)).is_file()
    assert stage_material(provider, first).received_bytes == 8


def test_promotion_refuses_insufficient_copy_space_as_infrastructure(
    tmp_path, monkeypatch
):
    from carbon.development_session import direct_material_staging

    provider = _provider(tmp_path)
    ref, files = _files()
    for name, body in files[:-1]:
        assert stage_material(
            provider, _request(ref.bundle_digest, name, body)
        ).complete
    actual_usage = direct_material_staging.shutil.disk_usage
    monkeypatch.setattr(
        direct_material_staging.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=0),
    )
    with pytest.raises(research.ResearchTaskProviderError) as refused:
        stage_material(provider, _request(ref.bundle_digest, *files[-1]))
    assert (
        refused.value.code is research.ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
    )
    monkeypatch.setattr(direct_material_staging.shutil, "disk_usage", actual_usage)
    assert stage_material(
        provider, _request(ref.bundle_digest, *files[-1])
    ).bundle_complete


def test_material_staging_requires_trusted_cumulative_capacity(tmp_path):
    from carbon.development_session.direct_material_staging import _cache_bytes

    provider = _provider(tmp_path)
    ref, files = _files()
    provider.image_resolver.material_cache_bytes = None
    with pytest.raises(research.ResearchTaskProviderError) as missing:
        stage_material(provider, _request(ref.bundle_digest, *files[0]))
    assert (
        missing.value.code is research.ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
    )

    provider.image_resolver.material_cache_bytes = 10 * 1024**2
    for name, body in files:
        stage_material(provider, _request(ref.bundle_digest, name, body))
    completed_bytes = _cache_bytes(provider.image_resolver.cache_root)
    manifest, source, wheels, lock, license_text = fixture()
    manifest["name"] = "second-bundle"
    second = bundle_ref(manifest, source, wheels, lock, license_text)
    second_files = [
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
        *wheels.items(),
        (
            "bundle.json",
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
        ),
    ]
    provider.image_resolver.material_cache_bytes = (
        completed_bytes + sum(len(body) for _, body in second_files) - 1
    )
    with pytest.raises(research.ResearchTaskProviderError) as full:
        for name, body in second_files:
            stage_material(provider, _request(second.bundle_digest, name, body))
    assert full.value.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED
    assert _cache_bytes(provider.image_resolver.cache_root) <= (
        provider.image_resolver.material_cache_bytes
    )


def test_finalized_replay_rejects_same_size_tail_corruption(tmp_path):
    provider = _provider(tmp_path)
    ref, files = _files()
    for name, body in files:
        stage_material(provider, _request(ref.bundle_digest, name, body))
    staged = inspect_staged_bundle_material(provider.image_resolver.cache_root, ref)
    archive = staged / "source.tar.gz"
    body = archive.read_bytes()
    archive.write_bytes(body[:-1] + bytes([body[-1] ^ 1]))
    with pytest.raises(research.ResearchTaskProviderError) as corrupted:
        stage_material(provider, _request(ref.bundle_digest, *files[0]))
    assert (
        corrupted.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    )
    with pytest.raises(research.ResearchTaskProviderError) as final:
        stage_material(provider, _request(ref.bundle_digest, *files[-1]))
    assert final.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT


def test_promotion_reserves_full_independent_copy_peak(tmp_path):
    from carbon.development_session.direct_material_staging import _cache_bytes

    provider = _provider(tmp_path)
    ref, files = _files()
    manifest = fixture()[0]
    uploaded = sum(len(body) for _, body in files)
    copied = (
        uploaded
        - len(files[-1][1])
        + len(json.dumps(manifest, sort_keys=True).encode())
    )
    provider.image_resolver.material_cache_bytes = uploaded + copied - 1
    for name, body in files[:-1]:
        stage_material(provider, _request(ref.bundle_digest, name, body))
    with pytest.raises(research.ResearchTaskProviderError) as full:
        stage_material(provider, _request(ref.bundle_digest, *files[-1]))
    assert full.value.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED
    assert _cache_bytes(provider.image_resolver.cache_root) <= (
        provider.image_resolver.material_cache_bytes
    )
    with pytest.raises(FileNotFoundError):
        inspect_staged_bundle_material(provider.image_resolver.cache_root, ref)
