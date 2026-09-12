from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dev/run_c_ep3_reference_probe.py"
PROTOCOL = ROOT / "docs/development/c_ep3_reference_probe_protocol_v1.json"
SPEC = importlib.util.spec_from_file_location("c_ep3_reference_probe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


def protocol() -> dict[str, object]:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def observation() -> dict[str, object]:
    return {
        "schema_version": probe.SCHEMA,
        "run_id": "a" * 64,
        "evidence_class": "OBSERVED_PUBLIC_NUMERICAL_PROBE",
        "qualified": False,
        "integrated_exam": False,
        "operations": [
            {
                "name": "primary_cold",
                "unit": "ns",
                "wall_elapsed": 10,
                "process_elapsed": 9,
                "outcome": "SUCCEEDED",
            }
        ],
        "counts": {
            "distinct_public_cases": 1,
            "primary_reference_calls": 3,
            "primary_cold_calls": 1,
            "primary_warm_repeat_calls": 2,
            "refinement_calls": 1,
            "independent_witness_calls": 2,
            "physical_reference_attempts": 6,
            "integrated_candidate_jobs": 0,
        },
        "unknown_quantities": [
            {
                "name": "compatible_miner_demand",
                "value": None,
                "missing_reason": "no eligible trace",
            }
        ],
    }


def write_fixture_archive(path: Path, *, extra_member: bool = False) -> str:
    payloads = {
        "a.txt": b"pinned source\n",
        "packages/release_manifest.json": json.dumps(
            {"release_digest": probe.EXPECTED_RELEASE_DIGEST}
        ).encode("utf-8"),
    }
    manifest = {
        "schema": "public-artifact-manifest/1",
        "scientifically_qualified": False,
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in payloads.items()
        },
    }
    with zipfile.ZipFile(path, "w") as bundle:
        for name, data in payloads.items():
            bundle.writestr("fixture/" + name, data)
        bundle.writestr("fixture/artifact_manifest.json", json.dumps(manifest))
        if extra_member:
            bundle.writestr("fixture/unmanifested.txt", b"must reject")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_protocol_is_closed_and_exact() -> None:
    value = protocol()
    probe.validate_protocol(value)
    assert value["source"]["scientifically_qualified"] is False
    assert value["source"]["runtime_integrated"] is False
    assert value["case"]["source"].startswith("Verified evidence/reference_audit.json")
    assert value["configuration"]["provider_calls"] == 0
    assert value["configuration"]["official_evaluations"] == 0


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "archive_sha256"), "0" * 64),
        (("source", "permission_scope"), "PRODUCTION"),
        (("source", "scientifically_qualified"), True),
        (("source", "runtime_integrated"), True),
        (("configuration", "reference_grid"), 32),
        (("configuration", "warm_primary_repetitions"), 99),
    ],
)
def test_protocol_source_and_configuration_mismatches_fail_closed(
    path: tuple[str, str], value: object
) -> None:
    candidate = protocol()
    candidate[path[0]][path[1]] = value
    with pytest.raises(ValueError):
        probe.validate_protocol(candidate)


@pytest.mark.parametrize(
    "name",
    ["/absolute.txt", "../escape.txt", "root/../../escape", "root\\escape"],
)
def test_unsafe_archive_members_reject(name: str) -> None:
    with pytest.raises(ValueError, match="unsafe archive member"):
        probe._safe_relative(name)


def test_archive_hash_and_manifest_are_both_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "fixture.zip"
    digest = write_fixture_archive(archive)
    monkeypatch.setattr(probe, "ARCHIVE_SHA256", digest)
    monkeypatch.setattr(
        probe,
        "EXPECTED_PINS",
        {"a.txt": hashlib.sha256(b"pinned source\n").hexdigest()},
    )
    result = probe.verify_archive(archive)
    assert result["verified_entries"] == 2
    assert result["scientifically_qualified"] is False

    bad = tmp_path / "bad.zip"
    digest = write_fixture_archive(bad, extra_member=True)
    monkeypatch.setattr(probe, "ARCHIVE_SHA256", digest)
    with pytest.raises(ValueError, match="differ from"):
        probe.verify_archive(bad)


def test_wrong_archive_hash_rejects_before_import(tmp_path: Path) -> None:
    archive = tmp_path / "fixture.zip"
    write_fixture_archive(archive)
    with pytest.raises(ValueError, match="archive SHA-256 mismatch"):
        probe.verify_archive(archive)


def test_observation_accepts_scoped_counts_and_unknowns() -> None:
    value = observation()
    probe.validate_observation(value)
    assert value["counts"]["physical_reference_attempts"] == 6
    assert value["unknown_quantities"][0]["value"] is None


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("operations", 0, "unit", "seconds"), "unit"),
        (("operations", 0, "wall_elapsed", -1), "wall_elapsed"),
        (("operations", 0, "process_elapsed", 1.5), "process_elapsed"),
        (("counts", "physical_reference_attempts", -1), "count"),
        (("unknown_quantities", 0, "value", 0), "unknown quantities"),
        (("unknown_quantities", 0, "missing_reason", ""), "unknown quantities"),
    ],
)
def test_invalid_units_counts_and_unknown_as_zero_reject(
    mutation: tuple[object, ...], message: str
) -> None:
    value = observation()
    target: object = value
    for key in mutation[:-2]:
        target = target[key]
    target[mutation[-2]] = mutation[-1]
    with pytest.raises(ValueError, match=message):
        probe.validate_observation(value)


@pytest.mark.parametrize(
    "private_key", ["strategy_hash", "pack_id", "attempt_id", "latent", "solution"]
)
def test_public_observation_rejects_private_or_raw_keys(private_key: str) -> None:
    value = observation()
    value["diagnostics"] = {private_key: "secret"}
    with pytest.raises(ValueError, match="forbidden keys"):
        probe.validate_observation(value)


def test_failed_call_is_retained_once_without_retry() -> None:
    operations: list[dict[str, object]] = []

    def fail() -> None:
        raise RuntimeError("source-defined failure")

    with pytest.raises(RuntimeError, match="source-defined failure"):
        probe.record_operation("reference", fail, operations)
    assert len(operations) == 1
    assert operations[0]["outcome"] == "FAILED_RETAINED"
    assert operations[0]["failure_type"] == "RuntimeError"


def test_cold_warm_and_case_counts_do_not_double_count_repeats() -> None:
    counts = observation()["counts"]
    assert counts["distinct_public_cases"] == 1
    assert counts["primary_reference_calls"] == (
        counts["primary_cold_calls"] + counts["primary_warm_repeat_calls"]
    )
    assert counts["physical_reference_attempts"] == (
        counts["primary_reference_calls"]
        + counts["refinement_calls"]
        + counts["independent_witness_calls"]
    )
    assert counts["integrated_candidate_jobs"] == 0


def test_existing_output_directory_refuses_duplicate_run(tmp_path: Path) -> None:
    output = tmp_path / "already-exists"
    output.mkdir()
    with pytest.raises(FileExistsError, match="refuse duplicate"):
        probe.run_probe(tmp_path / "unused.zip", PROTOCOL, output)


def test_harness_has_no_carbon_runtime_or_sharing_import() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "carbon.evaluation_packs",
        "carbon.candidates",
        "carbon.execution",
        "carbon.fees",
        "share_reference",
        "add_member",
    ):
        assert forbidden not in source
