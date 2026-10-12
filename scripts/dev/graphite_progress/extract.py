"""Turn raw Graphite run output into run summaries (`carbon.graphite.progress-run.v1`).

Reads only what a run prints or records for the people running it: the phase-3 Constructor
result document, the phase-4 Attacker coverage document and the executor's chain log. A field
the source does not hold is absent, and the aggregate then reports UNMEASURED. Improvement
magnitudes are not read from the run output (the Constructor is scored on the hidden pool):
only the public categorical outcome is, and a PUBLIC practice score may be supplied beside it.
"""

from __future__ import annotations

import datetime
import json
import re
from decimal import Decimal, InvalidOperation

from .model import RUN_SCHEMA, ProgressError, refuse_sealed

_START = re.compile(r"^(\S+Z) (\S+) .*\bstart\b")
_EXIT = re.compile(r"^(\S+Z) (\S+) .*\bexit (\d+)")


def read_document(path):
    """The first JSON object that starts a line in `path` (run output may open with progress
    text). A sealed path, an unreadable file or a file with no object is refused."""
    path = refuse_sealed(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ProgressError(f"source_unreadable: {path.name}") from error
    for match in re.finditer(r"^\{", text, re.MULTILINE):
        try:
            value, _ = json.JSONDecoder().raw_decode(text[match.start() :])
        except ValueError:
            continue
        if type(value) is dict:
            return value
    raise ProgressError(f"source_has_no_document: {path.name}")


def _usd(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number >= 0 else None


def wall_seconds(chain_text, label):
    """Seconds from the first `start` line to the last `exit` line that name `label` in an
    executor chain log (`<UTC> <words> start|exit N`), or None."""
    started = ended = None
    for line in chain_text.splitlines():
        words = line.strip().split(" ", 1)
        if (
            len(words) < 2
            or not words[0].endswith("Z")
            or f" {label} " not in f" {words[1]} "
        ):
            continue
        try:
            moment = datetime.datetime.fromisoformat(words[0].replace("Z", "+00:00"))
        except ValueError:
            continue
        if _START.search(line) and started is None:
            started = moment
        if _EXIT.search(line):
            ended = moment
    if started is None or ended is None or ended < started:
        return None
    return int((ended - started).total_seconds())


def constructor_run(
    document,
    *,
    level,
    source,
    batch,
    wall=None,
    practice_scores=None,
    public_improvement=None,
):
    """A Constructor run summary from the phase-3 result document."""
    summary = document.get("summary") or {}
    proposals = [p for p in summary.get("proposals", []) if p.get("kind") == "proposal"]
    outcomes, refused = {}, {}
    for proposal in proposals:
        status = str(proposal.get("status"))
        if status.startswith("REFUSED_") or status == "FAILED_INFRA":
            refused.setdefault(status, []).append(proposal.get("proposal_id"))
        if proposal.get("outcome"):
            outcomes[proposal["outcome"]] = outcomes.get(proposal["outcome"], 0) + 1
    campaigns = (document.get("budget") or {}).get("campaigns") or {}
    booked = sum(
        (_usd(c.get("committed")) or Decimal(0) for c in campaigns.values()), Decimal(0)
    )
    if not campaigns:
        booked = _usd((document.get("pod_charges") or {}).get("booked_usd"))
    delivery = document.get("delivery") or {}
    failure = None
    state = document.get("provider_state")
    return {
        "schema": RUN_SCHEMA,
        "role": "constructor",
        "level": level,
        "batch": batch,
        "source": source,
        "run_id": document.get("run_id"),
        "provider_state": state,
        "controller_phase": document.get("controller_phase"),
        "stalled": state != "succeeded",
        "failure": failure,
        "bundled": delivery.get("status") == "BUNDLED",
        "proposals": len(proposals),
        "outcomes": outcomes,
        "refused": {
            status: sorted(map(str, ids)) for status, ids in sorted(refused.items())
        },
        "booked_usd": None if booked is None else str(booked),
        "wall_seconds": wall,
        "practice_scores": practice_scores,
        "public_improvement": public_improvement,
    }


def attacker_run(document, *, level, source, batch, wall=None):
    """An Attacker run summary from the phase-4 coverage document (the `{coverage, session}`
    wrapper a phase-4 run prints)."""
    coverage = document.get("coverage") or document
    session = document.get("session") or {}
    families = coverage.get("families") or {}
    rows = families.get("families") or {}
    listed = sorted(name for name in rows if name != "UNASSIGNED")
    not_run = sorted(set(families.get("not_run") or []))
    by_source = coverage.get("findings_by_source") or {}
    usd = _usd(session.get("settled_usd"))
    return {
        "schema": RUN_SCHEMA,
        "role": "attacker",
        "level": level,
        "batch": batch,
        "source": source,
        "run_id": session.get("run_id"),
        "provider_state": session.get("provider_state"),
        "stalled": session.get("provider_state") not in (None, "succeeded"),
        "attempts": coverage.get("attempts"),
        "families_listed": len(listed),
        "families_attempted": len([n for n in listed if n not in not_run]),
        "not_run": not_run,
        "findings": sorted(coverage.get("findings") or session.get("findings") or []),
        "findings_by_source": {k: len(v) for k, v in sorted(by_source.items())},
        "booked_usd": None if usd is None else str(usd),
        "wall_seconds": wall,
    }
