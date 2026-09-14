"""Separate bounded native-array validator for C-05 worker output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .protocol import validate_measurement_snapshot


def main(arguments: list[str] | None = None) -> int:
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 2:
        return 2
    try:
        result = validate_measurement_snapshot(Path(values[0]), Path(values[1]))
        print(json.dumps(result.document(), sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:  # noqa: BLE001 - closed non-echoing validator failure.
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
