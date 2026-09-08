#!/usr/bin/env python3
"""Generate or verify the raw, non-qualifying B-E4 preflight calibration.

This diagnostic intentionally composes the repository's TEST_ONLY fixture graph
from ``tests/cpu/test_be4_execution_integration.py``.  It is a development
evidence tool, not a dependency of the packaged ``carbon`` runtime.  It calls
only ``prepare_nonqualifying_preflight``: no B-07C practice, A7/A8 official
submission, attack campaign, or qualifying gauntlet operation is reachable.

Wall-clock observations are empirical.  The manifest therefore exposes three
separate digests:

* ``content_digest`` binds the complete raw manifest, including wall time;
* ``ordered_transcript_set_digest`` binds ordered run ids and preflight
  transcript digests; and
* ``replay_stable_digest`` binds all replay-stable content with wall-time
  fields and wall-time summary values removed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CPU_FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "cpu"
if str(REPOSITORY_ROOT) not in sys.path:
    # Direct script execution otherwise prefers an older installed ``carbon``
    # over the checked-out evidence generator being replayed.
    sys.path.insert(0, str(REPOSITORY_ROOT))
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / ".agent"
    / "evidence"
    / "wave_b"
    / "b-e4-preflight-calibration-v1.json"
)
SCHEMA_VERSION = "1.0"
GENERATOR_ID = "be4_nonqualifying_preflight_calibration"
GENERATOR_VERSION = "1.0"
EVIDENCE_ROLE = "NONQUALIFYING_PREFLIGHT_CALIBRATION_RAW"
AUTHORITY_CEILING = "DESIGN_ANALYSIS_ONLY_NOT_EXECUTION_EVIDENCE"
BLOCKS_PER_PROFILE = 25
CALIBRATION_WALL_CEILING_SECONDS = 30.0
CALIBRATION_COMPUTE_CEILING = 1_000.0
CALIBRATION_ATTEMPT_LIMIT = 8
CALIBRATION_FIXTURE_RESOURCE_CEILING = 15

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_MANIFEST_DOMAIN = b"carbon.be4.preflight-calibration-manifest.v1\x00"
_DESIGN_DOMAIN = b"carbon.be4.preflight-calibration-design.v1\x00"
_TRANSCRIPT_SET_DOMAIN = b"carbon.be4.preflight-transcript-set.v1\x00"
_REPLAY_STABLE_DOMAIN = b"carbon.be4.preflight-calibration-replay.v1\x00"
_EXPECTED_PROFILES = (
    "PLANNER",
    "CODE_GENERATING",
    "EVOLUTIONARY",
    "LITERATURE_GROUNDED",
    "MINIMALIST",
)
_EXPECTED_ARMS = (
    "NO_PRIOR",
    "GENERIC_PRIOR",
    "V1_DIRECTIVE_PRIOR",
    "V2_TEST_ONLY_PRIOR",
)
_INFRASTRUCTURE_FAILURE_TYPES = (
    "PROVIDER_UNAVAILABLE",
    "INFRASTRUCTURE_FAILURE",
)


class CalibrationManifestError(ValueError):
    """The raw calibration evidence is malformed or content-inconsistent."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CalibrationManifestError(
            "manifest content is not canonical JSON"
        ) from exc


def _domain_digest(domain: bytes, value: object) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise CalibrationManifestError(f"{label} does not have its exact schema")
    return value


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _DIGEST_RE.fullmatch(value) is None:
        raise CalibrationManifestError(f"{label} is not an exact tagged SHA-256 digest")
    return value


def _finite_nonnegative(value: object, label: str) -> float:
    if type(value) not in (int, float) or type(value) is bool:
        raise CalibrationManifestError(f"{label} is not an exact number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise CalibrationManifestError(f"{label} is not finite and non-negative")
    return result


def _challenge_identity(key: object) -> dict[str, str]:
    return {
        "challenge_id": key.challenge_id,
        "version": key.version,
    }


def _object_ref_identity(ref: object) -> dict[str, object]:
    return {
        "challenge": _challenge_identity(ref.challenge_key),
        "object_id": ref.object_id,
        "object_version": ref.object_version,
        "schema_version": ref.schema_version,
        "canonicalization_profile": ref.canonicalization_profile,
        "content_digest": ref.content_digest,
    }


def _simple_ref_identity(ref: object) -> dict[str, object]:
    return {
        "challenge": _challenge_identity(ref.challenge_key),
        "schema_version": ref.schema_version,
        "canonicalization_profile": ref.canonicalization_profile,
        "content_digest": ref.content_digest,
    }


def _prior_ref_identity(ref: object) -> dict[str, object]:
    return {
        "challenge": _challenge_identity(ref.challenge_key),
        "channel": ref.channel.value,
        "publication_sequence": ref.publication_sequence,
        "content_hash": ref.content_hash,
    }


def _authorization_ref_identity(ref: object) -> dict[str, object]:
    return {
        "challenge": _challenge_identity(ref.challenge_key),
        "authorization_id": ref.authorization_id,
        "content_digest": ref.content_digest,
    }


def _driver_identity(ref: object) -> dict[str, object]:
    return {
        "profile": ref.profile.value,
        "driver_id": ref.driver_id,
        "driver_version": ref.driver_version,
        "runtime_id": ref.runtime_id,
        "runtime_version": ref.runtime_version,
        "runtime_digest": ref.runtime_digest,
        "policy_digest": ref.policy_digest,
        "corpus_digest": ref.corpus_digest,
    }


def _arm_identity(artifact: object) -> dict[str, object]:
    source = artifact.source_prior_pack_ref
    return {
        "arm": artifact.arm.value,
        "artifact_id": artifact.artifact_id,
        "artifact_version": artifact.artifact_version,
        "content_digest": artifact.content_digest,
        "source_prior_pack_ref": (
            None if source is None else _prior_ref_identity(source)
        ),
        "proposal_hints": [
            {
                "surface_id": hint.surface_id,
                "direction": hint.direction.value,
                "replacement_token": hint.replacement_token,
            }
            for hint in artifact.proposal_hints
        ],
    }


def _compute_identity(receipt: object) -> dict[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "policy_id": receipt.policy_id,
        "policy_digest": receipt.policy_digest,
        "counts": [
            {"kind": item.kind.value, "count": item.count} for item in receipt.counts
        ],
        "total_work_units": receipt.total_work_units,
        "content_digest": receipt.content_digest,
    }


def _configuration(
    *,
    domain: object,
    scaffold_ref: object,
    practice_pack_ref: object,
    prior_lookup: object,
    strategy_domain: object,
) -> dict[str, object]:
    source = domain.compile_fixture
    return {
        "fixture_graph_source": "tests/cpu/test_be4_execution_integration.py",
        "blocks_per_profile": BLOCKS_PER_PROFILE,
        "arm_count": 4,
        "calibration_budget": {
            "wall_time_seconds": CALIBRATION_WALL_CEILING_SECONDS,
            "normalized_compute_units": CALIBRATION_COMPUTE_CEILING,
            "attempt_limit": CALIBRATION_ATTEMPT_LIMIT,
            "per_candidate_fixture_resource_ceiling": (
                CALIBRATION_FIXTURE_RESOURCE_CEILING
            ),
        },
        "challenge": _challenge_identity(source.key),
        "candidate_assembly_ref": _object_ref_identity(source.assembly.to_ref()),
        "parameter_catalog_ref": _object_ref_identity(
            source.catalog.to_ref(candidate_assembly=source.assembly)
        ),
        "resource_policy_ref": _object_ref_identity(domain.policy_ref),
        "strategy_domain_digest": strategy_domain.content_digest,
        "scaffold_ref": _simple_ref_identity(scaffold_ref),
        "practice_pack_ref": _simple_ref_identity(practice_pack_ref),
        "v2_prior_pack_ref": _prior_ref_identity(prior_lookup.prior_pack_ref),
        "v2_authorization_ref": _authorization_ref_identity(
            prior_lookup.authorization.receipt_ref
        ),
    }


def _stable_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(manifest)
    value.pop("content_digest", None)
    value.pop("replay_stable_digest", None)
    for row in value["rows"]:
        row.pop("wall_seconds", None)
    for profile in value["summary"]["profiles"]:
        profile.pop("wall_time_p99_seconds", None)
        profile.pop("proposed_wall_time_cap_seconds", None)
    return value


def ordered_transcript_set_digest(manifest: dict[str, Any]) -> str:
    ordered = [
        {
            "row_id": row["row_id"],
            "transcript_digest": (
                "NO_TRANSCRIPT"
                if row["preflight_transcript_digest"] is None
                else row["preflight_transcript_digest"]
            ),
        }
        for row in manifest["rows"]
    ]
    return _domain_digest(_TRANSCRIPT_SET_DOMAIN, ordered)


def replay_stable_digest(manifest: dict[str, Any]) -> str:
    return _domain_digest(_REPLAY_STABLE_DOMAIN, _stable_projection(manifest))


def manifest_content_digest(manifest: dict[str, Any]) -> str:
    value = copy.deepcopy(manifest)
    value.pop("content_digest", None)
    return _domain_digest(_MANIFEST_DOMAIN, value)


def render_manifest(manifest: dict[str, Any]) -> str:
    validate_manifest(manifest)
    return (
        json.dumps(
            manifest, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True
        )
        + "\n"
    )


def _nearest_rank_p99(values: list[float]) -> float:
    return sorted(values)[math.ceil(0.99 * len(values)) - 1]


def _validate_compute(value: object) -> None:
    from carbon.gauntlet.meter import (
        METER_POLICY_DIGEST,
        METER_POLICY_ID,
        METER_SCHEMA_VERSION,
        NormalizedComputeReceipt,
        PolicyWorkCount,
        PolicyWorkKind,
    )

    receipt = _exact_keys(
        value,
        {
            "schema_version",
            "policy_id",
            "policy_digest",
            "counts",
            "total_work_units",
            "content_digest",
        },
        "normalized compute receipt",
    )
    if (
        receipt["schema_version"] != METER_SCHEMA_VERSION
        or receipt["policy_id"] != METER_POLICY_ID
        or receipt["policy_digest"] != METER_POLICY_DIGEST
    ):
        raise CalibrationManifestError("compute meter identity is not exact")
    _digest(receipt["content_digest"], "compute receipt digest")
    if type(receipt["counts"]) is not list or len(receipt["counts"]) != len(
        PolicyWorkKind
    ):
        raise CalibrationManifestError("compute receipt does not have nine counts")
    total = 0
    counts: list[PolicyWorkCount] = []
    for item in receipt["counts"]:
        count = _exact_keys(item, {"kind", "count"}, "compute count")
        if type(count["kind"]) is not str or type(count["count"]) is not int:
            raise CalibrationManifestError("compute count has the wrong type")
        if count["count"] < 0:
            raise CalibrationManifestError("compute count cannot be negative")
        try:
            kind = PolicyWorkKind(count["kind"])
        except ValueError as exc:
            raise CalibrationManifestError("compute count kind is unknown") from exc
        counts.append(PolicyWorkCount(kind, count["count"]))
        total += count["count"]
    if (
        tuple(item.kind for item in counts) != tuple(PolicyWorkKind)
        or receipt["total_work_units"] != total
    ):
        raise CalibrationManifestError("compute receipt totals are inconsistent")
    reconstructed = NormalizedComputeReceipt(
        METER_SCHEMA_VERSION,
        METER_POLICY_ID,
        METER_POLICY_DIGEST,
        tuple(counts),
        total,
    )
    if reconstructed.content_digest != receipt["content_digest"]:
        raise CalibrationManifestError("compute receipt digest is inconsistent")


def _validate_current_design_identities(
    *,
    configuration: dict[str, Any],
    drivers: object,
    arms: object,
) -> tuple[list[str], list[str], object, object, object, object]:
    """Reconstruct the current canonical driver and arm identities."""

    from carbon.gauntlet.agents import fixture_driver_ref
    from carbon.gauntlet.execution import (
        build_nonqualifying_preflight_arm_artifacts,
    )
    from carbon.gauntlet.model import AgentProfile
    from carbon.registry import ChallengeKey
    from carbon.research import (
        MockScaffoldRef,
        PracticePackRef,
        PriorChannel,
        PriorPackRef,
        TestOnlyPriorAuthorizationReceiptRef,
    )

    challenge = _exact_keys(
        configuration["challenge"], {"challenge_id", "version"}, "challenge"
    )
    if any(type(challenge[key]) is not str for key in challenge):
        raise CalibrationManifestError("challenge identity is not exact")
    try:
        challenge_key = ChallengeKey(challenge["challenge_id"], challenge["version"])
    except (TypeError, ValueError) as exc:
        raise CalibrationManifestError("challenge identity is invalid") from exc

    budget = _exact_keys(
        configuration["calibration_budget"],
        {
            "wall_time_seconds",
            "normalized_compute_units",
            "attempt_limit",
            "per_candidate_fixture_resource_ceiling",
        },
        "calibration budget",
    )
    if budget != {
        "wall_time_seconds": CALIBRATION_WALL_CEILING_SECONDS,
        "normalized_compute_units": CALIBRATION_COMPUTE_CEILING,
        "attempt_limit": CALIBRATION_ATTEMPT_LIMIT,
        "per_candidate_fixture_resource_ceiling": (
            CALIBRATION_FIXTURE_RESOURCE_CEILING
        ),
    }:
        raise CalibrationManifestError("calibration budget identity is not exact")
    if configuration["fixture_graph_source"] != (
        "tests/cpu/test_be4_execution_integration.py"
    ):
        raise CalibrationManifestError("fixture graph source is not exact")

    for label in (
        "candidate_assembly_ref",
        "parameter_catalog_ref",
        "resource_policy_ref",
    ):
        ref = _exact_keys(
            configuration[label],
            {
                "challenge",
                "object_id",
                "object_version",
                "schema_version",
                "canonicalization_profile",
                "content_digest",
            },
            label,
        )
        if ref["challenge"] != challenge or any(
            type(ref[field]) is not str
            for field in (
                "object_id",
                "object_version",
                "schema_version",
                "canonicalization_profile",
            )
        ):
            raise CalibrationManifestError(f"{label} identity is not exact")
        _digest(ref["content_digest"], f"{label} content digest")
    for label in ("scaffold_ref", "practice_pack_ref"):
        ref = _exact_keys(
            configuration[label],
            {
                "challenge",
                "schema_version",
                "canonicalization_profile",
                "content_digest",
            },
            label,
        )
        if ref["challenge"] != challenge or any(
            type(ref[field]) is not str
            for field in ("schema_version", "canonicalization_profile")
        ):
            raise CalibrationManifestError(f"{label} identity is not exact")
        _digest(ref["content_digest"], f"{label} content digest")
    try:
        scaffold_ref = MockScaffoldRef(
            challenge_key,
            configuration["scaffold_ref"]["schema_version"],
            configuration["scaffold_ref"]["canonicalization_profile"],
            configuration["scaffold_ref"]["content_digest"],
        )
        practice_pack_ref = PracticePackRef(
            challenge_key,
            configuration["practice_pack_ref"]["schema_version"],
            configuration["practice_pack_ref"]["canonicalization_profile"],
            configuration["practice_pack_ref"]["content_digest"],
        )
    except (TypeError, ValueError) as exc:
        raise CalibrationManifestError(
            "scaffold or practice-pack identity is invalid"
        ) from exc

    prior = _exact_keys(
        configuration["v2_prior_pack_ref"],
        {"challenge", "channel", "publication_sequence", "content_hash"},
        "v2 prior pack ref",
    )
    if prior["challenge"] != challenge or type(prior["channel"]) is not str:
        raise CalibrationManifestError("v2 prior pack identity is not exact")
    try:
        prior_pack_ref = PriorPackRef(
            challenge_key,
            PriorChannel(prior["channel"]),
            prior["publication_sequence"],
            prior["content_hash"],
        )
    except (TypeError, ValueError) as exc:
        raise CalibrationManifestError("v2 prior pack identity is invalid") from exc

    authorization = _exact_keys(
        configuration["v2_authorization_ref"],
        {"challenge", "authorization_id", "content_digest"},
        "v2 authorization ref",
    )
    if (
        authorization["challenge"] != challenge
        or type(authorization["authorization_id"]) is not str
    ):
        raise CalibrationManifestError("v2 authorization identity is not exact")
    _digest(authorization["content_digest"], "v2 authorization digest")
    try:
        authorization_ref = TestOnlyPriorAuthorizationReceiptRef(
            challenge_key,
            authorization["authorization_id"],
            authorization["content_digest"],
        )
    except (TypeError, ValueError) as exc:
        raise CalibrationManifestError("v2 authorization identity is invalid") from exc

    if type(drivers) is not list or len(drivers) != len(AgentProfile):
        raise CalibrationManifestError("calibration requires five driver identities")
    expected_drivers = [
        _driver_identity(fixture_driver_ref(item)) for item in AgentProfile
    ]
    if drivers != expected_drivers:
        raise CalibrationManifestError(
            "calibration driver identities are not canonical"
        )

    if type(arms) is not list or len(arms) != 4:
        raise CalibrationManifestError("calibration requires four arm identities")
    expected_arms = [
        _arm_identity(item)
        for item in build_nonqualifying_preflight_arm_artifacts(prior_pack_ref)
    ]
    if arms != expected_arms:
        raise CalibrationManifestError("calibration arm identities are not canonical")
    return (
        [item["profile"] for item in expected_drivers],
        [item["arm"] for item in expected_arms],
        prior_pack_ref,
        authorization_ref,
        scaffold_ref,
        practice_pack_ref,
    )


@lru_cache(maxsize=1)
def _current_design_identity_payload() -> bytes:
    """Build the exact current fixture graph identity without executing a run."""

    fixture = _load_fixture_builders()
    from carbon.gauntlet.agents import fixture_agent_drivers, fixture_strategy_domain
    from carbon.gauntlet.execution import (
        build_nonqualifying_preflight_arm_artifacts,
    )

    with tempfile.TemporaryDirectory(prefix="carbon-be4-identity-check-") as raw:
        working = Path(raw)
        domain = fixture._extended_resource_fixture(working / "domain")
        store, prior_provider, lookup = fixture._published_prior(
            working / "prior", domain
        )
        _service, scaffold_ref, practice_pack_ref = fixture._research_graph(
            working / "research", domain, store, prior_provider, lookup
        )
        strategy_domain = fixture_strategy_domain(
            domain.compile_fixture.catalog.to_ref(
                candidate_assembly=domain.compile_fixture.assembly
            )
        )
        return _canonical_bytes(
            {
                "configuration": _configuration(
                    domain=domain,
                    scaffold_ref=scaffold_ref,
                    practice_pack_ref=practice_pack_ref,
                    prior_lookup=lookup,
                    strategy_domain=strategy_domain,
                ),
                "drivers": [
                    _driver_identity(driver.ref) for driver in fixture_agent_drivers()
                ],
                "arms": [
                    _arm_identity(item)
                    for item in build_nonqualifying_preflight_arm_artifacts(
                        lookup.prior_pack_ref
                    )
                ],
            }
        )


def validate_manifest(manifest: object) -> dict[str, Any]:
    """Validate canonical raw evidence and reconstructible embedded identities."""

    root = _exact_keys(
        manifest,
        {
            "schema_version",
            "generator",
            "evidence_role",
            "authority_ceiling",
            "execution_boundary",
            "calibration_design_digest",
            "configuration",
            "drivers",
            "arms",
            "rows",
            "summary",
            "ordered_transcript_set_digest",
            "replay_stable_digest",
            "content_digest",
        },
        "calibration manifest",
    )
    if (
        root["schema_version"] != SCHEMA_VERSION
        or root["evidence_role"] != EVIDENCE_ROLE
        or root["authority_ceiling"] != AUTHORITY_CEILING
    ):
        raise CalibrationManifestError("calibration manifest identity is not exact")
    generator = _exact_keys(root["generator"], {"id", "version"}, "generator")
    if generator != {"id": GENERATOR_ID, "version": GENERATOR_VERSION}:
        raise CalibrationManifestError("calibration generator identity is not exact")
    boundary = _exact_keys(
        root["execution_boundary"],
        {
            "preflight_only_calls",
            "practice_calls",
            "official_submission_or_result_calls",
            "attack_campaign_calls",
            "qualifying_gauntlet_calls",
        },
        "execution boundary",
    )
    if any(
        type(boundary[key]) is not int or boundary[key] != 0
        for key in (
            "practice_calls",
            "official_submission_or_result_calls",
            "attack_campaign_calls",
            "qualifying_gauntlet_calls",
        )
    ):
        raise CalibrationManifestError("manifest crosses its preflight-only boundary")

    config = _exact_keys(
        root["configuration"],
        {
            "fixture_graph_source",
            "blocks_per_profile",
            "arm_count",
            "calibration_budget",
            "challenge",
            "candidate_assembly_ref",
            "parameter_catalog_ref",
            "resource_policy_ref",
            "strategy_domain_digest",
            "scaffold_ref",
            "practice_pack_ref",
            "v2_prior_pack_ref",
            "v2_authorization_ref",
        },
        "calibration configuration",
    )
    if config["blocks_per_profile"] != BLOCKS_PER_PROFILE or config["arm_count"] != 4:
        raise CalibrationManifestError("calibration matrix dimensions are not exact")
    _digest(config["strategy_domain_digest"], "strategy domain digest")
    _digest(root["calibration_design_digest"], "calibration design digest")

    (
        profiles,
        arms,
        prior_pack_ref,
        authorization_ref,
        scaffold_ref,
        practice_pack_ref,
    ) = _validate_current_design_identities(
        configuration=config,
        drivers=root["drivers"],
        arms=root["arms"],
    )
    if tuple(profiles) != _EXPECTED_PROFILES or tuple(arms) != _EXPECTED_ARMS:
        raise CalibrationManifestError("driver or arm identities are not exact")
    design_content = {
        "configuration": root["configuration"],
        "drivers": root["drivers"],
        "arms": root["arms"],
    }
    if _canonical_bytes(design_content) != _current_design_identity_payload():
        raise CalibrationManifestError(
            "calibration design identities do not match the current fixture graph"
        )
    if root["calibration_design_digest"] != _domain_digest(
        _DESIGN_DOMAIN, design_content
    ):
        raise CalibrationManifestError("calibration design digest is inconsistent")

    from carbon.gauntlet.agents import fixture_driver_ref
    from carbon.gauntlet.execution import (
        build_nonqualifying_four_arm_block,
        build_nonqualifying_preflight_arm_artifacts,
    )
    from carbon.gauntlet.model import AgentProfile, MatchedBudget

    preflight_artifacts = build_nonqualifying_preflight_arm_artifacts(prior_pack_ref)
    expected_plans = {}
    for profile in AgentProfile:
        for replicate in range(BLOCKS_PER_PROFILE):
            block_id = f"calibration-{profile.value.lower()}-{replicate + 1:02d}"
            block = build_nonqualifying_four_arm_block(
                design_digest=root["calibration_design_digest"],
                block_id=block_id,
                profile=profile,
                replicate=replicate,
                driver_ref=fixture_driver_ref(profile),
                artifacts=preflight_artifacts,
                budget=MatchedBudget(
                    profile,
                    CALIBRATION_WALL_CEILING_SECONDS,
                    CALIBRATION_COMPUTE_CEILING,
                    CALIBRATION_ATTEMPT_LIMIT,
                ),
                fixture_resource_ceiling=CALIBRATION_FIXTURE_RESOURCE_CEILING,
                scaffold_ref=scaffold_ref,
                practice_pack_ref=practice_pack_ref,
                v2_prior_pack_ref=prior_pack_ref,
                v2_authorization_ref=authorization_ref,
            )
            expected_plans.update(
                {
                    (profile.value, replicate, run.identity.arm.value): run
                    for run in block.runs
                }
            )

    rows = root["rows"]
    expected_count = 5 * BLOCKS_PER_PROFILE * 4
    if type(rows) is not list or len(rows) != expected_count:
        raise CalibrationManifestError("calibration does not contain 500 raw rows")
    if boundary["preflight_only_calls"] != len(rows):
        raise CalibrationManifestError("preflight call count does not match raw rows")
    expected_order = [
        (profile, replicate, arm)
        for profile in profiles
        for replicate in range(BLOCKS_PER_PROFILE)
        for arm in arms
    ]
    seen: list[tuple[str, int, str]] = []
    failed_blocks: set[tuple[str, str]] = set()
    per_profile: dict[str, dict[str, list[float]]] = {
        profile: {"wall": [], "compute": [], "fixture": []} for profile in profiles
    }
    for row in rows:
        raw = _exact_keys(
            row,
            {
                "row_id",
                "profile",
                "arm",
                "block_id",
                "replicate",
                "run_plan_slot_digest",
                "rng_stream_digest",
                "wall_seconds",
                "normalized_compute",
                "fixture_resources",
                "proposal_count",
                "first_preflight_executable_attempt",
                "service_reply_count",
                "preflight_transcript_digest",
                "infrastructure_failed",
                "failure_type",
            },
            "raw calibration row",
        )
        if (
            type(raw["profile"]) is not str
            or type(raw["arm"]) is not str
            or type(raw["replicate"]) is not int
            or type(raw["block_id"]) is not str
            or type(raw["row_id"]) is not str
            or type(raw["infrastructure_failed"]) is not bool
        ):
            raise CalibrationManifestError("raw calibration identity is not exact")
        expected_block = (
            f"calibration-{raw['profile'].lower()}-{raw['replicate'] + 1:02d}"
        )
        expected_row_id = f"{raw['profile']}:{raw['replicate']}:{raw['arm']}"
        if raw["block_id"] != expected_block or raw["row_id"] != expected_row_id:
            raise CalibrationManifestError(
                "raw calibration row identity is inconsistent"
            )
        seen.append((raw["profile"], raw["replicate"], raw["arm"]))
        _digest(raw["run_plan_slot_digest"], "run plan slot digest")
        _digest(raw["rng_stream_digest"], "RNG stream digest")
        try:
            expected_plan = expected_plans[
                (raw["profile"], raw["replicate"], raw["arm"])
            ]
        except KeyError as exc:
            raise CalibrationManifestError(
                "raw calibration plan identity is outside the frozen matrix"
            ) from exc
        if (
            raw["run_plan_slot_digest"] != expected_plan.final_submission_slot_digest
            or raw["rng_stream_digest"] != expected_plan.rng_stream_digest
        ):
            raise CalibrationManifestError(
                "raw calibration plan digest is inconsistent"
            )
        wall = _finite_nonnegative(raw["wall_seconds"], "wall observation")
        _validate_compute(raw["normalized_compute"])
        resources = _exact_keys(
            raw["fixture_resources"],
            {"dimension_id", "unit", "total_quantity", "candidate_quantities"},
            "fixture resource observation",
        )
        if (
            resources["dimension_id"] != "abstract_units"
            or resources["unit"] != "fixture_units"
            or type(resources["candidate_quantities"]) is not list
        ):
            raise CalibrationManifestError("fixture resource identity is not exact")
        quantities = []
        for candidate in resources["candidate_quantities"]:
            item = _exact_keys(
                candidate,
                {"attempt", "surface_id", "quantity"},
                "candidate fixture quantity",
            )
            if type(item["attempt"]) is not int or type(item["surface_id"]) is not str:
                raise CalibrationManifestError("candidate resource identity is invalid")
            quantities.append(_finite_nonnegative(item["quantity"], "fixture quantity"))
        total_quantity = _finite_nonnegative(
            resources["total_quantity"], "total fixture quantity"
        )
        if not math.isclose(
            total_quantity, math.fsum(quantities), rel_tol=0.0, abs_tol=0.0
        ):
            raise CalibrationManifestError("fixture resource total is inconsistent")
        if (
            type(raw["proposal_count"]) is not int
            or not 0 <= raw["proposal_count"] <= CALIBRATION_ATTEMPT_LIMIT
            or raw["proposal_count"] != len(quantities)
        ):
            raise CalibrationManifestError("proposal and resource counts disagree")
        compute_total = raw["normalized_compute"]["total_work_units"]
        per_profile[raw["profile"]]["wall"].append(wall)
        per_profile[raw["profile"]]["compute"].append(float(compute_total))
        per_profile[raw["profile"]]["fixture"].append(total_quantity)
        if raw["infrastructure_failed"]:
            failed_blocks.add((raw["profile"], raw["block_id"]))
            if (
                raw["failure_type"] not in _INFRASTRUCTURE_FAILURE_TYPES
                or raw["preflight_transcript_digest"] is not None
                or raw["proposal_count"] != 0
                or raw["first_preflight_executable_attempt"] is not None
                or type(raw["service_reply_count"]) is not int
                or raw["service_reply_count"] != 0
                or quantities
                or total_quantity != 0.0
            ):
                raise CalibrationManifestError("failed preflight row is inconsistent")
        else:
            if raw["failure_type"] is not None:
                raise CalibrationManifestError("successful preflight records a failure")
            _digest(raw["preflight_transcript_digest"], "preflight transcript digest")
            if (
                raw["proposal_count"] < 1
                or type(raw["service_reply_count"]) is not int
                or raw["service_reply_count"]
                != 3
                + (1 if raw["arm"] == "V2_TEST_ONLY_PRIOR" else 0)
                + 3 * raw["proposal_count"]
                or type(raw["first_preflight_executable_attempt"]) is not int
                or raw["first_preflight_executable_attempt"]
                != min(item["attempt"] for item in resources["candidate_quantities"])
            ):
                raise CalibrationManifestError("successful preflight row is incomplete")
    if seen != expected_order:
        raise CalibrationManifestError(
            "raw calibration rows are not in canonical order"
        )

    summary = _exact_keys(
        root["summary"],
        {
            "complete_block_count",
            "failed_block_count",
            "block_infrastructure_failure_rate",
            "block_infrastructure_failure_rate_ceiling",
            "block_infrastructure_failure_rate_within_ceiling",
            "profiles",
        },
        "calibration summary",
    )
    if summary["complete_block_count"] != 125 or summary["failed_block_count"] != len(
        failed_blocks
    ):
        raise CalibrationManifestError("calibration block summary is inconsistent")
    expected_rate = len(failed_blocks) / 125
    if summary["block_infrastructure_failure_rate"] != expected_rate:
        raise CalibrationManifestError("calibration failure rate is inconsistent")
    if summary["block_infrastructure_failure_rate_ceiling"] != 0.05:
        raise CalibrationManifestError("calibration failure ceiling is not exact")
    if summary["block_infrastructure_failure_rate_within_ceiling"] is not (
        expected_rate <= 0.05
    ):
        raise CalibrationManifestError("calibration failure decision is inconsistent")
    if type(summary["profiles"]) is not list or len(summary["profiles"]) != 5:
        raise CalibrationManifestError("calibration profile summary is incomplete")
    for profile, item in zip(profiles, summary["profiles"], strict=True):
        value = _exact_keys(
            item,
            {
                "profile",
                "sample_block_count",
                "wall_time_p99_seconds",
                "normalized_compute_p99",
                "proposed_wall_time_cap_seconds",
                "proposed_normalized_compute_cap",
                "fixture_units_p99",
            },
            "profile calibration summary",
        )
        observations = per_profile[profile]
        wall_p99 = _nearest_rank_p99(observations["wall"])
        compute_p99 = int(_nearest_rank_p99(observations["compute"]))
        fixture_p99 = _nearest_rank_p99(observations["fixture"])
        expected = {
            "profile": profile,
            "sample_block_count": 25,
            "wall_time_p99_seconds": wall_p99,
            "normalized_compute_p99": compute_p99,
            "proposed_wall_time_cap_seconds": math.ceil(1.25 * wall_p99),
            "proposed_normalized_compute_cap": (5 * compute_p99 + 3) // 4,
            "fixture_units_p99": fixture_p99,
        }
        if value != expected:
            raise CalibrationManifestError(
                "profile calibration summary is inconsistent"
            )

    if root["ordered_transcript_set_digest"] != ordered_transcript_set_digest(root):
        raise CalibrationManifestError("ordered transcript-set digest is inconsistent")
    if root["replay_stable_digest"] != replay_stable_digest(root):
        raise CalibrationManifestError("replay-stable digest is inconsistent")
    if root["content_digest"] != manifest_content_digest(root):
        raise CalibrationManifestError("raw manifest content digest is inconsistent")
    return root


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CalibrationManifestError(
            f"cannot load calibration manifest: {path}"
        ) from exc
    return validate_manifest(value)


def _load_fixture_builders() -> object:
    # This import is deliberately development-only.  Nothing under ``carbon``
    # imports a test fixture, and installed-wheel operation is unchanged.
    fixture_path = str(CPU_FIXTURE_ROOT)
    if fixture_path not in sys.path:
        sys.path.insert(0, fixture_path)
    import test_be4_execution_integration as fixture

    return fixture


def generate_manifest() -> dict[str, Any]:
    """Run exactly 500 preflight-only calls and return their raw evidence."""

    fixture = _load_fixture_builders()
    from carbon import research
    from carbon.fees import RequesterIdentity
    from carbon.gauntlet.agents import fixture_agent_drivers, fixture_strategy_domain
    from carbon.gauntlet.execution import (
        FIXTURE_RESOURCE_DIMENSION_ID,
        FIXTURE_RESOURCE_UNIT,
        CalibrationRunObservation,
        ResearchOperationFailure,
        build_nonqualifying_four_arm_block,
        build_nonqualifying_preflight_arm_artifacts,
        prepare_nonqualifying_preflight,
        summarize_nonqualifying_preflight_calibration,
    )
    from carbon.gauntlet.harness import AgentSession
    from carbon.gauntlet.meter import PolicyWorkMeter, WallTimeObservation
    from carbon.gauntlet.model import MatchedBudget

    with tempfile.TemporaryDirectory(prefix="carbon-be4-preflight-calibration-") as raw:
        working = Path(raw)
        domain = fixture._extended_resource_fixture(working / "domain")
        store, prior_provider, lookup = fixture._published_prior(
            working / "prior", domain
        )
        research_service, scaffold_ref, practice_pack_ref = fixture._research_graph(
            working / "research", domain, store, prior_provider, lookup
        )
        official, _lifecycle, _adapter = fixture._official_graph(
            working / "official", domain
        )
        strategy_domain = fixture_strategy_domain(
            domain.compile_fixture.catalog.to_ref(
                candidate_assembly=domain.compile_fixture.assembly
            )
        )
        drivers = fixture_agent_drivers()
        artifacts = build_nonqualifying_preflight_arm_artifacts(lookup.prior_pack_ref)
        configuration = _configuration(
            domain=domain,
            scaffold_ref=scaffold_ref,
            practice_pack_ref=practice_pack_ref,
            prior_lookup=lookup,
            strategy_domain=strategy_domain,
        )
        driver_identities = [_driver_identity(driver.ref) for driver in drivers]
        arm_identities = [_arm_identity(artifact) for artifact in artifacts]
        design_content = {
            "configuration": configuration,
            "drivers": driver_identities,
            "arms": arm_identities,
        }
        design_digest = _domain_digest(_DESIGN_DOMAIN, design_content)
        requester = RequesterIdentity("be4-preflight-calibration-v1")
        rows: list[dict[str, object]] = []
        observations: list[CalibrationRunObservation] = []

        for driver in drivers:
            budget = MatchedBudget(
                driver.profile,
                CALIBRATION_WALL_CEILING_SECONDS,
                CALIBRATION_COMPUTE_CEILING,
                CALIBRATION_ATTEMPT_LIMIT,
            )
            for replicate in range(BLOCKS_PER_PROFILE):
                block_id = (
                    f"calibration-{driver.profile.value.lower()}-{replicate + 1:02d}"
                )
                block = build_nonqualifying_four_arm_block(
                    design_digest=design_digest,
                    block_id=block_id,
                    profile=driver.profile,
                    replicate=replicate,
                    driver_ref=driver.ref,
                    artifacts=artifacts,
                    budget=budget,
                    fixture_resource_ceiling=(CALIBRATION_FIXTURE_RESOURCE_CEILING),
                    scaffold_ref=scaffold_ref,
                    practice_pack_ref=practice_pack_ref,
                    v2_prior_pack_ref=lookup.prior_pack_ref,
                    v2_authorization_ref=lookup.authorization.receipt_ref,
                )
                for plan in block.runs:
                    meter = PolicyWorkMeter()
                    session = AgentSession(research_service, official, requester, meter)
                    start_ns = time.perf_counter_ns()
                    prepared = None
                    failure: ResearchOperationFailure | None = None
                    try:
                        prepared = prepare_nonqualifying_preflight(
                            session=session,
                            plan=plan,
                            driver=driver,
                            strategy_domain=strategy_domain,
                            parameter_catalog=domain.compile_fixture.catalog,
                            candidate_assembly=domain.compile_fixture.assembly,
                            meter=meter,
                        )
                    except Exception as exc:
                        # Only the two existing explicitly infrastructure-classed
                        # B-07S outcomes become raw infrastructure-failure rows.
                        # Configuration/programming/protocol errors abort evidence
                        # generation instead of being mislabeled as infrastructure.
                        if not (
                            type(exc) is ResearchOperationFailure
                            and exc.code
                            in (
                                research.ResearchServiceErrorCode.PROVIDER_UNAVAILABLE,
                                research.ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE,
                            )
                        ):
                            raise
                        failure = exc
                    elapsed = (time.perf_counter_ns() - start_ns) / 1_000_000_000
                    receipt = meter.snapshot()
                    candidate_resources: list[dict[str, object]] = []
                    if prepared is not None:
                        for candidate in prepared.candidates:
                            if candidate.resource_inspection is None:
                                continue
                            quantity = math.fsum(
                                item.quantity
                                for item in candidate.resource_inspection.line_items
                            )
                            candidate_resources.append(
                                {
                                    "attempt": candidate.proposal.attempt,
                                    "surface_id": candidate.proposal.surface_id,
                                    "quantity": quantity,
                                }
                            )
                    total_fixture = math.fsum(
                        float(item["quantity"]) for item in candidate_resources
                    )
                    row_id = (
                        f"{driver.profile.value}:{replicate}:{plan.identity.arm.value}"
                    )
                    rows.append(
                        {
                            "row_id": row_id,
                            "profile": driver.profile.value,
                            "arm": plan.identity.arm.value,
                            "block_id": block_id,
                            "replicate": replicate,
                            "run_plan_slot_digest": plan.final_submission_slot_digest,
                            "rng_stream_digest": plan.rng_stream_digest,
                            "wall_seconds": elapsed,
                            "normalized_compute": _compute_identity(receipt),
                            "fixture_resources": {
                                "dimension_id": FIXTURE_RESOURCE_DIMENSION_ID,
                                "unit": FIXTURE_RESOURCE_UNIT,
                                "total_quantity": total_fixture,
                                "candidate_quantities": candidate_resources,
                            },
                            "proposal_count": (
                                0
                                if prepared is None
                                else len(prepared.proposal_batch.proposals)
                            ),
                            "first_preflight_executable_attempt": (
                                None
                                if prepared is None
                                else prepared.first_preflight_executable_attempt
                            ),
                            "service_reply_count": (
                                0
                                if prepared is None
                                else len(prepared.service_reply_digests)
                            ),
                            "preflight_transcript_digest": (
                                None if prepared is None else prepared.transcript_digest
                            ),
                            "infrastructure_failed": failure is not None,
                            "failure_type": (
                                None if failure is None else failure.code.value
                            ),
                        }
                    )
                    observations.append(
                        CalibrationRunObservation(
                            driver.profile,
                            plan.identity.arm,
                            block_id,
                            receipt,
                            WallTimeObservation(float(elapsed)),
                            (
                                research.ResourceObservation(
                                    FIXTURE_RESOURCE_DIMENSION_ID,
                                    total_fixture,
                                    FIXTURE_RESOURCE_UNIT,
                                ),
                            ),
                            failure is not None,
                        )
                    )

        report = summarize_nonqualifying_preflight_calibration(
            design_digest=design_digest, observations=tuple(observations)
        )
        summary = {
            "complete_block_count": report.complete_block_count,
            "failed_block_count": report.failed_block_count,
            "block_infrastructure_failure_rate": (
                report.block_infrastructure_failure_rate
            ),
            "block_infrastructure_failure_rate_ceiling": (
                report.block_infrastructure_failure_rate_ceiling
            ),
            "block_infrastructure_failure_rate_within_ceiling": (
                report.block_infrastructure_failure_rate_within_ceiling
            ),
            "profiles": [
                {
                    "profile": item.profile.value,
                    "sample_block_count": item.sample_count,
                    "wall_time_p99_seconds": item.wall_time_p99_seconds,
                    "normalized_compute_p99": item.normalized_compute_p99,
                    "proposed_wall_time_cap_seconds": (
                        item.proposed_wall_time_cap_seconds
                    ),
                    "proposed_normalized_compute_cap": (
                        item.proposed_normalized_compute_cap
                    ),
                    "fixture_units_p99": item.fixture_units_p99,
                }
                for item in report.profiles
            ],
        }
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "generator": {"id": GENERATOR_ID, "version": GENERATOR_VERSION},
            "evidence_role": EVIDENCE_ROLE,
            "authority_ceiling": report.authority_ceiling,
            "execution_boundary": {
                "preflight_only_calls": len(rows),
                "practice_calls": 0,
                "official_submission_or_result_calls": 0,
                "attack_campaign_calls": 0,
                "qualifying_gauntlet_calls": 0,
            },
            "calibration_design_digest": design_digest,
            "configuration": configuration,
            "drivers": driver_identities,
            "arms": arm_identities,
            "rows": rows,
            "summary": summary,
        }
        manifest["ordered_transcript_set_digest"] = ordered_transcript_set_digest(
            manifest
        )
        manifest["replay_stable_digest"] = replay_stable_digest(manifest)
        manifest["content_digest"] = manifest_content_digest(manifest)
        return validate_manifest(manifest)


def assert_replay_matches(reference: dict[str, Any], replay: dict[str, Any]) -> None:
    validate_manifest(reference)
    validate_manifest(replay)
    if (
        reference["ordered_transcript_set_digest"]
        != replay["ordered_transcript_set_digest"]
    ):
        raise CalibrationManifestError("replay changed the ordered transcript set")
    if reference["replay_stable_digest"] != replay["replay_stable_digest"]:
        raise CalibrationManifestError("replay changed deterministic evidence")


def _print_summary(manifest: dict[str, Any]) -> None:
    print(f"content_digest={manifest['content_digest']}")
    print(
        "ordered_transcript_set_digest=" f"{manifest['ordered_transcript_set_digest']}"
    )
    print(f"replay_stable_digest={manifest['replay_stable_digest']}")
    print(
        "blocks="
        f"{manifest['summary']['complete_block_count']} "
        f"rows={len(manifest['rows'])} "
        f"failed_blocks={manifest['summary']['failed_block_count']}"
    )
    for item in manifest["summary"]["profiles"]:
        print(
            f"{item['profile']}: "
            f"wall_p99={item['wall_time_p99_seconds']:.12f} "
            f"compute_p99={item['normalized_compute_p99']} "
            f"fixture_p99={item['fixture_units_p99']:.12g} "
            f"wall_cap={item['proposed_wall_time_cap_seconds']} "
            f"compute_cap={item['proposed_normalized_compute_cap']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--validate",
        type=Path,
        metavar="PATH",
        help="validate an existing raw calibration manifest without executing calls",
    )
    mode.add_argument(
        "--replay",
        type=Path,
        metavar="PATH",
        help="rerun 500 preflights and compare deterministic evidence to PATH",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="allow generation to replace an existing output file",
    )
    args = parser.parse_args(argv)

    if args.validate is not None:
        manifest = load_manifest(args.validate)
        _print_summary(manifest)
        return 0
    if args.replay is not None:
        reference = load_manifest(args.replay)
        replay = generate_manifest()
        assert_replay_matches(reference, replay)
        _print_summary(replay)
        return 0

    output = args.output.resolve()
    if output.exists() and not args.replace:
        parser.error(f"output exists; pass --replace to overwrite: {output}")
    manifest = generate_manifest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_manifest(manifest), encoding="utf-8")
    print(f"wrote {output}")
    _print_summary(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
