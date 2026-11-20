"""Carbon Evidence Catalog v0 (CEC): one row per submission joining recipe -> build -> grade -> per-case -> crown.

Data harvest plan 20 Nov 2026 section 4.2 (owner G-LEAD-6; priorities P2-17 catalog, P2-20 bank P1 corpus). An
INDEXER, never part of the door: it reads the receiver's stores READ-ONLY (sqlite ``?mode=ro`` + ``PRAGMA query_only``,
plain file reads), takes no door lock and calls no door API, and writes ONE new owner-only SQLite file outside the
receiver state, built in a temporary file and swapped in atomically. Run it on the door host at idle priority:

  nice -n 19 ionice -c 3 <live checkout>/.venv/bin/python -I scripts/dev/evidence_catalog.py \
      --state <receiver state root> --out <owner-only dir outside it> --owner-key <owner-only key file> \
      [--pool-store <pool store>]

Class C as a whole (V2 BANK contract, 20 Nov 11:42:03Z; COLD_STORAGE_RULING_20261120): it stays on the door host or goes
INTO custody2 only, never to the PC, a post or a client file. Inside it, every column names its contract row; hidden-
derived tables (grades, markers, gate failures, crown, per-case objects) are kept apart from the PUBLIC-SIGNAL ones
(recipes, builds) so the bank's reader can allow-list tables, not guess columns.

What it never copies:
- an owner's hotkey: owners appear only as an HMAC-SHA256 pseudonym under a key file on the host (contract row 11);
- the body of a build's worker evidence: only NAMED compute and fit fields (V2 R5), never ``predictions_raw_base64``;
- an infrastructure diagnosis's tail or traceback: only its failed stage and reason code;
- per-case predictions or errors: per-case evidence is listed as files (path, bytes), never read;
- a pool model's state blob, a score record or a crown event body.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import hmac
import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path

SCHEMA = "carbon.evidence-catalog.v0"
CATALOG_NAME = "cec-v0.sqlite3"
#: The deepest a per-case evidence folder is walked, and the most object rows kept per submission.
OBJECT_DEPTH = 4
OBJECTS_PER_SUBMISSION = 400

DDL = """
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
-- PUBLIC-SIGNAL (contract rows 1-3; class B: never published, never off-host unencrypted)
CREATE TABLE recipes(
    recipe_digest TEXT PRIMARY KEY, challenge_id TEXT, version TEXT, first_seen_s REAL, bytes INTEGER,
    recipe_json TEXT NOT NULL);
-- PUBLIC-SIGNAL closed fields (contract rows 2, 4, 9, 10, 11 pseudonym, 21 lineage)
CREATE TABLE submissions(
    submission_id TEXT PRIMARY KEY, challenge_id TEXT, version TEXT, owner TEXT, recipe_digest TEXT,
    request_sha256 TEXT, admitted_ns INTEGER, created_s REAL, updated_s REAL, completed_s REAL, task_state TEXT,
    refusal_code TEXT, infra_class TEXT, failure_stage TEXT, failure_reason TEXT, cancel_kind TEXT, rerun_of TEXT,
    copy_of TEXT);
-- PUBLIC-SIGNAL named fields only (contract rows 5-8; V2 R5): never the evidence body
CREATE TABLE builds(
    submission_id TEXT PRIMARY KEY, state_digest TEXT, practice_predictions_digest TEXT,
    practice_inputs_digest TEXT, build_device TEXT, build_image_id TEXT, inference_image_id TEXT, train_loss REAL,
    member_losses TEXT, members TEXT, steps INTEGER, train_cases INTEGER, trainer_sha256 TEXT, params_sha256 TEXT,
    per_call_s REAL, timing_s TEXT);
-- HIDDEN-DERIVED (contract rows 13-19): never a learning input
CREATE TABLE grades(
    submission_id TEXT NOT NULL, exam_key TEXT NOT NULL, kind TEXT, state TEXT, status TEXT, epoch INTEGER,
    reserved_ns INTEGER, settled_ns INTEGER, cpu_seconds REAL, lane_seconds REAL,
    PRIMARY KEY(submission_id, exam_key));
CREATE TABLE markers(submission_id TEXT PRIMARY KEY, state TEXT, code TEXT, next_step TEXT, pass TEXT);
CREATE TABLE gate_failures(submission_id TEXT NOT NULL, exam_key TEXT NOT NULL, failures TEXT NOT NULL,
    PRIMARY KEY(submission_id, exam_key));
CREATE TABLE requeues(submission_id TEXT PRIMARY KEY, attempt INTEGER, queued_ns INTEGER);
CREATE TABLE pool_models(model_id TEXT PRIMARY KEY, recipe_digest TEXT, state_digest TEXT);
CREATE TABLE crown_finals(final_id TEXT PRIMARY KEY, challenger TEXT, incumbent TEXT, finalist TEXT, state TEXT,
    outcome TEXT);
CREATE TABLE crown_incumbent(model_id TEXT PRIMARY KEY, reason TEXT, since REAL);
CREATE TABLE crown_events(sequence INTEGER PRIMARY KEY, at REAL, kind TEXT);
-- per-case evidence as FILES only (contract row 17): never read
CREATE TABLE objects(submission_id TEXT NOT NULL, relpath TEXT NOT NULL, bytes INTEGER, mtime REAL,
    PRIMARY KEY(submission_id, relpath));
CREATE INDEX submissions_recipe ON submissions(recipe_digest);
CREATE INDEX grades_submission ON grades(submission_id);
"""

#: Contract row 5-8 named fields of a build's worker evidence (V2 R5: never the body), as key paths.
BUILD_FIELDS = {
    "state_digest": ("state_digest",),
    "practice_predictions_digest": ("inference_receipt", "predictions_digest"),
    "practice_inputs_digest": ("inference_receipt", "inputs_digest"),
    "build_device": ("build_device",),
    "build_image_id": ("build_image_id",),
    "inference_image_id": ("inference_image_id",),
    "train_loss": ("build_receipt", "fit", "train_loss"),
    "member_losses": ("build_receipt", "fit", "member_losses"),
    "members": ("build_receipt", "fit", "members"),
    "steps": ("build_receipt", "fit", "steps"),
    "train_cases": ("build_receipt", "fit", "train_cases"),
    "trainer_sha256": ("build_receipt", "fit", "trainer_sha256"),
    "params_sha256": ("build_receipt", "fit", "params_sha256"),
    "per_call_s": ("timed_receipt", "measurement", "per_call_s"),
    "timing_s": ("timed_receipt", "measurement", "timing_s"),
}


class CatalogRefused(RuntimeError):
    """A typed refusal before anything is written (``code`` is closed)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _ro(path):
    db = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=5)
    db.execute("PRAGMA query_only=1")
    return db


def _tables(db):
    return {
        r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _owner_only(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return False
    if os.name != "posix":
        return True
    return info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077


def _field(doc, path):
    for key in path:
        if not isinstance(doc, dict) or key not in doc:
            return None
        doc = doc[key]
    if isinstance(doc, bool):
        return None
    if isinstance(doc, (int, float, str)):
        return doc
    if isinstance(doc, (list, dict)):
        text = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        # a list or map of numbers / short names only (losses, member names, stage timings): never a payload
        return text if len(text) <= 65536 else None
    return None


def _default_decoders():
    from carbon.research import DirectTaskViewV3, load_canonical
    from carbon.research.model import DirectStartTaskRequestV3

    def view(raw):
        v = load_canonical(bytes(raw), DirectTaskViewV3)
        r = v.terminal_receipt
        infra = None if r is None else r.infrastructure_failure_class
        return {
            "challenge_id": v.challenge_key.challenge_id,
            "version": v.challenge_key.version,
            "state": v.state.value,
            "created_s": v.created_at_micros / 1e6,
            "updated_s": v.updated_at_micros / 1e6,
            "recipe_digest": v.immutable_bindings.recipe_digest,
            "refusal_code": None if r is None else r.refusal_code,
            "infra_class": (
                None if infra is None else getattr(infra, "value", str(infra))
            ),
            "completed_s": None if r is None else r.completed_at_micros / 1e6,
        }

    def recipe(raw):
        return load_canonical(bytes(raw), DirectStartTaskRequestV3).recipe

    return view, recipe


def build(
    state_root, out_dir, owner_key, *, pool_store=None, decoders=None, now=time.time
):
    """Build the catalog; returns its row counts. Reads ``state_root`` only; writes ``out_dir``/`CATALOG_NAME`."""
    state_root, out_dir, owner_key = Path(state_root), Path(out_dir), Path(owner_key)
    if not (state_root / "attempts.sqlite3").is_file():
        raise CatalogRefused("catalog_state_root_invalid")
    if not out_dir.is_dir() or not _owner_only(out_dir):
        raise CatalogRefused("catalog_out_not_owner_only")
    resolved = out_dir.resolve()
    if resolved == state_root.resolve() or state_root.resolve() in resolved.parents:
        raise CatalogRefused("catalog_out_inside_state")
    if not owner_key.is_file() or not _owner_only(owner_key):
        raise CatalogRefused("catalog_owner_key_not_owner_only")
    key = owner_key.read_bytes()
    if len(key) < 32:
        raise CatalogRefused("catalog_owner_key_short")
    decode_view, decode_recipe = decoders or _default_decoders()

    def pseudonym(hotkey):
        if not hotkey:
            return None
        return "o:" + hmac.new(key, hotkey.encode(), hashlib.sha256).hexdigest()[:32]

    tmp = out_dir / f".{CATALOG_NAME}.{os.getpid()}.tmp"
    if tmp.exists():
        tmp.unlink()
    out = sqlite3.connect(str(tmp))
    try:
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        out.executescript(DDL)
        counts = _fill(
            out, state_root, pool_store, decode_view, decode_recipe, pseudonym
        )
        out.executemany(
            "INSERT INTO meta VALUES(?,?)",
            [
                ("schema", SCHEMA),
                ("built_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now()))),
                ("class", "C (whole file): door host or custody2 only"),
                ("counts", json.dumps(counts, sort_keys=True)),
            ],
        )
        out.commit()
    except BaseException:
        out.close()
        tmp.unlink(missing_ok=True)
        raise
    out.close()
    final = out_dir / CATALOG_NAME
    os.replace(tmp, final)
    return counts


def _fill(out, root, pool_store, decode_view, decode_recipe, pseudonym):
    subs = {}

    def sub(sid):
        return subs.setdefault(sid, {"submission_id": sid})

    counts = {}
    # ---- the receiver ledger: intake, intents, copies, grades, gate failures, requeues --------------------------
    db = _ro(root / "attempts.sqlite3")
    try:
        have = _tables(db)
        if "attempts" in have:
            for sid, hotkey, at in db.execute(
                "SELECT submission_id, MIN(hotkey), MIN(at_ns) FROM attempts WHERE kind='OUTCOME' "
                "AND submission_id IS NOT NULL GROUP BY submission_id"
            ):
                row = sub(sid)
                row["owner"], row["admitted_ns"] = pseudonym(hotkey), at
        if "recipe_task_intents" in have:
            for sid, hotkey, request in db.execute(
                "SELECT submission_id, hotkey, request_sha256 FROM recipe_task_intents"
            ):
                row = sub(sid)
                row.setdefault("owner", pseudonym(hotkey))
                row["request_sha256"] = request
        if "recipe_copy_digests" in have:
            for sid, digest in db.execute(
                "SELECT submission_id, recipe_digest FROM recipe_copy_digests"
            ):
                sub(sid).setdefault("recipe_digest", digest)
        if "recipe_copies" in have:
            for sid, first in db.execute(
                "SELECT submission_id, first_id FROM recipe_copies"
            ):
                sub(sid)["copy_of"] = first
        if "exam_graded" in have:
            out.executemany(
                "INSERT OR REPLACE INTO grades VALUES(?,?,?,?,?,?,?,?,?,?)",
                db.execute(
                    "SELECT submission_id, exam_key, kind, state, status, epoch, reserved_ns, settled_ns, "
                    "cpu_seconds, lane_seconds FROM exam_graded"
                ),
            )
        if "gate_failures_v1" in have:
            out.executemany(
                "INSERT OR REPLACE INTO gate_failures VALUES(?,?,?)",
                db.execute(
                    "SELECT submission_id, exam_key, failures FROM gate_failures_v1"
                ),
            )
        if "exam_requeues" in have:
            out.executemany(
                "INSERT OR REPLACE INTO requeues VALUES(?,?,?)",
                db.execute(
                    "SELECT submission_id, attempt, queued_ns FROM exam_requeues"
                ),
            )
    finally:
        db.close()

    # ---- owners: task records, recipes, named build fields, infra diagnosis (stage + code) ----------------------
    recipes = {}
    builds = 0
    for path in sorted(
        glob.glob(str(root / "owners" / "*" / "tasks" / "direct-tasks.sqlite3"))
    ):
        try:
            db = _ro(path)
        except sqlite3.Error:
            continue
        try:
            have = _tables(db)
            for sid, request, view, cancellation in db.execute(
                "SELECT id, request, view, cancellation FROM direct_tasks"
            ):
                row = sub(sid)
                try:
                    v = decode_view(view)
                # an undecodable record is counted, never guessed (a canonical refusal is a ValueError)
                except (ValueError, TypeError, KeyError, AttributeError):
                    counts["undecoded_views"] = counts.get("undecoded_views", 0) + 1
                    continue
                row.update(
                    challenge_id=v["challenge_id"],
                    version=v["version"],
                    task_state=v["state"],
                    created_s=v["created_s"],
                    updated_s=v["updated_s"],
                    completed_s=v["completed_s"],
                    refusal_code=v["refusal_code"],
                    infra_class=v["infra_class"],
                )
                row["recipe_digest"] = v["recipe_digest"] or row.get("recipe_digest")
                if cancellation:
                    row["cancel_kind"] = (
                        cancellation.split("rtsk_", 1)[0][:40] or "other"
                    )
                digest = row["recipe_digest"]
                if digest and digest not in recipes:
                    try:
                        text = json.dumps(
                            decode_recipe(request),
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    except (ValueError, TypeError, KeyError, AttributeError):
                        counts["undecoded_recipes"] = (
                            counts.get("undecoded_recipes", 0) + 1
                        )
                    else:
                        recipes[digest] = (
                            digest,
                            v["challenge_id"],
                            v["version"],
                            v["created_s"],
                            len(text.encode()),
                            text,
                        )
                elif digest in recipes and v["created_s"] < recipes[digest][3]:
                    recipes[digest] = (
                        recipes[digest][:3] + (v["created_s"],) + recipes[digest][4:]
                    )
            if "direct_evidence" in have:
                # one row at a time (a body can be ~24 MB with its predictions): only the NAMED fields leave it
                for sid, body in db.execute("SELECT id, body FROM direct_evidence"):
                    try:
                        doc = json.loads(body)
                    except (ValueError, TypeError):
                        continue
                    del body
                    if not isinstance(doc, dict):
                        continue
                    values = [_field(doc, p) for p in BUILD_FIELDS.values()]
                    del doc
                    if all(x is None for x in values):
                        continue
                    out.execute(
                        f"INSERT OR REPLACE INTO builds VALUES(?{',?' * len(BUILD_FIELDS)})",
                        [sid, *values],
                    )
                    builds += 1
            if "direct_infra_diagnosis" in have:
                for sid, body in db.execute(
                    "SELECT id, body FROM direct_infra_diagnosis"
                ):
                    try:
                        doc = json.loads(body)
                    except (ValueError, TypeError):
                        continue
                    row = sub(sid)
                    for name, key in (
                        ("failure_stage", "failed_stage"),
                        ("failure_reason", "reason_code"),
                    ):
                        value = doc.get(key) if isinstance(doc, dict) else None
                        row[name] = value[:96] if isinstance(value, str) else None
        finally:
            db.close()
    out.executemany("INSERT INTO recipes VALUES(?,?,?,?,?,?)", recipes.values())

    # ---- door re-runs (lineage of a failed chain), markers -------------------------------------------------------
    try:
        with open(
            root / "auto-grade" / "requeued" / "build-retries.jsonl",
            encoding="utf-8",
            errors="replace",
        ) as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict) and isinstance(d.get("new_task"), str):
                    sub(d["new_task"])["rerun_of"] = d.get("from_task")
    except OSError:
        pass
    markers = []
    for path in glob.glob(str(root / "auto-grade" / "markers" / "rtsk_*.json")):
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            markers.append(
                (
                    Path(path).stem,
                    d.get("state"),
                    d.get("code"),
                    d.get("next_step"),
                    d.get("pass"),
                )
            )
    out.executemany("INSERT OR REPLACE INTO markers VALUES(?,?,?,?,?)", markers)

    # ---- per-case evidence, as files only --------------------------------------------------------------------------
    objects = 0
    artifacts = root / "auto-grade" / "artifacts"
    if artifacts.is_dir():
        for entry in sorted(os.scandir(artifacts), key=lambda e: e.name):
            if not entry.name.startswith("rtsk_") or entry.is_symlink():
                continue
            sid = entry.name.split(".", 1)[0]
            rows = []
            stack = [(Path(entry.path), 0)]
            while stack and len(rows) < OBJECTS_PER_SUBMISSION:
                path, depth = stack.pop()
                if path.is_symlink():
                    continue
                if path.is_dir():
                    if depth < OBJECT_DEPTH:
                        stack.extend((p, depth + 1) for p in sorted(path.iterdir()))
                    continue
                info = path.stat()
                rows.append(
                    (
                        sid,
                        str(path.relative_to(root)).replace(os.sep, "/"),
                        info.st_size,
                        info.st_mtime,
                    )
                )
            out.executemany("INSERT OR REPLACE INTO objects VALUES(?,?,?,?)", rows)
            objects += len(rows)

    # ---- crown (pool store): models without their state, finals, incumbent, event kinds -------------------------
    if pool_store is not None and Path(pool_store).is_file():
        db = _ro(pool_store)
        try:
            have = _tables(db)
            if "models" in have:
                out.executemany(
                    "INSERT OR REPLACE INTO pool_models VALUES(?,?,?)",
                    db.execute(
                        "SELECT model_id, recipe_digest, state_digest FROM models"
                    ),
                )
            if "finals" in have:
                out.executemany(
                    "INSERT OR REPLACE INTO crown_finals VALUES(?,?,?,?,?,?)",
                    db.execute(
                        "SELECT final_id, challenger, incumbent, finalist, state, outcome FROM finals"
                    ),
                )
            if "incumbent" in have:
                out.executemany(
                    "INSERT OR REPLACE INTO crown_incumbent VALUES(?,?,?)",
                    db.execute("SELECT model_id, reason, since FROM incumbent"),
                )
            if "events" in have:
                out.executemany(
                    "INSERT OR REPLACE INTO crown_events VALUES(?,?,?)",
                    db.execute("SELECT sequence, at, kind FROM events"),
                )
        finally:
            db.close()

    columns = [
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
    ]
    out.executemany(
        f"INSERT INTO submissions VALUES({','.join('?' * len(columns))})",
        ([row.get(c) for c in columns] for row in subs.values()),
    )
    counts.update(
        submissions=len(subs),
        recipes=len(recipes),
        builds=builds,
        markers=len(markers),
        objects=objects,
    )
    for table in (
        "grades",
        "gate_failures",
        "requeues",
        "pool_models",
        "crown_finals",
        "crown_events",
    ):
        counts[table] = out.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def _pool_store_of(state_root):
    for candidate in (
        state_root / "receiver.json",
        state_root.parent / "receiver.json",
        state_root.parent.parent / "receiver.json",
    ):
        if candidate.is_file():
            try:
                cfg = json.loads(candidate.read_text(encoding="utf-8"))
            except ValueError:
                return None
            return ((cfg.get("auto_grade") or {}) if isinstance(cfg, dict) else {}).get(
                "pool_store"
            )
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--state", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--owner-key", required=True)
    parser.add_argument("--pool-store")
    args = parser.parse_args(argv)
    try:
        os.nice(19)
    except (AttributeError, OSError):
        pass
    state = Path(args.state)
    try:
        counts = build(
            state,
            args.out,
            args.owner_key,
            pool_store=args.pool_store or _pool_store_of(state),
        )
    except CatalogRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(
        json.dumps({"schema": SCHEMA, "counts": counts}, sort_keys=True)
    )  # counts only, never a value
    return 0


if __name__ == "__main__":
    sys.exit(main())
