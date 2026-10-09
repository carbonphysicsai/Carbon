"""SUBMISSION-RATE-STUDY-01's operator-side harness (VALIDATOR-30). Operator
only: no miner surface imports it.

**The non-consuming fresh scorer** (`fresh_score`): a run's retained model is
scored once on the study's sealed fresh set for window `w` (`bank-fresh-T<w>`
in the study ledger), with the validator's own metric
(`exam.evaluate`, the case store built as the validator builds its own). The
set is never consumed: every model at window `w` scores the same set, and a
repeat for one model returns its stored result. The result goes to the run's
private state only.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

FRESH_SCHEMA = "carbon.rate-study.fresh-score.v1"
FRESH_PREDICTIONS = "fresh/"


class StudyRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _private_json(path):
    if not path.exists():
        return {}
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise StudyRefused("study_file_not_owner_only")
    return json.loads(path.read_text())


def _write_private(path, value):
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
    os.replace(temporary, path)


def fresh_set(ledger, window):
    """`(case ids, inputs, references)` of the sealed fresh set for window
    index `window`. Private."""
    role = f"bank-fresh-T{int(window)}"
    rows = {r["role"]: r for r in ledger.tranches("fresh")}
    if rows.get(role, {}).get("state") != "SEALED":
        raise StudyRefused("study_fresh_set_not_sealed")
    leaves = ledger._leaves(role)
    ids = [case_id for case_id, _, _ in leaves]
    inputs = {case_id: case_inputs for case_id, case_inputs, _ in leaves}
    refs = {case_id: reference for case_id, _, reference in leaves}
    return ids, inputs, refs


def fresh_score(target, ledger, submission_id, window, state_dir):
    """The model's `s_fresh` on window `window`'s fresh set: scored once,
    stored in `state_dir/fresh-scores.json` (owner-only), never consumed."""
    from carbon.battery import exam
    from carbon.battery.worker import WorkerFailure

    from .tuning import case_store

    path = Path(state_dir) / "fresh-scores.json"
    stored = _private_json(path)
    key = f"{submission_id}/w{int(window):02d}"
    if key in stored and stored[key]["state"] != "FAILED_INFRA":
        return stored[key]
    ids, inputs, refs = fresh_set(ledger, window)
    try:
        predictions = target._quiz_predictions(
            submission_id,
            inputs,
            f"fresh-w{int(window):02d}",
            namespace=FRESH_PREDICTIONS,
        )
        _rows, aggregate = exam.evaluate(
            predictions,
            ids,
            case_store({"duplicates": []}, refs, target.repository),
        )
        found = {
            "schema": FRESH_SCHEMA,
            "state": "SCORED",
            "window": int(window),
            "s_fresh": aggregate["score"],
            "eligible": aggregate["eligible"],
        }
    except WorkerFailure as failure:
        found = {
            "schema": FRESH_SCHEMA,
            "state": "CANDIDATE_FAILED" if failure.candidate else "FAILED_INFRA",
            "window": int(window),
            "code": failure.code,
        }
    stored[key] = found
    _write_private(path, stored)
    return found


__all__ = ["StudyRefused", "fresh_score", "fresh_set"]
