"""Generate/replay public buyer-clause manifests and checklists; no science runs."""

import argparse
import json
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet, reconcile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/development/challenge_pipeline/packet-reconcile"
PREFIX = "docs/development/challenge_pipeline/round1/"
OWNER = ".agent/decisions/2026-10-08-OWNER-BATTERY-AMBIENT-MAP-03.md"
FIRST = ".agent/decisions/2026-10-07-OWNER-FIRST-THREE-CUSTOMER-ROUND-01.md"
COOLING = ".agent/decisions/2026-10-08-OWNER-DESIGN-VALUE-01.md"


def number(document, prefix, suffix, section=None):
    return {
        "document": document,
        "kind": "number",
        "section": section,
        "prefix": prefix,
        "suffix": suffix,
    }


def literal(document, phrase, value, section=None):
    return {
        "document": document,
        "kind": "literal",
        "section": section,
        "phrase": phrase,
        "value": value,
    }


def check(id_, field, left, right):
    return {"id": id_, "field": field, "packet": left, "evidence": [right]}


def specs():
    battery = [
        check(
            "charging-temperature",
            "hard_limits",
            number("packet", "Hard charging T<=", "C,"),
            number("owner", "Every band meets charging T<=", "C,"),
        ),
        check(
            "plating",
            "hard_limits",
            number("packet", "every-charge plating overpotential>=", "V,"),
            number("owner", "every-charge plating>=", "V,"),
        ),
        check(
            "voltage",
            "hard_limits",
            number("packet", "programme voltage<=", "V and"),
            number("owner", "programme voltage<=", "V and"),
        ),
        check(
            "retention",
            "hard_limits",
            number("packet", "Q30/Q1>=", "apply to"),
            number("owner", "Q30/Q1>=", "."),
        ),
        check(
            "time-is-objective",
            "objective",
            literal(
                "packet",
                "Minimize each band's session-start-to80 time;",
                "MINIMIZE_SESSION_TIME",
            ),
            literal("owner", "Minimize band session minutes;", "MINIMIZE_SESSION_TIME"),
        ),
        check(
            "discharge-scope",
            "outputs",
            literal(
                "packet",
                "Discharge and rest temperatures are diagnostics.",
                "DISCHARGE_DIAGNOSTIC",
            ),
            literal(
                "owner",
                "Discharge thermal extrema remain diagnostics.",
                "DISCHARGE_DIAGNOSTIC",
            ),
        ),
        check(
            "buyer-mix",
            "w",
            literal("packet", "owner selects `w_band=buyer_mix`", "BUYER_MIX"),
            literal(
                "owner", "owner selects buyer-mix weighting of band value.", "BUYER_MIX"
            ),
        ),
    ]
    motor = [
        check(
            "holding-floor",
            "hard_limits",
            number("packet", "Round up to **", "N·m holding torque**."),
            number("owner", "Precision robot-joint integrator |", "N·m holding;"),
        ),
        check(
            "peak-floor",
            "hard_limits",
            number("packet", "Demand **", "N·m for a 2-s"),
            number("owner", "N·m holding;", "N·m short peak;"),
        ),
        check(
            "ripple-relative",
            "hard_limits",
            number("packet", "Energized peak-to-peak ripple ≤", "% of absolute mean"),
            number("owner", "energized ripple ≤", "% and"),
        ),
        check(
            "cogging",
            "hard_limits",
            number("packet", "Zero-current cogging peak-to-peak ≤", "N·m"),
            number("owner", "unpowered cogging ≤", "N·m peak-to-peak"),
        ),
    ]
    cooling = [
        check(
            "case-temperature",
            "hard_limits",
            number("packet", "selects **", "C at the lid-side"),
            number("owner", "Cooling's", "C limit is the"),
        ),
        check(
            "temperature-plane",
            "outputs",
            literal(
                "packet", "lid-side TIM2 interface (case temperature)", "LID_TIM2_CASE"
            ),
            literal(
                "owner", "lid-side TIM2 interface / case temperature", "LID_TIM2_CASE"
            ),
        ),
        check(
            "vapour-chamber-input",
            "conditions",
            literal(
                "packet", "vapour-chamber lid as buyer input", "BUYER_VAPOUR_CHAMBER"
            ),
            literal(
                "owner",
                "The buyer supplies a **vapour-chamber lid**",
                "BUYER_VAPOUR_CHAMBER",
            ),
        ),
    ]
    return [
        ("battery-v3", "battery-ambient-map-v3.md", OWNER, battery),
        ("motor", "motor-precision-joint-v2.md", FIRST, motor),
        ("cooling-cell", "cooling-cell-v3.md", COOLING, cooling),
    ]


def build(root=ROOT):
    result = {}
    for family, filename, decision, checks in specs():
        docs = {}
        for key, path, kind in [
            ("packet", PREFIX + filename, "PACKET"),
            ("owner", decision, "OWNER_DECISION"),
        ]:
            docs[key] = {
                "path": path,
                "kind": kind,
                "sha256": packet.digest(packet.source_path(root, path).read_bytes()),
            }
        manifest = {
            "schema": reconcile.SCHEMA,
            "challenge": family,
            "documents": docs,
            "checks": checks,
        }
        report = reconcile.reconcile(root, manifest)
        result[family + "-manifest.json"] = (
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        )
        result[family + "-report.json"] = (
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
        result[family + "-report.md"] = reconcile.render(report)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        path = OUT / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != value:
                parser.exit(1, "Public reconciliation example differs: " + name + "\n")
        else:
            path.write_text(value, encoding="utf-8", newline="\n")
    print("3 public packets / 14 explicit checks; unbound fields retained, no approval")


if __name__ == "__main__":
    main()
