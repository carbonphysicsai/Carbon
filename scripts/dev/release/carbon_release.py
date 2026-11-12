#!/usr/bin/env python3
"""The deploy tool's checks, identity and log (MAINNET_UPDATE_ARCHITECTURE s5 + s7, head H5 v1).

    python3 -I -B scripts/dev/release/carbon_release.py manifest --repo R --rev REV [--out FILE]
    python3 -I -B scripts/dev/release/carbon_release.py declare  --repo R --old OLD --new NEW --reason TEXT --evidence FILE
    python3 -I -B scripts/dev/release/carbon_release.py precheck --mode prepare|switch --repo R \\
        --old-rev OLD --new-rev NEW --old-pack D --new-pack D --old-root DIR --new-root DIR \\
        --final-heads TSV [--declared FILE] [--older-root DIR ...]
    python3 -I -B scripts/dev/release/carbon_release.py precheck --mode open --repo R --new-rev NEW --new-root DIR \\
        --final-heads TSV --new-network finney --expect-network testnet --expect-network finney \\
        [--weights-loop-pending finney] [--host-root DIR ...]
    python3 -I -B scripts/dev/release/carbon_release.py pushline --repo R --sha FULL_SHA --final-heads TSV [--main REF]
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
  pack change (a re-seal) passes only with ``--declared-pack-change REASON`` (the receiver then regrades its king);
  an edit to the M2 rule itself only with ``--declared-rule-change REASON``.
- ``served_source`` (R66, design note s1.5): lists every `lean_recipe._SOURCE_PATHS` / staged-module file OLD..NEW
  changes, with what it costs on the doors; it informs, it never refuses by itself.
- ``disk`` (R25, Validator 08:13): free space on NEW's filesystem >= 2 x OLD root (prepare) or 1.5 x (switch) + 20 GiB.
- ``accepted``: OLD and NEW are the revisions the two roots' receiver configs ACCEPT (the ones the receiver compares and
  a declared record must name); ``ancestry``: OLD is an ancestor of NEW in ``--repo`` (the NEW release's checkout), as
  the receiver requires to migrate.
- switch only: ``caches`` (R15): every library-cache entry and prepared-overlay leaf of OLD (and each ``--older-root``)
  is on NEW with the same file count and bytes, no link anywhere on NEW's cache paths and the cache directories private
  (the receiver's own rule); an old root without a library cache or a receiver config is UNKNOWN, never empty;
  ``drain``: no ``draining`` flag in OLD's state directory (read from its config: H1's fixed state dir included);
  ``owners`` (R36): every retained owner in OLD has the shape the receiver restores (named, before any stop);
  ``receivers`` (R41): every running direct receiver is a declared ``--host-root``; ``chain_binding`` (H8 part
  3): every running receiver and weights-loop process is bound to ``--expect-network`` (testnet when unset) with no
  localnet variable, and no host root carries the staging marker; ``lock_versions`` (R79): when NEW
  has the round-robin host lock, every other door has it too or is DRAINING (``--allow-mixed-lock REASON``);
  ``release``: NEW root's ``release.json`` names NEW; ``chain`` (H8): OLD's own chain-state is not DEGRADED (never
  flip into a chain outage) unless ``--allow-chain-degraded REASON``.
- open (a FRESH door with no OLD: the mainnet day-of roots): ``final_heads``; ``accepted`` and ``release`` for NEW
  only; ``open_door``: NEW's receiver.json names ``--new-network`` explicitly (no record = a testnet root), that network
  is expected, and every pack store it reads is bound to that network (a non-testnet door must serve a sealed
  delivery); ``disk`` (1 x NEW's own root + 20 GiB); ``receivers``, ``chain_binding`` and ``lock_versions`` over every
  OTHER ``--host-root`` (each running, bound to its own network). ``--weights-loop-pending NET`` names an expected
  network whose weights loop starts only after its doors open; nothing else is relaxed.

The result also carries ``release_class`` (s7.5), derived from the ``exam`` and ``served_source`` items, never typed:
2 = the exam moves, 1 = served-source files change, 0 = neither, None = unknown (an item did not pass).

``pushline`` (R28) prints the owner's exact push line only for a full sha that is a fast-forward of main and FINAL or
LANDED in FINAL_HEADS; anything else refuses before an owner ask.

Exit 0 when every item passes, 3 on any REFUSE, 4 on UNKNOWN only (2 = usage). ``log`` keeps a hash-chained deploy log:
each line carries the previous line's sha, so an edited, reordered or removed line fails ``verify``; a cut tail is
caught with ``--expect-last`` (the last sha the deploy receipt recorded). Appends are serialised by a lock.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_identity as ei

SCHEMA = "carbon.release.v1"
PASS, REFUSE, UNKNOWN = "PASS", "REFUSE", "UNKNOWN"
GIB = 1 << 30
DISK_HEADROOM = 20 * GIB
#: free space needed on NEW's filesystem, as a multiple of the measured root (OLD; open mode: the fresh root itself,
#: room for it to grow by its own size) + DISK_HEADROOM
DISK_FACTOR = {"prepare": 2.0, "switch": 1.5, "open": 1.0}
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
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, ValueError) as failed:
        raise ei.Unknown("state_binding_unreadable") from failed
    for node in tree.body:
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
    """The FINAL_HEADS rows naming ``sha`` (full, or a prefix of >= 7 hex, cells stripped and lower-cased): PASS only
    when at least one exists and EVERY one is FINAL or LANDED. A matching row whose cell count differs from the header
    (a tab inside a cell shifts the status column) is UNKNOWN."""
    statuses = []
    header = None
    sha = sha.strip().lower()
    for line in Path(tsv).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = [c.strip() for c in line.split("\t")]
        if header is None:
            header = cells
            if "sha" not in header or "status" not in header:
                return {"state": UNKNOWN, "code": "final_heads_header"}
            continue
        at = header.index("sha")
        row_sha = cells[at].lower() if len(cells) > at else ""
        if not (row_sha == sha or (len(row_sha) >= 7 and sha.startswith(row_sha))):
            continue
        if len(cells) != len(header):
            return {
                "state": UNKNOWN,
                "code": "final_heads_row_shape",
                "row_sha": row_sha,
            }
        statuses.append(cells[header.index("status")].upper())
    if header is None:
        return {"state": UNKNOWN, "code": "final_heads_header"}
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


def exam_item(
    repo, old, new, old_pack, new_pack, declared, pack_change=None, rule_change=None
) -> dict:
    """``old``/``new`` are the doors' ACCEPTED revisions (the ones the receiver compares)."""
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
    if result["grading_rule_changed"] and not rule_change:
        # an edit to the M2 rule itself: the receiver's own path list cannot show it, so it is said separately
        return {**item, "state": REFUSE, "code": "grading_rule_change_undeclared"}
    if result["grading_rule_changed"] and not result.get("grading_rule_additions_only"):
        # declared or not: a rule edit that removes a path or changes the pattern / exclusions can weaken M2
        # (Validator-2 13:21); it needs its own reviewed head, never a declaration at switch time
        return {
            **item,
            "state": REFUSE,
            "code": "grading_rule_change_not_additions_only",
        }
    if result["grading_rule_changed"]:
        item["rule_change"] = rule_change
    want = receiver_paths(repo, result["old"], result["new"])
    if not want:
        return {**item, "state": PASS}
    if declared is None:
        return {**item, "state": REFUSE, "code": "exam_change_undeclared"}
    if not _valid_record(declared):
        return {**item, "state": REFUSE, "code": "declared_record_invalid"}
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


def _raise(error):
    raise error


def tree_size(root) -> int:
    """Bytes under ``root``; an unreadable directory raises (a low count would lower the disk floor)."""
    total = 0
    for base, dirs, files in os.walk(root, onerror=_raise):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in files:
            try:
                st = os.lstat(os.path.join(base, name))
            except FileNotFoundError:
                continue  # a live root changes while it is measured
            total += st.st_size
    return total


class Door:
    """A prepared door root, read from its own receiver config (``<root>/receiver/receiver.json``): its state
    directory (``root`` in the config: ``<root>/receiver/state``, or H1's fixed per-door path) and its accepted
    revision. Anything missing raises `ei.Unknown`: a wrong path never passes as an empty door.
    """

    def __init__(self, root):
        self.root = Path(root)
        try:
            cfg = json.loads(
                (self.root / "receiver" / "receiver.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as failed:
            raise ei.Unknown("receiver_config_unreadable") from failed
        if type(cfg) is not dict or type(cfg.get("root")) is not str:
            raise ei.Unknown("receiver_config_unreadable")
        self.state = Path(cfg["root"])
        if not self.state.is_absolute():
            self.state = self.root / self.state
        if not self.state.is_dir():
            raise ei.Unknown("state_dir_missing")
        self.accepted = cfg.get("accepted_revision")

    def size(self) -> int:
        size = tree_size(self.root)
        try:
            self.state.relative_to(self.root)
        except ValueError:
            size += tree_size(self.state)  # a fixed state dir outside the release root
        return size


def disk_item(mode, old_root, new_root, *, free=None, size=None) -> dict:
    size = Door(old_root).size() if size is None else size
    target = Path(new_root)
    while not target.exists():
        target = target.parent
    free = shutil.disk_usage(target).free if free is None else free
    floor = int(DISK_FACTOR[mode] * size) + DISK_HEADROOM
    out = {"free": free, "old_root_bytes": size, "floor": floor, "mode": mode}
    if free < floor:
        return {**out, "state": REFUSE, "code": "disk_below_floor"}
    return {**out, "state": PASS}


def _dirs(path):
    """Real (not linked) subdirectories of ``path`` whose names do not start with '.', and the linked ones."""
    real, links = [], []
    with os.scandir(path) as it:
        for entry in it:
            if entry.name.startswith("."):
                continue  # staging leftovers (.pending-*, .seedtmp.*, .ovtmp.*) are never cache entries
            if entry.is_symlink():
                links.append(entry.name)
            elif entry.is_dir(follow_symlinks=False):
                real.append(entry.name)
    return real, links


def cache_entries(root, *, require=False) -> tuple:
    """(``{name: (files, bytes)}``, links): every library-cache entry (64-hex bundle dirs, materials/*) and every
    prepared-overlay leaf (4 digest levels) under ``root``; ``links`` = every symlink met on the way (the receiver
    refuses a linked cache path: `_private_cache_directory`, the overlay path check). ``require``: the library-cache
    directory must exist (an old root without one is a wrong path, never an empty cache).
    """
    out, links = {}, []
    base = Path(root) / LIBRARY
    if base.is_symlink():
        return out, [LIBRARY]
    if not base.is_dir():
        if require:
            raise ei.Unknown("library_cache_missing")
        return out, links
    real, linked = _dirs(base)
    links += [f"{LIBRARY}/{n}" for n in linked]
    for name in real:
        if re.fullmatch(r"[0-9a-f]{64}", name):
            out["library/" + name] = base / name
    materials = base / "materials"
    if materials.is_symlink():
        links.append(f"{LIBRARY}/materials")
    elif materials.is_dir():
        with os.scandir(materials) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                if entry.is_symlink():
                    links.append(f"{LIBRARY}/materials/{entry.name}")
                else:
                    out["materials/" + entry.name] = materials / entry.name
    overlays = base / "overlays"
    if overlays.is_symlink():
        links.append(f"{LIBRARY}/overlays")
    elif overlays.is_dir():
        level = [Path()]
        for _ in range(4):
            deeper = []
            for rel in level:
                real, linked = _dirs(overlays / rel)
                links += [f"{LIBRARY}/overlays/{(rel / n).as_posix()}" for n in linked]
                deeper += [rel / n for n in real]
            level = deeper
        for rel in level:
            out["overlay/" + rel.as_posix()] = overlays / rel
    return {name: _counts(path) for name, path in out.items()}, links


def _counts(path) -> tuple:
    if path.is_file():
        return 1, path.stat().st_size
    files = size = 0
    for base, dirs, names in os.walk(path, onerror=_raise):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in names:
            files += 1
            size += os.lstat(os.path.join(base, name)).st_size
    return files, size


def _private(path, uid) -> bool:
    """`library_bundles._private_cache_directory`'s rule: a real directory, the receiver's owner, no group/other bits."""
    if path.is_symlink() or not path.is_dir() or path.resolve() != path.absolute():
        return False
    if os.name != "posix":
        return True
    st = path.stat()
    return st.st_uid == uid and stat.S_IMODE(st.st_mode) & 0o077 == 0


def caches_item(old_roots, new_root) -> dict:
    new, new_links = cache_entries(new_root)
    missing, differ, checked = [], [], 0
    uid = None
    for root in old_roots:
        entries, _ = cache_entries(root, require=True)
        if uid is None:
            uid = (Path(root) / LIBRARY).stat().st_uid if os.name == "posix" else 0
        for name, counts in entries.items():
            checked += 1
            if name not in new:
                missing.append(name)
            elif new[name] != counts:
                differ.append(name)
    missing, differ = sorted(set(missing)), sorted(set(differ) - set(missing))
    base = Path(new_root) / LIBRARY
    unusable = [
        str(p.relative_to(new_root))
        for p in (base, base / "materials")
        if (p.exists() or p.is_symlink()) and not _private(p, uid)
    ]
    out = {
        "checked": checked,
        "new_entries": len(new),
        "missing": len(missing),
        "differ": len(differ),
        "links": len(new_links),
        "unusable": unusable,
    }
    if new_links:
        return {
            **out,
            "state": REFUSE,
            "code": "cache_path_is_link",
            "first": new_links[:10],
        }
    if unusable:
        return {**out, "state": REFUSE, "code": "cache_dir_not_private"}
    if missing or differ:
        return {
            **out,
            "state": REFUSE,
            "code": "caches_not_carried",
            "first": (missing + differ)[:10],
        }
    return {**out, "state": PASS}


#: The commit that made the host lock round-robin (main, 5 Nov). A door whose accepted revision lacks it does not honour
#: the other doors' waits (R79: Cooling on old code starved the others' king work, 6 Nov 00:30).
ROUND_ROBIN_COMMIT = "d85950921be30aef4ce949c6874bc0771b09a378"
RECEIVER_MODULE = "carbon.challenge_validator.direct_receiver"


def owners_item(old_root) -> dict:
    """(R36) Every retained owner in OLD's state has the shape the receiver restores, so NEW starts: ``owner.json`` =
    exactly {"hotkey"} whose sha256 is the directory's name, and ``ledger/campaign.sqlite3`` holding its frozen
    campaign manifest. A partly restored owner refuses the switch here, named, before any stop (else NEW refuses at
    start: ``retained direct owner campaign manifest missing`` / ``owner binding differs``). Read-only.
    """
    import hashlib
    import sqlite3

    owners = Door(old_root).state / "owners"
    if not owners.is_dir():
        return {"state": PASS, "owners": 0}
    broken, count = [], 0
    for directory in sorted(owners.iterdir()):
        if directory.name.startswith("."):
            continue
        count += 1
        reason = None
        try:
            if directory.is_symlink() or not directory.is_dir():
                reason = "not_a_directory"
            else:
                owner = json.loads(
                    (directory / "owner.json").read_text(encoding="utf-8")
                )
                if (
                    type(owner) is not dict
                    or set(owner) != {"hotkey"}
                    or type(owner["hotkey"]) is not str
                    or hashlib.sha256(owner["hotkey"].encode()).hexdigest()
                    != directory.name
                ):
                    reason = "owner_binding_differs"
                else:
                    ledger = directory / "ledger" / "campaign.sqlite3"
                    if not ledger.is_file():
                        reason = "campaign_ledger_missing"
                    else:
                        db = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
                        try:
                            row = db.execute(
                                "SELECT 1 FROM campaign WHERE id=1"
                            ).fetchone()
                        finally:
                            db.close()
                        if row is None:
                            reason = "campaign_manifest_missing"
        except FileNotFoundError:
            reason = "owner_json_missing"
        except (OSError, ValueError, sqlite3.Error):
            reason = "owner_unreadable"
        if reason:
            broken.append({"owner": directory.name, "reason": reason})
    if broken:
        return {
            "state": REFUSE,
            "code": "owner_shape_broken",
            "owners": count,
            "broken": broken[:10],
        }
    return {"state": PASS, "owners": count}


def _receiver_roots(proc):
    """The receiver roots of every live direct-receiver process (from its --config <root>/receiver/receiver.json)."""
    roots = set()
    for entry in Path(proc).iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        words = [a.decode("utf-8", "replace") for a in argv if a]
        if RECEIVER_MODULE not in words and not any(
            w.endswith("direct_receiver.py") for w in words
        ):
            continue
        if "--config" in words and words.index("--config") + 1 < len(words):
            config = Path(words[words.index("--config") + 1])
            roots.add(str(config.parent.parent))
        else:
            roots.add("<no --config>")
    return roots


#: A process the binding check reads: a direct receiver or the weights loop.
WEIGHTS_MARKERS = (
    "carbon.validator_setup",
    "carbon.rewards.testnet_winner_publication",
    "wcycle",
    # between cycles only the loop's shell script runs; its environment is what each cycle inherits
    "weights-loop",
)
#: The process table the host checks read (a test points it at a fake one).
PROC = "/proc"
CHAIN_ENVIRONMENT = (
    "CARBON_CHAIN_NETWORK",
    "CARBON_LOCALNET_GENESIS",
    "CARBON_LOCALNET_ENDPOINT",
)


def _config_network(config):
    """The network a receiver.json names (``chain_network``; testnet for a root prepared before the record existed),
    or None when it cannot be read."""
    try:
        record = json.loads(Path(config).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if type(record) is not dict:
        return None
    network = record.get("chain_network", {"network": "testnet"})
    return network.get("network") if type(network) is dict else None


def _door_network(words):
    """The network a running receiver's own ``--config`` receiver.json names, or None when it cannot be read."""
    try:
        return _config_network(words[words.index("--config") + 1])
    except (ValueError, IndexError):
        return None


def door_network_item(old_root, new_root, expect="testnet") -> dict:
    """(N2/N3) NEW serves OLD's door, so it is bound to OLD's network: NEW's receiver.json names the same network as
    OLD's, and one this host serves. A NEW prepared from a shell bound elsewhere (a testnet re-prepare in a shell still
    exporting finney) refuses here, before the switch; its own process would match its record and start.
    """
    expects = (expect,) if isinstance(expect, str) else tuple(dict.fromkeys(expect))
    config = Path("receiver") / "receiver.json"
    old = _config_network(Path(old_root) / config)
    new = _config_network(Path(new_root) / config)
    if old is None or new is None:
        return {
            "state": UNKNOWN,
            "code": "receiver_config_unreadable",
            "old": old,
            "new": new,
        }
    if new != old:
        return {"state": REFUSE, "code": "new_network_differs", "old": old, "new": new}
    if new not in expects:
        return {
            "state": REFUSE,
            "code": "door_network_not_expected",
            "network": new,
            "expect": expect,
        }
    return {"state": PASS, "network": new}


#: a sealed-pack store's network record (`sealed_pack_import.STORE_NETWORK_FILE`); none = the legacy testnet store
STORE_NETWORK_FILE = ".store-network.json"
STORE_NETWORK_SCHEMA = "carbon.sealed-pack-store-network.v1"
LEGACY_STORE_NETWORK = "testnet-567"


def _store_network(store):
    """A pack store's recorded network (``NETWORK-NETUID``), the legacy testnet one when it has no record, or None when
    the record cannot be read. Read as `SealedPackStore.network` reads it; this tool imports no carbon code.
    """
    path = Path(store) / STORE_NETWORK_FILE
    if not Path(store).is_dir():
        return None
    if not path.exists() and not path.is_symlink():
        return LEGACY_STORE_NETWORK
    if path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        type(value) is not dict
        or set(value) != {"network", "schema"}
        or value["schema"] != STORE_NETWORK_SCHEMA
        or type(value["network"]) is not str
    ):
        return None
    return value["network"]


def open_door_item(new_root, network, expect="testnet") -> dict:
    """(Fri mainnet day-of, step 2) A FRESH door has no OLD to compare with, so its own records are checked before it
    opens: its receiver.json names ``network`` explicitly (a root with no ``chain_network`` record is a testnet root
    and never opens as a mainnet door), that network is one this host serves, and every pack store the door reads
    (``evaluation_pack.sealed_delivery`` and ``evaluation_pack_set``) is bound to that same network. A non-testnet door
    must serve a sealed delivery; it never opens on a pack copied in by hand.
    """
    expects = (expect,) if isinstance(expect, str) else tuple(dict.fromkeys(expect))
    try:
        record = json.loads(
            (Path(new_root) / "receiver" / "receiver.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {"state": UNKNOWN, "code": "receiver_config_unreadable"}
    if type(record) is not dict:
        return {"state": UNKNOWN, "code": "receiver_config_unreadable"}
    chain = record.get("chain_network")
    recorded = chain.get("network") if type(chain) is dict else None
    if recorded is None:
        return {"state": REFUSE, "code": "new_door_network_unrecorded"}
    out = {"network": recorded}
    if recorded != network:
        return {
            **out,
            "state": REFUSE,
            "code": "new_door_network_not_the_one_named",
            "named": network,
        }
    if recorded not in expects:
        return {
            **out,
            "state": REFUSE,
            "code": "door_network_not_expected",
            "expect": expect,
        }
    stores = []
    pack = record.get("evaluation_pack")
    delivery = pack.get("sealed_delivery") if type(pack) is dict else None
    if type(delivery) is dict:
        stores.append(delivery.get("store"))
    block = record.get("evaluation_pack_set")
    if type(block) is dict:
        stores.append(block.get("store"))
    if not stores:
        if recorded != "testnet":
            return {**out, "state": REFUSE, "code": "new_door_pack_not_sealed_delivery"}
        return {**out, "state": PASS, "stores": []}
    seen = []
    for store in dict.fromkeys(stores):
        if type(store) is not str:
            return {**out, "state": UNKNOWN, "code": "pack_store_unreadable"}
        stored = _store_network(store)
        if stored is None:
            return {
                **out,
                "state": UNKNOWN,
                "code": "pack_store_network_unreadable",
                "store": store,
            }
        seen.append({"store": store, "network": stored})
        if stored.rsplit("-", 1)[0] != recorded:
            return {
                **out,
                "state": REFUSE,
                "code": "pack_store_network_mismatch",
                "store": store,
                "store_network": stored,
            }
    return {**out, "state": PASS, "stores": seen}


def chain_binding_item(
    host_roots,
    expect="testnet",
    *,
    proc="/proc",
    receivers_expected=0,
    loops_pending=(),
) -> dict:
    """(H8 part 3, Validator-2 6 Nov 09:22) No live door and no weights loop runs bound to anything but ``expect``:
    every running direct receiver's and weights-loop process's environment has ``CARBON_CHAIN_NETWORK`` unset/empty or
    ``testnet`` (``finney`` only when ``expect`` is finney) and no localnet variable; and no ``--host-root`` carries the
    staging marker (``receiver/STAGING``; OLD and NEW are always read too). An environment this user cannot read is UNKNOWN, never a pass.

    (N2, lock-in rev 4) Mainnet and testnet doors share one host: ``expect`` may name several live networks (the ones
    this host serves). A RECEIVER is then held to its OWN door's network, the ``chain_network`` its ``--config``
    receiver.json names (a root prepared before that record is testnet); a door whose network this host does not
    serve refuses (``receiver_network_not_expected``). A weights loop may be bound to any expected network.

    ``loops_pending`` (open mode, ``--weights-loop-pending``) names an expected network whose weights loop has not
    started YET (mainnet day-of: the finney loop starts after its doors open); it is exempt from the one-loop-per-
    network rule only, never from the binding rules, and must itself be an expected network.
    """
    expects = (expect,) if isinstance(expect, str) else tuple(dict.fromkeys(expect))
    staged = sorted(
        {str(r) for r in host_roots if (Path(r) / "receiver" / "STAGING").exists()}
    )
    if staged:
        return {"state": REFUSE, "code": "staging_root_on_host", "roots": staged[:10]}
    if not Path(proc).is_dir():
        return {"state": UNKNOWN, "code": "process_table_unreadable"}

    def allowed_for(network):
        return {"", "testnet"} if network == "testnet" else {network}

    loop_allowed = set().union(*(allowed_for(n) for n in expects))
    read, wrong, receivers, loops = 0, [], 0, 0
    loops_by = dict.fromkeys(expects, 0)  # weights loops found per expected network
    for entry in Path(proc).iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        words = [a.decode("utf-8", "replace") for a in argv if a]
        receiver = RECEIVER_MODULE in words or any(
            w.endswith("direct_receiver.py") for w in words
        )
        weights = any(m in w for w in words for m in WEIGHTS_MARKERS)
        if not (receiver or weights):
            continue
        try:
            raw = (entry / "environ").read_bytes()
        except FileNotFoundError:
            continue  # it exited
        except OSError:
            return {"state": UNKNOWN, "code": "process_environment_unreadable"}
        env = dict(
            item.decode("utf-8", "replace").partition("=")[::2]
            for item in raw.split(b"\0")
            if b"=" in item
        )
        read += 1
        receivers += receiver
        loops += not receiver
        allowed, door_network = loop_allowed, None
        if receiver:
            door_network = _door_network(words)
            if door_network is None:
                return {
                    "state": UNKNOWN,
                    "code": "receiver_config_unreadable",
                    "pid": int(entry.name),
                }
            if door_network not in expects:
                return {
                    "state": REFUSE,
                    "code": "receiver_network_not_expected",
                    "pid": int(entry.name),
                    "door_network": door_network,
                    "expect": expect,
                }
            allowed = allowed_for(door_network)
        if env.get("CARBON_CHAIN_NETWORK", "") not in allowed or any(
            name in env for name in CHAIN_ENVIRONMENT[1:]
        ):
            item = {
                "pid": int(entry.name),
                "kind": "receiver" if receiver else "weights",
                "network": env.get("CARBON_CHAIN_NETWORK", ""),
            }
            if door_network is not None:
                item["door_network"] = door_network
            wrong.append(item)
        elif not receiver:
            loops_by[env.get("CARBON_CHAIN_NETWORK", "") or "testnet"] += 1
    if wrong:
        return {
            "state": REFUSE,
            "code": "process_not_on_the_live_chain",
            "processes": wrong[:10],
        }
    # (N2) a host that serves two networks runs one weights loop for each (a pending one is named, never assumed)
    unlooped = [n for n in expects if loops_by[n] < 1 and n not in loops_pending]
    looped_needed = any(n not in loops_pending for n in expects)
    if receivers < receivers_expected or (loops < 1 and looped_needed) or unlooped:
        # (Validator-2 10:43) a check that read nothing is no pass: the running doors and the weights loop must be
        # FOUND, so a marker that stops matching surfaces here instead of passing silently
        return {
            "state": UNKNOWN,
            "code": "binding_processes_missing",
            "receivers": receivers,
            "receivers_expected": receivers_expected,
            "weights_loops": loops,
            **({"networks_without_a_loop": unlooped} if unlooped else {}),
        }
    return {
        "state": PASS,
        "read": read,
        "receivers": receivers,
        "weights_loops": loops,
        "expect": expect,
        **({"loops_pending": sorted(loops_pending)} if loops_pending else {}),
    }


def _expected_networks(given):
    """``--expect-network`` as given: testnet when unset, one name when one, else the names in order."""
    names = list(dict.fromkeys(given or ["testnet"]))
    return names[0] if len(names) == 1 else names


def receivers_item(host_roots, *, proc="/proc") -> dict:
    """(R41) Every direct receiver running on this host is one of the declared door roots: a stray scratch receiver
    (shared IP, chain load, a host-lock contender) refuses the switch until it is stopped or declared.
    """
    if not Path(proc).is_dir():
        return {"state": UNKNOWN, "code": "process_table_unreadable"}
    declared = {str(Path(r).absolute()) for r in host_roots}
    running = _receiver_roots(proc)
    stray = sorted(running - declared)
    if stray:
        return {
            "state": REFUSE,
            "code": "undeclared_receiver_running",
            "stray": stray[:10],
            "running": len(running),
        }
    return {"state": PASS, "running": len(running)}


def lock_versions_item(repo, host_roots, new, allow=None) -> dict:
    """(R79) Doors on one host share one grading lock: a door on lock code older than the round-robin does not honour
    the others' waits. When NEW has the round-robin, every OTHER declared door must have it too or be DRAINING (its own
    flag), unless ``allow`` (``--allow-mixed-lock REASON``) names why."""
    import subprocess

    def has_round_robin(revision):
        done = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "merge-base",
                "--is-ancestor",
                ROUND_ROBIN_COMMIT,
                revision,
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if done.returncode not in (0, 1):
            raise ei.Unknown("lock_version_unknown")
        return done.returncode == 0

    known = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", ROUND_ROBIN_COMMIT + "^{commit}"],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if known.returncode != 0:
        # a repository without the round-robin commit (a test fixture, a fork): nothing on this host can have it
        return {
            "state": PASS,
            "new_round_robin": False,
            "note": "round_robin_commit_not_in_repo",
        }
    if not has_round_robin(new):
        return {"state": PASS, "new_round_robin": False}
    doors, mixed = [], []
    for root in host_roots:
        door = Door(root)
        if door.accepted is None:
            raise ei.Unknown("door_accepted_revision_missing")
        rr = has_round_robin(door.accepted)
        draining = (door.state / DRAIN_NAME).exists()
        doors.append({"root": str(root), "round_robin": rr, "draining": draining})
        if not rr and not draining:
            mixed.append(str(root))
    out = {"new_round_robin": True, "doors": doors}
    if mixed and not allow:
        return {
            **out,
            "state": REFUSE,
            "code": "mixed_lock_code_undrained",
            "undrained": mixed,
        }
    if mixed:
        return {**out, "state": PASS, "allowed": allow}
    return {**out, "state": PASS}


def chain_item(old_root, allow=None) -> dict:
    """(H8) Never flip into a chain outage: OLD's own ``chain-state.json`` (written by H8 receivers) must not say
    DEGRADED. ``allow`` (``--allow-chain-degraded REASON``) lets a fix-forward for the chain fault itself through,
    named in the result (Validator-2 5 Nov 18:56: no guard without a way through when the harm is the guard's own).
    A door from before H8 writes no such file: reported as not_reported, never a refusal.
    """
    path = Door(old_root).state / "chain-state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"state": PASS, "chain": "not_reported"}
    except (OSError, ValueError):
        return {"state": UNKNOWN, "code": "chain_state_unreadable"}
    if type(state) is not dict or state.get("state") not in ("OK", "DEGRADED"):
        return {"state": UNKNOWN, "code": "chain_state_unreadable"}
    if state["state"] == "OK":
        return {"state": PASS, "chain": "OK"}
    out = {
        "chain": "DEGRADED",
        "code": state.get("code"),
        "since_ns": state.get("since_ns"),
    }
    if allow:
        return {**out, "state": PASS, "allowed": allow}
    return {**out, "state": REFUSE, "code": "chain_degraded"}


def drain_item(old_root) -> dict:
    """OLD's drain flag, in the state directory its own config names (`door_drain.py`)."""
    flag = Door(old_root).state / DRAIN_NAME
    if flag.exists() or flag.is_symlink():
        return {"state": REFUSE, "code": "old_door_draining"}
    return {"state": PASS}


def ancestry_item(repo, old, new) -> dict:
    """The receiver migrates only when OLD is an ancestor of NEW in its checkout (`direct_receiver._is_ancestor`):
    ``--repo`` is the NEW release's checkout."""
    import subprocess

    done = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", old, new],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if done.returncode == 0:
        return {"state": PASS}
    if done.returncode == 1:
        return {"state": REFUSE, "code": "old_not_ancestor_of_new"}
    return {"state": UNKNOWN, "code": "ancestry_unknown"}


def accepted_item(old_root, new_root, old, new) -> dict:
    """The revisions given are the ones the doors ACCEPT: the receiver compares those, and a declared record must
    name them."""
    for root, rev, side in ((old_root, old, "old"), (new_root, new, "new")):
        accepted = Door(root).accepted
        if accepted is None:
            # a config that names no accepted revision cannot show the receiver compares these (Validator-2 11:55)
            return {"state": UNKNOWN, "code": f"{side}_accepted_revision_missing"}
        if accepted != rev:
            return {"state": REFUSE, "code": f"{side}_rev_is_not_the_accepted_revision"}
    return {"state": PASS}


SERVED_FILE = "carbon/challenge_validator/lean_recipe.py"
STAGING_WORKERS = (
    "carbon/development_session/bundle_construction_worker.py",
    "carbon/development_session/direct_graph_construction_worker.py",
)


def _tuple_at(repo, commit, path, name):
    """The string tuple assigned to ``name`` at module level in ``path`` at ``commit`` (by ast), or None."""
    try:
        tree = ast.parse(ei._git(repo, "show", f"{commit}:{path}").decode("utf-8"))
    except ei.Unknown:
        return None
    except (SyntaxError, ValueError) as failed:
        raise ei.Unknown("served_source_list_unreadable") from failed
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and getattr(node.targets[0], "id", None) == name
        ):
            value = ast.literal_eval(node.value)
            if type(value) is not tuple or any(type(v) is not str for v in value):
                raise ei.Unknown("served_source_list_unreadable")
            return value
    return None


def served_files(repo, commit) -> set:
    """The files the served source identity hashes at ``commit`` (`lean_recipe._source_identity`): `_SOURCE_PATHS`
    plus every module the construction workers stage."""
    files = set(_tuple_at(repo, commit, SERVED_FILE, "_SOURCE_PATHS") or ())
    for worker in STAGING_WORKERS:
        for module in _tuple_at(repo, commit, worker, "STAGED_MODULES") or ():
            files.add(module.replace(".", "/") + ".py")
    if not files:
        raise ei.Unknown("served_source_list_absent")
    return files


def served_source_item(repo, old, new) -> dict:
    """Which served-source files OLD..NEW changes (design note s1.5): never a refusal by itself, but said before the
    switch with its cost, so a plumbing edit is a decision, not a surprise."""
    files = served_files(repo, old) | served_files(repo, new)
    names = ei._git(repo, "diff", "--name-only", "-z", "--no-renames", old, new, "--")
    changed = sorted(p for p in names.decode("utf-8").split("\0") if p in files)
    if not changed:
        return {"state": PASS, "changed": []}
    return {
        "state": PASS,
        "changed": changed,
        "note": (
            "served source changes: on every door this needs the declared record + one spare regrade "
            "(design note s1.5); if R66 showed key movement, every king is rebuilt"
        ),
    }


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


def release_class(items) -> dict:
    """The release class (MAINNET_UPDATE_ARCHITECTURE s7.5) as the checks REPORT it, never as the operator says it:
    2 = the exam moves (a declared grading-code change, a re-sealed pack or an M2 rule edit); 1 = served-source files
    change (no key moves, R66, but every door is told); 0 = neither. None when the ``exam`` or ``served_source`` item did
    not pass (the class is unknown, so nothing is routine). A state migration (class 3) is not visible in the diff:
    the spare prepare's migration count says it."""
    exam, served = items.get("exam"), items.get("served_source")
    if (
        type(exam) is not dict
        or type(served) is not dict
        or exam.get("state") != PASS
        or served.get("state") != PASS
    ):
        return {"class": None, "basis": "exam_or_served_source_not_passed"}
    if (
        exam.get("declared")
        or "pack_change" in exam
        or "rule_change" in exam
        or (exam.get("identity") or {}).get("state") != ei.SAME
    ):
        return {"class": 2, "basis": "exam_changes_declared"}
    if served.get("changed"):
        return {
            "class": 1,
            "basis": "served_source_changed",
            "changed": served["changed"],
        }
    return {"class": 0, "basis": "exam_keys_equal_and_no_served_source"}


def open_checks(args, new) -> list:
    """(Fri mainnet day-of, step 2) The items for opening a FRESH door, one with no OLD to compare: the release and
    its records, the new door's own network and pack stores, disk, and every other door on this host still bound
    right. There is no exam comparison (nothing to compare with), so ``release_class`` is reported unknown.
    """
    expect = _expected_networks(args.expect_network)
    others = [
        r
        for r in args.host_root
        if Path(r).absolute() != Path(args.new_root).absolute()
    ]
    return [
        ("final_heads", lambda: final_heads_status(args.final_heads, new)),
        ("accepted", lambda: open_accepted_item(args.new_root, new)),
        ("release", lambda: release_item(args.new_root, new)),
        ("open_door", lambda: open_door_item(args.new_root, args.new_network, expect)),
        (
            "disk",
            lambda: disk_item(
                args.mode, None, args.new_root, size=Door(args.new_root).size()
            ),
        ),
        ("receivers", lambda: receivers_item([*others, args.new_root], proc=PROC)),
        (
            "chain_binding",
            lambda: chain_binding_item(
                [*others, args.new_root],
                expect,
                proc=PROC,
                # every other declared door must be running and read; NEW is prepared, not yet started
                receivers_expected=len({str(Path(r).absolute()) for r in others}),
                loops_pending=tuple(args.weights_loop_pending),
            ),
        ),
        (
            "lock_versions",
            lambda: lock_versions_item(args.repo, others, new, args.allow_mixed_lock),
        ),
    ]


def open_accepted_item(new_root, new) -> dict:
    """The fresh door's config ACCEPTS the revision given (``accepted_item`` without an OLD side)."""
    accepted = Door(new_root).accepted
    if accepted is None:
        return {"state": UNKNOWN, "code": "new_accepted_revision_missing"}
    if accepted != new:
        return {"state": REFUSE, "code": "new_rev_is_not_the_accepted_revision"}
    return {"state": PASS}


def precheck(args) -> dict:
    out = {"schema": SCHEMA + ".precheck", "mode": args.mode, "items": {}}
    if args.mode == "open":
        try:
            new = ei.resolve(args.repo, args.new_rev)
        except ei.Unknown as failed:
            return {**out, "state": UNKNOWN, "code": str(failed)}
        out.update(new=new)
        return _run_checks(
            out, open_checks(args, new), class_basis="open_has_no_old_door"
        )
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
        ("accepted", lambda: accepted_item(args.old_root, args.new_root, old, new)),
        ("ancestry", lambda: ancestry_item(args.repo, old, new)),
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
                args.declared_rule_change,
            ),
        ),
        ("disk", lambda: disk_item(args.mode, args.old_root, args.new_root)),
        ("served_source", lambda: served_source_item(args.repo, old, new)),
    ]
    if args.mode == "switch":
        checks += [
            (
                "caches",
                lambda: caches_item([args.old_root, *args.older_root], args.new_root),
            ),
            ("drain", lambda: drain_item(args.old_root)),
            ("chain", lambda: chain_item(args.old_root, args.allow_chain_degraded)),
            ("owners", lambda: owners_item(args.old_root)),
            (
                "door_network",
                lambda: door_network_item(
                    args.old_root,
                    args.new_root,
                    _expected_networks(args.expect_network),
                ),
            ),
            ("receivers", lambda: receivers_item(args.host_root, proc=PROC)),
            (
                "chain_binding",
                lambda: chain_binding_item(
                    [*args.host_root, args.old_root, args.new_root],
                    _expected_networks(args.expect_network),
                    proc=PROC,
                    # every declared door but NEW (prepared, not yet started) must be running and read
                    receivers_expected=len(
                        {str(Path(r).absolute()) for r in args.host_root}
                        - {str(Path(args.new_root).absolute())}
                    ),
                ),
            ),
            (
                "lock_versions",
                lambda: lock_versions_item(
                    args.repo,
                    [
                        r
                        for r in args.host_root
                        if Path(r).absolute() != Path(args.old_root).absolute()
                    ],
                    new,
                    args.allow_mixed_lock,
                ),
            ),
            ("release", lambda: release_item(args.new_root, new)),
        ]
    return _run_checks(out, checks)


def _run_checks(out, checks, *, class_basis=None) -> dict:
    items = out["items"]
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
    out["release_class"] = (
        release_class(items)
        if class_basis is None
        else {"class": None, "basis": class_basis}
    )
    return out


# --- the owner's push line (R28) -------------------------------------------------------------------------------------


def pushline(repo, sha, final_heads, *, main="origin/main") -> dict:
    """The owner's push line for ``sha``, ONLY when it can land as asked: a full commit id, a fast-forward of ``main``
    (``main`` is its ancestor) and FINAL or LANDED in FINAL_HEADS on every row. Anything else refuses BEFORE an owner
    ask (5 Nov: a line for a non-FF head cost an owner round trip)."""
    if not _HEX40.fullmatch(sha or ""):
        return {"state": REFUSE, "code": "not_a_full_commit_id"}
    commit = ei.resolve(repo, sha)
    if commit != sha:
        return {"state": REFUSE, "code": "not_a_full_commit_id"}
    base = ei.resolve(repo, main)
    ff = ancestry_item(repo, base, commit)
    if ff["state"] != PASS:
        return {
            "state": ff["state"],
            "code": "not_a_fast_forward_of_main",
            "main": base,
        }
    heads = final_heads_status(final_heads, commit)
    if heads["state"] != PASS:
        return {**heads, "main": base}
    return {
        "state": PASS,
        "main": base,
        "sha": commit,
        "line": f"PR Head: push {commit} to main.",
    }


# --- deploy log ----------------------------------------------------------------------------------------------------


def log_append(path, event) -> dict:
    """Append ``event`` with the previous line's sha (a chain). Refuses to extend a log that does not verify."""
    if type(event) is not dict or not event:
        raise ValueError("an event is a non-empty JSON object")
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        _lock(fd)
        checked = log_verify(path)
        if checked["state"] != PASS:
            raise ValueError("log_does_not_verify")
        line = {
            "seq": checked["lines"] + 1,
            "at_ns": time.time_ns(),
            "prev": checked["last"],
            "event": event,
        }
        line["sha"] = "sha256:" + hashlib.sha256(_canonical(line)).hexdigest()
        os.write(fd, _canonical(line) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)  # also drops the lock
    return {"state": PASS, "seq": line["seq"], "sha": line["sha"]}


def _lock(fd):
    """An exclusive lock on the log for one append (two writers would both take the same seq)."""
    try:
        import fcntl
    except (
        ImportError
    ):  # not POSIX: tests only; the tool runs on the Linux validator host
        return
    fcntl.flock(fd, fcntl.LOCK_EX)


def log_verify(path, expect_last=None) -> dict:
    """The chain: each line's seq, prev and sha. A cut TAIL still verifies on its own; pass the last sha recorded
    elsewhere (the deploy receipt) as ``expect_last`` to catch it."""
    prev, n = None, 0
    data = Path(path).read_bytes() if Path(path).exists() else b""
    for raw in data.splitlines():
        n += 1
        try:
            line = json.loads(raw)
            sha = line.pop("sha")
        except (ValueError, KeyError, AttributeError, TypeError):
            return {"state": REFUSE, "code": "line_unreadable", "line": n}
        if line.get("seq") != n or line.get("prev") != prev:
            return {"state": REFUSE, "code": "chain_broken", "line": n}
        if "sha256:" + hashlib.sha256(_canonical(line)).hexdigest() != sha:
            return {"state": REFUSE, "code": "line_edited", "line": n}
        prev = sha
    if expect_last is not None and prev != expect_last:
        return {"state": REFUSE, "code": "last_line_differs", "lines": n, "last": prev}
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
    p.add_argument("--new-rev", required=True)
    # OLD and the packs: required in prepare/switch; open mode (a fresh door) has no OLD
    for name in ("--old-rev", "--old-pack", "--new-pack"):
        p.add_argument(name)
    p.add_argument("--old-root", type=Path)
    p.add_argument("--new-root", type=Path, required=True)
    p.add_argument("--final-heads", type=Path, required=True)
    p.add_argument("--declared", type=Path)
    p.add_argument("--declared-pack-change")
    p.add_argument("--declared-rule-change")
    p.add_argument("--allow-chain-degraded")
    # every door root on this host, OLD and NEW included (switch mode: R41 stray receivers, R79 lock versions)
    p.add_argument("--host-root", type=Path, action="append", default=[])
    p.add_argument("--allow-mixed-lock")
    # the live chain every door and the weights loop must be bound to (switch mode, H8 part 3)
    # (N2) repeat it on a host that serves both: each door is then held to its own receiver.json's network
    p.add_argument("--expect-network", choices=("testnet", "finney"), action="append")
    p.add_argument("--older-root", type=Path, action="append", default=[])
    # open mode: the network the fresh door serves (its receiver.json and pack stores must name it) ...
    p.add_argument("--new-network", choices=("testnet", "finney"))
    # ... and an expected network whose weights loop has not started yet (it starts after its doors open)
    p.add_argument(
        "--weights-loop-pending",
        choices=("testnet", "finney"),
        action="append",
        default=[],
    )
    pl = sub.add_parser("pushline")
    pl.add_argument("--repo", type=Path, required=True)
    pl.add_argument("--sha", required=True)
    pl.add_argument("--final-heads", type=Path, required=True)
    pl.add_argument("--main", default="origin/main")
    lg = sub.add_parser("log")
    lsub = lg.add_subparsers(dest="log_command", required=True)
    la = lsub.add_parser("append")
    la.add_argument("--log", type=Path, required=True)
    la.add_argument("--event", required=True)
    lv = lsub.add_parser("verify")
    lv.add_argument("--log", type=Path, required=True)
    lv.add_argument("--expect-last")
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
        elif args.command == "pushline":
            result = pushline(args.repo, args.sha, args.final_heads, main=args.main)
        elif args.command == "precheck":
            if args.mode == "open":
                if args.new_network is None:
                    parser.error("--new-network is required in open mode")
                if (
                    any(
                        getattr(args, n) is not None
                        for n in ("old_rev", "old_pack", "old_root")
                    )
                    or args.older_root
                ):
                    parser.error("open mode opens a fresh door: it takes no OLD")
                expected = set(args.expect_network or ["testnet"])
                if args.new_network not in expected:
                    parser.error("--new-network must be one of the --expect-network")
                if not set(args.weights_loop_pending) <= expected:
                    parser.error("--weights-loop-pending must be an --expect-network")
                if args.new_pack is not None:
                    ei.pack(args.new_pack)
            else:
                missing = [
                    "--" + n.replace("_", "-")
                    for n in ("old_rev", "old_pack", "new_pack", "old_root")
                    if getattr(args, n) is None
                ]
                if missing:
                    parser.error(f"{', '.join(missing)} required in {args.mode} mode")
                if args.new_network is not None or args.weights_loop_pending:
                    parser.error(
                        "--new-network / --weights-loop-pending are open-mode only"
                    )
                for name in ("old_pack", "new_pack"):
                    ei.pack(getattr(args, name))
            if args.mode == "switch" and not args.host_root:
                parser.error(
                    "--host-root (every door root on this host, OLD and NEW) is required in switch mode"
                )
            result = precheck(args)
        elif args.log_command == "append":
            result = log_append(args.log, json.loads(args.event))
        else:
            result = log_verify(args.log, args.expect_last)
    except Exception as failed:  # noqa: BLE001
        # every failure is a refusal or UNKNOWN, never a traceback
        result = {
            "state": REFUSE if isinstance(failed, ValueError) else UNKNOWN,
            "code": str(failed) or type(failed).__name__,
        }
    print(json.dumps(result, sort_keys=True))
    return EXIT[result["state"]]


if __name__ == "__main__":
    sys.exit(main())
