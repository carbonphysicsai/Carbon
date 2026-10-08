"""Public DEVELOPMENT cost-panel recipes; not a solver, runner or grant.

Emit 30 complete-task definitions per requested Challenge and null result slots.
No provider, reference access, subprocess, registry or file writes occur here.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from copy import deepcopy
from pathlib import Path

from portfolio_round1_screen import screen, validate_allowances

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "docs/development/challenge_pipeline/round1/requirements.json"
VERSION = "customer-feasibility-panels-development-v1"
CHALLENGES = ("f02", "f08", "f13")
COST_FIELDS = (
    "consumed_cpu_hours",
    "end_to_end_wall_hours",
    "allocated_vcpu_hours",
    "peak_memory_gib",
    "charged_solver_launches",
)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _waveform(thermal: dict, family: str, power: int, duration: int) -> list:
    onset, base = thermal["onset_s"], thermal["base_w"]
    segments = [[0, onset, base, base]]
    if family == "two-pulse":
        half, gap = duration / 2, thermal["two_pulse_gap_s"]
        segments += [
            [onset, onset + half, power, power],
            [onset + half, onset + half + gap, base, base],
            [onset + half + gap, onset + duration + gap, power, power],
        ]
    else:
        segments += [
            [onset, onset + duration, base if family == "ramp" else power, power]
        ]
    segments += [[segments[-1][1], thermal["horizon_s"], base, base]]
    return segments


def _thermal_cases(sheet: dict) -> list:
    thermal = sheet["challenges"]["f02"]["thermal"]
    families = ("rectangular", "ramp", "two-pulse")
    rows = [
        (cooling, initial, split, family, 110, 10, "stratum-nominal")
        for cooling, initial, split, family in itertools.product(
            thermal["cooling_regimes"], thermal["initial_c"], (0.5, 0.8), families
        )
    ]
    probes = screen(sheet)["f02"]["near_limit_actions"]
    for family in families:
        rows += [
            (thermal["cooling_regimes"][1], 55, 0.8, family, 80, 5, "low-probe"),
            (
                thermal["cooling_regimes"][1],
                55,
                0.8,
                family,
                probes[family]["peak_w"],
                probes[family]["on_time_s"],
                "rc-selected-probe-NOT_TRUTH",
            ),
        ]
    return [
        {
            "role": role,
            "cooling": deepcopy(cooling),
            "initial_c": initial,
            "left_power_fraction": split,
            "waveform_family": family,
            "peak_w": power,
            "on_time_s": duration,
            "segments_start_end_s_power_start_end_w": _waveform(
                thermal, family, power, duration
            ),
        }
        for cooling, initial, split, family, power, duration, role in rows
    ]


def _structural_cases(sheet: dict) -> list:
    # Ten whole geometries, each at all three damping conditions. Not thirty
    # independent geometries; frequency samples are not counted as cases.
    geometries = [
        (180, 70, 4, 8, 3, 20),
        (220, 80, 6, 12, 4, 40),
        (260, 100, 8, 16, 5, 60),
        (260, 70, 4, 8, 3, 60),
        (180, 100, 8, 16, 5, 20),
        (260, 100, 4, 16, 3, 40),
        (180, 80, 8, 8, 5, 40),
        (220, 70, 6, 16, 3, 60),
        (220, 100, 6, 8, 5, 20),
        (260, 80, 6, 12, 4, 60),
    ]
    keys = (
        "length_mm",
        "width_mm",
        "thickness_mm",
        "rib_height_mm",
        "rib_thickness_mm",
        "relief_length_mm",
    )
    return [
        {
            "geometry": dict(zip(keys, geometry, strict=True)),
            "modal_damping": damping,
        }
        for geometry, damping in itertools.product(
            geometries, sheet["challenges"]["f08"]["structure"]["modal_damping"]
        )
    ]


def _acoustic_cases(sheet: dict) -> list:
    acoustic = sheet["challenges"]["f13"]["acoustic"]
    keys = (
        "radius_1_mm",
        "radius_2_mm",
        "length_1_mm",
        "length_2_mm",
        "neck_length_mm",
        "neck_offset_mm",
    )
    bounds = [
        acoustic["chamber_radius_mm"],
        acoustic["chamber_radius_mm"],
        acoustic["chamber_length_mm"],
        acoustic["chamber_length_mm"],
        acoustic["neck_length_mm"],
        acoustic["neck_offset_mm"],
    ]
    # A fixed midpoint Latin stratum recipe, not a claim of random P sampling.
    # Multipliers are coprime to 27, so every coordinate visits all 27 bins.
    recipes = []
    for i in range(27):
        geometry = {
            key: lo + (hi - lo) * (((multiplier * i + offset) % 27 + 0.5) / 27)
            for key, (lo, hi), multiplier, offset in zip(
                keys, bounds, (1, 2, 4, 5, 7, 8), (0, 3, 7, 11, 17, 23), strict=True
            )
        }
        recipes.append({"role": "stratified-geometry", "geometry": geometry})
    for fraction in (0, 0.5, 1):
        recipes.append(
            {
                "role": "boundary-or-nominal-geometry",
                "geometry": {
                    key: lo + fraction * (hi - lo)
                    for key, (lo, hi) in zip(keys, bounds, strict=True)
                },
            }
        )
    return recipes


def panel(challenge: str, sheet: dict) -> dict:
    """Prepare public recipes only; the return value is never execution authority."""
    validate_allowances(sheet)
    if challenge not in CHALLENGES:
        raise ValueError("unsupported cost-panel Challenge")
    builder = {"f02": _thermal_cases, "f08": _structural_cases, "f13": _acoustic_cases}
    rows = builder[challenge](sheet)
    tasks = {
        "f02": "120-s spatial transient including event/peak/crossing search",
        "f08": "static + eigen + adaptive complete 80-600-Hz harmonic response",
        "f13": "complete 500-2500-Hz transmission curve + adaptive quadrature",
    }
    cases = []
    for i, definition in enumerate(rows, 1):
        cases.append(
            {
                "public_recipe_label": f"{challenge}-development-cost-{i:02d}",
                "definition": definition,
                "definition_digest": _digest(definition),
                "status": "NOT_RUN",
                "measured_cost": dict.fromkeys(COST_FIELDS),
                "retained_artifacts": None,
            }
        )
    common = deepcopy(sheet["challenges"][challenge])
    return {
        "schema": VERSION,
        "purpose": "PUBLIC_DEVELOPMENT_PANEL_DEFINITION_NOT_EXECUTION_AUTHORITY",
        "challenge_planning_label": challenge,
        "dispatch_ready": False,
        "solver_runs_performed": 0,
        "reference_adequacy": "NOT_DEMONSTRATED",
        "source_sheet_digest": _digest(sheet),
        "source_packet": common.pop("packet"),
        "complete_task": tasks[challenge],
        "common_requirements_and_existing_caps": common,
        "supplemental_contract": "docs/development/challenge_pipeline/round1/feasibility-panels.md",
        "execution_blockers": [
            "exact solver image/build and mesher pins",
            "verified domain deck and complete-task extractor",
            "controls/refinements and process-launch accounting",
            "enforced provider resource/spend manifest and retained ledger",
            "existing protocol stage authority; no eight-at-once grant",
        ],
        "required_pins": dict.fromkeys(
            ("solver_image", "solver_build", "mesher", "deck", "extractor", "hardware")
        ),
        "cases": cases,
        "panel_definition_digest": _digest(
            {"version": VERSION, "challenge": challenge, "sheet": sheet, "rows": rows}
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", choices=CHALLENGES)
    args = parser.parse_args()
    print(
        json.dumps(
            panel(args.challenge, json.loads(SHEET.read_text(encoding="utf-8"))),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
