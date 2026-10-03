"""Versioned public workspace tasks behind B-07's existing twelve operations.

The legacy provider does not execute the new task kind. This explicit D4
composition opts in; all files/scripts remain miner-owned and non-authoritative.

A request's values are the requester's to get right, and refusing them is
never an infrastructure failure (LP-PROD-D). `check_workspace_request` is the
one rule: the request path reads it before dispatch, so a bad value starts no
task and charges no trial slot, and the executor reads it again before acting,
so a request that reaches it anyway completes as REQUEST_REFUSED with the same
code, field and fix.
"""

from __future__ import annotations

import base64
import json

from carbon.authoring.model import EvidenceRole
from carbon.research import (
    DevelopmentWorkspaceTaskSpecV1,
    DevelopmentWorkspaceTaskSpecV2,
    PracticeTaskSpec,
    ResearchTaskKind,
    ResearchTaskState,
    StartResearchTaskRequest,
    canonical_bytes,
    load_canonical,
)
from carbon.research.durable import DurableResearchTaskProvider
from carbon.research.model import InfrastructureFailureClass
from carbon.research.records import (
    AuthorizedResearchOutcome,
    EvidenceContext,
    EvidenceQualityMetadata,
    PrivateIdentityRef,
    ResearchCensoringStatus,
    ResearchEvidenceClass,
    ResearchRetentionScope,
    RetentionReuseBinding,
)

from .profile import canonical, digest
from .research_carrier import (
    ACTIVE_TASK,
    MinerProgramFailure,
    record_output_tamper,
    request_cancel,
    run_script,
)
from .research_workspace import ResearchWorkspace, request_capability


class PublicDevelopmentResearchTasks(DurableResearchTaskProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            # A worker reconciled while no supervisor held this store (the
            # launchpad's cleanup) settled the ledger; end its task now.
            self.settle_reconciled_tasks()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _spec_parts(request):
        if type(request.task_spec) is DevelopmentWorkspaceTaskSpecV1:
            return ResearchTaskKind.DEVELOPMENT_WORKSPACE_V1, (), (), ()
        if type(request.task_spec) is DevelopmentWorkspaceTaskSpecV2:
            return ResearchTaskKind.DEVELOPMENT_WORKSPACE_V2, (), (), ()
        return DurableResearchTaskProvider._spec_parts(request)

    def cancel_research_task(self, request):
        result = super().cancel_research_task(request)
        if result.task.state is ResearchTaskState.CANCEL_REQUESTED:
            self._executor.executor.cancel(request.task_id.value)
        return result

    def reconcile_task(self, task_id):
        """Reconcile an orphaned task's worker and end the task in one call.

        The ledger settles through ``reconcile_worker`` (observed cleanup, full
        reservation kept); the task then leaves RUNNING for its terminal state
        rather than staying RUNNING over a settled operation.
        """
        from .research_carrier import reconcile_worker

        executor = self._executor.executor
        result = reconcile_worker(
            executor.ledger, owner=executor.owner, identity=task_id.value
        )
        self.settle_reconciled_tasks(only=task_id)
        return result

    def settle_reconciled_tasks(self, *, only=None):
        """End tasks whose worker operation was already reconciled.

        Only a ledger FAILED_INFRA settles a task here: RESERVED still needs
        reconciliation, and an absent operation is not evidence of anything.
        A requested cancellation ends CANCELLED, as the lifecycle ends it.
        Called on load, where the supervisor lock excludes any live execution,
        and after ``reconcile_task``, whose numerical lease excluded it.
        """
        executor = self._executor.executor
        settled = []
        with self._lock:
            for task in self._tasks.values():
                if only is not None and task.task_id != only:
                    continue
                if task.state not in {
                    ResearchTaskState.RUNNING,
                    ResearchTaskState.CANCEL_REQUESTED,
                }:
                    continue
                state = executor.ledger.operation_state(
                    task.task_id.value, owner=executor.owner
                )
                if state != "FAILED_INFRA":
                    continue
                completed_at = self._now(task.updated_at_micros)
                if task.state is ResearchTaskState.CANCEL_REQUESTED:
                    receipt = self._receipt(
                        task, ResearchTaskState.CANCELLED, completed_at
                    )
                    self._transition(task, ResearchTaskState.CANCELLED, receipt=receipt)
                else:
                    receipt = self._receipt(
                        task,
                        ResearchTaskState.FAILED_INFRA,
                        completed_at,
                        failure_class=InfrastructureFailureClass.WORKER_LOST,
                    )
                    self._transition(
                        task, ResearchTaskState.FAILED_INFRA, receipt=receipt
                    )
                settled.append(task.task_id)
        return tuple(settled)

    def request_for_execution(self, task_id):
        """Trusted executor lookup, never a public operation."""
        with self._lock:
            if self._tasks[task_id].state not in {
                ResearchTaskState.RUNNING,
                ResearchTaskState.CANCEL_REQUESTED,
            }:
                raise ValueError("task is not running")
            return load_canonical(self._requests[task_id], StartResearchTaskRequest)


#: The most bytes one `read_file` returns (LP-PROD-D). It was 4 KiB of base64;
#: 64 KiB now, with text also returned as `content_utf8`. Even worst-case
#: escaped, both encodings stay well inside the 1 MiB public result bound.
READ_FILE_MAX_BYTES = 64 * 1024
#: The notebook kinds a miner (or their agent) may write.
NOTEBOOK_KINDS = ("hypothesis", "decision", "notebook")
#: The actions that run the miner's own program in the miner lane.
RUN_ACTIONS = frozenset({"run_python", "run_julia"})
#: Names the carrier stages itself; a run's own files may not take them.
RESERVED_STAGE_NAMES = frozenset({"program.py", "program.jl"})
#: The bound on a run's prospective hypothesis and expected effect.
RUN_TEXT = 2048


class WorkspaceRequestRefused(ValueError):
    """A workspace request whose values Carbon refuses: the requester's to fix.

    `code` is a closed correction code (`research_tools.TASK_CORRECTIONS`),
    `field` the registered field it is about, and `choices` the Carbon-written
    values the correction may list (material names, environments). The text
    is the historical message, so a caller that only knew ValueError reads
    what it always read. It is never an infrastructure failure: before
    dispatch it becomes REJECTED_BEFORE_DISPATCH, and at execution the task
    completes reporting REQUEST_REFUSED, with nothing run and no trial slot
    charged.
    """

    def __init__(self, code, field, message, choices=()):
        super().__init__(message)
        self.code, self.field, self.choices = code, field, tuple(choices)


def public_material_names(public_material):
    """The material names the bound material service serves, in order.

    The bound material service owns the allowlist. No arbitrary path, case
    coordinate, URL, evaluator query or hidden-role selector.
    """
    from .advection_research import MATERIAL as ADVECTION_MATERIAL
    from .advection_research import PublicAdvectionMaterial
    from .julia_envelope import MATERIAL as ENVELOPE
    from .julia_envelope import JuliaEnvelopeMaterial
    from .julia_research import MATERIAL, JuliaPublicMaterial

    names = [
        "objective",
        "capabilities",
        "training_data",
        "practice_data",
        "reference_method",
    ]
    if type(public_material) is JuliaPublicMaterial:
        names.append(MATERIAL)
    if type(public_material) is PublicAdvectionMaterial:
        names.append(ADVECTION_MATERIAL)
    if type(public_material) is JuliaEnvelopeMaterial:
        names += [MATERIAL, ENVELOPE]
    return tuple(dict.fromkeys(names))


def _refuse(code, field, message, choices=()):
    raise WorkspaceRequestRefused(code, field, message, choices)


def _workspace_name(value, field):
    from .research_workspace import is_workspace_name

    if not is_workspace_name(value):
        _refuse(
            "workspace_name_invalid",
            field,
            "workspace names are bounded flat identifiers, never paths",
        )


def _decoded(text):
    try:
        return base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        return None


def check_workspace_request(executor, action, args, *, state=True):
    """Refuse a workspace request's values before anything acts on them.

    Raises `WorkspaceRequestRefused` naming the first problem: its closed code,
    its registered field and the fix. One function for both callers - the
    request path before dispatch and the executor before it acts - so what is
    refused before dispatch is refused by the rule execution would apply.

    `state=False` skips the checks that read the workspace or the budget (a
    file exists, a write's expected digest, a compute-time budget): the
    request path does so when a task for this operation id already exists,
    so resending a started request returns that task rather than a refusal
    of a request that already ran. Checks only; nothing is written.
    """
    expected, optional = workspace_fields(action)
    if not expected <= set(args):
        missing = sorted(expected - set(args))
        _refuse(
            "workspace_field_missing",
            "arguments_json." + missing[0],
            "workspace fields differ from registered action",
        )
    if not set(args) <= expected | optional:
        _refuse(
            "workspace_field_unexpected",
            "arguments_json",
            "workspace fields differ from registered action",
        )
    workspace = getattr(executor, "workspace", None)
    if action == "public_material":
        names = public_material_names(executor.public_material)
        if args["name"] not in names:
            _refuse(
                "public_material_unknown",
                "arguments_json.name",
                "public material unavailable",
                names,
            )
    elif action == "read_file":
        _workspace_name(args["name"], "arguments_json.name")
        for name, low, high in (
            ("offset", 0, None),
            ("count", 1, READ_FILE_MAX_BYTES),
        ):
            value = args[name]
            if (
                type(value) is not int
                or value < low
                or (high is not None and value > high)
            ):
                _refuse(
                    "read_file_range",
                    "arguments_json." + name,
                    "bounded byte range required",
                )
        if state and workspace.current_digest(args["name"]) is None:
            _refuse(
                "workspace_file_missing",
                "arguments_json.name",
                "workspace artifact unavailable",
            )
    elif action == "write_file":
        _workspace_name(args["name"], "arguments_json.name")
        body = (
            _decoded(args["content_base64"])
            if type(args["content_base64"]) is str
            else None
        )
        if body is None:
            _refuse(
                "write_file_content_invalid",
                "arguments_json.content_base64",
                "base64 file content required",
            )
        expected_digest = args["expected_digest"]
        if expected_digest is not None and type(expected_digest) is not str:
            _refuse(
                "write_file_expected_digest_conflict",
                "arguments_json.expected_digest",
                "workspace compare-and-swap conflict",
            )
        if state:
            current = workspace.current_digest(args["name"])
            # Writing the bytes a file already holds succeeds whatever the
            # guard says, exactly as the workspace's own write does.
            if current != digest(body) and current != expected_digest:
                _refuse(
                    "write_file_expected_digest_conflict",
                    "arguments_json.expected_digest",
                    "workspace compare-and-swap conflict",
                )
    elif action == "notebook":
        if args["kind"] not in NOTEBOOK_KINDS:
            _refuse(
                "notebook_kind_unknown",
                "arguments_json.kind",
                "miner notebook kind unavailable",
                NOTEBOOK_KINDS,
            )
        from .miner_guidance import is_reserved

        if is_reserved(args["body"]):
            # Only the miner's own page writes a miner message (RSURF-D13).
            _refuse(
                "notebook_body_reserved",
                "arguments_json.body",
                "miner message schema is reserved",
            )
    elif action == "capability_request":
        from .research_workspace import capability_request_refusal

        refused = capability_request_refusal(
            args["request"], getattr(executor, "challenge", None)
        )
        if refused is not None:
            _refuse(*refused)
    elif action == "check_design":
        from .design_check import design_refusal

        refused = design_refusal(args["design"])
        if refused is not None:
            _refuse(*refused)
    elif action in RUN_ACTIONS:
        _check_run(executor, action, args, workspace, state=state)


def _check_run(executor, action, args, workspace, *, state):
    """`check_workspace_request` for the miner's own program."""
    for name in ("hypothesis", "expected_effect"):
        value = args[name]
        if type(value) is not str or not 1 <= len(value) <= RUN_TEXT:
            _refuse(
                "run_hypothesis_required",
                "arguments_json." + name,
                "prospective hypothesis and expected effect required",
            )
    if type(args["source"]) is not str or not args["source"]:
        _refuse(
            "run_source_required", "arguments_json.source", "research source required"
        )
    files = args["files"]
    if (
        type(files) is not list
        or any(type(name) is not str for name in files)
        or len(files) != len(set(files))
    ):
        _refuse(
            "run_files_invalid",
            "arguments_json.files",
            "distinct workspace selection required",
        )
    for name in files:
        _workspace_name(name, "arguments_json.files")
        if name in RESERVED_STAGE_NAMES:
            _refuse(
                "run_files_invalid",
                "arguments_json.files",
                "closed stage required",
                tuple(sorted(RESERVED_STAGE_NAMES)),
            )
    seconds = args.get("seconds")
    if seconds is not None and (type(seconds) is not int or seconds < 1):
        _refuse(
            "run_seconds_invalid",
            "arguments_json.seconds",
            "a positive wall allowance, or none",
        )
    if action == "run_julia":
        from .julia_analysis import DEFAULT_ENVIRONMENT, ENVIRONMENTS

        if args.get("environment", DEFAULT_ENVIRONMENT) not in ENVIRONMENTS:
            _refuse(
                "julia_environment_unknown",
                "arguments_json.environment",
                "environment must be one of: " + ", ".join(ENVIRONMENTS),
                ENVIRONMENTS,
            )
    from . import gpu_code_cell

    lane = getattr(executor, "gpu", None)
    code = gpu_code_cell.refusal(action, args, lane)
    if code is not None:
        # A device that cannot run (RSURF-D20); the two historical messages
        # are kept, every other is its code, as `gpu_code_cell.run` raises.
        _refuse(
            code,
            (
                "arguments_json.seconds"
                if code == "remote_gpu_seconds_required"
                else "arguments_json.device"
            ),
            {
                "device_choice_invalid": "device is cpu or gpu",
                "gpu_lane_not_configured": "this campaign has no GPU lane",
            }.get(code, code),
        )
    remote = args.get("device") == "gpu" and getattr(lane, "remote", None) is not None
    if remote and gpu_code_cell.WRAPPED in files:
        _refuse(
            "run_files_invalid",
            "arguments_json.files",
            gpu_code_cell.WRAPPED + " is the wrapper's own name",
            (gpu_code_cell.WRAPPED,),
        )
    if not state:
        return
    for name in files:
        if workspace.current_digest(name) is None:
            _refuse(
                "workspace_file_missing",
                "arguments_json.files",
                "workspace artifact unavailable",
            )
    if seconds is None and not remote:
        from .research_carrier import _has_time_budget

        if _has_time_budget(executor.ledger):
            # The miner's own budget still binds where they set one: a run
            # with no allowance could not be reserved against it.
            _refuse(
                "run_seconds_required",
                "arguments_json.seconds",
                "you set a compute-time budget; give this run a wall allowance",
            )


def refused_result(refused):
    """The task result for a workspace request refused at execution.

    The request path refuses these before dispatch; this is the same refusal
    for a request that reached the executor anyway (a raw protocol client, or
    a workspace that changed in between). Carbon examined the request and
    refused it: the task completes with this typed outcome, never as an
    infrastructure failure, and nothing ran or was charged.
    """
    from .research_tools import task_correction

    return {
        "outcome": "REQUEST_REFUSED",
        "correction_code": refused.code,
        "field": refused.field,
        "correction": task_correction(
            refused.code, refused.field, None, choices=refused.choices
        ),
        "nothing_ran": True,
        "trial_charged": False,
        "authority_granted": False,
    }


def workspace_fields(action):
    """The (required, optional) argument fields of one workspace action.

    The one table both the executor and the pre-dispatch check read, so a
    request refused for its fields before dispatch is refused by the same
    rule the executor would apply. Raises KeyError for an unknown action.
    """
    expected = {
        "public_material": {"name"},
        "inventory": set(),
        "read_file": {"name", "offset", "count"},
        "write_file": {"name", "content_base64", "expected_digest"},
        "notebook": {"kind", "body"},
        "capability_request": {"request"},
        "check_design": {"design"},
        "roadmap": set(),
        "run_python": {"source", "files", "hypothesis", "expected_effect"},
        "run_julia": {"source", "files", "hypothesis", "expected_effect"},
    }[action]
    # `environment` is run_julia's one optional field: which pinned package
    # environment to run in. For the miner's own scripts a wall allowance,
    # `seconds`, may be omitted for none at all. Every other field is
    # exactly required.
    optional = {"environment"} if action == "run_julia" else set()
    if action in {"run_python", "run_julia"}:
        # `device`: cpu (the default) or gpu, on the campaign's GPU lane
        # (RSURF-D20). Absent, a request means what it always has.
        optional = optional | {"seconds", "device"}
    return frozenset(expected), frozenset(optional)


def _arguments(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate workspace argument")
            result[key] = value
        return result

    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite workspace argument")
        ),
    )
    if type(value) is not dict or canonical(value).decode() != raw:
        raise ValueError("canonical closed workspace arguments required")
    return value


class PublicResearchExecutor:
    """Trusted owner-bound composition; it receives no wallet or API key."""

    def __init__(
        self,
        *,
        ledger,
        owner,
        image,
        public_material,
        practice,
        julia_image=None,
        cleanup_only=False,
        demand=None,
    ):
        self.ledger, self.owner, self.image = ledger, owner, image
        # This host's capability demand store, or None where it collects none.
        self.demand = demand
        self.workspace = ResearchWorkspace(ledger, owner)
        self.public_material, self.practice = public_material, practice
        self.julia_image = julia_image
        # The campaign's GPU lane for the code cell (RSURF-D20), set by its
        # composition from the frozen runtime; None runs every cell on CPU.
        self.gpu = None
        self.cleanup_only = cleanup_only
        if cleanup_only:
            ledger.retained_owner(owner)
        elif julia_image is not None:
            from .julia_analysis import authorize_julia

            authorize_julia(ledger, owner, julia_image)
        self.request_resolver = None
        with ledger.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
            )

    #: The Challenge this executor serves, by registry token: its registry
    #: answers capability requests, the roadmap and demand. Burgers' unless
    #: the composition says otherwise (battery's sets its own), as before
    #: Challenges were threaded through.
    challenge = None

    def _workspace_action(self, spec, identity):
        args = _arguments(spec.arguments_json)
        # The one value check the request path also reads before dispatch.
        check_workspace_request(self, spec.action, args)
        if spec.action == "public_material":
            result = self.public_material(args["name"], self.workspace)
            from .gpu_research import PublicGPUPractice

            if type(self.practice) is PublicGPUPractice:
                result = self.practice.projection(args["name"], result, self.workspace)
            return result
        if spec.action == "inventory":
            return {"files": self.workspace.inventory()}
        if spec.action == "read_file":
            return self._read_file(args)
        if spec.action == "write_file":
            from .research_workspace import WorkspaceConflict

            try:
                fingerprint = self.workspace.put(
                    args["name"],
                    base64.b64decode(args["content_base64"], validate=True),
                    expected_digest=args["expected_digest"],
                )
            except WorkspaceConflict:
                # Changed since the check, by another write: the same refusal.
                _refuse(
                    "write_file_expected_digest_conflict",
                    "arguments_json.expected_digest",
                    "workspace compare-and-swap conflict",
                )
            return {"name": args["name"], "digest": fingerprint}
        if spec.action == "notebook":
            self.ledger.note(owner=self.owner, kind=args["kind"], body=args["body"])
            return {"retained": True}
        if spec.action == "check_design":
            from .design_check import check_design

            # Compile-only: no execution and no trial charged. What it records
            # is demand: registry ids only, never the miner's own text.
            result = check_design(args["design"])
            if getattr(self, "demand", None) is not None:
                from .capability_demand import demanded

                ids, unrecognized = demanded(result, self.challenge)
                self.demand.record(
                    self.owner,
                    ids,
                    unrecognized=unrecognized,
                    challenge=self.challenge,
                )
            return result
        if spec.action == "roadmap":
            from .capability_demand import public_roadmap

            return public_roadmap(getattr(self, "demand", None), self.challenge)
        if spec.action == "capability_request":
            record = request_capability(
                self.ledger,
                owner=self.owner,
                request=args["request"],
                challenge=self.challenge,
            )
            if getattr(self, "demand", None) is not None and "capability" in record:
                self.demand.record(
                    self.owner, [record["capability"]], challenge=self.challenge
                )
            return record
        files = self._staged(args["files"])
        self.ledger.note(
            owner=self.owner,
            kind="hypothesis",
            body={
                "task": identity,
                "hypothesis": args["hypothesis"],
                "expected_effect": args["expected_effect"],
            },
        )
        if args.get("device", "cpu") == "gpu":
            from . import gpu_code_cell

            # run_julia on gpu: this machine's GPU, in a CUDA environment
            # (JULIA-GPU-01); gpu_code_cell refuses every other case by name.
            return gpu_code_cell.run(
                self,
                identity=identity,
                args=args,
                files=files,
                action=spec.action,
            )
        runner, image, selection = run_script, self.image, {}
        if spec.action == "run_julia":
            from .julia_analysis import DEFAULT_ENVIRONMENT, run_julia

            runner, image = run_julia, self.julia_image
            selection = {"environment": args.get("environment", DEFAULT_ENVIRONMENT)}
        try:
            result = runner(
                self.ledger,
                owner=self.owner,
                identity=identity,
                source=args["source"],
                files=files,
                image=image,
                seconds=args.get("seconds"),
                **selection,
            )
        except MinerProgramFailure as failure:
            # The miner's program failed, observed, with cleanup observed and
            # the full reservation kept. Carbon executed the request, so the
            # task completes and reports the typed miner-caused outcome; it is
            # never relabelled as an infrastructure failure, and it carries no
            # scientific claim (workspace records stay STRUCTURAL_ONLY).
            return {
                "provenance": "MINER_SELF_REPORTED",
                "outcome": "MINER_PROGRAM_FAILED",
                "worker": failure.result,
                "workspace_exports": [],
                "program_output": self.program_output(failure.result),
            }
        return {
            "provenance": "MINER_SELF_REPORTED",
            "worker": result,
            "workspace_exports": self.export(identity, result),
            "program_output": self.program_output(result),
        }

    def _staged(self, names):
        """The run's own files, read once; a file gone since the check is the
        same refusal, never an infrastructure failure."""
        from .research_workspace import WorkspaceFileMissing

        try:
            return self.workspace.snapshot(names)
        except WorkspaceFileMissing:
            _refuse(
                "workspace_file_missing",
                "arguments_json.files",
                "workspace artifact unavailable",
            )

    def _read_file(self, args):
        """One bounded slice of an own file: base64 always, and the same bytes
        as text in `content_utf8` when they are UTF-8 (null when not)."""
        from .research_workspace import WorkspaceFileMissing

        offset, count = args["offset"], args["count"]
        try:
            body = self.workspace.get(args["name"])
        except WorkspaceFileMissing:
            _refuse(
                "workspace_file_missing",
                "arguments_json.name",
                "workspace artifact unavailable",
            )
        chunk = body[offset : offset + count]
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        return {
            "name": args["name"],
            "digest": digest(body),
            "bytes": len(body),
            "offset": offset,
            "content_base64": base64.b64encode(chunk).decode("ascii"),
            "content_utf8": text,
        }

    def program_output(self, worker):
        """The bounded tails of what the program printed, for its result."""
        from .research_carrier import program_output

        worker = worker if type(worker) is dict else {}
        return program_output(
            self.ledger,
            worker.get("operation"),
            observation=worker.get("observation"),
        )

    def export(self, identity, result, *, skip=frozenset()):
        """Import only the bounded validated export into the owner's scratch
        space. No path from miner output is ever interpreted as a host source
        path. `skip` names files that are the carrier's, not the program's."""
        snapshot = self.ledger.root / result["operation"] / "snapshot"
        exported = []
        for relative, fingerprint in result["files"].items():
            if "/" in relative or relative in skip:
                continue  # nested checkpoint bundles remain retained by task
            body = (snapshot / relative).read_bytes()
            if digest(body) != fingerprint:
                record_output_tamper(
                    self.ledger,
                    owner=self.owner,
                    operation=result["operation"],
                    name=relative,
                    expected=fingerprint,
                    observed=digest(body),
                )
            name = identity[-20:] + "-" + relative
            if len(body) <= 8 * 1024**2 and len(name) <= 96:
                self.workspace.put(name, body)
                exported.append(name)
        return exported

    def cancel(self, identity):
        request_cancel(self.ledger, owner=self.owner, identity=identity)

    def execute(self, attempt):
        if self.cleanup_only:
            raise ValueError("cleanup-only executor cannot admit research")
        token = ACTIVE_TASK.set(attempt.task_id.value)
        try:
            return self._execute(attempt)
        finally:
            ACTIVE_TASK.reset(token)

    def _execute(self, attempt):
        request = self.request_resolver(attempt.task_id)
        spec = request.task_spec
        identity = attempt.task_id.value
        if type(spec) in (
            DevelopmentWorkspaceTaskSpecV1,
            DevelopmentWorkspaceTaskSpecV2,
        ):
            try:
                result = self._workspace_action(spec, identity)
            except WorkspaceRequestRefused as refused:
                # The requester's values, refused before anything acted on
                # them: a typed outcome, never an infrastructure failure.
                result = refused_result(refused)
            evidence = ResearchEvidenceClass.STRUCTURAL_ONLY
        elif type(spec) is PracticeTaskSpec:
            # The practice adapter supplies trusted labels/randomness and the
            # catalog compiler; the requester supplies only a registered recipe.
            result = self.practice(identity, spec.strategy)
            evidence = ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
        else:
            raise ValueError("task kind unavailable in real D4 provider")
        body = canonical(result)
        if len(body) > 1024**2:
            raise ValueError("bounded public result required")
        fingerprint = digest(body)
        with self.ledger.db() as db:
            prior = db.execute(
                "SELECT body FROM research_results WHERE owner=? AND task=?",
                (self.owner, identity),
            ).fetchone()
            if prior and prior[0] != body:
                raise ValueError("research result replay conflict")
            db.execute(
                "INSERT OR IGNORE INTO research_results VALUES(?,?,?,?)",
                (self.owner, identity, body, fingerprint),
            )
        origin = PrivateIdentityRef("research_evidence_origin", fingerprint)
        return AuthorizedResearchOutcome(
            evidence,
            EvidenceContext(
                EvidenceRole.NUMERICAL,
                origin,
                None,
                None,
                None,
                (),
                None,
                None,
                ResearchCensoringStatus.NOT_APPLICABLE,
                EvidenceQualityMetadata(),
            ),
            RetentionReuseBinding(ResearchRetentionScope.LOCAL_PRIVATE_ONLY),
            (),
            (PrivateIdentityRef("research_result", fingerprint),),
            None,
            (),
        )

    def public_result(self, task):
        # Called only after B-07 confirms an owned terminal task and the
        # authenticated gateway confirms this executor's requester binding.
        if task.state is not ResearchTaskState.SUCCEEDED:
            return None
        with self.ledger.db() as db:
            row = db.execute(
                "SELECT body,digest FROM research_results WHERE owner=? AND task=?",
                (self.owner, task.task_id.value),
            ).fetchone()
        if row is None or digest(row[0]) != row[1]:
            raise ValueError("owned research result unavailable")
        return {
            "schema": "carbon.autoresearch.public-result.v1",
            "task_id": task.task_id.value,
            "receipt_digest": digest(canonical_bytes(task.terminal_receipt)),
            "result_digest": row[1],
            "result": json.loads(row[0]),
            "official_eligible": False,
        }
