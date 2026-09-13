"""Owner-facing local doctor/status/reconciliation commands for C-03."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from carbon.execution import DurableWorkerLaunchStore
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    doctor,
    load_image_identity,
    remove_exact_container,
)
from carbon.reconstruction.worker.model import WorkerFailure


def _stores(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(sorted(root.rglob("launches.sqlite3")))


def _doctor(manifest: Path) -> int:
    image = load_image_identity(manifest)
    result = doctor(image_id=image.image_id, image_identity=image)
    print(
        json.dumps(
            {
                "eligible": result.eligible,
                "code": result.code,
                "cpuset": result.cpuset,
                "host": result.host,
                "image_id": image.image_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if result.eligible else 2


def _status(root: Path) -> int:
    values = []
    for path in _stores(root):
        store = DurableWorkerLaunchStore(path)
        values.extend({"store": str(path), **item} for item in store.all_statuses())
    print(json.dumps(values, sort_keys=True, separators=(",", ":")))
    return 0


def _reconcile(root: Path) -> int:
    cli = DockerCLI()
    outcomes = []
    failed = False
    for path in _stores(root):
        store = DurableWorkerLaunchStore(path)
        for item in store.reconciliation_targets():
            cleaned = True
            try:
                remove_exact_container(
                    cli=cli,
                    container_name=item["container_name"],
                    launch_digest=item["launch_digest"],
                )
            except WorkerFailure:
                cleaned = False
                failed = True
            state = store.record_operator_cleanup(
                execution_id=item["execution_id"],
                launch_digest=item["launch_digest"],
                cleaned=cleaned,
            )
            outcomes.append(
                {
                    "store": str(path),
                    "execution_id": item["execution_id"],
                    "cleaned": cleaned,
                    "state": state.value,
                }
            )
    print(json.dumps(outcomes, sort_keys=True, separators=(",", ":")))
    return 3 if failed else 0


def _parse(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("manifest", type=Path)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("state_root", type=Path)
    reconcile_parser = subparsers.add_parser("reconcile")
    reconcile_parser.add_argument("state_root", type=Path)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    parsed = _parse(arguments)
    if parsed.command == "doctor":
        return _doctor(parsed.manifest)
    if parsed.command == "status":
        return _status(parsed.state_root)
    if parsed.command == "reconcile":
        return _reconcile(parsed.state_root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
