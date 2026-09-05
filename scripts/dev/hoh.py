#!/usr/bin/env python3
"""Repository entry point for the bounded B-01H development controller."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from agent_pack.executors.hoh.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
