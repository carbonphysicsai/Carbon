"""Build a separate authored Julia image from an existing exact worker manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from carbon.development_session.julia_analysis import (
    authored_julia_scope,
    build_julia_analysis_image,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    image = build_julia_analysis_image(args.parent_manifest, args.root)
    print(
        json.dumps(
            {
                "manifest": str(
                    args.root / image.runtime_digest[7:] / "julia-analysis-image.json"
                ),
                "runtime_authored_research": [authored_julia_scope(image)],
                "next": (
                    "Put runtime_authored_research in your runner profile's "
                    "runtime and this manifest path in authored_julia_image. "
                    "No grant is needed; building grants nothing by itself."
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
