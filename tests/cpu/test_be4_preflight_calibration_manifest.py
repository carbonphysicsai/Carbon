"""Raw non-qualifying B-E4 preflight calibration evidence tests."""

from __future__ import annotations

import copy
import math
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.dev.generate_be4_preflight_calibration import (
    _DESIGN_DOMAIN,
    DEFAULT_OUTPUT,
    CalibrationManifestError,
    _domain_digest,
    assert_replay_matches,
    load_manifest,
    manifest_content_digest,
    ordered_transcript_set_digest,
    render_manifest,
    replay_stable_digest,
    validate_manifest,
)


def _redigest(value: dict[str, object]) -> None:
    value["ordered_transcript_set_digest"] = ordered_transcript_set_digest(value)
    value["replay_stable_digest"] = replay_stable_digest(value)
    value["content_digest"] = manifest_content_digest(value)


def _manifest() -> dict[str, object]:
    return copy.deepcopy(load_manifest(DEFAULT_OUTPUT))


def test_committed_manifest_is_canonical_raw_preflight_only_evidence() -> None:
    manifest = _manifest()
    assert len(manifest["rows"]) == 500
    assert manifest["summary"]["complete_block_count"] == 125
    assert manifest["summary"]["failed_block_count"] == 0
    assert manifest["execution_boundary"] == {
        "preflight_only_calls": 500,
        "practice_calls": 0,
        "official_submission_or_result_calls": 0,
        "attack_campaign_calls": 0,
        "qualifying_gauntlet_calls": 0,
    }
    assert all(
        item["sample_block_count"] == 25 for item in manifest["summary"]["profiles"]
    )
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_manifest(manifest)


def test_empirical_wall_time_changes_raw_digest_but_not_replay_identity() -> None:
    reference = _manifest()
    replay = copy.deepcopy(reference)
    for row in replay["rows"]:
        row["wall_seconds"] += 0.000_001
    for profile in replay["summary"]["profiles"]:
        values = sorted(
            row["wall_seconds"]
            for row in replay["rows"]
            if row["profile"] == profile["profile"]
        )
        p99 = values[math.ceil(0.99 * len(values)) - 1]
        profile["wall_time_p99_seconds"] = p99
        profile["proposed_wall_time_cap_seconds"] = math.ceil(1.25 * p99)
    _redigest(replay)

    validate_manifest(replay)
    assert replay["content_digest"] != reference["content_digest"]
    assert (
        replay["ordered_transcript_set_digest"]
        == reference["ordered_transcript_set_digest"]
    )
    assert replay["replay_stable_digest"] == reference["replay_stable_digest"]
    assert_replay_matches(reference, replay)


def test_authority_relabel_is_rejected_even_after_all_digests_are_recomputed() -> None:
    manifest = _manifest()
    manifest["authority_ceiling"] = "QUALIFYING_EXECUTION_EVIDENCE"
    _redigest(manifest)
    with pytest.raises(CalibrationManifestError, match="identity is not exact"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    "mutation, message",
    (
        (
            lambda value: value["rows"].reverse(),
            "canonical order",
        ),
        (
            lambda value: value["rows"][0]["fixture_resources"].__setitem__(
                "total_quantity",
                value["rows"][0]["fixture_resources"]["total_quantity"] + 1.0,
            ),
            "resource total",
        ),
        (
            lambda value: value["rows"][0]["normalized_compute"]["counts"][
                0
            ].__setitem__(
                "count",
                value["rows"][0]["normalized_compute"]["counts"][0]["count"] + 1,
            ),
            "totals are inconsistent",
        ),
    ),
)
def test_structural_tampering_fails_after_outer_redigest(
    mutation, message: str
) -> None:
    manifest = _manifest()
    mutation(manifest)
    _redigest(manifest)
    with pytest.raises(CalibrationManifestError, match=message):
        validate_manifest(manifest)


def test_transcript_tampering_breaks_separate_set_digest() -> None:
    manifest = _manifest()
    manifest["rows"][0]["preflight_transcript_digest"] = "sha256:" + "0" * 64
    manifest["content_digest"] = manifest_content_digest(manifest)
    with pytest.raises(CalibrationManifestError, match="transcript-set"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("failure_type", "ARBITRARY_FAILURE"),
        ("service_reply_count", {"not": "a count"}),
        ("first_preflight_executable_attempt", {"not": "an attempt"}),
        ("proposal_count", False),
    ),
)
def test_failed_row_rejects_untyped_or_non_infrastructure_values(
    field: str, value: object
) -> None:
    manifest = _manifest()
    row = manifest["rows"][0]
    row.update(
        {
            "infrastructure_failed": True,
            "failure_type": "INFRASTRUCTURE_FAILURE",
            "proposal_count": 0,
            "first_preflight_executable_attempt": None,
            "service_reply_count": 0,
            "preflight_transcript_digest": None,
        }
    )
    row["fixture_resources"]["candidate_quantities"] = []
    row["fixture_resources"]["total_quantity"] = 0.0
    row[field] = value
    manifest["summary"]["failed_block_count"] = 1
    manifest["summary"]["block_infrastructure_failure_rate"] = 1 / 125
    _redigest(manifest)
    with pytest.raises(
        CalibrationManifestError,
        match="failed preflight row|proposal and resource counts",
    ):
        validate_manifest(manifest)


@pytest.mark.parametrize("section", ("arms", "drivers"))
def test_embedded_runtime_identity_tampering_fails_after_all_redigests(
    section: str,
) -> None:
    manifest = _manifest()
    if section == "arms":
        manifest["arms"][1]["artifact_id"] = "tampered_generic"
    else:
        manifest["drivers"][0]["policy_digest"] = "sha256:" + "7" * 64
    manifest["calibration_design_digest"] = _domain_digest(
        _DESIGN_DOMAIN,
        {
            "configuration": manifest["configuration"],
            "drivers": manifest["drivers"],
            "arms": manifest["arms"],
        },
    )
    _redigest(manifest)
    with pytest.raises(CalibrationManifestError, match="identities are not canonical"):
        validate_manifest(manifest)


def test_owner_ref_substitution_fails_after_all_outer_redigests() -> None:
    manifest = _manifest()
    manifest["configuration"]["candidate_assembly_ref"]["schema_version"] = "!!"
    manifest["calibration_design_digest"] = _domain_digest(
        _DESIGN_DOMAIN,
        {
            "configuration": manifest["configuration"],
            "drivers": manifest["drivers"],
            "arms": manifest["arms"],
        },
    )
    _redigest(manifest)
    with pytest.raises(CalibrationManifestError, match="current fixture graph"):
        validate_manifest(manifest)


def test_generator_source_cannot_convert_process_control_into_evidence() -> None:
    source = Path("scripts/dev/generate_be4_preflight_calibration.py").read_text(
        encoding="utf-8"
    )
    assert "except BaseException" not in source
    assert "except Exception as exc" in source
    assert "submit_prepared_fixture_run" not in source
    assert "read_official_fixture_result" not in source


def test_direct_generator_loads_the_checked_out_runtime(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/dev/generate_be4_preflight_calibration.py"
    command = (
        "import pathlib, runpy; "
        f"ns=runpy.run_path({str(script)!r}); "
        "ns['_load_fixture_builders'](); "
        "import carbon; print(pathlib.Path(carbon.__file__).resolve())"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(result.stdout.strip()).is_relative_to(root)
