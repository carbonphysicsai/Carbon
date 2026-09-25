"""R1 on real sessions: build captures from session records and let compare_r1 decide.

Amendment 10 qualified the R1 comparison, as a DEVELOPMENT qualification, for four
GPU parts on the fixture Challenge `fixture_authoring 1.0`, bit-exact.
`carbon/reproducibility/development.py` implements it. This is what connects it to
real runs: it turns the session records `repeat_gpu.py` prints into
`NumericalRunCapture`s and hands same-part pairs to `compare_r1` with the qualified
procedure. Two pods of one part, each running the pinned session on its own, are
two simulated validators.

**Simulated validators, not validator_launch.** A pod cannot run the containers
`validator_launch` requires, so each "validator" is direct execution inside the
pinned image, with containment from the provider's runtime. Two such pods agreeing
under R1 is two independent executions agreeing, not two validators' orchestration
agreeing.

Order of checks, and each refuses rather than guesses:

1. `compare_units` first: named units, readable and matching driver builds (or a
   deviation naming exactly the builds seen), and one condition. R1 never runs on a
   comparison the driver check refused.
2. The device name NVML reported must map to a qualified part. The map starts
   **empty** and is filled only from names read on real devices, so an unrecorded
   name - or a part the ruling did not name, whatever its generation - has no part
   and no capture.
3. Every run in a session must have produced identical predictions, or the session
   has no single output to capture.

What R0 compares, and where each field comes from. **From the session:** the plan,
the candidate artifact (the plan bytes), the training archive (as the generator
output), the randomness, the pinned environment, and the backend profile of the
part. **Declared not applicable:** the fixture study has no physical system spec,
output contract, target distribution, sampling plan, uncertainty, reconstruction or
reference policy, scoring, or receipt construction. Those fields carry fixed
digests of a statement saying so, identical on both sides, so they neither invent a
policy nor let a difference hide there. Host facts - driver build, CPU ISA - are
not identity: the driver is governed by the check in step 1, and the rest are
recorded without being compared.

    python r1_capture.py <session.json>... [--deviation <deviation.json>]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    from scripts.dev.gpu_determinism_study import compare_units
except ImportError:  # run as a script without the repository on the path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import compare_units

from carbon import reproducibility
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
)
from carbon.construction import ResolvedConstructionPlanRef
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.measurement import ReconstructionEvidencePolicyRef, UncertaintyPolicyRef
from carbon.registry import ChallengeKey

RecordError = compare_units.RecordError
Kind = reproducibility.ReproducibilityRefKind

#: NVML device name -> qualified part. Filled only from names read on real devices
#: of each part, so a part whose name has not been read has no capture. Each entry
#: names the evidence it was read from.
#:
#: A40 and RTX PRO 6000 SE are qualified but absent: neither was in stock on a
#: CUDA 13 host when these were read, and their names are not guessed.
PART_BY_NVML_NAME: dict[str, str] = {
    # docs/development/evidence/r1-simulated-validators-2026-09-24/l4-v{1,2}
    "NVIDIA L4": "L4",
    # docs/development/evidence/r1-simulated-validators-2026-09-24/h100-v{1,2}
    "NVIDIA H100 80GB HBM3": "H100 SXM",
}

#: The numerics fields that define the pinned execution environment. Host facts are
#: deliberately absent; see the module docstring.
ENVIRONMENT_FIELDS = (
    "schema",
    "backend",
    "xla_flags",
    "default_matmul_precision",
    "nvidia_tf32_override",
    "cublas_workspace_config",
    "cuda_version",
    "cudnn_version",
)


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tagged(hexdigest: str) -> str:
    return "sha256:" + hexdigest


def _not_applicable(challenge: ChallengeKey, field: str) -> str:
    return _sha(
        f"carbon.study.r1.not-applicable:{field}:"
        f"{challenge.challenge_id}/{challenge.version}"
    )


def part_for(record: dict, label: str) -> str:
    name = (record.get("device_identity") or {}).get("name")
    part = PART_BY_NVML_NAME.get(name) if isinstance(name, str) else None
    if part is None:
        raise RecordError(
            f"{label}: device {name!r} is not a recorded name of a part Amendment 10 "
            "qualifies, so it has no backend profile and no capture"
        )
    return part


def predictions(record: dict, label: str) -> tuple[float, ...]:
    runs = record.get("runs") or []
    series = [run.get("predictions") for run in runs]
    if not series or any(
        not isinstance(values, list) or not values for values in series
    ):
        raise RecordError(
            f"{label}: no recorded predictions; run with STUDY_PREDICTIONS=1"
        )
    if any(values != series[0] for values in series[1:]):
        raise RecordError(
            f"{label}: runs within the session produced different predictions, so "
            "the session has no single output to capture"
        )
    return tuple(float.fromhex(value) for value in series[0])


def capture(
    record: dict, *, source: str = "record"
) -> reproducibility.NumericalRunCapture:
    """One session as an R1 capture. Refuses anything it cannot establish."""
    label = record.get("label") or source
    compare_units.UnitSession.read(record, source=source)
    part = part_for(record, label)
    values = predictions(record, label)
    materials = record.get("materials") or {}
    plan = materials.get("plan_ref") or {}
    try:
        challenge = ChallengeKey(plan["challenge_id"], plan["challenge_version"])
        plan_sha = materials["plan_sha256"]
        train_sha = materials["train_sha256"]
        randomness_sha = materials["randomness_sha256"]
    except (KeyError, TypeError, ValueError):
        raise RecordError(f"{label}: the record does not name its materials") from None

    def ref(kind, object_id: str, digest: str):
        return reproducibility.ReproducibilityRef(
            challenge, kind, object_id, "1.0", digest
        )

    def declared(ref_type, field: str, *extra):
        return ref_type(
            challenge,
            f"not-applicable-{field.replace('_', '-')}",
            "1.0",
            AUTHORING_SCHEMA_VERSION,
            CANONICALIZATION_PROFILE,
            _not_applicable(challenge, field),
            *extra,
        )

    numerics = record.get("numerics") or {}
    environment = {name: numerics.get(name) for name in ENVIRONMENT_FIELDS}
    environment["software"] = record.get("software")
    try:
        return _capture(
            challenge,
            plan,
            plan_sha,
            train_sha,
            randomness_sha,
            part,
            environment,
            values,
            ref,
            declared,
        )
    except ValueError as error:
        # Names the field, never the value: this branch sees whatever the record
        # held, and the record is not trusted to be what it claims.
        where = getattr(error, "path", None) or type(error).__name__
        raise RecordError(
            f"{label}: the record does not form a valid R1 identity at {where}"
        ) from None


def _capture(
    challenge,
    plan,
    plan_sha,
    train_sha,
    randomness_sha,
    part,
    environment,
    values,
    ref,
    declared,
):
    identity = reproducibility.ExactIdentityManifest(
        challenge_key=challenge,
        candidate_artifact_ref=ref(
            Kind.CANDIDATE_ARTIFACT, "study-plan", _tagged(plan_sha)
        ),
        physical_system_ref=declared(PhysicalSystemSpecRef, "physical_system"),
        candidate_output_contract_ref=declared(
            CandidateOutputContractRef, "candidate_output_contract"
        ),
        target_distribution_ref=declared(
            InstanceDistributionContractRef,
            "target_distribution",
            "TARGET_WORKLOAD_P",
        ),
        sampling_plan_ref=declared(SamplingPlanRef, "sampling_plan"),
        resolved_plan_ref=ResolvedConstructionPlanRef(
            challenge,
            plan.get("schema_version", "1.0"),
            plan.get("canonicalization_profile", ""),
            plan.get("digest", ""),
        ),
        uncertainty_policy_ref=UncertaintyPolicyRef(
            challenge, _not_applicable(challenge, "uncertainty_policy")
        ),
        reconstruction_policy_ref=ReconstructionEvidencePolicyRef(
            challenge, _not_applicable(challenge, "reconstruction_policy")
        ),
        reference_policy_ref=ReferencePolicyRef(
            challenge, _not_applicable(challenge, "reference_policy")
        ),
        generator_ref=ref(Kind.GENERATOR, "study-training-archive", _tagged(train_sha)),
        scoring_ref=ref(
            Kind.SCORING,
            "not-applicable-scoring",
            _not_applicable(challenge, "scoring"),
        ),
        backend_profile_ref=reproducibility.development_backend_profile_ref(part),
        backend_support=reproducibility.development_backend_support(
            reproducibility.development_backend_profile_ref(part)
        ),
        environment_ref=ref(
            Kind.ENVIRONMENT,
            "study-pinned-environment",
            _sha(json.dumps(environment, sort_keys=True, separators=(",", ":"))),
        ),
        execution_limits_ref=ref(
            Kind.EXECUTION_LIMITS, "study-plan-limits", _tagged(plan_sha)
        ),
        seed_role_structure_ref=ref(
            Kind.SEED_ROLE_STRUCTURE, "study-randomness", _tagged(randomness_sha)
        ),
        receipt_construction_ref=ref(
            Kind.RECEIPT_CONSTRUCTION,
            "not-applicable-receipt-construction",
            _not_applicable(challenge, "receipt_construction"),
        ),
        hardware_role_ref=ref(
            Kind.HARDWARE_ROLE,
            "simulated-validator",
            _sha("carbon.study.r1.hardware-role:simulated-validator"),
        ),
        fixture_origin=True,
    )
    outputs = tuple(
        reproducibility.NumericalDatum(
            ref(
                Kind.NUMERICAL_OUTPUT,
                f"prediction-{index:06d}",
                _sha(f"{plan.get('digest')}:prediction:{index}"),
            ),
            value,
        )
        for index, value in enumerate(values)
    )
    return reproducibility.NumericalRunCapture(identity, outputs)


def compare(records: list[tuple[str, dict]], deviation=None) -> dict:
    """The unit comparison, then R1 on every cross-unit pair of sessions."""
    sessions = [compare_units.UnitSession.read(r, source=s) for s, r in records]
    result = compare_units.compare(sessions, deviation)
    if result["outcome"] not in ("AGREE", "DISAGREE"):
        result["r1"] = None
        return result
    captured = [
        (session, capture(record, source=source), part_for(record, session.label))
        for session, (source, record) in zip(sessions, records, strict=True)
    ]
    pairs = []
    for i, (a, first, part) in enumerate(captured):
        for b, second, _ in captured[i + 1 :]:
            if a.device_uuid == b.device_uuid:
                continue
            r1 = reproducibility.compare_r1(
                first, second, reproducibility.development_procedure(part)
            )
            pairs.append(
                {
                    "first": a.label,
                    "second": b.label,
                    "outcome": r1.outcome.value,
                    "r0_mismatched_fields": list(r1.r0_result.mismatched_fields),
                    "max_absolute_delta": max(
                        (d.absolute_delta for d in r1.deltas), default=None
                    ),
                }
            )
    outcomes = {pair["outcome"] for pair in pairs}
    result["r1"] = {
        "qualification": "DEVELOPMENT - Amendment 10, owner as deputy for the MQ-008 holder",
        "execution": "simulated validators: direct execution in the pinned image; not validator_launch",
        "pairs": pairs,
        "outcome": outcomes.pop() if len(outcomes) == 1 else "MIXED",
    }
    return result


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    deviation = None
    if "--deviation" in args:
        at = args.index("--deviation")
        try:
            deviation = compare_units.DriverDeviation.read(
                json.loads(Path(args[at + 1]).read_text())
            )
        except (IndexError, OSError, ValueError, RecordError) as error:
            print(f"deviation: {error}", file=sys.stderr)
            return 2
        del args[at : at + 2]
    if len(args) < 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    try:
        records = [(name, json.loads(Path(name).read_text())) for name in args]
        result = compare(records, deviation)
    except (OSError, ValueError) as error:
        print(f"not a readable session record: {error}", file=sys.stderr)
        return 2
    except RecordError as error:
        print(f"refusing: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result.get("r1") and result["r1"]["outcome"] == "REPRODUCIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
