#!/usr/bin/env python3
"""Why a RETAINED graph model has the design value D it has: the receiver's OWN retained-entry regrade, parts recorded.

`design_value_parts_regrade` packages a retained BUNDLE model into the recal's artifact form. A graph model has no such
form: it is re-inferred and graded by the receiver itself (`lean_recipe_retention.regrade_retained_entry`, the grade the
crown repeat uses) from the task's `recipe.json`, `state.npz`, receipts and timed query under ``artifacts/<id>``. THIS tool
runs that same regrade in this process with `design_value_parts.recording()` around it and prints the same per-target
scalars. Bundle entries regrade through the same path.

    python -m scripts.dev.design_value_parts_regrade_graph --config RECEIVER.json --entry sha256:<entry id>
        --artifact-directory ARTIFACTS --entry-directory ENTRIES --work SCRATCH --stored STORED.json
        [--challenge ID --version V --agen-scale-sets SETS.json] [--no-pick-values] [--in-place] [--json]

- The receiver must be STOPPED (its serve unit holds the receiver state lock, as for ``--regrade-entry``).
- The regrade is the receiver's uncounted REGRADE: no pool store is given, so nothing is filed for the Ladder, KOTH or the
  pool. By default the entry's task files (origin task directory, roles, custody and the entry) are COPIED under ``--work``
  and the regrade writes there, so the receiver's ``artifacts/`` and ``entries/`` are not changed (``--in-place`` runs on
  them as ``--regrade-entry`` does). The receiver's own ledger and snapshot files are used as the regrade uses them.
- ``--stored`` names what the receiver recorded for the entry (``{"A": x, "D": y}`` or one document with one ``legs``
  object with ``A`` and ``D``, e.g. the entry's original evaluation binding). The tool exits 0 ONLY when the regraded A and D
  (the legs of the regrade's own bound evaluation) EQUAL the stored legs bit for bit and the recomputed D equals the grader's
  D. Otherwise it prints what differs and exits 1; an input it cannot use, or a regrade the receiver refuses, exits 2.
- Per target it prints q, e, d, feasible and, unless ``--no-pick-values``, the model's PREDICTED and the TRUE value of each
  output at the final pick (named scalars only: no design, no row, no input). ``--agen-scale-sets`` (a recorder
  `agen-sets-<kind>-<version>.json`) adds the exam's A at each stricter A_gen scale set.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from scripts.dev import design_value_parts as parts_tool
from scripts.dev.design_value_parts_regrade import (
    RegradeError,
    _read,
    _same_path,
    load_agen_sets,
    stored_legs,
)


def origin_of(entry_directory, entry_id):
    """``(entry file, origin task id)`` of a retained bank entry, from the entry's own custody receipt name."""
    import re

    if type(entry_id) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", entry_id):
        raise RegradeError("--entry is not a sha256:<64 hex> entry id")
    path = Path(entry_directory) / (entry_id.removeprefix("sha256:") + ".json")
    try:
        entry = json.loads(_read(path))
        name = entry["custody_receipt"]["file"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RegradeError("the entry file is not readable") from exc
    found = re.fullmatch(r"(rtsk_[0-9a-f]{64})\.custody\.json", str(name))
    if found is None:
        raise RegradeError("the entry names no origin task")
    return path, found.group(1)


def isolate(artifact_directory, entry_directory, entry_id, work):
    """Copy the one entry's task files under ``work``; return ``(artifacts, entries)`` of the copies.

    Copied: the origin task directory, its ``.roles.json`` and ``.custody.json``, and the entry file. A regrade writes its
    new task and entry beside these, so the receiver's own directories are not touched.
    """
    artifact_directory, entry_directory, work = (
        Path(artifact_directory),
        Path(entry_directory),
        Path(work),
    )
    for parent in (artifact_directory, entry_directory):
        if _same_path(work, parent):
            raise RegradeError("--work must not be inside the receiver's directories")
    entry_file, origin = origin_of(entry_directory, entry_id)
    artifacts, entries = work / "artifacts", work / "entries"
    if artifacts.exists() or entries.exists():
        raise RegradeError("--work already holds a copy: use a fresh --work")
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifacts.mkdir(mode=0o700)
    entries.mkdir(mode=0o700)
    source = artifact_directory / origin
    if source.is_symlink() or not source.is_dir():
        raise RegradeError("the origin task directory is missing")
    shutil.copytree(source, artifacts / origin, symlinks=False)
    for suffix in (".roles.json", ".custody.json"):
        shutil.copy2(
            artifact_directory / (origin + suffix), artifacts / (origin + suffix)
        )
    shutil.copy2(entry_file, entries / entry_file.name)
    return artifacts, entries


def _run_receiver(config, entry_id, artifacts, entries):
    from carbon.challenge_validator import direct_receiver

    return direct_receiver.serve(
        Path(config),
        stop=threading.Event(),
        ready=lambda _item: None,
        retention=(entry_id, artifacts, entries),
        regrade=True,
    )


def regrade(
    config,
    entry_id,
    *,
    artifact_directory,
    entry_directory,
    work,
    stored,
    agen_scale_sets=None,
    pick_values=True,
    in_place=False,
    serve=None,
    challenge=None,
    version=None,
):
    """Regrade the retained entry through the receiver's own path, recorded; the report dict.

    ``serve(config, entry_id, artifacts, entries)`` replaces the receiver in tests. ``report["ok"]`` is true only when the
    regraded A and D equal ``stored`` exactly and the recomputed D equals the grader's D.
    """
    if in_place:
        artifacts, entries = Path(artifact_directory), Path(entry_directory)
    else:
        artifacts, entries = isolate(
            artifact_directory, entry_directory, entry_id, work
        )
    run = serve or _run_receiver
    with parts_tool.recording(agen_scale_sets, pick_values=pick_values) as recorder:
        result = run(config, entry_id, artifacts, entries)
    state = result.get("private_evaluation_state")
    if state != "BOUND_DEVELOPMENT_ONLY":
        raise RegradeError(
            "the receiver's regrade bound no evaluation: "
            + str(result.get("private_evaluation_reason", state))
        )
    try:
        binding = json.loads(_read(result["private_evaluation_path"]))
    except (KeyError, OSError, ValueError, RegradeError) as exc:
        raise RegradeError("the regrade's bound evaluation is unreadable") from exc
    regraded_a, regraded_d = stored_legs(binding)
    stored_a, stored_d = stored
    report = {
        "graded_under": (
            None if challenge is None else {"challenge": challenge, "version": version}
        ),
        "stored_a": stored_a,
        "stored_d": stored_d,
        "regraded_a": regraded_a,
        "regraded_d": regraded_d,
        "sets": [],
        "binding_d": [],
        "gated": False,
    }
    if recorder.sets:
        report["sets"] = parts_tool.parts(recorder)
        report["recomputed_d"] = parts_tool.recomputed_d(report["sets"])
        d_ok = stored_d == regraded_d == report["recomputed_d"]
    else:
        # a gated model has no pool grade: its D is the 0.0 the grader gave it
        report["gated"] = True
        report["recomputed_d"] = regraded_d
        d_ok = stored_d == regraded_d == 0.0
    report["ok"] = bool(d_ok and stored_a == regraded_a)
    if agen_scale_sets and recorder.sets:
        report["agen_sweep"] = parts_tool.agen_sweep(recorder, agen_scale_sets)
    return report


def render(report):
    lines = parts_tool.render(
        {
            "sets": report["sets"],
            "gated": report["gated"],
            "stored_d": report["stored_d"],
            "recomputed_d": report["recomputed_d"],
            "binding_d": [],
            "ok": report["ok"],
        }
    ).splitlines()
    graded = report.get("graded_under")
    if graded:
        lines.insert(-1, f"graded under = {graded['challenge']} {graded['version']}")
    lines.insert(-1, f"stored A     = {report['stored_a']!r}")
    lines.insert(-1, f"regraded A   = {report['regraded_a']!r}")
    lines.insert(-1, f"regraded D   = {report['regraded_d']!r}")
    for row in report.get("agen_sweep", []):
        lines.insert(-1, f"A at A_gen scales {row['scales']!r} = {row['A']!r}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--entry", required=True)
    parser.add_argument("--artifact-directory", required=True, type=Path)
    parser.add_argument("--entry-directory", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--stored", required=True, type=Path)
    parser.add_argument("--challenge")
    parser.add_argument("--version")
    parser.add_argument(
        "--agen-scale-sets",
        type=Path,
        help="the agen-sets-<kind>-<version>.json the recorder wrote; needs --challenge and --version, which it must match",
    )
    parser.add_argument("--no-pick-values", action="store_true")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    from carbon.challenge_validator import cpu_pin

    try:
        cpu_pin.require()  # the regrade scores on the same pinned kernels as the receiver
    except cpu_pin.CpuPinRefused as refused:
        print(f"REFUSED: {refused}", file=sys.stderr)
        return 2
    try:
        if args.agen_scale_sets is not None and (
            args.challenge is None or args.version is None
        ):
            raise RegradeError("--agen-scale-sets needs --challenge and --version")
        sets = (
            None
            if args.agen_scale_sets is None
            else load_agen_sets(args.agen_scale_sets, args.challenge, args.version)
        )
        report = regrade(
            args.config,
            args.entry,
            artifact_directory=args.artifact_directory,
            entry_directory=args.entry_directory,
            work=args.work,
            stored=stored_legs(json.loads(_read(args.stored))),
            agen_scale_sets=sets,
            pick_values=not args.no_pick_values,
            in_place=args.in_place,
            challenge=args.challenge,
            version=args.version,
        )
    except (RegradeError, parts_tool.PartsError) as refused:
        print(f"REFUSED: {type(refused).__name__}: {refused}", file=sys.stderr)
        return 2
    except Exception as failure:  # noqa: BLE001
        # the receiver's typed unavailable codes; never its private text
        code = getattr(failure, "code", None) or str(failure)
        print(f"REFUSED: {type(failure).__name__}: {code}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            parts_tool._jsonable(report), indent=2, sort_keys=True, allow_nan=False
        )
        if args.json
        else render(report)
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
