"""The logs of a pod run that did not score, kept as operator-side evidence.

A pod exports `program.log` (the practice program's output, `pod_phase.py`)
and `phase.log` (the pod phase's, `bootstrap.py`). Carbon fetches every
exported file and digests it into the pod ledger's `pod_exported` row. For a
proposal whose outcome is not `SCORED`, `keep` also writes the log bodies,
bounded, into that proposal's record directory under the session root:

    <session root>/.../proposals/<pid>/pod-logs/attempt-<n>/
        index.json      what was kept, withheld or refused, and why
        program.log     the kept text, when kept
        phase.log

Each stored log starts with a header line naming the file, its full size, its
sha256 and what was kept; a truncated log keeps its head and tail with a marker
at the cut saying how many bytes were left out.

A log is never stored when:
- its bytes do not match the sha256 the pod listed for it (`digest_mismatch`;
  a backend that lists nothing matches nothing);
- any of its text names protected material (`protected_material.protected`;
  `withheld_protected_material`);
- it is too large to scan whole (`withheld_too_large_to_scan`);
- the proposal's total log allowance is spent (`withheld_total_cap`).
Its size and digest are recorded in every case. A log withheld for protected
material also records which class of marker tripped (`marker_classes`, the
class names of `protected_material.MARKER_CLASSES`): never a marker, never
the matched text (GRAPHITE-POD-GPU-PROBE-01).

**Isolation.** These files are operator evidence only. Nothing here is read
back into a tool result, a feedback document, an event, the session record or
a delivery bundle; the session root lives outside the repository
(`phase3._root`). A log's text is the pod's, written by the program, and is
treated as data.
"""

from __future__ import annotations

import hashlib
import json
import re

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from . import pods as podlib
from .protected_material import marker_classes, protected

#: The pod's log files Carbon keeps for a run that did not score.
LOG_NAMES = ("program.log", "phase.log")
INDEX_SCHEMA = "carbon.graphite.phase3.pod-logs.v1"
#: Engineering caps (GRAPHITE-POD-LOGS-RETRY-01). Per file: the first
#: `LOG_HEAD_BYTES` and the last `LOG_TAIL_BYTES`; a Python traceback ends a
#: log, so the tail gets the larger share.
LOG_HEAD_BYTES = 16 * 1024
LOG_TAIL_BYTES = 48 * 1024
#: The most log text kept for one proposal, over all its attempts and files.
LOG_TOTAL_BYTES = 256 * 1024
#: A log larger than this is not scanned for protected material, so it is
#: withheld whole (its digest is kept).
MAX_LOG_SCAN_BYTES = 16 * 1024 * 1024

KEPT = "kept"
DIGEST_MISMATCH = "digest_mismatch"
WITHHELD_PROTECTED = "withheld_protected_material"
WITHHELD_TOO_LARGE = "withheld_too_large_to_scan"
WITHHELD_TOTAL_CAP = "withheld_total_cap"

_TRACEBACK = "Traceback (most recent call last):"
_EXCEPTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]{0,127})(?::|$)")


def exception_class(text):
    """The class name of the last Python traceback's exception in `text`, or
    None. Only the name: never the message, which is the program's text."""
    at = text.rfind(_TRACEBACK)
    if at < 0:
        return None
    for line in text[at + len(_TRACEBACK) :].splitlines():
        if not line or line[0].isspace():
            continue
        match = _EXCEPTION.match(line)
        return match.group(1) if match else None
    return None


def _bounded(body, allowance):
    """`(head, tail, truncated)` of `body` within `allowance` bytes."""
    cap = min(LOG_HEAD_BYTES + LOG_TAIL_BYTES, allowance)
    if len(body) <= cap:
        return body, b"", 0
    head = min(LOG_HEAD_BYTES, cap // 4)
    tail = cap - head
    return body[:head], body[len(body) - tail :], len(body) - head - tail


def _stored(name, body, head, tail, truncated):
    header = (
        f"[carbon pod log] {name}: {len(body)} bytes, sha256 "
        f"{hashlib.sha256(body).hexdigest()}; "
        + (
            f"kept the first {len(head)} and last {len(tail)} bytes, "
            f"{truncated} bytes truncated (caps: head {LOG_HEAD_BYTES}, tail "
            f"{LOG_TAIL_BYTES}, per proposal {LOG_TOTAL_BYTES})"
            if truncated
            else "kept whole"
        )
        + "\n"
    ).encode()
    if not truncated:
        return header + head
    marker = f"\n[carbon pod log: {truncated} bytes truncated here]\n".encode()
    return header + head + marker + tail


def kept_for(status):
    """Whether a proposal closing with `status` keeps its pods' logs: only a
    run that did not score."""
    return status != "SCORED"


def digest_matches(body, listed):
    """The bytes are the ones the pod listed (a missing listing never is)."""
    return type(listed) is str and listed == hashlib.sha256(body).hexdigest()


def scannable(body):
    return len(body) <= MAX_LOG_SCAN_BYTES


def names_protected(text):
    return protected(text)


def withheld_classes(text):
    """Which class of protected-material marker a withheld log tripped
    (`protected_material.MARKER_CLASSES`): class names only, never a marker or
    the matched text (GRAPHITE-POD-GPU-PROBE-01)."""
    return marker_classes(text)


def allowance_left(allowance):
    return allowance > 0


def _withheld(entry, text):
    """A log withheld for protected material: its size and digest, and the
    classes of marker it tripped, never what matched."""
    return {
        **entry,
        "status": WITHHELD_PROTECTED,
        "marker_classes": withheld_classes(text),
    }


def _one(name, body, listed, allowance):
    """One log's index entry and, when kept, its stored bytes."""
    entry = {
        "name": name,
        "bytes": len(body),
        "digest": digest(body),
        "listed_sha256": listed,
    }
    if not digest_matches(body, listed):
        return {**entry, "status": DIGEST_MISMATCH}, None
    if not scannable(body):
        return {**entry, "status": WITHHELD_TOO_LARGE}, None
    text = body.decode("utf-8", errors="replace")
    if names_protected(text):
        return _withheld(entry, text), None
    if not allowance_left(allowance):
        return {**entry, "status": WITHHELD_TOTAL_CAP}, None
    head, tail, truncated = _bounded(body, allowance)
    stored = _stored(name, body, head, tail, truncated)
    if names_protected(stored.decode("utf-8", errors="replace")):
        # What would be stored must itself be clean (fail closed).
        return _withheld(entry, stored.decode("utf-8", errors="replace")), None
    return {
        **entry,
        "status": KEPT,
        "kept_bytes": len(head) + len(tail),
        "truncated_bytes": truncated,
        "exception_class": exception_class(text),
    }, stored


def keep(folder, attempts):
    """Write the logs of each attempt in `attempts`, a list of
    `(intent_id, {name: bytes}, {name: listed sha256 hex} | None)` in attempt
    order, under `folder`; return the index entries (no log text)."""
    folder = podlib.private_dir(folder)
    allowance = LOG_TOTAL_BYTES
    summary = []
    for number, (intent_id, logs, listed) in enumerate(attempts):
        where = podlib.private_dir(folder / f"attempt-{number}")
        entries = []
        for name in LOG_NAMES:
            if name not in logs:
                continue
            claimed = (listed or {}).get(name)
            entry, stored = _one(
                name, logs[name], claimed if type(claimed) is str else None, allowance
            )
            if stored is not None:
                write_once(where / name, stored)
                allowance -= entry["kept_bytes"]
            entries.append(entry)
        index = {
            "schema": INDEX_SCHEMA,
            "intent_id": intent_id,
            "attempt": number,
            "operator_evidence_only": True,
            "caps": caps(),
            "logs": entries,
        }
        write_once(where / "index.json", canonical(index))
        summary.append(
            {
                "intent_id": intent_id,
                "logs": [
                    {k: e[k] for k in ("name", "status", "bytes", "digest")}
                    for e in entries
                ],
            }
        )
    return summary


def caps():
    return {
        "head_bytes": LOG_HEAD_BYTES,
        "tail_bytes": LOG_TAIL_BYTES,
        "per_proposal_bytes": LOG_TOTAL_BYTES,
        "max_scan_bytes": MAX_LOG_SCAN_BYTES,
    }


def read_index(folder):
    """Every attempt's index under a proposal's `pod-logs` folder (operator
    tooling and tests)."""
    return [
        json.loads(path.read_bytes())
        for path in sorted(folder.glob("attempt-*/index.json"))
    ]


__all__ = [
    "DIGEST_MISMATCH",
    "KEPT",
    "LOG_HEAD_BYTES",
    "LOG_NAMES",
    "LOG_TAIL_BYTES",
    "LOG_TOTAL_BYTES",
    "MAX_LOG_SCAN_BYTES",
    "WITHHELD_PROTECTED",
    "WITHHELD_TOO_LARGE",
    "WITHHELD_TOTAL_CAP",
    "allowance_left",
    "caps",
    "digest_matches",
    "exception_class",
    "keep",
    "kept_for",
    "names_protected",
    "read_index",
    "scannable",
    "withheld_classes",
]
