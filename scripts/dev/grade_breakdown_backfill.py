"""Backfill the private grade breakdown of every kept Motor 1.8 grade, labelled recomputed (data harvest plan G1 / S6).

Design receipted by Validator-2 (RECEIPTS 2026-11-20T11:26:59Z, "DESIGN Y with 5 changes"). Each kept grade on the
door (``<state>/auto-grade/artifacts/<task>.evaluation`` holding its ``dual-measurement.json``) is recomputed with the
receipted read-only tool's own path (`king_grade_breakdown.breakdown`: the door's grade path called unchanged, E1 key
only, aggregates only) from what the grade kept: ``<task>/predictions.json`` and the evaluation folder's
``menu-rowcheck-*.json``, ``single-call.json`` and ``subset-repeat-*.json``.

The recomputed A, D and total are compared with the grade's HISTORICAL values: A and D from its kept dual measurement
(``dual-measurement.json`` benchmark legs), the total from its kept ``private-evaluation-binding.json``
(``model_p.total_score``). ``TOLERANCE`` (5e-5) is a MATCH-LABEL tolerance only: it decides whether a file is written,
never a score; the actual ``|diff|`` of A, D and total is written into the file and counted in the report. A miss
writes nothing (``self_check_failed``). No status, score, ledger row, crown, ladder or existing file is ever changed
(invariant 10): the only file written per grade is a NEW write-once, owner-only
``<task>.evaluation/<task>.grade-breakdown.recomputed.json`` (never the live ``.grade-breakdown.json`` name) with the
provenance ``recomputed``, its label, the self-check numbers, the grade's own code revision
(``grade-installed-commit.json``) beside the tool's commit, and the sha256 of every kept input read.

Refused, by typed code, never guessed: ``live_breakdown_present`` (the grade wrote its own), ``recomputed_present``
(done: resumable), ``archived`` (an archived grade: until `grade_archive` is live and receipted), a missing kept file
(``predictions_missing`` / ``rowcheck_missing`` / ``single_call_missing`` / ``binding_missing`` /
``grade_revision_unrecorded``), ``version_not_supported`` (another Challenge version, or a grade whose producer digest
is not the tool's: never recomputed under other semantics), ``pack_differs`` (a grade under another evaluation pack /
epoch than the installed E1 one), and any typed refusal of the tool itself.

Hidden material (the sealed pack, the menu key) is read on the door host only, in process; nothing is copied out.
The run stops (resumable: a grade with a recomputed file is skipped next time) when the state filesystem has less
than ``--min-free-gb`` (10) free, or the 1-minute load is above ``--max-load`` (16). Dry run unless ``--apply``: the
dry run lists, per (version, evaluation pack), kept / to_compute / refused by code, for Validator-2's receipt.

    python -I scripts/dev/grade_breakdown_backfill.py --state STATE --private-root P --menu-key-file K \\
        --tool-commit SHA --report FILE [--copy-hotkey HK] [--apply]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.exam.grade-breakdown-recomputed.v1"
SUFFIX = ".grade-breakdown.recomputed.json"
LIVE_SUFFIX = ".grade-breakdown.json"
LABEL = "recomputed from the kept grade, self-check matched"
TOLERANCE = 5e-5
ARCHIVE_STUB = "ARCHIVED.json"


class Refused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(path, code):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Refused(code)
    return json.loads(path.read_bytes())


def _one(folder, pattern, code, required=True, exclude=None):
    """The ONE kept file matching ``pattern`` (``.json`` or, since H3a, ``.json.gz``), never a name starting with
    ``exclude`` (the row check's basis file also matches its side file's pattern)."""
    found = sorted(
        p
        for p in folder.glob(pattern)
        if p.is_file()
        and not p.is_symlink()
        and not (exclude and p.name.startswith(exclude))
    )
    if len(found) > 1 or (required and not found):
        raise Refused(code)
    return found[0] if found else None


def grades(state):
    """``[(task, evaluation folder, task folder)]`` of every kept grade (an evaluation folder with its dual
    measurement), oldest first."""
    artifacts = Path(state) / "auto-grade" / "artifacts"
    found = []
    for folder in artifacts.glob("rtsk_*.evaluation"):
        if folder.is_symlink() or not folder.is_dir():
            continue
        if (folder / "dual-measurement.json").is_file():
            task = folder.name.removesuffix(".evaluation")
            found.append((folder.stat().st_mtime, task, folder, artifacts / task))
    return [(task, folder, root) for _t, task, folder, root in sorted(found)]


def plan(task, folder, root, identity):
    """The kept inputs and historical values of one grade, or `Refused` with its typed code. ``identity``: the
    tool's ``{"challenge", "version", "pack_digest", "producer_digest"}``."""
    if (folder / (task + LIVE_SUFFIX)).exists():
        raise Refused("live_breakdown_present")
    if (folder / (task + SUFFIX)).exists():
        raise Refused("recomputed_present")
    if (folder / ARCHIVE_STUB).exists() or (root / ARCHIVE_STUB).exists():
        raise Refused("archived")
    binding = _json(folder / "private-evaluation-binding.json", "binding_missing")
    dual = _json(folder / "dual-measurement.json", "dual_measurement_missing")
    if (binding.get("challenge"), binding.get("challenge_version")) != (
        identity["challenge"],
        identity["version"],
    ) or dual.get("producer_digest") != identity["producer_digest"]:
        raise Refused("version_not_supported")
    if binding.get("evaluation_pack_digest") != identity["pack_digest"]:
        raise Refused("pack_differs")
    revision = _json(
        folder / "grade-installed-commit.json", "grade_revision_unrecorded"
    )
    predictions = root / "predictions.json"
    if predictions.is_symlink() or not predictions.is_file():
        raise Refused("predictions_missing")
    inputs = {
        "predictions": predictions,
        "rowcheck": _one(
            folder,
            "menu-rowcheck-*.json*",
            "rowcheck_missing",
            exclude="menu-rowcheck-basis-",
        ),
        "single_call": _one(folder, "single-call.json", "single_call_missing"),
        "pair": _one(folder, "subset-repeat-*.json*", "pair_ambiguous", required=False),
    }
    from carbon.scoring.physical_dual_pack import METRICS

    try:
        legs = dual["benchmark"]["models"][0]["measurements"]
        historical = {
            "A": float(legs[METRICS["A"]]["value"]),
            "D": float(legs[METRICS["D"]]["value"]),
            "total": float(binding["model_p"]["total_score"]),
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise Refused("historical_values_unavailable") from exc
    return {
        "inputs": inputs,
        "historical": historical,
        "revision": {k: revision.get(k) for k in ("commit", "tree", "dirty")},
    }


def _tool_identity(args):
    """The installed tool's Challenge, version, evaluation pack digest and producer digest (read on the door)."""
    import king_grade_breakdown as king

    from carbon.scoring import physical_dual_pack as physical

    development = king._arm()
    snapshot = king._snapshot(Path(args.private_root))
    return {
        "challenge": king.CHALLENGE,
        "version": king.VERSION,
        "pack_digest": snapshot.manifest_digest,
        "producer_digest": physical.producer_digest(development),
    }


def _recompute(args, task, inputs):
    """``(aggregates, breakdown)`` from the receipted tool's own path: its aggregates document (A, D, total) and the
    checked private grade breakdown of the same measure (`king_grade_breakdown.grade_breakdown_document`).
    """
    import king_grade_breakdown as king

    call = SimpleNamespace(
        private_root=args.private_root,
        menu_key_file=args.menu_key_file,
        copy_hotkey=args.copy_hotkey,
        predictions=str(inputs["predictions"]),
        rowcheck=str(inputs["rowcheck"]),
        single_call=str(inputs["single_call"]),
        pair=None if inputs["pair"] is None else str(inputs["pair"]),
        task=task,
        speed_lane=None,
    )
    keep = {}
    doc = king.breakdown(call, keep)
    return doc, king.grade_breakdown_document(call, keep)


def _document(args, task, item, doc, breakdown, diffs):
    return {
        "schema": SCHEMA,
        "provenance": "recomputed",
        "label": LABEL,
        "task": task,
        "breakdown": breakdown,
        "self_check": {
            "tolerance": TOLERANCE,
            **{
                name: {
                    "recomputed": doc[name],
                    "historical": item["historical"][name],
                    "abs_diff": diffs[name],
                }
                for name in ("A", "D", "total")
            },
        },
        "grade_revision": item["revision"],
        "tool_commit": args.tool_commit,
        "inputs": {
            name: (None if path is None else _sha256(path))
            for name, path in sorted(item["inputs"].items())
        },
        "recomputed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _write_once(path, document):
    raw = (
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            view = view[os.write(descriptor, view) :]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return len(raw)


def run(args, *, identity=None, recompute=_recompute, free=None, load=None):
    """The dry run or the writing run; returns the report document."""
    identity = identity or _tool_identity(args)
    free = free or (lambda: shutil.disk_usage(args.state).free)
    load = load or (lambda: os.getloadavg()[0])
    groups = collections.defaultdict(
        lambda: {
            "kept": 0,
            "to_compute": 0,
            "recomputed": 0,
            "self_check_failed": 0,
            "nonzero_diff": 0,
            "refused": collections.Counter(),
        }
    )
    report = {"apply": bool(args.apply), "stopped": None, "bytes_written": 0}
    for task, folder, root in grades(args.state):
        try:
            binding = json.loads(
                (folder / "private-evaluation-binding.json").read_bytes()
            )
            key = (
                str(binding.get("challenge_version")),
                str(binding.get("evaluation_pack_digest"))[:19],
            )
        except (OSError, ValueError):
            key = ("unknown", "unknown")
        group = groups[key]
        group["kept"] += 1
        try:
            item = plan(task, folder, root, identity)
        except (Refused, OSError, ValueError) as refused:
            group["refused"][
                getattr(refused, "code", None) or type(refused).__name__
            ] += 1
            continue
        group["to_compute"] += 1
        if not args.apply or report["stopped"]:
            continue
        if free() < args.min_free_gb * 1024**3:
            report["stopped"] = "disk_below_min_free"
            continue
        if load() > args.max_load:
            report["stopped"] = "load_above_max"
            continue
        try:
            doc, breakdown = recompute(args, task, item["inputs"])
        except Exception as exc:  # noqa: BLE001 - a typed code only, never a message
            code = getattr(exc, "code", None)
            group["refused"][code if type(code) is str else type(exc).__name__] += 1
            continue
        diffs = {
            name: abs(float(doc[name]) - item["historical"][name])
            for name in ("A", "D", "total")
        }
        if any(diffs.values()):
            group["nonzero_diff"] += 1
        if max(diffs.values()) > TOLERANCE:
            group["self_check_failed"] += 1
            continue
        try:
            document = _document(args, task, item, doc, breakdown, diffs)
            report["bytes_written"] += _write_once(folder / (task + SUFFIX), document)
        except FileExistsError:
            group["refused"]["recomputed_present"] += 1
            continue
        except (OSError, ValueError, TypeError) as exc:
            group["refused"]["write_" + type(exc).__name__] += 1
            continue
        group["recomputed"] += 1
    report["groups"] = [
        {
            "version": version,
            "evaluation_pack": pack,
            **{k: v for k, v in counts.items() if k != "refused"},
            "refused": dict(sorted(counts["refused"].items())),
        }
        for (version, pack), counts in sorted(groups.items())
    ]
    return report


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--state", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--menu-key-file", required=True)
    parser.add_argument("--copy-hotkey", default=None)
    parser.add_argument("--tool-commit", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--min-free-gb", type=float, default=10.0)
    parser.add_argument("--max-load", type=float, default=16.0)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    for path in (str(ROOT), str(ROOT / "scripts" / "dev")):
        if path not in sys.path:
            sys.path.insert(0, path)
    report = run(args)
    raw = (json.dumps(report, sort_keys=True, indent=1) + "\n").encode()
    descriptor = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
    print(
        json.dumps(
            {
                "apply": report["apply"],
                "stopped": report["stopped"],
                "bytes_written": report["bytes_written"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
