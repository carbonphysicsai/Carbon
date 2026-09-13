"""Fixed resource-bounded native artifact-validation child for C-03."""

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
    tagged_sha256,
)
from carbon.reconstruction.worker.protocol import (
    load_worker_request,
    validate_snapshot,
    validated_receipt_payload,
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
        resource.setrlimit(
            resource.RLIMIT_AS, (VALIDATION_MEMORY_BYTES, VALIDATION_MEMORY_BYTES)
        )


def main(arguments: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if len(values) != 2:
        return 2
    try:
        _limits()
        snapshot, stage = (Path(item).resolve(strict=True) for item in values)
        execution_ref, plan, training_archive, seed, _ = load_worker_request(stage)
        receipt = validate_snapshot(
            snapshot,
            execution_ref=execution_ref,
            plan=plan,
            training_archive=training_archive,
            randomness_digest=tagged_sha256(seed.as_backend_bytes()),
        )
        sys.stdout.buffer.write(
            json.dumps(
                validated_receipt_payload(receipt),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        return 0
    except (OSError, ValueError, WorkerFailure):
        return 20
    except Exception:  # noqa: BLE001 - never expose native parser diagnostics.
        return 21


if __name__ == "__main__":
    raise SystemExit(main())
