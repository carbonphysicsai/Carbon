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
import binascii
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from carbon.authoring.model import EvidenceRole
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from carbon.research import (
    CancellationDisposition,
    DevelopmentWorkspaceTaskSpecV1,
    DevelopmentWorkspaceTaskSpecV2,
    DirectCancelTaskRequestV3,
    DirectCancelTaskResultV3,
    DirectGetTaskRequestV3,
    DirectGetTaskResultV3,
    DirectPracticeTaskSpecV1,
    DirectStartTaskRequestV3,
    DirectStartTaskResultV3,
    DirectTaskBindingsV3,
    DirectTaskReceiptV3,
    DirectTaskStateV3,
    DirectTaskViewV3,
    PracticeTaskSpec,
    ResearchTaskKind,
    ResearchTaskState,
    StartResearchTaskRequest,
    canonical_bytes,
    load_canonical,
)
from carbon.research.durable import DurableResearchTaskProvider
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError
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

from .construction_recipe import ConstructionRecipe
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

    def _resolve_start(self, request):
        if (
            type(request.task_spec) is DirectPracticeTaskSpecV1
            and getattr(self._executor.executor.practice, "construction_mode", None)
            != "direct"
        ):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        return super()._resolve_start(request)

    @staticmethod
    def _spec_parts(request):
        if type(request.task_spec) is DevelopmentWorkspaceTaskSpecV1:
            return ResearchTaskKind.DEVELOPMENT_WORKSPACE_V1, (), (), ()
        if type(request.task_spec) is DevelopmentWorkspaceTaskSpecV2:
            return ResearchTaskKind.DEVELOPMENT_WORKSPACE_V2, (), (), ()
        if type(request.task_spec) is DirectPracticeTaskSpecV1:
            recipe = request.task_spec.recipe
            challenge = recipe["challenge"]
            if (
                challenge["id"] != request.challenge_key.challenge_id
                or challenge["version"] != request.challenge_key.version
            ):
                raise ValueError("direct recipe Challenge differs from task")
            return ResearchTaskKind.DIRECT_PRACTICE, (), (), ()
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


class DirectDevelopmentTasksV3:
    """Durable public-development direct tasks beside the historical v2 store.

    This provider owns task state and both C-03 child operations. Its public
    binding is Challenge material, while image and effective controls remain
    private execution evidence. There is deliberately no injected runner or
    generic completion callback in this normal task path.
    """

    _LIMITATIONS = (
        "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
        "NOT_OFFICIAL_EVIDENCE",
        "NOT_SCIENTIFICALLY_QUALIFIED",
    )
    _EXPORT_OP = re.compile(
        rb"(?m)^carbon\.level4\.graph\.GraphRefused: "
        rb"aten_op_(?:not_lowered|not_allowlisted) at "
        rb"(aten\.[A-Za-z_][A-Za-z_0-9]{0,63}\."
        rb"[A-Za-z_][A-Za-z_0-9]{0,63})\r?$"
    )
    _SCATTER_INDEX_OP = re.compile(
        rb"(?m)^carbon\.level4\.graph\.GraphRefused: "
        rb"aten_scatter_index_not_static at (aten\.scatter_add\.default)\r?$"
    )

    def __init__(
        self,
        *,
        root: Path,
        requester: str,
        ledger,
        owner: str,
        discovery,
        image=None,
        inference_image,
        image_resolver=None,
        construction_parent=None,
        construction_parents=None,
        evaluation_pack_digest=None,
    ) -> None:
        from .gpu_practice import DirectParents

        # Two CPU construction parents (OWNER-BACKBONE-CATALOG-01): each bundle
        # task builds on its pinned runtime's parent, never a miner's choice.
        if construction_parents is not None and (
            type(construction_parents) is not DirectParents
            or not construction_parents.runtimes()
            or construction_parent is not None
            or image is not None
            or image_resolver is None
        ):
            raise ValueError("per-runtime parents need the per-recipe resolver")
        if (
            not isinstance(root, Path)
            or not root.is_absolute()
            or root.is_symlink()
            or type(requester) is not str
            or not requester
            or type(owner) is not str
            or not owner
            or evaluation_pack_digest
            != getattr(discovery, "evaluation_pack_digest", None)
            or (
                evaluation_pack_digest is not None
                and (
                    type(evaluation_pack_digest) is not str
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", evaluation_pack_digest)
                    is None
                )
            )
        ):
            raise ValueError("private direct task root and requester required")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self._path = root / "direct-tasks.sqlite3"
        if self._path.is_symlink():
            raise ValueError("symlink direct task store rejected")
        import fcntl

        self._lease = (root / "direct-supervisor.lock").open("a+b")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise ValueError("direct research supervisor already active") from None
        self._lock = threading.RLock()
        self.ledger, self.owner = ledger, owner
        self.discovery = discovery
        self.evaluation_pack_digest = evaluation_pack_digest
        self.image, self.inference_image = image, inference_image
        self.image_resolver = image_resolver
        self.construction_parents = construction_parents
        self.construction_parent = (
            None
            if construction_parents is not None
            else (
                construction_parent
                if construction_parent is not None
                else image.parent if image is not None else inference_image
            )
        )
        self._requests: dict[str, DirectStartTaskRequestV3] = {}
        self._views: dict[str, DirectTaskViewV3] = {}
        self._task_image_bindings: dict[str, str] = {}
        self._measured_tasks: set[str] = set()
        self._idempotency: dict[str, str] = {}
        self._cancellations: dict[str, str | None] = {}
        try:
            self._check_image_identity()
            with self._db() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS direct_binding (
                        id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL,
                        entropy BLOB NOT NULL);
                    CREATE TABLE IF NOT EXISTS direct_tasks (
                        id TEXT PRIMARY KEY, request BLOB NOT NULL,
                        view BLOB NOT NULL, cancellation TEXT);
                    CREATE TABLE IF NOT EXISTS direct_evidence (
                        id TEXT PRIMARY KEY REFERENCES direct_tasks(id),
                        body BLOB NOT NULL);
                    CREATE TABLE IF NOT EXISTS direct_task_images (
                        id TEXT PRIMARY KEY REFERENCES direct_tasks(id),
                        identity TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS direct_task_sources (
                        id TEXT PRIMARY KEY REFERENCES direct_tasks(id),
                        body BLOB NOT NULL, digest TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS direct_task_measurements (
                        id TEXT PRIMARY KEY REFERENCES direct_tasks(id),
                        profile TEXT NOT NULL);
                """)
                binding = (
                    json.dumps(
                        [
                            requester,
                            owner,
                            "PER_RECIPE_LIBRARY_IMAGE",
                            inference_image.image_id,
                            *(
                                (
                                    [self.construction_parent.image_id]
                                    if self.construction_parent != inference_image
                                    else []
                                )
                                if construction_parents is None
                                else [
                                    item
                                    for runtime in construction_parents.runtimes()
                                    for item in (
                                        "CONSTRUCTION_PARENT",
                                        runtime,
                                        construction_parents.for_runtime(
                                            runtime
                                        ).image_id,
                                    )
                                ]
                            ),
                            *(
                                ["EVALUATION_PACK", evaluation_pack_digest]
                                if evaluation_pack_digest is not None
                                else []
                            ),
                        ],
                        separators=(",", ":"),
                    )
                    if image_resolver is not None
                    else json.dumps(
                        [
                            requester,
                            owner,
                            image.image_id,
                            image.parent.image_id,
                            inference_image.image_id,
                            image.bundle_ref,
                            *(
                                ["EVALUATION_PACK", evaluation_pack_digest]
                                if evaluation_pack_digest is not None
                                else []
                            ),
                        ],
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                row = db.execute(
                    "SELECT identity,entropy FROM direct_binding WHERE id=1"
                ).fetchone()
                if row is None:
                    row = (binding, os.urandom(32))
                    db.execute("INSERT INTO direct_binding VALUES(1,?,?)", row)
                if row[0] != binding:
                    raise ValueError("direct requester or image binding changed")
                self._entropy = row[1]
                retained = db.execute(
                    "SELECT id,request,view,cancellation FROM direct_tasks ORDER BY id"
                ).fetchall()
                retained_images = dict(
                    db.execute("SELECT id,identity FROM direct_task_images").fetchall()
                )
                retained_sources = {
                    row[0] for row in db.execute("SELECT id FROM direct_task_sources")
                }
                retained_measurements = dict(
                    db.execute("SELECT id,profile FROM direct_task_measurements")
                )
            self._path.chmod(0o600)
            for identity, request_bytes, view_bytes, cancellation in retained:
                request = load_canonical(request_bytes, DirectStartTaskRequestV3)
                view = load_canonical(view_bytes, DirectTaskViewV3)
                if (
                    identity != view.task_id.value
                    or self._task_id(request).value != identity
                    or self._bindings(request) != view.immutable_bindings
                ):
                    raise ValueError("retained direct task binding conflict")
                self._requests[identity] = request
                self._views[identity] = view
                if identity in retained_measurements:
                    if retained_measurements[identity] != "COLD_QUERY_V2":
                        raise ValueError("retained direct measurement profile differs")
                    self._measured_tasks.add(identity)
                source_kind = request.recipe["source"]["kind"]
                if image_resolver is not None or source_kind == "graph":
                    if identity not in retained_images:
                        raise ValueError("retained direct task image binding missing")
                    self._task_image_bindings[identity] = retained_images[identity]
                if source_kind == "graph":
                    self._source_envelope(
                        identity, ConstructionRecipe.from_dict(request.recipe)
                    )
                elif identity in retained_sources:
                    raise ValueError("retained bundle task has graph source bytes")
                self._idempotency[request.idempotency_key] = identity
                self._cancellations[identity] = cancellation
                if view.state is DirectTaskStateV3.SUCCEEDED:
                    self._verified_success_evidence(view)
                elif view.state is DirectTaskStateV3.FAILED_INFRA:
                    self._verified_failure_evidence(view)
            self._reconcile_interrupted()
            expected_image_bindings = {
                identity
                for identity, request in self._requests.items()
                if image_resolver is not None
                or request.recipe["source"]["kind"] == "graph"
            }
            if set(retained_images) != expected_image_bindings or retained_sources != {
                identity
                for identity, request in self._requests.items()
                if request.recipe["source"]["kind"] == "graph"
            }:
                raise ValueError("retained direct task image binding differs")
            if set(retained_measurements) - set(self._requests):
                raise ValueError("retained direct measurement task missing")
            # Retained children are cleaned before a live image doctor can
            # reject new admission after a crash.
            self._verify_images()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if not self._lease.closed:
            self._lease.close()

    def _check_image_identity(self) -> None:
        from carbon.reconstruction.worker.model import WorkerImageIdentity

        from .gpu_practice import direct_bundle_accelerators
        from .research_image import LibraryWorkerImage

        parents = (
            [self.construction_parent]
            if self.construction_parents is None
            else [
                self.construction_parents.for_runtime(runtime)
                for runtime in self.construction_parents.runtimes()
            ]
        )
        if type(self.inference_image) is not WorkerImageIdentity or any(
            type(parent) is not WorkerImageIdentity for parent in parents
        ):
            raise ValueError("exact C-03 library child and parent images required")
        if self.image_resolver is not None:
            if self.image is not None or not callable(self.image_resolver):
                raise ValueError("one trusted per-recipe library resolver required")
        elif (
            type(self.image) is not LibraryWorkerImage
            or self.image.parent != self.construction_parent
        ):
            raise ValueError("exact C-03 library child and parent images required")
        accelerators = {
            direct_bundle_accelerators(parent, self.inference_image)
            for parent in parents
        }
        if len(accelerators) != 1:
            raise ValueError("construction parents differ in accelerator")
        self.build_accelerator, self.inference_accelerator = accelerators.pop()

    def _parent_for(self, bundle):
        """The construction parent for `bundle`: its pinned runtime's alone.

        An unregistered runtime is refused (`construction_runtime_unknown`); a
        registered one whose parent is not installed is `backend_not_served`.
        """
        if self.construction_parents is None:
            return self.construction_parent
        return self.construction_parents.for_bundle(bundle)

    def _verify_images(self) -> None:
        from .research_image import verify_library_worker_image

        self._check_image_identity()
        if self.image_resolver is None:
            verify_library_worker_image(self.image)

    def _resolved_image(self, request):
        """Resolve only a recipe ref; runtime verifies the selected child anew."""
        from .construction_recipe import ConstructionRecipe
        from .direct_graph_construction_worker import graph_adapter_ids
        from .library_bundles import LibraryBundleRef
        from .research_image import LibraryWorkerImage, verify_library_worker_image

        recipe = ConstructionRecipe.from_dict(request.recipe)
        source = recipe.to_dict()["source"]
        if source["kind"] == "graph":
            adapter = getattr(self.discovery, "graph_adapter_for", None)
            if not callable(adapter) or (
                adapter(request.challenge_key) not in graph_adapter_ids()
            ):
                raise ValueError("direct graph adapter unavailable for Challenge")
            return self.inference_image
        if source["kind"] != "bundle":
            raise ValueError("direct task source unavailable")
        if self.image_resolver is None:
            return self.image
        bundle = LibraryBundleRef.from_dict(source["bundle_ref"])
        parent = self._parent_for(bundle)
        image = self.image_resolver(bundle)
        if (
            type(image) is not LibraryWorkerImage
            or image.bundle_ref != source["bundle_ref"]
            or image.parent != parent
        ):
            raise ValueError("resolved library worker identity differs")
        verify_library_worker_image(image)
        return image

    def _inspected_source_binding(self, request):
        """Check staged bundle bytes without resolving or building an image."""
        from .library_bundles import LibraryBundleRef

        source = request.recipe["source"]
        bundle = LibraryBundleRef.from_dict(source["bundle_ref"])
        self._parent_for(bundle)
        inspected = self.image_resolver.inspect_source(bundle)
        if inspected != bundle:
            raise ValueError("inspected direct bundle source differs")
        return json.dumps(
            ["BUNDLE_SOURCE", bundle.to_dict()],
            sort_keys=True,
            separators=(",", ":"),
        )

    def _provision_admitted_image(self, request, *, deadline: float):
        """Resolve a child or prepare exact dependencies after durable admission."""
        from carbon.reconstruction.worker.docker_runtime import DockerCLI

        from .bundle_construction_worker import (
            direct_child_identity,
            prepare_library_overlay,
        )
        from .construction_recipe import ConstructionRecipe, RecipeRefused
        from .library_bundles import (
            LibraryBundleRef,
            load_pinned_bundle_directory,
            verify_bundle_parent_environment,
        )
        from .library_environment_cache import (
            cache_verified_overlay,
            inspect_staged_bundle_material,
        )
        from .research_image import LibraryWorkerImage, verify_library_worker_image

        bundle = LibraryBundleRef.from_dict(request.recipe["source"]["bundle_ref"])
        parent = self._parent_for(bundle)
        task = self._task_id(request)

        def check_cancel():
            with self._lock:
                current = self._views.get(task.value)
                if current is None or current.state is not DirectTaskStateV3.RUNNING:
                    raise ValueError(
                        "direct task cancelled during dependency preparation"
                    )
            if time.monotonic() >= deadline:
                raise RecipeRefused("construction_total_deadline_reached")

        check_cancel()
        # Check original staged bytes against the actual registered parent
        # before the resolver can return a cached child. A cache hit must not
        # bypass the source's declared base environment.
        directory = inspect_staged_bundle_material(
            self.image_resolver.cache_root, bundle
        )
        material = load_pinned_bundle_directory(directory)
        verify_bundle_parent_environment(material[0], parent)
        check_cancel()
        # A library child has no registered GPU lock/profile fields. A GPU
        # bundle must use the checked parent plus a verified source overlay,
        # even when a CPU-style child image happens to be cached.
        image = None
        if self.build_accelerator is None:
            try:
                image = self.image_resolver.provision_admitted(
                    bundle, parent=parent, cli=DockerCLI()
                )
            except FileNotFoundError as error:
                if str(error) != (
                    "bounded automatic dependency build unavailable; verified child missing"
                ):
                    raise
        if image is not None:
            if (
                type(image) is not LibraryWorkerImage
                or image.bundle_ref != bundle.to_dict()
                or image.parent != parent
            ):
                raise ValueError("provisioned direct library image differs")
            verify_library_worker_image(image)
            return image
        capacity = getattr(self.image_resolver, "material_cache_bytes", None)
        if type(capacity) is not int or capacity < 1:
            raise ValueError("trusted overlay cache capacity unavailable")
        check_cancel()
        kit = self.discovery._material["construction_kit"]
        binding = {
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        }
        remaining = int(deadline - time.monotonic())
        if remaining < 40:
            raise RecipeRefused("construction_total_deadline_reached")
        prep = prepare_library_overlay(
            self.ledger,
            owner=self.owner,
            identity=direct_child_identity(task.value, "prep"),
            parent=parent,
            recipe=ConstructionRecipe.from_dict(request.recipe),
            challenge_binding=binding,
            limits_document=self.discovery._material["construction_limits_document"],
            material=material,
            seconds=min(600, remaining),
            deadline=deadline,
            cancel=check_cancel,
            **(
                {}
                if self.build_accelerator is None
                else {"accelerator": self.build_accelerator}
            ),
        )
        if prep.controls_digest is None:
            raise ValueError("completed C03 preparation controls unavailable")
        overlay = cache_verified_overlay(
            prep.snapshot,
            self.image_resolver.cache_root,
            expected_bundle=bundle,
            expected_parent=parent,
            expected_receipt=prep.receipt,
            material_cache_bytes=capacity,
            deadline=deadline,
            cancel=check_cancel,
        )
        return overlay, prep

    @staticmethod
    def _image_binding(image):
        from dataclasses import asdict

        from carbon.reconstruction.worker.model import WorkerImageIdentity

        from .library_environment_cache import VerifiedLibraryOverlay

        if type(image) is WorkerImageIdentity:
            return json.dumps(
                ["GRAPH_PARENT", asdict(image)],
                sort_keys=True,
                separators=(",", ":"),
            )

        if type(image) is VerifiedLibraryOverlay:
            return json.dumps(
                [
                    "BUNDLE_OVERLAY",
                    {
                        "parent_image_id": image.parent_image_id,
                        "bundle_ref": image.bundle_ref.to_dict(),
                        "tree_digest": image.tree_digest,
                        "archive_digest": image.archive_digest,
                    },
                ],
                sort_keys=True,
                separators=(",", ":"),
            )

        return json.dumps(
            [
                image.image_id,
                asdict(image.parent),
                image.bundle_ref,
                image.provisioned.context_digest,
            ],
            sort_keys=True,
            separators=(",", ":"),
        )

    def _db(self):
        from contextlib import contextmanager

        @contextmanager
        def opened():
            if self._lease.closed:
                raise ValueError("direct supervisor closed")
            db = sqlite3.connect(self._path, timeout=10)
            db.execute("PRAGMA synchronous=FULL")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

        return opened()

    def _source_envelope(self, identity: str, recipe: ConstructionRecipe) -> bytes:
        """Read charged immutable source bytes, never mutable workspace names."""
        from .construction_recipe import recipe_graph_bounds
        from .direct_graph_construction_worker import _checked_envelope

        if recipe.to_dict()["source"]["kind"] != "graph":
            raise ValueError("direct task has no graph source")
        bound = recipe_graph_bounds(recipe)["submission_bytes"]
        with self._db() as db:
            row = db.execute(
                "SELECT body,digest FROM direct_task_sources WHERE id=?", (identity,)
            ).fetchone()
        if row is None or row[0] != b"" or type(row[1]) is not str:
            raise ValueError("retained direct graph source differs")
        path = self._source_path(identity)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * bound:
            raise ValueError("retained direct graph source differs")
        body = path.read_bytes()
        if digest(body) != row[1]:
            raise ValueError("retained direct graph source differs")
        try:
            return _checked_envelope(recipe, body)
        except ValueError:
            raise ValueError("retained direct graph source differs") from None

    def _source_path(self, identity: str) -> Path:
        """Keep frozen graph bytes under the ledger's existing storage meter."""
        folder = self.ledger.root / "direct-task-sources"
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError("retained direct graph source directory differs")
        folder.mkdir(mode=0o700, exist_ok=True)
        folder.chmod(0o700)
        return folder / (hashlib.sha256(identity.encode("utf-8")).hexdigest() + ".json")

    def _retain_source(self, identity: str, source_envelope: bytes) -> None:
        """Admit and atomically retain each new task's bytes inside the ledger."""
        path = self._source_path(identity)
        if path.is_symlink():
            raise ValueError("retained direct graph source differs")
        if path.exists():
            if (
                not path.is_file()
                or path.stat().st_size != len(source_envelope)
                or path.read_bytes() != source_envelope
            ):
                raise ValueError("retained direct graph source differs")
            self.ledger.check_storage(65536)
            return
        self.ledger.check_storage(len(source_envelope) + 65536)
        staged = path.with_name(path.name + "." + os.urandom(8).hex() + ".staging")
        handle = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(source_envelope)
                out.flush()
                os.fsync(out.fileno())
            os.replace(staged, path)
        finally:
            staged.unlink(missing_ok=True)
        if path.is_symlink() or path.read_bytes() != source_envelope:
            raise ValueError("retained direct graph source differs")
        try:
            self.ledger.check_storage(65536)
        except BaseException:
            # This exact task has no DB row yet; do not leave a newly staged
            # over-budget object available to a later admission attempt.
            path.unlink()
            raise

    def _bindings(self, request: DirectStartTaskRequestV3) -> DirectTaskBindingsV3:
        from carbon.development_session.bundle_construction_worker import (
            verify_direct_resource_policy,
        )
        from carbon.development_session.construction_recipe import (
            ConstructionRecipe,
            bind_recipe,
        )
        from carbon.research import canonical_digest

        from .direct_graph_construction_worker import graph_adapter_ids

        info, manifest = self.discovery._checked(request.challenge_key)
        material = self.discovery._material
        kit = material["construction_kit"]
        policy = material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        expected = (
            canonical_digest(info),
            canonical_digest(manifest),
            digest(canonical(kit)),
            info.public_train_digest,
            info.practice_inputs_digest,
            info.interface_digest,
            info.construction_limits_digest,
            digest(canonical(policy)),
        )
        actual = (
            request.challenge_info_digest,
            request.manifest_digest,
            request.construction_kit_digest,
            request.public_train_digest,
            request.practice_inputs_digest,
            request.interface_digest,
            request.construction_limits_digest,
            request.resource_policy_digest,
        )
        if actual != expected:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        binding = {
            "challenge_id": request.challenge_key.challenge_id,
            "challenge_version": request.challenge_key.version,
            "train_digest": info.public_train_digest,
            "interface_digest": info.interface_digest,
            "construction_limits_digest": info.construction_limits_digest,
        }
        recipe = bind_recipe(request.recipe, **binding)
        source = recipe.to_dict()["source"]
        graph_adapter = getattr(self.discovery, "graph_adapter_for", None)
        if (
            # A catalog recipe runs as the Carbon bundle it names, expanded at
            # the door (`backbone_catalog.served.expand`); never here as itself.
            source["kind"] not in ("graph", "bundle")
            or (
                source["kind"] == "graph"
                and (
                    not callable(graph_adapter)
                    or graph_adapter(request.challenge_key) not in graph_adapter_ids()
                )
            )
            or (
                source["kind"] == "bundle"
                and self.image_resolver is None
                and source["bundle_ref"] != self.image.bundle_ref
            )
            or verify_direct_resource_policy(
                binding, material["construction_limits_document"]
            )
            != info.construction_limits_digest
        ):
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        return DirectTaskBindingsV3(
            request.challenge_key,
            ConstructionRecipe.from_dict(request.recipe).digest,
            *actual,
        )

    def _task_id(self, request: DirectStartTaskRequestV3):
        from carbon.research.refs import ResearchTaskId

        body = canonical_bytes(request)
        hashed = hashlib.sha256(
            b"CARBON-DIRECT-TASK-V3\0" + self._entropy + body
        ).hexdigest()
        return ResearchTaskId("rtsk_" + hashed)

    def _save(
        self,
        request: DirectStartTaskRequestV3,
        view: DirectTaskViewV3,
        cancellation: str | None = None,
        image_binding: str | None = None,
        failure_evidence: dict | None = None,
        source_envelope: bytes | None = None,
        measure_query: bool = False,
    ) -> None:
        if cancellation is None:
            cancellation = self._cancellations.get(view.task_id.value)
        with self._db() as db:
            db.execute(
                """INSERT INTO direct_tasks VALUES(?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    request=excluded.request,
                    view=excluded.view,
                    cancellation=excluded.cancellation""",
                (
                    view.task_id.value,
                    canonical_bytes(request),
                    canonical_bytes(view),
                    cancellation,
                ),
            )
            if image_binding is not None:
                db.execute(
                    "INSERT INTO direct_task_images VALUES(?,?)",
                    (view.task_id.value, image_binding),
                )
            if source_envelope is not None:
                db.execute(
                    "INSERT INTO direct_task_sources VALUES(?,?,?)",
                    (view.task_id.value, b"", digest(source_envelope)),
                )
            if measure_query:
                db.execute(
                    "INSERT INTO direct_task_measurements VALUES(?,?)",
                    (view.task_id.value, "COLD_QUERY_V2"),
                )
            if failure_evidence is not None:
                db.execute(
                    "INSERT INTO direct_evidence VALUES(?,?)",
                    (view.task_id.value, canonical(failure_evidence)),
                )
        self._views[view.task_id.value] = view
        if image_binding is not None:
            self._task_image_bindings[view.task_id.value] = image_binding
        self._cancellations[view.task_id.value] = cancellation
        if measure_query:
            self._measured_tasks.add(view.task_id.value)

    def start_research_task(self, request, *, measure_query=False):
        from carbon.research.refs import ResearchTaskId

        from .gpu_practice import DirectParentRefused
        from .research_ledger import LedgerRefusal

        if (
            type(request) is not DirectStartTaskRequestV3
            or type(measure_query) is not bool
        ):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        with self._lock:
            bindings = self._bindings(request)
            if measure_query:
                from carbon.challenge_kit.interface_dtype import output_dtype

                try:
                    declared = output_dtype(
                        self.discovery._material.get("interface_document", {})
                    )
                except ValueError:
                    declared = None
                if type(declared) is not str or not declared:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
            prior = self._idempotency.get(request.idempotency_key)
            if prior is not None:
                if (
                    self._requests[prior] != request
                    or (prior in self._measured_tasks) != measure_query
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                    )
                return DirectStartTaskResultV3(False, self._views[prior])
            if len(self._views) >= 256:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
            try:
                self._verify_images()
                staged_source = (
                    self.image_resolver is not None
                    and callable(getattr(self.image_resolver, "inspect_source", None))
                    and callable(
                        getattr(self.image_resolver, "provision_admitted", None)
                    )
                    and request.recipe["source"]["kind"] == "bundle"
                )
                image_binding = (
                    self._inspected_source_binding(request) if staged_source else None
                )
                image = None if staged_source else self._resolved_image(request)
                source_envelope = None
                if request.recipe["source"]["kind"] == "graph":
                    from .construction_recipe import graph_envelope_from_workspace
                    from .direct_graph_construction_worker import _checked_envelope

                    recipe = ConstructionRecipe.from_dict(request.recipe)
                    source_envelope = _checked_envelope(
                        recipe,
                        graph_envelope_from_workspace(self.ledger, self.owner, recipe),
                    )
            except DirectParentRefused as refused:
                # A registered runtime without its parent here is a capability
                # gap; an unregistered runtime is the miner's mismatch.
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
                    if refused.code == "backend_not_served"
                    else ResearchServiceErrorCode.REFERENCE_MISMATCH
                ) from None
            except FileNotFoundError:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_NOT_FOUND
                ) from None
            except ValueError:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_MISMATCH
                ) from None
            except (OSError, WorkerFailure):
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
                ) from None
            task_id: ResearchTaskId = self._task_id(request)
            if source_envelope is not None:
                try:
                    self._retain_source(task_id.value, source_envelope)
                except LedgerRefusal:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.BOUND_EXCEEDED
                    ) from None
                except ValueError:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    ) from None
                except OSError:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
                    ) from None
            now = time.time_ns() // 1000
            view = DirectTaskViewV3(
                task_id,
                request.challenge_key,
                DirectTaskStateV3.QUEUED,
                0,
                now,
                now,
                bindings,
                None,
            )
            self._save(
                request,
                view,
                image_binding=(
                    image_binding
                    if staged_source
                    else (
                        self._image_binding(image)
                        if self.image_resolver is not None
                        or request.recipe["source"]["kind"] == "graph"
                        else None
                    )
                ),
                source_envelope=source_envelope,
                measure_query=measure_query,
            )
            self._requests[task_id.value] = request
            self._idempotency[request.idempotency_key] = task_id.value
            return DirectStartTaskResultV3(True, view)

    def get_research_result(self, request):
        if type(request) is not DirectGetTaskRequestV3:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        with self._lock:
            view = self._views.get(request.task_id.value)
            if view is None or view.challenge_key != request.challenge_key:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            if view.state is DirectTaskStateV3.SUCCEEDED:
                self._verified_success_evidence(view)
            return DirectGetTaskResultV3(view)

    def queued_tasks(self):
        """Owned queue snapshot for the authenticated supervisor after restart."""
        with self._lock:
            return tuple(
                view.task_id
                for view in self._views.values()
                if view.state is DirectTaskStateV3.QUEUED
            )

    def cancel_observed_task(self, task_id, challenge):
        cancellation = (
            self._cancellations.get(task_id.value) or "mcp-cancel-" + task_id.value
        )
        return self.cancel_research_task(
            DirectCancelTaskRequestV3(challenge, task_id, cancellation)
        )

    def requires_reconciliation(self, task_id):
        with self._lock:
            view = self._views.get(task_id.value)
            if view is None:
                return False
            if view.state in (
                DirectTaskStateV3.RUNNING,
                DirectTaskStateV3.CANCEL_REQUESTED,
            ):
                return True
        return any(
            self.ledger.operation_state(child, owner=self.owner) == "RESERVED"
            for child in self._all_children(task_id)
        )

    def public_result(self, task):
        """Only bounded public predictions or a verified adapter-gap hint."""
        if (
            type(task) is DirectTaskViewV3
            and task.state is DirectTaskStateV3.FAILED_INFRA
        ):
            return self._verified_failure_evidence(task)
        if (
            type(task) is not DirectTaskViewV3
            or task.state is not DirectTaskStateV3.SUCCEEDED
        ):
            return None
        evidence = self._verified_success_evidence(task)
        return {
            "schema": "carbon.direct-public-practice-result.v3",
            "task_id": task.task_id.value,
            "receipt_digest": digest(canonical_bytes(task.terminal_receipt)),
            "predictions_digest": evidence["predictions_digest"],
            "predictions": evidence["predictions"],
            "official_eligible": False,
        }

    def _verified_failure_evidence(self, view):
        """Read only our closed failure projection, never private worker text."""
        if (
            type(view) is not DirectTaskViewV3
            or view.state is not DirectTaskStateV3.FAILED_INFRA
            or view.terminal_receipt is None
            or self._views.get(view.task_id.value) != view
        ):
            raise ValueError("direct failure receipt unavailable")
        with self._db() as db:
            row = db.execute(
                "SELECT body FROM direct_evidence WHERE id=?", (view.task_id.value,)
            ).fetchone()
        if row is None:
            return None  # Historical v3 failures have no structured hint.
        if len(row[0]) > 4096:
            raise ValueError("retained direct failure custody differs")
        try:
            evidence = json.loads(row[0])
        except (TypeError, ValueError, UnicodeError):
            raise ValueError("retained direct failure custody differs") from None
        if (
            type(evidence) is not dict
            or set(evidence)
            != {
                "schema",
                "task_id",
                "receipt_digest",
                "failed_stage",
                "reason_code",
                "diagnostic_provenance",
                "reported_operation",
                "next_step",
                "official_eligible",
            }
            or evidence["schema"] != "carbon.direct-public-construction-failure.v1"
            or evidence["task_id"] != view.task_id.value
            or evidence["receipt_digest"]
            != digest(canonical_bytes(view.terminal_receipt))
            or evidence["failed_stage"] != "BUILD_EXPORT"
            or evidence["reason_code"] != "REPORTED_CARBON_EXPORT_OPERATION_GAP"
            or evidence["diagnostic_provenance"] != "WORKER_DIAGNOSTIC_ADVISORY"
            or evidence["next_step"] != "CHECK_CARBON_ADAPTER_SUPPORT"
            or evidence["official_eligible"] is not False
            or type(evidence["reported_operation"]) is not str
            or not re.fullmatch(
                r"aten\.[A-Za-z_][A-Za-z_0-9]{0,63}\." r"[A-Za-z_][A-Za-z_0-9]{0,63}",
                evidence["reported_operation"],
            )
        ):
            raise ValueError("retained direct failure custody differs")
        return evidence

    def _verified_success_evidence(self, view):
        """Bind retained output bytes and worker receipt to the public terminal."""
        if (
            type(view) is not DirectTaskViewV3
            or view.state is not DirectTaskStateV3.SUCCEEDED
            or view.terminal_receipt is None
            or self._views.get(view.task_id.value) != view
        ):
            raise ValueError("direct success receipt unavailable")
        with self._db() as db:
            row = db.execute(
                "SELECT body FROM direct_evidence WHERE id=?", (view.task_id.value,)
            ).fetchone()
        if row is None or len(row[0]) > 24 * 1024**2:
            raise ValueError("retained direct result custody differs")
        try:
            evidence = json.loads(row[0])
            if (
                type(evidence) is not dict
                or type(evidence.get("predictions_raw_base64")) is not str
            ):
                raise ValueError("retained direct result custody differs")
            encoded = evidence["predictions_raw_base64"].encode("ascii")
            raw = base64.b64decode(encoded, validate=True)
            predictions = json.loads(raw)
        except (KeyError, TypeError, ValueError, UnicodeError, binascii.Error):
            raise ValueError("retained direct result custody differs") from None
        source = self._requests[view.task_id.value].recipe["source"]
        if view.task_id.value in self._task_image_bindings:
            image_binding = json.loads(self._task_image_bindings[view.task_id.value])
            if source["kind"] == "graph":
                if (
                    image_binding[0] != "GRAPH_PARENT"
                    or evidence.get("schema")
                    != "carbon.direct-private-attempt.graph.v1"
                    or any(
                        evidence.get(field) != image_binding[1]["image_id"]
                        for field in (
                            "image_id",
                            "parent_image_id",
                            "inference_image_id",
                        )
                    )
                    or evidence.get("submission_digest") != source["submission_digest"]
                    or "bundle_digest" in evidence
                    or "context_digest" in evidence
                ):
                    raise ValueError("retained direct worker image custody differs")
            elif (
                type(image_binding) is list
                and len(image_binding) == 2
                and image_binding[0] == "BUNDLE_OVERLAY"
            ):
                binding = image_binding[1]
                prep_receipt = evidence.get("prep_receipt")
                if (
                    type(binding) is not dict
                    or set(binding)
                    != {
                        "parent_image_id",
                        "bundle_ref",
                        "tree_digest",
                        "archive_digest",
                    }
                    or binding["bundle_ref"] != source["bundle_ref"]
                    or evidence.get("schema")
                    != "carbon.direct-private-attempt.overlay.v1"
                    or evidence.get("image_id") != binding["parent_image_id"]
                    or evidence.get("parent_image_id") != binding["parent_image_id"]
                    or evidence.get("inference_image_id")
                    != self.inference_image.image_id
                    or evidence.get("bundle_digest")
                    != binding["bundle_ref"]["bundle_digest"]
                    or evidence.get("overlay_tree_digest") != binding["tree_digest"]
                    or evidence.get("overlay_archive_digest")
                    != binding["archive_digest"]
                    or type(prep_receipt) is not dict
                    or prep_receipt.get("bundle_ref") != binding["bundle_ref"]
                    or prep_receipt.get("parent_image_id") != binding["parent_image_id"]
                    or prep_receipt.get("tree_digest") != binding["tree_digest"]
                    or prep_receipt.get("archive_sha256") != binding["archive_digest"]
                    or "context_digest" in evidence
                ):
                    raise ValueError("retained direct overlay custody differs")
            else:
                image_id, parent, bundle_ref, context_digest = image_binding
                if (
                    evidence.get("schema") != "carbon.direct-private-attempt.v3"
                    or evidence.get("image_id") != image_id
                    or evidence.get("parent_image_id") != parent["image_id"]
                    or evidence.get("inference_image_id")
                    != self.inference_image.image_id
                    or evidence.get("bundle_digest") != bundle_ref["bundle_digest"]
                    or evidence.get("context_digest") != context_digest
                ):
                    raise ValueError("retained direct worker image custody differs")
        receipt = view.terminal_receipt
        inference = evidence.get("inference_receipt")
        measured = view.task_id.value in self._measured_tasks
        if (
            not 0 < len(raw) <= 16 * 1024**2
            or base64.b64encode(raw) != encoded
            or type(predictions) is not list
            or digest(raw) != receipt.predictions_digest
            or evidence.get("predictions_digest") != receipt.predictions_digest
            or evidence.get("state_digest") != receipt.state_digest
            or type(inference) is not dict
            # Graph and bundle alike grade one case at a time (v1).
            or inference.get("schema") != "carbon.development.bundle-inference.v1"
            or inference.get("recipe_digest") != view.immutable_bindings.recipe_digest
            or inference.get("state_digest") != receipt.state_digest
            or inference.get("predictions_digest") != receipt.predictions_digest
        ):
            raise ValueError("retained direct result custody differs")
        if measured:
            from .bundle_construction_worker import _tensors

            # The graded query runs one case at a time; the measurement belongs
            # to the separate batched cold query kept only for timing.
            timed = evidence.get("timed_receipt")
            if (
                type(timed) is not dict
                or timed.get("schema") != "carbon.development.bundle-inference.v2"
                or timed.get("recipe_digest") != inference.get("recipe_digest")
                or timed.get("state_digest") != receipt.state_digest
                or type(evidence.get("timed_operation")) is not str
                or re.fullmatch(r"operation-[0-9a-f]{64}", evidence["timed_operation"])
                is None
            ):
                raise ValueError("retained direct timed query differs")
            inference = timed
            measurement = inference.get("measurement")
            material = self.discovery._material
            import numpy as np

            from carbon.challenge_kit.interface_dtype import output_dtype

            # The program reports the canonical name ("float64"); registered
            # interfaces may spell the same dtype "<f8" (F08: "<f4").
            expected_dtype = str(np.dtype(output_dtype(material["interface_document"])))
            if (
                set(inference)
                != {
                    "schema",
                    "recipe_digest",
                    "state_digest",
                    "inputs_digest",
                    "predictions_digest",
                    "measurement",
                }
                or type(measurement) is not dict
                or set(measurement)
                != {
                    "scope",
                    "timing_s",
                    "input_shape",
                    "input_dtype",
                    "output_shape",
                    "output_dtype",
                }
                or measurement["scope"]
                != "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
                or inference["inputs_digest"]
                != digest(_tensors(inputs=material["practice_inputs"]))
                or measurement["input_shape"] != list(material["practice_inputs"].shape)
                or measurement["input_dtype"] != str(material["practice_inputs"].dtype)
                or measurement["output_shape"]
                != list(material["expected_output_shape"])
                or measurement["output_dtype"] != expected_dtype
                or type(measurement["timing_s"]) is not dict
                or set(measurement["timing_s"])
                != {"preprocess", "inference", "postprocess", "export"}
                or any(
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or value < 0
                    for value in measurement["timing_s"].values()
                )
                or math.fsum(measurement["timing_s"].values()) <= 0
            ):
                raise ValueError("retained direct measurement differs")
        elif "measurement" in inference or "timed_receipt" in evidence:
            raise ValueError("retained direct measurement without profile")
        evidence["predictions"] = predictions
        return evidence

    @classmethod
    def _reported_export_gap(cls, error, child_states):
        """Extract one fixed lowering operation name, never echo diagnostic text.

        This is advice about a public fixture's Carbon exporter, not an
        authority-bearing classification of participant code or evaluation.
        """
        if (
            not isinstance(error, WorkerFailure)
            or error.code is not WorkerCode.RUNTIME
            or child_states[0] != "FAILED_INFRA"
            or child_states[1] is not None
        ):
            return None
        generic = cls._EXPORT_OP.findall(error.private_diagnostic)
        static_index = cls._SCATTER_INDEX_OP.findall(error.private_diagnostic)
        if len(generic) + len(static_index) != 1:
            return None
        if static_index:
            return static_index[0].decode("ascii")
        return generic[0].decode("ascii")

    def _transition(
        self,
        view,
        state,
        *,
        receipt=None,
        cancellation=None,
        export_gap=None,
        build_refusal=None,
    ):
        from dataclasses import replace

        now = max(time.time_ns() // 1000, view.updated_at_micros)
        updated = replace(
            view,
            state=state,
            revision=view.revision + 1,
            updated_at_micros=now,
            terminal_receipt=receipt,
        )
        failure_evidence = None
        if export_gap is not None:
            if state is not DirectTaskStateV3.FAILED_INFRA or receipt is None:
                raise ValueError(
                    "export gap requires a terminal infrastructure receipt"
                )
            failure_evidence = {
                "schema": "carbon.direct-public-construction-failure.v1",
                "task_id": view.task_id.value,
                "receipt_digest": digest(canonical_bytes(receipt)),
                "failed_stage": "BUILD_EXPORT",
                "reason_code": "REPORTED_CARBON_EXPORT_OPERATION_GAP",
                "diagnostic_provenance": "WORKER_DIAGNOSTIC_ADVISORY",
                "reported_operation": export_gap,
                "next_step": "CHECK_CARBON_ADAPTER_SUPPORT",
                "official_eligible": False,
            }
        if build_refusal is not None:
            if state is not DirectTaskStateV3.REFUSED or receipt is None:
                raise ValueError("build refusal requires a terminal refusal receipt")
            failure_evidence = {
                "schema": "carbon.direct-build-refusal.v1",
                "task_id": view.task_id.value,
                "receipt_digest": digest(canonical_bytes(receipt)),
                "outcome": build_refusal.outcome,
                "reason_code": build_refusal.code,
                "operation": build_refusal.at,
                "official_eligible": False,
            }
        self._save(
            self._requests[view.task_id.value],
            updated,
            cancellation,
            failure_evidence=failure_evidence,
        )
        return updated

    def _receipt(self, view, state, *, result=None, failure=None, refusal_code=None):
        return DirectTaskReceiptV3(
            view.task_id,
            state,
            view.immutable_bindings,
            result.build.state_digest if result is not None else None,
            result.inference.predictions_digest if result is not None else None,
            failure,
            refusal_code,
            max(time.time_ns() // 1000, view.updated_at_micros),
            self._LIMITATIONS,
        )

    def _children(self, task_id):
        from .bundle_construction_worker import direct_child_identity

        return tuple(
            direct_child_identity(task_id.value, phase)
            for phase in ("build", "inference")
        )

    def _all_children(self, task_id):
        from .bundle_construction_worker import direct_child_identity

        children = self._children(task_id)
        request = self._requests.get(task_id.value)
        retained = self._task_image_bindings.get(task_id.value)
        if request is not None and request.recipe["source"]["kind"] == "bundle":
            binding = json.loads(retained) if retained is not None else None
            if (
                type(binding) is list
                and len(binding) == 2
                and binding[0] in {"BUNDLE_SOURCE", "BUNDLE_OVERLAY"}
            ):
                return (*children, direct_child_identity(task_id.value, "prep"))
        return children

    def cancel_research_task(self, request):
        if type(request) is not DirectCancelTaskRequestV3:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        with self._lock:
            view = self._views.get(request.task_id.value)
            if view is None or view.challenge_key != request.challenge_key:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            if view.state in (
                DirectTaskStateV3.SUCCEEDED,
                DirectTaskStateV3.REFUSED,
                DirectTaskStateV3.UNRESOLVED,
                DirectTaskStateV3.FAILED_INFRA,
                DirectTaskStateV3.CANCELLED,
            ):
                return DirectCancelTaskResultV3(view, CancellationDisposition.TOO_LATE)
            if view.state is DirectTaskStateV3.CANCEL_REQUESTED:
                if self._cancellations[view.task_id.value] != request.cancellation_id:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                    )
                for child in self._all_children(view.task_id):
                    request_cancel(self.ledger, owner=self.owner, identity=child)
                return DirectCancelTaskResultV3(
                    view, CancellationDisposition.ALREADY_ACCEPTED
                )
            if view.state is DirectTaskStateV3.QUEUED:
                receipt = self._receipt(view, DirectTaskStateV3.CANCELLED)
                view = self._transition(
                    view,
                    DirectTaskStateV3.CANCELLED,
                    receipt=receipt,
                    cancellation=request.cancellation_id,
                )
            else:
                view = self._transition(
                    view,
                    DirectTaskStateV3.CANCEL_REQUESTED,
                    cancellation=request.cancellation_id,
                )
                for child in self._all_children(view.task_id):
                    request_cancel(self.ledger, owner=self.owner, identity=child)
            return DirectCancelTaskResultV3(view, CancellationDisposition.ACCEPTED)

    def _reconcile_interrupted(self):
        from .research_carrier import reconcile_worker

        for view in tuple(self._views.values()):
            if view.state not in (
                DirectTaskStateV3.RUNNING,
                DirectTaskStateV3.CANCEL_REQUESTED,
            ):
                continue
            if view.state is DirectTaskStateV3.CANCEL_REQUESTED:
                for child in self._all_children(view.task_id):
                    request_cancel(self.ledger, owner=self.owner, identity=child)
            child_states = []
            for child in self._all_children(view.task_id):
                state = self.ledger.operation_state(child, owner=self.owner)
                if state == "RESERVED":
                    reconcile_worker(self.ledger, owner=self.owner, identity=child)
                    state = self.ledger.operation_state(child, owner=self.owner)
                if state not in (
                    None,
                    "SUCCEEDED",
                    "FAILED_INFRA",
                    "FAILED_MINER",
                    "CANCELLED",
                ):
                    raise ValueError("direct child cleanup status unresolved")
                child_states.append(state)
            state = (
                DirectTaskStateV3.CANCELLED
                if view.state is DirectTaskStateV3.CANCEL_REQUESTED
                else (
                    DirectTaskStateV3.REFUSED
                    if "FAILED_MINER" in child_states
                    and "FAILED_INFRA" not in child_states
                    else DirectTaskStateV3.FAILED_INFRA
                )
            )
            receipt = self._receipt(
                view,
                state,
                failure=(
                    (
                        InfrastructureFailureClass.INTERNAL
                        if "FAILED_INFRA" in child_states
                        else InfrastructureFailureClass.WORKER_LOST
                    )
                    if state is DirectTaskStateV3.FAILED_INFRA
                    else None
                ),
                refusal_code=(
                    "candidate_program_failed"
                    if state is DirectTaskStateV3.REFUSED
                    else None
                ),
            )
            self._transition(view, state, receipt=receipt)

    def run_queued_task(self, task_id):
        from .bundle_construction_worker import (
            CandidateBuildRefused,
            DirectReconstructionResult,
            _private_controls_digest,
            reconstruct_and_infer_public,
        )
        from .construction_recipe import ConstructionRecipe
        from .direct_graph_construction_worker import (
            BUILD_PROVENANCE as GRAPH_BUILD_PROVENANCE,
        )
        from .direct_graph_construction_worker import (
            INFERENCE_PROVENANCE as GRAPH_INFERENCE_PROVENANCE,
        )
        from .direct_graph_construction_worker import (
            GraphConstructionDecision,
            reconstruct_and_infer_graph_public,
        )
        from .library_bundles import LibraryBundleRef

        with self._lock:
            view = self._views.get(task_id.value)
            if view is None:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            if view.state is not DirectTaskStateV3.QUEUED:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INVALID_TASK_TRANSITION
                )
            request = self._requests[task_id.value]
            try:
                recipe = ConstructionRecipe.from_dict(request.recipe)
                source_kind = recipe.to_dict()["source"]["kind"]
                if source_kind == "graph" and (
                    self.build_accelerator is not None
                    or self.inference_accelerator is not None
                ):
                    raise ValueError("direct graph GPU construction is unavailable")
                retained_image = self._task_image_bindings.get(task_id.value)
                retained_binding = (
                    json.loads(retained_image) if retained_image is not None else None
                )
                staged_source = (
                    type(retained_binding) is list
                    and len(retained_binding) == 2
                    and retained_binding[0] == "BUNDLE_SOURCE"
                    and source_kind == "bundle"
                    and self.image_resolver is not None
                    and callable(getattr(self.image_resolver, "inspect_source", None))
                    and callable(
                        getattr(self.image_resolver, "provision_admitted", None)
                    )
                )
                image = None if staged_source else self._resolved_image(request)
                source_envelope = (
                    self._source_envelope(task_id.value, recipe)
                    if source_kind == "graph"
                    else None
                )
                expected_binding = (
                    self._inspected_source_binding(request)
                    if staged_source
                    else self._image_binding(image)
                )
                if task_id.value in self._task_image_bindings and (
                    expected_binding != self._task_image_bindings[task_id.value]
                ):
                    raise ValueError("admitted direct library image changed")
            except (FileNotFoundError, ValueError, OSError, WorkerFailure):
                receipt = self._receipt(
                    view,
                    DirectTaskStateV3.FAILED_INFRA,
                    failure=InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE,
                )
                return self._transition(
                    view, DirectTaskStateV3.FAILED_INFRA, receipt=receipt
                )
            view = self._transition(view, DirectTaskStateV3.RUNNING)
        provisioning = False
        try:
            total_deadline_started = None
            overlay_prep = None
            if staged_source:
                provisioning = True
                total_deadline_started = time.monotonic()
                policy = self.discovery._material["construction_limits_document"][
                    "reconstruction_resource_policy"
                ]
                provisioned = self._provision_admitted_image(
                    request,
                    deadline=(
                        total_deadline_started
                        + policy["total_reconstruction_wall_seconds_max"]
                    ),
                )
                if type(provisioned) is tuple:
                    image, overlay_prep = provisioned
                else:
                    image = provisioned
                actual_binding = self._image_binding(image)
                with self._lock:
                    with self._db() as db:
                        changed = db.execute(
                            "UPDATE direct_task_images SET identity=? "
                            "WHERE id=? AND identity=?",
                            (
                                actual_binding,
                                task_id.value,
                                expected_binding,
                            ),
                        )
                        if changed.rowcount != 1:
                            raise ValueError("admitted direct source custody changed")
                    self._task_image_bindings[task_id.value] = actual_binding
                    current = self._views[task_id.value]
                    if current.state is DirectTaskStateV3.CANCEL_REQUESTED:
                        return self._transition(
                            current,
                            DirectTaskStateV3.CANCELLED,
                            receipt=self._receipt(current, DirectTaskStateV3.CANCELLED),
                        )
                provisioning = False
            self._bindings(request)
            from carbon.challenge_kit import physical_material
            from carbon.challenge_kit.interface_dtype import output_dtype

            material = self.discovery._material
            kit = material["construction_kit"]
            binding = {
                "challenge_id": kit["id"],
                "challenge_version": kit["version"],
                "train_digest": kit["train_digest"],
                "interface_digest": kit["interface_digest"],
                "construction_limits_digest": kit["construction_limits_digest"],
            }
            if source_kind == "graph":
                result = reconstruct_and_infer_graph_public(
                    self.ledger,
                    owner=self.owner,
                    identity=task_id.value,
                    image=image,
                    recipe=recipe,
                    challenge_binding=binding,
                    limits_document=material["construction_limits_document"],
                    source_envelope=source_envelope,
                    train=material["train"],
                    seed=0,
                    inputs=material["practice_inputs"],
                    expected_output_shape=material["expected_output_shape"],
                    allowlist_bytes=material["allowlist_bytes"],
                    measure_query=task_id.value in self._measured_tasks,
                    adapter_id=self.discovery.graph_adapter_for(request.challenge_key),
                )
            else:
                result = reconstruct_and_infer_public(
                    self.ledger,
                    owner=self.owner,
                    identity=task_id.value,
                    image=image,
                    inference_image=self.inference_image,
                    construction_parent=self._parent_for(
                        LibraryBundleRef.from_dict(
                            request.recipe["source"]["bundle_ref"]
                        )
                    ),
                    recipe=recipe,
                    challenge_binding=binding,
                    limits_document=material["construction_limits_document"],
                    train=material["train"],
                    example=material["example"],
                    seed=0,
                    inputs=material["practice_inputs"],
                    expected_output_shape=material["expected_output_shape"],
                    allowlist_bytes=material["allowlist_bytes"],
                    expected_output_dtype=(
                        output_dtype(material["interface_document"])
                        if (
                            kit["id"] == BATTERY_CHALLENGE
                            and kit["version"] in ("1.0", "2.0", "2.1")
                        )
                        or kit["version"] == "1.3"
                        or physical_material.is_registered(kit["id"], kit["version"])
                        or task_id.value in self._measured_tasks
                        else None
                    ),
                    measure_query=task_id.value in self._measured_tasks,
                    total_deadline_started=total_deadline_started,
                    **(
                        {}
                        if self.build_accelerator is None
                        else {"accelerator": self.build_accelerator}
                    ),
                    **(
                        {}
                        if self.inference_accelerator is None
                        else {"inference_accelerator": self.inference_accelerator}
                    ),
                )
            if (
                type(result) is not DirectReconstructionResult
                or result.execution_boundary != "C03_DOCKER"
                or result.policy_digest != request.construction_limits_digest
                or result.build.recipe_digest != view.immutable_bindings.recipe_digest
                or result.inference.recipe_digest
                != view.immutable_bindings.recipe_digest
                or result.build.state_digest != result.inference.state_digest
                or result.build_controls_digest is None
                or result.inference_controls_digest is None
                or not result.build.worker_operation
                or not result.inference.worker_operation
                or result.build.worker_operation == result.inference.worker_operation
            ):
                raise ValueError("direct C-03 two-phase evidence incomplete")
            # A replacement callback cannot yield success without both settled
            # real child operations and their retained effective controls.
            from .library_environment_cache import VerifiedLibraryOverlay
            from .research_carrier import (
                LIBRARY_BUILD_PROVENANCE,
                LIBRARY_OVERLAY_BUILD_PROVENANCE,
                LIBRARY_PREP_PROVENANCE,
            )

            overlay_run = type(image) is VerifiedLibraryOverlay

            build_provenance, inference_provenance = (
                (GRAPH_BUILD_PROVENANCE, GRAPH_INFERENCE_PROVENANCE)
                if source_kind == "graph"
                else (
                    (
                        LIBRARY_OVERLAY_BUILD_PROVENANCE
                        if overlay_run
                        else LIBRARY_BUILD_PROVENANCE
                    ),
                    "DIRECT_BUNDLE_PUBLIC_INFERENCE",
                )
            )

            controls = (
                _private_controls_digest(
                    self.ledger,
                    owner=self.owner,
                    identity=self._children(task_id)[0],
                    operation=result.build.worker_operation,
                    provenance=build_provenance,
                ),
                _private_controls_digest(
                    self.ledger,
                    owner=self.owner,
                    identity=self._children(task_id)[1],
                    operation=result.inference.worker_operation,
                    provenance=inference_provenance,
                ),
            )
            if controls != (
                result.build_controls_digest,
                result.inference_controls_digest,
            ):
                raise ValueError("direct worker controls changed")
            if result.timed is not None:
                from .bundle_construction_worker import direct_child_identity

                timed_controls = _private_controls_digest(
                    self.ledger,
                    owner=self.owner,
                    identity=direct_child_identity(task_id.value, "timed"),
                    operation=result.timed.worker_operation,
                    provenance=inference_provenance,
                )
                if (
                    result.timed_controls_digest is None
                    or timed_controls != result.timed_controls_digest
                ):
                    raise ValueError("direct timed controls changed")
            if overlay_run:
                if overlay_prep is None or overlay_prep.controls_digest is None:
                    raise ValueError("direct overlay preparation evidence unavailable")
                prep_controls = _private_controls_digest(
                    self.ledger,
                    owner=self.owner,
                    identity=self._all_children(task_id)[2],
                    operation=overlay_prep.worker_operation,
                    provenance=LIBRARY_PREP_PROVENANCE,
                )
                if prep_controls != overlay_prep.controls_digest:
                    raise ValueError("direct overlay preparation controls changed")
            snapshot = (
                self.ledger.root
                / result.inference.worker_operation
                / "snapshot"
                / "predictions.json"
            )
            if (
                snapshot.is_symlink()
                or not snapshot.is_file()
                or not 0 < snapshot.stat().st_size <= 16 * 1024**2
            ):
                raise ValueError("direct prediction snapshot unavailable")
            predictions_raw = snapshot.read_bytes()
            if (
                digest(predictions_raw) != result.inference.predictions_digest
                or json.loads(predictions_raw) != result.inference.predictions
            ):
                raise ValueError("direct prediction snapshot changed")
            private = {
                "schema": (
                    "carbon.direct-private-attempt.graph.v1"
                    if source_kind == "graph"
                    else (
                        "carbon.direct-private-attempt.overlay.v1"
                        if overlay_run
                        else "carbon.direct-private-attempt.v3"
                    )
                ),
                "image_id": (image.parent_image_id if overlay_run else image.image_id),
                "parent_image_id": (
                    image.image_id
                    if source_kind == "graph"
                    else (
                        image.parent_image_id if overlay_run else image.parent.image_id
                    )
                ),
                "inference_image_id": self.inference_image.image_id,
                "build_operation": result.build.worker_operation,
                "inference_operation": result.inference.worker_operation,
                "build_controls_digest": controls[0],
                "inference_controls_digest": controls[1],
                "state_digest": result.build.state_digest,
                "predictions_digest": result.inference.predictions_digest,
                "build_receipt": result.build.receipt,
                "inference_receipt": result.inference.receipt,
                "predictions_raw_base64": base64.b64encode(predictions_raw).decode(
                    "ascii"
                ),
            }
            if result.timed is not None:
                private["timed_operation"] = result.timed.worker_operation
                private["timed_receipt"] = result.timed.receipt
                if result.timed_controls_digest is not None:
                    private["timed_controls_digest"] = result.timed_controls_digest
            if source_kind == "bundle" and result.prediction_comparison is not None:
                private["prediction_comparison"] = result.prediction_comparison
            if source_kind == "graph":
                private["submission_digest"] = recipe.to_dict()["source"][
                    "submission_digest"
                ]
            elif overlay_run:
                private.update(
                    {
                        "bundle_digest": image.bundle_ref.bundle_digest,
                        "overlay_tree_digest": image.tree_digest,
                        "overlay_archive_digest": image.archive_digest,
                        "prep_operation": overlay_prep.worker_operation,
                        "prep_controls_digest": overlay_prep.controls_digest,
                        "prep_receipt": overlay_prep.receipt,
                    }
                )
            else:
                private["bundle_digest"] = image.provisioned.bundle.bundle_digest
                private["context_digest"] = image.provisioned.context_digest
            with self._lock:
                view = self._views[task_id.value]
                if view.state is DirectTaskStateV3.CANCEL_REQUESTED:
                    receipt = self._receipt(view, DirectTaskStateV3.CANCELLED)
                    return self._transition(
                        view, DirectTaskStateV3.CANCELLED, receipt=receipt
                    )
                if view.state is not DirectTaskStateV3.RUNNING:
                    raise ValueError("direct task state changed")
                from dataclasses import replace

                completed = max(time.time_ns() // 1000, view.updated_at_micros)
                receipt = self._receipt(
                    view, DirectTaskStateV3.SUCCEEDED, result=result
                )
                succeeded = replace(
                    view,
                    state=DirectTaskStateV3.SUCCEEDED,
                    revision=view.revision + 1,
                    updated_at_micros=max(completed, receipt.completed_at_micros),
                    terminal_receipt=receipt,
                )
                with self._db() as db:
                    db.execute(
                        "INSERT INTO direct_evidence VALUES(?,?)",
                        (task_id.value, canonical(private)),
                    )
                    db.execute(
                        "UPDATE direct_tasks SET view=? WHERE id=?",
                        (canonical_bytes(succeeded), task_id.value),
                    )
                self._views[task_id.value] = succeeded
                return succeeded
        except Exception as exc:  # noqa: BLE001 - private worker details stay private.
            # A child can be RESERVED after an exception. Do not mark the
            # parent terminal until every claimed child has observed cleanup.
            from .research_carrier import reconcile_worker

            child_states = []
            for child in self._all_children(task_id):
                child_state = self.ledger.operation_state(child, owner=self.owner)
                if child_state == "RESERVED":
                    reconcile_worker(self.ledger, owner=self.owner, identity=child)
                    child_state = self.ledger.operation_state(child, owner=self.owner)
                if child_state not in (
                    None,
                    "SUCCEEDED",
                    "FAILED_INFRA",
                    "FAILED_MINER",
                    "CANCELLED",
                ):
                    raise ValueError("direct child cleanup remains unresolved")
                child_states.append(child_state)
            with self._lock:
                view = self._views[task_id.value]
                graph_decision = (
                    exc
                    if source_kind == "graph"
                    and isinstance(exc, GraphConstructionDecision)
                    and child_states == ["SUCCEEDED", None]
                    else None
                )
                state = (
                    DirectTaskStateV3.CANCELLED
                    if view.state is DirectTaskStateV3.CANCEL_REQUESTED
                    else (
                        DirectTaskStateV3(graph_decision.state)
                        if graph_decision is not None
                        else (
                            DirectTaskStateV3.FAILED_INFRA
                            if provisioning or "FAILED_INFRA" in child_states
                            else (
                                DirectTaskStateV3.REFUSED
                                if isinstance(
                                    exc, (MinerProgramFailure, CandidateBuildRefused)
                                )
                                or "FAILED_MINER" in child_states
                                else DirectTaskStateV3.UNRESOLVED
                            )
                        )
                    )
                )
                receipt = self._receipt(
                    view,
                    state,
                    failure=(
                        InfrastructureFailureClass.INTERNAL
                        if state is DirectTaskStateV3.FAILED_INFRA
                        else None
                    ),
                    refusal_code=(
                        graph_decision.reason_code
                        if graph_decision is not None
                        and state
                        in (DirectTaskStateV3.REFUSED, DirectTaskStateV3.UNRESOLVED)
                        else (
                            (
                                (
                                    "carbon_capability_gap"
                                    if exc.outcome == "CARBON_CAPABILITY_GAP"
                                    else "candidate_build_refused"
                                )
                                if isinstance(exc, CandidateBuildRefused)
                                else "candidate_program_failed"
                            )
                            if state is DirectTaskStateV3.REFUSED
                            else (
                                "unresolved_execution"
                                if state is DirectTaskStateV3.UNRESOLVED
                                else None
                            )
                        )
                    ),
                )
                return self._transition(
                    view,
                    state,
                    receipt=receipt,
                    export_gap=(
                        self._reported_export_gap(exc, child_states)
                        if state is DirectTaskStateV3.FAILED_INFRA
                        else None
                    ),
                    build_refusal=(
                        exc
                        if isinstance(exc, CandidateBuildRefused)
                        and state is DirectTaskStateV3.REFUSED
                        else None
                    ),
                )

    def private_refusal(self, task_id):
        """The classified build refusal of a REFUSED task (outcome, code, operation),
        or None: the record Launchpad's op list reads for capability gaps."""
        view = self._views.get(task_id.value)
        if (
            view is None
            or view.state is not DirectTaskStateV3.REFUSED
            or view.terminal_receipt is None
        ):
            return None
        with self._db() as db:
            row = db.execute(
                "SELECT body FROM direct_evidence WHERE id=?", (task_id.value,)
            ).fetchone()
        if row is None or len(row[0]) > 4096:
            return None
        record = json.loads(row[0])
        if (
            type(record) is not dict
            or record.get("schema") != "carbon.direct-build-refusal.v1"
            or record.get("task_id") != task_id.value
            or record.get("receipt_digest")
            != digest(canonical_bytes(view.terminal_receipt))
        ):
            raise ValueError("retained build refusal custody differs")
        return record

    def private_attempt(self, task_id):
        """Trusted inspection only; public service never returns this record."""
        view = self._views.get(task_id.value)
        if view is None or view.state is not DirectTaskStateV3.SUCCEEDED:
            return None
        return self._verified_success_evidence(view)


#: The most bytes one `read_file` returns, by the campaign's research tools
#: rule (`research_tools.frozen_tools_rule`; None is the historical rule).
#: Historical: 4 KiB as `content_base64`, exactly as before. Under v2
#: (LP-PROD-D): 8 KiB, returned once - as `content_utf8` when the bytes are
#: UTF-8 text no longer escaped than base64, otherwise as `content_base64`
#: (`read_file_content`). Whatever a read returns stays in the agent's
#: context for the rest of its epoch, and a request is admitted only within
#: max_input_tokens less a reserve (61440 at the default selection). 8 KiB is
#: the most whose worst case - 16 KiB of escaped text, carried in the
#: history as a JSON string - still fits beside the battery agent's first
#: request (about 34 KB) as its first tool result; 12 KiB does not. A test
#: checks that fit against the real request (test_lp_prod_research_tools).
READ_FILE_MAX_BYTES = {None: 4096, "carbon.autoresearch.research-tools.v2": 8192}
#: The notebook kinds a miner (or their agent) may write.
NOTEBOOK_KINDS = ("hypothesis", "decision", "notebook")
#: The actions that run the miner's own program in the miner lane.
RUN_ACTIONS = frozenset({"run_python", "run_julia"})
#: The bound on a run's prospective hypothesis and expected effect.
RUN_TEXT = 2048


def reserved_stage_names(action):
    """The names the carrier stages itself for `action`, which a run's own
    files may not take: every run's `program.py` (the carrier refuses it in
    any stage) and, for run_julia, its program `program.jl` too."""
    return frozenset(
        {"program.py", "program.jl"} if action == "run_julia" else {"program.py"}
    )


def read_file_limit(executor):
    """The most bytes one `read_file` returns for this executor's campaign:
    the limit its frozen research tools rule sets (`READ_FILE_MAX_BYTES`)."""
    from .research_tools import campaign_tools_rule

    return READ_FILE_MAX_BYTES[campaign_tools_rule(getattr(executor, "ledger", None))]


def read_file_content(chunk, rule):
    """One read's bytes as its result carries them, by research tools rule.

    The historical rule returns `content_base64` alone, as it always has. v2
    returns the bytes once, never both encodings: `content_utf8` when they
    decode as UTF-8 and their JSON-escaped text is no longer than their
    base64 (ordinary text always is), otherwise `content_base64`; the other
    is null. Text full of control or non-ASCII characters escapes to up to
    six bytes per byte, so it comes back as base64 rather than cost the
    model's context several times its size.
    """
    encoded = base64.b64encode(chunk).decode("ascii")
    if rule is None:
        return {"content_base64": encoded}
    try:
        text = chunk.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None and len(canonical(text)) - 2 > len(encoded):
        text = None
    return {
        "content_utf8": text,
        "content_base64": encoded if text is None else None,
    }


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


#: Battery's published scaffold as a ready direct recipe
#: (`carbon.battery.research.BatteryPublicMaterial`, Validator option A).
SCAFFOLD_RECIPE = "scaffold_recipe"
#: Motor 1.2's backbone catalog and construction kit
#: (`carbon.motor.research.MotorCatalogMaterial`).
CATALOG_MATERIALS = ("catalog", "construction_kit")
#: The material names every bound material service serves.
PUBLIC_MATERIALS = (
    "objective",
    "capabilities",
    "training_data",
    "practice_data",
    "reference_method",
)


def every_public_material_name():
    """Every name `public_material_names` can return, for any material
    service: the closed list a `public_material_unknown` correction lists
    from (`research_tools.correction_choices`)."""
    from .advection_research import MATERIAL as ADVECTION_MATERIAL
    from .julia_envelope import MATERIAL as ENVELOPE
    from .julia_research import MATERIAL

    return (
        *PUBLIC_MATERIALS,
        MATERIAL,
        ADVECTION_MATERIAL,
        ENVELOPE,
        SCAFFOLD_RECIPE,
        *CATALOG_MATERIALS,
    )


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

    names = list(PUBLIC_MATERIALS)
    if type(public_material) is JuliaPublicMaterial:
        names.append(MATERIAL)
    if type(public_material) is PublicAdvectionMaterial:
        names.append(ADVECTION_MATERIAL)
    if type(public_material) is JuliaEnvelopeMaterial:
        names += [MATERIAL, ENVELOPE]
    # A material service's own declared names, inside the closed list: the
    # names its discovery document lists are the names its door accepts
    # (BUG GRAPHITE_SCAFFOLD_UNREACHABLE_20261020: Battery listed
    # scaffold_recipe and the door refused it).
    every = every_public_material_name()
    declared = getattr(type(public_material), "NAMES", ())
    names += [name for name in declared if type(name) is str and name in every]
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
        limit = read_file_limit(executor)
        for name, low, high in (
            ("offset", 0, None),
            ("count", 1, limit),
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
                    (str(limit),),
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
    reserved = reserved_stage_names(action)
    for name in files:
        _workspace_name(name, "arguments_json.files")
        if name in reserved:
            _refuse(
                "run_files_invalid",
                "arguments_json.files",
                "closed stage required",
                tuple(sorted(reserved)),
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


#: The outcome of a task the campaign's own ceiling refused
#: (RESEARCH-BUDGET-REFUSAL-TYPING-01), beside REQUEST_REFUSED and
#: MINER_PROGRAM_FAILED: Carbon examined the request and completed it with
#: this typed outcome. Results retained before it are read unchanged.
CEILING_OUTCOME = "MINER_CEILING_REACHED"


def ceiling_correction(record):
    """What the requester can do about a ceiling refusal, from its record.

    Registered text over Carbon-written values only: the dimension name, the
    campaign's own counts, and the launch field that sets the limit. A
    product campaign's budget is the miner's own, set at launch and frozen
    with the campaign; a development campaign's is its operator's.
    """
    dimension = record["dimension"]
    elapsed = dimension == "elapsed_seconds"
    field = "budget.elapsed_seconds" if elapsed else "budget.ceilings." + dimension
    counts = ", ".join(
        f"{name} {record[key]}"
        for key, name in (
            ("used", "used"),
            ("requested", "requested"),
            ("ceiling", "ceiling"),
        )
        if record[key] is not None
    )
    counts = f" ({counts})" if counts else ""
    tail = (
        " Nothing of the refused work was reserved."
        if record["refused_at"] == "reservation"
        else ""
    )
    if record["basis"] == "miner_launch_budget":
        return (
            f"This campaign reached a ceiling you set yourself: {dimension}"
            f"{counts}. It is your own budget, set at launch in {field}; Carbon "
            "sets no ceiling of its own on it. A launched campaign's budget is "
            f"frozen with it, so to go further launch a new campaign with a "
            f"larger {field}, or leave it out for no ceiling.{tail}"
        )
    return (
        f"This campaign reached its {dimension} ceiling{counts}, set by its "
        f"development budget when it was created.{tail}"
    )


def ceiling_result(refusal):
    """The task result for work the campaign's own ceiling refused.

    Never an infrastructure failure: the ledger refused against a limit the
    campaign froze (before it recorded the refused reservation, when
    `refused_at` is `reservation`). It names the
    dimension, the counts the ledger compared and whose limit it is, and says
    how to raise it. No hidden or official value, and no other owner's state:
    only this campaign's own budget and use."""
    record = refusal.record()
    return {
        "outcome": CEILING_OUTCOME,
        **record,
        "correction": ceiling_correction(record),
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
        """One bounded slice of an own file, encoded as the campaign's
        research tools rule says (`read_file_content`): base64 alone under
        the historical rule, exactly as before; under v2 the bytes once, as
        text when they are text."""
        from .research_tools import campaign_tools_rule
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
        return {
            "name": args["name"],
            "digest": digest(body),
            "bytes": len(body),
            "offset": offset,
            **read_file_content(
                body[offset : offset + count], campaign_tools_rule(self.ledger)
            ),
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
        elif type(spec) is DirectPracticeTaskSpecV1:
            if getattr(self.practice, "construction_mode", None) != "direct":
                raise ValueError("direct practice is unavailable for this campaign")
            result = self.practice(identity, spec.recipe)
            evidence = ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
        elif type(spec) is PracticeTaskSpec:
            # The practice adapter supplies trusted labels/randomness and the
            # catalog compiler; the requester supplies only a registered recipe.
            # A smoke practice the campaign's own practice path recorded for
            # this trial runs the same callback, truncated, and keeps only
            # its smoke result (LAUNCHPAD-SMOKE-PRACTICE-01).
            from . import smoke_practice

            smoke = smoke_practice.requested(
                self.ledger, self.owner, request.idempotency_key
            )
            if smoke is None:
                result = self.practice(identity, spec.strategy)
            else:
                result = smoke_practice.run(
                    self.practice,
                    identity,
                    spec.strategy,
                    smoke,
                    workspace=self.workspace,
                )
            evidence = ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
        else:
            raise ValueError("task kind unavailable in real D4 provider")
        return self._complete(identity, result, evidence)

    def refusal_outcome(self, attempt, error):
        """The typed outcome of a ledger refusal raised while executing
        `attempt`, or None for anything else (`durable._typed_refusal`).

        The campaign's own ceiling - a cap in the budget it froze, or its
        elapsed time - completes the task with `ceiling_result`, stored as
        its result like every other outcome: never an infrastructure failure
        (RESEARCH-BUDGET-REFUSAL-TYPING-01). Carbon's own service capacity is
        Carbon's limit, so it stays an infrastructure failure, typed
        RESOURCE_LIMIT rather than INTERNAL. Every other exception is None:
        the caller keeps INTERNAL, exactly as before.
        """
        from carbon.research.records import InfrastructureExecutionFailure

        from .research_control import CampaignDeadlineReached
        from .research_ledger import (
            CARBON_SERVICE_CAPACITY,
            MINER_CEILING_REACHED,
            LedgerRefusal,
        )

        if type(error) is CampaignDeadlineReached:
            # Campaign control's own check of the same time limit, made before
            # the ledger's (`CampaignLedger.reserve` runs it first).
            error = error.refusal
        if type(error) is not LedgerRefusal:
            return None
        if error.code == CARBON_SERVICE_CAPACITY:
            return InfrastructureExecutionFailure(
                InfrastructureFailureClass.RESOURCE_LIMIT, False
            )
        if error.code != MINER_CEILING_REACHED:
            return None
        return self._complete(
            attempt.task_id.value,
            ceiling_result(error),
            ResearchEvidenceClass.STRUCTURAL_ONLY,
        )

    def _complete(self, identity, result, evidence):
        """Retain `result` as this task's public result and return its
        authorized outcome."""
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
