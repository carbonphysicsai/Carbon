"""A finished workspace run's own output (RSURF-D17).

The research protocol returns a run by reference: its worker record and the
names of the files it exported to the miner's workspace. `run_output` is the
one read-only operation, in the shared table, that both doors use to show
the rest:
- the run's retained stdout, the last `STDOUT_MAX` bytes, as text;
- its exported files, with name, size and media type;
- each raster image among them, recognised by its bytes (PNG, JPEG, GIF,
  WebP), inline as base64 within `IMAGE_MAX`, `IMAGES_TOTAL` and
  `IMAGES_COUNT`. SVG and every other type is listed, never inlined.

It is the miner's own program's output, run on public and own files in the
isolated analysis image, and it stays MINER_SELF_REPORTED, untrusted text.
The unchanged carrier keeps no stderr, and keeps no stdout when the program
fails; the document says so instead of implying otherwise.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

SCHEMA = "carbon.control-center.run-output.v1"
STDOUT_MAX = 64 * 1024
IMAGE_MAX = 1024**2
IMAGES_TOTAL = 3 * 1024**2
IMAGES_COUNT = 6
EXPORTS_MAX = 64
_TASK = re.compile(r"rtsk_[0-9a-f]{64}\Z")
_OPERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
#: C0 controls other than tab, newline and carriage return, DEL, C1 controls
#: and bidirectional overrides: shown as U+FFFD, so text reads as it is.
_UNSAFE = re.compile(
    "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f-\\x9f\\u061c\\u200e\\u200f"
    "\\u202a-\\u202e\\u2066-\\u2069]"
)
CARRIER = {
    "stderr": "not kept: the sandbox treats it as a private diagnostic",
    "failed_run_stdout": "not kept: a program that fails keeps no stdout",
    "tip": (
        "Print to stdout, or write files to /scratch/output, to see them "
        "here. In Python, sys.stderr = sys.stdout sends errors to stdout."
    ),
}
_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def media_type(body):
    """A raster image's media type from its own bytes, or None."""
    for signature, kind in _SIGNATURES:
        if body.startswith(signature):
            return kind
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def text(body):
    return _UNSAFE.sub("�", body.decode("utf-8", errors="replace"))


def check_task(task):
    from scripts.dev.miner_launchpad.controller import Rejected

    if type(task) is not str or _TASK.fullmatch(task) is None:
        raise Rejected("research_task_id_required")
    return task


def document(task, result, *, stdout, exports):
    """The run's output document. `stdout` is the retained bytes or None;
    `exports` is [(name, body or None)] in the run's export order."""
    worker = result.get("worker") if type(result.get("worker")) is dict else {}
    failed = result.get("outcome") == "MINER_PROGRAM_FAILED"
    files, inlined, total = [], 0, 0
    for name, body in exports[:EXPORTS_MAX]:
        entry = {"name": name, "bytes": None if body is None else len(body)}
        kind = None if body is None else media_type(body)
        entry["media_type"] = kind
        if (
            kind is not None
            and len(body) <= IMAGE_MAX
            and total + len(body) <= IMAGES_TOTAL
            and inlined < IMAGES_COUNT
        ):
            entry["image_base64"] = base64.b64encode(body).decode("ascii")
            inlined += 1
            total += len(body)
        elif kind is not None:
            entry["not_inlined"] = "over the image bounds; read it with read_file"
        files.append(entry)
    tail = None
    truncated = False
    if stdout is not None:
        truncated = len(stdout) > STDOUT_MAX
        tail = text(stdout[-STDOUT_MAX:])
    return {
        "schema": SCHEMA,
        "task": task,
        "provenance": "MINER_SELF_REPORTED",
        "outcome": "MINER_PROGRAM_FAILED" if failed else "SUCCEEDED",
        "failure_code": worker.get("failure_code") if failed else None,
        "stdout": tail,
        "stdout_truncated_to_last_bytes": STDOUT_MAX if truncated else None,
        "files": files,
        "more_files": max(0, len(exports) - EXPORTS_MAX),
        "bounds": {
            "stdout_bytes": STDOUT_MAX,
            "image_bytes": IMAGE_MAX,
            "images_total_bytes": IMAGES_TOTAL,
            "images": IMAGES_COUNT,
        },
        "carrier": CARRIER,
        "shown_as": "untrusted text and raster images, never HTML",
        "official_eligible": False,
    }


def for_campaign(root, owner, task):
    """`run_output` for a campaign on this machine, from its own ledger."""
    from carbon.development_session.profile import digest
    from carbon.development_session.research_ledger import CampaignLedger
    from carbon.development_session.research_workspace import ResearchWorkspace
    from scripts.dev.miner_launchpad.controller import Rejected

    task = check_task(task)
    root = Path(root)
    ledger = CampaignLedger(root)
    with ledger.db() as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='research_results' AND type='table'"
        ).fetchone()
        row = (
            db.execute(
                "SELECT body,digest FROM research_results WHERE owner=? AND task=?",
                (owner, task),
            ).fetchone()
            if exists
            else None
        )
    if row is None or digest(row[0]) != row[1]:
        raise Rejected("run_output_unavailable", 404)
    result = json.loads(row[0])
    worker = result.get("worker") if type(result.get("worker")) is dict else {}
    if result.get("provenance") != "MINER_SELF_REPORTED" or not worker:
        # Only a workspace run has output of this kind.
        raise Rejected("not_a_workspace_run", 409)
    stdout = None
    operation = worker.get("operation")
    if type(operation) is str and _OPERATION.fullmatch(operation):
        path = root / operation / "stdout.txt"
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as handle:
                size = path.stat().st_size
                handle.seek(max(0, size - STDOUT_MAX - 1))
                stdout = handle.read()
    workspace = ResearchWorkspace(ledger, owner)
    exports = []
    for name in result.get("workspace_exports") or []:
        if type(name) is not str:
            continue
        try:
            exports.append((name, workspace.get(name)))
        except ValueError:
            exports.append((name, None))
    return document(task, result, stdout=stdout, exports=exports)
