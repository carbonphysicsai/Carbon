#!/usr/bin/env python3
"""Why a RETAINED entry has the design value D it has: re-grade it with the recal's grade path, with the parts recorded.

A receiver keeps only ``artifacts/<id>/`` (the task's recipe, built state and receipts), its custody, roles and the
evaluation-pack binding; it does not keep the grade's transient inputs (trusted job, references, source receipt,
dual-measurement). So `design_value_parts` cannot be run on a live entry. THIS tool re-grades the retained model exactly
as the recalibrations do (`calibration_grade_run.run`: the judge pack, the host's judge image, the same inference worker
and measure) with `design_value_parts.recording()` around it, and prints the same per-target scalars.

    python -m scripts.dev.design_value_parts_regrade --retained ARTIFACTS/<id> --pack PACK_DIR --challenge ID
        --version V --judge-image JUDGE.json --work SCRATCH --stored STORED.json [--copy-hotkey HOTKEY] [--json]
        [--fake]

- ``--retained`` is read, never written (it must not contain ``--work``). Its ``recipe.json``, ``state.npz`` and
  ``image.json`` become a calibration artifact under ``--work`` (the recal's own artifact form), pinned to the retained
  state's digest. The receiver's ledger, custody and pool store are not opened.
- ``--stored`` names what the receiver recorded for the entry: a JSON file holding ``{"A": x, "D": y}`` or any document that
  carries one ``legs`` object with ``A`` and ``D`` (the evaluation's ``model_p``/binding). The tool exits 0 ONLY when the
  re-graded A and D EQUAL the stored legs bit for bit (no tolerance) and the recomputed D equals the grader's D. Otherwise it
  prints what differs and exits 1; an input it cannot use exits 2.
- Nothing but scalars is printed: no inputs, truth, designs, picks or rows. ``--fake`` replaces only the container run (a
  rehearsal with stand-in predictions, never a verdict on a model).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from scripts.dev import design_value_parts as parts_tool

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_RETAINED_FILES = ("recipe.json", "state.npz", "image.json")


class RegradeError(ValueError):
    """An input this tool cannot use (never a candidate's score)."""


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RegradeError(f"{path.name}: not a regular file")
    return path.read_bytes()


def read_retained(directory):
    """The retained task's recipe, state and image record, read-only. Refuses a missing or odd file."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise RegradeError("--retained is not a directory")
    return {name: _read(directory / name) for name in _RETAINED_FILES}


def _digest(value, label):
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise RegradeError(f"image.json: {label} is not a full sha256 digest")
    return value


def identities(files):
    """``(recipe, bundle_ref, worker_image_digest, parent_image_digest)`` of a retained bundle model, from its own files:
    a GPU overlay names its tree digest, a CPU library child its image id (as the recal's packaging does)."""
    try:
        recipe = json.loads(files["recipe.json"])
        image = json.loads(files["image.json"])
        source = recipe["source"]
        bundle_ref = source["bundle_ref"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RegradeError("recipe.json / image.json are not a bundle model's") from exc
    if source.get("kind") != "bundle" or type(image) is not dict:
        raise RegradeError("only a bundle model can be re-graded here")
    worker = image.get("overlay_tree_digest") or image.get("image_id")
    return (
        recipe,
        bundle_ref,
        _digest(worker, "overlay_tree_digest/image_id"),
        _digest(image.get("parent_image_id"), "parent_image_id"),
    )


def artifact_from_retained(retained, out, *, challenge_id, version, name="retained"):
    """Write the recal's calibration artifact for the retained model into the new directory ``out`` and return its manifest.
    The state and recipe are the retained bytes, unchanged; the identities are read from the retained files."""
    from carbon.agent_campaign import calibration_artifact_job as job

    files = retained if isinstance(retained, dict) else read_retained(retained)
    recipe, bundle_ref, worker, parent = identities(files)
    runtime = bundle_ref.get("runtime_profile_id")
    gpu = ("retained", "retained", "retained")
    try:
        return job.write_artifact(
            out,
            recipe_bytes=files["recipe.json"],
            state_bytes=files["state.npz"],
            challenge_id=challenge_id,
            version=version,
            bundle_ref="retained/" + name,
            bundle_sha256=_digest(bundle_ref.get("bundle_digest"), "bundle_digest"),
            worker_image_digest=worker,
            parent_image_digest=parent,
            runtime=runtime,
            train_sha256=_digest(recipe["challenge"]["train_digest"], "train_digest"),
            seed=0,
            build_wall_s=0.0,
            pod_id="retained",
            gpu=gpu,
        )
    except (job.ArtifactRefused, KeyError, TypeError) as exc:
        raise RegradeError(f"the retained model cannot be packaged: {exc}") from exc


def stored_legs(document):
    """``(A, D)`` the receiver recorded: a flat ``{"A", "D"}`` or the one ``legs`` object found in a document."""
    found = []

    def numbers(candidate):
        if type(candidate) is dict and all(
            type(candidate.get(k)) in (int, float)
            and not isinstance(candidate.get(k), bool)
            for k in ("A", "D")
        ):
            found.append((candidate["A"], candidate["D"]))

    def walk(value, key=None):
        if isinstance(value, dict):
            if key is None or key == "legs":
                numbers(value)
            for name, inner in value.items():
                walk(inner, name)
        elif isinstance(value, list):
            for inner in value:
                walk(inner, key)

    walk(document)
    unique = {pair for pair in found}
    if len(unique) != 1:
        raise RegradeError(
            "--stored must carry exactly one A and D pair (a flat object or one `legs`)"
        )
    return unique.pop()


def _same_path(child, parent):
    child, parent = Path(child).resolve(), Path(parent).resolve()
    return parent == child or parent in child.parents


def regrade(
    retained_dir,
    *,
    pack,
    challenge,
    version,
    work,
    judge_image,
    stored,
    copy_hotkey=None,
    fake=False,
    grade=None,
):
    """Re-grade the retained entry with the recal's grade path, recorded; the report dict.

    ``grade`` replaces `calibration_grade_run.run` in tests. ``report["ok"]`` is true only when the re-graded A and D equal
    ``stored`` exactly and the recomputed D equals the grader's D."""
    from carbon.challenge_validator import calibration_grade_run as runner

    retained_dir, work = Path(retained_dir), Path(work)
    if _same_path(work, retained_dir):
        raise RegradeError(
            "--work must not be inside --retained: the receiver's files are read-only here"
        )
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    artifact = work / ("artifact-" + retained_dir.name)
    if artifact.exists():
        raise RegradeError(
            "--work already holds this entry's artifact: use a fresh --work"
        )
    artifact_from_retained(
        read_retained(retained_dir),
        artifact,
        challenge_id=challenge,
        version=version,
        name=retained_dir.name,
    )
    run = grade or runner.run
    with parts_tool.recording() as recorder:
        result = run(
            artifact_dir=artifact,
            pack_root=Path(pack),
            challenge_id=challenge,
            version=version,
            work_root=work / "grade",
            judge_image=judge_image,
            fake=fake,
            copy_hotkey=copy_hotkey,
        )
    stored_a, stored_d = stored
    report = {
        "stored_a": stored_a,
        "stored_d": stored_d,
        "regraded_a": result.get("A"),
        "regraded_d": result.get("D"),
        "sets": [],
        "binding_d": [],
        "gated": False,
    }
    if recorder.sets:
        report["sets"] = parts_tool.parts(recorder)
        report["recomputed_d"] = parts_tool.recomputed_d(report["sets"])
        d_ok = stored_d == report["regraded_d"] == report["recomputed_d"]
    else:
        # a gated model has no pool grade: its D is the 0.0 the grader gave it
        report["gated"] = True
        report["recomputed_d"] = report["regraded_d"]
        d_ok = stored_d == report["regraded_d"] == 0.0
    report["ok"] = bool(d_ok and stored_a == report["regraded_a"])
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
    lines.insert(-1, f"stored A     = {report['stored_a']!r}")
    lines.insert(-1, f"regraded A   = {report['regraded_a']!r}")
    lines.insert(-1, f"regraded D   = {report['regraded_d']!r}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--retained", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--judge-image", type=Path)
    parser.add_argument("--stored", required=True, type=Path)
    parser.add_argument("--copy-hotkey")
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    from carbon.challenge_validator import calibration_grade as cg
    from carbon.challenge_validator import calibration_grade_run as runner
    from carbon.challenge_validator import cpu_pin

    try:
        cpu_pin.require()  # the re-grade scores on the same pinned kernels as the receiver
    except cpu_pin.CpuPinRefused as refused:
        print(f"REFUSED: {refused}", file=sys.stderr)
        return 2
    try:
        stored = stored_legs(json.loads(_read(args.stored)))
        if args.judge_image is None and not args.fake:
            raise RegradeError("--judge-image is required (or --fake for a rehearsal)")
        judge = (
            None
            if args.judge_image is None
            else runner._load_judge_image(args.judge_image)
        )
        report = regrade(
            args.retained,
            pack=args.pack,
            challenge=args.challenge,
            version=args.version,
            work=args.work,
            judge_image=judge,
            stored=stored,
            copy_hotkey=args.copy_hotkey,
            fake=args.fake,
        )
    except (RegradeError, parts_tool.PartsError, cg.CalibrationRefused) as refused:
        print(f"REFUSED: {type(refused).__name__}: {refused}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as refused:
        print(f"REFUSED: {type(refused).__name__}: {refused}", file=sys.stderr)
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
