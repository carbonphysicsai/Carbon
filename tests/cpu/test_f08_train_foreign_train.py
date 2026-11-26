"""A registered F08 version whose TRAIN another module serves never breaks `f08_train`'s import (blind-audit row 1).

Before: `f08_train.TRAIN_FOR_VERSION` was built at import by indexing a two-name table with every registered F08
version's TRAIN name, so registering a later F08 version whose TRAIN another module serves raised a KeyError
at import. `physical_material` imports `f08_train`, and the receiver imports `physical_material`, so one overlay row
would have stopped every door on that host, the live ones included. Now the table holds only the versions whose TRAIN
this loader serves, and `load_public_train` refuses any other version typed.

The F08 version here is registered ONLY through a temporary host overlay, in a fresh interpreter; its number is
synthetic (no code names it).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
VERSION = "9.9"
ENTRY = {
    "challenge_id": "f08-ribbed-bracket",
    "version": VERSION,
    "train": "f08-dev-train-9p9-v9",
    "allowlist": "v8",
    "step_caps": False,
    "pack_version": "f08-normal-construction-development-synthetic-9",
    "development_evaluation": None,
    "sealed_evaluation": None,
    "campaign": "catalog",
    "catalog": True,
    "graph_adapter": "v2",
    "catalog_entries_from": [],
    "predecessor": None,
    "rebuild_wall_seconds": 648,
}

_PROGRAM = r"""
import json, sys
from pathlib import Path
from carbon.challenge_kit import version_overlay, version_registry
version_overlay.install(path=Path(sys.argv[1]))
version = sys.argv[2]
from carbon.challenge_kit import f08_train, physical_material  # the import that used to raise
out = {
    "registered": version in f08_train.CHALLENGE_VERSIONS,
    "in_table": version in f08_train.TRAIN_FOR_VERSION,
    "table": sorted(f08_train.TRAIN_FOR_VERSION.items()),
    "served": sorted(
        v for v in f08_train.CHALLENGE_VERSIONS
        if version_registry.entry(f08_train.CHALLENGE_ID, v).train
        in (version_registry.F08_TRAIN_V1, version_registry.F08_TRAIN_V2)
    ),
}
try:
    f08_train.load_public_train(version)
    out["load"] = "loaded"
except ValueError as refused:
    out["load"] = str(refused)
print(json.dumps(out))
"""


def test_a_foreign_train_version_imports_and_refuses_typed(tmp_path):
    path = tmp_path / "version_overlay.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.challenge-kit.version-overlay.v1",
                "versions": {f"f08-ribbed-bracket {VERSION}": ENTRY},
            }
        ),
        encoding="utf-8",
    )
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM, str(path), VERSION],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["registered"] is True
    assert out["in_table"] is False
    assert out["load"] == "unknown public f08 TRAIN version"
    # every version this loader serves is still in the table, with its own TRAIN
    assert [version for version, _train in out["table"]] == out["served"]
    assert {train for _version, train in out["table"]} <= {"v1", "v2"}
