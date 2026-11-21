"""Motor Specialist Bank, PATH A v1: graph-level recipe features, COUNTS ONLY, into the bank file.

V2 02:50:46Z (shape Y); case-procs 03:00:01Z (file mapping + 3 caveats). For each submission in the bank file
(``bank_features.py`` output, ``outcomes``), its frozen graph envelope is the file
``owners/<o>/ledger/direct-task-sources/<sha256(task id)>.json`` (``research_tasks._source_path``). This reader:

- finds that file BY NAME from the hashed task id under ``owners/*/ledger/direct-task-sources/`` (no hotkey read;
  the owner directory name is never stored or printed);
- opens it read-only, one at a time, no lock; checks its sha256 against that owner's ``direct_task_sources`` row
  (``tasks/direct-tasks.sqlite3``, ``?mode=ro``; the row holds the ENVELOPE digest); a missing file or row is counted
  ``missing``, a mismatch ``refused`` (never inferred);
- parses it with the door's own parser (``carbon.level4.staging.from_envelope``) and, per graph document role
  (forward / loss / init / init_spec), counts: graphs, nodes by op name (only names in the version's served allowlist;
  any other name is counted as ``other``), constants, their total elements and declared bytes, inputs, outputs, and
  the init spec's parameter count; plus the envelope's bytes.

It never copies a constant VALUE, a document, an input name or any bytes (B4: fitted constants stay unread as
values), never reads a grade, gate, crown or score, and writes only the ``graph_features`` table of the bank file
(class C, owner-only, on GPUYard). stdout: counts only. TEAM_RULES #15: a read-only query at nice 19 / idle, never
during an apply stop; the first run gets V2's receipt of the exact line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import stat
import sys
from collections import Counter
from pathlib import Path

SCHEMA = "carbon.bank-graph-features.v0"
ROLES = ("forward", "loss", "init", "init_spec")
#: An operational read bound per envelope (not a science value): larger files are counted, never read.
MAX_ENVELOPE_BYTES = 64 << 20
DDL = """
DROP TABLE IF EXISTS graph_features;
CREATE TABLE graph_features(
    recipe_digest TEXT NOT NULL, role TEXT NOT NULL, envelope_bytes INTEGER, graphs INTEGER, nodes INTEGER,
    constants INTEGER, constant_elements INTEGER, constant_bytes INTEGER, inputs INTEGER, outputs INTEGER,
    parameters INTEGER, ops TEXT, PRIMARY KEY(recipe_digest, role));
"""


class BankRefused(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _ro(path):
    db = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=5)
    db.execute("PRAGMA query_only=1")
    return db


def served_ops(challenge_id, version):
    """The op names the version's served allowlist admits (public)."""
    from carbon.development_session import graph_adapters
    from carbon.level4.allowlist import Allowlist

    module = graph_adapters.module_for(challenge_id, version)
    if module is None:
        raise BankRefused("adapter_unregistered")
    allowed = Allowlist(module.served_allowlist_bytes(challenge_id, version))
    return frozenset(allowed.ops) | frozenset(allowed.aten) | frozenset(allowed.named)


def index_sources(state_root):
    """{file name: (envelope path, tasks db path)} over every owner; owner names stay in memory only."""
    found = {}
    owners = Path(state_root) / "owners"
    if not owners.is_dir():
        raise BankRefused("state_owners_missing")
    for owner in sorted(os.scandir(owners), key=lambda e: e.name):
        if owner.is_symlink() or not owner.is_dir():
            continue
        folder = Path(owner.path) / "ledger" / "direct-task-sources"
        tasks = Path(owner.path) / "tasks" / "direct-tasks.sqlite3"
        if not folder.is_dir() or folder.is_symlink():
            continue
        for entry in os.scandir(folder):
            if entry.name.endswith(".json") and not entry.is_symlink():
                found.setdefault(entry.name, (Path(entry.path), tasks))
    return found


def _count_doc(role, doc, ops):
    row = Counter()
    hist = Counter()
    if role == "init_spec":
        params = doc.get("parameters") if isinstance(doc, dict) else None
        row["parameters"] = len(params) if isinstance(params, list) else 0
        return row, hist
    graphs = doc.get("graphs") if isinstance(doc, dict) else None
    if not isinstance(graphs, dict):
        return None, hist
    row["graphs"] = len(graphs)
    for g in graphs.values():
        if not isinstance(g, dict):
            return None, hist
        nodes = g.get("nodes") or []
        consts = g.get("constants") or []
        row["nodes"] += len(nodes)
        row["inputs"] += len(g.get("inputs") or [])
        row["outputs"] += len(g.get("outputs") or [])
        row["constants"] += len(consts)
        for c in consts:
            shape = c.get("shape") if isinstance(c, dict) else None
            if isinstance(shape, list) and all(
                type(d) is int and d >= 0 for d in shape
            ):
                row["constant_elements"] += math.prod(shape)
            size = c.get("bytes") if isinstance(c, dict) else None
            if type(size) is int and size >= 0:
                row["constant_bytes"] += size
        for node in nodes:
            op = node.get("op") if isinstance(node, dict) else None
            hist[op if isinstance(op, str) and op in ops else "other"] += 1
    return row, hist


def features(raw, ops):
    """Per role: (counts, op histogram) of one envelope's documents, or a typed refusal."""
    from carbon.level4 import staging
    from carbon.level4.graph import GraphRefused

    try:
        _digest, raw_manifest, files = staging.from_envelope(json.loads(raw))
        names = json.loads(raw_manifest).get("documents")
    except (GraphRefused, ValueError, AttributeError):
        raise BankRefused("envelope_invalid") from None
    if not isinstance(names, dict):
        raise BankRefused("manifest_invalid")
    out = {}
    for role in ROLES:
        name = names.get(role)
        if name is None:
            continue
        if name not in files:
            raise BankRefused("document_missing")
        try:
            doc = json.loads(files[name])
        except ValueError:
            raise BankRefused("document_invalid") from None
        row, hist = _count_doc(role, doc, ops)
        if row is None:
            raise BankRefused("document_invalid")
        out[role] = (row, hist)
    return out


def _owner_only(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return False
    if os.name != "posix":
        return True
    return info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077


def build(bank_file, state_root, *, ops=None):
    """Fill ``graph_features`` in ``bank_file``; returns counts."""
    bank_file = Path(bank_file)
    if not bank_file.is_file() or not _owner_only(bank_file):
        raise BankRefused("bank_file_not_owner_only")
    out = sqlite3.connect(bank_file)
    try:
        meta = dict(out.execute("SELECT k, v FROM meta"))
        if meta.get("schema") != "carbon.bank-features.v0":
            raise BankRefused("bank_file_unknown")
        ops = served_ops(meta["challenge_id"], meta["version"]) if ops is None else ops
        subs = out.execute(
            "SELECT submission_id, recipe_digest FROM outcomes WHERE recipe_digest IS NOT NULL"
            " ORDER BY submission_id"
        ).fetchall()
        sources = index_sources(state_root)
        digests = {}
        counts = Counter()
        refused = Counter()
        totals = Counter()
        done = set()
        out.executescript(DDL)
        for sid, recipe in subs:
            if recipe in done:
                continue
            name = hashlib.sha256(sid.encode("utf-8")).hexdigest() + ".json"
            hit = sources.get(name)
            if hit is None:
                counts["missing_file"] += 1
                continue
            path, tasks = hit
            if tasks not in digests:
                try:
                    db = _ro(tasks)
                    try:
                        digests[tasks] = dict(
                            db.execute("SELECT id, digest FROM direct_task_sources")
                        )
                    finally:
                        db.close()
                except sqlite3.Error:
                    digests[tasks] = {}
            expected = digests[tasks].get(sid)
            if expected is None:
                counts["missing_row"] += 1
                continue
            size = path.stat().st_size
            if size > MAX_ENVELOPE_BYTES:
                refused["too_large"] += 1
                continue
            raw = path.read_bytes()
            if "sha256:" + hashlib.sha256(raw).hexdigest() != expected:
                refused["digest_mismatch"] += 1
                continue
            try:
                per_role = features(raw, ops)
            except BankRefused as error:
                refused[error.code] += 1
                continue
            del raw
            for role, (row, hist) in per_role.items():
                out.execute(
                    "INSERT INTO graph_features VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        recipe,
                        role,
                        size,
                        row["graphs"],
                        row["nodes"],
                        row["constants"],
                        row["constant_elements"],
                        row["constant_bytes"],
                        row["inputs"],
                        row["outputs"],
                        row["parameters"],
                        json.dumps(dict(sorted(hist.items()))),
                    ),
                )
                totals.update(hist)
            done.add(recipe)
            counts["recipes_with_graph"] += 1
        out.execute(
            "INSERT OR REPLACE INTO meta VALUES('graph_features_schema', ?)", (SCHEMA,)
        )
        out.commit()
    finally:
        out.close()
    return {
        **dict(counts),
        "refused": dict(refused),
        "op_totals": dict(totals.most_common()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--bank", required=True, help="the bank file (bank-features-v0.sqlite3)"
    )
    parser.add_argument(
        "--state", required=True, help="the receiver state root (read-only)"
    )
    args = parser.parse_args(argv)
    try:
        counts = build(args.bank, args.state)
    except BankRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
