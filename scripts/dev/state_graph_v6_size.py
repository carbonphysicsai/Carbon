"""Accounting-v6 size of the frozen forward graph in catalog build outputs. Read-only.

Usage: python scripts/dev/state_graph_v6_size.py PATH [PATH ...]

A PATH is a ``state.npz`` (`bundle_graph_state.freeze`) or a directory searched for
them. Prints one line per state: ``under|OVER  v6=<bytes>  <path>`` against the served
cap (`allowlist.CAPS["constant_bytes"]`, 16384). A build the cap refuses at freeze writes
no state, only ``refusal.json`` with code ``bundle_graph_caps_refused``; such a directory
is printed ``OVER (refused at freeze)``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph

CAP = allowlist_module.CAPS["constant_bytes"]


def measure(state_path) -> int:
    with np.load(state_path, allow_pickle=False) as archive:
        raw = bytes(archive["graph"].tobytes())
    return graph.recipe_info_bytes(json.loads(raw))


def main(argv):
    rows = 0
    for argument in argv:
        root = Path(argument)
        states = [root] if root.is_file() else sorted(root.rglob("state.npz"))
        for state in states:
            size = measure(state)
            rows += 1
            print(f"{'OVER ' if size > CAP else 'under'}  v6={size:>8}  {state}")
        if root.is_dir():
            for refusal in sorted(root.rglob("refusal.json")):
                if json.loads(refusal.read_bytes()).get("code") == (
                    "bundle_graph_caps_refused"
                ):
                    rows += 1
                    print(f"OVER   (refused at freeze)  {refusal.parent}")
    print(f"rows={rows} cap={CAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
