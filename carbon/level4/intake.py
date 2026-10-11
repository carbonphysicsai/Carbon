"""Gate G0, intake, and G3's isolated parse (development only).

`intake` takes a submission as it arrives: the manifest's bytes and the
documents' bytes, each named by its digest (`submission`). In order:

1. **Bounds.** Every bound in `BOUNDS` must be set by the caller; an unset
   one (`HUMAN_INPUT`) stops intake with `IntakeBlocked`: nothing is parsed
   and nothing is refused on the miner's account.
2. **Sizes.** The manifest, each document and the whole submission are
   checked against their bounds before any parsing.
3. **Isolated parse (G3).** A separate process with CPU, memory and file
   limits, no inherited environment and no network-facing state parses and
   verifies the submission first (`_parse_worker`). A parse that crashes,
   exhausts its memory or overruns its deadline is a typed construction
   refusal on the submission. A failure to start that process is Carbon's
   own: `IntakeInfraFailure`, `FAILED_INFRA`, never charged to the miner.
4. **In-process verify.** Only then does Carbon parse the bytes itself
   (`submission.verify`) to hand them on to G4.

The bounds are the owner's (OWNER-L4-VALUES-01, development and testnet);
nothing here chooses one. Development tests pass fixture values.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from . import graph, submission
from .allowlist import HUMAN_INPUT

#: Intake bounds, approved as proposed in
#: `docs/development/graphite/level4/LEVEL4_VALUES_PROPOSAL.md` §1-§2
#: (OWNER-L4-VALUES-01). The transport bound is the validator intake's.
BOUNDS = {
    "manifest_bytes": 16 * 1024,
    "document_bytes": 1024**2,
    "submission_bytes": 4 * 1024**2,
    "parse_seconds": 10,
    "parse_memory_bytes": 512 * 1024**2,
}
FAILED_INFRA = "FAILED_INFRA"


class IntakeBlocked(RuntimeError):
    """A bound is unset (HUMAN_INPUT): intake cannot run, and nothing is
    refused on the submission's account."""


class IntakeInfraFailure(RuntimeError):
    """Carbon's own infrastructure failed (`FAILED_INFRA`): never a refusal."""

    kind = FAILED_INFRA


def _bounds(bounds):
    merged = {**BOUNDS, **(bounds or {})}
    unset = sorted(k for k, v in merged.items() if v == HUMAN_INPUT or v is None)
    if unset:
        raise IntakeBlocked("unset intake bounds: " + ", ".join(unset))
    return merged


def _sizes(raw_manifest, files, bounds):
    if len(raw_manifest) > bounds["manifest_bytes"]:
        raise graph.GraphRefused("oversized_manifest")
    for raw in files.values():
        if len(raw) > bounds["document_bytes"]:
            raise graph.GraphRefused("oversized_document")
    if (
        len(raw_manifest) + sum(len(r) for r in files.values())
        > bounds["submission_bytes"]
    ):
        raise graph.GraphRefused("oversized_submission")


def _isolated_parse(
    raw_manifest, files, *, allowlist, challenge, interface, bounds, worker
):
    request = json.dumps(
        {
            "manifest": base64.b64encode(raw_manifest).decode(),
            "files": {k: base64.b64encode(v).decode() for k, v in files.items()},
            "allowlist": base64.b64encode(allowlist.raw).decode(),
            "challenge": challenge,
            "interface": interface,
            "max_bytes": bounds["document_bytes"],
            "cpu_seconds": bounds["parse_seconds"],
            "memory_bytes": bounds["parse_memory_bytes"],
        }
    ).encode()
    root = str(Path(__file__).resolve().parents[2])
    environment = {"PATH": "/usr/bin:/bin", "PYTHONPATH": root, "LC_ALL": "C.UTF-8"}
    try:
        done = subprocess.run(
            worker or [sys.executable, "-m", "carbon.level4._parse_worker"],
            input=request,
            capture_output=True,
            env=environment,
            cwd=os.path.dirname(root) or "/",
            timeout=bounds["parse_seconds"] * 2 + 5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise graph.GraphRefused("parse_deadline") from None
    except OSError as failure:
        raise IntakeInfraFailure(
            f"parse worker did not start: {type(failure).__name__}"
        ) from None
    lines = done.stdout.decode(errors="replace").strip().splitlines()
    try:
        answer = json.loads(lines[-1]) if lines else None
    except ValueError:
        answer = None
    if done.returncode == 0 and isinstance(answer, dict):
        if answer.get("state") == FAILED_INFRA:
            raise IntakeInfraFailure("parse worker could not run its checks")
        if answer.get("refused"):
            raise graph.GraphRefused(str(answer["refused"]), "isolated parse")
        if answer.get("ok") is True:
            return
    # A signal (CPU limit), a memory failure or a crash: the submission's.
    raise graph.GraphRefused("parse_resource_limit")


def intake(
    raw_manifest,
    files,
    *,
    allowlist,
    challenge,
    interface,
    bounds=None,
    isolate=True,
    worker=None,
    loss_override=None,
):
    """G0 and G3 for one submission: `(manifest, {slot: document})`.

    A loss document is refused unless the Challenge declares
    `loss_override: graph` (`loss.gate`); never ignored.
    `worker` replaces the isolated parser's command (tests only)."""
    from . import loss as loss_slot

    bounds = _bounds(bounds)
    if type(raw_manifest) is not bytes or type(files) is not dict:
        raise graph.GraphRefused("intake_malformed")
    if not all(type(k) is str and type(v) is bytes for k, v in files.items()):
        raise graph.GraphRefused("intake_malformed")
    _sizes(raw_manifest, files, bounds)
    if isolate:
        _isolated_parse(
            raw_manifest,
            files,
            allowlist=allowlist,
            challenge=challenge,
            interface=interface,
            bounds=bounds,
            worker=worker,
        )
    manifest, parsed = submission.verify(
        raw_manifest,
        files,
        allowlist=allowlist,
        challenge=challenge,
        interface=interface,
        max_bytes=bounds["document_bytes"],
    )
    loss_slot.gate(parsed, loss_override)
    return manifest, parsed
