"""Static preflight for a copied CONFIRM-02 operator sheet.

This never runs a sheet command, touches a host, draws a question, or reads a
sealed work directory. It catches stale release pins before the owner sees it.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TAG = "producer-code-r8.6"
COMMIT = "e9a28008b3975c3aaa93b710b6f623221241c2eb"
CLONE = "/opt/carbon-r86"
WATCHDOG_SHA = "eba55521a397574560e75ee50be6ad2b625f737a11d44568d00436c093bc90e8"


class SheetRefused(ValueError):
    """A copied sheet is stale or omits a fail-closed preflight check."""


def inspect(text: str) -> dict[str, object]:
    if not isinstance(text, str) or not text:
        raise SheetRefused("empty_sheet")
    stale = sorted(
        set(re.findall(r"\b(?:r8[._-]?[345]|R8[345]|carbon-r8[345])\b", text))
    )
    if stale:
        raise SheetRefused("stale_release_pin")
    required = {
        "tagged_clone": f"--branch {TAG}",
        "clone_path": f"R={CLONE}; cd $R",
        "exact_commit_guard": f'test "$(git -C {CLONE} rev-parse HEAD)" = {COMMIT}',
        "watchdog_hash_guard": f"sha256sum scripts/dev/battery/pod_watchdog.py                           # must be {WATCHDOG_SHA}",
        "three_shards": "--shards 3",
        "public_dry_question": "public_dev_questions draw --work $WD --questions 1",
        "one_final_look": "--phase confirmation --look final",
    }
    missing = [name for name, fragment in required.items() if fragment not in text]
    if missing:
        raise SheetRefused("missing_sheet_guards:" + ",".join(missing))
    return {
        "status": "STATIC_PREFLIGHT_ONLY",
        "release_tag": TAG,
        "release_commit": COMMIT,
        "checked_guards": sorted(required),
        "checked_count": len(required),
        "host_execution": "NOT_RUN",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(inspect(args.sheet.read_text(encoding="utf-8")), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
