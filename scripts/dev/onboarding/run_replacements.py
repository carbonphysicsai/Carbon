"""Three explicit replacement briefs; draft tools only, no input discovery."""

import argparse
import json
from pathlib import Path

from carbon.challenge_pipeline.onboarding import law, packet, panel, status
from scripts.dev.onboarding.run_remaining import build_brief, write_batch

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = "docs/development/challenge_pipeline/replacement-onboarding"
SOURCES = DIRECTORY + "/run-sources.json"
BINDINGS = DIRECTORY + "/artifacts.json"
OUTPUT = DIRECTORY + "/generated"
CHALLENGES = frozenset(("solenoid-pole", "bolted-joint", "seal-gland"))


def generate(root=ROOT):
    config = packet.read_json(packet.source_path(root, SOURCES))
    entries = config.get("entries", [])
    if (
        config.get("schema") != "carbon.onboarding.replacement-application.v1"
        or type(entries) is not list
        or len(entries) != 3
        or any(type(row) is not dict for row in entries)
        or {row.get("challenge") for row in entries} != CHALLENGES
    ):
        raise packet.DraftError("three explicit replacement briefs required")
    results = {}
    for entry in entries:
        intake_path = entry["intake"]
        intake = packet.read_json(packet.source_path(root, intake_path))
        if (
            intake.get("schema") != "carbon.onboarding.replacement-intake.v1"
            or intake.get("challenge") != entry["challenge"]
            or intake.get("disposition") != "HOLD_OPEN_SET_NOT_CONFIRMED"
            or intake.get("run_authorized") is not False
        ):
            raise packet.DraftError("matching held replacement intake required")
        brief = build_brief(root, entry)
        draft = packet.generate(brief, root)
        results[entry["challenge"]] = {
            "brief": brief,
            "packet": draft,
            "law": law.generate(draft),
            "panel": panel.generate(draft),
            "status": status.generate(root, entry["challenge"], bindings_path=BINDINGS),
            "intake": intake,
            "basis": [
                {
                    "path": name,
                    "sha256": packet.digest(
                        packet.source_path(root, name).read_bytes()
                    ),
                }
                for name in [entry["packet"], intake_path, *entry["evidence"], BINDINGS]
            ],
            "limits": {
                "solved_export_supplied": False,
                "numeric_panel_seed_supplied": False,
                "reuse_receipts_supplied": False,
                "solver_runs": 0,
                "spend": 0,
                "stage_exits_verified": False,
            },
        }
    return results


def write(root, results):
    if set(results) != CHALLENGES:
        raise packet.DraftError("three explicit replacement results required")
    return write_batch(root, results, source=SOURCES, output=OUTPUT)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="retain only these development drafts"
    )
    args = parser.parse_args(argv)
    results = generate()
    if args.write:
        manifest = write(ROOT, results)
        print(
            f"{len(manifest['challenges'])} held replacement draft sets retained; no run or stage acceptance"
        )
    else:
        print(
            json.dumps(
                {key: row["intake"]["disposition"] for key, row in results.items()},
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
