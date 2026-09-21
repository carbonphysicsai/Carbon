"""Which cores a worker gets is resolved from the host, not written down.

The allocation used to be the literal `"0,1"` - not "two cores", but *those* two
cores - enforced on the create path and again on the kernel-visible check. Two
concurrent reconstructions were impossible on any host, because both demanded the
same pair. A validator working a queue was serialised by a string literal.

Measured before it was changed: varying the container's actual CPU allocation
across one, two, four and eight usable cores left `checkpoint/state.npz`
byte-identical, as did memory ceilings of 2, 4 and 8 GiB, and two simultaneous
in-class runs on disjoint core sets. The allocation is resource policy, not part
of what determines the numbers - which is why it can be resolved per host at all.

No container is created here and no daemon is contacted.
"""

from __future__ import annotations

import pytest

from carbon.reconstruction.host_execution import (
    HOST_EXECUTION_RECORD,
    HOST_EXECUTION_SCHEMA,
    HostExecutionRecord,
    derive_cpuset,
    parse_cpuset,
    resolve_cpuset,
)
from carbon.reconstruction.worker.model import CPU_COUNT, MEMORY_BYTES, WorkerFailure


@pytest.mark.parametrize(
    ("value", "cores"),
    [
        ("0", (0,)),
        ("0,1", (0, 1)),
        ("0-3", (0, 1, 2, 3)),
        ("2-3,8", (2, 3, 8)),
        ("8,2-3", (2, 3, 8)),
    ],
)
def test_a_cpuset_is_parsed_into_the_set_it_denotes(value, cores):
    """Parsed, not pattern-matched: the set is what both checks compare."""
    assert parse_cpuset(value) == cores


@pytest.mark.parametrize(
    "value", ["", "1-0", "0,0", "0-3,3", "a", "0,", ",0", "-1", "0 1", None, 1]
)
def test_a_malformed_or_repeating_cpuset_is_refused(value):
    """A cpuset naming a core twice is not a larger allocation."""
    with pytest.raises(WorkerFailure):
        parse_cpuset(value)


def test_the_default_is_derived_from_the_host_rather_than_named():
    assert derive_cpuset(20) == ",".join(str(i) for i in range(CPU_COUNT))
    assert derive_cpuset(CPU_COUNT) == ",".join(str(i) for i in range(CPU_COUNT))
    # A host too small for the registered minimum is refused rather than
    # silently given fewer cores than the worker is built to use.
    with pytest.raises(WorkerFailure):
        derive_cpuset(CPU_COUNT - 1)


def test_an_absent_record_means_the_derived_default(tmp_path):
    """Not having thought about core placement must not block a run."""
    assert HostExecutionRecord.load(tmp_path) is None
    assert resolve_cpuset(logical_cpus=16, root=tmp_path) == derive_cpuset(16)


def _install(root, **overrides):
    from carbon.development_session.profile import canonical

    document = {
        "schema": HOST_EXECUTION_SCHEMA,
        "cpuset": "4-7",
        "memory_bytes": MEMORY_BYTES,
    }
    document.update(overrides)
    path = root / HOST_EXECUTION_RECORD
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    return path


def test_an_installed_record_places_the_worker_elsewhere(tmp_path):
    """The point of the change: a second worker can have different cores."""
    _install(tmp_path)
    assert resolve_cpuset(logical_cpus=16, root=tmp_path) == "4-7"


def test_a_record_naming_cores_the_host_lacks_is_refused(tmp_path):
    """A mistake worth failing on rather than silently trimming."""
    _install(tmp_path, cpuset="30-31")
    with pytest.raises(WorkerFailure):
        resolve_cpuset(logical_cpus=16, root=tmp_path)


def test_a_record_cannot_widen_the_registered_memory_ceiling(tmp_path):
    """Placement is the operator's; the budget the worker enforces is not."""
    _install(tmp_path, memory_bytes=MEMORY_BYTES * 2)
    with pytest.raises(WorkerFailure):
        HostExecutionRecord.load(tmp_path)


def test_a_present_but_broken_record_fails_rather_than_defaulting(tmp_path):
    """An operator who installed a record meant something by it."""
    (tmp_path / HOST_EXECUTION_RECORD).write_bytes(b"{not json")
    (tmp_path / HOST_EXECUTION_RECORD).chmod(0o600)
    with pytest.raises(WorkerFailure):
        resolve_cpuset(logical_cpus=16, root=tmp_path)

    _install(tmp_path, schema="carbon.something-else.v1")
    with pytest.raises(WorkerFailure):
        resolve_cpuset(logical_cpus=16, root=tmp_path)


# --- the create path no longer demands one particular pair of cores -----------


def _worker_profile():
    from carbon.reconstruction.worker.model import DevelopmentWorkerProfile

    return DevelopmentWorkerProfile("sha256:" + "2" * 64, "sha256:" + "3" * 64)


@pytest.mark.parametrize("cpuset", ["0,1", "0-3", "4-7", "2-3,8", "0"])
def test_any_well_formed_allocation_is_accepted_for_create(tmp_path, cpuset):
    """Two workers on different cores is the case that used to be impossible."""
    from carbon.reconstruction.worker.docker_runtime import create_arguments

    arguments = create_arguments(
        container_name="carbon-c03-fixture",
        image_id="sha256:" + "a" * 64,
        input_directory=tmp_path,
        cpuset=cpuset,
        launch_digest="sha256:" + "b" * 64,
        worker_profile=_worker_profile(),
    )
    assert "--cpuset-cpus" in arguments
    assert arguments[arguments.index("--cpuset-cpus") + 1] == cpuset


@pytest.mark.parametrize("cpuset", ["", "1-0", "0,0", "nonsense"])
def test_a_malformed_allocation_is_still_refused_for_create(tmp_path, cpuset):
    from carbon.reconstruction.worker.docker_runtime import create_arguments

    with pytest.raises(WorkerFailure):
        create_arguments(
            container_name="carbon-c03-fixture",
            image_id="sha256:" + "a" * 64,
            input_directory=tmp_path,
            cpuset=cpuset,
            launch_digest="sha256:" + "b" * 64,
            worker_profile=_worker_profile(),
        )
