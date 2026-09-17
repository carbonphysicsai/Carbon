"""Resolve authentic, complete session evidence; never issue a chain intent."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from carbon.audit import (
    DevelopmentEvidenceLedger,
    DevelopmentRunStatus,
    ReceiptLifecycleState,
)
from carbon.construction import CompileAccepted
from carbon.development_session.contracts import build_contracts
from carbon.development_session.profile import (
    canonical,
    digest,
    profile_document,
)
from carbon.development_testnet.execution import load_source_handoff
from carbon.measurement_runtime.model import FrozenFieldArtifact
from carbon.measurement_runtime.protocol import (
    decode_measurement_request,
    decode_measurement_result,
)
from carbon.miner_mcp import MinerMcpJournal
from carbon.orchestration import OperationalDisposition
from carbon.orchestration.development_feedback import aggregate_development_feedback
from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
from carbon.reexecution.store import ReexecutionJournal
from carbon.reference_runtime.model import BurgersReferenceArtifact
from carbon.transport.store import ReceiptJournal


def read_json(path: Path, maximum=2 * 1024**2):
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.resolve() != path.absolute()
        or not 0 < path.stat().st_size <= maximum
    ):
        raise ValueError("bounded regular comparison artifact required")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate comparison field")
            result[key] = value
        return result

    return json.loads(path.read_bytes(), object_pairs_hook=pairs)


@dataclass(frozen=True)
class ResolvedSource:
    identity: dict
    bindings: dict
    manifest: dict
    cohorts: tuple
    strategy: dict
    feedback: dict
    dossier: dict
    trust: dict


def validate_reference_association(request, signed_c04_digest, payload):
    # C-04's trajectory artifact and C-05's role-tagged frozen field deliberately
    # have different digest domains. Bind both to the exact same retained bytes.
    c04 = BurgersReferenceArtifact(
        request.reference_request_digest, request.shape, payload
    )
    c05 = FrozenFieldArtifact(
        request.reference_request_digest, request.shape, payload, "REFERENCE_PRIMARY"
    )
    if (
        c04.artifact_digest != signed_c04_digest
        or c05.artifact_digest != request.reference_artifact_digest
    ):
        raise ValueError("signed reference artifact association differs")


def validate_active_association(receipt, account, auth, lifecycle):
    if (
        lifecycle is not ReceiptLifecycleState.ACTIVE
        or receipt.run_status is not DevelopmentRunStatus.COMPLETE_UNRESOLVED
        or account.disposition is not OperationalDisposition.COMPLETE_UNRESOLVED
        or receipt.receipt_digest != account.receipt_digest
        or receipt.receipt_id != account.receipt_id
        or receipt.binding.submission_id != account.submission_id
        or receipt.started_at_micros != account.started_at_micros
        or receipt.finished_at_micros != account.finished_at_micros
        or (auth.challenge_id, auth.challenge_version)
        != (receipt.binding.challenge_id, receipt.binding.challenge_version)
    ):
        raise ValueError("active complete authenticated DEVELOPMENT source required")
    for obj in (receipt, account):
        if any(
            getattr(obj, field) is not False
            for field in (
                "protected_execution_eligible",
                "score_eligible",
                "archive_acknowledged",
                "network_eligible",
                "reward_eligible",
            )
        ):
            raise ValueError("incompatible source eligibility")
    if account.official is not False:
        raise ValueError("official sources are not development comparisons")


def resolve_source(
    path: Path,
    *,
    retention_root: Path,
    quarantine_journal: Path,
    trusted: dict | None = None,
    reference_root: Path | None = None,
    research_profile: bool = False,
) -> ResolvedSource:
    document = read_json(path, 128 * 1024)
    trust = {
        key: document[key]
        for key in (
            "evidence_ledger",
            "transport_journal",
            "transport_context",
            "verification_keys",
        )
    }
    if trusted is not None and trust != trusted:
        raise ValueError("source differs from frozen trust roots")
    source = load_source_handoff(
        path, retention_root=retention_root, export_root=retention_root / "exports"
    )
    account = source.evidence.account
    signed, lifecycle = DevelopmentEvidenceLedger(
        source.evidence_ledger, source.verification_keys
    ).resolve(
        source.evidence.ledger_reference, verified_at_micros=account.finished_at_micros
    )
    receipt = signed.receipt
    auth = MinerMcpJournal(
        ReceiptJournal(source.transport_journal, source.transport_context)
    ).resolve_development_source(source.evidence.authenticated_request_receipt, account)
    validate_active_association(receipt, account, auth, lifecycle)
    states = ReexecutionJournal.source_states(
        quarantine_journal,
        account_digest=account.account_digest,
        receipt_digest=receipt.receipt_digest,
    )
    if any(state != "COMPARED" for state in states):
        raise ValueError(
            "C-10 quarantine or unresolved reexecution withholds comparison"
        )
    export = source.export_manifest.parent
    dossier = read_json(export / "dossier.json")
    manifest = read_json(export / "case-manifest.json")
    strategy = read_json(export / "strategy.json")
    active_profile = profile_document()
    contracts = build_contracts()
    resources = active_profile["budget"]
    if research_profile:
        from carbon.development_session.research_catalog import research_contracts
        from carbon.development_session.research_profile import (
            document as research_document,
        )

        active_profile = research_document()
        if read_json(export / "profile.json") != active_profile:
            raise ValueError("research profile differs from registered version")
        contracts = research_contracts()
        resources = active_profile["final_worker"]
    active_digest = digest(canonical(active_profile))
    compiled = contracts.compile(strategy)
    expected_steps = strategy.get("parameters", {}).get("steps")
    if research_profile and type(compiled) is CompileAccepted:
        from carbon.reconstruction.profile import compile_development_profile

        expected_steps = json.loads(
            compile_development_profile(compiled.construction_plan).train_config_json
        )["steps"]
    binding = receipt.binding
    worker = DevelopmentWorkerProfile(active_digest, digest(canonical(resources)))
    if (
        type(compiled) is not CompileAccepted
        or compiled.construction_plan.strategy_hash.value != binding.strategy_digest
        or compiled.construction_plan.to_ref().content_digest
        != binding.reconstruction_plan_digest
        or binding.resource_policy_digest != active_digest
        or binding.execution_policy_digest != worker.digest
        or binding.scoring_policy_digest != active_digest
        or digest(canonical(dossier)) != binding.dossier_digest
        or dossier["profile_digest"] != active_digest
        or digest(canonical(manifest)) != dossier["case_manifest_digest"]
        or dossier["strategy_digest"] != binding.strategy_digest
        or dossier["repeat_plan_digest"] != binding.repeat_plan_digest
        or manifest["worker_image"] != binding.worker_image_digest
        or dossier["training_runs"] != 3
        or dossier["training_steps"] != expected_steps * 3
    ):
        raise ValueError(
            "incompatible construction, resource or signed dossier identity"
        )
    members = {row["name"]: row for row in manifest["cases"]}
    if (
        set(members)
        != {
            f"{role}-{cell:02d}"
            for role in (
                ("eval", "stress") if research_profile else ("train", "eval", "stress")
            )
            for cell in range(12)
        }
        or len(manifest["cases"]) != (24 if research_profile else 36)
        or len({row["case_digest"] for row in members.values()})
        != (24 if research_profile else 36)
    ):
        raise ValueError("exact complete separated registered cohort required")
    if research_profile and (
        manifest.get("schema") != "carbon.autoresearch.final-cases.v1"
        or manifest.get("training_parents") != 72
        or manifest.get("training_archive_digest") != binding.training_data_commitment
    ):
        raise ValueError("research TRAIN/final association differs")
    rows = {
        (row["replica"], row["role"], row["case_digest"]): row
        for row in dossier["measurements"]
    }
    if len(rows) != 72 or len(dossier["measurements"]) != 72:
        raise ValueError("complete distinct signed measurement set required")
    expected_cases = {
        role: frozenset(
            row["case_digest"] for row in members.values() if row["role"] == role
        )
        for role in ("EVAL", "STRESS")
    }
    cohorts = []
    material = {}
    for role in ("EVAL", "STRESS"):
        pairs = []
        for replica in range(3):
            for cell in range(12):
                name = f"replica-{replica}-{role.lower()}-{cell:02d}-measurement.json"
                case = members[f"{role.lower()}-{cell:02d}"]
                row = rows[(replica, role, case["case_digest"])]
                result_doc = read_json(export / name)
                request = decode_measurement_request(
                    read_json(
                        retention_root
                        / "evaluations"
                        / account.submission_id
                        / name.replace("-measurement.json", "-measurement-request.json")
                    )
                )
                result = decode_measurement_result(result_doc, request)
                if (
                    request.case_digest != case["case_digest"]
                    or request.candidate_replica_id
                    != f"reconstruction-replica-{replica}"
                    or request.candidate_plan_digest
                    != binding.reconstruction_plan_digest
                    or request.request_digest != row["measurement_request_digest"]
                    or result.result_digest != row["measurement_result_digest"]
                    or request.measurement_contract_digest
                    != binding.measurement_contract_digest
                    or request.implementation_digest
                    != binding.measurement_implementation_digest
                    or request.measurement_environment_digest
                    != binding.measurement_environment_digest
                    or request.reference_policy_digest
                    != binding.reference_policy_digest
                ):
                    raise ValueError("measurement source/version association mismatch")
                if (
                    request.candidate_artifact_digest
                    != row["candidate_artifact_digest"]
                ):
                    raise ValueError("signed candidate artifact association differs")
                record = read_json(
                    retention_root / f"{role.lower()}-{cell:02d}-reference-result.json"
                )
                payload_path = Path(record["solution_path"])
                allowed_root = (
                    retention_root if reference_root is None else reference_root
                )
                if (
                    payload_path.resolve() != payload_path.absolute()
                    or not payload_path.is_relative_to(allowed_root)
                    or payload_path.is_symlink()
                    or not payload_path.is_file()
                    or payload_path.stat().st_size
                    != request.shape[0] * request.shape[1] * 8
                ):
                    raise ValueError("bounded trusted reference payload required")
                payload = payload_path.read_bytes()
                if digest(payload) != record["payload_digest"]:
                    raise ValueError("retained reference payload changed")
                validate_reference_association(
                    request, row["reference_artifact_digest"], payload
                )
                common = request.document()
                del common["candidate"]
                key = role + ":" + case["case_digest"]
                current = digest(canonical(common))
                if key in material and material[key] != current:
                    raise ValueError(
                        "replicas use different reference/normalization material"
                    )
                material[key] = current
                pairs.append((request, result))
        cohorts.append((role, tuple(pairs)))
    feedback = aggregate_development_feedback(
        tuple(cohorts), expected_cases=expected_cases
    )
    if digest(canonical(feedback)) != dossier["feedback_digest"]:
        raise ValueError("feedback differs from signed dossier")
    # Candidate/replica-specific commitments remain in the source identity;
    # only common material pins are compared for cohort compatibility.
    shared = (
        "challenge_id",
        "challenge_version",
        "generator_digest",
        "target_population_digest",
        "sampling_plan_digest",
        "training_data_commitment",
        "resource_policy_digest",
        "reference_policy_digest",
        "reference_implementation_digest",
        "reference_environment_digest",
        "measurement_contract_digest",
        "measurement_implementation_digest",
        "measurement_environment_digest",
        "scoring_policy_digest",
        "qualification_manifest_digest",
        "source_tree_digest",
        "worker_image_digest",
        "execution_policy_digest",
    )
    bindings = {key: getattr(binding, key) for key in shared}
    bindings["case_manifest_digest"] = dossier["case_manifest_digest"]
    bindings["measurement_material_digest"] = digest(canonical(material))
    identity = {
        "source_digest": digest(path.read_bytes()),
        "receipt_digest": receipt.receipt_digest,
        "account_digest": account.account_digest,
        "binding": asdict(binding),
        "authenticated_hotkey": auth.hotkey,
        "authenticated_uid": auth.uid,
        "lifecycle": lifecycle.value,
        "c10_states": list(states),
        "independent_reexecution_recorded": bool(states),
    }
    return ResolvedSource(
        identity, bindings, manifest, tuple(cohorts), strategy, feedback, dossier, trust
    )
