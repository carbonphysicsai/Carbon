"""Gate item R8: the hostile-model lowering probe at Level 4, bound to the current analysis image digest.

A readiness item for the development and testnet gate, not a security acceptance. The result is a
digest-bound record; a new image digest re-arms it; no record is NOT_BUILT; nothing malformed,
stale or incomplete ever passes; below Level 4 the item does not apply.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_pipeline.readiness import checks, model
from carbon.development_session import research_image

CH = "battery-fastcharge-ageing-development-v1"
IMAGE = "sha256:" + "1" * 64
RUNTIME = "sha256:" + "2" * 64


def manifest(tmp_path, monkeypatch, *, image=IMAGE, runtime=RUNTIME):
    path = tmp_path / "analysis-image.json"
    path.write_text(
        json.dumps(
            {
                "schema": research_image.SCHEMA,
                "image_id": image,
                "parent_image": "sha256:" + "3" * 64,
                "runtime_digest": runtime,
            }
        )
    )
    monkeypatch.setenv(checks.ANALYSIS_IMAGE_ENV, str(path))
    return path


def results(**changes):
    body = {
        name: {"status": "PASS", "result_digest": "sha256:" + "a" * 64}
        for name in checks.HOSTILE_PROBES
    }
    body.update(changes)
    return body


def record(tmp_path, **changes):
    document = {
        "schema": checks.HOSTILE_PROBE_SCHEMA,
        "challenge": CH,
        "image_id": IMAGE,
        "runtime_digest": RUNTIME,
        "results": results(),
        **changes,
    }
    folder = tmp_path / "carbon/challenge_pipeline/readiness" / CH
    folder.mkdir(parents=True, exist_ok=True)
    (folder / checks.HOSTILE_PROBE_FILE).write_text(json.dumps(document))
    return folder / checks.HOSTILE_PROBE_FILE


def run(tmp_path, level=4):
    ctx = checks.Context(challenge=CH, level=level, repository=tmp_path)
    return checks.hostile_probe({}, ctx)


def test_the_item_is_registered_as_a_level_four_auto_check_that_is_not_an_acceptance():
    item = next(i for i in model.load_items() if i["id"] == "R8")
    assert item["kind"] == "auto" and item["check"] == "hostile_probe"
    assert "not a security acceptance" in item["title"]
    assert checks.CHECKS["hostile_probe"] is checks.hostile_probe
    assert model.ITEM_ID.match("R8")


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_it_does_not_apply_below_level_four(tmp_path, level):
    result = run(tmp_path, level)
    assert result.status == model.PASS and "not applicable" in result.detail


def test_no_record_is_not_built(tmp_path, monkeypatch):
    manifest(tmp_path, monkeypatch)
    result = run(tmp_path)
    assert result.status == model.NOT_BUILT and "executor" in result.detail


def test_a_matching_complete_record_passes_and_binds_the_file_digest(
    tmp_path, monkeypatch
):
    manifest(tmp_path, monkeypatch)
    path = record(tmp_path)
    result = run(tmp_path)
    assert result.status == model.PASS
    assert model.file_digest(path) in result.evidence
    assert "not a security acceptance" in result.detail


def test_a_new_image_digest_rearms_the_item(tmp_path, monkeypatch):
    record(tmp_path)
    manifest(tmp_path, monkeypatch)
    assert run(tmp_path).status == model.PASS
    manifest(tmp_path, monkeypatch, image="sha256:" + "9" * 64)
    result = run(tmp_path)
    assert (
        result.status == model.FAIL and "another analysis image digest" in result.detail
    )
    manifest(tmp_path, monkeypatch, runtime="sha256:" + "8" * 64)
    assert run(tmp_path).status == model.FAIL


def test_a_record_with_no_manifest_to_bind_to_never_passes(tmp_path, monkeypatch):
    record(tmp_path)
    monkeypatch.delenv(checks.ANALYSIS_IMAGE_ENV, raising=False)
    result = run(tmp_path)
    assert result.status == model.FAIL and "cannot be bound" in result.detail


@pytest.mark.parametrize(
    "damage",
    [
        {"schema": "carbon.readiness.other.v1"},
        {"challenge": "another-challenge"},
        {"results": {}},
        {
            "results": {
                "memory": {"status": "PASS", "result_digest": "sha256:" + "a" * 64}
            }
        },
        {
            "results": results(
                time={"status": "FAIL", "result_digest": "sha256:" + "a" * 64}
            )
        },
        {"results": results(memory={"status": "PASS"})},
        {"results": results(scratch_flood={"status": "PASS", "result_digest": "abc"})},
        {
            "results": results(
                extra={"status": "PASS", "result_digest": "sha256:" + "a" * 64}
            )
        },
        {"results": []},
    ],
)
def test_a_malformed_or_incomplete_record_never_passes(tmp_path, monkeypatch, damage):
    manifest(tmp_path, monkeypatch)
    record(tmp_path, **damage)
    assert run(tmp_path).status == model.FAIL


def test_an_unreadable_record_fails(tmp_path, monkeypatch):
    manifest(tmp_path, monkeypatch)
    path = record(tmp_path)
    path.write_text("{not json")
    assert run(tmp_path).status == model.FAIL
    path.write_text("[]")
    assert run(tmp_path).status == model.FAIL
