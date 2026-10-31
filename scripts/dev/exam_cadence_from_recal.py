#!/usr/bin/env python3
"""Write `exam_cadence.json` (schema v2) from the launch recalibration's measured lane rows (Test Engineer, 2026-10-30).

It registers nothing: it writes the candidate file where you point it, and putting it at
`carbon/challenge_validator/exam_cadence.json` is a reviewed change of its own (exam_cap.py: "the recalibration writes
it and it is changed only by review"). Until that file carries values every official grade is refused with
`exam_cadence_unregistered`.

    python -m scripts.dev.exam_cadence_from_recal --lane-rows ROWS.json --class-record CLASS.json \\
        --lanes L [--challenges ID[,ID...]] --out exam_cadence.json

`--challenges` (default: the four launch Challenges) names the Challenges this file values: each needs its >= 10 rows,
only those are written, and the registry's `source` text names the included set. A partial file is valid and fails
closed for every Challenge left out (`ExamCap.reserve` refuses it with `exam_cap_unregistered`, never a default value),
so a Challenge whose recalibration is not done yet is added by a later file, not guessed.

The file's own registered formula (exam_cap.py module docstring and the registry's `source` text):

    capacity_gpu_lane_hours_per_day  R = lanes x 24 x 0.7          (lanes = the measured official GPU lanes)
    rebuild_gpu_lane_hours[C]        t_c = the mean GPU-lane-hours from lane start to lane release over the panel's
                                     rebuilds of Challenge C, at least 10 of them
    measurement_digest               sha256 of the lane-rows file, byte for byte
    class_record_digest              sha256 of the host-class record file, byte for byte

Input `--lane-rows` (JSON), schema "carbon.recal-lane-rows.v1":
    {"schema": ..., "challenges": {<challenge id>: {"rebuilds": [
        {"entry_id": <str>, "seed": <int>, "repeat": <int>,
         "lane_start_s": <number>, "lane_release_s": <number>}, ...]}}}
`lane_start_s` / `lane_release_s` are the driver's clock readings (seconds, one clock) when the rebuild took its GPU
lane and when it released it, around the WHOLE graded rebuild (build, graded inference, timed query, repeat pair): the
lane is held for all of it, and the build wall alone would understate t_c. Every row needs both fields, finite,
release strictly after start; a Challenge needs at least 10 distinct rows; every launch Challenge must be present.
Anything missing is a refusal naming where, never a default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.challenge_validator import exam_cap

SCHEMA_IN = "carbon.recal-lane-rows.v1"
MIN_REBUILDS = 10
#: The launch Challenges every cadence must value (Battery is registered in exam_cap but is not a launch exam).
REQUIRED = exam_cap._LEAN_CHALLENGES
UTILISATION = 0.7


class CadenceError(ValueError):
    pass


def _number(value, where):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise CadenceError(f"{where}: a finite number is required")
    return float(value)


def lane_hours(challenge, spec):
    """t_c in GPU-lane-hours for one Challenge, or a refusal."""
    rebuilds = spec.get("rebuilds") if isinstance(spec, dict) else None
    if not isinstance(rebuilds, list) or len(rebuilds) < MIN_REBUILDS:
        raise CadenceError(
            f"{challenge}: at least {MIN_REBUILDS} rebuilds with lane timing are required"
        )
    seen, seconds = set(), []
    for index, row in enumerate(rebuilds):
        where = f"{challenge}.rebuilds[{index}]"
        if not isinstance(row, dict):
            raise CadenceError(f"{where}: a row is required")
        key = (row.get("entry_id"), row.get("seed"), row.get("repeat"))
        if (
            not isinstance(key[0], str)
            or not key[0]
            or any(isinstance(k, bool) or not isinstance(k, int) for k in key[1:])
        ):
            raise CadenceError(f"{where}: entry_id, seed and repeat are required")
        if key in seen:
            raise CadenceError(f"{where}: a rebuild is listed twice")
        seen.add(key)
        start = _number(row.get("lane_start_s"), f"{where}.lane_start_s")
        release = _number(row.get("lane_release_s"), f"{where}.lane_release_s")
        if release <= start:
            raise CadenceError(f"{where}: lane_release_s must be after lane_start_s")
        seconds.append(release - start)
    return math.fsum(seconds) / len(seconds) / 3600.0


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _named(challenges):
    """The Challenges a file values, in the order named: the launch four by default; each must be registered in exam_cap."""
    if challenges is None:
        return tuple(REQUIRED)
    if not isinstance(challenges, (list, tuple)):
        raise CadenceError("challenges: a list of Challenge ids is required")
    names = tuple(dict.fromkeys(challenges))
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise CadenceError("challenges: at least one Challenge id is required")
    registered = exam_cap.registered_challenges()
    unknown = [name for name in names if name not in registered]
    if unknown:
        raise CadenceError(
            f"challenges: not registered in exam_cap: {', '.join(unknown)}"
        )
    return names


def build(lane_rows_raw, class_record_raw, lanes, challenges=None):
    """The v2 registry document for these inputs (the bytes' digests included), or a refusal. ``challenges`` names the
    Challenges to value (default the launch four); a Challenge left out gets no entry, so the cap refuses it.
    """
    included = _named(challenges)
    if isinstance(lanes, bool) or not isinstance(lanes, int) or lanes < 1:
        raise CadenceError("lanes: a whole number of at least 1 is required")
    if not class_record_raw:
        raise CadenceError("class record: an empty file")
    try:
        rows = json.loads(lane_rows_raw)
    except ValueError:
        raise CadenceError("lane rows: not JSON") from None
    if not isinstance(rows, dict) or rows.get("schema") != SCHEMA_IN:
        raise CadenceError(f"lane rows: schema must be {SCHEMA_IN}")
    challenges = rows.get("challenges")
    if not isinstance(challenges, dict):
        raise CadenceError("lane rows: challenges are required")
    missing = [name for name in included if name not in challenges]
    if missing:
        raise CadenceError(f"lane rows: no rebuilds for {', '.join(missing)}")
    measurement = _sha(lane_rows_raw)
    return {
        "schema": exam_cap.REGISTRY_SCHEMA,
        "source": (
            f"recalibration lane rows {measurement}: R = lanes x 24 x {UTILISATION} with lanes={lanes}; "
            f"t_c = mean GPU-lane-hours from lane start to release over the panel's >= {MIN_REBUILDS} rebuilds "
            "per Challenge (exam_cap.py); "
            f"Challenges included: {', '.join(sorted(included))}"
        ),
        "capacity_gpu_lane_hours_per_day": lanes * 24 * UTILISATION,
        "lanes": lanes,
        "rebuild_gpu_lane_hours": {
            name: lane_hours(name, challenges[name]) for name in sorted(included)
        },
        "measurement_digest": measurement,
        "class_record_digest": _sha(class_record_raw),
    }


def write(document, out):
    """Create-only canonical write, then the registry's own reader must accept it."""
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise CadenceError(f"{out.name}: refusing to overwrite an existing file")
    raw = (
        json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    out.write_bytes(raw)
    try:
        exam_cap.registered_cadence(out)
    except exam_cap.ExamCapRefused as refused:
        out.unlink()
        raise CadenceError(
            f"the written file fails the registry: {refused.code}"
        ) from None
    return _sha(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane-rows", required=True, type=Path)
    parser.add_argument("--class-record", required=True, type=Path)
    parser.add_argument("--lanes", required=True, type=int)
    parser.add_argument(
        "--challenges",
        type=lambda text: [item.strip() for item in text.split(",")],
        default=None,
        help="comma-separated Challenge ids to value (default: the four launch Challenges)",
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        document = build(
            args.lane_rows.read_bytes(),
            args.class_record.read_bytes(),
            args.lanes,
            args.challenges,
        )
        digest = write(document, args.out)
    except (OSError, CadenceError) as refused:
        print(f"REFUSED: {refused}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "out": str(args.out),
                "sha256": digest,
                "lanes": document["lanes"],
                "capacity_gpu_lane_hours_per_day": document[
                    "capacity_gpu_lane_hours_per_day"
                ],
                "rebuild_gpu_lane_hours": document["rebuild_gpu_lane_hours"],
                "measurement_digest": document["measurement_digest"],
                "class_record_digest": document["class_record_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
