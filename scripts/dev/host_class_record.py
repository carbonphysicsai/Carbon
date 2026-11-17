"""Fill a validator host-class record (schema ``carbon.validator.host-class.v2``) from boxes' identity reads.

    python scripts/dev/host_class_record.py \\
        --identity fsn1=fsn1.identity.json --identity hel1=hel1.identity.json \\
        --id VALIDATOR-HOST-CLASS-RYZEN5950X-01 --scope MAINNET \\
        --owner-decision "OWNER-5950X-GRADING-CLASS-01 (finney)" \\
        --read-by "Deploy-B, read-only identity kit as carbon-grade" --procedure "..." \\
        --out RYZEN5950X-01.json

    python scripts/dev/host_class_record.py --template --id ... --owner-decision ... --out TEMPLATE.json

Each identity.json is the output of the read-only box identity kit (schema `IDENTITY_SCHEMA`), read as the unprivileged
grade user on one box. The record is modelled on ``scripts/validator_host_classes/EPYC7402P-VM-01.json``; the fields
``install_validator.sh`` reads (model, ISA flags, nproc, memory floor, virtualization) are taken from the reads exactly as
that installer reads them on a host (lscpu ``Model name`` and ``Flags``, ``amx`` = any ``amx_*`` flag, ``nproc``,
``MemTotal`` floored to GiB, ``systemd-detect-virt``). With two or more boxes the record is ONE class: it refuses, and
prints every difference, when the boxes differ in any class field or in kernel, OS or Docker. CPU microcode and stepping
are RECORDED per box, never required equal (owner, 16 Nov: one 5950X class across FSN1 stepping 2 and HEL1 stepping 0, a
hardware difference). The memory floor is the lowest box's. Per-box facts (each identity.json's sha256, MemTotal,
microcode, stepping when the kit read it) are kept per box under ``recorded``.

``--template`` writes the same record with every field that must be read on the box left as an explicit
``HUMAN_INPUT`` placeholder: such a file is deliberately NOT a well-formed class (the installer ignores it).

This script measures nothing and sets no limit: every value comes from a box read or from the command line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "carbon.validator.host-class.v2"
IDENTITY_SCHEMA = "carbon.gradebox.identity.v1"
FLAGS = ("avx2", "fma", "avx512f", "avx512_bf16", "amx")
SCOPES = ("DEVELOPMENT", "MAINNET")
PLACEHOLDER = "HUMAN_INPUT: read on the box by the identity kit"
#: The identity fields one class must agree on across its boxes (besides the derived class fields).
SAME_ACROSS_BOXES = (
    "cpu_model_name",
    "isa_flags_present",
    "nproc",
    "virtualization",
    "kernel",
    "os",
    "docker",
)
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_IDENTITY_KEYS = {
    "schema",
    "box",
    "captured_utc",
    "cpu_model_name",
    "lscpu_flags",
    "cpuinfo_flags",
    "nproc",
    "kernel",
    "microcode",
    "os",
    "docker_server_version",
    "mem_total_kb",
    "virtualization",
    "lscpu_p",
}


class ClassError(ValueError):
    """A refusal: the message says what is wrong."""


def isa_flags(flags):
    """The class's ISA booleans of a flag list, as ``install_validator.sh`` derives them."""
    present = set(flags)
    seen = {name: name in present for name in FLAGS if name != "amx"}
    seen["amx"] = any(flag.startswith("amx_") for flag in present)
    return dict(sorted(seen.items()))


def read_identity(name, path):
    """``(facts, sha256 of the file)`` of one box's identity.json, or ClassError."""
    data = Path(path).read_bytes()
    if b"\r" in data:
        raise ClassError(f"{name}: carriage return in {path}")
    document = json.loads(data)
    if type(document) is not dict or document.get("schema") != IDENTITY_SCHEMA:
        raise ClassError(f"{name}: {path} is not a {IDENTITY_SCHEMA} document")
    missing = sorted(_IDENTITY_KEYS - set(document))
    if missing:
        raise ClassError(f"{name}: identity lacks {missing}")
    if document["box"] != name:
        raise ClassError(f"{name}: identity was captured as box {document['box']!r}")
    for key in (
        "cpu_model_name",
        "kernel",
        "os",
        "docker_server_version",
        "virtualization",
    ):
        if type(document[key]) is not str or not document[key]:
            raise ClassError(f"{name}: identity {key} is empty")
    for key in ("nproc", "mem_total_kb"):
        if type(document[key]) is not int or document[key] < 1:
            raise ClassError(f"{name}: identity {key} is not a positive integer")
    microcode = document["microcode"]
    if (
        type(microcode) is not list
        or not microcode
        or any(type(item) is not str or not item for item in microcode)
    ):
        raise ClassError(f"{name}: identity microcode is not a list of values")
    if len(set(microcode)) != 1:
        raise ClassError(
            f"{name}: CPUs report different microcode {sorted(set(microcode))}"
        )
    for key in ("lscpu_flags", "cpuinfo_flags"):
        if type(document[key]) is not list or any(
            type(item) is not str for item in document[key]
        ):
            raise ClassError(f"{name}: identity {key} is not a list of flags")
    lscpu_isa, cpuinfo_isa = isa_flags(document["lscpu_flags"]), isa_flags(
        document["cpuinfo_flags"]
    )
    if lscpu_isa != cpuinfo_isa:
        raise ClassError(
            f"{name}: lscpu and /proc/cpuinfo disagree on ISA flags: {lscpu_isa} vs {cpuinfo_isa}"
        )
    facts = {
        "cpu_model_name": document["cpu_model_name"],
        "isa_flags_present": lscpu_isa,
        "nproc": document["nproc"],
        "virtualization": document["virtualization"],
        "microcode": microcode[0],
        "stepping": _stepping(name, document),
        "kernel": document["kernel"],
        "os": document["os"],
        "docker": document["docker_server_version"],
        "mem_total_kb": document["mem_total_kb"],
    }
    return facts, hashlib.sha256(data).hexdigest()


def _stepping(name, document):
    """The box's CPU stepping (one value across its CPUs), or None when the identity predates kit rev 2."""
    if "stepping" not in document:
        return None
    stepping = document["stepping"]
    if (
        type(stepping) is not list
        or not stepping
        or any(type(item) is not str or not item.isdigit() for item in stepping)
    ):
        raise ClassError(f"{name}: identity stepping is not a list of decimal values")
    if len(set(stepping)) != 1:
        raise ClassError(
            f"{name}: CPUs report different steppings {sorted(set(stepping))}"
        )
    return stepping[0]


def differences(boxes):
    """``{field: {box: value}}`` for every field in `SAME_ACROSS_BOXES` that is not one value across ``boxes``."""
    found = {}
    for key in SAME_ACROSS_BOXES:
        values = {name: facts[key] for name, (facts, _) in boxes.items()}
        if len({json.dumps(value, sort_keys=True) for value in values.values()}) > 1:
            found[key] = values
    return found


def build(boxes, *, class_id, scope, owner_decision, read_by, procedure, stage_2):
    """The class record of ``boxes`` (name -> (facts, sha256), in order), or ClassError naming every difference."""
    if not boxes:
        raise ClassError("no --identity")
    diff = differences(boxes)
    if diff:
        raise ClassError(
            "the boxes are not one class:\n"
            + json.dumps(diff, indent=2, sort_keys=True)
        )
    first = next(iter(boxes.values()))[0]
    record = {
        "cpu_model_name": first["cpu_model_name"],
        "id": class_id,
        "isa_flags_present": first["isa_flags_present"],
        "mem_total_min_gib": min(facts["mem_total_kb"] for facts, _ in boxes.values())
        // 1048576,
        "nproc": first["nproc"],
        "recorded": {
            "boxes": list(boxes),
            "docker": first["docker"],
            "identity_json_sha256": {name: sha for name, (_, sha) in boxes.items()},
            "kernel": first["kernel"],
            "mem_total_kb": {
                name: facts["mem_total_kb"] for name, (facts, _) in boxes.items()
            },
            "microcode": {
                name: facts["microcode"] for name, (facts, _) in boxes.items()
            },
            "os": first["os"],
            "owner_decision": owner_decision,
            "procedure": procedure,
            "read_by": read_by,
            "stage_2": stage_2,
        },
        "schema": SCHEMA,
        "scope": scope,
        "stage": 1,
        "virtualization": first["virtualization"],
    }
    steppings = {
        name: facts["stepping"]
        for name, (facts, _) in boxes.items()
        if facts.get("stepping") is not None
    }
    if steppings:
        record["recorded"]["stepping"] = steppings
    if not wellformed(record):
        raise ClassError("the filled record is not a well-formed host class")
    return record


def template(
    *, class_id, scope, owner_decision, read_by, procedure, stage_2, box_names
):
    """The record with every box-read field an explicit `PLACEHOLDER` (deliberately not a well-formed class)."""
    return {
        "cpu_model_name": PLACEHOLDER,
        "id": class_id,
        "isa_flags_present": {name: PLACEHOLDER for name in sorted(FLAGS)},
        "mem_total_min_gib": PLACEHOLDER,
        "nproc": PLACEHOLDER,
        "recorded": {
            "boxes": list(box_names),
            "docker": PLACEHOLDER,
            "identity_json_sha256": {name: PLACEHOLDER for name in box_names},
            "kernel": PLACEHOLDER,
            "mem_total_kb": {name: PLACEHOLDER for name in box_names},
            "microcode": PLACEHOLDER,
            "os": PLACEHOLDER,
            "owner_decision": owner_decision,
            "procedure": procedure,
            "read_by": read_by,
            "stage_2": stage_2,
        },
        "schema": SCHEMA,
        "scope": scope,
        "stage": 1,
        "virtualization": PLACEHOLDER,
    }


def wellformed(record):
    """``install_validator.sh``'s own test of a v2 class record (kept in step with its ``wellformed``)."""
    try:
        flags = record["isa_flags_present"]
        return not (
            record["schema"] != SCHEMA
            or record["scope"] not in SCOPES
            or type(record["cpu_model_name"]) is not str
            or not record["cpu_model_name"]
            or set(flags) != set(FLAGS)
            or any(type(flags[name]) is not bool for name in FLAGS)
            or type(record["nproc"]) is not int
            or record["nproc"] < 1
            or type(record["mem_total_min_gib"]) is not int
            or record["mem_total_min_gib"] < 1
            or type(record["id"]) is not str
            or not record["id"]
            or type(record["virtualization"]) is not str
            or not record["virtualization"]
        )
    except (KeyError, TypeError):
        return False


def render(record):
    """Sorted keys, two-space indent, LF, one trailing newline (the layout of the registered class files)."""
    return (
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--identity",
        action="append",
        help="NAME=identity.json (repeat per box, in order)",
    )
    parser.add_argument(
        "--expect-sha256",
        action="append",
        default=[],
        help="NAME=HEX printed by the kit on the box",
    )
    parser.add_argument("--id", required=True)
    parser.add_argument("--scope", choices=SCOPES, required=True)
    parser.add_argument("--owner-decision", required=True)
    parser.add_argument(
        "--read-by",
        default=PLACEHOLDER.replace(
            "read on the box by the identity kit", "who ran the kit"
        ),
    )
    parser.add_argument("--procedure", default="HUMAN_INPUT: the kit and its receipt")
    parser.add_argument(
        "--stage-2",
        default=(
            "UNREGISTERED: lane cpusets (CV-Motor B2), the boxes' host execution records, worker image ids and the "
            "remote-lane record come after the reads"
        ),
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="write the placeholder record (box names from --box)",
    )
    parser.add_argument(
        "--box",
        action="append",
        default=[],
        help="with --template: a box name (repeat)",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    common = {
        "class_id": args.id,
        "scope": args.scope,
        "owner_decision": args.owner_decision,
        "read_by": args.read_by,
        "procedure": args.procedure,
        "stage_2": args.stage_2,
    }
    try:
        if args.template:
            for name in args.box:
                if not _NAME.fullmatch(name):
                    raise ClassError(f"bad box name {name!r}")
            record = template(box_names=args.box, **common)
        else:
            boxes = {}
            for value in args.identity or ():
                name, sep, path = value.partition("=")
                if not sep or not _NAME.fullmatch(name) or name in boxes:
                    raise ClassError(f"--identity wants a unique NAME=FILE: {value!r}")
                boxes[name] = read_identity(name, path)
            for value in args.expect_sha256:
                name, _, digest = value.partition("=")
                if name not in boxes or boxes[name][1] != digest.lower():
                    raise ClassError(
                        f"{name}: identity.json sha256 is not the one the kit printed ({digest})"
                    )
            record = build(boxes, **common)
        Path(args.out).write_bytes(render(record))
        print(
            f"wrote {args.out} ({'TEMPLATE, not a class' if args.template else 'well-formed v2 class'})"
        )
        return 0
    except (ClassError, OSError, json.JSONDecodeError) as failure:
        print(f"REFUSED: {failure}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
