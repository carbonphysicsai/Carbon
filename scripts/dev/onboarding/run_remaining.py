"""Apply the four offline draft tools; no solvers, providers or panel discovery."""

import argparse
import json
import re
from pathlib import Path

from carbon.challenge_pipeline.onboarding import law, packet, panel, status

ROOT = Path(__file__).resolve().parents[3]
SOURCES = "docs/development/challenge_pipeline/onboarding-runs/run-sources.json"
OUTPUT = "docs/development/challenge_pipeline/onboarding-runs/generated"
CHALLENGES = frozenset(
    ("cooling-cell", "f02", "f06", "f08", "f13", "f17", "solenoid-pole", "seal-gland")
)
SECTION_FIELDS = {
    1: ("value", "wrong_decision"),
    2: ("geometry", "materials", "conditions"),
    3: ("P", "Q", "w", "strata"),
    4: ("case_identity", "disclosure"),
    5: ("solver", "pins", "refinement", "uncertainty", "cost"),
    6: ("outputs", "hard_limits", "objective"),
    7: ("vocabulary", "permissions"),
    8: ("public_kit", "baseline"),
    9: ("panel", "controls"),
    10: ("readiness", "owners", "next_gate"),
}


def build_brief(root, entry):
    target = packet.source_path(root, entry["packet"])
    raw = target.read_bytes()
    text = raw.decode("utf-8")
    brief = {
        "schema": packet.SCHEMA,
        **{
            key: entry[key]
            for key in ("challenge", "buyer", "decision", "physics", "solver")
        },
        "fields": {},
    }
    sections = re.split(r"^## (\d+)\. [^\n]*\n", text, flags=re.MULTILINE)
    for i in range(1, len(sections), 2):
        number = int(sections[i])
        # Full retained section excerpt, bounded to the tool's text limit. This
        # proves bytes, not that each field has an accepted numeric binding.
        excerpt = sections[i + 1].strip()[:6000]
        if not excerpt:
            continue
        for field in SECTION_FIELDS.get(number, ()):
            brief["fields"][field] = {
                "value": excerpt,
                "sources": [
                    {
                        "path": entry["packet"],
                        "sha256": packet.digest(raw),
                        "excerpt": excerpt,
                    }
                ],
            }
    return brief


def generate(root=ROOT):
    config = packet.read_json(packet.source_path(root, SOURCES))
    entries = config.get("entries", [])
    if (
        config.get("schema") != "carbon.onboarding.application-batch.v1"
        or type(entries) is not list
        or len(entries) != 8
        or any(type(entry) is not dict for entry in entries)
        or {entry.get("challenge") for entry in entries} != CHALLENGES
    ):
        raise packet.DraftError("eight explicit application briefs required")
    results = {}
    for entry in entries:
        brief = build_brief(root, entry)
        draft = packet.generate(brief, root)
        proposal = (
            packet.read_json(packet.source_path(root, entry["law"]))
            if entry.get("law")
            else None
        )
        results[entry["challenge"]] = {
            "brief": brief,
            "packet": draft,
            "law": law.generate(draft, law_source=proposal),
            "panel": panel.generate(draft),
            "status": status.generate(root, entry["challenge"]),
            "basis": [
                {
                    "path": name,
                    "sha256": packet.digest(
                        packet.source_path(root, name).read_bytes()
                    ),
                }
                for name in [
                    entry["packet"],
                    *entry["evidence"],
                    *([entry["law"]] if entry.get("law") else []),
                ]
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
        raise packet.DraftError("eight explicit application results required")
    root = root.resolve()
    destination = (root / OUTPUT).resolve()
    if not destination.is_relative_to(root):
        raise packet.DraftError("application output outside repository")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "carbon.onboarding.application-run.v1",
        "input_sha256": packet.digest((root / SOURCES).read_bytes()),
        "basis": status.git_basis(root),
        "drafts_not_adoption": True,
        "challenges": {},
    }
    for challenge, result in results.items():
        folder = (destination / challenge).resolve()
        if not folder.is_relative_to(destination):
            raise packet.DraftError("application output outside ticket directory")
        folder.mkdir(exist_ok=True)
        files = {}
        for kind, body in result.items():
            if kind not in {
                "brief",
                "packet",
                "law",
                "panel",
                "status",
                "basis",
                "limits",
            }:
                raise packet.DraftError("known application output required")
            target = folder / (kind + ".json")
            if not target.resolve().is_relative_to(destination):
                raise packet.DraftError("application output outside ticket directory")
            raw = (
                json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n"
            ).encode("utf-8")
            target.write_bytes(raw)
            files[kind] = {
                "path": target.relative_to(root).as_posix(),
                "sha256": packet.digest(raw),
            }
        target = folder / "packet.md"
        if not target.resolve().is_relative_to(destination):
            raise packet.DraftError("application output outside ticket directory")
        raw = packet.render(result["packet"]).encode("utf-8")
        target.write_bytes(raw)
        files["packet_markdown"] = {
            "path": target.relative_to(root).as_posix(),
            "sha256": packet.digest(raw),
        }
        manifest["challenges"][challenge] = files
    target = destination / "manifest.json"
    if not target.resolve().is_relative_to(destination):
        raise packet.DraftError("application output outside ticket directory")
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="retain only this ticket's generated development drafts",
    )
    args = parser.parse_args(argv)
    results = generate()
    if args.write:
        manifest = write(ROOT, results)
        print(
            f"{len(manifest['challenges'])} four-tool draft sets retained; no stage exit or run authorization"
        )
    else:
        print(
            json.dumps(
                {key: value["limits"] for key, value in results.items()}, sort_keys=True
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
