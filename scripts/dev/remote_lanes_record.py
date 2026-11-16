"""Write (or check) the operator record of remote grade lanes, ``remote-grade-lanes.json``.

    python scripts/dev/remote_lanes_record.py \\
        --box fsn1=ssh://carbon-grade@ADDRESS --topology fsn1=fsn1.lscpu-p.txt \\
        --box hel1=ssh://carbon-grade@ADDRESS --topology hel1=hel1.lscpu-p.txt \\
        --lanes-per-box 4 --cores-per-lane 4 --cpuset-shape physical-only \\
        --stage-root /ABSOLUTE/STAGE/ROOT --worker-cpus 4 \\
        --out-host remote-grade-lanes.json --out-door remote-grade-lanes.door.json

    python scripts/dev/remote_lanes_record.py --check remote-grade-lanes.json [--topology NAME=FILE --box NAME=URL ...]

The record's schema and parse rules are `carbon.reconstruction.remote_lane` (`SCHEMA`, `load_record`); every file this
writes is read back through `load_record` before it is kept. Two forms are written:

- ``--out-host``: ``{"schema", "lanes"}``, for ``<HOST_ROOT>/remote-grade-lanes.json``. A door reads it only through
  its version's values row (``"remote_lanes": n``, the first n lanes) and ALWAYS beside its local lanes.
- ``--out-door``: the same lanes with ``"only": true``, for a door's OWN state root (a scratch door's re-grades, or a
  door that must grade on the remote lanes alone: `grade_lanes.door_remote_only`). It needs at least two lanes.

**Cores are read, never assumed.** Each box's lane cpusets come from ``lscpu -p=CPU,CORE,SOCKET`` captured ON THAT BOX
(the raw text, or the box's identity.json from the read-only identity kit, key ``lscpu_p``). Physical cores are the
distinct ``(SOCKET, CORE)`` pairs in ascending order; lane k takes cores ``k*c .. k*c+c-1``:

- ``physical-only``: the FIRST (lowest-numbered) logical CPU of each core; its SMT siblings are left unused by every lane;
- ``physical-with-siblings``: every logical CPU of each core (2c CPUs per lane on an SMT-2 box).

A lane's cpuset size must equal the worker's CPU count (`host_execution.resolve_cpuset` refuses any other size inside a
lane-bound round): give ``--worker-cpus`` and the script refuses a shape that would be refused there.

Lane ORDER interleaves the boxes (box1 lane0, box2 lane0, box1 lane1, ...), so a values row asking for fewer lanes than
the record lists still spreads over every box (``--order box`` lists box by box).

This script sets no value. The lane count, cores per lane and the shape are inputs; the shape of a Ryzen 9 5950X lane is
CV-Motor's open ruling (B2), so its output is PROPOSED until CV-Motor rules. No address is written into this file: boxes
are named on the command line.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.reconstruction import remote_lane
from carbon.reconstruction.host_execution import parse_cpuset

SHAPES = ("physical-only", "physical-with-siblings")
ORDERS = ("interleave", "box")
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


class RecordError(ValueError):
    """A refusal: the message says what is wrong."""


# -- topology -------------------------------------------------------------------------------------------------------------


def read_topology_text(path):
    """The ``lscpu -p=CPU,CORE,SOCKET`` text in ``path``: the raw capture, or an identity.json holding it (``lscpu_p``)."""
    data = Path(path).read_bytes()
    if b"\r" in data:
        raise RecordError(f"{path}: carriage return in a box capture")
    text = data.decode("utf-8")
    if text.lstrip().startswith("{"):
        document = json.loads(text)
        if type(document) is not dict or type(document.get("lscpu_p")) is not str:
            raise RecordError(f"{path}: identity json without lscpu_p")
        return document["lscpu_p"]
    return text


def parse_topology(text):
    """``[(socket, core, (cpu, ...)), ...]``: every physical core of the capture in ascending (socket, core) order, with its
    logical CPUs ascending. Refuses a capture that is empty, malformed or names a CPU twice.
    """
    cores = {}
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) != 3 or not all(field.isdigit() for field in fields):
            raise RecordError(f"topology line is not CPU,CORE,SOCKET: {line!r}")
        cpu, core, socket = (int(field) for field in fields)
        if cpu in seen:
            raise RecordError(f"topology names CPU {cpu} twice")
        seen.add(cpu)
        cores.setdefault((socket, core), []).append(cpu)
    if not cores:
        raise RecordError("topology names no CPU")
    return [
        (socket, core, tuple(sorted(cpus)))
        for (socket, core), cpus in sorted(cores.items())
    ]


def format_cpuset(cpus):
    """The canonical cpuset string of ``cpus`` (ascending, runs folded: ``0-3,16-19``)."""
    ordered = sorted(set(cpus))
    if not ordered:
        raise RecordError("empty cpuset")
    groups, start, last = [], ordered[0], ordered[0]
    for cpu in ordered[1:]:
        if cpu == last + 1:
            last = cpu
            continue
        groups.append(f"{start}-{last}" if last > start else str(start))
        start = last = cpu
    groups.append(f"{start}-{last}" if last > start else str(start))
    return ",".join(groups)


def lane_cpusets(topology, *, lanes, cores_per_lane, shape):
    """The ``lanes`` cpusets of one box (see the module docstring), or RecordError when the box has too few cores."""
    if shape not in SHAPES:
        raise RecordError(f"unknown cpuset shape {shape!r}")
    if (
        type(lanes) is not int
        or lanes < 1
        or type(cores_per_lane) is not int
        or cores_per_lane < 1
    ):
        raise RecordError("lanes and cores per lane must be positive integers")
    needed = lanes * cores_per_lane
    if needed > len(topology):
        raise RecordError(
            f"{lanes} lanes x {cores_per_lane} cores need {needed} physical cores; the box has {len(topology)}"
        )
    result = []
    for index in range(lanes):
        chosen = topology[index * cores_per_lane : (index + 1) * cores_per_lane]
        cpus = [
            cpu
            for _, _, threads in chosen
            for cpu in (threads[:1] if shape == "physical-only" else threads)
        ]
        result.append(format_cpuset(cpus))
    return result


# -- the record -----------------------------------------------------------------------------------------------------------


def _pairs(values, flag):
    found = {}
    for value in values or ():
        name, sep, rest = value.partition("=")
        if not sep or not _NAME.fullmatch(name) or not rest:
            raise RecordError(
                f"{flag} wants NAME=VALUE with a lower-case name: {value!r}"
            )
        if name in found:
            raise RecordError(f"{flag} names {name} twice")
        found[name] = rest
    return found


def build_lanes(
    boxes,
    topologies,
    *,
    lanes_per_box,
    cores_per_lane,
    shape,
    stage_root,
    order="interleave",
):
    """The record's lane list. ``boxes`` maps a box name to its ``ssh://`` daemon; ``topologies`` a name to its capture
    text; the boxes keep the order given."""
    if order not in ORDERS:
        raise RecordError(f"unknown order {order!r}")
    if not boxes:
        raise RecordError("no --box")
    if set(boxes) != set(topologies):
        raise RecordError(
            "every --box needs exactly one --topology and the reverse: "
            + ", ".join(sorted(set(boxes) ^ set(topologies)))
        )
    hosts = list(boxes.values())
    if len(set(hosts)) != len(hosts):
        raise RecordError("two boxes name one docker host")
    for host in hosts:
        try:
            remote_lane.parse_docker_host(host)
        except ValueError:
            raise RecordError(
                f"not an ssh://user@host[:port] docker host: {host!r}"
            ) from None
    per_box = {
        name: lane_cpusets(
            parse_topology(topologies[name]),
            lanes=lanes_per_box,
            cores_per_lane=cores_per_lane,
            shape=shape,
        )
        for name in boxes
    }
    names = list(boxes)
    if order == "box":
        slots = [(name, index) for name in names for index in range(lanes_per_box)]
    else:
        slots = [(name, index) for index in range(lanes_per_box) for name in names]
    return [
        {
            "cpuset": per_box[name][index],
            "docker_host": boxes[name],
            "stage_root": stage_root,
        }
        for name, index in slots
    ]


def render(lanes, *, only):
    """The canonical bytes of a record: sorted keys, two-space indent, LF, one trailing newline."""
    document = {"lanes": lanes, "schema": remote_lane.SCHEMA}
    if only:
        document["only"] = True
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("ascii")


def load_bytes(data):
    """``(specs, only)`` exactly as the door reads ``data`` (`remote_lane.load_record`), or RecordError."""
    if b"\r" in data:
        raise RecordError("carriage return in the record")
    directory = Path(tempfile.mkdtemp(prefix="remote-lanes-check-"))
    try:
        (directory / remote_lane.RECORD).write_bytes(data)
        return remote_lane.load_record(directory)
    except (ValueError, UnicodeDecodeError) as failure:
        raise RecordError(
            f"remote_lane.load_record refuses the record: {failure}"
        ) from None
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def check(data, *, topologies=None, boxes=None, worker_cpus=None):
    """Refuse a record the door would refuse, plus what it would only find later: two lanes of one box sharing a CPU,
    lanes of unequal size, a lane of other than ``worker_cpus`` CPUs, a lane that splits an SMT core with another lane or
    names a CPU the box lacks (given the box's ``topologies`` and ``boxes`` name -> docker host), a record not in
    canonical form. Returns ``(specs, only)``."""
    specs, only = load_bytes(data)
    if only and len(specs) < 2:
        raise RecordError(
            '"only": true needs at least two lanes (a door falls back to every lane otherwise)'
        )
    document = json.loads(data)
    if render(document["lanes"], only=only) != data:
        raise RecordError(
            "the record is not in canonical form (sorted keys, indent 2, LF, one trailing newline)"
        )
    sizes = {len(parse_cpuset(spec.cpuset)) for spec in specs}
    if len(sizes) != 1:
        raise RecordError(f"lanes of unequal size: {sorted(sizes)}")
    if worker_cpus is not None and sizes != {worker_cpus}:
        raise RecordError(
            f"a lane has {sizes.pop()} CPUs; a {worker_cpus}-CPU worker is refused on it (host_execution.resolve_cpuset)"
        )
    by_host = {}
    for spec in specs:
        by_host.setdefault(spec.docker_host, []).append(set(parse_cpuset(spec.cpuset)))
    for host, cpusets in by_host.items():
        for i, own in enumerate(cpusets):
            for other in cpusets[i + 1 :]:
                if own & other:
                    raise RecordError(
                        f"two lanes of {host} share CPUs {sorted(own & other)}"
                    )
    names = {host: name for name, host in (boxes or {}).items()}
    for host, cpusets in by_host.items():
        name = names.get(host)
        if name is None or name not in (topologies or {}):
            continue
        core_of = {
            cpu: (socket, core)
            for socket, core, cpus in parse_topology(topologies[name])
            for cpu in cpus
        }
        missing = sorted(set().union(*cpusets) - set(core_of))
        if missing:
            raise RecordError(f"{name}: lane CPUs {missing} are not on the box")
        cores = [{core_of[cpu] for cpu in own} for own in cpusets]
        for i, mine in enumerate(cores):
            if any(mine & other for other in cores[i + 1 :]):
                raise RecordError(
                    f"{name}: two lanes share a physical core (SMT siblings across lanes)"
                )
    return specs, only


def _stage_note(stage_root, door_state_root):
    if door_state_root is None:
        return (
            "NOTE: a container's /input is mirrored to the SAME absolute path on the box and only paths under "
            "stage_root are written there (remote_lane._remote_path): the door's input directories must lie under "
            f"{stage_root} on the door host too. Pass --door-state-root to check."
        )
    path = posixpath.normpath(door_state_root)
    if not (path == stage_root or path.startswith(stage_root.rstrip("/") + "/")):
        raise RecordError(
            f"the door's state root {path} is not under stage_root {stage_root}: every mirror would refuse "
            "(remote_lane._remote_path, RemoteLaneDown)"
        )
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--box",
        action="append",
        help="NAME=ssh://user@host[:port] (repeat per box, in order)",
    )
    parser.add_argument(
        "--topology",
        action="append",
        help="NAME=FILE: lscpu -p=CPU,CORE,SOCKET read on that box",
    )
    parser.add_argument("--lanes-per-box", type=int)
    parser.add_argument("--cores-per-lane", type=int)
    parser.add_argument("--cpuset-shape", choices=SHAPES)
    parser.add_argument("--order", choices=ORDERS, default="interleave")
    parser.add_argument("--stage-root")
    parser.add_argument(
        "--door-state-root",
        help="the door's state dir on the door host: must lie under --stage-root",
    )
    parser.add_argument(
        "--worker-cpus",
        type=int,
        help="the worker profile's CPU count: every lane must have exactly it",
    )
    parser.add_argument("--out-host", help="write the HOST_ROOT form (no 'only')")
    parser.add_argument("--out-door", help="write the door-own form ('only': true)")
    parser.add_argument(
        "--check",
        nargs="+",
        metavar="FILE",
        help="check existing record files instead of writing",
    )
    args = parser.parse_args(argv)
    try:
        boxes = _pairs(args.box, "--box")
        topologies = {
            name: read_topology_text(path)
            for name, path in _pairs(args.topology, "--topology").items()
        }
        if args.check:
            for path in args.check:
                specs, only = check(
                    Path(path).read_bytes(),
                    topologies=topologies,
                    boxes=boxes,
                    worker_cpus=args.worker_cpus,
                )
                print(
                    f"OK {path}: {len(specs)} lanes, only={str(only).lower()}, schema {remote_lane.SCHEMA}"
                )
            return 0
        missing = [
            flag
            for flag, value in (
                ("--lanes-per-box", args.lanes_per_box),
                ("--cores-per-lane", args.cores_per_lane),
                ("--cpuset-shape", args.cpuset_shape),
                ("--stage-root", args.stage_root),
            )
            if value is None
        ]
        if missing:
            raise RecordError(
                "missing "
                + ", ".join(missing)
                + " (this script sets no lane value of its own)"
            )
        if not (args.out_host or args.out_door):
            raise RecordError("nothing to write: give --out-host and/or --out-door")
        note = _stage_note(args.stage_root, args.door_state_root)
        lanes = build_lanes(
            boxes,
            topologies,
            lanes_per_box=args.lanes_per_box,
            cores_per_lane=args.cores_per_lane,
            shape=args.cpuset_shape,
            stage_root=args.stage_root,
            order=args.order,
        )
        written = []
        for path, only in ((args.out_host, False), (args.out_door, True)):
            if path is None:
                continue
            data = render(lanes, only=only)
            check(
                data, topologies=topologies, boxes=boxes, worker_cpus=args.worker_cpus
            )
            Path(path).write_bytes(data)
            written.append(path)
        for lane in lanes:
            name = next(
                name for name, host in boxes.items() if host == lane["docker_host"]
            )
            print(f"lane {name} cpuset {lane['cpuset']}")
        print(
            f"PROPOSED for CV-Motor: {len(boxes)} boxes x {args.lanes_per_box} lanes x {args.cores_per_lane} physical "
            f"cores, shape {args.cpuset_shape}, order {args.order}; wrote {', '.join(written)}"
        )
        if note:
            print(note, file=sys.stderr)
        return 0
    except (RecordError, OSError, json.JSONDecodeError) as failure:
        print(f"REFUSED: {failure}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
