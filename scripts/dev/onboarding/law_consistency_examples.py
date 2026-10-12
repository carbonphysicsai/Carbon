"""Reviewed packet-to-law projections for three existing public Challenges."""

import argparse
import json
from pathlib import Path

from carbon.challenge_pipeline.onboarding import law_consistency as lc
from carbon.challenge_pipeline.onboarding import packet

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/development/challenge_pipeline/law-consistency"
PACKETS = "docs/development/challenge_pipeline/round1/"
LAWS = "docs/development/challenge_pipeline/question-laws/"


def row(id_, facet, expected, excerpt, pointer):
    return {
        "id": id_,
        "facet": facet,
        "packet_value": expected,
        "excerpt": excerpt,
        "law_pointer": pointer,
    }


def specs():
    return [
        (
            "battery-v3",
            "battery-ambient-map-v3.md",
            "battery-v3-round2.json",
            [
                row(
                    "charging-limit",
                    "hard_limits",
                    45,
                    "Hard\ncharging T<=45 C",
                    "/hard_anchor_limits/charging_temperature_max_c",
                ),
                row(
                    "plating-limit",
                    "hard_limits",
                    0,
                    "every-charge plating overpotential>=0 V",
                    "/hard_anchor_limits/every_charge_plating_min_v",
                ),
                row(
                    "voltage-limit",
                    "hard_limits",
                    4.2,
                    "programme\nvoltage<=4.2 V",
                    "/hard_anchor_limits/programme_voltage_max_v",
                ),
                row(
                    "retention",
                    "hard_limits",
                    0.99,
                    "Q30/Q1>=0.99",
                    "/hard_anchor_limits/q30_over_q1_min",
                ),
                row(
                    "time-not-cap",
                    "objective",
                    None,
                    "There is no\n30-minute cutoff.",
                    "/hard_anchor_limits/hard_session_time_cap",
                ),
                row(
                    "discharge-scope",
                    "observer_scope",
                    "DIAGNOSTIC",
                    "Discharge and rest\ntemperatures are diagnostics.",
                    "/hard_anchor_limits/discharge_thermal_role",
                ),
                row(
                    "population-unapproved",
                    "P",
                    None,
                    "remain HUMAN_INPUT, not measured fleet frequencies.",
                    "/registered_P",
                ),
                row(
                    "diagnostic-no-redraw",
                    "Q",
                    False,
                    "NONE_FEASIBLE and cannot be replaced with a favorable new draw.",
                    "/Q_recommendation/redraw_none_feasible",
                ),
                row(
                    "band-mix",
                    "w",
                    "OWNER_SELECTED_BUYER_MIX",
                    "owner selects `w_band=buyer_mix`",
                    "/w/band_value",
                ),
                row(
                    "none-feasible-no-redraw",
                    "NONE_FEASIBLE",
                    False,
                    "NONE_FEASIBLE and cannot be replaced with a favorable new draw.",
                    "/question/none_feasible_policy/redraw",
                ),
            ],
        ),
        (
            "motor",
            "motor-precision-joint-v2.md",
            "motor-round2.json",
            [
                row(
                    "holding-floor",
                    "hard_limits",
                    6,
                    "Holding mean ≥6 N·m",
                    "/requirements/0/anchor",
                ),
                row(
                    "peak-floor",
                    "hard_limits",
                    12,
                    "**12 N·m for a 2-s acceleration",
                    "/requirements/1/anchor",
                ),
                row(
                    "cogging",
                    "hard_limits",
                    0.05,
                    "Zero-current cogging peak-to-peak ≤0.05 N·m",
                    "/requirements/4/anchor",
                ),
            ],
        ),
        (
            "f02",
            "f02-burst-thermal.md",
            "f02-round2.json",
            [
                row(
                    "temperature-anchor",
                    "hard_limits",
                    95,
                    "**95 °C over 120 s**",
                    "/hard_temperature_anchor_c",
                ),
                row(
                    "context-count",
                    "P",
                    24,
                    "uniform over 24 exogenous strata",
                    "/context_count",
                ),
            ],
        ),
    ]


def build():
    outputs = {}
    for family, filename, lawname, checks in specs():
        source_path = PACKETS + filename
        raw = packet.source_path(ROOT, source_path).read_bytes()
        text = raw.decode()
        lawpath = LAWS + lawname
        law = packet.read_json(packet.source_path(ROOT, lawpath))
        bindings = []
        for item in checks:
            item = dict(item)
            excerpt = item.pop("excerpt")
            # Explicit retained prose quotes; no NLP authority selection.
            # A whitespace-only authored line-wrap is retained from actual bytes.
            if excerpt not in text:
                import re

                match = re.search(
                    r"\s+".join(re.escape(w) for w in excerpt.split()),
                    text,
                    re.IGNORECASE,
                )
                if match is None:
                    raise packet.DraftError("reviewed packet excerpt missing")
                excerpt = match[0]
            item["packet_source"] = {
                "path": source_path,
                "sha256": packet.digest(raw),
                "excerpt": excerpt,
            }
            bindings.append(item)
        spec = {
            "schema": lc.SCHEMA,
            "challenge": family,
            "law": {
                "path": lawpath,
                "schema": law["schema"],
                "sha256": packet.digest(packet.source_path(ROOT, lawpath).read_bytes()),
            },
            "checks": bindings,
        }
        report = lc.check(ROOT, spec)
        outputs[family + "-bindings.json"] = (
            json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
        )
        outputs[family + "-report.json"] = (
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in outputs.items():
        path = OUT / name
        if args.check:
            if path.read_text(encoding="utf-8") != text:
                parser.exit(1, "Law consistency example differs: " + name + "\n")
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
    print("3 public packet/law examples; 15 projections; unbound facets remain open")


if __name__ == "__main__":
    main()
