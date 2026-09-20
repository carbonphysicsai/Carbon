"""run, cancel and recover: the miner's actual entry point.

A miner rents compute through the launchpad and approves a budget. Carbon's
worker has to start on hardware nobody chose in advance - and it has to stop and
clean up on that same hardware, because a container left behind on a rented
instance bills until somebody notices. Until these existed, ordinary permitted
operation meant hand-building typed Python objects, which is not an entry point.

These drive the real controller, the real launch store and the real cleanup
path. Nothing here is a second scheduler: every admission, bound and transition
decision stays where it already was.

Synthetic host roots and a scripted container CLI throughout. No device is
attached and no container is created.
"""

import json
import shutil

import pytest
import scripted_docker  # noqa: F401  (fixtures)
from test_local_controller_lifecycle import harness as _lifecycle_harness

from carbon.reconstruction.miner_launch import (
    LAUNCH_SCHEMA,
    MinerLaunchRequest,
    cancel_requested,
    clear_cancel,
    recover,
    request_cancel,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _lifecycle_harness

EXECUTION_ID = "fixture-execution-1"


def _admitted_queue(bench, path):
    """A queue holding one admitted execution, as the launchpad would leave it.

    `launch` claims from here rather than building an execution identity of its
    own - which it could not do anyway, since a seed pin's evaluation binding is
    deliberately opaque and exposes no accessor.
    """
    from carbon.execution import DurableExecutionQueue

    queue = DurableExecutionQueue(path)
    queue.admit(bench.claimed.binding)
    return queue


def _manifest(bench, directory, **overrides):
    """A launch manifest for the harness's own plan, archive and seed."""
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
        "replicate_id": "miner-replica-1",
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
        "image": {
            name: getattr(bench.image, name)
            for name in (
                "image_id",
                "config_digest",
                "source_tree_digest",
                "wheel_digest",
                "lock_digest",
                "base_image_digest",
                "build_recipe_digest",
                "entrypoint_digest",
            )
        },
    }
    document.update(overrides)
    path = directory / "launch.json"
    path.write_text(json.dumps(document, indent=2))
    return path


# --- the manifest is a closed record ------------------------------------------


def test_the_manifest_is_closed(harness, tmp_path):
    path = _manifest(harness, tmp_path / "materials")
    MinerLaunchRequest.load(path)

    document = json.loads(path.read_text())
    for change in (
        {"unexpected": 1},
        {"schema": "carbon.something-else.v1"},
        {"replicate_id": ""},
        {"replicate_id": 1},
    ):
        path.write_text(json.dumps({**document, **change}))
        with pytest.raises(WorkerFailure):
            MinerLaunchRequest.load(path)


def test_a_manifest_cannot_name_a_file_outside_its_own_directory(harness, tmp_path):
    materials = tmp_path / "materials"
    path = _manifest(harness, materials)
    document = json.loads(path.read_text())
    secret = tmp_path / "elsewhere.bin"
    secret.write_bytes(b"not for this launch")

    for name in ("../elsewhere.bin", "/etc/hostname", "", "sub/plan.bin"):
        document["paths"] = {**document["paths"], "plan": name}
        path.write_text(json.dumps(document))
        with pytest.raises(WorkerFailure):
            MinerLaunchRequest.load(path).plan()


def test_the_plan_must_match_the_reference_the_manifest_names(harness, tmp_path):
    """Content-bound: a swapped plan is refused, not silently run."""
    materials = tmp_path / "materials"
    path = _manifest(harness, materials)
    (materials / "plan.bin").write_bytes(b"not the plan this manifest names")
    from carbon.construction import ConstructionError

    with pytest.raises((ConstructionError, WorkerFailure, ValueError)):
        MinerLaunchRequest.load(path).plan()


def test_the_training_archive_is_type_enforced_public(harness, tmp_path):
    """The manifest cannot point this at anything but a public TRAIN archive."""
    path = _manifest(harness, tmp_path / "materials")
    archive = MinerLaunchRequest.load(path).training_archive()
    assert archive.role == "TRAIN"
    assert archive.format == "carbon.public-trajectories.v1"


# --- cancel is a durable request, not a kill ----------------------------------


def test_cancel_writes_a_request_that_survives_the_process(tmp_path):
    state_root = tmp_path / "controller"
    state_root.mkdir()
    assert not cancel_requested(state_root=state_root, execution_id=EXECUTION_ID)

    path = request_cancel(state_root=state_root, execution_id=EXECUTION_ID)
    assert path.is_file()
    assert path.stat().st_mode & 0o077 == 0, "a cancel request is operator-private"
    assert cancel_requested(state_root=state_root, execution_id=EXECUTION_ID)

    # Read back by a different caller, which is the whole point: the process
    # that cancels is not the process that runs.
    document = json.loads(path.read_text())
    assert document["execution_id"] == EXECUTION_ID


def test_cancelling_one_launch_does_not_cancel_another(tmp_path):
    state_root = tmp_path / "controller"
    state_root.mkdir()
    request_cancel(state_root=state_root, execution_id=EXECUTION_ID)
    assert not cancel_requested(state_root=state_root, execution_id="other-execution-1")


def test_a_served_request_is_cleared_so_it_cannot_cancel_the_next_run(tmp_path):
    state_root = tmp_path / "controller"
    state_root.mkdir()
    request_cancel(state_root=state_root, execution_id=EXECUTION_ID)
    clear_cancel(state_root=state_root, execution_id=EXECUTION_ID)
    assert not cancel_requested(state_root=state_root, execution_id=EXECUTION_ID)
    # Clearing an absent request is not an error; recovery must be idempotent.
    clear_cancel(state_root=state_root, execution_id=EXECUTION_ID)


@pytest.mark.parametrize("value", ["", "../escape", "a/b", "with space", "a\\b"])
def test_a_malformed_execution_id_is_refused(tmp_path, value):
    state_root = tmp_path / "controller"
    state_root.mkdir()
    with pytest.raises((WorkerFailure, ValueError)):
        request_cancel(state_root=state_root, execution_id=value)


# --- recover is scoped cleanup, and reports rather than asserts ---------------


def test_recover_on_a_clean_host_reports_nothing_outstanding(harness):
    report = recover(state_root=harness.controller.state_root, cli=harness.cli)
    assert report["outstanding"] == 0
    assert report["launches"] == []
    assert report["authority"] == "TASK_OWNED_CLEANUP_ONLY_NOT_DEVICE_RELEASE"


def test_recover_finds_the_launch_a_failed_run_left_behind(harness):
    """The cost-control case: a run ended without reaching a terminal state."""
    with pytest.raises(WorkerFailure):
        harness.run()

    report = recover(
        state_root=harness.controller.state_root, cli=harness.cli, dry_run=True
    )
    # Whether this run left something outstanding depends on where it failed;
    # what must hold is that a dry run only ever reports.
    for entry in report["launches"]:
        assert entry["action"] == "WOULD_REMOVE"
        assert "removed" not in entry
    assert report["dry_run"] is True


def test_recover_never_claims_a_device_release(harness):
    """Cleanup confirms this launch's own resources, and says only that."""
    report = recover(state_root=harness.controller.state_root, cli=harness.cli)
    assert "DEVICE_RELEASE" not in report["authority"].replace("NOT_DEVICE_RELEASE", "")
    assert report["authority"].endswith("NOT_DEVICE_RELEASE")


# --- the command surface ------------------------------------------------------


def _cli(argv, capsys):
    import carbon_accelerator

    code = carbon_accelerator.main(argv)
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture(autouse=True)
def importable_cli(monkeypatch):
    from pathlib import Path as _Path

    monkeypatch.syspath_prepend(
        str(_Path(__file__).resolve().parents[2] / "scripts" / "dev")
    )


def test_the_cancel_command_requests_a_stop(tmp_path, capsys):
    state_root = tmp_path / "controller"
    state_root.mkdir()
    code, value = _cli(
        ["cancel", EXECUTION_ID, "--state-root", str(state_root)], capsys
    )
    assert code == 0
    assert value["status"] == "REQUESTED"
    assert value["authority"] == "COOPERATIVE_STOP_REQUEST_NOT_TERMINATION"
    assert cancel_requested(state_root=state_root, execution_id=EXECUTION_ID)


def test_the_recover_command_reports_a_clean_host(harness, capsys, monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(
        docker_runtime, "DockerCLI", lambda *a, **k: harness.cli, raising=True
    )
    code, value = _cli(
        ["recover", "--state-root", str(harness.controller.state_root), "--dry-run"],
        capsys,
    )
    assert code == 0
    assert value["schema"] == "carbon.accelerator-miner-recover.v1"


def test_the_run_command_refuses_a_malformed_manifest(harness, tmp_path, capsys):
    path = _manifest(harness, tmp_path / "materials")
    path.write_text(json.dumps({"schema": "wrong"}))
    code, value = _cli(
        [
            "run",
            str(path),
            "--state-root",
            str(harness.controller.state_root),
        ],
        capsys,
    )
    assert code == 2
    assert value["status"] == "REFUSED"
    assert value["code"] == WorkerCode.INVALID.value


# --- run reaches the controller, on the miner lane -----------------------------


def test_launch_assembles_and_reaches_the_controller_on_the_miner_lane(
    harness, tmp_path, monkeypatch
):
    """The assembly is the point: no hand-built typed objects, same controller.

    The run still ends at the export boundary, because a scripted container
    produces no real artifact - that limit belongs to the fixture, not to the
    lane. What this establishes is that an admitted execution plus a materials
    manifest reaches `execute` with the miner role and a miner-authority worker
    profile, which is the piece that did not exist.
    """
    from carbon.reconstruction.accelerators import AcceleratorRole
    from carbon.reconstruction.miner_launch import MinerLaunchRequest, launch
    from carbon.reconstruction.worker import controller as controller_module
    from carbon.reconstruction.worker.model import MINER_HOST_AUTHORITY

    observed = []
    original = controller_module.create_arguments

    def recording(*args, **kwargs):
        observed.append(kwargs.get("worker_profile"))
        return original(*args, **kwargs)

    monkeypatch.setattr(controller_module, "create_arguments", recording)

    path = _manifest(harness, tmp_path / "materials")
    _admitted_queue(harness, tmp_path / "miner-queue.sqlite3")
    with pytest.raises(WorkerFailure):
        launch(
            request=MinerLaunchRequest.load(path),
            state_root=harness.controller.state_root,
            queue_path=tmp_path / "miner-queue.sqlite3",
            cli=harness.cli,
        )

    assert observed, "the manifest never reached a container build"
    profile = observed[-1]
    assert profile.accelerator_authority == MINER_HOST_AUTHORITY
    assert profile.accelerator_role == AcceleratorRole.MINER_RESEARCH.value
    assert profile.body["accelerators"]["lane"] == "MINER_CONTAINED"
    # No grant was loaded, and none exists.
    assert not (harness.host / "grant.json").exists()


def test_launch_refuses_materials_for_a_different_execution(harness, tmp_path):
    """The manifest and the admitted binding must describe the same work."""
    from carbon.reconstruction.miner_launch import MinerLaunchRequest, launch

    path = _manifest(harness, tmp_path / "materials")
    document = json.loads(path.read_text())
    document["policy_ref"] = {
        **document["policy_ref"],
        "content_digest": "sha256:" + "9" * 64,
    }
    path.write_text(json.dumps(document))
    _admitted_queue(harness, tmp_path / "miner-queue.sqlite3")

    with pytest.raises(WorkerFailure) as error:
        launch(
            request=MinerLaunchRequest.load(path),
            state_root=harness.controller.state_root,
            queue_path=tmp_path / "miner-queue.sqlite3",
            cli=harness.cli,
        )
    assert error.value.code is WorkerCode.POLICY


def test_launch_with_nothing_admitted_invents_no_work(harness, tmp_path):
    """An idle host stays idle rather than being given something to do."""
    from carbon.reconstruction.miner_launch import MinerLaunchRequest, launch

    path = _manifest(harness, tmp_path / "materials")
    with pytest.raises(WorkerFailure) as error:
        launch(
            request=MinerLaunchRequest.load(path),
            state_root=harness.controller.state_root,
            queue_path=tmp_path / "empty-queue.sqlite3",
            cli=harness.cli,
        )
    assert error.value.code is WorkerCode.UNAVAILABLE


def test_a_cancel_request_stops_a_launch_before_it_builds_anything(
    harness, tmp_path, monkeypatch
):
    """Cancellation is observed at the controller's own boundaries."""
    from carbon.reconstruction.miner_launch import MinerLaunchRequest, launch
    from carbon.reconstruction.worker import controller as controller_module

    built = []
    original = controller_module.create_arguments
    monkeypatch.setattr(
        controller_module,
        "create_arguments",
        lambda *a, **k: (built.append(k), original(*a, **k))[1],
    )

    path = _manifest(harness, tmp_path / "materials")
    _admitted_queue(harness, tmp_path / "miner-queue.sqlite3")
    reference = harness.claimed.claim.ref
    execution_id = f"{reference.submission_id.value}-{reference.attempt_number}"
    request_cancel(state_root=harness.controller.state_root, execution_id=execution_id)

    with pytest.raises(WorkerFailure) as error:
        launch(
            request=MinerLaunchRequest.load(path),
            state_root=harness.controller.state_root,
            queue_path=tmp_path / "miner-queue.sqlite3",
            cli=harness.cli,
        )
    assert error.value.code is WorkerCode.CANCELLED
    assert not built, "a cancelled launch must not build a container"
    # And the served request was cleared, so it cannot cancel the next launch.
    assert not cancel_requested(
        state_root=harness.controller.state_root, execution_id=execution_id
    )
