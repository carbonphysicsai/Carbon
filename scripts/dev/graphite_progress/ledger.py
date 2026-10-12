"""Aggregate run summaries into one ledger line per level per batch, and append it idempotently.

Efficiency (cost, wall-clock, agent-hours, waste) and effectiveness (improvement outcomes,
bundling, attack coverage, real findings, findings that led to a fix, gate coverage) in one line.
Every number carries its sample size `n` and a source; a number whose source is missing is
`UNMEASURED`, never estimated. Dollars are on the reservation plus model-charge basis, totals only.
"""

from __future__ import annotations

import json
import statistics
from decimal import Decimal
from pathlib import Path

from . import improvement
from .model import (
    LINE_SCHEMA,
    REFUSAL_CLASSES,
    TRIAGE_CLASSES,
    UNMEASURED,
    USD_BASIS,
    ProgressError,
    metric,
    refuse_sealed,
    unmeasured,
)


def _ratio(numerator, denominator, digits=4):
    return round(numerator / denominator, digits) if denominator else None


def _usd_total(runs):
    values = [Decimal(r["booked_usd"]) for r in runs if r.get("booked_usd") is not None]
    return (sum(values, Decimal(0)), len(values)) if values else (None, 0)


def refusal_class(level, proposal_id, status, classes):
    """A refusal's class: `infra` for FAILED_INFRA, else the registered class for this level's
    proposal (`L<level>:<proposal id>`: ids repeat across runs), else UNCLASSIFIED."""
    if status == "FAILED_INFRA":
        return "infra"
    found = classes.get(f"L{level}:{proposal_id}")
    return found if found in REFUSAL_CLASSES else "UNCLASSIFIED"


def constructor_block(runs, classes):
    if not runs:
        return None
    n = len(runs)
    bundled = sum(1 for r in runs if r["bundled"])
    proposals = sum(r["proposals"] for r in runs)
    improving = sum(r["outcomes"].get("IMPROVEMENT", 0) for r in runs)
    scores = [s for r in runs for s in (r.get("practice_scores") or [])]
    by_class = {name: 0 for name in REFUSAL_CLASSES}
    causes = {}
    for r in runs:
        for status, ids in r["refused"].items():
            causes[status] = causes.get(status, 0) + len(ids)
            for proposal_id in ids:
                by_class[refusal_class(r["level"], proposal_id, status, classes)] += 1
    refused = sum(by_class.values())
    usd = _usd_total(runs)[0]
    walls = [r["wall_seconds"] for r in runs if r.get("wall_seconds") is not None]
    return {
        "runs": n,
        "proposals": proposals,
        "improvement": {
            "best": (
                metric(
                    max(scores),
                    len(scores),
                    "PUBLIC practice scores supplied with the batch",
                )
                if scores
                else unmeasured(
                    "run output holds no public score; proposals are judged on the hidden pool"
                )
            ),
            "median": (
                metric(
                    statistics.median(scores),
                    len(scores),
                    "PUBLIC practice scores supplied with the batch",
                )
                if scores
                else unmeasured("run output holds no public score")
            ),
            "public_dev": improvement.public_dev_block(
                [r["public_improvement"] for r in runs if r.get("public_improvement")]
            ),
            "proposals_with_outcome_IMPROVEMENT": metric(
                improving,
                proposals,
                "the public categorical outcome of each scored proposal",
            ),
        },
        "bundled_share": metric(
            _ratio(bundled, n), n, f"{bundled} of {n} runs BUNDLED"
        ),
        "refusals": {
            "rate": metric(
                _ratio(refused, proposals),
                proposals,
                f"{refused} of {proposals} proposals refused",
            ),
            "by_class": by_class,
            "causes": dict(sorted(causes.items())),
        },
        "usd_per_bundled": (
            metric(str((usd / bundled).quantize(Decimal("0.01"))), bundled, USD_BASIS)
            if bundled and usd is not None
            else unmeasured(
                "no BUNDLED run" if not bundled else "no booked cost recorded", bundled
            )
        ),
        "wall_hours_per_bundled": (
            metric(
                round(sum(walls) / 3600 / bundled, 3),
                len(walls),
                f"executor chain-log start to exit, {len(walls)} of {n} runs",
            )
            if bundled and len(walls) == n
            else unmeasured("no BUNDLED run or a run has no chain log", len(walls))
        ),
        "agent_hours": (
            metric(
                round(sum(walls) / 3600, 3),
                len(walls),
                f"session duration from the executor chain log, {len(walls)} of {n} runs",
            )
            if walls
            else unmeasured("no session duration recorded")
        ),
        "waste": {
            "refused": refused,
            "failed_infra": by_class["infra"],
            "stalled_runs": sum(1 for r in runs if r["stalled"]),
            "causes": dict(sorted(causes.items())),
        },
        "booked_usd": None if usd is None else str(usd),
    }


def attacker_block(runs, triage, fixes):
    if not runs:
        return None
    ids = sorted({f for r in runs for f in r["findings"]})
    classes = {i: triage.get(i) for i in ids}
    triaged = {i: c for i, c in classes.items() if c in TRIAGE_CLASSES}
    real = [i for i, c in triaged.items() if c == "REAL_ESCAPE"]
    usd = _usd_total(runs)[0]
    listed = sum(r["families_listed"] for r in runs)
    attempted = sum(r["families_attempted"] for r in runs)
    walls = [r["wall_seconds"] for r in runs if r.get("wall_seconds") is not None]
    actionable = [i for i, c in triaged.items() if c in ("REAL_ESCAPE", "ORACLE_GAP")]
    fixed = [i for i in actionable if i in (fixes or {})]
    return {
        "runs": len(runs),
        "attempts": sum(r.get("attempts") or 0 for r in runs),
        "families": {
            "listed": listed,
            "attempted": attempted,
            "share_attempted": metric(
                _ratio(attempted, listed), len(runs), "run coverage reports"
            ),
        },
        "raw_findings": metric(
            len(ids), len(runs), "distinct finding ids in the coverage reports"
        ),
        "real_findings_per_run": (
            metric(
                _ratio(len(real), len(runs)),
                len(runs),
                f"{len(real)} REAL_ESCAPE of {len(triaged)} triaged",
            )
            if len(triaged) == len(ids)
            else unmeasured(
                f"{len(ids) - len(triaged)} of {len(ids)} findings are not triaged",
                len(triaged),
            )
        ),
        "triage": {
            k: sum(1 for c in triaged.values() if c == k) for k in TRIAGE_CLASSES
        },
        "usd_per_real_finding": (
            metric(
                str((usd / len(real)).quantize(Decimal("0.01"))), len(real), USD_BASIS
            )
            if real and usd is not None
            else unmeasured("no real finding" if not real else "no booked cost")
        ),
        "usd_per_family_attempted": (
            metric(
                str((usd / attempted).quantize(Decimal("0.01"))), attempted, USD_BASIS
            )
            if attempted and usd is not None
            else unmeasured("no family attempted")
        ),
        "findings_led_to_fix": (
            metric(
                _ratio(len(fixed), len(actionable)),
                len(actionable),
                "triaged REAL_ESCAPE and ORACLE_GAP findings with a recorded fix",
            )
            if actionable and fixes is not None
            else unmeasured("no actionable triaged finding or no finding-to-fix record")
        ),
        "agent_hours": (
            metric(
                round(sum(walls) / 3600, 3),
                len(walls),
                f"session duration from the executor chain log, {len(walls)} of {len(runs)} runs",
            )
            if walls
            else unmeasured("no session duration recorded")
        ),
        "stalled_runs": sum(1 for r in runs if r["stalled"]),
        "booked_usd": None if usd is None else str(usd),
    }


def gate_block(history, level, challenge):
    """NOT_BUILT and FAIL burn-down per level from the committed readiness history."""
    rows = [
        h
        for h in history
        if h.get("level") == level
        and h.get("challenge") == challenge
        and not h.get("partial")
    ]
    if not rows:
        return unmeasured("no readiness history for this level")
    series = [
        {
            "utc": h["utc"],
            "NOT_BUILT": h["counts"].get("NOT_BUILT", 0),
            "FAIL": h["counts"].get("FAIL", 0),
            "launch_ready": h.get("launch_ready"),
        }
        for h in sorted(rows, key=lambda h: h["utc"])
    ]
    return {
        "runs": len(series),
        "first": series[0],
        "last": series[-1],
        "series": series,
    }


def build_line(
    *,
    batch_id,
    level,
    challenge,
    date,
    runs,
    classes,
    triage,
    fixes,
    history,
    excluded=(),
):
    constructors = [
        r for r in runs if r["role"] == "constructor" and r["level"] == level
    ]
    attackers = [r for r in runs if r["role"] == "attacker" and r["level"] == level]
    return {
        "schema": LINE_SCHEMA,
        "batch": batch_id,
        "level": level,
        "challenge": challenge,
        "date": date,
        "basis": USD_BASIS,
        "constructor": constructor_block(constructors, classes),
        "attacker": attacker_block(attackers, triage, fixes),
        "gate": gate_block(history, level, challenge),
        "excluded_sources": [
            dict(e) for e in excluded if e.get("level") in (None, level)
        ],
        "claims": "DEVELOPMENT evidence only: grades nothing, accepts nothing; UNMEASURED means no cited source",
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def read_ledger(path):
    path = Path(path)
    if not path.exists():
        return []
    lines = []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            line = json.loads(text)
        except ValueError as error:
            raise ProgressError(f"ledger_corrupt: line {number}") from error
        if line.get("schema") != LINE_SCHEMA:
            raise ProgressError(f"ledger_corrupt: line {number} has another schema")
        lines.append(line)
    return lines


def append_line(path, line):
    """Append `line` unless its (batch, level) is already there. The same content is a no-op;
    different content for the same key is refused (the ledger is append-only)."""
    path = refuse_sealed(path)
    existing = read_ledger(path)
    for found in existing:
        if (found["batch"], found["level"]) == (line["batch"], line["level"]):
            if canonical(found) == canonical(line):
                return "unchanged"
            raise ProgressError(
                f"batch_exists_with_different_content: {line['batch']} L{line['level']}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(line) + "\n")
    return "appended"


__all__ = ["UNMEASURED", "append_line", "build_line", "read_ledger"]
