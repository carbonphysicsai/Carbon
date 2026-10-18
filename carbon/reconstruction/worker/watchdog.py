"""Detached trusted deadline reaper for one exact C-03 launch."""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    _canonical,
    remove_exact_container,
)
from carbon.reconstruction.worker.model import WorkerFailure, tagged_sha256


def _retain_deadline_request(intent_path, container_name, launch_digest, deadline):
    """Private trigger evidence; failure cannot prevent existing owned cleanup."""
    try:
        path = Path(intent_path)
        if (
            type(deadline) is not float
            or not math.isfinite(deadline)
            or not path.is_absolute()
            or path.name != "intent.json"
            or path.parent.name != "operation-" + launch_digest[7:]
            or path.resolve(strict=True) != path
            or not 0 < path.stat().st_size <= 65536
        ):
            return
        with path.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return
        intent = json.loads(raw)
        if (
            type(intent) is not dict
            or intent.get("launch") != launch_digest
            or intent.get("container") != container_name
            or container_name != "carbon-d4-" + launch_digest[7:31]
            or intent.get("deadline_unix") != deadline
            or tagged_sha256(
                _canonical(
                    {key: intent[key] for key in ("owner", "identity", "request")}
                )
            )
            != launch_digest
            or intent["request"].get("provenance") != "DIRECT_BUNDLE_DEPENDENCY_PREP"
        ):
            return
        record = _canonical(
            {
                "schema": "carbon.autoresearch.watchdog-observation.v1",
                "launch_digest": launch_digest,
                "observed_unix": time.time(),
                "deadline_unix": deadline,
                "action": "DEADLINE_CLEANUP_REQUESTED",
                "interpretation": "Request observed; cleanup outcome is separate.",
            }
        )
        if len(record) > 4096:
            return
        target = path.parent / "private-watchdog-observation.json"
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(record)
    except Exception:  # noqa: BLE001, S110 - a missing observation remains unknown
        pass


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(arguments) not in (3, 4):
        return 2
    container_name, launch_digest, raw_deadline = arguments[:3]
    intent_path = arguments[3] if len(arguments) == 4 else None
    try:
        deadline = float(raw_deadline)
    except ValueError:
        return 2
    cli = DockerCLI()
    while time.time() < deadline:
        probe = cli.run(["inspect", container_name], timeout=5, accepted=(0, 1))
        if probe.returncode != 0:
            return 0
        time.sleep(min(1.0, max(0.05, deadline - time.time())))
    if intent_path is not None:
        try:
            _retain_deadline_request(
                intent_path, container_name, launch_digest, deadline
            )
        except Exception:  # noqa: BLE001, S110 - observation never gates cleanup
            pass
    try:
        remove_exact_container(
            cli=cli, container_name=container_name, launch_digest=launch_digest
        )
    except WorkerFailure:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
