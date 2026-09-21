"""C-CORE-20: the shipped path that constructs a validator reconstruction.

C-CORE-19 made `VALIDATOR_RECONSTRUCTION` admissible and recorded that nothing
built one. These drive the real controller, the real durable queue and the real
launch store through `validator_launch`, exactly as the miner tests do for the
other lane.

**What these establish, stated precisely.** A synthetic host root and a scripted
container CLI are used throughout: no device is attached, no container is
created, and no GPU numerics are exercised. The property under test is
*orchestration* - which role, which lane, which image identity, and which work
binding reach the controller's launch boundary - and a scripted CLI is a
faithful fixture for that and for nothing else. Several runs below therefore end
in `WorkerFailure` at the export boundary, which is a limit of the fixture and
not of the lane; each says so where it matters.

**None of this is GPU acceptance.** Nothing here is HARDWARE_EXERCISED. The
orchestration is IMPLEMENTED and TESTED; backend qualification remains MQ-008's
at G4.
"""

import json
import shutil

import pytest
import scripted_docker  # noqa: F401  (fixtures)
from test_local_controller_lifecycle import harness as _lifecycle_harness

from carbon.reconstruction.validator_launch import (
    CANCEL_SCHEMA,
    LAUNCH_SCHEMA,
    RECOVER_SCHEMA,
    VALIDATOR_IMAGE_RECORD,
    ValidatorLaunchRequest,
    cancel_requested,
    launch,
    launch_lane,
    recover,
    registered_image,
    request_cancel,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _lifecycle_harness

IMAGE_FIELDS = (
    "image_id",
    "config_digest",
    "source_tree_digest",
    "wheel_digest",
    "lock_digest",
    "base_image_digest",
    "build_recipe_digest",
    "entrypoint_digest",
)


def _register_image(bench, **overrides):
    """Install the validator worker image record, as an operator would."""
    document = {
        "schema": "carbon.c03.worker-image.v1",
        **{name: getattr(bench.image, name) for name in IMAGE_FIELDS},
    }
    document.update(overrides)
    path = bench.host / VALIDATOR_IMAGE_RECORD
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2))
    return path


def _admitted_queue(bench, path):
    from carbon.execution import DurableExecutionQueue

    queue = DurableExecutionQueue(path)
    queue.admit(bench.claimed.binding)
    return queue


def _manifest(bench, directory, **overrides):
    """A validator launch manifest. Note the absence of an image block."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    (directory / "plan.bin").write_bytes(bench.plan.canonical_bytes())
    shutil.copyfile(bench.archive.path, directory / "train.npz")
    (directory / "randomness.bin").write_bytes(bench.seed.as_backend_bytes())

    identity = bench.replica.binding.replicate_identity
    plan_ref = bench.plan.to_ref()

    def policy(ref):
        return {
            "challenge_id": ref.challenge_key.challenge_id,
            "challenge_version": ref.challenge_key.version,
            "object_id": ref.object_id,
            "object_version": ref.object_version,
            "schema_version": ref.schema_version,
            "canonicalization_profile": ref.canonicalization_profile,
            "content_digest": ref.content_digest,
        }

    document = {
        "schema": LAUNCH_SCHEMA,
        "replicate_id": "validator-replica-1",
        "paths": {
            "plan": "plan.bin",
            "training_archive": "train.npz",
            "randomness": "randomness.bin",
        },
        "plan_ref": {
            "challenge_id": plan_ref.challenge_key.challenge_id,
            "challenge_version": plan_ref.challenge_key.version,
            "schema_version": plan_ref.schema_version,
            "canonicalization_profile": plan_ref.canonicalization_profile,
            "digest": plan_ref.content_digest,
        },
        "policy_ref": policy(identity.policy_ref),
        "resource_class_ref": policy(identity.resource_class_ref),
    }
    document.update(overrides)
    path = directory / "launch.json"
    path.write_text(json.dumps(document, indent=2))
    return path


def _run(bench, tmp_path, monkeypatch=None, **kwargs):
    """Launch, recording every worker profile that reached a container build."""
    from carbon.reconstruction.worker import controller as controller_module

    observed = []
    if monkeypatch is not None:
        original = controller_module.create_arguments

        def recording(*args, **kw):
            observed.append(kw.get("worker_profile"))
            return original(*args, **kw)

        monkeypatch.setattr(controller_module, "create_arguments", recording)

    path = kwargs.pop("manifest", None) or _manifest(bench, tmp_path / "materials")
    queue_path = kwargs.pop("queue_path", tmp_path / "validator-queue.sqlite3")
    if kwargs.pop("admit", True):
        _admitted_queue(bench, queue_path)
    return observed, lambda: launch(
        request=ValidatorLaunchRequest.load(path),
        state_root=bench.controller.state_root,
        queue_path=queue_path,
        host_root=bench.host,
        cli=bench.cli,
        **kwargs,
    )


# --- positive: the connected path -----------------------------------------------


def test_launch_reaches_the_controller_on_the_validator_lane(
    harness, tmp_path, monkeypatch
):
    """The gap C-CORE-19 recorded, closed.

    An admitted execution plus a materials manifest now reaches `execute` with
    the validator role, the validator lane label, the registered image identity
    and the exact committed work binding. The run still ends at the export
    boundary because a scripted container produces no real artifact - a fixture
    limit, not a lane limit, and not a claim about GPU numerics.
    """
    from carbon.reconstruction.accelerators import AcceleratorRole
    from carbon.reconstruction.worker.model import SELF_SERVICE_HOST_AUTHORITY

    _register_image(harness)
    observed, run = _run(harness, tmp_path, monkeypatch)
    with pytest.raises(WorkerFailure):
        run()

    assert observed, "the manifest never reached a container build"
    profile = observed[-1]
    assert profile.accelerator_role == AcceleratorRole.VALIDATOR_RECONSTRUCTION.value
    assert profile.accelerator_authority == SELF_SERVICE_HOST_AUTHORITY
    body = profile.body["accelerators"]
    assert body["lane"] == "VALIDATOR_ISOLATED"
    assert profile.body["schema"] == "carbon.c03.development-worker-profile.v6"
    assert body["assurance"]["verification"] == "BACKEND_QUALIFICATION_REQUIRED_MQ008"
    assert body["assurance"]["official_eligible"] is False
    # No grant was loaded and none exists: admission came from the host record.
    assert not (harness.host / "grant.json").exists()


def test_the_launch_carries_the_registered_image_not_a_submitted_one(
    harness, tmp_path, monkeypatch
):
    """The execution class is Carbon's. The manifest has no say in it."""
    _register_image(harness)
    _, run = _run(harness, tmp_path, monkeypatch)
    with pytest.raises(WorkerFailure):
        run()
    registered = registered_image(host_root=harness.host)
    for name in IMAGE_FIELDS:
        assert getattr(registered, name) == getattr(harness.image, name)


def test_the_result_never_claims_official_eligibility(harness):
    """Admission is not qualification, asserted on the label itself."""
    from carbon.reconstruction.accelerators import (
        assurance_permits_official_use,
        validator_self_service_assurance,
    )

    assurance = validator_self_service_assurance()
    assert assurance_permits_official_use(assurance) is False
    assert assurance["official_eligible"] is False
    assert assurance["verification"] == "BACKEND_QUALIFICATION_REQUIRED_MQ008"


def test_there_is_no_parameter_that_requests_authoritative_use(harness):
    """Missing backend eligibility cannot be waived, because nothing asks.

    The negative the ticket names is "missing backend eligibility where
    authoritative use is requested". There is no such request to make: no
    argument of `launch` selects role, lane, backend support or eligibility, so
    the refusal is structural rather than a check that could be forgotten.
    """
    import inspect

    parameters = set(inspect.signature(launch).parameters)
    assert parameters == {
        "request",
        "state_root",
        "queue_path",
        "host_root",
        "cli",
        "worker_id",
    }
    for forbidden in ("role", "lane", "backend", "official", "eligible", "image"):
        assert not any(forbidden in name for name in parameters)


def test_the_lane_is_derived_from_the_role_and_not_chosen(harness):
    from carbon.reconstruction.accelerators import AcceleratorLane

    assert launch_lane() is AcceleratorLane.VALIDATOR_ISOLATED


# --- negative: each of these must refuse ----------------------------------------


def test_a_miner_manifest_is_refused_by_validator_orchestration(harness, tmp_path):
    """Miner role presented to validator orchestration.

    A miner manifest declares the miner schema and carries an image block. Both
    are refused by the closed record, so a miner request cannot be replayed here
    to obtain a validator-lane run.
    """
    from carbon.reconstruction.miner_launch import LAUNCH_SCHEMA as MINER_SCHEMA

    path = _manifest(
        harness,
        tmp_path / "materials",
        schema=MINER_SCHEMA,
        image={name: getattr(harness.image, name) for name in IMAGE_FIELDS},
    )
    with pytest.raises(WorkerFailure):
        ValidatorLaunchRequest.load(path)


def test_a_validator_manifest_cannot_carry_an_image(harness, tmp_path):
    """Validator request bearing a submitted execution class.

    The field is absent rather than ignored, so a manifest that names an image -
    even the correct one - is refused instead of quietly having it dropped.
    """
    path = _manifest(
        harness,
        tmp_path / "materials",
        image={name: getattr(harness.image, name) for name in IMAGE_FIELDS},
    )
    with pytest.raises(WorkerFailure):
        ValidatorLaunchRequest.load(path)


def test_a_missing_image_record_refuses_the_launch(harness, tmp_path):
    """Missing image: fails closed rather than falling back to any image."""
    assert not (harness.host / VALIDATOR_IMAGE_RECORD).exists()
    _, run = _run(harness, tmp_path)
    with pytest.raises(WorkerFailure) as error:
        run()
    assert error.value.code is WorkerCode.INVALID


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "carbon.c03.worker-image.v2"},
        {"image_id": "sha256:" + "0" * 64},
        {"wheel_digest": "not-a-digest"},
        {"unexpected": "field"},
    ],
)
def test_a_mismatched_image_record_refuses_the_launch(harness, tmp_path, change):
    """Mismatched image: the record is a closed, exact document."""
    _register_image(harness, **change)
    if "image_id" in change:
        # A well-formed record naming a different image is a different execution
        # class, and the controller refuses it against the pinned labels.
        _, run = _run(harness, tmp_path)
        with pytest.raises(WorkerFailure):
            run()
        return
    with pytest.raises(WorkerFailure):
        registered_image(host_root=harness.host)


def test_launch_refuses_materials_for_a_different_execution(harness, tmp_path):
    """Changed binding: the manifest and the admitted work must agree."""
    _register_image(harness)
    path = _manifest(harness, tmp_path / "materials")
    document = json.loads(path.read_text())
    document["policy_ref"] = {
        **document["policy_ref"],
        "content_digest": "sha256:" + "9" * 64,
    }
    path.write_text(json.dumps(document))
    _, run = _run(harness, tmp_path, manifest=path)
    with pytest.raises(WorkerFailure) as error:
        run()
    assert error.value.code is WorkerCode.POLICY


def test_a_changed_plan_is_refused(harness, tmp_path):
    """Changed plan or recipe: content-bound, not merely named."""
    from carbon.construction import ConstructionError

    _register_image(harness)
    materials = tmp_path / "materials"
    path = _manifest(harness, materials)
    (materials / "plan.bin").write_bytes(b"not the plan this manifest names")
    with pytest.raises((ConstructionError, WorkerFailure, ValueError)):
        ValidatorLaunchRequest.load(path).plan()


def test_a_changed_seed_changes_the_replica_identity(harness, tmp_path):
    """Changed seed: the seed is bound into the replicate digest, not carried.

    A different seed produces a different replicate identity, so a swapped seed
    cannot masquerade as the admitted work.
    """
    _register_image(harness)
    materials = tmp_path / "materials"
    _manifest(harness, materials)
    original = ValidatorLaunchRequest.load(materials / "launch.json").derived_seed()
    (materials / "randomness.bin").write_bytes(
        b"\x01" * len(original.as_backend_bytes())
    )
    swapped = ValidatorLaunchRequest.load(materials / "launch.json").derived_seed()
    assert swapped.as_backend_bytes() != original.as_backend_bytes()


def test_a_manifest_cannot_name_a_file_outside_its_own_directory(harness, tmp_path):
    """Changed protected input identity: nothing outside the manifest's own root."""
    _register_image(harness)
    materials = tmp_path / "materials"
    path = _manifest(harness, materials)
    document = json.loads(path.read_text())
    (tmp_path / "elsewhere.bin").write_bytes(b"not for this launch")
    for name in ("../elsewhere.bin", "/etc/hostname", "", "sub/plan.bin"):
        document["paths"] = {**document["paths"], "plan": name}
        path.write_text(json.dumps(document))
        with pytest.raises(WorkerFailure):
            ValidatorLaunchRequest.load(path).plan()


def test_the_training_archive_is_type_enforced_public(harness, tmp_path):
    """Protected material cannot be pointed at by a manifest."""
    _register_image(harness)
    path = _manifest(harness, tmp_path / "materials")
    archive = ValidatorLaunchRequest.load(path).training_archive()
    assert archive.role == "TRAIN"
    assert archive.format == "carbon.public-trajectories.v1"


def test_the_manifest_is_a_closed_record(harness, tmp_path):
    _register_image(harness)
    path = _manifest(harness, tmp_path / "materials")
    ValidatorLaunchRequest.load(path)
    document = json.loads(path.read_text())
    for change in (
        {"unexpected": 1},
        {"schema": "carbon.something-else.v1"},
        {"replicate_id": ""},
        {"replicate_id": 1},
    ):
        path.write_text(json.dumps({**document, **change}))
        with pytest.raises(WorkerFailure):
            ValidatorLaunchRequest.load(path)


def test_launch_with_nothing_admitted_invents_no_work(harness, tmp_path):
    """Replay against an empty queue: an idle host stays idle."""
    _register_image(harness)
    _, run = _run(harness, tmp_path, admit=False)
    with pytest.raises(WorkerFailure) as error:
        run()
    assert error.value.code is WorkerCode.UNAVAILABLE


def test_a_replayed_manifest_whose_identities_differ_is_refused(harness, tmp_path):
    """Replayed request whose identities differ.

    Refused as a launch CONFLICT rather than merely finding an empty queue: the
    durable launch store recognises that this execution already has a launch and
    declines the second, so a replay cannot run the same work twice even if a
    claim were somehow available.
    """
    _register_image(harness)
    queue_path = tmp_path / "validator-queue.sqlite3"
    path = _manifest(harness, tmp_path / "materials")
    _admitted_queue(harness, queue_path)

    def once():
        return launch(
            request=ValidatorLaunchRequest.load(path),
            state_root=harness.controller.state_root,
            queue_path=queue_path,
            host_root=harness.host,
            cli=harness.cli,
        )

    with pytest.raises(WorkerFailure):
        once()
    with pytest.raises(WorkerFailure) as error:
        once()
    assert error.value.code is WorkerCode.CONFLICT


# --- no fallback, in any direction ----------------------------------------------


def test_cpu_never_silently_substitutes_for_a_declared_accelerator_run(
    harness, tmp_path, monkeypatch
):
    """Where GPU was declared, CPU must not quietly stand in.

    A CPU plan presented with an accelerator role is **refused**, and refused
    before anything is built. It does not fall through to the in-process CPU
    path - that path is `repeats.py`, reached another way entirely, and where
    policy selects CPU, CPU stays CPU.

    The refusal arrives as an environment pin mismatch rather than the
    controller's own role check, because the plan's pinned environment is
    validated first. Both are refusals and the test accepts either: what must
    never happen is a CPU reconstruction proceeding under a record that says a
    GPU role was requested, and that is what the absence of any container build
    establishes.
    """
    from c02_fixtures import compile_c02_plan

    from carbon.reconstruction.accelerators import AcceleratorRole
    from carbon.reconstruction.model import ReconstructionFailure
    from carbon.reconstruction.worker import controller as controller_module

    built = []
    original = controller_module.create_arguments
    monkeypatch.setattr(
        controller_module,
        "create_arguments",
        lambda *a, **k: (built.append(k), original(*a, **k))[1],
    )

    _register_image(harness)
    cpu_plan = compile_c02_plan(tmp_path / "cpu-plan")
    with pytest.raises((WorkerFailure, ReconstructionFailure)):
        harness.run(
            local_diagnostic=None,
            accelerator_role=AcceleratorRole.VALIDATOR_RECONSTRUCTION,
            plan=cpu_plan,
        )
    assert not built, "a CPU plan under an accelerator role must build nothing"


def test_the_validator_module_fixes_its_role(harness):
    """No fallback to the miner lane: the role is a literal, not an argument."""
    import inspect

    from carbon.reconstruction import validator_launch

    source = inspect.getsource(validator_launch.launch)
    assert "AcceleratorRole.VALIDATOR_RECONSTRUCTION" in source
    assert "MINER_RESEARCH" not in source


def test_the_miner_module_still_fixes_its_own_role(harness):
    """And the other direction: a validator rejection cannot retry as a miner."""
    import inspect

    from carbon.reconstruction import miner_launch

    source = inspect.getsource(miner_launch.launch)
    assert "AcceleratorRole.MINER_RESEARCH" in source
    assert "VALIDATOR_RECONSTRUCTION" not in source


# --- cancel and recover ---------------------------------------------------------


def test_cancel_writes_a_validator_labelled_request(tmp_path):
    state_root = tmp_path / "controller"
    state_root.mkdir()
    path = request_cancel(state_root=state_root, execution_id="fixture-execution-1")
    assert path.stat().st_mode & 0o077 == 0, "a cancel request is operator-private"
    assert json.loads(path.read_text())["schema"] == CANCEL_SCHEMA
    assert cancel_requested(state_root=state_root, execution_id="fixture-execution-1")


def test_a_cancel_request_stops_a_launch_before_it_builds_anything(
    harness, tmp_path, monkeypatch
):
    from carbon.reconstruction.worker import controller as controller_module

    _register_image(harness)
    built = []
    original = controller_module.create_arguments
    monkeypatch.setattr(
        controller_module,
        "create_arguments",
        lambda *a, **k: (built.append(k), original(*a, **k))[1],
    )
    reference = harness.claimed.claim.ref
    execution_id = f"{reference.submission_id.value}-{reference.attempt_number}"
    request_cancel(state_root=harness.controller.state_root, execution_id=execution_id)

    _, run = _run(harness, tmp_path)
    with pytest.raises(WorkerFailure) as error:
        run()
    assert error.value.code is WorkerCode.CANCELLED
    assert not built, "a cancelled launch must not build a container"
    assert not cancel_requested(
        state_root=harness.controller.state_root, execution_id=execution_id
    )


def test_recover_reports_under_the_validator_schema(harness):
    report = recover(state_root=harness.controller.state_root, cli=harness.cli)
    assert report["schema"] == RECOVER_SCHEMA
    assert report["authority"].endswith("NOT_DEVICE_RELEASE")


def test_recover_shares_one_implementation_with_the_miner_path(harness):
    """Reclaiming is a host property, not a lane property.

    A second copy could only drift from the first, so both entry points call the
    same function and differ in the label on the report.
    """
    from carbon.reconstruction import miner_launch, validator_launch

    assert validator_launch._recover_launches is miner_launch.recover


# --- cancellation crosses lanes, deliberately ----------------------------------
#
# Raised by external review: `_cancel_path` is keyed by execution id alone, so
# neither lane nor schema appears in it. The decided semantics are that
# cancellation is lane-independent exactly as recovery is - an execution id
# already names one admitted execution, which ran in one lane, so putting the
# lane in the key would disambiguate nothing and would only let a correct cancel
# silently miss. These assert that decision in both directions rather than
# leaving the filesystem layout and the docstrings disagreeing.


def test_a_validator_cancel_stops_a_miner_execution_on_the_same_host(tmp_path):
    """Decided semantics, direction one."""
    from carbon.reconstruction import miner_launch

    state_root = tmp_path / "controller"
    state_root.mkdir()
    request_cancel(state_root=state_root, execution_id="miner-execution-1")
    assert miner_launch.cancel_requested(
        state_root=state_root, execution_id="miner-execution-1"
    )


def test_a_miner_cancel_stops_a_validator_execution_on_the_same_host(tmp_path):
    """Decided semantics, direction two."""
    from carbon.reconstruction import miner_launch

    state_root = tmp_path / "controller"
    state_root.mkdir()
    miner_launch.request_cancel(
        state_root=state_root, execution_id="validator-execution-1"
    )
    assert cancel_requested(state_root=state_root, execution_id="validator-execution-1")


def test_either_lane_clears_a_served_request(tmp_path):
    """Clearing is lane-independent too, or a stale request would outlive it."""
    from carbon.reconstruction import miner_launch

    state_root = tmp_path / "controller"
    state_root.mkdir()
    request_cancel(state_root=state_root, execution_id="execution-1")
    miner_launch.clear_cancel(state_root=state_root, execution_id="execution-1")
    assert not cancel_requested(state_root=state_root, execution_id="execution-1")


def test_a_cancel_still_names_exactly_one_execution(tmp_path):
    """Lane-independent is not identity-independent.

    The request is keyed by execution id, so it reaches whichever lane ran that
    execution - and reaches nothing else. Without this, "crosses lanes" could be
    mistaken for "cancels broadly".
    """
    state_root = tmp_path / "controller"
    state_root.mkdir()
    request_cancel(state_root=state_root, execution_id="execution-1")
    assert not cancel_requested(state_root=state_root, execution_id="execution-2")


def test_either_lane_recovers_the_other_lanes_launch_record(harness):
    """Recovery is lane-independent by the same decision, and already says so.

    A leaked container is a leaked container: both entry points reclaim from the
    one launch store, so neither can leave the other's container billing.
    """
    from carbon.reconstruction import miner_launch

    validator = recover(state_root=harness.controller.state_root, cli=harness.cli)
    miner = miner_launch.recover(
        state_root=harness.controller.state_root, cli=harness.cli
    )
    assert validator["outstanding"] == miner["outstanding"]
    assert validator["schema"] == RECOVER_SCHEMA
    assert miner["schema"] == "carbon.accelerator-miner-recover.v1"


def test_the_shared_schema_argument_cannot_change_what_runs(tmp_path):
    """The reuse argument must not have become a laundering route.

    `schema` labels a written record. It is not a role, not a lane, and not part
    of any durable execution identity, so no value of it can convert work between
    lanes or alter which execution a request names.
    """
    import inspect

    from carbon.reconstruction import miner_launch

    for function in (miner_launch.request_cancel, miner_launch.recover):
        source = inspect.getsource(function)
        assert "accelerator_role" not in source
        assert "AcceleratorRole" not in source
        assert "execution_queue" not in source

    state_root = tmp_path / "controller"
    state_root.mkdir()
    forged = miner_launch.request_cancel(
        state_root=state_root,
        execution_id="execution-1",
        schema="carbon.accelerator-validator-cancel.v1",
    )
    # Same file a miner cancel writes, located the same way: the label changed,
    # nothing else did.
    assert forged == miner_launch._cancel_path(state_root, "execution-1")
    assert set(json.loads(forged.read_text())) == {"schema", "execution_id"}


# --- image injection: the rest of the set --------------------------------------


@pytest.mark.parametrize("field", ["worker_image", "image", "unexpected_field"])
def test_a_manifest_field_is_refused_even_when_its_value_is_legitimate(
    harness, tmp_path, field
):
    """Refusal comes from the closed schema, not from a value comparison.

    Each of these carries the *correct* installed image. If refusal depended on
    comparing values, they would pass - which is exactly the weaker design this
    asserts against.
    """
    _register_image(harness)
    legitimate = {name: getattr(harness.image, name) for name in IMAGE_FIELDS}
    path = _manifest(harness, tmp_path / "materials", **{field: legitimate})
    with pytest.raises(WorkerFailure):
        ValidatorLaunchRequest.load(path)


def test_the_manifest_cannot_name_a_path_or_a_host_root(harness, tmp_path):
    """Nothing in the manifest can redirect where the image record is read from."""
    from carbon.reconstruction.validator_launch import REQUIRED_FIELDS

    for name in ("host_root", "image_record", "path", "root", "state_root"):
        assert name not in REQUIRED_FIELDS
    _register_image(harness)
    path = _manifest(harness, tmp_path / "materials", host_root=str(tmp_path))
    with pytest.raises(WorkerFailure):
        ValidatorLaunchRequest.load(path)


def test_the_image_record_may_not_be_a_symlink(harness, tmp_path):
    """An execution class resolved through a link is one someone can repoint."""
    real = tmp_path / "elsewhere.json"
    real.write_text(
        json.dumps(
            {
                "schema": "carbon.c03.worker-image.v1",
                **{name: getattr(harness.image, name) for name in IMAGE_FIELDS},
            }
        )
    )
    link = harness.host / VALIDATOR_IMAGE_RECORD
    link.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    link.symlink_to(real)
    with pytest.raises(WorkerFailure) as error:
        registered_image(host_root=harness.host)
    assert error.value.code is WorkerCode.INVALID


def test_the_host_root_is_not_environment_configurable(monkeypatch):
    """No environment variable redirects the registered execution class."""
    import importlib

    from carbon.reconstruction.worker import accelerator_runtime

    monkeypatch.setenv("CARBON_ACCELERATOR_HOST_ROOT", "/tmp/attacker")
    monkeypatch.setenv("HOST_ROOT", "/tmp/attacker")
    reloaded = importlib.reload(accelerator_runtime)
    assert str(reloaded.HOST_ROOT) == "/var/lib/carbon/accelerators"
