"""The refused-capability log: what a Constructor asked for that its level refused.

DEVELOPMENT, LOG ONLY. Every `REFUSED_*` proposal result, and every capability wish a
Constructor files, is appended as one row to a Markdown table
(`docs/development/graphite/level4/REFUSED_CAPABILITY_LOG.md`), keyed by Challenge and
level. The rows are the evidence for which capability a later level should build first.
Nothing here widens a level: no capability reaches any run, no score or result record
changes, and a wish is data, never an instruction.

A wish rides in a proposal's `hypothesis` as one line:

    WISH: optimisation=<the code-level optimisation>; needs=<the op, kernel or library>;
    expected_gain=<what it would gain>; evidence=<why it believes it>

so the Constructor files it while it is blocked, instead of only being refused. A line
that does not parse is logged as written (truncated), not dropped.

Opt-in: nothing is written unless `CARBON_CAPABILITY_LOG` names the file, so a run
without it is exactly as before. Names and out-of-range values only: any text that
trips the protected-material check is withheld, and a failure to write never affects a
run.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .protected_material import protected

LOG_ENV = "CARBON_CAPABILITY_LOG"
DEFAULT_LOG = Path("docs/development/graphite/level4/REFUSED_CAPABILITY_LOG.md")
WISH_KEYS = ("optimisation", "needs", "expected_gain", "evidence")
_WISH = re.compile(r"^\s*WISH:\s*(.+)$", re.MULTILINE)
_PAIR = re.compile(r"(optimisation|needs|expected_gain|evidence)\s*=\s*")
MAX_CELL = 200
WITHHELD = "WITHHELD (protected material)"
COLUMNS = (
    "When (UTC)",
    "Challenge",
    "Level",
    "Run",
    "Proposal",
    "Kind",
    "Status",
    "Code",
    "Field",
    "Requested",
    "Optimisation",
    "Needs",
    "Expected gain",
    "Evidence",
    "Source",
)
HEADER = (
    "# Refused-capability log (Graphite)\n\n"
    "DEVELOPMENT, LOG ONLY. Each row is one refused proposal or one filed capability wish, "
    "keyed by Challenge and level. It widens nothing: no capability reaches any run. "
    "Names and out-of-range values only; no seed, key or hidden material. A wish is the "
    "Constructor's words, stored as data.\n\n"
    "Rows are appended by `carbon/agent_campaign/graphite/capability_log.py` when "
    f"`{LOG_ENV}` names this file; earlier rows are backfilled from the cited sources.\n\n"
    "| " + " | ".join(COLUMNS) + " |\n"
    "|" + "---|" * len(COLUMNS) + "\n"
)


#: What a brief says when it opts in: the grammar and the promise that a wish is a record,
#: never a grant.
WISH_BRIEF = {
    "line": (
        "WISH: optimisation=<the code-level optimisation>; needs=<the op, kernel or "
        "library it needs>; expected_gain=<what it would gain>; evidence=<why you believe it>"
    ),
    "where": "one line in a proposal's hypothesis",
    "effect": (
        "Carbon logs the wish with the level and Challenge. It widens nothing: no "
        "capability reaches any run, and a wish never changes a score."
    ),
}
WISH_INSTRUCTIONS = (
    " If a limit blocks an idea, say what you wanted with a WISH line (capability_wish) "
    "in the hypothesis of your next proposal, instead of only being refused."
)


def log_path():
    """The file named by the environment, or None (logging off)."""
    value = os.environ.get(LOG_ENV)
    return Path(value) if value else None


def parse_wish(text):
    """`{optimisation, needs, expected_gain, evidence}` from a `WISH:` line, or None
    when the text carries none. A malformed line is returned under `raw` only."""
    if type(text) is not str:
        return None
    found = _WISH.search(text)
    if not found:
        return None
    body = found.group(1)
    marks = list(_PAIR.finditer(body))
    wish = dict.fromkeys(WISH_KEYS)
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        wish[mark.group(1)] = body[mark.end() : end].strip(" ;")
    if not any(wish.values()):
        return {"raw": body}
    return wish


def _cell(value):
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text.replace("|", "/")).strip()
    return text[: MAX_CELL - 1] + "…" if len(text) > MAX_CELL else text


def _protected(*values):
    return any(protected(v) for v in values if v)


def row(entry):
    """One Markdown table row for `entry`: a dict keyed by `COLUMNS` names in
    snake case (`when`, `challenge`, `level`, `run`, `proposal`, `kind`, `status`,
    `code`, `field`, `requested`, `optimisation`, `needs`, `expected_gain`,
    `evidence`, `source`)."""
    keys = (
        "when",
        "challenge",
        "level",
        "run",
        "proposal",
        "kind",
        "status",
        "code",
        "field",
        "requested",
        "optimisation",
        "needs",
        "expected_gain",
        "evidence",
        "source",
    )
    return "| " + " | ".join(_cell(entry.get(k)) for k in keys) + " |\n"


def _requested(strategy, path):
    """`(field, value)` a refusal's issue path names in the strategy: the parameter
    name and, for a short scalar, the value asked for."""
    parts = [p for p in str(path).split("/") if p]
    if not parts:
        return "", ""
    field = parts[-1]
    node = strategy
    for part in parts:
        node = node.get(part) if isinstance(node, dict) else None
    if isinstance(node, (int, float, str)) and not isinstance(node, bool):
        text = str(node)
        return field, text if len(text) <= 40 else ""
    if isinstance(node, bool):
        return field, str(node).lower()
    return field, ""


def refusal_entries(
    *, challenge, level, run, proposal, record, strategy, why, when, source="live run"
):
    """Rows for one closed proposal that was refused: one per named issue, or one for
    the refusal itself; plus a wish row when its hypothesis carries one."""
    status = record.get("status", "")
    issues = record.get("issues") or []
    base = {
        "when": when,
        "challenge": challenge,
        "level": level,
        "run": run,
        "proposal": proposal,
        "kind": "refusal",
        "status": status,
        "source": source,
    }
    entries = []
    if status.startswith("REFUSED") and issues:
        for issue in issues:
            code, path = (list(issue) + ["", ""])[:2]
            field, value = _requested(strategy, path)
            entries.append(
                {**base, "code": code, "field": field or path, "requested": value}
            )
    elif status.startswith("REFUSED"):
        entries.append({**base, "code": record.get("reason_code", "")})
    return entries


def wish_entry(*, challenge, level, run, proposal, hypothesis, when, source="live run"):
    wish = parse_wish(hypothesis)
    if wish is None:
        return None
    entry = {
        "when": when,
        "challenge": challenge,
        "level": level,
        "run": run,
        "proposal": proposal,
        "kind": "wish",
        "source": source,
    }
    if "raw" in wish:
        entry["optimisation"] = wish["raw"]
    else:
        entry.update({k: wish[k] for k in WISH_KEYS})
    return entry


def append(entries, path=None):
    """Append `entries` as rows. A protected value withholds that row's text. Returns
    the number written. Never raises: logging must not affect a run."""
    path = log_path() if path is None else Path(path)
    if path is None or not entries:
        return 0
    try:
        lines = []
        for entry in entries:
            if _protected(*(str(v) for v in entry.values() if v is not None)):
                entry = {
                    **{k: entry.get(k) for k in ("when", "challenge", "level")},
                    "kind": entry.get("kind"),
                    "status": WITHHELD,
                }
            lines.append(row(entry))
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists() or path.stat().st_size == 0
        with open(path, "ab") as stream:
            if fresh:
                stream.write(HEADER.encode("utf-8"))
            stream.write("".join(lines).encode("utf-8"))
        return len(lines)
    except OSError:
        return 0


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
