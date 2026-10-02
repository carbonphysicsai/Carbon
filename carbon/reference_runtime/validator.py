"""Resource-bounded native validator for one C-04 output snapshot."""

from __future__ import annotations

import json
import resource
import sys
from pathlib import Path

from carbon.reconstruction.worker.model import (
    VALIDATION_CPU_SECONDS,
    VALIDATION_MEMORY_BYTES,
    VALIDATION_NOFILE_LIMIT,
    WorkerFailure,
)
from carbon.reference_runtime.protocol import (
    load_staged_reference_request,
    validate_reference_snapshot,
)


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(
        resource.RLIMIT_NOFILE, (VALIDATION_NOFILE_LIMIT, VALIDATION_NOFILE_LIMIT)
    )
    resource.setrlimit(
        resource.RLIMIT_CPU, (VALIDATION_CPU_SECONDS, VALIDATION_CPU_SECONDS)
    )
    if hasattr(resource, "RLIMIT_AS"):
        try:
            resource.setrlimit(
                resource.RLIMIT_AS,
                (VALIDATION_MEMORY_BYTES, VALIDATION_MEMORY_BYTES),
            )
        except ValueError:
            # Darwin exposes RLIMIT_AS but does not accept a finite value.  The
            # native path remains diagnostic; required Linux acceptance must
            # enforce this limit and does not take this branch.
            if sys.platform != "darwin":
                raise


def main(arguments: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if len(values) != 2:
        return 2
    try:
        _limits()
        snapshot, stage = (Path(item).resolve(strict=True) for item in values)
        request = load_staged_reference_request(stage)
        result = validate_reference_snapshot(snapshot, request)
        sys.stdout.write(
            json.dumps(
                {
                    "request_digest": result.request_digest,
                    "role": result.role.value,
                    "outcome": result.outcome.value,
                    "failure_reason": (
                        None
                        if result.failure_reason is None
                        else result.failure_reason.value
                    ),
                    "artifact_digest": result.artifact_digest,
                    "artifact_bytes": result.artifact_bytes,
                    "shape": None if result.shape is None else list(result.shape),
                    "diagnostics": [list(item) for item in result.diagnostics],
                    "eligible_for_truth_or_score": False,
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        return 0
    except (OSError, ValueError, WorkerFailure):
        return 20
    except Exception:  # noqa: BLE001 - do not expose parser diagnostics.
        return 21


if __name__ == "__main__":
    raise SystemExit(main())
