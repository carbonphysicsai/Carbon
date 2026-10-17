"""Read only an explicitly named public calibration copy; report owner holds.

No predictions, model fitting, question search, solver calls or acceptance.
Public source bytes and provenance identities are checked; wall_s is only a
DEVELOPMENT cost estimate and is never converted to CPU core-seconds.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path

from . import configuration as cfg

MANIFEST_SHA256 = "7d4529df11998aadb6c16f6d87fcccde64fe24009aed1089f6959c8f1e31785b"


def _json(body):
    def reject(_):
        raise cfg.AssistantConfigurationError("finite_public_json_required")

    try:
        return json.loads(body, parse_constant=reject)
    except (ValueError, UnicodeError):
        raise cfg.AssistantConfigurationError("public_json_unavailable") from None


def _inspect_bytes(manifest_bytes, records_bytes, *, expected_manifest_sha256):
    """Pure aggregate extraction with source-byte and row provenance checks."""
    cfg.require(
        type(manifest_bytes) is bytes and type(records_bytes) is bytes,
        "public_bytes_required",
    )
    cfg.require(
        len(manifest_bytes) <= 1_000_000 and len(records_bytes) <= 32_000_000,
        "public_input_size_limit",
    )
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    cfg.require(
        manifest_sha == expected_manifest_sha256, "public_manifest_identity_mismatch"
    )
    manifest = _json(manifest_bytes)
    cfg.closed(
        manifest,
        {
            "schema",
            "scope",
            "counts",
            "missing",
            "plan",
            "records",
            "records_file_sha256",
            "solver",
        },
    )
    cfg.require(
        manifest["schema"] == "carbon.battery.physics-calibration-manifest.v1"
        and type(manifest["scope"]) is str
        and manifest["scope"].startswith("PUBLIC_DEVELOPMENT;"),
        "public_calibration_manifest_required",
    )
    cfg.require(
        type(manifest["counts"]) is dict
        and type(manifest["records"]) is dict
        and type(manifest["missing"]) is list,
        "public_manifest_inventory_required",
    )
    for count in manifest["counts"].values():
        cfg.checked(cfg.data.count, count)
    source_hash = hashlib.sha256(records_bytes).hexdigest()
    cfg.require(
        source_hash == manifest["records_file_sha256"],
        "public_records_identity_mismatch",
    )
    solver = manifest["solver"]
    cfg.require(
        type(solver) is dict
        and type(solver.get("image")) is str
        and re.fullmatch(
            r"ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:[0-9a-f]{64}",
            solver["image"],
        )
        is not None,
        "public_solver_identity_required",
    )
    image = solver["image"]
    lock = cfg.checked(cfg.data.sha, solver["overlay_lock_sha256"])
    expected_version = solver["overlay_verified"]["versions"]["pybamm"]
    wall, build, solve, seen, statuses = [], [], [], set(), {}
    for line in records_bytes.splitlines():
        if not line.strip():
            continue
        row = _json(line)
        cfg.require(
            type(row) is dict and type(row.get("case_id")) is str,
            "public_record_required",
        )
        identity = row["case_id"]
        cfg.require(
            identity not in seen and identity in manifest["records"],
            "public_record_identity_mismatch",
        )
        seen.add(identity)
        # This source's MANIFEST binds the exact JSONL line, excluding its LF.
        row_hash = hashlib.sha256(line).hexdigest()
        cfg.require(
            row_hash == manifest["records"][identity], "public_record_digest_mismatch"
        )
        provenance = row.get("solver_provenance")
        cfg.require(
            type(provenance) is dict
            and provenance.get("solver_image") == image
            and provenance.get("overlay_lock_sha256") == lock
            and provenance.get("pybamm") == expected_version,
            "public_record_provenance_mismatch",
        )
        status = row.get("status")
        cfg.require(
            status
            in ("OK", "REFERENCE_TIMEOUT", "REFERENCE_SOLVER_FAILED", "FAILED_INFRA"),
            "public_reference_status_invalid",
        )
        statuses[status] = statuses.get(status, 0) + 1
        wall.append(cfg.number(row["wall_s"], nonnegative=True))
        build.append(cfg.number(row["timing_s"]["build"], nonnegative=True))
        solve.append(cfg.number(row["timing_s"]["solve"], nonnegative=True))
    cfg.require(
        bool(wall)
        and set(manifest["records"]) == seen
        and statuses == manifest["counts"],
        "complete_public_record_inventory_required",
    )
    return {
        "schema": "carbon.product.assistant-public-panel-gap.v1",
        "scope": "DEVELOPMENT",
        "source_role": "PUBLIC_PHYSICS_CALIBRATION_NOT_ACCEPTED_DECISION_EVIDENCE",
        "manifest_sha256": manifest_sha,
        "records_sha256": source_hash,
        "records": len(seen),
        "counts": statuses,
        "provenance_basis": "BYTE_AND_DOCUMENT_IDENTITY_MATCH_ONLY",
        "solver_image": image,
        "pybamm_version": expected_version,
        "overlay_lock_sha256": lock,
        "solver_acceptance": {
            "status": "SOLVER_NOT_ACCEPTED",
            "accepted": False,
            "authority": "OWNER_PRODUCT_CHAT_2026_10_12",
            "reason": "CURRENT_USE_HOLD_NOT_OVERRIDDEN_BY_HISTORICAL_MANIFEST_TEXT",
        },
        "wall_cost_estimate": {
            "basis": "DEVELOPMENT_RECORDED_WALL_SECONDS_ONLY",
            "minimum": min(wall),
            "median": statistics.median(wall),
            "maximum": max(wall),
            "build_median": statistics.median(build),
            "solve_median": statistics.median(solve),
        },
        "cpu_core_seconds": {
            "value": None,
            "status": "GAP",
            "reason": "NOT_RECORDED_NO_WALL_TIME_OR_RSS_CONVERSION",
        },
        "real_battery_comparison": {
            "status": "GAP",
            "regret": None,
            "reasons": ["SOLVER_NOT_ACCEPTED", "CPU_CORE_SECONDS_MISSING"],
        },
        "qualification_claim": False,
    }


def inspect_bytes(manifest_bytes, records_bytes, *, expected_manifest_sha256):
    try:
        return _inspect_bytes(
            manifest_bytes,
            records_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        raise cfg.AssistantConfigurationError(
            "public_panel_unavailable_or_mismatched"
        ) from None


def read_copy(directory, *, expected_manifest_sha256=MANIFEST_SHA256):
    """Two fixed public filenames, no discovery and no raw-record export."""
    root = Path(directory)
    targets = [root / "MANIFEST.json", root / "records.jsonl"]
    cfg.require(
        not re.search(r"hidden|sealed|protected|private", str(root), re.IGNORECASE),
        "public_path_required",
    )
    for target in targets:
        cfg.require(
            not any(p.is_symlink() for p in [target, *target.parents]),
            "public_regular_files_required",
        )
        cfg.require(target.is_file(), "public_copy_unavailable")
    manifest_bytes = targets[0].read_bytes()
    # Refuse a wrong/private manifest before opening any record body.
    cfg.require(
        hashlib.sha256(manifest_bytes).hexdigest() == expected_manifest_sha256,
        "public_manifest_identity_mismatch",
    )
    manifest = _json(manifest_bytes)
    cfg.require(
        type(manifest.get("scope")) is str
        and manifest["scope"].startswith("PUBLIC_DEVELOPMENT;"),
        "public_calibration_manifest_required",
    )
    cfg.require(targets[1].stat().st_size <= 32_000_000, "public_input_size_limit")
    return inspect_bytes(
        manifest_bytes,
        targets[1].read_bytes(),
        expected_manifest_sha256=expected_manifest_sha256,
    )


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        report = read_copy(args.directory)
    except (
        cfg.AssistantConfigurationError,
        OSError,
        KeyError,
        TypeError,
        UnicodeError,
    ):
        parser.exit(2, "Refused: public calibration copy unavailable or mismatched.\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
