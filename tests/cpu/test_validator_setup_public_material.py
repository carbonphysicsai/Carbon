"""Actual public Git material and fresh-process synthetic import-only setup."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from carbon.battery.calibration import PREPARE_PATH, frozen_calibration
from carbon.battery.challenge import OCV_TABLE_PATH, TRAIN_V1_PATH, PublicMaterial
from carbon.battery.daemon import published_inputs
from carbon.battery.truth import LOCK_PATH, lock_digest
from carbon.validator_setup.bundle import PUBLIC_RUNTIME_MATERIALS, materialize, verify

REPOSITORY = Path(__file__).resolve().parents[2]


def package(tmp_path):
    revision = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY)
        .decode()
        .strip()
    )
    return materialize(REPOSITORY, revision, tmp_path / "release")


def test_package_contains_actual_pinned_public_runtime_material(tmp_path):
    built = package(tmp_path)
    material = PublicMaterial.load(built.root)
    assert material.train is not None
    assert frozen_calibration(built.root) == frozen_calibration(REPOSITORY)
    assert lock_digest(built.root) == lock_digest(REPOSITORY)
    for path in PUBLIC_RUNTIME_MATERIALS:
        assert (built.root / path).read_bytes() == (REPOSITORY / path).read_bytes()
    assert {
        OCV_TABLE_PATH,
        TRAIN_V1_PATH,
        PREPARE_PATH,
        LOCK_PATH,
    } <= PUBLIC_RUNTIME_MATERIALS
    published = published_inputs(REPOSITORY)
    assert published
    assert published_inputs(built.root) == published
    assert verify(built.root, built.digest) == built


def test_fresh_process_initializes_import_only_development_fixture_from_bundle(
    tmp_path,
):
    built = package(tmp_path)
    state = tmp_path / "public-synthetic-state"
    state.mkdir(mode=0o700)
    for directory in ("service", "backups", "work", "intake"):
        (state / directory).mkdir(mode=0o700)
    root = state / "public-fixture-root.bin"
    root.write_bytes(b"PUBLIC-FIXTURE-ROOT-NO-LIVE".ljust(32, b"!"))
    root.chmod(0o600)
    marker = state / "history"
    marker.write_bytes(b"public-synthetic-history-retained")
    before = hashlib.sha256(marker.read_bytes()).hexdigest()
    deployment, intake, service = (
        state / name for name in ("deployment.json", "intake.json", "service.json")
    )
    configs = {
        deployment: {
            "schema": "carbon.battery.validator-deployment.v1",
            "state": str(state / "state.sqlite3"),
            "private_root": str(root),
            "journal": str(state / "journal.jsonl"),
            "work": str(state / "work"),
            "backend": "direct",
            "require_commitment": False,
            "development_only": True,
            "batch_source": "answer_key",
            "rule": "v2",
        },
        intake: {
            "schema": "carbon.battery.intake.v1",
            "deployment": str(deployment),
            "transport_journal": str(state / "intake/transport.sqlite3"),
            "inbox": str(state / "intake/inbox.sqlite3"),
            "receiver": "public-synthetic-no-registration",
            "host": "127.0.0.1",
            "port": 8467,
        },
        service: {
            "schema": "carbon.battery.validator-service.v1",
            "intake": str(intake),
            "state_dir": str(state / "service"),
            "backups": str(state / "backups"),
            "allow_direct_backend": True,
        },
    }
    for path, value in configs.items():
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.validator_setup",
            "initialize",
            "--bundle",
            str(built.root),
            "--digest",
            built.digest,
            "--config",
            str(deployment),
            "--service-config",
            str(service),
        ],
        cwd=built.root,
        env={
            **os.environ,
            "PYTHONPATH": str(built.root),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    response = json.loads(result.stdout)
    assert response == {
        "status": "INITIALIZED_IMPORT_ONLY",
        "pool": "ROTATION_PENDING",
        "evaluation_ready": False,
        "references": "SHARED_IMPORT_ONLY",
    }
    assert hashlib.sha256(marker.read_bytes()).hexdigest() == before
    assert root.read_bytes() == b"PUBLIC-FIXTURE-ROOT-NO-LIVE".ljust(32, b"!")
    assert not (state / "wallet").exists()
