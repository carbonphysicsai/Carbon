"""Detached trusted deadline reaper for one exact C-03 launch."""

from __future__ import annotations

import sys
import time

from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    remove_exact_container,
)
from carbon.reconstruction.worker.model import WorkerFailure


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(arguments) != 3:
        return 2
    container_name, launch_digest, raw_deadline = arguments
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
    try:
        remove_exact_container(
            cli=cli, container_name=container_name, launch_digest=launch_digest
        )
    except WorkerFailure:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
