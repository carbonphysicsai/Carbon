"""An admitted overlay is retained from its original source and prep bytes."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from types import SimpleNamespace

import pytest
from test_lean_recipe_retention import _recipe, _source_image

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.lean_recipe_retention import (
    RetentionUnavailable,
    retain_served_result,
)
from carbon.development_session import library_bundles, library_environment_cache
from carbon.research import DirectTaskStateV3


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def test_retention_rechecks_admitted_overlay_without_resolving_a_child(
    tmp_path, monkeypatch
):
    material = bundle_material_v5()
    image, _ = _source_image(tmp_path)
    recipe = _recipe(material, image)
    cache_root = tmp_path / "operator-cache"
    cache_root.mkdir(mode=0o700)
    pinned = tmp_path / "pinned"
    pinned.mkdir()
    (pinned / "wheels").mkdir()
    context = image.provisioned.context
    manifest_raw = (context / "bundle.json").read_bytes()
    manifest = json.loads(manifest_raw)
    source, _, lock, license_text = library_bundles.load_cached_bundle_material(
        context, manifest
    )
    for name, raw in (
        ("bundle.json", manifest_raw),
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
    ):
        (pinned / name).write_bytes(raw)
    selected = library_environment_cache.stage_pinned_bundle_material(
        pinned, cache_root
    )
    assert selected == image.provisioned.bundle

    ledger_root = tmp_path / "ledger"
    prep = ledger_root / ("operation-" + "1" * 64) / "snapshot"
    prep.mkdir(parents=True)
    content = b"VALUE = 1\n"
    relative = "source/probe.py"
    with tarfile.open(
        prep / "overlay.tar", mode="w", format=tarfile.USTAR_FORMAT
    ) as archive:
        member = tarfile.TarInfo(relative)
        member.size = len(content)
        member.mode = 0o444
        archive.addfile(member, io.BytesIO(content))
    archive_raw = (prep / "overlay.tar").read_bytes()
    row = [relative, len(content), _sha(content)]
    receipt = {
        "schema": library_environment_cache.OVERLAY_SCHEMA,
        "bundle_ref": selected.to_dict(),
        "parent_image_id": image.parent.image_id,
        "archive_sha256": _sha(archive_raw),
        "archive_bytes": len(archive_raw),
        "tree_digest": _sha(json.dumps([row], separators=(",", ":")).encode()),
        "file_count": 1,
        "total_file_bytes": len(content),
    }
    (prep / "overlay.json").write_text(json.dumps(receipt))
    overlay = library_environment_cache.cache_verified_overlay(
        prep,
        cache_root,
        expected_bundle=selected,
        expected_parent=image.parent,
        expected_receipt=receipt,
        material_cache_bytes=10 * 1024**2,
    )
    binding = json.dumps(
        [
            "BUNDLE_OVERLAY",
            {
                "parent_image_id": image.parent.image_id,
                "bundle_ref": selected.to_dict(),
                "tree_digest": overlay.tree_digest,
                "archive_digest": overlay.archive_digest,
            },
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence = {
        "schema": "carbon.direct-private-attempt.overlay.v1",
        "image_id": image.parent.image_id,
        "parent_image_id": image.parent.image_id,
        "inference_image_id": image.parent.image_id,
        "overlay_tree_digest": overlay.tree_digest,
        "overlay_archive_digest": overlay.archive_digest,
        "prep_operation": prep.parent.name,
        "prep_receipt": receipt,
        "build_operation": "operation-" + "2" * 64,
        "inference_operation": "operation-" + "3" * 64,
    }
    task_id = "rtsk_" + "a" * 64
    provider = SimpleNamespace(
        image_resolver=SimpleNamespace(cache_root=cache_root),
        construction_parent=image.parent,
        inference_image=image.parent,
        ledger=SimpleNamespace(root=ledger_root),
        _task_image_bindings={task_id: binding},
        _requests={task_id: SimpleNamespace(recipe=recipe.to_dict())},
        get_research_result=lambda _: SimpleNamespace(
            task=SimpleNamespace(
                state=DirectTaskStateV3.SUCCEEDED,
                terminal_receipt=SimpleNamespace(state_digest=_sha(b"state")),
            )
        ),
        private_attempt=lambda _: evidence,
        _resolved_image=lambda _: pytest.fail("overlay must not resolve a child"),
    )
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.discovery = SimpleNamespace(
        _material=material,
        info=SimpleNamespace(challenge_key=material["challenge_key"]),
    )
    monkeypatch.setattr(LeanRecipeAdapter, "owner", lambda *_: "miner")
    monkeypatch.setattr(LeanRecipeAdapter, "_provider", lambda *_: provider)
    monkeypatch.setattr(
        library_bundles, "verify_bundle_parent_environment", lambda *_: None
    )
    from carbon.challenge_validator import lean_recipe_retention as retention

    original_snapshot = retention._snapshot

    class SourceVerified(Exception):
        pass

    def stop_after_source(path, *, limit, digest, label):
        if label == "state_snapshot":
            raise SourceVerified
        return original_snapshot(path, limit=limit, digest=digest, label=label)

    monkeypatch.setattr(retention, "_snapshot", stop_after_source)
    with pytest.raises(SourceVerified):
        retain_served_result(
            adapter,
            task_id,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )
    (overlay.path / relative).chmod(0o600)
    (overlay.path / relative).write_bytes(b"CHANGED\n")
    with pytest.raises(RetentionUnavailable, match="source_overlay_unavailable"):
        retain_served_result(
            adapter,
            task_id,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )
