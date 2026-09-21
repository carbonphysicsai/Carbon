"""Start, stop and clean up a validator-lane reconstruction on this host.

C-CORE-19 made `VALIDATOR_RECONSTRUCTION` admissible on a GPU and then recorded,
honestly, that nothing constructed one: `repeats.py` calls `reconstruct()` in
process, with no backend, accelerator, profile or device selection anywhere in
that module. Admission was unblocked and unreachable. This closes that gap.

It is the validator counterpart of `miner_launch`, and deliberately its near
twin - same controller, same durable queue, same launch store, same cleanup.
Nothing here can start work the controller would not have started or finish work
the store would not have finished.

Three properties make it a *validator* entry point rather than a parameterised
miner one:

**The role is fixed and is not a parameter.** Exactly as the miner path fixes
its own, and for the same reason: a caller that could choose the role could
choose the lane, and the lane is what decides the requirements a run was held
to.

**The execution class is Carbon's, not the submitter's.** The miner manifest
names its own image, which is right for a miner running their own research on
their own rented box. A validator is the arbiter. Its image is resolved from an
operator-installed registered record on the host, and the manifest has no image
field at all - not an ignored one, an absent one, so there is nothing to smuggle
and nothing to disagree with. The device, provider, driver, execution flags and
numerical environment are likewise host-side and untouchable from a submission.

**Identity comes from the queue, never from the file.** Which execution this is,
who requested it and what seed it is pinned to were committed when the work was
admitted. The manifest supplies materials, and every material is checked against
the digests the binding already holds. A manifest naming different work than the
queue admitted is refused before anything is staged.

**What this does not do.** It does not qualify a backend. `compare_r1` returns
`BACKEND_UNSUPPORTED` while the backend profile is not `SUPPORTED`, and MQ-008 at
G4 owns that. A run through here is engineering evidence: the orchestration is
IMPLEMENTED and TESTED, and it is not HARDWARE_EXERCISED,
SCIENTIFICALLY_QUALIFIED, SECURITY_QUALIFIED or PRODUCTION_QUALIFIED. There is no
parameter anywhere on this path that asks for authoritative use, because there is
nothing here that could grant it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from dataclasses import replace as _replace
from pathlib import Path

from carbon.construction import (
    ResolvedConstructionPlanRef,
    decode_resolved_construction_plan,
)
from carbon.development_session.profile import digest as _digest
from carbon.execution import DurableExecutionQueue
from carbon.reconstruction.accelerators import AcceleratorLane, AcceleratorRole
from carbon.reconstruction.miner_launch import (
    _closed,
    _within,
    cancel_requested,
    clear_cancel,
)
from carbon.reconstruction.miner_launch import recover as _recover_launches
from carbon.reconstruction.miner_launch import request_cancel as _request_cancel
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.profile import compile_development_profile
from carbon.reconstruction.repeats import (
    DevelopmentReplica,
    development_replicate_digest,
    freeze_development_repeat_plan,
)
from carbon.reconstruction.worker.model import (
    WorkerCode,
    WorkerFailure,
    exact_digest,
    exact_token,
)
from carbon.resource_policy import (
    BoundReconstructionReplicate,
    ReconstructionReplicateIdentity,
)
from carbon.seeding import DerivedSeed

LAUNCH_SCHEMA = "carbon.accelerator-validator-launch.v1"
CANCEL_SCHEMA = "carbon.accelerator-validator-cancel.v1"
RECOVER_SCHEMA = "carbon.accelerator-validator-recover.v1"

#: The operator-installed record naming the registered validator worker image.
#: It lives in the host root beside the device record, is written by an operator
#: from a build manifest, and is read here through the existing image mechanism.
VALIDATOR_IMAGE_RECORD = "validator-worker-image.json"

# Every field a validator launch needs, and nothing it does not. Closed, so an
# unexpected key is refused rather than ignored.
#
# Note what is *absent* against the miner manifest: there is no `image`. A
# validator's execution class is Carbon's to pin, so the image is not something
# a manifest gets to state - correctly or otherwise. Adding it here as a field
# that must merely *match* the registered record would be weaker: it would make
# the submitted value part of the conversation.
REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "replicate_id",
        "paths",
        "plan_ref",
        "policy_ref",
        "resource_class_ref",
    }
)
REQUIRED_PATHS = frozenset({"plan", "training_archive", "randomness"})
REQUIRED_PLAN_REF = frozenset(
    {
        "challenge_id",
        "challenge_version",
        "schema_version",
        "canonicalization_profile",
        "digest",
    }
)
REQUIRED_POLICY_REF = frozenset(
    {
        "challenge_id",
        "challenge_version",
        "object_id",
        "object_version",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ValidatorLaunchRequest:
    """One assembled validator reconstruction, read from a manifest.

    Materials only. The absence of an `image` field is the point of the type:
    see `REQUIRED_FIELDS`.
    """

    root: Path
    document: dict

    @classmethod
    def load(cls, path: Path) -> ValidatorLaunchRequest:
        path = Path(path).resolve()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise WorkerFailure(WorkerCode.INVALID) from None
        _closed(document, REQUIRED_FIELDS)
        if document["schema"] != LAUNCH_SCHEMA:
            raise WorkerFailure(WorkerCode.INVALID)
        _closed(document["paths"], REQUIRED_PATHS)
        _closed(document["plan_ref"], REQUIRED_PLAN_REF)
        _closed(document["policy_ref"], REQUIRED_POLICY_REF)
        _closed(document["resource_class_ref"], REQUIRED_POLICY_REF)
        if type(document["replicate_id"]) is not str or not document["replicate_id"]:
            raise WorkerFailure(WorkerCode.INVALID)
        return cls(path.parent, document)

    def plan(self):
        from carbon.registry import ChallengeKey

        reference = self.document["plan_ref"]
        expected = ResolvedConstructionPlanRef(
            ChallengeKey(reference["challenge_id"], reference["challenge_version"]),
            reference["schema_version"],
            reference["canonicalization_profile"],
            reference["digest"],
        )
        payload = _within(self.root, self.document["paths"]["plan"]).read_bytes()
        return decode_resolved_construction_plan(payload, expected_ref=expected)

    def training_archive(self) -> PublicTrainingArchive:
        # Type-enforced public at construction: any role but TRAIN is refused
        # there, so a manifest cannot point this at protected material. The
        # validator path needs that guarantee more than the miner path does,
        # because this is the side that holds protected material at all.
        return PublicTrainingArchive.from_file(
            _within(self.root, self.document["paths"]["training_archive"]),
            provenance="validator_lane_launch",
        )

    def derived_seed(self) -> DerivedSeed:
        return DerivedSeed(
            _within(self.root, self.document["paths"]["randomness"]).read_bytes()
        )

    def refs(self):
        """The policy and resource-class identities this launch is bound to."""
        from carbon.registry import ChallengeKey
        from carbon.resource_policy import ResearchResourcePolicyRef, ResourceClassRef

        def build(ref_type, values):
            return ref_type(
                ChallengeKey(values["challenge_id"], values["challenge_version"]),
                values["object_id"],
                values["object_version"],
                values["schema_version"],
                values["canonicalization_profile"],
                values["content_digest"],
            )

        return (
            build(ResearchResourcePolicyRef, self.document["policy_ref"]),
            build(ResourceClassRef, self.document["resource_class_ref"]),
        )


def registered_image(*, host_root: Path | None = None):
    """The validator worker image this host is registered to run.

    Resolved from the operator-installed record through the existing image
    mechanism, which validates the document's exact closed shape and schema. It
    fails closed: an absent, malformed or unreadable record refuses the launch
    rather than falling back to whatever image happens to be present.

    Deliberately not a parameter of `launch()`. The execution class is the one
    thing on this path that a submission must not be able to influence, and the
    cheapest way to guarantee that is for the value never to travel with the
    submission at all. Nothing in the manifest names a path, a host root or an
    image, so there is no manifest content that could redirect this; `HOST_ROOT`
    is a fixed path in source and is not configurable by environment.

    The record itself must be a real file, not a link to one. Every other
    operator-private input on this path refuses a symlink, and an execution class
    resolved through a link is a class someone else can repoint.
    """
    from carbon.reconstruction.worker.accelerator_runtime import HOST_ROOT
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    root = Path(host_root) if host_root is not None else HOST_ROOT
    path = root / VALIDATOR_IMAGE_RECORD
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise WorkerFailure(WorkerCode.INVALID)
    return load_image_identity(path)


def request_cancel(*, state_root: Path, execution_id: str) -> Path:
    """Ask a running launch on this host to stop. Durable, destroys nothing.

    **Deliberately lane-independent, exactly as `recover` is.** The request is
    keyed by execution id alone, so this entry point can stop a miner-lane launch
    on the same host and the miner entry point can stop a validator-lane one.
    That is the intended semantics, not an oversight, and it is tested in both
    directions.

    The reason is that an execution id already names exactly one admitted
    execution, which ran in exactly one lane. Adding the lane to the key would
    disambiguate nothing; it would only create a way for a *correct* cancel to
    silently fail to match. For a cooperative stop whose purpose is halting spend
    on rented compute, a cancel that quietly misses is the dangerous failure, not
    one that reaches across lanes.

    It grants nothing either way. `state_root` is operator-private, so anyone who
    can write a request into it already controls the host, and the request only
    asks a run to stop at its own next boundary and perform its own cleanup.
    """
    return _request_cancel(
        state_root=state_root, execution_id=execution_id, schema=CANCEL_SCHEMA
    )


def recover(*, state_root: Path, cli=None, dry_run: bool = False) -> dict:
    """Remove containers this host's unfinished launches still own.

    Delegated rather than reimplemented. Reclaiming a container that a launch
    still owns is a property of the host and its launch store, not of the lane
    the launch ran in, so a second copy here could only drift from the first.
    What differs is the label on the report, which names the tool that produced
    it.
    """
    return _recover_launches(
        state_root=state_root, cli=cli, dry_run=dry_run, schema=RECOVER_SCHEMA
    )


def launch(
    *,
    request: ValidatorLaunchRequest,
    state_root: Path,
    queue_path: Path | None = None,
    host_root: Path | None = None,
    cli=None,
    worker_id: str = "validator-lane",
):
    """Claim one admitted execution and reconstruct it on the validator lane.

    Assembly only, and the same assembly the miner path performs - the
    difference is which role is fixed, and where the image comes from.

    There is no backend parameter and no fallback. If the compiled plan does not
    declare an accelerator execution profile, the controller refuses the role
    rather than quietly reconstructing on CPU: a validator that asked for GPU and
    silently got CPU would produce a result whose record does not describe how it
    was computed, which is the failure this whole ticket exists to prevent. Where
    policy selects CPU, CPU stays CPU, and that is the `repeats.py` path, not
    this one.
    """
    from carbon.reconstruction.worker.controller import IsolatedReconstructionController
    from carbon.reconstruction.worker.docker_runtime import DockerCLI

    state_root = Path(state_root).resolve()
    queue = DurableExecutionQueue(
        Path(queue_path)
        if queue_path
        else state_root / "validator-launch-queue.sqlite3"
    )
    # Resolved before anything is claimed. A host that is not registered to run
    # validator work should not take work off the queue and then discover it.
    image = registered_image(host_root=host_root)

    claim_id = exact_token(f"validator-{os.getpid()}")
    claimed = queue.claim_next(worker_id, claim_id=claim_id)
    if claimed is None:
        # Nothing admitted. Not an error in the work, and nothing is invented to
        # give the host something to do.
        raise WorkerFailure(WorkerCode.UNAVAILABLE)

    binding = claimed.binding
    plan = request.plan()
    archive = request.training_archive()
    seed = request.derived_seed()
    policy_ref, resource_class_ref = request.refs()
    profile = compile_development_profile(plan)
    plan_ref = plan.to_ref()

    # The manifest and the admitted binding must describe the same work, checked
    # before anything is staged. A mismatch means this host was handed materials
    # for a different execution, which on the validator side would mean grading
    # one submission with another's inputs.
    if (
        plan_ref.content_digest != binding.resolved_plan_digest
        or profile.profile_digest != binding.reconstruction_policy_digest
        or policy_ref.content_digest != binding.resource_policy_digest
    ):
        raise WorkerFailure(WorkerCode.POLICY)

    execution = claimed.claim.ref
    request_digest = exact_digest(plan_ref.content_digest)

    placeholder = BoundReconstructionReplicate(
        ReconstructionReplicateIdentity(
            plan.challenge_key,
            plan_ref,
            policy_ref,
            resource_class_ref,
            request.document["replicate_id"],
            request_digest,
        )
    )
    randomness = _digest(seed.as_backend_bytes())
    replicate_digest = development_replicate_digest(
        binding=placeholder,
        execution_ref=execution,
        randomness_digest=randomness,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
    )
    replica = DevelopmentReplica(
        BoundReconstructionReplicate(
            _replace(placeholder.replicate_identity, replicate_digest=replicate_digest)
        ),
        execution,
        randomness,
    )
    repeat = freeze_development_repeat_plan(
        plan_id="validator-" + request_digest[7:35],
        construction_plan_digest=plan_ref.content_digest,
        training_data_digest=archive.content_digest,
        request_digest=request_digest,
        replicas=(replica,),
    )

    controller = IsolatedReconstructionController(
        state_root=state_root,
        execution_queue=queue,
        image=image,
        cli=cli or DockerCLI(),
    )
    execution_id = f"{execution.submission_id.value}-{execution.attempt_number}"

    def cancelled() -> bool:
        return cancel_requested(state_root=state_root, execution_id=execution_id)

    try:
        return controller.execute(
            claimed=claimed,
            repeat_plan=repeat,
            replica=replica,
            plan=plan,
            training_archive=archive,
            derived_seed=seed,
            # Fixed. Not a parameter, not read from the manifest, not derived
            # from anything a submitter controls.
            accelerator_role=AcceleratorRole.VALIDATOR_RECONSTRUCTION,
            cancelled=cancelled,
        )
    finally:
        # A served request must not cancel whatever runs next on this host.
        clear_cancel(state_root=state_root, execution_id=execution_id)


def launch_lane() -> AcceleratorLane:
    """The lane a launch from this module runs in. Derived, never chosen."""
    from carbon.reconstruction.accelerators import lane_for_role

    return lane_for_role(AcceleratorRole.VALIDATOR_RECONSTRUCTION)


__all__ = [
    "CANCEL_SCHEMA",
    "LAUNCH_SCHEMA",
    "RECOVER_SCHEMA",
    "VALIDATOR_IMAGE_RECORD",
    "ValidatorLaunchRequest",
    "cancel_requested",
    "clear_cancel",
    "launch",
    "launch_lane",
    "recover",
    "registered_image",
    "request_cancel",
]
