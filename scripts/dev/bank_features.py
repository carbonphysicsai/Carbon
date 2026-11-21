"""Motor Specialist Bank, PATH A v0: the bank's corpus reader, recipe features and recipe lineage.

Owner G-LEAD-6 (STATE/bank-BRIEF.md REVISED SHAPE step 1); V2 BANK data contract (reports/BANK/
BANK_DATA_CONTRACT_MOTOR18_20261120.md, rule 1 "column allow-list"); V2 00:51:38Z (PATH A: scripts/dev/, first run
on a receipted line, class C output on GPUYard, counts-only stdout).

It reads ONE file, the Carbon Evidence Catalog (``scripts/dev/evidence_catalog.py`` output, class C), READ-ONLY, and
only through ``BankReader``: an allow-list of PUBLIC-SIGNAL tables and columns (contract rows 1-5, 8-11, 21). Every
other table (grades, markers, gate failures, requeues, pool models, crown, per-case objects: contract rows 12-20) and
every column not named below is refused BY NAME, before any SQL runs, and a catalog whose allowed tables do not carry
exactly the expected columns is refused as a whole (fail closed on schema drift). It never opens the receiver state,
a door lock or a door API. Run it on the catalog's host at idle priority:

  nice -n 19 ionice -c 3 <checkout>/.venv/bin/python -I scripts/dev/bank_features.py \
      --catalog <cec dir>/cec-v0.sqlite3 --out <owner-only dir> --challenge-id <id> --version <v>

It writes ONE new owner-only SQLite file (``BANK_NAME``), built in a temporary file and swapped in atomically:
- ``recipe_features``: per recipe digest, the recipe resolved by the version's OWN graph adapter
  (``graph_adapters.module_for(...).training_settings``; no re-parse here): source kind, graph digest, train fraction,
  members, batch, output weights, and per member its outputs, weight, resolved knobs and the knobs that differ from
  the version's registered defaults. A recipe the adapter refuses keeps the adapter's closed code.
- ``outcomes``: per submission, the PUBLIC build facts (task state, refusal / infra class, failed stage, train loss,
  member losses, steps, train cases, timing, device). Infra classes label Carbon's failures, never the recipe's.
- ``lineage``: per pseudonymous owner, submissions in admission order with the previous submission's recipe, whether
  the graph changed and which knobs changed. Observed structure only: never a score input (invariant 11).

Nothing here reads, derives or selects by an official score, grade, gate, crown or Ladder value. Graph-level
features (op histogram, constants bytes) need the built source envelopes and are v1, not this file.
stdout: counts only (no digest, id, pseudonym or value).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path

SCHEMA = "carbon.bank-features.v0"
BANK_NAME = "bank-features-v0.sqlite3"
CATALOG_SCHEMA = "carbon.evidence-catalog.v0"

#: The ONLY catalog tables and columns the bank may read (contract tag PUBLIC-SIGNAL). ``ALLOWED`` names what the
#: bank reads; ``EXPECTED`` is each allowed table's full v0 column set, so drift in the catalog fails closed.
ALLOWED = {
    "meta": ("k", "v"),
    "recipes": (
        "recipe_digest",
        "challenge_id",
        "version",
        "first_seen_s",
        "recipe_json",
    ),
    "submissions": (
        "submission_id",
        "challenge_id",
        "version",
        "owner",
        "recipe_digest",
        "admitted_ns",
        "created_s",
        "task_state",
        "refusal_code",
        "infra_class",
        "failure_stage",
        "rerun_of",
        "copy_of",
    ),
    "builds": (
        "submission_id",
        "build_device",
        "train_loss",
        "member_losses",
        "steps",
        "train_cases",
        "timing_s",
    ),
}
EXPECTED = {
    "meta": {"k", "v"},
    "recipes": {
        "recipe_digest",
        "challenge_id",
        "version",
        "first_seen_s",
        "bytes",
        "recipe_json",
    },
    "submissions": {
        "submission_id",
        "challenge_id",
        "version",
        "owner",
        "recipe_digest",
        "request_sha256",
        "admitted_ns",
        "created_s",
        "updated_s",
        "completed_s",
        "task_state",
        "refusal_code",
        "infra_class",
        "failure_stage",
        "failure_reason",
        "cancel_kind",
        "rerun_of",
        "copy_of",
    },
    "builds": {
        "submission_id",
        "state_digest",
        "practice_predictions_digest",
        "practice_inputs_digest",
        "build_device",
        "build_image_id",
        "inference_image_id",
        "train_loss",
        "member_losses",
        "members",
        "steps",
        "train_cases",
        "trainer_sha256",
        "params_sha256",
        "per_call_s",
        "timing_s",
    },
}

DDL = """
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE recipe_features(
    recipe_digest TEXT PRIMARY KEY, parse_code TEXT, source_kind TEXT, graph_digest TEXT, train_fraction REAL,
    members INTEGER, batch_size INTEGER, output_weights TEXT, first_seen_s REAL);
CREATE TABLE member_knobs(
    recipe_digest TEXT NOT NULL, member INTEGER NOT NULL, outputs TEXT, weight REAL, knobs TEXT, nondefault TEXT,
    PRIMARY KEY(recipe_digest, member));
CREATE TABLE outcomes(
    submission_id TEXT PRIMARY KEY, recipe_digest TEXT, task_state TEXT, refusal_code TEXT, infra_class TEXT,
    failure_stage TEXT, rerun_of TEXT, copy_of TEXT, build_device TEXT, train_loss REAL, member_losses TEXT,
    steps TEXT, train_cases INTEGER, timing_s TEXT);
CREATE TABLE lineage(
    submission_id TEXT PRIMARY KEY, owner TEXT NOT NULL, seq INTEGER NOT NULL, prev_submission_id TEXT,
    prev_recipe_digest TEXT, same_recipe INTEGER, graph_changed INTEGER, changed_knobs TEXT);
CREATE INDEX lineage_owner ON lineage(owner, seq);
"""


class BankRefused(RuntimeError):
    """A typed refusal before anything is written (``code`` is closed)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class BankReader:
    """The bank's ONLY way into the catalog: allow-listed tables and columns, read-only."""

    def __init__(self, catalog):
        path = Path(catalog)
        if not path.is_file():
            raise BankRefused("catalog_missing")
        self._db = sqlite3.connect(
            "file:" + str(path) + "?mode=ro", uri=True, timeout=5
        )
        self._db.execute("PRAGMA query_only=1")
        try:
            for table, expected in EXPECTED.items():
                have = {r[1] for r in self._db.execute(f"PRAGMA table_info({table})")}
                if have != expected:
                    raise BankRefused("catalog_schema_drift")
            meta = dict(self.rows("meta", ("k", "v")))
            if meta.get("schema") != CATALOG_SCHEMA:
                raise BankRefused("catalog_schema_unknown")
        except BaseException:
            self._db.close()
            raise

    def rows(self, table, columns, where=None, params=()):
        """``SELECT columns FROM table [WHERE where]``, only for allow-listed names."""
        if table not in ALLOWED:
            raise BankRefused("table_not_allowed")
        if not columns or any(c not in ALLOWED[table] for c in columns):
            raise BankRefused("column_not_allowed")
        sql = f"SELECT {','.join(columns)} FROM {table}"
        if where is not None:
            # only equality on allow-listed columns: ``where`` is a tuple of column names
            if any(c not in ALLOWED[table] for c in where):
                raise BankRefused("column_not_allowed")
            sql += " WHERE " + " AND ".join(f"{c}=?" for c in where)
        return self._db.execute(sql, params)

    def close(self):
        self._db.close()


def _owner_only_dir(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return False
    if os.name != "posix":
        return True
    return info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077


def _resolve(doc, challenge_id, version):
    """(parse_code, source_kind, graph_digest, settings, defaults) by the version's own adapter."""
    from carbon.development_session import graph_adapters
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )

    source = doc.get("source") if isinstance(doc, dict) else None
    kind = source.get("kind") if isinstance(source, dict) else None
    graph = source.get("submission_digest") if isinstance(source, dict) else None
    module = graph_adapters.module_for(challenge_id, version)
    if module is None:
        return "bank_adapter_unregistered", kind, graph, None, None
    try:
        settings = module.training_settings(ConstructionRecipe.from_dict(doc))
    except RecipeRefused as refused:
        return refused.code, kind, graph, None, None
    surfaces_for = getattr(module, "surfaces_for", None)
    surfaces = (
        {}
        if surfaces_for is None
        else surfaces_for(module.spec_for(challenge_id, version))
    )
    return None, kind, graph, settings, {name: row[2] for name, row in surfaces.items()}


def _shape(settings):
    """The recipe's comparable shape for lineage: ensemble layout + every member's resolved knobs."""
    return {
        "train_fraction": settings["train_fraction"],
        "output_weights": settings["output_weights"],
        "members": [(m["outputs"], m["weight"]) for m in settings["ensemble"]],
        "knobs": [m["training"] for m in settings["ensemble"]],
    }


def _changed(before, after):
    if before is None or after is None:
        return None
    names = set()
    for key in ("train_fraction", "output_weights", "members"):
        if before[key] != after[key]:
            names.add(key)
    for b, a in zip(before["knobs"], after["knobs"]):
        names.update(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return sorted(names)


def build(catalog, out_dir, challenge_id, version, *, resolve=None, now=time.time):
    """Build the bank file; returns counts. Reads ``catalog`` through ``BankReader`` only."""
    resolve = _resolve if resolve is None else resolve
    out_dir = Path(out_dir)
    if not out_dir.is_dir() or not _owner_only_dir(out_dir):
        raise BankRefused("out_dir_not_owner_only")
    if Path(catalog).resolve().parent == out_dir.resolve():
        raise BankRefused("out_dir_is_catalog_dir")
    reader = BankReader(catalog)
    counts = {
        "recipes": 0,
        "refused_by_adapter": {},
        "members": {},
        "nondefault_knobs": {},
    }
    tmp = out_dir / (BANK_NAME + ".tmp")
    if tmp.exists():
        tmp.unlink()
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    out = sqlite3.connect(tmp)
    try:
        out.executescript(DDL)
        out.executemany(
            "INSERT INTO meta VALUES(?,?)",
            [
                ("schema", SCHEMA),
                ("challenge_id", challenge_id),
                ("version", version),
                ("built_s", str(now())),
            ],
        )
        shapes, graphs = {}, {}
        for digest, first_seen, text in reader.rows(
            "recipes",
            ("recipe_digest", "first_seen_s", "recipe_json"),
            ("challenge_id", "version"),
            (challenge_id, version),
        ):
            try:
                doc = json.loads(text)
            except (ValueError, TypeError):
                doc = None
            code, kind, graph, settings, defaults = (
                ("bank_recipe_json_invalid", None, None, None, None)
                if doc is None
                else resolve(doc, challenge_id, version)
            )
            counts["recipes"] += 1
            graphs[digest] = graph
            if settings is None:
                counts["refused_by_adapter"][code] = (
                    counts["refused_by_adapter"].get(code, 0) + 1
                )
                out.execute(
                    "INSERT INTO recipe_features VALUES(?,?,?,?,?,?,?,?,?)",
                    (digest, code, kind, graph, None, None, None, None, first_seen),
                )
                continue
            members = settings["ensemble"]
            shapes[digest] = _shape(settings)
            n = str(len(members))
            counts["members"][n] = counts["members"].get(n, 0) + 1
            out.execute(
                "INSERT INTO recipe_features VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    digest,
                    None,
                    kind,
                    graph,
                    settings["train_fraction"],
                    len(members),
                    settings["batch_size"],
                    json.dumps(settings["output_weights"]),
                    first_seen,
                ),
            )
            seen = set()
            for index, member in enumerate(members):
                knobs = member["training"]
                nondefault = sorted(
                    k for k in knobs if k in defaults and knobs[k] != defaults[k]
                )
                seen.update(nondefault)
                out.execute(
                    "INSERT INTO member_knobs VALUES(?,?,?,?,?,?)",
                    (
                        digest,
                        index,
                        json.dumps(member["outputs"]),
                        member["weight"],
                        json.dumps(knobs, sort_keys=True),
                        json.dumps(nondefault),
                    ),
                )
            for name in seen:
                counts["nondefault_knobs"][name] = (
                    counts["nondefault_knobs"].get(name, 0) + 1
                )

        built = {r[0]: r[1:] for r in reader.rows("builds", ALLOWED["builds"])}
        subs = list(
            reader.rows(
                "submissions",
                (
                    "submission_id",
                    "owner",
                    "recipe_digest",
                    "admitted_ns",
                    "created_s",
                    "task_state",
                    "refusal_code",
                    "infra_class",
                    "failure_stage",
                    "rerun_of",
                    "copy_of",
                ),
                ("challenge_id", "version"),
                (challenge_id, version),
            )
        )
        for (
            sid,
            _owner,
            digest,
            _adm,
            _cre,
            state,
            refusal,
            infra,
            stage,
            rerun,
            copy,
        ) in subs:
            b = built.get(sid, (None,) * (len(ALLOWED["builds"]) - 1))
            out.execute(
                "INSERT INTO outcomes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, digest, state, refusal, infra, stage, rerun, copy, *b),
            )
        counts["outcomes"] = len(subs)
        counts["outcomes_with_build"] = sum(1 for s in subs if s[0] in built)

        by_owner = {}
        for row in subs:
            if row[1] is not None:
                by_owner.setdefault(row[1], []).append(row)
        chains = 0
        for owner, rows in by_owner.items():
            rows.sort(key=lambda r: (r[3] is None, r[3] or 0, r[4] or 0, r[0]))
            prev = None
            for seq, row in enumerate(rows):
                sid, digest = row[0], row[2]
                if prev is None:
                    out.execute(
                        "INSERT INTO lineage VALUES(?,?,?,?,?,?,?,?)",
                        (sid, owner, seq, None, None, None, None, None),
                    )
                else:
                    chains += 1
                    pd = prev[2]
                    changed = _changed(shapes.get(pd), shapes.get(digest))
                    g0, g1 = graphs.get(pd), graphs.get(digest)
                    out.execute(
                        "INSERT INTO lineage VALUES(?,?,?,?,?,?,?,?)",
                        (
                            sid,
                            owner,
                            seq,
                            prev[0],
                            pd,
                            int(pd == digest),
                            None if g0 is None or g1 is None else int(g0 != g1),
                            None if changed is None else json.dumps(changed),
                        ),
                    )
                prev = row
        counts["owners"] = len(by_owner)
        counts["lineage_edges"] = chains
        out.commit()
    except BaseException:
        out.close()
        reader.close()
        tmp.unlink(missing_ok=True)
        raise
    out.close()
    reader.close()
    os.replace(tmp, out_dir / BANK_NAME)
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--challenge-id", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        counts = build(args.catalog, args.out, args.challenge_id, args.version)
    except BankRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
