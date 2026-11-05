#!/usr/bin/env python3
"""The deploy tool's checks, identity and log (MAINNET_UPDATE_ARCHITECTURE s5 + s7, head H5 v1).

    python3 -I -B scripts/dev/release/carbon_release.py manifest --repo R --rev REV [--out FILE]
    python3 -I -B scripts/dev/release/carbon_release.py declare  --repo R --old OLD --new NEW --reason TEXT --evidence FILE
    python3 -I -B scripts/dev/release/carbon_release.py precheck --mode prepare|switch --repo R \\
        --old-rev OLD --new-rev NEW --old-pack D --new-pack D --old-root DIR --new-root DIR \\
        --final-heads TSV [--declared FILE] [--older-root DIR ...]
    python3 -I -B scripts/dev/release/carbon_release.py log append --log FILE --event JSON
    python3 -I -B scripts/dev/release/carbon_release.py log verify --log FILE

Every command prints ONE JSON line and reads no stdin (R22: nothing in the deploy path can wait on a prompt).

``manifest`` writes a release's identity, ``release.json``: full revision + tree, the grading-path digest and the
build-inputs digest (`exam_identity`), and ``first_start_files``, the exact set of files the release's first start
writes into a door's state (read from that revision's ``state_binding``; R16: a hook accepts exactly this set).

``declare`` prints a ``declared_exam_change`` record (the receiver's five fields) whose ``paths`` are computed exactly
as the receiver computes them at start (``BUILD_INPUTS_CHANGED`` first when the build inputs moved, then the changed
files the NEW revision's M2 rule names, sorted), so the record the receiver checks is never typed by hand (R17).

``precheck`` refuses a step BEFORE any write. Items (each PASS, or REFUSE / UNKNOWN with a code):

- ``final_heads``: NEW is FINAL or LANDED in the Validator's FINAL_HEADS.tsv (comment lines skipped, the status column
  exact, every row for that sha agreeing); HOLD, CONTENT, OPEN, any other status or a conflict refuses.
- ``exam`` (R17, R18): `exam_identity.check`; SAME_EXAM passes; a grading-code change passes only with ``--declared``
  whose record is valid, names OLD and NEW as full ids and whose paths EQUAL the receiver's own list for OLD..NEW; a
  pack change (a re-seal) passes only with ``--declared-pack-change REASON`` (the receiver then regrades its king).
- ``disk`` (R25, Validator 08:13): free space on NEW's filesystem >= 2 x OLD root (prepare) or 1.5 x (switch) + 20 GiB.
- switch only: ``caches`` (R15): every library-cache entry and prepared-overlay leaf of OLD (and each ``--older-root``)
  is on NEW with the same file count and bytes; ``drain``: OLD's state has no ``draining`` flag (carried, NEW would start
  drained); ``release``: NEW root's ``release.json`` names NEW.

Exit 0 when every item passes, 3 on any REFUSE, 4 on UNKNOWN only (2 = usage). ``log`` keeps a hash-chained deploy log:
each line carries the previous line's sha, so an edited or dropped line fails ``verify``.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_identity as ei

SCHEMA = "carbon.release.v1"
PASS, REFUSE, UNKNOWN = "PASS", "REFUSE", "UNKNOWN"
GIB = 1 << 30
DISK_HEADROOM = 20 * GIB
DISK_FACTOR = {"prepare": 2.0, "switch": 1.5}
LANDABLE = {"FINAL", "LANDED"}
BINDING_FILE = "carbon/challenge_validator/state_binding.py"
LIBRARY = "environment/campaigns/.direct-development/library-cache"
OVERLAYS = LIBRARY + "/overlays"
STATE = "receiver/state"
DRAIN_NAME = "draining"
BUILD_INPUTS_CHANGED = "build_inputs"
_HEX40 = re.compile(r"[0-9a-f]{40}")
_EVIDENCE = re.compile(r"sha256:[0-9a-f]{64}")


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


# --- identity ------------------------------------------------------------------------------------------------------


def first_start_files(repo, commit) -> list:
    """The files a first start at ``commit`` writes into a door's state: the legacy binding, and from H1 on the door
    binding plus exactly one ``bindings/<64 hex>.json`` (names read from that revision's ``state_binding``).
    """
    try:
        source = ei._git(repo, "show", f"{commit}:{BINDING_FILE}")
    except ei.Unknown:
        return ["receiver-binding.json"]  # before H1: the one legacy file
    names = {}
    for node in ast.parse(source.decode("utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = getattr(node.targets[0], "id", None)
            if target in ("LEGACY_NAME", "DOOR_NAME", "RELEASES_DIR"):
                names[target] = ast.literal_eval(node.value)
    if set(names) != {"LEGACY_NAME", "DOOR_NAME", "RELEASES_DIR"}:
        raise ei.Unknown("state_binding_names_unreadable")
    return [
        names["LEGACY_NAME"],
        names["DOOR_NAME"],
        names["RELEASES_DIR"] + "/<64hex>.json",
    ]


def manifest(repo, rev) -> dict:
    commit = ei.resolve(repo, rev)
    tree = ei._git(repo, "rev-parse", "--verify", f"{commit}^{{tree}}").decode().strip()
    build = hashlib.sha256(ei.build_listing(repo, commit)).hexdigest()
    return {
        "schema": SCHEMA,
        "revision": commit,
        "tree": tree,
        "grading_digest": ei.grading_digest(repo, commit),
        "build_inputs_digest": "sha256:" + build,
        "first_start_files": first_start_files(repo, commit),
    }


def receiver_paths(repo, old, new) -> list:
    """OLD..NEW's changed grading paths exactly as the receiver lists them (`direct_receiver._grading_change` at NEW)."""
    rule = ei.rule(repo, new)
    if rule is None:
        raise ei.Unknown("grading_rule_absent_at_new")
    named = ei._predicate(rule)
    names = ei._git(repo, "diff", "--name-only", "-z", "--no-renames", old, new, "--")
    moved = ei.build_listing(repo, old) != ei.build_listing(repo, new)
    paths = sorted(p for p in names.decode("utf-8").split("\0") if p and named(p))
    return ([BUILD_INPUTS_CHANGED] if moved else []) + paths


def declare(repo, old, new, reason, evidence) -> dict:
    if not reason or not reason.strip():
        raise ValueError("a declared exam change needs a reason")
    old, new = ei.resolve(repo, old), ei.resolve(repo, new)
    paths = receiver_paths(repo, old, new)
    if not paths:
        raise ValueError("nothing to declare: OLD..NEW changes no grading path")
    return {
        "from_revision": old,
        "to_revision": new,
        "paths": paths,
        "reason": reason.strip(),
        "evidence_sha256": _sha_file(evidence),
    }


# --- precheck items ------------------------------------------------------------------------------------------------


def final_heads_status(tsv, sha) -> dict:
    """The FINAL_HEADS rows for full ``sha``: PASS when every row is FINAL or LANDED (and at least one exists)."""
    statuses = []
    header = None
    for line in Path(tsv).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            header = cells
            if "sha" not in header or "status" not in header:
                return {"state": UNKNOWN, "code": "final_heads_header"}
            continue
        row = dict(zip(header, cells))
        if row.get("sha") == sha:
            statuses.append(row.get("status", ""))
    if not statuses:
        return {"state": REFUSE, "code": "not_in_final_heads"}
    if any(s not in LANDABLE for s in statuses):
        return {"state": REFUSE, "code": "not_final", "statuses": statuses}
    return {"state": PASS, "statuses": statuses}


def _valid_record(record) -> bool:
    fields = {"from_revision", "to_revision", "paths", "reason", "evidence_sha256"}
    return (
        type(record) is dict
        and set(record) == fields
        and all(
            type(record[k]) is str and _HEX40.fullmatch(record[k])
            for k in ("from_revision", "to_revision")
        )
        and type(record["paths"]) is list
        and bool(record["paths"])
        and all(type(p) is str and p for p in record["paths"])
        and record["paths"] == sorted(set(record["paths"]), key=record["paths"].index)
        and type(record["reason"]) is str
        and bool(record["reason"].strip())
        and type(record["evidence_sha256"]) is str
        and _EVIDENCE.fullmatch(record["evidence_sha256"]) is not None
    )


def exam_item(repo, old, new, old_pack, new_pack, declared, pack_change=None) -> dict:
    result = ei.check(repo, old, new, old_pack=old_pack, new_pack=new_pack)
    item = {"identity": result}
    if result["state"] == ei.SAME:
        return {**item, "state": PASS}
    if result["state"] == ei.UNKNOWN:
        return {**item, "state": UNKNOWN, "code": result.get("reason")}
    if result["pack_changed"] and not pack_change:
        # a re-seal (new pack on the same door) is said, never silent: the receiver then regrades its king
        return {**item, "state": REFUSE, "code": "pack_change_undeclared"}
    if result["pack_changed"]:
        item["pack_change"] = pack_change
    if not (
        result["grading_paths_changed"]
        or result["build_inputs_moved"]
        or result["grading_rule_changed"]
    ):
        return {**item, "state": PASS}
    if declared is None:
        return {**item, "state": REFUSE, "code": "exam_change_undeclared"}
    if not _valid_record(declared):
        return {**item, "state": REFUSE, "code": "declared_record_invalid"}
    want = receiver_paths(repo, result["old"], result["new"])
    if (declared["from_revision"], declared["to_revision"]) != (
        result["old"],
        result["new"],
    ):
        return {**item, "state": REFUSE, "code": "declared_revisions_differ"}
    if declared["paths"] != want:
        return {
            **item,
            "state": REFUSE,
            "code": "declared_paths_differ",
            "computed_paths": want,
        }
    return {**item, "state": PASS, "declared": True}


def tree_size(root) -> int:
    total = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in files:
            try:
                st = os.lstat(os.path.join(base, name))
            except FileNotFoundError:
                continue  # a live root changes while it is measured
            total += st.st_size
    return total


def disk_item(mode, old_root, new_root, *, free=None, size=None) -> dict:
    size = tree_size(old_root) if size is None else size
    target = Path(new_root)
    while not target.exists():
        target = target.parent
    free = shutil.disk_usage(target).free if free is None else free
    floor = int(DISK_FACTOR[mode] * size) + DISK_HEADROOM
    out = {"free": free, "old_root_bytes": size, "floor": floor, "mode": mode}
    if free < floor:
        return {**out, "state": REFUSE, "code": "disk_below_floor"}
    return {**out, "state": PASS}


def cache_entries(root) -> dict:
    """``{name: (files, bytes)}`` for every library-cache entry (64-hex bundle dirs and materials/*) and every
    prepared-overlay leaf (4 digest levels) under ``root``."""
    out = {}
    base = Path(root) / LIBRARY
    if base.is_dir():
        for p in base.iterdir():
            if (
                p.is_dir()
                and not p.is_symlink()
                and re.fullmatch(r"[0-9a-f]{64}", p.name)
            ):
                out["library/" + p.name] = p
        materials = base / "materials"
        if materials.is_dir() and not materials.is_symlink():
            for p in materials.iterdir():
                if not p.is_symlink():
                    out["materials/" + p.name] = p
    overlays = Path(root) / OVERLAYS
    if overlays.is_dir():
        for leaf in overlays.glob("*/*/*/*"):
            if leaf.is_dir() and not leaf.name.startswith("."):
                out["overlay/" + leaf.relative_to(overlays).as_posix()] = leaf
    return {name: _counts(path) for name, path in out.items()}


def _counts(path) -> tuple:
    if path.is_file():
        return 1, path.stat().st_size
    files = size = 0
    for base, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in names:
            files += 1
            size += os.lstat(os.path.join(base, name)).st_size
    return files, size


def caches_item(old_roots, new_root) -> dict:
    new = cache_entries(new_root)
    missing, differ, checked = [], [], 0
    for root in old_roots:
        for name, counts in cache_entries(root).items():
            checked += 1
            if name not in new:
                missing.append(name)
            elif new[name] != counts:
                differ.append(name)
    missing, differ = sorted(set(missing)), sorted(set(differ) - set(missing))
    out = {
        "checked": checked,
        "new_entries": len(new),
        "missing": len(missing),
        "differ": len(differ),
    }
    if missing or differ:
        return {
            **out,
            "state": REFUSE,
            "code": "caches_not_carried",
            "first": (missing + differ)[:10],
        }
    return {**out, "state": PASS}


def drain_item(old_root) -> dict:
    flag = Path(old_root) / STATE / DRAIN_NAME
    if flag.exists() or flag.is_symlink():
        return {"state": REFUSE, "code": "old_door_draining"}
    return {"state": PASS}


def release_item(new_root, new) -> dict:
    path = Path(new_root) / "release.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"state": REFUSE, "code": "release_json_missing"}
    except (OSError, ValueError):
        return {"state": REFUSE, "code": "release_json_unreadable"}
    if type(record) is not dict or record.get("schema") != SCHEMA:
        return {"state": REFUSE, "code": "release_json_schema"}
    if record.get("revision") != new:
        return {"state": REFUSE, "code": "release_json_names_another_revision"}
    return {"state": PASS, "sha256": _sha_file(path)}


def precheck(args) -> dict:
    out = {"schema": SCHEMA + ".precheck", "mode": args.mode, "items": {}}
    items = out["items"]
    try:
        new = ei.resolve(args.repo, args.new_rev)
        old = ei.resolve(args.repo, args.old_rev)
    except ei.Unknown as failed:
        return {**out, "state": UNKNOWN, "code": str(failed)}
    out.update(old=old, new=new)
    declared = None
    if args.declared is not None:
        try:
            declared = json.loads(Path(args.declared).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            declared = {}
    checks = [
        ("final_heads", lambda: final_heads_status(args.final_heads, new)),
        (
            "exam",
            lambda: exam_item(
                args.repo,
                old,
                new,
                args.old_pack,
                args.new_pack,
                declared,
                args.declared_pack_change,
            ),
        ),
        ("disk", lambda: disk_item(args.mode, args.old_root, args.new_root)),
    ]
    if args.mode == "switch":
        checks += [
            (
                "caches",
                lambda: caches_item([args.old_root, *args.older_root], args.new_root),
            ),
            ("drain", lambda: drain_item(args.old_root)),
            ("release", lambda: release_item(args.new_root, new)),
        ]
    for name, run in checks:
        try:
            items[name] = run()
        except Exception as failed:  # noqa: BLE001
            # any failure inside a check is a refusal to proceed, never a pass
            items[name] = {"state": UNKNOWN, "code": type(failed).__name__}
    states = {item["state"] for item in items.values()}
    out["state"] = (
        REFUSE if REFUSE in states else UNKNOWN if UNKNOWN in states else PASS
    )
    return out


# --- deploy log ----------------------------------------------------------------------------------------------------


def log_append(path, event) -> dict:
    """Append ``event`` with the previous line's sha (a chain). Refuses to extend a log that does not verify."""
    if type(event) is not dict or not event:
        raise ValueError("an event is a non-empty JSON object")
    checked = (
        log_verify(path)
        if Path(path).exists()
        else {"state": PASS, "lines": 0, "last": None}
    )
    if checked["state"] != PASS:
        raise ValueError("log_does_not_verify")
    line = {
        "seq": checked["lines"] + 1,
        "at_ns": time.time_ns(),
        "prev": checked["last"],
        "event": event,
    }
    line["sha"] = "sha256:" + hashlib.sha256(_canonical(line)).hexdigest()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, _canonical(line) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"state": PASS, "seq": line["seq"], "sha": line["sha"]}


def log_verify(path) -> dict:
    prev, n = None, 0
    for raw in Path(path).read_bytes().splitlines():
        n += 1
        try:
            line = json.loads(raw)
            sha = line.pop("sha")
        except (ValueError, KeyError, AttributeError):
            return {"state": REFUSE, "code": "line_unreadable", "line": n}
        if line.get("seq") != n or line.get("prev") != prev:
            return {"state": REFUSE, "code": "chain_broken", "line": n}
        if "sha256:" + hashlib.sha256(_canonical(line)).hexdigest() != sha:
            return {"state": REFUSE, "code": "line_edited", "line": n}
        prev = sha
    return {"state": PASS, "lines": n, "last": prev}


# --- CLI -----------------------------------------------------------------------------------------------------------

EXIT = {PASS: 0, REFUSE: 3, UNKNOWN: 4}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="carbon_release.py")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("manifest")
    m.add_argument("--repo", type=Path, required=True)
    m.add_argument("--rev", required=True)
    m.add_argument("--out", type=Path)
    d = sub.add_parser("declare")
    d.add_argument("--repo", type=Path, required=True)
    d.add_argument("--old", required=True)
    d.add_argument("--new", required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--evidence", type=Path, required=True)
    p = sub.add_parser("precheck")
    p.add_argument("--mode", choices=sorted(DISK_FACTOR), required=True)
    p.add_argument("--repo", type=Path, required=True)
    for name in ("--old-rev", "--new-rev", "--old-pack", "--new-pack"):
        p.add_argument(name, required=True)
    p.add_argument("--old-root", type=Path, required=True)
    p.add_argument("--new-root", type=Path, required=True)
    p.add_argument("--final-heads", type=Path, required=True)
    p.add_argument("--declared", type=Path)
    p.add_argument("--declared-pack-change")
    p.add_argument("--older-root", type=Path, action="append", default=[])
    lg = sub.add_parser("log")
    lsub = lg.add_subparsers(dest="log_command", required=True)
    la = lsub.add_parser("append")
    la.add_argument("--log", type=Path, required=True)
    la.add_argument("--event", required=True)
    lv = lsub.add_parser("verify")
    lv.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "manifest":
            result = {"state": PASS, "release": manifest(args.repo, args.rev)}
            if args.out is not None:
                fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(_canonical(result["release"]) + b"\n")
                result["written"] = str(args.out)
        elif args.command == "declare":
            result = {
                "state": PASS,
                "declared_exam_change": declare(
                    args.repo, args.old, args.new, args.reason, args.evidence
                ),
            }
        elif args.command == "precheck":
            for name in ("old_pack", "new_pack"):
                ei.pack(getattr(args, name))
            result = precheck(args)
        elif args.log_command == "append":
            result = log_append(args.log, json.loads(args.event))
        else:
            result = log_verify(args.log)
    except (ValueError, ei.Unknown, OSError) as failed:
        result = {
            "state": REFUSE if isinstance(failed, ValueError) else UNKNOWN,
            "code": str(failed) or type(failed).__name__,
        }
    print(json.dumps(result, sort_keys=True))
    return EXIT[result["state"]]


if __name__ == "__main__":
    sys.exit(main())
