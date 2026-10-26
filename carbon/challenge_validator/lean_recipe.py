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

from .interface import (
    ChallengeAdapter,
    SameRecipeAlreadySubmitted,
    Unavailable,
    digest,
)

OUTCOME_SCHEMA = "carbon.lean-recipe-development-outcome.v1"
#: How many fresh re-runs one recipe may get on one pack set after
#: infrastructure failures (invariant 7): an engineering bound on retries of our
#: own failures, never a scientific value. Past it the door is unavailable.
MAX_INFRA_RERUNS = 16
_SOURCE_PATHS = (
    "carbon/challenge_validator/lean_recipe.py",
    "carbon/development_session/construction_recipe.py",
    "carbon/development_session/research_tasks.py",
    "carbon/development_session/direct_graph_construction_worker.py",
    "carbon/development_session/bundle_construction_worker.py",
    "carbon/development_session/library_bundles.py",
    "carbon/development_session/library_overlay_prep.py",
    "carbon/development_session/synthetic_graph_adapter.py",
    "carbon/development_session/physical_graph_adapter.py",
    "carbon/development_session/physical_graph_state.py",
    "carbon/development_session/physical_graph_trainer.py",
    # Battery's graph adapter (the Validator's ruling (a)) and the Battery
    # modules it stages unchanged into its build and inference children.
    "carbon/development_session/graph_adapters.py",
    "carbon/development_session/battery_graph_adapter.py",
    "carbon/development_session/build_refusal.py",
    "carbon/battery/domain.py",
    "carbon/battery/recipes.py",
    "carbon/battery/training.py",
    "carbon/battery/direct_graph.py",
    # Graph route v2's adapter, state, trainer and refusal classes.
    "carbon/development_session/physical_graph_adapter_v2.py",
    "carbon/development_session/physical_graph_state_v2.py",
    "carbon/development_session/physical_graph_trainer_v2.py",
    "carbon/development_session/build_refusal_v2.py",
    "carbon/development_session/bundle_graph_state.py",
    "carbon/reconstruction/served_recipe_contract.py",
    "carbon/challenge_kit/physical_material.py",
    "carbon/challenge_kit/physical_pack.py",
    "carbon/challenge_kit/physical_public.py",
    "carbon/challenge_kit/physical_public_train.py",
    "carbon/challenge_kit/version_registry.py",
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
        self,
        discovery,
        provider_for: Callable,
        ledger,
        *,
        measure_query: bool = False,
        copy_hotkey: str | None = None,
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
        # This validator's hotkey: a sealed pack is accepted only as its copy for
        # this hotkey (traceable copies; None = no copy header required).
        self.copy_hotkey = copy_hotkey
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
        """Strict recipe and exact Challenge binding before any worker
        reservation. A catalog recipe is returned as the Carbon bundle recipe
        it names (`backbone_catalog.served.expand`), its settings checked by
        that bundle's own door; it then runs as that bundle."""
        recipe = bind_recipe(
            strategy,
            challenge_id=self._kit["id"],
            challenge_version=self._kit["version"],
            train_digest=self._kit["train_digest"],
            interface_digest=self._kit["interface_digest"],
            construction_limits_digest=self._kit["construction_limits_digest"],
        )
        if recipe.to_dict()["source"]["kind"] == "bundle":
            # a smoke-only GPU build is practice only: refuse it before anything is reserved
            from carbon.backbone_catalog.served import refuse_unreproducible_runtime

            refuse_unreproducible_runtime(recipe.to_dict()["source"]["bundle_ref"])
        if recipe.to_dict()["source"]["kind"] == "catalog":
            from carbon.backbone_catalog.served import expand_official
            from carbon.development_session.construction_recipe import (
                ConstructionRecipe,
            )

            # The grading rebuild: the entry's official-grade GPU twin where this receiver holds
            # that GPU worker, else its CPU build (OWNER-NO-LAUNCH-WITHOUT-GPU-REBUILD-01).
            expanded, _runtime = expand_official(recipe.to_dict(), self._gpu_runtimes())
            return ConstructionRecipe.from_dict(expanded)
        return recipe

    def _gpu_runtimes(self):
        """The GPU build runtimes this receiver's construction parents serve (none for a CPU
        receiver, and for a provider source that does not say)."""
        found = getattr(self.provider_for, "gpu_runtimes", None)
        return tuple(found()) if callable(found) else ()

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

    def _request(self, hotkey, recipe, *, evaluation_pack_digest=None, rerun=0):
        """The task request; ``rerun`` n > 0 is the n-th fresh task for the same
        recipe after infrastructure failures (generation 0 is unchanged)."""
        from carbon.development_session.profile import canonical
        from carbon.development_session.profile import digest as sha
        from carbon.research import DirectStartTaskRequestV3

        info = self.discovery.info
        task_binding = hotkey + "\0" + self.contract_digest + "\0" + recipe.digest
        if self._measure_query:
            task_binding += "\0" + self._identities["rule_digest"]
        if evaluation_pack_digest is not None:
            task_binding += "\0EVALUATION_PACK\0" + evaluation_pack_digest
        if rerun:
            task_binding += "\0INFRA_RERUN\0" + str(rerun)
        identity = hashlib.sha256(task_binding.encode("utf-8")).hexdigest()
        return DirectStartTaskRequestV3(
            info.challenge_key,
            "lean-recipe-" + identity,
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

    def evaluate(self, submission):
        from carbon.development_session.construction_recipe import (
            RecipeRefused,
            graph_envelope_from_workspace,
        )
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        recipe = self.validate_strategy(submission.strategy)
        provider = self._provider(submission.hotkey)
        # The durable task provider owns source inspection and admitted
        # environment preparation. A missing preinstalled image is not a
        # separate construction-admission rule at the signed door.
        # Generation 0 is the recipe's task. One that ended on our own
        # infrastructure (the task, or its grading released as FAILED_INFRA)
        # is never the miner's result (invariant 7): the next generation is a
        # fresh task, graded in the miner's next slot.
        for rerun in range(MAX_INFRA_RERUNS + 1):
            request = self._request(
                submission.hotkey,
                recipe,
                evaluation_pack_digest=provider.evaluation_pack_digest,
                rerun=rerun,
            )
            task_id = provider._task_id(request)
            if self._already_graded(submission.hotkey, task_id.value, provider):
                raise SameRecipeAlreadySubmitted(self.outcome(task_id.value))
            if not self._ended_on_infra(submission.hotkey, task_id, provider):
                break
        else:
            raise Unavailable("direct_infra_rerun_limit_reached")
        source = recipe.to_dict()["source"]
        if source["kind"] == "graph":
            try:
                graph_envelope_from_workspace(provider.ledger, provider.owner, recipe)
            except RecipeRefused as refused:
                raise Unavailable(refused.code) from None
        from carbon.research import canonical_bytes

        self.ledger.record_recipe_task_intent(
            self.contract_digest,
            task_id.value,
            submission.hotkey,
            "sha256:" + hashlib.sha256(canonical_bytes(request)).hexdigest(),
        )
        if submission.strategy.get("source", {}).get("kind") == "catalog":
            from carbon.backbone_catalog.served import submission_document

            self.ledger.record_catalog_submission(
                self.contract_digest,
                task_id.value,
                submission_document(submission.strategy, recipe.to_dict()),
            )
        try:
            task = provider.start_research_task(
                request, measure_query=self._measure_query
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

    def _already_graded(self, hotkey, submission_id, provider):
        """Validator ruling (a): this hotkey's recipe already graded on this
        pack set. The task identity binds hotkey, contract, recipe and pack,
        so its exam-cap row is the earlier grading; a rotated pack set is a
        new task. Without a pack nothing is graded, so nothing is refused."""
        if provider.evaluation_pack_digest is None:
            return False
        from carbon.challenge_validator.exam_cap import ExamCap

        return ExamCap(self.ledger).holds_slot(
            hotkey=hotkey,
            challenge_id=self.challenge_id,
            challenge_version=self.challenge_version,
            exam_key=provider.evaluation_pack_digest,
            submission_id=submission_id,
        )

    def _ended_on_infra(self, hotkey, task_id, provider):
        """Whether this task exists and ended on Carbon's infrastructure: its
        task state, or its grading released as FAILED_INFRA. Anything else
        (absent, running, reconstructed, the candidate's own failure) is not."""
        from carbon.research import DirectGetTaskRequestV3, DirectTaskStateV3
        from carbon.research.errors import ResearchServiceErrorCode
        from carbon.research.lifecycle import ResearchTaskProviderError

        try:
            task = provider.get_research_result(
                DirectGetTaskRequestV3(self.discovery.info.challenge_key, task_id)
            ).task
        except ResearchTaskProviderError as missing:
            if missing.code is ResearchServiceErrorCode.TASK_NOT_FOUND:
                return False
            raise
        if task.state in (
            DirectTaskStateV3.FAILED_INFRA,
            DirectTaskStateV3.UNRESOLVED,
            DirectTaskStateV3.CANCELLED,
        ):
            return True
        if provider.evaluation_pack_digest is None:
            return False
        from carbon.challenge_validator.exam_cap import ExamCap

        return ExamCap(self.ledger).released_on_infra(
            hotkey=hotkey,
            challenge_id=self.challenge_id,
            challenge_version=self.challenge_version,
            exam_key=provider.evaluation_pack_digest,
            submission_id=task_id.value,
        )

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

    def owner(self, submission_id):
        owner = self.ledger.owned_outcome(self.contract_digest, submission_id)
        if owner is None:
            return None
        from carbon.development_session.construction_recipe import ConstructionRecipe

        provider = self._provider(owner)
        retained = provider._requests.get(submission_id)
        if retained is None:
            return None
        recipe = ConstructionRecipe.from_dict(retained.recipe)
        expected = next(
            (
                request
                for request in (
                    self._request(
                        owner,
                        recipe,
                        evaluation_pack_digest=provider.evaluation_pack_digest,
                        rerun=rerun,
                    )
                    for rerun in range(MAX_INFRA_RERUNS + 1)
                )
                if request == retained
            ),
            None,
        )
        if (
            expected is None
            or provider._task_id(expected).value != submission_id
            or (submission_id in provider._measured_tasks) != self._measure_query
        ):
            return None
        return owner

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
