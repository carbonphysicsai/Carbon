#!/usr/bin/env python3
"""Generate retained public DEVELOPMENT C-05 bundles from source-owned code."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)
from carbon.measurement_runtime.model import (
    MEASUREMENT_IDS,
    PHYSICS_IDS,
    BurgersMeasurementResult,
    FrozenFieldArtifact,
    MeasurementDisposition,
    build_measurement_request,
    execute_measurement,
)
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    execute_reference,
    runtime_environment_digest,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "8dbee54dcd5bdea3a76b22812955e31fbe95e8da"


def canonical(v):
    return json.dumps(
        v, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


def digest_text(v):
    return "sha256:" + hashlib.sha256(v.encode("ascii")).hexdigest()


def fake(c):
    return "sha256:" + c * 64


def source_result(disposition):
    context = MockContext(
        MockEntropy(b"m" * 32),
        SeedPin(
            ChallengeKey("burgers-dynamics-v1", "1.0"),
            "1.0",
            fake("1"),
            "1.0",
            fake("2"),
            EvaluationBinding(b"q" * 32),
        ),
    )
    case = generate_development_case(
        context, BurgersCaseCoordinates(PublicDevelopmentRole.EVAL, 2, 0)
    )
    rr = build_reference_request(
        case,
        BurgersReferenceRole.CANDIDATE_PRIMARY,
        output_points=64,
        requested_times=tuple(
            float(f * case.characteristic_time) for f in (0, 0.1, 0.25, 0.5, 1, 2, 4)
        ),
        environment_digest=runtime_environment_digest(),
    )
    run = execute_reference(rr)
    assert run.artifact is not None
    values = run.artifact.array()
    points = np.asarray(rr.spatial_points)
    candidate = FrozenFieldArtifact(
        fake("a"),
        values.shape,
        np.asarray(values + 1e-4 * np.sin(points)[None, :], dtype="<f8").tobytes(
            order="C"
        ),
        "CANDIDATE_PREDICTION",
    )
    request = build_measurement_request(
        case,
        rr,
        run.artifact,
        candidate,
        candidate_source_digest=fake("b"),
        candidate_environment_digest=fake("c"),
        candidate_plan_digest=fake("d"),
        candidate_replica_id="reconstruction-replica-0",
    )
    reference = FrozenFieldArtifact(
        rr.request_digest, run.artifact.shape, run.artifact.payload, "REFERENCE_PRIMARY"
    )
    complete = execute_measurement(request, candidate, reference)
    if disposition is MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY:
        return request, complete
    return request, BurgersMeasurementResult(
        request.request_digest,
        disposition,
        (),
        (),
        (("reason", "retained public typed non-complete fixture"),),
    )


CLASSIFICATION = [
    (
        "PEAK_MISSED",
        "OBSERVABLE_WITH_CURRENT_C05_RESULT",
        "Compression and dissipation errors are present; no preference rank is inferred.",
    ),
    (
        "OVERSMOOTHED",
        "OBSERVABLE_WITH_CURRENT_C05_RESULT",
        "Raw field, compression and dissipation effects are visible; no tolerance is qualified.",
    ),
    (
        "MANDATORY_FAILURE",
        "OBSERVABLE_WITH_CURRENT_C05_RESULT",
        "Six raw physics defects are present, while every decision remains unresolved.",
    ),
    (
        "NONFINITE_OR_WITHHELD",
        "REQUIRES_DEDICATED_PUBLIC_FIXTURE",
        "This complete fixture is finite; source validation rejects nonfinite artifacts before measurement.",
    ),
    (
        "DROPPED_WORK",
        "REQUIRES_SCOREPACK_DIAGNOSTIC_CONTRACT",
        "C-05 has no population denominator, censoring, or dropped-work score contract.",
    ),
    (
        "UNIT_OR_FLOOR",
        "REQUIRES_QUALIFIED_FLOOR_OR_UNCERTAINTY",
        "C-05 retains raw values and normalization scales but supplies no qualified floor.",
    ),
    (
        "BELOW_UNCERTAINTY",
        "REQUIRES_QUALIFIED_FLOOR_OR_UNCERTAINTY",
        "Every uncertainty field is null, so below-uncertainty behavior cannot be decided.",
    ),
    (
        "PERSISTENCE_OR_MEMORIZATION",
        "REQUIRES_SCOREPACK_DIAGNOSTIC_CONTRACT",
        "C-05 measures one bound field artifact and defines no persistence or memorization checks.",
    ),
]


def bundle(binding, fixture_id, disposition):
    request, result = source_result(disposition)
    request_json, result_json = canonical(request.document()), canonical(
        result.document()
    )
    source = {
        "fixture_id": fixture_id,
        "repository": "carbonphysicsai/Carbon",
        "source_revision": SOURCE_REVISION,
        "implementation": "carbon.measurement_runtime.model.execute_measurement",
        "request_schema": "carbon.c05.burgers-measurement.v1",
        "result_schema": "carbon.c05.burgers-measurement-result.v1",
        "request_digest": digest_text(request_json),
        "result_digest": digest_text(result_json),
    }
    value = {
        "schema_version": "carbon.goal-workbench.c05-evidence-bundle.v1",
        "association": binding,
        "source": source,
        "measurement_request_json": request_json,
        "measurement_result_json": result_json,
        "behavior_classification": [
            {"example": e, "classification": c, "reason": r}
            for e, c, r in CLASSIFICATION
        ],
        "limitations": [
            "Public DEVELOPMENT fixture only; no protected or customer data.",
            "Scientific limits, uncertainty policy, score input, qualification, approval and launch authority are absent.",
            "One public EVAL case and deterministic test-created candidate perturbation are not population evidence.",
            "Import replays retained fixture bytes through a registry-pinned manual workbench association; the association is inspectable but is not operator authentication or proof of honest execution.",
        ],
        "authority": {
            "development_only": True,
            "scientifically_qualified": False,
            "protected_execution_eligible": False,
            "score_eligible": False,
            "approved": False,
            "launch_authorized": False,
        },
    }
    doc = request.document()
    index = {
        "fixture_id": fixture_id,
        "request_digest": source["request_digest"],
        "result_digest": source["result_digest"],
        "case_digest": doc["case_digest"],
        "candidate_artifact_digest": doc["candidate"]["artifact_digest"],
        "candidate_binding_digest": doc["candidate"]["binding_digest"],
        "candidate_source_digest": doc["candidate"]["source_digest"],
        "candidate_environment_digest": doc["candidate"]["environment_digest"],
        "candidate_plan_digest": doc["candidate"]["plan_digest"],
        "candidate_replica_id": doc["candidate"]["replica_id"],
        "measurement_contract_digest": doc["measurement"]["contract_digest"],
        "measurement_environment_digest": doc["measurement"]["environment_digest"],
        "measurement_implementation_digest": doc["measurement"][
            "implementation_digest"
        ],
        "source_revision": SOURCE_REVISION,
        "association": binding,
    }
    return value, index


def main():
    binding = json.loads((ROOT / "data/c05_fixture_binding_v1.json").read_text())
    fixtures = []
    for filename, fixture_id, disposition in (
        (
            "c05_public_development_evidence_v1.json",
            "C05-PUBLIC-EVAL2-PERTURBED",
            MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY,
        ),
        (
            "c05_public_development_noncomplete_v1.json",
            "C05-PUBLIC-EVAL2-NUMERICAL-FAILURE",
            MeasurementDisposition.NUMERICAL_FAILURE,
        ),
    ):
        value, item = bundle(binding, fixture_id, disposition)
        (ROOT / "data" / filename).write_text(json.dumps(value, indent=2) + "\n")
        fixtures.append(item)
    index = {
        "schema_version": "carbon.goal-workbench.c05-fixture-index.v1",
        "source_interface": {
            "request_schema": "carbon.c05.burgers-measurement.v1",
            "result_schema": "carbon.c05.burgers-measurement-result.v1",
            "measurement_ids": list(MEASUREMENT_IDS),
            "physics_ids": list(PHYSICS_IDS),
        },
        "fixtures": fixtures,
        "authority": "PUBLIC_DEVELOPMENT_BYTES_ONLY_NO_QUALIFICATION",
    }
    (ROOT / "data/c05_fixture_index_v1.json").write_text(
        json.dumps(index, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "platform": platform.platform(),
                "fixtures": len(fixtures),
            }
        )
    )


if __name__ == "__main__":
    main()
