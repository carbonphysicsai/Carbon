"""DEVELOPMENT-only ConstructionRecipe adapter over the durable direct tasks.

The signed validator door authenticates and strictly screens the request. This
adapter binds the registered Challenge material and sends the recipe to the
existing per-owner direct task provider. That provider owns source/image
resolution, C-03 build, frozen source-free inference, durable child operations
and reconciliation. No scorer or promotion is installed here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from carbon.development_session.construction_recipe import (
    SCHEMA as RECIPE_SCHEMA,
)
from carbon.development_session.construction_recipe import bind_recipe
from carbon.reconstruction.served_recipe_contract import registered

from .interface import ChallengeAdapter, Unavailable, digest

OUTCOME_SCHEMA = "carbon.lean-recipe-development-outcome.v1"
_SOURCE_PATHS = (
    "carbon/challenge_validator/lean_recipe.py",
    "carbon/development_session/construction_recipe.py",
    "carbon/development_session/research_tasks.py",
    "carbon/development_session/direct_graph_construction_worker.py",
    "carbon/development_session/bundle_construction_worker.py",
    "carbon/development_session/library_bundles.py",
    "carbon/development_session/library_overlay_prep.py",
    "carbon/development_session/synthetic_graph_adapter.py",
    "carbon/development_session/bundle_graph_state.py",
    "carbon/reconstruction/served_recipe_contract.py",
)


def _source_identity() -> str:
    """Bind the adapter and every repository module staged into its workers."""
    from carbon.development_session.bundle_construction_worker import (
        STAGED_MODULES as BUNDLE_STAGED_MODULES,
    )
    from carbon.development_session.direct_graph_construction_worker import (
        STAGED_MODULES as GRAPH_STAGED_MODULES,
    )

    root = Path(__file__).resolve().parents[2]
    observed = {}
    staged = {
        module.replace(".", "/") + ".py"
        for module in (*BUNDLE_STAGED_MODULES, *GRAPH_STAGED_MODULES)
    }
    for name in sorted(set(_SOURCE_PATHS) | staged):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("served recipe source unavailable")
        observed[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return digest({"schema": "carbon.lean-recipe-source-binding.v1", "files": observed})


def _implementation_identity() -> str:
    return digest(
        {
            "schema": OUTCOME_SCHEMA,
            "recipe_schema": RECIPE_SCHEMA,
            "task_schema": "direct_start_task_request_v3",
            "source_boundary": "C03_BUILD_THEN_SOURCE_FREE_INFERENCE",
            "source_identity": _source_identity(),
        }
    )


class LeanRecipeAdapter(ChallengeAdapter):
    """One registered kit; provider instances remain bound to signer owners."""

    strategy_schema = RECIPE_SCHEMA
    disclosure_fields = frozenset({"task_id", "state_digest", "predictions_digest"})

    def __init__(
        self, discovery, provider_for: Callable, ledger, *, measure_query: bool = False
    ):
        from carbon.challenge_validator.ledger import AttemptLedger
        from carbon.development_session.research_service import DirectFixtureDiscovery
        from carbon.transport.models import MAX_BODY

        if (
            type(discovery) is not DirectFixtureDiscovery
            or type(ledger) is not AttemptLedger
            or not callable(provider_for)
            or type(measure_query) is not bool
        ):
            raise TypeError(
                "verified discovery, owner provider and attempt ledger required"
            )
        info, _manifest = discovery._checked(discovery.info.challenge_key)
        contract = registered(
            info.challenge_key.challenge_id, info.challenge_key.version
        )
        if discovery._material["construction_kit"] != contract.construction_kit:
            raise ValueError("served recipe material differs from registered kit")
        self.discovery = discovery
        self.provider_for = provider_for
        self.ledger = ledger
        self._measure_query = measure_query
        self.challenge_id = contract.challenge_id
        self.challenge_version = contract.version
        self.contract_digest = contract.digest
        self._evidence_label = contract.evidence_label
        self.max_strategy_bytes = MAX_BODY
        self._kit = dict(contract.construction_kit)
        self._identities = self._bound_identities(contract)

    def _bound_identities(self, contract):
        from carbon.development_session.profile import canonical
        from carbon.development_session.profile import digest as sha
        from carbon.research import canonical_digest

        key = self.discovery.info.challenge_key
        info, manifest = self.discovery._checked(key)
        material = self.discovery._material
        policy = material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        rule = {"schema": "carbon.lean-recipe-score-binding.v1", "score_pack": None}
        if self._measure_query:
            rule = {
                "schema": "carbon.lean-recipe-score-binding.v2",
                "score_pack": None,
                "measurement_profile": "COLD_QUERY_V2",
            }
        return {
            "schema": "carbon.lean-recipe-adapter-identities.v1",
            "contract_digest": contract.digest,
            "rule_digest": digest(rule),
            "implementation_digest": _implementation_identity(),
            "construction_kit_digest": sha(canonical(self._kit)),
            "challenge_info_digest": canonical_digest(info),
            "manifest_digest": canonical_digest(manifest),
            "resource_policy_digest": sha(canonical(policy)),
            "allowlist_digest": contract.allowlist_digest,
        }

    def identities(self):
        return json.loads(json.dumps(self._identities))

    def validate_strategy(self, strategy):
        """Strict recipe and exact Challenge binding before any worker reservation."""
        return bind_recipe(
            strategy,
            challenge_id=self._kit["id"],
            challenge_version=self._kit["version"],
            train_digest=self._kit["train_digest"],
            interface_digest=self._kit["interface_digest"],
            construction_limits_digest=self._kit["construction_limits_digest"],
        )

    def _provider(self, hotkey):
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

        if self._identities["implementation_digest"] != _implementation_identity():
            raise Unavailable("served_recipe_source_changed")
        provider = self.provider_for(hotkey)
        if (
            type(provider) is not DirectDevelopmentTasksV3
            or provider.owner != hotkey
            or provider.discovery is not self.discovery
            or provider.evaluation_pack_digest != self.discovery.evaluation_pack_digest
        ):
            raise Unavailable("direct_provider_binding_unavailable")
        return provider

    def _request(self, hotkey, recipe, *, evaluation_pack_digest=None, retry_of=None):
        from carbon.development_session.profile import canonical
        from carbon.development_session.profile import digest as sha
        from carbon.research import DirectStartTaskRequestV3, ResearchTaskId

        info = self.discovery.info
        task_binding = hotkey + "\0" + self.contract_digest + "\0" + recipe.digest
        if self._measure_query:
            task_binding += "\0" + self._identities["rule_digest"]
        if evaluation_pack_digest is not None:
            task_binding += "\0EVALUATION_PACK\0" + evaluation_pack_digest
        identity = hashlib.sha256(task_binding.encode("utf-8")).hexdigest()
        key = "lean-recipe-" + identity
        if retry_of is not None:
            from carbon.development_session.research_tasks import (
                DIRECT_RETRY_KEY_PREFIX,
            )

            key = DIRECT_RETRY_KEY_PREFIX + ResearchTaskId(retry_of).value
        return DirectStartTaskRequestV3(
            info.challenge_key,
            key,
            recipe.to_dict(),
            self._identities["challenge_info_digest"],
            self._identities["manifest_digest"],
            self._identities["construction_kit_digest"],
            info.public_train_digest,
            info.practice_inputs_digest,
            info.interface_digest,
            info.construction_limits_digest,
            sha(
                canonical(
                    self.discovery._material["construction_limits_document"][
                        "reconstruction_resource_policy"
                    ]
                )
            ),
        )

    @staticmethod
    def _check_graph_source(provider, recipe):
        from carbon.development_session.construction_recipe import (
            RecipeRefused,
            graph_envelope_from_workspace,
        )

        source = recipe.to_dict()["source"]
        if source["kind"] == "graph":
            try:
                graph_envelope_from_workspace(provider.ledger, provider.owner, recipe)
            except RecipeRefused as refused:
                raise Unavailable(refused.code) from None

    def evaluate(self, submission):
        recipe = self.validate_strategy(submission.strategy)
        provider = self._provider(submission.hotkey)
        self._check_graph_source(provider, recipe)
        # The durable task provider owns source inspection and admitted
        # environment preparation. A missing preinstalled image is not a
        # separate construction-admission rule at the signed door.
        request = self._request(
            submission.hotkey,
            recipe,
            evaluation_pack_digest=provider.evaluation_pack_digest,
        )
        return self._admit_request(submission, provider, request)

    def retry(self, submission, retry_of):
        """Create one explicit child of an authentic infrastructure-failed task."""
        from dataclasses import replace

        from carbon.research import ResearchTaskId, canonical_bytes

        from .interface import Admitted

        if type(submission) is not Admitted:
            raise TypeError("screened construction submission required")
        if (
            submission.challenge_id != self.challenge_id
            or submission.challenge_version != self.challenge_version
            or submission.contract_digest != self.contract_digest
        ):
            raise Unavailable("construction_retry_binding_mismatch")
        try:
            predecessor = ResearchTaskId(retry_of)
        except (TypeError, ValueError):
            raise Unavailable("construction_retry_predecessor_invalid") from None
        recipe = self.validate_strategy(submission.strategy)
        provider = self._provider(submission.hotkey)
        with provider._lock:
            if not self._owned_lineage(provider, submission.hotkey, predecessor.value):
                raise Unavailable("construction_retry_predecessor_unavailable")
            prior = provider._requests[predecessor.value]
            request = self._request(
                submission.hotkey,
                recipe,
                evaluation_pack_digest=provider.evaluation_pack_digest,
                retry_of=predecessor.value,
            )
            if canonical_bytes(
                replace(prior, idempotency_key=request.idempotency_key)
            ) != canonical_bytes(request) or not self._failed_predecessor(
                provider, predecessor, prior
            ):
                raise Unavailable("construction_retry_predecessor_unavailable")
            child_id = provider._idempotency.get(request.idempotency_key)
            child_request = provider._requests.get(child_id)
            retained_child = (
                child_request is not None
                and canonical_bytes(child_request) == canonical_bytes(request)
                and provider._task_id(request).value == child_id
                and (child_id in provider._measured_tasks) == self._measure_query
            )
        # A replay uses the admitted child's immutable source, even if the
        # owner's live workspace changed after the response was lost.
        if not retained_child:
            self._check_graph_source(provider, recipe)
        return self._admit_request(
            submission, provider, request, predecessor=predecessor
        )

    def _admit_request(self, submission, provider, request, *, predecessor=None):
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        task_id = provider._task_id(request)
        from carbon.research import canonical_bytes

        self.ledger.record_recipe_task_intent(
            self.contract_digest,
            task_id.value,
            submission.hotkey,
            "sha256:" + hashlib.sha256(canonical_bytes(request)).hexdigest(),
        )
        try:
            task = (
                provider.start_research_task(request, measure_query=self._measure_query)
                if predecessor is None
                else provider.retry_research_task(
                    request,
                    predecessor_id=predecessor,
                    measure_query=self._measure_query,
                )
            ).task
        except ResearchTaskProviderError as refused:
            if refused.code in (
                ResearchServiceErrorCode.REFERENCE_NOT_FOUND,
                ResearchServiceErrorCode.REFERENCE_MISMATCH,
                ResearchServiceErrorCode.BOUND_EXCEEDED,
            ):
                raise Unavailable("direct_" + refused.code.value.lower()) from None
            raise Unavailable("direct_provider_unavailable") from None
        if task.task_id != task_id:
            raise RuntimeError("direct task identity changed after owner intent")
        return self._project(task, provider)

    def _project(self, task, provider):
        from carbon.research import DirectTaskStateV3

        state = task.state
        outcome = {
            "schema": OUTCOME_SCHEMA,
            "submission_id": task.task_id.value,
            "challenge": {"id": self.challenge_id, "version": self.challenge_version},
            "state": "ADMITTED",
            "evidence": self._evidence_label,
            "qualification": False,
            "reward": False,
            "task_id": task.task_id.value,
        }
        if state is DirectTaskStateV3.SUCCEEDED:
            evidence = provider.public_result(task)
            if (
                type(evidence) is not dict
                or evidence.get("official_eligible") is not False
                or evidence.get("predictions_digest")
                != task.terminal_receipt.predictions_digest
            ):
                raise RuntimeError("direct task success evidence differs")
            outcome["state"] = "RECONSTRUCTED"
            outcome["state_digest"] = task.terminal_receipt.state_digest
            outcome["predictions_digest"] = evidence["predictions_digest"]
        elif state is DirectTaskStateV3.REFUSED:
            outcome["state"] = "RECONSTRUCTION_FAILED"
            outcome["failure"] = {"code": task.terminal_receipt.refusal_code}
        elif state in (
            DirectTaskStateV3.FAILED_INFRA,
            DirectTaskStateV3.UNRESOLVED,
            DirectTaskStateV3.CANCELLED,
        ):
            outcome["state"] = "FAILED_INFRA"
            outcome["failure"] = {
                "code": (
                    task.terminal_receipt.refusal_code
                    if state is DirectTaskStateV3.UNRESOLVED
                    and task.terminal_receipt.refusal_code is not None
                    else "direct_task_" + state.value.lower()
                )
            }
            if state is DirectTaskStateV3.FAILED_INFRA:
                advisory = provider.public_result(task)
                if advisory is not None:
                    outcome["failure"]["issues"] = [
                        {
                            "reason_code": advisory["reason_code"],
                            "failed_stage": advisory["failed_stage"],
                            "diagnostic_provenance": advisory["diagnostic_provenance"],
                            "reported_operation": advisory["reported_operation"],
                            "next_step": advisory["next_step"],
                        }
                    ]
        return outcome

    def _failed_predecessor(self, provider, task_id, request):
        from carbon.research import (
            DirectGetTaskRequestV3,
            DirectTaskReceiptV3,
            DirectTaskStateV3,
            DirectTaskViewV3,
            canonical_bytes,
        )
        from carbon.research.lifecycle import ResearchTaskProviderError

        try:
            task = provider.get_research_result(
                DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
            ).task
            if type(task) is not DirectTaskViewV3:
                return False
            canonical_bytes(task)
            receipt = task.terminal_receipt
            return (
                task.task_id == task_id
                and task.state is DirectTaskStateV3.FAILED_INFRA
                and type(receipt) is DirectTaskReceiptV3
                and receipt.task_id == task_id
                and receipt.terminal_state is DirectTaskStateV3.FAILED_INFRA
                and receipt.immutable_bindings == task.immutable_bindings
                and task.immutable_bindings == provider._bindings(request)
                and receipt.infrastructure_failure_class is not None
            )
        except (ValueError, TypeError, AttributeError, ResearchTaskProviderError):
            return False

    def _owned_lineage(self, provider, owner, submission_id):
        from carbon.development_session.construction_recipe import ConstructionRecipe
        from carbon.development_session.research_tasks import DIRECT_RETRY_KEY_PREFIX
        from carbon.research import ResearchTaskId, canonical_bytes
        from carbon.research.lifecycle import ResearchTaskProviderError

        seen = set()
        recipe = None
        try:
            current = ResearchTaskId(submission_id).value
            # The retained provider already bounds storage to 256 requests.
            # Use that actual roster rather than an independent retry cap.
            while len(seen) < len(provider._requests) and current not in seen:
                seen.add(current)
                retained = provider._requests.get(current)
                if (
                    retained is None
                    or self.ledger.owned_outcome(self.contract_digest, current) != owner
                    or (current in provider._measured_tasks) != self._measure_query
                ):
                    return False
                if recipe is None:
                    recipe = ConstructionRecipe.from_dict(retained.recipe)
                key = retained.idempotency_key
                parent = (
                    ResearchTaskId(key[len(DIRECT_RETRY_KEY_PREFIX) :])
                    if key.startswith(DIRECT_RETRY_KEY_PREFIX)
                    else None
                )
                expected = self._request(
                    owner,
                    recipe,
                    evaluation_pack_digest=provider.evaluation_pack_digest,
                    retry_of=None if parent is None else parent.value,
                )
                if (
                    canonical_bytes(expected) != canonical_bytes(retained)
                    or provider._task_id(expected).value != current
                ):
                    return False
                if parent is None:
                    return True
                prior = provider._requests.get(parent.value)
                if prior is None or not self._failed_predecessor(
                    provider, parent, prior
                ):
                    return False
                current = parent.value
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            ResearchTaskProviderError,
        ):
            return False
        return False

    def owner(self, submission_id):
        owner = self.ledger.owned_outcome(self.contract_digest, submission_id)
        if owner is None:
            return None
        provider = self._provider(owner)
        with provider._lock:
            return (
                owner if self._owned_lineage(provider, owner, submission_id) else None
            )

    def outcome(self, submission_id):
        from carbon.research import DirectGetTaskRequestV3, ResearchTaskId

        owner = self.owner(submission_id)
        if owner is None:
            raise LookupError("unknown_submission")
        provider = self._provider(owner)
        task = provider.get_research_result(
            DirectGetTaskRequestV3(
                self.discovery.info.challenge_key, ResearchTaskId(submission_id)
            )
        ).task
        return self._project(task, provider)

    def _active_owner(self, submission_id):
        try:
            return self.owner(submission_id)
        except Unavailable as unavailable:
            if unavailable.code != "direct_provider_registration_unavailable":
                raise
            # Retained cleanup custody is not fresh dispatch authority.
            return None

    def advance(self):
        from carbon.research import (
            DirectGetTaskRequestV3,
            DirectTaskStateV3,
            ResearchTaskId,
        )
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        moved = 0
        for submission_id in self.ledger.submitted_outcomes(self.contract_digest):
            owner = self._active_owner(submission_id)
            if owner is None:
                continue
            provider = self._provider(owner)
            task_id = ResearchTaskId(submission_id)
            try:
                task = provider.get_research_result(
                    DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
                ).task
            except ResearchTaskProviderError as missing:
                if missing.code is ResearchServiceErrorCode.TASK_NOT_FOUND:
                    # An intent can precede a refused or interrupted start.
                    # The owner may retry the same signed recipe idempotently.
                    continue
                raise
            if task.state is DirectTaskStateV3.QUEUED:
                provider.run_queued_task(task_id)
                moved += 1
                # One operator pass dispatches at most one construction. The
                # existing carrier enforces its per-child resource limits;
                # this adapter never fans out a backlog on one call.
                break
        return moved

    def score_record(self, submission_id):
        raise LookupError("score_pack_unbound")

    def sealed_roles(self):
        return frozenset()

    def _prepare_batch(self, role, *, kind, **options):
        raise Unavailable("development_fixture_has_no_exam")

    def reference_jobs(self, fingerprint):
        raise Unavailable("development_fixture_has_no_exam")

    def ingest_references(self, fingerprint, records):
        raise Unavailable("development_fixture_has_no_exam")

    def open_pool(self):
        raise Unavailable("development_fixture_has_no_exam")

    def status(self):
        return {
            "schema": "carbon.lean-recipe-adapter-status.v1",
            "contract_digest": self.contract_digest,
            "submissions": sum(
                self._active_owner(submission_id) is not None
                for submission_id in self.ledger.submitted_outcomes(
                    self.contract_digest
                )
            ),
            "score_pack": None,
            "qualification": False,
        }
