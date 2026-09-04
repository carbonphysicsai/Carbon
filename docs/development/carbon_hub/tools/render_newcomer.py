"""Compatibility entry point for newcomer-aware Hub generation.

The newcomer projection is part of the normal deterministic Hub build. This
entry point delegates to ``render_hub.py`` so the Overview cannot drift into a
separately generated product.
"""

from __future__ import annotations

import argparse

from render_hub import DATA_PATH, EVENTS_PATH, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return run(
        check=args.check,
        data_path=DATA_PATH.resolve(),
        events_path=EVENTS_PATH.resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
