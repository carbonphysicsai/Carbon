"""Replay eight existing public f02 triage tuples; no new contexts or solves."""

import argparse
import json
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet, panel, panel_diff

ROOT = Path(__file__).resolve().parents[3]
SOURCE = "docs/development/challenge_pipeline/round1/reference-route-panels.json"
OUT = ROOT / "docs/development/challenge_pipeline/panel-diffs/f02-existing-public.json"


def build():
    raw = packet.source_path(ROOT, SOURCE).read_bytes()
    family = json.loads(raw)["families"]["f02"]
    brief = packet.read_json(
        ROOT
        / "docs/development/challenge_pipeline/onboarding-runs/generated/f02/brief.json"
    )
    draft = packet.generate(brief, ROOT)
    results = []
    for row in family["public_cases"]:
        params = dict(zip(family["panel_fields"], row["parameters"], strict=True))
        seed = {
            "schema": panel.SCHEMA,
            "challenge": "f02",
            "designs": [
                {
                    "id": row["label"],
                    "coordinates": {
                        k: params[k] for k in ("waveform", "peak_w", "on_time_s")
                    },
                }
            ],
            "strata": [
                {
                    "id": row["bank"],
                    "inputs": {
                        k: params[k]
                        for k in (
                            "coolant_c",
                            "h_w_m2_k",
                            "initial_c",
                            "left_source_fraction",
                        )
                    },
                }
            ],
            "rungs": [
                {
                    "id": "proposed-standard",
                    "settings": {"mesh_level": 1, "dt_scale": 1},
                }
            ],
            "pins": {k: None for k in panel.PIN_KEYS},
            "cost_cpu_seconds": {},
        }
        results.append(panel_diff.generate(draft, seed=seed))
    return {
        "scope": "PUBLIC_DEVELOPMENT_PREPARATION_ONLY",
        "source": SOURCE,
        "source_sha256": packet.digest(raw),
        "existing_public_tuples": len(results),
        "rung_basis": "Proposed standard settings from f02 deck; adequacy/pins not accepted by this tool",
        "inventory_basis": "No complete public completed/scheduled inventory supplied; do not assume no reuse",
        "results": results,
        "registration_adopted": False,
        "solver_runs": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if OUT.read_text(encoding="utf-8") != rendered:
            parser.exit(1, "Public panel diff differs\n")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        "8 existing public f02 tuples; pins/inventory unknown, no registration or dispatch"
    )


if __name__ == "__main__":
    main()
