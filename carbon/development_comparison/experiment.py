"""Trusted local freeze and admission; no provider or public-network dispatch."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from carbon.development_session.data import freeze as freeze_cases
from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest, profile_digest
from carbon.development_session.service import development_signer
from carbon.reconstruction.worker.model import (
    CONTROL_BYTES,
    DIAGNOSTIC_BYTES,
    INPUT_BYTES,
    OUTPUT_BYTES,
)

from .sources import read_json, resolve_source

SCHEMA = "carbon.cw1.development-comparison-contract.v1"
# Bounds derive from two evaluations, each 3 reconstructions, 3 predictions and
# 72 measurements. Retained references are reused; none are newly dispatched.
MAX_WORKERS = 156
WORKER_RESERVATION_BYTES = (
    4 * (INPUT_BYTES + OUTPUT_BYTES) + CONTROL_BYTES + DIAGNOSTIC_BYTES
)
STORAGE_LIMIT = MAX_WORKERS * WORKER_RESERVATION_BYTES + 2 * 2 * 1024**3 + 512 * 1024**2
LIMITS = {
    "schema": "carbon.cw1.comparison-session-limits.v1",
    "max_proposals": 2,
    "max_evaluations": 2,
    "max_worker_operations": MAX_WORKERS,
    "max_worker_seconds": 7200.0,
    "max_session_seconds": 10800,
    "max_storage_bytes": STORAGE_LIMIT,
    "worker_storage_reservation_bytes": WORKER_RESERVATION_BYTES,
    "max_provider_calls": 24,
    "max_provider_usd": 1.0,
    "max_service_calls": 24,
    "max_training_runs": 6,
    "max_training_updates": 384,
    "max_prediction_runs": 6,
    "max_measurement_runs": 144,
    "new_reference_runs": 0,
    "chain_transactions": 0,
}


def implementation_digest():
    carbon_root = Path(__file__).resolve().parent.parent
    paths = list((carbon_root / "development_comparison").glob("*.py"))
    paths += [
        carbon_root / "development_session" / name
        for name in (
            "agent.py",
            "budget.py",
            "service.py",
            "evaluation.py",
            "handoff.py",
            "data.py",
            "profile.py",
            "contracts.py",
            "prediction.py",
        )
    ]
    paths += [
        carbon_root / "measurement_runtime/protocol.py",
        carbon_root / "reexecution/store.py",
    ]
    return digest(
        canonical(
            {
                str(path.relative_to(carbon_root)): digest(path.read_bytes())
                for path in sorted(paths)
            }
        )
    )


def load_contract(root: Path):
    value = read_json(root / "comparison-contract.json")
    if (
        value.get("schema") != SCHEMA
        or value.get("limits") != LIMITS
        or value.get("profile_digest") != profile_digest()
        or value.get("session_root") != str(root)
        or value.get("acceptance_rule") is not None
        or value.get("equivalence_rule") is not None
    ):
        raise ValueError("exact frozen descriptive comparison contract required")
    return value


def check_storage(root: Path, reserve=0):
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("session symlink rejected")
        if path.is_file():
            total += path.stat().st_size
    if total + reserve > STORAGE_LIMIT or shutil.disk_usage(root).free < reserve:
        raise ValueError("comparison storage ceiling/headroom exhausted")
    return total


def freeze(
    root: Path,
    *,
    baseline_source: Path,
    image_manifest: Path,
    quarantine_journal: Path,
    reference_root: Path,
):
    if not root.is_absolute() or root.exists() or root.resolve() != root.absolute():
        raise ValueError("new absolute private comparison directory required")
    baseline_root = baseline_source.parent
    baseline = resolve_source(
        baseline_source,
        retention_root=baseline_root,
        quarantine_journal=quarantine_journal,
        reference_root=reference_root,
    )
    root.mkdir(mode=0o700, parents=True)
    # Explicit allow-list: no historical budgets, provider responses, authority,
    # signing keys, controller journals or evaluation labels are copied to miner.
    names = [
        "private-generation-entropy.bin",
        "generation-pin.json",
        "public-train.npz",
    ]
    names += [
        f"{role}-{cell:02d}-reference-result.json"
        for role in ("train", "eval", "stress")
        for cell in range(12)
    ]
    for name in names:
        source = baseline_root / name
        if (
            source.is_symlink()
            or not source.is_file()
            or source.stat().st_size > INPUT_BYTES
        ):
            raise ValueError("bounded retained preparation artifact required")
        write_once(root / name, source.read_bytes())
    manifest = freeze_cases(root, image_manifest)
    if manifest != baseline.manifest:
        raise ValueError("retained cohort/image differs")
    preparation = read_json(baseline_root / "preparation.json")
    if preparation["train_archive_digest"] != digest(
        (root / "public-train.npz").read_bytes()
    ):
        raise ValueError("retained TRAIN archive differs")
    for role in ("train", "eval", "stress"):
        for cell in range(12):
            record = read_json(root / f"{role}-{cell:02d}-reference-result.json")
            path = Path(record["solution_path"])
            if (
                not path.resolve().is_relative_to(reference_root.resolve())
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > INPUT_BYTES
                or digest(path.read_bytes()) != record["payload_digest"]
            ):
                raise ValueError("retained reference source changed")
    preparation["accounting"] = []
    preparation["reused_reference_count"] = 36
    preparation["new_reference_runs"] = 0
    write_once(root / "preparation.json", canonical(preparation))
    signer = development_signer(root)
    key = signer.verification_key
    trusted = {
        "evidence_ledger": str(root / "evidence.sqlite3"),
        "transport_journal": str(root / "transport.sqlite3"),
        "transport_context": baseline.trust["transport_context"],
        "verification_keys": [
            {
                "key_id": key.key_id,
                "public_key_hex": key.public_key.hex(),
                "valid_from_micros": key.valid_from_micros,
                "valid_until_micros": key.valid_until_micros,
                "revoked_at_micros": key.revoked_at_micros,
            }
        ],
    }
    commitments = []
    for slot in range(1, 3):
        row = []
        for replica in range(3):
            seed = os.urandom(32)
            write_once(root / f"proposal-{slot}-replica-{replica}-seed.bin", seed)
            row.append(digest(seed))
        commitments.append(row)
    value = {
        "schema": SCHEMA,
        "controller_implementation_digest": implementation_digest(),
        "report_schema": "carbon.cw1.development-comparison-report.v1",
        "profile_digest": profile_digest(),
        "session_root": str(root),
        "baseline_source": str(baseline_source),
        "baseline_source_digest": baseline.identity["source_digest"],
        "baseline_trust": baseline.trust,
        "challenger_trust": trusted,
        "shared_bindings": baseline.bindings,
        "baseline_strategy": baseline.strategy,
        "case_manifest": manifest,
        "quarantine_journal": str(quarantine_journal),
        "reference_root": str(reference_root),
        "reconstruction_seed_commitments": commitments,
        "limits": LIMITS,
        "roles": {
            "TRAIN": "RECONSTRUCTION_LABELS_ONLY",
            "EVAL": "SEPARATE_DESCRIPTIVE_MEASUREMENTS",
            "STRESS": "SEPARATE_DESCRIPTIVE_MEASUREMENTS",
        },
        "cohort_status": "HISTORICAL_SEEN_DEVELOPMENT_SUBSET",
        "aggregation": "EQUAL_CASE_WITHIN_REPLICA_THEN_EQUAL_REPLICA",
        "missing_or_nonfinite": "WITHHOLD_COMPLETE_COMPARISON",
        "half_time": "HORIZON_CLIPPED_WITH_CENSOR_COUNTS",
        "acceptance_rule": None,
        "equivalence_rule": None,
        "scalar_rule": None,
        "uncertainty_rule": None,
        "feedback_schema": baseline.feedback["schema"],
        "baseline_identity": baseline.identity,
    }
    write_once(root / "comparison-contract.json", canonical(value))
    write_once(root / "session-limits.json", canonical(LIMITS))
    check_storage(root, WORKER_RESERVATION_BYTES)
    return value


def baseline_for_session(root):
    contract = load_contract(root)
    path = Path(contract["baseline_source"])
    baseline = resolve_source(
        path,
        retention_root=path.parent,
        quarantine_journal=Path(contract["quarantine_journal"]),
        trusted=contract["baseline_trust"],
        reference_root=Path(contract["reference_root"]),
    )
    if (
        baseline.identity["source_digest"] != contract["baseline_source_digest"]
        or baseline.bindings != contract["shared_bindings"]
    ):
        raise ValueError("frozen baseline changed")
    return baseline


def proposal_seeds(root, number):
    contract = load_contract(root)
    if number not in (1, 2):
        raise ValueError("proposal slot exhausted")
    values = tuple(
        (root / f"proposal-{number}-replica-{replica}-seed.bin").read_bytes()
        for replica in range(3)
    )
    if (
        any(len(value) != 32 for value in values)
        or [digest(value) for value in values]
        != contract["reconstruction_seed_commitments"][number - 1]
    ):
        raise ValueError("frozen reconstruction randomness changed")
    return values
