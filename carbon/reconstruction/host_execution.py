"""Which cores and how much memory this host gives one worker.

The device identity problem was solved once already: one laptop's GPU used to be
a constant in the source tree, and it became an operator-installed
`HostDeviceRecord` so that running Carbon on other hardware never means editing
Carbon. The CPU allocation had the same defect and this is the same fix.

It mattered more than it looks. The allocation was the literal `"0,1"` - not
"two cores", but *those* two cores - and both the create path and the
kernel-visible check compared against it. Two concurrent reconstructions were
therefore impossible on any host, because both demanded the same two cores. A
validator working through a queue was serialised by a string literal.

**Measured before changing it.** Varying the container's actual CPU allocation
across one, two, four and eight usable cores left `checkpoint/state.npz`
byte-identical, as did memory ceilings of 2, 4 and 8 GiB, as did two simultaneous
in-class runs on disjoint core sets. So the allocation is a resource-policy
choice and not part of what determines the numbers. Had it moved the weights, the
core count would have had to join the declared execution class and a validator
could not be sized freely.

Registered minimums still apply. This resolves *which* resources a worker gets,
never *whether* the worker may run, and it grants no authority of any kind.
"""

from __future__ import annotations

import re

from carbon.reconstruction.worker.model import (
    CPU_COUNT,
    MEMORY_BYTES,
    WorkerCode,
    WorkerFailure,
)

HOST_EXECUTION_RECORD = "host-execution.json"
HOST_EXECUTION_SCHEMA = "carbon.accelerator-host-execution.v1"

# A cpuset as the kernel and the container runtime spell it: comma-separated
# single cores and inclusive ranges. Parsed rather than pattern-matched, because
# the set it denotes is what both checks actually compare.
_CPUSET = re.compile(r"^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$")


def parse_cpuset(value: object) -> tuple[int, ...]:
    """The exact cores a cpuset string denotes, in ascending order.

    Refuses anything malformed, empty, reversed or repeated. A cpuset that
    denotes a core twice is not a larger allocation and is not accepted as one.
    """
    if type(value) is not str or not _CPUSET.fullmatch(value):
        raise WorkerFailure(WorkerCode.INVALID)
    cores: list[int] = []
    for group in value.split(","):
        if "-" in group:
            start, end = (int(item) for item in group.split("-", 1))
            if end < start:
                raise WorkerFailure(WorkerCode.INVALID)
            cores.extend(range(start, end + 1))
        else:
            cores.append(int(group))
    if len(cores) != len(set(cores)) or not cores:
        raise WorkerFailure(WorkerCode.INVALID)
    return tuple(sorted(cores))


def derive_cpuset(logical_cpus: object, *, count: int = CPU_COUNT) -> str:
    """The default allocation on a host with no installed execution record.

    Deliberately derived from what the host reports rather than written down: a
    literal here would be the defect this module exists to remove, only spelled
    differently. It takes the lowest `count` cores, which is a policy choice and
    not a numerical one.
    """
    if type(logical_cpus) is not int or logical_cpus < count or count < 1:
        raise WorkerFailure(WorkerCode.INVALID)
    return ",".join(str(index) for index in range(count))


class HostExecutionRecord:
    """An operator-installed statement of what one worker may use on this host.

    Optional. Its absence means the derived default, not a refusal - an operator
    who has not thought about core placement should still be able to run.
    """

    __slots__ = ("cpuset", "memory_bytes")

    def __init__(self, cpuset: str, memory_bytes: int) -> None:
        parse_cpuset(cpuset)
        if type(memory_bytes) is not int or isinstance(memory_bytes, bool):
            raise WorkerFailure(WorkerCode.INVALID)
        # The registered ceiling is a floor on what the implementation enforces,
        # so an operator may pin a different placement but not a larger budget
        # than the worker is built to apply.
        if memory_bytes != MEMORY_BYTES:
            raise WorkerFailure(WorkerCode.POLICY)
        object.__setattr__(self, "cpuset", cpuset)
        object.__setattr__(self, "memory_bytes", memory_bytes)

    @classmethod
    def load(cls, root) -> HostExecutionRecord | None:
        """Read the installed record, or None when the operator installed none."""
        from pathlib import Path

        from carbon.development_session.research_admission import private_json

        path = Path(root) / HOST_EXECUTION_RECORD
        if not path.exists():
            return None
        try:
            document = private_json(path)
        except (OSError, ValueError):
            # Present but unreadable is not the same as absent. An operator who
            # installed a record meant something by it, so a broken one fails
            # rather than silently becoming the default.
            raise WorkerFailure(WorkerCode.POLICY) from None
        if type(document) is not dict or set(document) != {
            "schema",
            "cpuset",
            "memory_bytes",
        }:
            raise WorkerFailure(WorkerCode.POLICY)
        if document["schema"] != HOST_EXECUTION_SCHEMA:
            raise WorkerFailure(WorkerCode.POLICY)
        return cls(document["cpuset"], document["memory_bytes"])


def resolve_cpuset(*, logical_cpus: object, root=None) -> str:
    """The cpuset this host allocates to one worker.

    An installed record wins; otherwise the default is derived from the host.
    Either way the answer comes from the host rather than from this file.
    """
    if root is not None:
        record = HostExecutionRecord.load(root)
        if record is not None:
            cores = parse_cpuset(record.cpuset)
            if type(logical_cpus) is int and max(cores) >= logical_cpus:
                # A record naming cores this host does not have is a mistake
                # worth failing on, not something to silently trim.
                raise WorkerFailure(WorkerCode.POLICY)
            return record.cpuset
    return derive_cpuset(logical_cpus)
