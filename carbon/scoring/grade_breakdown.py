"""The PRIVATE grade breakdown a producer writes at grade time (owner, 18 Nov 2026: "keep all the data that matters";
model-eval 18-19 Nov: one shared, versioned writer for the next versions' producers, a must-have before each seal).

One small JSON document per graded submission, schema `SCHEMA`, kept in custody next to the grade record and NEVER
public (it holds hidden-exam values). What it holds, and nothing else (a closed field set, checked field by field):

- ``challenge_id``, ``challenge_version``, ``submission_id``, ``exam_key`` (the evaluation pack digest the grade ran on);
- ``contract_ids``: ``{name: id}``, the registered contract / pack / scorer identities the producer names;
- ``halves``: ``{"A", "D"}``, the grade's own A and D (the dual pack's two halves, before 0.5 A + 0.5 D);
- ``sets``: ``{set id: {"A", "D", "rows"}}``, each target set's A, its D as the total saw it, and its target count;
- ``tasks``: ``[{"task", "D", "Z", "oracle"}]``, each design task's D with its zero (Z, the registered zero model's value)
  and its oracle value;
- ``rule_flags``: ``{name: true | false}``, the registered rules' outcomes on this grade;
- ``outputs``: ``[{"class", "output", "range", "n", "median", "p90"}]``, the custody accuracy record's per class and
  output error aggregates (`pool_physics_score.accuracy_record`); never a per-case value;
- ``speed``: ``{"call_seconds", "median_seconds", "ceiling_seconds", "passed"}``, the speed lane's scored
  single-design call seconds and the gate's verdict on them (`pool_exam.single_call_speed_gate`);
- ``recipe``: ``{"recipe_info_bytes", "trained_arrays": {"count", "bytes"}}``, the charged recipe size under accounting v6
  (`carbon.level4.graph.recipe_info_bytes`) and the trained arrays the rebuilt state carries outside it (model-eval,
  19 Nov: computed by the build and dropped until now); `recipe_measures` reads both from the retained state bytes;
- ``written_at``: UTC, seconds.

A value a producer does not measure is ``null``, never a stand-in. Numbers are finite. The document is bounded
(`MAX_BYTES`) and written once (`write`), owner-only, into an owner-only directory: a breakdown is never replaced, and an
existing one with different bytes refuses. Nothing here grades, scores or changes a graded number: a producer computes
its grade as before and hands the values it already has to `breakdown`.

KEPT FROM THE OFFICIAL GRADE (owner via Lead, 19 Nov 2026: king statistics come from the exam's actual results, no
remeasuring). The receiver stages a keep around its producer call (`staged`, the `pool_menu.staged_rowcheck`
pattern: never through a producer file, whose bytes never move); the pool grade (`pool_exam.measure_pool`,
`pool_menu.score`) OFFERS the values it already computed (`offer`); `kept` reads them back after the call. Nothing
staged keeps nothing, so every other caller runs exactly as before; an offer never raises into a grade.

This module imports no accelerator profile and no execution package (`test_protected_material_isolation`).
"""

from __future__ import annotations

import contextlib
import contextvars
import copy
import datetime
import io
import json
import math
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path

SCHEMA = "carbon.exam.grade-breakdown.v1"
FIELDS = frozenset(
    {
        "schema",
        "challenge_id",
        "challenge_version",
        "submission_id",
        "exam_key",
        "contract_ids",
        "sets",
        "tasks",
        "rule_flags",
        "halves",
        "outputs",
        "speed",
        "recipe",
        "written_at",
    }
)
SET_FIELDS = frozenset({"A", "D", "rows"})
HALF_FIELDS = frozenset({"A", "D"})
OUTPUT_FIELDS = frozenset({"class", "output", "range", "n", "median", "p90"})
SPEED_FIELDS = frozenset(
    {"call_seconds", "median_seconds", "ceiling_seconds", "passed"}
)
MAX_CALLS = 256
TASK_FIELDS = frozenset({"task", "D", "Z", "oracle"})
RECIPE_FIELDS = frozenset({"recipe_info_bytes", "trained_arrays"})
ARRAY_FIELDS = frozenset({"count", "bytes"})
#: An engineering bound: a few KB is the expected size (a 305-task pool is ~30 KB).
MAX_BYTES = 262144
MAX_ENTRIES = 4096
SUFFIX = ".grade-breakdown.json"
#: The state archive members that are not trained arrays (`bundle_graph_state.freeze` and the physical states).
_NOT_TRAINED = frozenset({"__header__.npy", "graph.npy"})
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
#: A submission id names the file: no path separator.
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


class GradeBreakdownRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _name(value, code):
    if type(value) is not str or not _NAME.fullmatch(value):
        raise GradeBreakdownRefused(code)
    return value


def _id(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise GradeBreakdownRefused("grade_breakdown_submission_invalid")
    return value


def _value(value, code):
    """A finite number, or None (not measured)."""
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise GradeBreakdownRefused(code)
    return float(value)


def _count(value, code):
    if type(value) is not int or value < 0:
        raise GradeBreakdownRefused(code)
    return value


def _mapping(value, code):
    if type(value) is not dict or len(value) > MAX_ENTRIES:
        raise GradeBreakdownRefused(code)
    return value


def _recipe(value):
    if value is None:
        return {"recipe_info_bytes": None, "trained_arrays": None}
    if type(value) is not dict or set(value) != RECIPE_FIELDS:
        raise GradeBreakdownRefused("grade_breakdown_recipe_invalid")
    info = value["recipe_info_bytes"]
    arrays = value["trained_arrays"]
    if arrays is not None and (type(arrays) is not dict or set(arrays) != ARRAY_FIELDS):
        raise GradeBreakdownRefused("grade_breakdown_recipe_invalid")
    return {
        "recipe_info_bytes": (
            None if info is None else _count(info, "grade_breakdown_recipe_invalid")
        ),
        "trained_arrays": (
            None
            if arrays is None
            else {
                "count": _count(arrays["count"], "grade_breakdown_recipe_invalid"),
                "bytes": _count(arrays["bytes"], "grade_breakdown_recipe_invalid"),
            }
        ),
    }


def _halves(value):
    if value is None:
        return {"A": None, "D": None}
    if type(value) is not dict or set(value) != HALF_FIELDS:
        raise GradeBreakdownRefused("grade_breakdown_halves_invalid")
    return {
        key: _value(value[key], "grade_breakdown_halves_invalid") for key in ("A", "D")
    }


def _outputs(value):
    if value is None:
        return None
    if type(value) not in (list, tuple) or len(value) > MAX_ENTRIES:
        raise GradeBreakdownRefused("grade_breakdown_outputs_invalid")
    rows, seen = [], set()
    for entry in value:
        if type(entry) is not dict or set(entry) != OUTPUT_FIELDS:
            raise GradeBreakdownRefused("grade_breakdown_outputs_invalid")
        key = (
            _name(entry["class"], "grade_breakdown_outputs_invalid"),
            _name(entry["output"], "grade_breakdown_outputs_invalid"),
        )
        if key in seen:
            raise GradeBreakdownRefused("grade_breakdown_outputs_invalid")
        seen.add(key)
        rows.append(
            {
                "class": key[0],
                "output": key[1],
                "range": _name(entry["range"], "grade_breakdown_outputs_invalid"),
                "n": _count(entry["n"], "grade_breakdown_outputs_invalid"),
                "median": _value(
                    entry["median"], "grade_breakdown_outputs_invalid"
                ),
                "p90": _value(entry["p90"], "grade_breakdown_outputs_invalid"),
            }
        )
    return rows


def _speed(value):
    if value is None:
        return None
    if type(value) is not dict or set(value) != SPEED_FIELDS:
        raise GradeBreakdownRefused("grade_breakdown_speed_invalid")
    calls = value["call_seconds"]
    if type(calls) not in (list, tuple) or not 0 < len(calls) <= MAX_CALLS:
        raise GradeBreakdownRefused("grade_breakdown_speed_invalid")
    if type(value["passed"]) is not bool:
        raise GradeBreakdownRefused("grade_breakdown_speed_invalid")
    seconds = [_value(c, "grade_breakdown_speed_invalid") for c in calls]
    if any(c is None for c in seconds):
        raise GradeBreakdownRefused("grade_breakdown_speed_invalid")
    return {
        "call_seconds": seconds,
        "median_seconds": _value(
            value["median_seconds"], "grade_breakdown_speed_invalid"
        ),
        "ceiling_seconds": _value(
            value["ceiling_seconds"], "grade_breakdown_speed_invalid"
        ),
        "passed": value["passed"],
    }


def breakdown(
    *,
    challenge_id,
    challenge_version,
    submission_id,
    exam_key,
    contract_ids,
    sets,
    tasks,
    rule_flags,
    halves=None,
    outputs=None,
    speed=None,
    recipe=None,
    clock=None,
):
    """The checked breakdown document (see the module text), or `GradeBreakdownRefused`. ``clock``: unix seconds
    (default now)."""
    contract_ids = _mapping(contract_ids, "grade_breakdown_contract_ids_invalid")
    sets = _mapping(sets, "grade_breakdown_sets_invalid")
    rule_flags = _mapping(rule_flags, "grade_breakdown_rule_flags_invalid")
    if type(tasks) not in (list, tuple) or len(tasks) > MAX_ENTRIES:
        raise GradeBreakdownRefused("grade_breakdown_tasks_invalid")
    if type(exam_key) is not str or not _DIGEST.fullmatch(exam_key):
        raise GradeBreakdownRefused("grade_breakdown_exam_key_invalid")
    checked_sets = {}
    for set_id, entry in sets.items():
        _name(set_id, "grade_breakdown_sets_invalid")
        if type(entry) is not dict or set(entry) != SET_FIELDS:
            raise GradeBreakdownRefused("grade_breakdown_sets_invalid")
        checked_sets[set_id] = {
            "A": _value(entry["A"], "grade_breakdown_sets_invalid"),
            "D": _value(entry["D"], "grade_breakdown_sets_invalid"),
            "rows": _count(entry["rows"], "grade_breakdown_sets_invalid"),
        }
    checked_tasks, seen = [], set()
    for entry in tasks:
        if type(entry) is not dict or set(entry) != TASK_FIELDS:
            raise GradeBreakdownRefused("grade_breakdown_tasks_invalid")
        task = _name(entry["task"], "grade_breakdown_tasks_invalid")
        if task in seen:
            raise GradeBreakdownRefused("grade_breakdown_task_repeated")
        seen.add(task)
        checked_tasks.append(
            {
                "task": task,
                **{
                    key: _value(entry[key], "grade_breakdown_tasks_invalid")
                    for key in ("D", "Z", "oracle")
                },
            }
        )
    flags = {}
    for name, flag in rule_flags.items():
        _name(name, "grade_breakdown_rule_flags_invalid")
        if type(flag) is not bool:
            raise GradeBreakdownRefused("grade_breakdown_rule_flags_invalid")
        flags[name] = flag
    ids = {}
    for name, identity in contract_ids.items():
        _name(name, "grade_breakdown_contract_ids_invalid")
        ids[name] = _name(identity, "grade_breakdown_contract_ids_invalid")
    now = datetime.datetime.now(datetime.UTC).timestamp() if clock is None else clock
    if type(now) not in (int, float) or not math.isfinite(now) or now <= 0:
        raise GradeBreakdownRefused("grade_breakdown_clock_invalid")
    document = {
        "schema": SCHEMA,
        "challenge_id": _name(challenge_id, "grade_breakdown_challenge_invalid"),
        "challenge_version": _name(
            challenge_version, "grade_breakdown_challenge_invalid"
        ),
        "submission_id": _id(submission_id),
        "exam_key": exam_key,
        "contract_ids": ids,
        "sets": checked_sets,
        "tasks": checked_tasks,
        "rule_flags": flags,
        "halves": _halves(halves),
        "outputs": _outputs(outputs),
        "speed": _speed(speed),
        "recipe": _recipe(recipe),
        "written_at": datetime.datetime.fromtimestamp(now, datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
    if set(document) != FIELDS or len(dumps(document)) > MAX_BYTES:
        raise GradeBreakdownRefused("grade_breakdown_too_large")
    return document


def dumps(document):
    """Canonical bytes: sorted keys, no whitespace, no NaN."""
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def write(directory, document):
    """Write ``document`` once as ``<directory>/<submission_id>.grade-breakdown.json`` (owner-only, whole or not at
    all) and return its path. ``directory`` must exist, be a real directory and give no access to group or others; the
    same bytes again is a no-op, different bytes refuse (``grade_breakdown_conflict``).
    """
    if (
        type(document) is not dict
        or set(document) != FIELDS
        or document["schema"] != SCHEMA
    ):
        raise GradeBreakdownRefused("grade_breakdown_document_invalid")
    rechecked = breakdown(
        **{key: document[key] for key in FIELDS - {"schema", "written_at", "recipe"}},
        recipe=document.get("recipe"),
        clock=_parsed_time(document.get("written_at")),
    )
    if rechecked != document:
        raise GradeBreakdownRefused("grade_breakdown_document_invalid")
    directory = Path(directory)
    try:
        mode = os.lstat(directory).st_mode
    except OSError:
        raise GradeBreakdownRefused("grade_breakdown_directory_unavailable") from None
    if not stat.S_ISDIR(mode) or (os.name == "posix" and mode & 0o077):
        raise GradeBreakdownRefused("grade_breakdown_directory_not_private")
    path = directory / (document["submission_id"] + SUFFIX)
    payload = dumps(document)
    if path.is_symlink():
        raise GradeBreakdownRefused("grade_breakdown_conflict")
    if path.exists():
        if path.read_bytes() != payload:
            raise GradeBreakdownRefused("grade_breakdown_conflict")
        return path
    descriptor, staged = tempfile.mkstemp(prefix=f".{path.name}.", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staged, 0o600)
        try:
            os.link(staged, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != payload:
                raise GradeBreakdownRefused("grade_breakdown_conflict") from None
    finally:
        os.unlink(staged)
    return path


def _parsed_time(text):
    try:
        return (
            datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.UTC)
            .timestamp()
        )
    except (TypeError, ValueError):
        raise GradeBreakdownRefused("grade_breakdown_document_invalid") from None


def recipe_measures(state_bytes):
    """``{"recipe_info_bytes", "trained_arrays": {"count", "bytes"}}`` of a retained rebuilt state (an ``.npz`` written
    by the graph states' ``freeze``): the accounting-v6 charged size of its graph document, and the count and data bytes
    (element count x item size) of every other array member, the trained values outside that charge. Reads headers and
    the graph only; no array is loaded. `GradeBreakdownRefused` for anything else."""
    import numpy as np

    from carbon.level4 import graph

    if type(state_bytes) is not bytes:
        raise GradeBreakdownRefused("grade_breakdown_state_invalid")
    count = total = 0
    document = None
    try:
        with zipfile.ZipFile(io.BytesIO(state_bytes)) as archive:
            for member in archive.infolist():
                if not member.filename.endswith(".npy") or "/" in member.filename:
                    raise GradeBreakdownRefused("grade_breakdown_state_invalid")
                with archive.open(member) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version == (1, 0):
                        header = np.lib.format.read_array_header_1_0(stream)
                    elif version == (2, 0):
                        header = np.lib.format.read_array_header_2_0(stream)
                    else:
                        raise GradeBreakdownRefused("grade_breakdown_state_invalid")
                    shape, _fortran, dtype = header
                    if member.filename == "graph.npy":
                        if dtype != np.uint8 or len(shape) != 1:
                            raise GradeBreakdownRefused("grade_breakdown_state_invalid")
                        document = json.loads(stream.read(shape[0]))
                        continue
                if member.filename in _NOT_TRAINED:
                    continue
                count += 1
                total += math.prod(shape) * dtype.itemsize
    except (zipfile.BadZipFile, ValueError, OSError, EOFError):
        raise GradeBreakdownRefused("grade_breakdown_state_invalid") from None
    if type(document) is not dict:
        raise GradeBreakdownRefused("grade_breakdown_state_invalid")
    try:
        charged = graph.recipe_info_bytes(document)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise GradeBreakdownRefused("grade_breakdown_state_invalid") from None
    return {
        "recipe_info_bytes": charged,
        "trained_arrays": {"count": count, "bytes": total},
    }


#: The keep staged for the grade produced in THIS context (`staged`): set by the receiver around its producer call,
#: never through a producer file (the `pool_menu.staged_rowcheck` pattern).
_STAGED = contextvars.ContextVar("carbon_grade_breakdown", default=None)


@contextlib.contextmanager
def staged():
    """Stage a keep for the grade measured inside this block; yields the stage `kept` reads. Cleared on exit."""
    stage = {"measures": 0, "values": {}, "broken": None}
    token = _STAGED.set(stage)
    try:
        yield stage
    finally:
        _STAGED.reset(token)


def offer(name, value):
    """The pool grade hands one value it already computed to the staged keep (a deep copy; a zero-argument callable is
    called here, so building the value is inside the guard); nothing staged: a no-op, nothing built. ``name`` "measure"
    closes one measure (a second one in the same stage makes the keep ambiguous). Never raises."""
    stage = _STAGED.get()
    if stage is None:
        return
    try:
        if name == "measure":
            stage["measures"] += 1
        elif name not in stage["values"]:
            stage["values"][name] = copy.deepcopy(value() if callable(value) else value)
    except Exception:  # noqa: BLE001 (an offer never changes or stops a grade)
        stage["broken"] = "grade_breakdown_offer_failed"


def kept(stage):
    """The values one staged grade offered, ``{name: value}``; None when no pool grade ran inside the stage (nothing
    to keep); `GradeBreakdownRefused` when the keep is ambiguous (more than one measure) or an offer failed."""
    if type(stage) is not dict or stage.get("measures", 0) == 0:
        return None
    if stage["broken"] is not None:
        raise GradeBreakdownRefused(stage["broken"])
    if stage["measures"] != 1:
        raise GradeBreakdownRefused("grade_breakdown_more_than_one_measure")
    return dict(stage["values"])
