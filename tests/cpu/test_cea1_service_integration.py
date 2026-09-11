"""Canonical Linux service-backed evidence for C-EA1's one-host profile."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from carbon.evidence_archive import (
    POSTGRES_IMAGE,
    SYNTHETIC_FIXTURE_PREFIX,
    AcknowledgementState,
    ArchiveCode,
    ArchiveFailure,
    ArtifactInput,
    ArtifactState,
    AttemptRelation,
    AttemptRelationKind,
    CapacityLimits,
    EvidenceArchive,
    ExecutionDisposition,
    HttpImmutableObjectStore,
    KeyMaterial,
    PostgresCatalogue,
    ScientificResultState,
    SourceBinding,
    StageJournal,
    canonical_bytes,
    synthetic_capture_profile,
)
from carbon.execution import DurableExecutionBinding, ExecutionScope
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, SeedPin

pytestmark = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_DOCKER_TESTS") != "1",
    reason="canonical disposable-service evidence runs only in Docker-capable CI",
)


def _sha(character: str) -> str:
    return "sha256:" + character * 64


def _source(suffix: int = 1) -> SourceBinding:
    binding = DurableExecutionBinding(
        handle=ExecutionAttemptHandle(
            SubmissionId(f"00000000-0000-4000-8000-{suffix:012d}"),
            1,
            AdmissionKind.FIXTURE,
            SeedPin(
                ChallengeKey("burgers", "1.0"),
                "generator-v1",
                _sha("1"),
                "score-v1",
                _sha("2"),
                EvaluationBinding(b"e" * 32),
            ),
            ExecutionEnvironmentPin("synthetic-cpu-v1", _sha("3")),
        ),
        requester_identity=RequesterIdentity("synthetic-owner"),
        strategy_hash=StrategyHash(_sha("4")),
        scope=ExecutionScope.FIXTURE_DEVELOPMENT,
        resolved_plan_digest=_sha("5"),
        reconstruction_policy_digest=_sha("6"),
        resource_policy_digest=_sha("7"),
        protected_evaluation_policy_digest=_sha("8"),
    )
    return SourceBinding.from_execution_binding(
        binding,
        execution_id=f"synthetic-execution-{suffix}",
        physical_attempt_id=f"synthetic-attempt-{suffix}",
    )


def _inputs(source: SourceBinding):
    profile = synthetic_capture_profile()
    bodies = {
        "source_binding": canonical_bytes(source.payload()),
        "manifest_input": canonical_bytes(profile.payload()),
        "representative_output": SYNTHETIC_FIXTURE_PREFIX + b"output",
        "execution_log": SYNTHETIC_FIXTURE_PREFIX + b"public-log",
        "checkpoint": SYNTHETIC_FIXTURE_PREFIX + b"checkpoint",
    }
    return tuple(
        (
            ArtifactInput(rule.name, ArtifactState.WRITTEN, bodies[rule.name])
            if rule.name in bodies
            else ArtifactInput(rule.name, ArtifactState.INTENTIONALLY_ABSENT)
        )
        for rule in profile.artifact_rules
    )


class ObjectProcess:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.ready = root / "ready"
        self.process = None
        self.endpoint = ""

    def start(self) -> None:
        self.ready.unlink(missing_ok=True)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "carbon.evidence_archive.object_service",
                "--root",
                str(self.root),
                "--ready-file",
                str(self.ready),
                "--tenant-id",
                "carbon-synthetic-ci",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            if self.ready.is_file():
                self.endpoint = (
                    f"http://127.0.0.1:{self.ready.read_text(encoding='ascii')}"
                )
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.05)
        raise AssertionError("disposable object service did not start")

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)


@pytest.fixture(scope="module")
def postgres_service(tmp_path_factory):
    assert shutil.which("docker") is not None
    name = "carbon-cea1-" + uuid.uuid4().hex[:12]
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--platform",
            "linux/amd64",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            "POSTGRES_PASSWORD=carbon-synthetic-only",
            "--env",
            "POSTGRES_DB=carbon_cea1",
            POSTGRES_IMAGE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        port = (
            subprocess.run(
                ["docker", "port", name, "5432/tcp"],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .rsplit(":", 1)[1]
        )
        dsn = (
            f"postgresql://postgres:carbon-synthetic-only@127.0.0.1:{port}/carbon_cea1"
        )
        catalogue = PostgresCatalogue(dsn, CapacityLimits(max_active_entries=32))
        for _ in range(150):
            try:
                catalogue.migrate()
                break
            except ArchiveFailure:
                time.sleep(0.1)
        else:
            raise AssertionError("disposable PostgreSQL service did not become ready")
        yield name, dsn
    finally:
        subprocess.run(
            ["docker", "rm", "--force", name], capture_output=True, check=False
        )


@pytest.fixture
def services(tmp_path, postgres_service):
    name, dsn = postgres_service
    objects = ObjectProcess(tmp_path / "objects")
    objects.start()
    limits = CapacityLimits(max_active_entries=32)
    catalogue = PostgresCatalogue(dsn, limits)
    catalogue.migrate()
    archive = EvidenceArchive(
        catalogue,
        StageJournal(tmp_path / "spool.sqlite3", limits),
        HttpImmutableObjectStore(objects.endpoint, "carbon-synthetic-ci"),
    )
    try:
        yield name, objects, archive, catalogue
    finally:
        objects.stop()


def _admit_and_archive(archive, suffix=1):
    source = _source(suffix)
    profile = synthetic_capture_profile()
    admission = archive.admit(
        source,
        AttemptRelation(AttemptRelationKind.INITIAL),
        profile,
        execution_disposition=ExecutionDisposition.COMPLETED,
        scientific_result_state=ScientificResultState.SOURCE_RESULT_REF,
        scientific_result_ref=f"synthetic-result-{suffix}",
        declared_objects=7,
        declared_bytes=65536,
    )
    return archive.archive(
        admission,
        profile,
        _inputs(source),
        KeyMaterial("ephemeral-service-key-v1", b"s" * 32),
    )


def test_actual_postgres_and_object_services_preserve_exact_state_across_restarts(
    services,
):
    container, objects, archive, catalogue = services
    result = _admit_and_archive(archive, suffix=101)
    assert result.acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE
    before = catalogue.outbox()

    subprocess.run(["docker", "restart", container], check=True, capture_output=True)
    for _ in range(100):
        try:
            catalogue.verify_schema()
            break
        except ArchiveFailure:
            time.sleep(0.1)
    else:
        raise AssertionError("PostgreSQL did not recover after restart")
    objects.stop()
    objects.start()
    recovered = EvidenceArchive(
        catalogue,
        archive.journal,
        HttpImmutableObjectStore(objects.endpoint, "carbon-synthetic-ci"),
    )
    acknowledgement, _ = recovered.verify_current(
        result.entry,
        synthetic_capture_profile(),
        result.manifest,
        KeyMaterial("ephemeral-service-key-v1", b"s" * 32),
    )
    assert acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE
    assert catalogue.outbox() == before
    assert recovered.consume_outbox("service-audit", reverse=True) == 1
    assert recovered.consume_outbox("service-audit") == 0


def test_each_service_interruption_fails_closed_then_exact_replay_recovers(services):
    container, objects, archive, catalogue = services
    source = _source(102)
    profile = synthetic_capture_profile()
    admission = archive.admit(
        source,
        AttemptRelation(AttemptRelationKind.INITIAL),
        profile,
        execution_disposition=ExecutionDisposition.COMPLETED,
        scientific_result_state=ScientificResultState.SOURCE_RESULT_REF,
        scientific_result_ref="synthetic-result-102",
        declared_objects=7,
        declared_bytes=65536,
    )
    subprocess.run(["docker", "stop", container], check=True, capture_output=True)
    with pytest.raises(ArchiveFailure) as captured:
        catalogue.verify_schema()
    assert captured.value.code is ArchiveCode.STORE
    subprocess.run(["docker", "start", container], check=True, capture_output=True)
    for _ in range(100):
        try:
            catalogue.verify_schema()
            break
        except ArchiveFailure:
            time.sleep(0.1)

    objects.stop()
    with pytest.raises(ArchiveFailure) as captured:
        archive.archive(
            admission,
            profile,
            _inputs(source),
            KeyMaterial("ephemeral-service-key-v1", b"s" * 32),
        )
    assert captured.value.code is ArchiveCode.STORE
    objects.start()
    recovered = EvidenceArchive(
        catalogue,
        archive.journal,
        HttpImmutableObjectStore(objects.endpoint, "carbon-synthetic-ci"),
    )
    result = recovered.archive(
        admission,
        profile,
        _inputs(source),
        KeyMaterial("ephemeral-service-key-v1", b"s" * 32),
    )
    assert result.acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE


def test_service_backed_missing_corrupt_object_and_schema_version_fail_closed(services):
    _, objects, archive, catalogue = services
    result = _admit_and_archive(archive, suffix=103)
    object_key = next(
        record.object_key for record in result.manifest.artifacts if record.object_key
    )
    storage_digest = hashlib.sha256(object_key.encode("ascii")).hexdigest()
    stored_file = objects.root / "objects" / storage_digest[:2] / storage_digest[2:]
    original = stored_file.read_bytes()
    stored_file.write_bytes(original[:-1] + b"x")
    acknowledgement, _ = archive.verify_current(
        result.entry,
        synthetic_capture_profile(),
        result.manifest,
        KeyMaterial("ephemeral-service-key-v1", b"s" * 32),
    )
    assert acknowledgement.state is AcknowledgementState.REJECTED
    stored_file.write_bytes(original)

    with catalogue.transaction() as connection:
        connection.execute(
            "UPDATE cea1_schema_meta SET schema_version='corrupt-version' WHERE singleton=1"
        )
    with pytest.raises(ArchiveFailure) as captured:
        catalogue.verify_schema()
    assert captured.value.code is ArchiveCode.STORE
    with catalogue.transaction() as connection:
        connection.execute(
            "UPDATE cea1_schema_meta SET schema_version=%s WHERE singleton=1",
            ("carbon.evidence-archive.postgresql.v1",),
        )
    catalogue.verify_schema()


def test_service_configuration_contains_no_secret_or_payload_material():
    source = Path("carbon/evidence_archive/storage.py").read_text(encoding="utf-8")
    assert "carbon-synthetic-only" not in source
    assert "CARBON_CEA1_SYNTHETIC_V1" not in source
    assert "postgres:17.11-bookworm" in source
    assert POSTGRES_IMAGE.endswith(
        "051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0"
    )


def test_postgres_capacity_reservation_is_atomic_and_object_tenant_is_closed(
    tmp_path, postgres_service
):
    _, dsn = postgres_service
    limits = CapacityLimits(
        max_active_entries=1,
        max_objects=7,
        max_bytes=65536,
        max_spool_bytes=65536,
    )
    catalogue = PostgresCatalogue(dsn, limits)
    catalogue.migrate()
    objects = ObjectProcess(tmp_path / "capacity-objects")
    objects.start()
    try:
        archive = EvidenceArchive(
            catalogue,
            StageJournal(tmp_path / "capacity-spool.sqlite3", limits),
            HttpImmutableObjectStore(objects.endpoint, "carbon-synthetic-ci"),
        )
        barrier = threading.Barrier(3)
        admissions = []
        errors = []

        def admit(suffix):
            source = _source(suffix)
            barrier.wait()
            try:
                admissions.append(
                    archive.admit(
                        source,
                        AttemptRelation(AttemptRelationKind.INITIAL),
                        synthetic_capture_profile(),
                        execution_disposition=ExecutionDisposition.COMPLETED,
                        scientific_result_state=ScientificResultState.SOURCE_RESULT_REF,
                        scientific_result_ref=f"synthetic-result-{suffix}",
                        declared_objects=7,
                        declared_bytes=65536,
                    )
                )
            except ArchiveFailure as failure:
                errors.append(failure.code)

        threads = [
            threading.Thread(target=admit, args=(suffix,)) for suffix in (104, 105)
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        assert len(admissions) == 1
        assert errors == [ArchiveCode.CAPACITY]
        source = admissions[0].entry.source
        result = archive.archive(
            admissions[0],
            synthetic_capture_profile(),
            _inputs(source),
            KeyMaterial("ephemeral-service-key-v1", b"s" * 32),
        )
        assert result.acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE

        denied = HttpImmutableObjectStore(
            objects.endpoint, "different-synthetic-tenant"
        )
        with pytest.raises(ArchiveFailure) as captured:
            denied.list_keys("different-synthetic-tenant")
        assert captured.value.code is ArchiveCode.DENIED
    finally:
        objects.stop()
