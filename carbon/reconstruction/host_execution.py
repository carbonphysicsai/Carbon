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
#: v2 adds ``lanes``: the disjoint core sets of the host's grade lanes (`carbon.reconstruction.grade_lanes`), one per
#: lane, each the size of one worker. ``cpuset`` stays what every caller outside a lane-bound round uses.
HOST_EXECUTION_SCHEMA_V2 = "carbon.accelerator-host-execution.v2"

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

    __slots__ = ("cpuset", "lanes", "memory_bytes")

    def __init__(self, cpuset: str, memory_bytes: int, lanes: tuple = ()) -> None:
        parse_cpuset(cpuset)
        lanes = _checked_lanes(lanes)
        if type(memory_bytes) is not int or isinstance(memory_bytes, bool):
            raise WorkerFailure(WorkerCode.INVALID)
        # The registered ceiling is a floor on what the implementation enforces,
        # so an operator may pin a different placement but not a larger budget
        # than the worker is built to apply. A smaller one is accepted (over-broad
        # rules audit S7 H1 271: nothing reads it to grant more; the container's
        # limit comes from the worker profile).
        if memory_bytes < 1 or memory_bytes > MEMORY_BYTES:
            raise WorkerFailure(WorkerCode.POLICY)
        object.__setattr__(self, "cpuset", cpuset)
        object.__setattr__(self, "memory_bytes", memory_bytes)
        object.__setattr__(self, "lanes", lanes)

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
        v1 = {"schema", "cpuset", "memory_bytes"}
        if type(document) is not dict:
            raise WorkerFailure(WorkerCode.POLICY)
        if document.get("schema") == HOST_EXECUTION_SCHEMA and set(document) == v1:
            return cls(document["cpuset"], document["memory_bytes"])
        if document.get("schema") == HOST_EXECUTION_SCHEMA_V2 and set(document) == {
            *v1,
            "lanes",
        }:
            if type(document["lanes"]) is not list:
                raise WorkerFailure(WorkerCode.POLICY)
            return cls(
                document["cpuset"], document["memory_bytes"], tuple(document["lanes"])
            )
        raise WorkerFailure(WorkerCode.POLICY)


def _checked_lanes(lanes: object) -> tuple[str, ...]:
    """A record's lane core sets: none, or one or more, each a valid cpuset, all one size, pairwise disjoint. Anything
    else is an operator's mistake worth failing on (POLICY), never trimmed into something that looks fine. One lane is
    allowed (over-broad rules audit S7 H1 272: it protects nothing to refuse it); equal size and disjoint stay (a lane's
    cores are what a candidate's scored speed runs on, and two lanes on one core set would contend).
    """
    if type(lanes) is not tuple:
        raise WorkerFailure(WorkerCode.POLICY)
    if not lanes:
        return ()
    sets = [set(parse_cpuset(value)) for value in lanes]
    if len({len(cores) for cores in sets}) != 1:
        raise WorkerFailure(WorkerCode.POLICY)
    seen: set[int] = set()
    for cores in sets:
        if cores & seen:
            raise WorkerFailure(WorkerCode.POLICY)
        seen |= cores
    return lanes


def _fitted(cpuset: str, *, logical_cpus: object, count: int) -> str:
    """``cpuset`` (a lane's, a remote slot's or the record's) for one worker of ``count`` CPUs.

    Cores this host lacks refuse. More cores than ``count`` are narrowed to exactly ``count``, the lowest (switch 5,
    audit #5: never refused), for today's count too: a container is created with ``--cpus`` = its profile's count and
    the kernel check holds that quota to the cpuset's size, so a worker of today's count on a 4-core lane must get 2
    cores, not 4 (Validator-2, 18 Nov: else the switch-2 POLICY class again). Fewer cores than ``count`` refuse for a
    sized worker (a slower run would not be its own timing); at today's count they are returned as given (an unsized
    check never refuses here, V2 17 Nov).
    """
    cores = parse_cpuset(cpuset)
    if type(logical_cpus) is int and max(cores) >= logical_cpus:
        # cores the host does not have are a mistake worth failing on, not something to silently trim
        raise WorkerFailure(WorkerCode.POLICY)
    if len(cores) == count:
        return cpuset
    if len(cores) < count:
        if count == CPU_COUNT:
            return cpuset
        raise WorkerFailure(WorkerCode.POLICY)
    return ",".join(str(core) for core in sorted(cores)[:count])


def resolve_cpuset(*, logical_cpus: object, root=None, count: int = CPU_COUNT) -> str:
    """The cpuset this host allocates to one worker of ``count`` CPUs.

    An installed record wins; otherwise the default is derived from the host.
    Either way the answer comes from the host rather than from this file.

    A worker given more than today's CPUs (a next version's larger resources)
    needs exactly that many cores: the kernel check holds the quota to the
    cpuset's size, so a record naming fewer refuses here, not at launch, and one
    naming more is narrowed to its lowest ``count`` cores (`_fitted`).

    Inside a lane-bound grading round (`carbon.reconstruction.grade_lanes`, two-lane mode only) the round's lane wins:
    exactly that lane's cores (this host's, or it refuses), narrowed to the worker's CPU count, the lowest (`_fitted`).
    A sized worker on a lane with fewer cores refuses; today's count never refuses here (V2, 17 Nov 2026: an unsized
    doctor refused every migrated task on a 4-core lane, switch 2). It never falls back to the record's or the derived
    cores, which may be the other lane's.

    A build bound to a remote GPU build slot (`carbon.reconstruction.remote_gpu_build`) runs on the lane machine: exactly
    its slot's cores there (``logical_cpus`` is that machine's, from its own daemon), whatever round it is part of.
    """
    from carbon.reconstruction import grade_lanes, remote_gpu_build

    remote = remote_gpu_build.cpuset()
    if remote is not None:
        # read as an installed record is: cores the machine lacks refuse; a worker of other than today's CPU count needs
        # exactly that many cores; today's count runs on the slot's cores whatever their number
        return _fitted(remote, logical_cpus=logical_cpus, count=count)
    # A build round that started LANELESS (V2, 17 Nov 2026): wherever a container's cores are chosen outside the
    # carrier's own op path, the round first holds a local lane (the builds' reserved lane first): never the record's or
    # the derived cores, which may be a grade lane's
    lane = grade_lanes.take_lane_if_laneless()
    if lane is not None:
        return _fitted(lane.cpuset, logical_cpus=logical_cpus, count=count)
    if root is not None:
        record = HostExecutionRecord.load(root)
        if record is not None:
            return _fitted(record.cpuset, logical_cpus=logical_cpus, count=count)
    return derive_cpuset(logical_cpus, count=count)
