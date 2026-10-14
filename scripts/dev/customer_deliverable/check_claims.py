"""Check published development claims against registered current public artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .claims import check_inventory, check_package_outputs, parse_json, require_pass
from .generate import GitReader, load_policy

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "Business/research/deliverable-generator/claim-inventory.json"


def check_presentations(reader, inventory=None):
    if inventory is None:
        inventory = parse_json(INVENTORY.read_text(encoding="utf-8"))

    def read(path):
        source = reader.get({"id": "CLAIM", "path": path})
        return None if source is None else source.text.encode("utf-8")

    return check_inventory(inventory, read)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="current commit to check; never selected by the old output",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="previously generated public generation-manifest.json",
    )
    args = parser.parse_args(argv)
    reader = GitReader(args.repo_root, args.ref, args.ref)
    try:
        reports = [check_presentations(reader)]
        if args.manifest is not None:
            if any(
                parent.is_symlink()
                for parent in [args.manifest, *args.manifest.parents]
            ):
                raise ValueError("claim manifest must not be a symlink")
            manifest = parse_json(args.manifest.read_text(encoding="utf-8"))
            outputs = {}
            for name in ("sample.md", "sample.json", "deliverable.schema.json"):
                path = args.manifest.parent / name
                if path.is_symlink():
                    raise ValueError(
                        f"Claim citation FAIL: package.output.{name}: {name}: symlink refused"
                    )
                outputs[name] = path.read_text(encoding="utf-8")
            reports.append(
                check_package_outputs(manifest, outputs, reader, load_policy())
            )
        for report in reports:
            require_pass(report)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "basis": "ARTIFACT_TRACEABILITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE",
                    "reports": reports,
                },
                indent=2,
            )
        )
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
        parser.exit(2, f"Claim check refused: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
