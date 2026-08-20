"""CPU acceptance tests for A3's exact-version challenge registry."""

from __future__ import annotations

import fcntl
import hashlib
import importlib
import json
import multiprocessing
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    LiveActivationError,
    QualificationEvidence,
    QualificationManifest,
    RegistryError,
    serialize_record,
)

CHALLENGE_ID = "example_challenge"
VERSION = "1.0"
ARTIFACT_ID = "qualification_bundle"
ARTIFACT_PATH = f"{CHALLENGE_ID}/{VERSION}/qualification/bundle.json"
ARTIFACT_BYTES = b"synthetic A3 structure-only evidence\n"


def _digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _registry(tmp_path: Path) -> ChallengeRegistry:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    return ChallengeRegistry(tmp_path / "registry", artifact_root)


def _write_artifact(
    registry: ChallengeRegistry,
    *,
    path: str = ARTIFACT_PATH,
    content: bytes = ARTIFACT_BYTES,
) -> Path:
    target = registry.artifact_root.joinpath(*path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _complete_record(
    registry: ChallengeRegistry,
    *,
    challenge_id: str = CHALLENGE_ID,
    version: str = VERSION,
    status: str = "draft",
    mode: str = "production",
    artifact_path: str = ARTIFACT_PATH,
    artifact_digest: str | None = None,
    write_artifact: bool = True,
    allowed_backbones: tuple[str, ...] = ("fno", "future_operator"),
) -> ChallengeRecord:
    if write_artifact:
        target = _write_artifact(registry, path=artifact_path)
        expected_digest = _digest(target.read_bytes())
    else:
        expected_digest = _digest(ARTIFACT_BYTES)
    if artifact_digest is not None:
        expected_digest = artifact_digest
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=ARTIFACT_ID,
            reference="synthetic-structure-only-test-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    return ChallengeRecord(
        challenge_id=challenge_id,
        version=version,
        status=status,
        allowed_backbones=allowed_backbones,
        artifacts={
            ARTIFACT_ID: ArtifactBinding(
                path=artifact_path,
                digest=expected_digest,
            )
        },
        qualification=QualificationManifest(
            challenge_id=challenge_id,
            challenge_version=version,
            mode=mode,
            slots=slots,
        ),
    )


def _write_raw_record(
    registry: ChallengeRegistry,
    payload: object,
    *,
    challenge_id: str = CHALLENGE_ID,
    version: str = VERSION,
) -> Path:
    path = registry.registry_root / challenge_id / f"{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return path


def _stored_object(record: ChallengeRecord) -> dict[str, object]:
    value = json.loads(serialize_record(record))
    assert type(value) is dict
    return value


def _store_live_directly(
    registry: ChallengeRegistry, record: ChallengeRecord
) -> ChallengeRecord:
    live_record = replace(record, status="live")
    _write_raw_record(registry, serialize_record(live_record))
    return live_record


def _with_reserved_bindings(
    record: ChallengeRecord,
    *,
    receipt_schema_version: str | None = "reserved_schema-v1.0",
    required_backend_profile_id: str | None = "reserved_profile_a-v1.0",
    allowed_backend_profile_ids: tuple[str, ...] = (
        "reserved_profile_a-v1.0",
        "reserved_profile_b-v1.0",
    ),
) -> ChallengeRecord:
    """Bind reserved record metadata to the corresponding evidence slots."""
    manifest = record.qualification
    assert manifest is not None
    slots = dict(manifest.slots)
    train_backend = slots["train_backend"]
    mcp_readiness = slots["mcp_readiness"]
    assert isinstance(train_backend, QualificationEvidence)
    assert isinstance(mcp_readiness, QualificationEvidence)
    slots["train_backend"] = replace(
        train_backend,
        backend_profile_ids=allowed_backend_profile_ids,
    )
    slots["mcp_readiness"] = replace(
        mcp_readiness,
        receipt_schema_version=receipt_schema_version,
    )
    return replace(
        record,
        qualification=replace(manifest, slots=slots),
        receipt_schema_version=receipt_schema_version,
        required_backend_profile_id=required_backend_profile_id,
        allowed_backend_profile_ids=allowed_backend_profile_ids,
    )


def _activation_worker(
    registry_root: str,
    artifact_root: str,
    entered_atomic_write: Any,
    release_atomic_write: Any,
    results: Any,
) -> None:
    class PausingRegistry(ChallengeRegistry):
        def _atomic_write(self, record: ChallengeRecord) -> None:
            if record.status == "live":
                entered_atomic_write.set()
                if not release_atomic_write.wait(timeout=10):
                    raise TimeoutError("activation test was not released")
            super()._atomic_write(record)

    registry = PausingRegistry(registry_root, artifact_root)
    activated = registry.activate_live(CHALLENGE_ID, VERSION)
    results.put(("activation", activated.status))


def _contending_save_worker(
    registry_root: str,
    artifact_root: str,
    observed_contention: Any,
    unexpected_acquisition: Any,
    results: Any,
) -> None:
    original_flock = fcntl.flock

    def probed_flock(descriptor: int, operation: int) -> None:
        if operation == fcntl.LOCK_EX:
            try:
                original_flock(descriptor, operation | fcntl.LOCK_NB)
            except BlockingIOError:
                observed_contention.set()
                original_flock(descriptor, operation)
            else:
                unexpected_acquisition.set()
            return
        original_flock(descriptor, operation)

    fcntl.flock = probed_flock
    registry = ChallengeRegistry(registry_root, artifact_root)
    try:
        registry.save(ChallengeRecord(CHALLENGE_ID, VERSION))
    except RegistryError as exc:
        results.put(("save", exc.code))
    else:
        results.put(("save", "saved"))


def _reason_codes(
    registry: ChallengeRegistry, *, fixture_mode: bool = False
) -> tuple[str, ...]:
    result = registry.assess_live_eligibility(
        CHALLENGE_ID, VERSION, fixture_mode=fixture_mode
    )
    return tuple(reason.code for reason in result.reasons)


def test_default_record_is_draft_and_not_live(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = ChallengeRecord(CHALLENGE_ID, VERSION)
    assert record.status == "draft"
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)


def test_models_are_frozen_and_nested_maps_are_read_only(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    with pytest.raises(FrozenInstanceError):
        record.status = "live"  # type: ignore[misc]
    with pytest.raises(TypeError):
        record.artifacts["other"] = ArtifactBinding()  # type: ignore[index]


@pytest.mark.parametrize("missing", ("challenge_id", "version"))
def test_missing_identity_field_is_rejected(tmp_path: Path, missing: str) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    del payload[missing]
    _write_raw_record(registry, payload)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.field_required"
    assert captured.value.path == f"/{missing}"


@pytest.mark.parametrize(
    "challenge_id",
    (
        "",
        "Example",
        "1example",
        "example/id",
        "example\\id",
        "example id",
        "example__id",
        "example..id",
    ),
)
def test_invalid_challenge_id_is_rejected(challenge_id: str) -> None:
    with pytest.raises(ValueError):
        ChallengeKey(challenge_id, VERSION)


@pytest.mark.parametrize(
    "version",
    (
        "",
        ".1",
        "1.",
        "1..0",
        "1/0",
        "1\\0",
        "1 0",
        "../1",
        "v" + "1" * 64,
    ),
)
def test_invalid_version_is_rejected(version: str) -> None:
    with pytest.raises(ValueError):
        ChallengeKey(CHALLENGE_ID, version)


@pytest.mark.parametrize("version", ("1.0", "1.0.1", "v1.0", "2026-08"))
def test_required_version_forms_are_accepted(version: str) -> None:
    assert ChallengeKey(CHALLENGE_ID, version).version == version


def test_embedded_key_must_match_file_location(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry, version="1.0.1")
    _write_raw_record(registry, _stored_object(record))
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.key_mismatch"


@pytest.mark.parametrize(
    "payload",
    (
        '{"challenge_id":"example_challenge","challenge_id":"other"}',
        (
            '{"challenge_id":"example_challenge","version":"1.0",'
            '"status":"draft","allowed_backbones":[],"artifacts":{},'
            '"qualification":{"slots":{},"slots":{}}}'
        ),
    ),
)
def test_duplicate_json_object_key_is_rejected(tmp_path: Path, payload: str) -> None:
    registry = _registry(tmp_path)
    _write_raw_record(registry, payload)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "json.duplicate_key"


def test_duplicate_challenge_key_is_rejected_during_scan(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    payload = _stored_object(record)
    _write_raw_record(registry, payload)
    _write_raw_record(
        registry,
        payload,
        challenge_id="other_challenge",
        version="2.0",
    )
    with pytest.raises(RegistryError) as captured:
        registry.scan()
    assert captured.value.code == "registry.duplicate_key"


@pytest.mark.parametrize("nested", ("artifact", "manifest", "evidence"))
def test_unknown_fields_are_rejected_at_every_shape(
    tmp_path: Path, nested: str
) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    if nested == "artifact":
        payload["artifacts"][ARTIFACT_ID]["actual_digest"] = "operator-supplied"
    elif nested == "manifest":
        payload["qualification"]["signed"] = True
    else:
        payload["qualification"]["slots"]["score_pack"]["approved"] = True
    _write_raw_record(registry, payload)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.field_unknown"


def test_unknown_top_level_field_is_rejected(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    payload["actual_digest"] = payload["artifacts"][ARTIFACT_ID]["digest"]
    _write_raw_record(registry, payload)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.field_unknown"


def test_unsupported_lifecycle_state_is_rejected(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    payload["status"] = "retired"
    _write_raw_record(registry, payload)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.invalid"


@pytest.mark.parametrize("payload", ("{", '{"challenge_id":'))
def test_malformed_or_partial_json_fails_closed(tmp_path: Path, payload: str) -> None:
    registry = _registry(tmp_path)
    _write_raw_record(registry, payload)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert not assessment.eligible
    assert assessment.reasons[0].code == "json.invalid"


def test_excessively_deep_json_fails_closed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _write_raw_record(registry, "[" * 2_000 + "0" + "]" * 2_000)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert not assessment.eligible
    assert assessment.reasons[0].code == "json.invalid"


def test_oversized_json_integer_fails_closed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    configured_limit = getattr(sys, "get_int_max_str_digits", lambda: 4_300)()
    digit_count = (configured_limit or 4_300) + 1
    _write_raw_record(registry, "9" * digit_count)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert not assessment.eligible
    assert assessment.reasons[0].code == "json.invalid"


def test_fifo_record_is_rejected_without_blocking(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is unavailable")
    registry = _registry(tmp_path)
    path = registry.registry_root / CHALLENGE_ID / f"{VERSION}.json"
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.not_regular_file"


@pytest.mark.parametrize("slot", tuple(dict(REQUIRED_QUALIFICATION_STATES)))
def test_each_required_slot_missing_blocks(tmp_path: Path, slot: str) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    assert record.qualification is not None
    slots = dict(record.qualification.slots)
    del slots[slot]
    registry.save(
        replace(
            record,
            qualification=replace(record.qualification, slots=slots),
        )
    )
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert not assessment.eligible
    assert any(
        reason.code == "qualification.slot_missing" and reason.path.endswith(f"/{slot}")
        for reason in assessment.reasons
    )


def test_unknown_qualification_slot_is_rejected(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    payload["qualification"]["slots"]["operator_override"] = None
    _write_raw_record(registry, payload)
    with pytest.raises(RegistryError) as captured:
        registry.load(CHALLENGE_ID, VERSION)
    assert captured.value.code == "record.invalid"


def test_null_qualification_slot_blocks(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    assert record.qualification is not None
    slots = dict(record.qualification.slots)
    slots["score_pack"] = None
    registry.save(
        replace(record, qualification=replace(record.qualification, slots=slots))
    )
    assert "qualification.slot_null" in _reason_codes(registry)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    (
        ("state", None, "qualification.state_missing"),
        ("state", "HUMAN_INPUT", "qualification.state_placeholder"),
        ("state", "BLOCKED_FOR_LIVE_UNTIL_SET", "qualification.state_placeholder"),
        ("state", "", "qualification.state_missing"),
        ("reference", "HUMAN_INPUT", "qualification.reference_placeholder"),
        (
            "reference",
            "BLOCKED_FOR_LIVE_UNTIL_SET",
            "qualification.reference_placeholder",
        ),
        ("reference", None, "qualification.reference_missing"),
        ("reference", "   ", "qualification.reference_missing"),
        ("artifact_id", None, "qualification.artifact_id_missing"),
        ("artifact_id", "unknown_artifact", "qualification.artifact_unknown"),
    ),
)
def test_incomplete_or_placeholder_evidence_blocks(
    tmp_path: Path,
    field: str,
    value: str | None,
    expected_code: str,
) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    assert record.qualification is not None
    slots = dict(record.qualification.slots)
    evidence = slots["score_pack"]
    assert isinstance(evidence, QualificationEvidence)
    slots["score_pack"] = replace(evidence, **{field: value})
    registry.save(
        replace(record, qualification=replace(record.qualification, slots=slots))
    )
    assert expected_code in _reason_codes(registry)


@pytest.mark.parametrize(
    ("slot", "wrong_state"),
    (
        ("generator_envelope", "SIGNED"),
        ("launch_bar", "APPROVED"),
        ("generator_validation", "QUALIFIED"),
        ("train_backend", "PASSED"),
        ("mcp_readiness", "true"),
    ),
)
def test_slot_specific_state_matching_is_exact(
    tmp_path: Path, slot: str, wrong_state: str
) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    assert record.qualification is not None
    slots = dict(record.qualification.slots)
    evidence = slots[slot]
    assert isinstance(evidence, QualificationEvidence)
    slots[slot] = replace(evidence, state=wrong_state)
    registry.save(
        replace(record, qualification=replace(record.qualification, slots=slots))
    )
    assert "qualification.state_mismatch" in _reason_codes(registry)


def test_json_boolean_does_not_count_as_qualification_state(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    payload["qualification"]["slots"]["score_pack"]["state"] = True
    _write_raw_record(registry, payload)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert not assessment.eligible
    assert assessment.reasons[0].code == "record.field_type"


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    (
        ("challenge_id", "other_challenge", "qualification.challenge_id_mismatch"),
        (
            "challenge_version",
            "0.9",
            "qualification.challenge_version_mismatch",
        ),
        (
            "challenge_version",
            "1.0.0",
            "qualification.challenge_version_mismatch",
        ),
    ),
)
def test_wrong_or_stale_manifest_identity_blocks(
    tmp_path: Path, field: str, value: str, expected_code: str
) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    assert record.qualification is not None
    registry.save(
        replace(record, qualification=replace(record.qualification, **{field: value}))
    )
    assert expected_code in _reason_codes(registry)


@pytest.mark.parametrize(
    "digest",
    (
        "",
        "sha256:abc",
        "sha256:" + "A" * 64,
        "sha256:" + "0" * 63,
        "sha512:" + "0" * 64,
        "0" * 64,
    ),
)
def test_missing_or_malformed_digest_blocks(tmp_path: Path, digest: str) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry, artifact_digest=digest)
    registry.save(record)
    expected = "artifact.digest_missing" if not digest else "artifact.digest_invalid"
    assert expected in _reason_codes(registry)


def test_absent_digest_field_blocks(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    payload = _stored_object(_complete_record(registry))
    del payload["artifacts"][ARTIFACT_ID]["digest"]
    _write_raw_record(registry, payload)
    assert "artifact.digest_missing" in _reason_codes(registry)


@pytest.mark.parametrize(
    ("artifact_path", "expected_code"),
    (
        ("missing/file.json", "artifact.missing"),
        ("/absolute/file.json", "artifact.path_invalid"),
        ("../escape.json", "artifact.path_invalid"),
        ("safe/../../escape.json", "artifact.path_invalid"),
        ("safe\\escape.json", "artifact.path_invalid"),
    ),
)
def test_unsafe_or_missing_artifact_path_blocks(
    tmp_path: Path, artifact_path: str, expected_code: str
) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(
        registry,
        artifact_path=artifact_path,
        write_artifact=False,
    )
    registry.save(record)
    assert expected_code in _reason_codes(registry)


def test_directory_where_regular_artifact_required_blocks(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    directory_path = "evidence/directory"
    registry.artifact_root.joinpath(*directory_path.split("/")).mkdir(parents=True)
    record = _complete_record(
        registry,
        artifact_path=directory_path,
        write_artifact=False,
    )
    registry.save(record)
    assert "artifact.not_regular_file" in _reason_codes(registry)


def test_fifo_artifact_is_rejected_without_blocking(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is unavailable")
    registry = _registry(tmp_path)
    fifo_path = "evidence/qualification.fifo"
    target = registry.artifact_root.joinpath(*fifo_path.split("/"))
    target.parent.mkdir(parents=True)
    os.mkfifo(target)
    registry.save(
        _complete_record(
            registry,
            artifact_path=fifo_path,
            write_artifact=False,
        )
    )
    assert "artifact.not_regular_file" in _reason_codes(registry)


def test_non_filesystem_encodable_artifact_path_fails_closed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(
        _complete_record(
            registry,
            artifact_path="evidence/\ud800.json",
            write_artifact=False,
        )
    )
    assert "artifact.path_invalid" in _reason_codes(registry)


def test_symlink_escape_blocks(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    outside = tmp_path / "outside-secret.json"
    outside.write_bytes(ARTIFACT_BYTES)
    link = registry.artifact_root / "escaped.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    record = _complete_record(
        registry,
        artifact_path="escaped.json",
        write_artifact=False,
    )
    registry.save(record)
    assert "artifact.path_escape" in _reason_codes(registry)


def test_symlink_substitution_during_final_open_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    target = registry.artifact_root.joinpath(*ARTIFACT_PATH.split("/"))
    outside = tmp_path / "outside-matching-bytes.json"
    outside.write_bytes(ARTIFACT_BYTES)
    original_open = os.open
    substituted = False

    def substituting_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal substituted
        if not substituted and os.fspath(path) == target.name and dir_fd is not None:
            target.unlink()
            try:
                target.symlink_to(outside)
            except OSError:
                pytest.skip("symlinks are unavailable")
            substituted = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", substituting_open)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert substituted
    assert not assessment.eligible
    assert "artifact.path_escape" in tuple(reason.code for reason in assessment.reasons)


def test_hash_shaped_metadata_does_not_replace_actual_byte_verification(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    incorrect = _digest(b"operator-selected metadata")
    record = _complete_record(registry, artifact_digest=incorrect)
    registry.save(record)
    assert _reason_codes(registry) == ("artifact.digest_mismatch",)


def test_matching_digest_is_computed_from_actual_file_bytes(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert assessment.eligible
    assert assessment.reasons == ()


def test_artifact_byte_change_blocks(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    registry.save(record)
    _write_artifact(registry, content=b"changed bytes")
    assert "artifact.digest_mismatch" in _reason_codes(registry)


def test_same_name_artifact_file_substitution_blocks(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    target = registry.artifact_root.joinpath(*ARTIFACT_PATH.split("/"))
    original_inode = target.stat().st_ino
    substitute = target.with_name("substitute.json")
    substitute.write_bytes(b"substituted artifact at same filename")
    substitute.replace(target)
    assert target.stat().st_ino != original_inode
    assert "artifact.digest_mismatch" in _reason_codes(registry)


def test_stored_live_without_evidence_is_not_effectively_live(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    _store_live_directly(registry, ChallengeRecord(CHALLENGE_ID, VERSION))
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)


def test_stored_live_with_digest_mismatch_is_not_effectively_live(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry, artifact_digest=_digest(b"wrong"))
    _store_live_directly(registry, record)
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)


def test_successful_activation_and_later_artifact_mutation_fail_closed(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    activated = registry.activate_live(CHALLENGE_ID, VERSION)
    assert activated.status == "live"
    assert registry.is_effectively_live(CHALLENGE_ID, VERSION)
    _write_artifact(registry, content=b"changed after activation")
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)
    assert registry.load(CHALLENGE_ID, VERSION).status == "live"


def test_ordinary_save_rejects_direct_live_status(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    with pytest.raises(RegistryError) as captured:
        registry.save(replace(_complete_record(registry), status="live"))
    assert captured.value.code == "mutation.live_forbidden"


def test_existing_live_record_is_immutable_through_ordinary_save(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    live = _store_live_directly(registry, _complete_record(registry))
    with pytest.raises(RegistryError) as captured:
        registry.save(replace(live, status="draft"))
    assert captured.value.code == "mutation.live_immutable"


def test_activation_failure_leaves_original_record_bytes_unchanged(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry, artifact_digest=_digest(b"wrong")))
    path = registry.registry_root / CHALLENGE_ID / f"{VERSION}.json"
    before = path.read_bytes()
    with pytest.raises(LiveActivationError):
        registry.activate_live(CHALLENGE_ID, VERSION)
    assert path.read_bytes() == before
    assert registry.load(CHALLENGE_ID, VERSION).status == "draft"


def test_activation_uses_atomic_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    store_module = importlib.import_module("carbon.registry.store")
    original_replace = store_module.os.replace
    replacements: list[
        tuple[str, str, int | None, int | None, tuple[int, int] | None]
    ] = []

    def tracked_replace(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        directory_identity = None
        if src_dir_fd is not None:
            directory_stat = store_module.os.fstat(src_dir_fd)
            directory_identity = (directory_stat.st_dev, directory_stat.st_ino)
        replacements.append(
            (source, destination, src_dir_fd, dst_dir_fd, directory_identity)
        )
        original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(store_module.os, "replace", tracked_replace)
    registry.activate_live(CHALLENGE_ID, VERSION)
    assert len(replacements) == 1
    source, destination, src_dir_fd, dst_dir_fd, directory_identity = replacements[0]
    expected_parent_stat = (registry.registry_root / CHALLENGE_ID).stat()
    assert source.startswith(f".{VERSION}.") and source.endswith(".tmp")
    assert "/" not in source
    assert destination == f"{VERSION}.json"
    assert src_dir_fd is not None and src_dir_fd == dst_dir_fd
    assert directory_identity == (
        expected_parent_stat.st_dev,
        expected_parent_stat.st_ino,
    )


def test_per_key_lock_serializes_save_against_checked_activation(
    tmp_path: Path,
) -> None:
    try:
        context = multiprocessing.get_context("fork")
    except ValueError:
        pytest.skip("interprocess lock regression requires fork support")

    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    entered_atomic_write = context.Event()
    release_atomic_write = context.Event()
    observed_contention = context.Event()
    unexpected_acquisition = context.Event()
    results = context.Queue()
    activation = context.Process(
        target=_activation_worker,
        args=(
            str(registry.registry_root),
            str(registry.artifact_root),
            entered_atomic_write,
            release_atomic_write,
            results,
        ),
    )
    save = context.Process(
        target=_contending_save_worker,
        args=(
            str(registry.registry_root),
            str(registry.artifact_root),
            observed_contention,
            unexpected_acquisition,
            results,
        ),
    )

    activation.start()
    try:
        assert entered_atomic_write.wait(timeout=5)
        save.start()
        assert observed_contention.wait(timeout=5)
        assert not unexpected_acquisition.is_set()
    finally:
        release_atomic_write.set()
        activation.join(timeout=10)
        if save.pid is not None:
            save.join(timeout=10)
        for process in (activation, save):
            if process.pid is not None and process.is_alive():
                process.terminate()
                process.join(timeout=5)

    assert activation.exitcode == 0
    assert save.exitcode == 0
    outcomes = dict(results.get(timeout=2) for _ in range(2))
    assert outcomes == {
        "activation": "live",
        "save": "mutation.live_immutable",
    }
    assert registry.load(CHALLENGE_ID, VERSION).status == "live"
    assert registry.is_effectively_live(CHALLENGE_ID, VERSION)


def test_reason_codes_and_order_are_deterministic(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = ChallengeRecord(
        challenge_id=CHALLENGE_ID,
        version=VERSION,
        status="fixture",
        artifacts={
            "z_artifact": ArtifactBinding(path=None, digest="bad"),
            "a_artifact": ArtifactBinding(path=None, digest=None),
        },
        qualification=QualificationManifest(
            challenge_id="other_challenge",
            challenge_version="0.9",
            mode="fixture",
            slots={},
        ),
    )
    registry.save(record)
    first = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    second = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert first == second
    codes = tuple(reason.code for reason in first.reasons)
    assert codes[:4] == (
        "qualification.challenge_id_mismatch",
        "qualification.challenge_version_mismatch",
        "lifecycle.fixture_blocked",
        "qualification.fixture_mode_blocked",
    )
    slot_paths = tuple(reason.path for reason in first.reasons[4:12])
    assert slot_paths == tuple(
        f"/qualification/slots/{slot}" for slot, _ in REQUIRED_QUALIFICATION_STATES
    )
    assert tuple(reason.path for reason in first.reasons[12:]) == (
        "/artifacts/a_artifact/path",
        "/artifacts/a_artifact/digest",
        "/artifacts/z_artifact/path",
        "/artifacts/z_artifact/digest",
    )


def test_diagnostics_do_not_expose_artifact_path_or_bytes(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    secret_path = "private/evaluation/hidden-material.json"
    record = _complete_record(
        registry,
        artifact_path=secret_path,
        artifact_digest=_digest(b"different"),
    )
    registry.save(record)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    rendered = "\n".join(
        f"{reason.code} {reason.path} {reason.message}" for reason in assessment.reasons
    )
    assert secret_path not in rendered
    assert ARTIFACT_BYTES.decode().strip() not in rendered


def test_assessment_opens_only_the_configured_trusted_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    original_open = os.open
    opened: list[tuple[str, int | None]] = []

    def tracking_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        rendered = os.fsdecode(path)
        opened.append((rendered, dir_fd))
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", tracking_open)
    assert registry.can_go_live(CHALLENGE_ID, VERSION)
    absolute_opens = {
        Path(path)
        for path, dir_fd in opened
        if dir_fd is None and Path(path).is_absolute()
    }
    assert absolute_opens == {registry.registry_root, registry.artifact_root}
    assert all("hidden" not in path and "seed" not in path for path, _ in opened)


def test_complete_fixture_requires_explicit_fixture_mode(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry, status="fixture", mode="fixture"))
    assert not registry.can_go_live(CHALLENGE_ID, VERSION)
    assert registry.can_go_live(CHALLENGE_ID, VERSION, fixture_mode=True)
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)


def test_fixture_mode_requires_fixture_status(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry, status="draft", mode="fixture")
    registry.save(record)
    assessment = registry.assess_live_eligibility(
        CHALLENGE_ID, VERSION, fixture_mode=True
    )
    assert not assessment.eligible
    assert "lifecycle.fixture_status_required" in tuple(
        reason.code for reason in assessment.reasons
    )


def test_fixture_mode_requires_fixture_qualification_mode(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry, status="fixture", mode="production")
    registry.save(record)
    assessment = registry.assess_live_eligibility(
        CHALLENGE_ID, VERSION, fixture_mode=True
    )
    assert not assessment.eligible
    assert "qualification.fixture_mode_required" in tuple(
        reason.code for reason in assessment.reasons
    )


def test_changing_only_fixture_status_to_live_cannot_make_it_production_eligible(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    fixture = _complete_record(registry, status="fixture", mode="fixture")
    _store_live_directly(registry, fixture)
    assert not registry.can_go_live(CHALLENGE_ID, VERSION)
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)
    assert "qualification.fixture_mode_blocked" in _reason_codes(registry)


def test_fixture_evidence_cannot_be_activated_and_is_not_mutated(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry, status="fixture", mode="fixture"))
    path = registry.registry_root / CHALLENGE_ID / f"{VERSION}.json"
    before = path.read_bytes()
    with pytest.raises(LiveActivationError) as captured:
        registry.activate_live(CHALLENGE_ID, VERSION)
    assert captured.value.eligibility.reasons[0].code == (
        "lifecycle.activation_source_invalid"
    )
    assert path.read_bytes() == before
    assert registry.load(CHALLENGE_ID, VERSION).status == "fixture"


def test_draft_with_fixture_manifest_cannot_be_activated_or_mutated(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry, status="draft", mode="fixture"))
    path = registry.registry_root / CHALLENGE_ID / f"{VERSION}.json"
    before = path.read_bytes()
    with pytest.raises(LiveActivationError) as captured:
        registry.activate_live(CHALLENGE_ID, VERSION)
    assert "qualification.fixture_mode_blocked" in tuple(
        reason.code for reason in captured.value.eligibility.reasons
    )
    assert path.read_bytes() == before
    assert registry.load(CHALLENGE_ID, VERSION).status == "draft"


def test_repository_ships_no_default_live_registry_record() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    candidate_roots = (
        repository_root / "carbon" / "registry",
        repository_root / "tests" / "fixtures" / "registry",
    )
    for root in candidate_roots:
        for path in root.rglob("*.json") if root.exists() else ():
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload.get("status") != "live"


def test_static_fixture_is_structurally_isolated_from_production() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "registry"
    registry = ChallengeRegistry(
        fixture_root / "records",
        fixture_root / "artifacts",
    )
    record = registry.load("example_fixture", VERSION)
    assert record.status == "fixture"
    assert record.qualification is not None
    assert record.qualification.mode == "fixture"
    assert not registry.can_go_live("example_fixture", VERSION)
    assert registry.can_go_live("example_fixture", VERSION, fixture_mode=True)
    assert not registry.is_effectively_live("example_fixture", VERSION)


def test_exact_backbone_compatibility_lookup(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry, allowed_backbones=("fno", "uno")))
    assert registry.is_backbone_allowed(CHALLENGE_ID, VERSION, "fno")
    assert not registry.is_backbone_allowed(CHALLENGE_ID, VERSION, "deeponet")
    with pytest.raises(RegistryError) as captured:
        registry.is_backbone_allowed(CHALLENGE_ID, VERSION, "FNO")
    assert captured.value.code == "backbone.identifier_invalid"


def test_duplicate_allowed_backbone_is_rejected() -> None:
    with pytest.raises(ValueError):
        ChallengeRecord(
            CHALLENGE_ID,
            VERSION,
            allowed_backbones=("fno", "fno"),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("allowed_backbones", "fno"),
        ("allowed_backend_profile_ids", "reserved_profile_a-v1.0"),
    ),
)
def test_direct_model_rejects_string_where_identifier_tuple_is_required(
    field: str, value: str
) -> None:
    with pytest.raises(TypeError):
        ChallengeRecord(CHALLENGE_ID, VERSION, **{field: value})  # type: ignore[arg-type]


def test_compatibility_is_declarative_and_not_limited_to_a2_names(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    registry.save(
        ChallengeRecord(
            CHALLENGE_ID,
            VERSION,
            allowed_backbones=("future_operator",),
        )
    )
    assert registry.is_backbone_allowed(CHALLENGE_ID, VERSION, "future_operator")
    assert not registry.can_go_live(CHALLENGE_ID, VERSION)
    assert not registry.is_effectively_live(CHALLENGE_ID, VERSION)
    assert registry.load(CHALLENGE_ID, VERSION).status == "draft"


def test_compatibility_lookup_does_not_import_runtime_backend_registry(
    tmp_path: Path,
) -> None:
    script = f"""
import json
import pathlib
import sys
import tempfile

from carbon.registry import ChallengeRecord, ChallengeRegistry

assert "carbon.backbones" not in sys.modules
root = pathlib.Path(tempfile.mkdtemp(dir={str(tmp_path)!r}))
artifacts = root / "artifacts"
artifacts.mkdir()
registry = ChallengeRegistry(root / "registry", artifacts)
registry.save(ChallengeRecord(
    {CHALLENGE_ID!r}, {VERSION!r}, allowed_backbones=("future_operator",)
))
allowed = registry.is_backbone_allowed(
    {CHALLENGE_ID!r}, {VERSION!r}, "future_operator"
)
print(json.dumps({{
    "allowed": allowed,
    "runtime_registry_loaded": "carbon.backbones" in sys.modules,
}}))
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "allowed": True,
        "runtime_registry_loaded": False,
    }


def test_reserved_evidence_and_backend_bindings_round_trip(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _with_reserved_bindings(_complete_record(registry))
    registry.save(record)
    assert registry.load(CHALLENGE_ID, VERSION) == record
    assert registry.can_go_live(CHALLENGE_ID, VERSION)


def test_placeholder_challenge_version_blocks_production(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry, version="TODO")
    registry.save(record)
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, "TODO")
    assert not assessment.eligible
    assert "record.version_placeholder" in tuple(
        reason.code for reason in assessment.reasons
    )


def test_placeholder_receipt_binding_blocks_production(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _with_reserved_bindings(
        _complete_record(registry),
        receipt_schema_version="TODO",
        required_backend_profile_id=None,
        allowed_backend_profile_ids=(),
    )
    registry.save(record)
    codes = _reason_codes(registry)
    assert "receipt_schema.placeholder" in codes
    assert "receipt_schema.evidence_placeholder" in codes


def test_placeholder_backend_bindings_block_production(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _with_reserved_bindings(
        _complete_record(registry),
        receipt_schema_version=None,
        required_backend_profile_id="TODO",
        allowed_backend_profile_ids=("TODO",),
    )
    registry.save(record)
    codes = _reason_codes(registry)
    assert "backend_profile.placeholder" in codes
    assert "backend_profile.evidence_placeholder" in codes


def test_reserved_record_and_evidence_bindings_must_match_exactly(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    record = _with_reserved_bindings(_complete_record(registry))
    manifest = record.qualification
    assert manifest is not None
    slots = dict(manifest.slots)
    train_backend = slots["train_backend"]
    mcp_readiness = slots["mcp_readiness"]
    assert isinstance(train_backend, QualificationEvidence)
    assert isinstance(mcp_readiness, QualificationEvidence)
    slots["train_backend"] = replace(
        train_backend,
        backend_profile_ids=("reserved_profile_a-v1.0",),
    )
    slots["mcp_readiness"] = replace(
        mcp_readiness,
        receipt_schema_version="different_schema-v1.0",
    )
    registry.save(replace(record, qualification=replace(manifest, slots=slots)))
    codes = _reason_codes(registry)
    assert "backend_profile.binding_mismatch" in codes
    assert "receipt_schema.binding_mismatch" in codes


def test_required_backend_profile_must_be_in_exact_allowed_set(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    record = replace(
        _complete_record(registry),
        required_backend_profile_id="reserved_profile_a-v1.0",
        allowed_backend_profile_ids=("reserved_profile_b-v1.0",),
    )
    registry.save(record)
    assert "backend_profile.required_not_allowed" in _reason_codes(registry)


def test_reserved_binding_strings_do_not_qualify_a_challenge(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(
        ChallengeRecord(
            CHALLENGE_ID,
            VERSION,
            receipt_schema_version="reserved_schema-v1.0",
            required_backend_profile_id="reserved_profile_a-v1.0",
            allowed_backend_profile_ids=("reserved_profile_a-v1.0",),
        )
    )
    assessment = registry.assess_live_eligibility(CHALLENGE_ID, VERSION)
    assert not assessment.eligible
    assert assessment.reasons[0].code == "qualification.missing"


def test_json_round_trip_is_deterministic(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    registry.save(record)
    path = registry.registry_root / CHALLENGE_ID / f"{VERSION}.json"
    first = path.read_bytes()
    loaded = registry.load(CHALLENGE_ID, VERSION)
    registry.save(loaded)
    second = path.read_bytes()
    assert first == second
    assert first == serialize_record(loaded).encode("utf-8")


def test_save_rejects_records_larger_than_the_read_limit(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    record = _complete_record(registry)
    assert record.qualification is not None
    slots = dict(record.qualification.slots)
    evidence = slots["score_pack"]
    assert isinstance(evidence, QualificationEvidence)
    slots["score_pack"] = replace(evidence, reference="r" * (1024 * 1024))
    oversized = replace(
        record,
        qualification=replace(record.qualification, slots=slots),
    )
    with pytest.raises(RegistryError) as captured:
        registry.save(oversized)
    assert captured.value.code == "record.too_large"
    assert not (registry.registry_root / CHALLENGE_ID / f"{VERSION}.json").exists()


def test_scan_ignores_atomic_temporary_files(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.save(_complete_record(registry))
    temporary = registry.registry_root / CHALLENGE_ID / ".1.0.partial.tmp"
    temporary.write_text("{", encoding="utf-8")
    assert tuple(record.key for record in registry.scan()) == (
        ChallengeKey(CHALLENGE_ID, VERSION),
    )


def test_scan_fails_closed_if_registry_root_disappears(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.registry_root.rmdir()
    with pytest.raises(RegistryError) as captured:
        registry.scan()
    assert captured.value.code == "registry.root_invalid"


def test_scan_rejects_symbolic_link_entries(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    outside = tmp_path / "outside-registry"
    outside.mkdir()
    link = registry.registry_root / CHALLENGE_ID
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(RegistryError) as captured:
        registry.scan()
    assert captured.value.code == "registry.symlink_forbidden"


def test_installed_outside_tree_registry_is_dependency_free_and_usable(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert repository_root not in tmp_path.parents
    script = f"""
import importlib.abc
import json
import pathlib
import sys

blocked_roots = {{
    "bittensor", "jax", "mcp", "neuralop", "numpy", "physicsnemo", "torch"
}}
blocked_carbon = {{
    "carbon.backbones", "carbon.challenges", "carbon.common", "carbon.evaluation",
    "carbon.mcp", "carbon.qualification", "carbon.schema", "carbon.scoring",
    "carbon.seeding", "carbon.traineval", "carbon.training", "carbon.validator",
}}

class BoundaryBlocker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        del path, target
        root = fullname.partition(".")[0]
        blocked = root in blocked_roots or any(
            fullname == name or fullname.startswith(name + ".")
            for name in blocked_carbon
        )
        if blocked:
            self.attempted.append(fullname)
            raise ModuleNotFoundError("blocked A3 boundary import", name=fullname)
        return None

blocker = BoundaryBlocker()
sys.meta_path.insert(0, blocker)

from carbon.registry import ChallengeRecord, ChallengeRegistry

root = pathlib.Path({str(tmp_path)!r})
artifact_root = root / "artifacts"
artifact_root.mkdir()
registry = ChallengeRegistry(root / "registry", artifact_root)
registry.save(ChallengeRecord(
    {CHALLENGE_ID!r}, {VERSION!r}, allowed_backbones=("future_operator",)
))
loaded = registry.load({CHALLENGE_ID!r}, {VERSION!r})
sensitive_loaded = sorted(
    name for name in sys.modules
    if name.partition(".")[0] in blocked_roots
    or any(name == item or name.startswith(item + ".") for item in blocked_carbon)
)
print(json.dumps({{
    "attempted": blocker.attempted,
    "key": [loaded.challenge_id, loaded.version],
    "sensitive_loaded": sensitive_loaded,
}}))
"""
    process = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "attempted": [],
        "key": [CHALLENGE_ID, VERSION],
        "sensitive_loaded": [],
    }
