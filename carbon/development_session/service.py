"""Supervised local connection to C-08; no public listener or model filesystem."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from carbon import audit, mcp
from carbon.chain import ChainContext
from carbon.chain.auth import BittensorHotkeyVerifier, BittensorMessageSigner
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
from carbon.chain.sdk import BittensorReader
from carbon.construction import CompileAccepted
from carbon.execution import DurableExecutionQueue, ExecutionScope
from carbon.fees import (
    ExecutionEnvironmentPin,
    FeePolicyKey,
    FixtureSubmissionPolicy,
    SubmissionService,
)
from carbon.miner_mcp import AuthenticatedMinerMcpService, MinerMcpJournal
from carbon.orchestration import DevelopmentEvaluationOrchestrator
from carbon.registry import (
    ArtifactBinding,
    ChallengeRecord,
    ChallengeRegistry,
    QualificationManifest,
)
from carbon.registry.development import DevelopmentServiceAdmission
from carbon.transport.gateway import AuthenticatedGateway, requester_for_receipt
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal

from .budget import SessionBudget
from .contracts import build_contracts, strategy_limits
from .data import context, write_once
from .profile import CHALLENGE, canonical, digest, profile_digest, profile_document


def scaffold():
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE.challenge_id,
        "backbone": "fno",
        "parameters": {"steps": 32},
    }


class Publications:
    def __init__(self):
        self.prior_ref = mcp.PriorRef(
            CHALLENGE, "registered_backbones", "1.0", profile_digest()
        )
        self.directive = mcp.PriorDirective(
            mcp.PriorDirectiveKind.EXPLORE, "backbone", ("fno", "deeponet")
        )

    def get_prior(self, challenge_key):
        if challenge_key != CHALLENGE:
            raise ValueError("wrong challenge")
        return mcp.PublishedPrior("1.0", self.prior_ref, (self.directive,))

    def get_scaffold(self, challenge_key, scaffold_id):
        if challenge_key != CHALLENGE or scaffold_id not in (None, "starter"):
            raise ValueError("unknown scaffold")
        return mcp.PublishedScaffold(
            "1.0",
            mcp.ScaffoldRef(CHALLENGE, "starter", "1.0", digest(canonical(scaffold()))),
            scaffold(),
            self.prior_ref,
            True,
        )

    def estimate(self, challenge_key, prior, strategy, validation):
        return mcp.StructuralEstimate(
            "1.0",
            challenge_key,
            prior.prior_ref,
            validation,
            (self.directive,),
            "non_binding_structural_prior_only",
        )


class QueryGate:
    def __init__(self):
        self.calls = 0

    def consume(self, requester, tool):
        self.calls += 1
        if self.calls > 24:
            raise mcp.McpQueryBudgetError()


class ObservedSnapshot:
    """One freshly read SDK snapshot shared with envelope construction."""

    def __init__(self):
        self.value = None

    async def observe(self, *, minimum_finalized_block):
        if self.value is None or self.value.finalized_block < minimum_finalized_block:
            raise ValueError("fresh chain observation required")
        return self.value


def make_mcp(root: Path, research_inputs=None):
    active_document = (
        profile_document()
        if research_inputs is None
        else research_inputs.profile_document
    )
    active_digest = digest(canonical(active_document))
    active_context = (
        context(root) if research_inputs is None else research_inputs.context
    )
    registry_root, artifacts = root / "registry", root / "registry-artifacts"
    registry_root.mkdir(exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    write_once(artifacts / "development-profile.json", canonical(active_document))
    registry = ChallengeRegistry(
        registry_root,
        artifacts,
        development_service_admissions=(
            DevelopmentServiceAdmission(
                CHALLENGE, "development_profile", active_digest
            ),
        ),
    )
    registry.save(
        ChallengeRecord(
            CHALLENGE.challenge_id,
            CHALLENGE.version,
            fixture_origin=True,
            status="fixture",
            allowed_backbones=("fno", "deeponet"),
            artifacts={
                "development_profile": ArtifactBinding(
                    "development-profile.json", active_digest
                )
            },
            qualification=QualificationManifest(
                CHALLENGE.challenge_id, CHALLENGE.version, "fixture", {}
            ),
        )
    )
    pin = active_context.pin
    submissions = SubmissionService(
        strategy_limits(),
        registry,
        FixtureSubmissionPolicy(
            FeePolicyKey("development-zero-local-fee"),
            0,
            1,
            pin.generator_version,
            pin.generator_digest,
            pin.scoring_version,
            pin.scoring_digest,
            ExecutionEnvironmentPin("burgers-development", active_digest),
        ),
    )
    limits = mcp.McpResourceLimits(
        16, 512, 32, 32, 4096, 128, 64, 16384, 4096, 256, 4096, 64, 32768, 1
    )
    publications = Publications()
    return (
        mcp.McpService(
            registry,
            submissions,
            limits,
            QueryGate(),
            publications,
            publications,
            publications,
        ),
        registry,
    )


def development_signer(root: Path):
    key_path = root / "private-evidence-signing-key.bin"
    metadata_path = root / "evidence-signing-public.json"
    if not key_path.exists():
        write_once(key_path, os.urandom(32))
    if key_path.is_symlink() or key_path.stat().st_size != 32:
        raise ValueError("invalid development key file")
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_bytes())
    else:
        now = time.time_ns() // 1000
        metadata = {
            "key_id": "burgers-development-" + uuid.uuid4().hex,
            "valid_from_micros": now,
            "valid_until_micros": now + 180 * 86400 * 1_000_000,
        }
    signer = audit.DevelopmentReceiptSigner(
        private_key=key_path.read_bytes(), **metadata
    )
    write_once(metadata_path, canonical(metadata))
    return signer


@dataclass
class LocalMinerConnection:
    root: Path
    image_manifest: Path
    chain_context: ChainContext
    publisher: str
    miner_key: object
    comparison_contract_digest: str | None = None
    research_inputs: object | None = None

    def attach_development_comparison(self, ref):
        from carbon.development_comparison.acceptance import resolve_acceptance

        report = resolve_acceptance(ref)
        if report["challenger"]["authenticated_hotkey"] != self.miner_key.ss58_address:
            raise ValueError("only own development comparison feedback is permitted")
        submission = report["challenger"]["binding"]["submission_id"]
        if submission not in self.completed:
            raise ValueError("comparison must bind this authenticated session result")
        if not hasattr(self, "development_comparison_feedback"):
            self.development_comparison_feedback = {}
        self.development_comparison_feedback[submission] = ref

    def __post_init__(self):
        if (
            self.chain_context.netuid != CARBON_NETUID
            or self.chain_context.network != CARBON_NETWORK
        ):
            raise ValueError(f"public {CARBON_NETWORK} {CARBON_NETUID} required")
        if self.miner_key.ss58_address == self.publisher:
            raise ValueError("distinct miner hotkey required")
        if self.research_inputs is not None:
            from .research_final import ResearchEvaluationInputs

            if (
                type(self.research_inputs) is not ResearchEvaluationInputs
                or self.research_inputs.root != self.root
                or self.comparison_contract_digest is not None
            ):
                raise ValueError("exact separate research final binding required")
        self.signer = development_signer(self.root)
        self.ledger = audit.DevelopmentEvidenceLedger(
            self.root / "evidence.sqlite3", (self.signer.verification_key,)
        )
        self.orchestrator = DevelopmentEvaluationOrchestrator(
            DurableExecutionQueue(self.root / "orchestration.sqlite3"), self.ledger
        )
        self.transport = ReceiptJournal(
            self.root / "transport.sqlite3", self.chain_context
        )
        self.observed = ObservedSnapshot()
        gateway = AuthenticatedGateway(
            self.chain_context,
            CHALLENGE,
            self.publisher,
            self.observed,
            BittensorHotkeyVerifier(),
            self.transport,
        )
        service, self.registry = make_mcp(self.root, self.research_inputs)
        self.service = AuthenticatedMinerMcpService(
            gateway, service, self.orchestrator, MinerMcpJournal(self.transport)
        )
        self.budget = SessionBudget(self.root / "budget.sqlite3")
        self.proposals = {}
        self.sequence = 0
        self.completed = {}
        self.submitted = {}
        self.proposal_limit = 3 if self.research_inputs is None else 1
        if self.comparison_contract_digest is not None:
            from carbon.development_comparison.experiment import load_contract

            contract = load_contract(self.root)
            if digest(canonical(contract)) != self.comparison_contract_digest:
                raise ValueError("comparison contract differs from selected agent plan")
            self.proposal_limit = 2

    async def check_registration(self):
        observed = await BittensorReader().capture(self.chain_context)
        if observed.resolve(self.miner_key.ss58_address) is None:
            raise ValueError(
                "distinct miner registration required before authenticated session"
            )
        if observed.resolve(self.publisher) is None:
            raise ValueError("publisher registration missing")
        self.observed.value = observed
        return observed

    async def call(self, tool: str, fields: dict[str, object]):
        if tool not in {item.value for item in mcp.McpTool} or type(fields) is not dict:
            raise ValueError("unsupported miner tool")
        if len(canonical(fields)) > 16384:
            raise ValueError("tool input exceeds bound")
        if self.comparison_contract_digest is not None:
            from carbon.development_comparison.experiment import load_contract

            if (
                digest(canonical(load_contract(self.root)))
                != self.comparison_contract_digest
            ):
                raise ValueError("comparison contract changed during session")
        print(f"Miner tool: {tool}", flush=True)
        identity = None
        if "strategy" in fields:
            strategy = fields["strategy"]
            if self.research_inputs is not None:
                self.research_inputs.verify(strategy)
            identity = digest(canonical(strategy))
            if identity not in self.proposals:
                number = len(self.proposals) + 1
                self.budget.reserve(
                    f"proposal-{number}",
                    "proposal",
                    1.0,
                    float(self.proposal_limit),
                    self.proposal_limit,
                )
                self.proposals[identity] = number
                write_once(self.root / f"proposal-{number}.json", canonical(strategy))
                compiled = (
                    build_contracts()
                    if self.research_inputs is None
                    else self.research_inputs.contracts
                ).compile(strategy)
                self.budget.finish(
                    f"proposal-{number}",
                    1.0,
                    "COMPLETE" if type(compiled) is CompileAccepted else "FAILED",
                )
            compiled = (
                build_contracts()
                if self.research_inputs is None
                else self.research_inputs.contracts
            ).compile(strategy)
            if type(compiled) is not CompileAccepted:
                return {
                    "status": "REJECTED",
                    "proposal_attempt": self.proposals[identity],
                    "reason": "Unsupported strategy; choose fno or deeponet and integer steps 32..64. Fixed physical values cannot change.",
                }
        observed = await self.check_registration()
        if tool == "submit" and identity is not None and identity in self.submitted:
            return dict(self.submitted[identity])
        self.sequence += 1
        body = message(
            self.chain_context,
            observed.snapshot_id,
            CHALLENGE,
            session="burgers-session",
            request=f"tool-{self.sequence}",
            tool=tool,
            fields=fields,
        )
        headers = BittensorMessageSigner(self.miner_key).sign(
            body, receiver=self.publisher, nonce_ns=time.time_ns()
        )
        result = await self.service.call(body, headers)
        value = result.mcp_result
        if type(value) is mcp.ChallengeInfo:
            projection = {
                "challenge": profile_document(),
                "effectively_live": False,
                "strategy_schema": {
                    "schema_version": "1.0",
                    "challenge_id": CHALLENGE.challenge_id,
                    "backbone": ["fno", "deeponet"],
                    "parameters": {"steps": "integer 32..64"},
                },
            }
            if self.comparison_contract_digest is not None:
                projection["session_limits"] = {
                    "max_proposals_including_invalid": 2,
                    "max_evaluations": 2,
                    "replicas_per_evaluation": 3,
                    "max_provider_calls": 24,
                    "max_provider_usd": 1.0,
                    "public_network_transactions": 0,
                }
            from carbon.orchestration.development_feedback import development_objective

            projection["available_development_objective"] = development_objective()
            projection["development_objective_activation"] = (
                "requires separate prospective rule registration before fresh constructions; legacy source flags unchanged"
            )
            return projection
        if type(value) is mcp.PublishedPrior:
            projection = {
                "prior": [
                    {
                        "kind": item.kind.value,
                        "subject": item.subject,
                        "tokens": list(item.tokens),
                    }
                    for item in value.directives
                ]
            }
            if self.comparison_contract_digest is not None:
                from carbon.development_comparison.experiment import (
                    baseline_for_session,
                )

                baseline = baseline_for_session(self.root)
                if (
                    baseline.identity["authenticated_hotkey"]
                    != self.miner_key.ss58_address
                ):
                    raise ValueError("only own historical feedback is permitted")
                projection["own_historical_development"] = {
                    "strategy": baseline.strategy,
                    "feedback": baseline.feedback,
                    "cohort_previously_seen": True,
                }
            return projection
        if type(value) is mcp.PublishedScaffold:
            return {"strategy": value.strategy, "execution_deferred": True}
        if type(value) is mcp.DryValidateResponse:
            return {"valid": value.validation.ok}
        if type(value) is mcp.StructuralEstimate:
            return {
                "valid": value.validation.ok,
                "disclaimer": value.disclaimer,
                "training_replicas": 3,
                "worker_cpu": 2,
                "worker_memory_gib": 4,
                "quality_estimate": None,
            }
        if type(value) is mcp.SubmitReceipt:
            from .evaluation import evaluate
            from .handoff import finish_handoff

            ref = self.transport.resolve(result.transport_receipt)
            requester = requester_for_receipt(self.chain_context, ref)
            seeds = (
                None
                if self.research_inputs is None
                else self.research_inputs.randomness
            )
            if self.comparison_contract_digest is not None:
                from carbon.development_comparison.experiment import proposal_seeds

                seeds = proposal_seeds(self.root, self.proposals[identity])
                self.budget.reserve(
                    f"evaluation-{self.proposals[identity]}", "evaluation", 1.0, 2.0, 2
                )
            print(
                f"Reconstruction and evaluation: proposal {self.proposals[identity]}",
                flush=True,
            )
            numerical = evaluate(
                self.root,
                self.image_manifest,
                fields["strategy"],
                value.status.submission_id.value,
                requester,
                execution_scope=ExecutionScope.REAL_PATH_NON_LIVE,
                frozen_randomness=seeds,
                research_inputs=self.research_inputs,
            )
            complete = finish_handoff(
                self, result.transport_receipt, requester, numerical
            )
            if self.comparison_contract_digest is not None:
                self.budget.finish(
                    f"evaluation-{self.proposals[identity]}", 1.0, "COMPLETE"
                )
                from carbon.development_comparison.report import write_report

                ref = write_report(
                    self.root,
                    self.root / f"source-{value.status.submission_id.value}.json",
                )
                print(
                    f"Comparison report: {ref.path}; INDETERMINATE_NO_ACCEPTANCE_RULE",
                    flush=True,
                )
            print(
                f"Evaluation complete: {value.status.submission_id.value}; COMPLETE_UNRESOLVED",
                flush=True,
            )
            self.completed[value.status.submission_id.value] = (
                complete,
                numerical["feedback"],
            )
            response = {
                "submission_id": value.status.submission_id.value,
                "status": "COMPLETE_UNRESOLVED",
            }
            self.submitted[identity] = response
            return dict(response)
        if type(value) is mcp.SubmissionResult:
            entry = self.completed.get(value.status.submission_id.value)
            if entry is None:
                return {
                    "submission_id": value.status.submission_id.value,
                    "status": value.status.state.value,
                }
            complete, feedback = entry
            _, lifecycle = self.ledger.resolve(
                complete.ledger_reference, verified_at_micros=time.time_ns() // 1000
            )
            if lifecycle is not audit.ReceiptLifecycleState.ACTIVE:
                return {"status": "QUARANTINED", "feedback": None}
            result = {
                "submission_id": value.status.submission_id.value,
                "status": "COMPLETE_UNRESOLVED",
                "feedback": feedback,
            }
            ref = getattr(self, "development_comparison_feedback", {}).get(
                value.status.submission_id.value
            )
            if ref is not None:
                from carbon.orchestration.development_feedback import (
                    project_development_acceptance,
                )

                result["development_comparison"] = project_development_acceptance(ref)
            return result
        raise ValueError("unsupported service result projection")
