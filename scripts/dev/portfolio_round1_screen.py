"""Offline dimensional screens for the first customer DEVELOPMENT round.

No solver, provider, registry, data generation or file writes. These estimates
cannot establish reference adequacy, admissibility, score or qualification.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

SHEET = (
    Path(__file__).resolve().parents[2]
    / "docs/development/challenge_pipeline/round1/requirements.json"
)
VERSION = "portfolio-customer-development-round1-v1"
FAMILIES = {"f02", "f06", "f08", "f13", "f17"}


def _positive(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def validate_allowances(sheet: dict) -> dict:
    """Check this planning sheet, not an executable grant or scientific gate."""
    if sheet["version"] != VERSION or set(sheet["challenges"]) != FAMILIES:
        raise ValueError("unknown first-round sheet or family set")
    if (
        sheet["scope"] != "SYNTHETIC_DEVELOPMENT_REFERENCE_FEASIBILITY"
        or sheet["dispatch_ready"] is not False
        or sheet["protocol_transition"] is not False
        or sheet["official_scoring"] is not False
        or sheet["qualification"] != "NOT_DEMONSTRATED"
    ):
        raise ValueError("this screen cannot authorize execution or qualification")
    usd = node_hours = vcpu_hours = attempts = 0
    for challenge in sheet["challenges"].values():
        grant = challenge["grant"]
        if challenge["reference_adequacy"] != "NOT_DEMONSTRATED":
            raise ValueError("adequacy needs evidence, not this screen")
        for key in ("memory_gib", "node_hours", "usd", "attempts", "timeout_s"):
            if not _positive(grant[key]):
                raise ValueError(f"invalid grant {key}")
        if (
            any(
                type(grant[key]) is not int
                for key in (
                    "vcpu",
                    "attempts",
                    "timeout_s",
                    "concurrent_executions",
                    "automatic_retries",
                )
            )
            or grant["vcpu"] != 16
            or grant["concurrent_executions"] != 1
            or grant["automatic_retries"] != 0
            or isinstance(grant["automatic_retries"], bool)
            or isinstance(grant["attempts"], bool)
            or int(grant["attempts"]) != grant["attempts"]
        ):
            raise ValueError("first round is one 16-vCPU process, zero retries")
        usd += grant["usd"]
        node_hours += grant["node_hours"]
        vcpu_hours += grant["vcpu"] * grant["node_hours"]
        attempts += grant["attempts"]
    totals = {
        "usd": usd,
        "allocated_node_hours": node_hours,
        "allocated_vcpu_hours": vcpu_hours,
    }
    if totals != sheet["aggregate"]:
        raise ValueError("aggregate must equal the non-transferable allowances")
    return {**totals, "maximum_attempts": attempts}


def screen(sheet: dict) -> dict:
    """Return named simple estimates and their explicit model-form limits."""
    totals = validate_allowances(sheet)
    challenges = sheet["challenges"]
    thermal = challenges["f02"]["thermal"]
    layers = thermal["layers"]
    solid_r = sum(p["thickness_m"] / (p["k_w_m_k"] * p["area_m2"]) for p in layers)
    heat_c = sum(
        p["rho_kg_m3"] * p["cp_j_kg_k"] * p["thickness_m"] * p["area_m2"]
        for p in layers
    )
    optical = challenges["f06"]["optical"]
    smallest_pitch = optical["pitch_nm"][0] + optical["pitch_offset_nm"][0]
    smallest_duty = optical["duty"][0] + optical["duty_offset"][0]
    largest_duty = optical["duty"][1] + optical["duty_offset"][1]
    feature = smallest_pitch * min(smallest_duty, 1 - largest_duty)
    structure = challenges["f08"]["structure"]
    length = sum(structure["length_mm"]) / 2000
    width = sum(structure["width_mm"]) / 2000
    thick = sum(structure["thickness_mm"]) / 2000
    rib_h = sum(structure["rib_height_mm"]) / 2000
    rib_t = sum(structure["rib_thickness_mm"]) / 2000
    relief_l = sum(structure["relief_length_mm"]) / 2000
    relief_w = structure["relief_width_mm"] / 1000
    # Sharp-corner relief subtraction; actual rounded CAD has slightly more mass.
    mass = structure["rho_kg_m3"] * (
        length * width * thick
        + 2 * length * rib_h * rib_t
        - relief_l * relief_w * thick
    )
    beam_i = width * thick**3 / 12
    beam_compliance = length**3 / (3 * structure["e_pa"] * beam_i)
    beam_f1 = (
        1.875104**2
        / (2 * math.pi * length**2)
        * math.sqrt(
            structure["e_pa"] * beam_i / (structure["rho_kg_m3"] * width * thick)
        )
    )
    acoustic = challenges["f13"]["acoustic"]
    # First rigid circular-duct transverse root J1'(x)=0, x=1.84118.
    duct_radius = acoustic["duct_diameter_mm"] / 2000
    cutoff = 1.84118 * acoustic["sound_speed_m_s"] / (2 * math.pi * duct_radius)
    mixer = challenges["f17"]["mixer"]
    channel_w = mixer["width_um"] * 1e-6
    channel_h = mixer["height_um"] * 1e-6
    channel_l = mixer["length_mm"] * 1e-3
    area = channel_w * channel_h
    hydraulic_d = 2 * channel_w * channel_h / (channel_w + channel_h)
    flows = [q * 1e-9 / 60 for q in mixer["flow_ul_min"]]
    velocities = [q / area for q in flows]
    reynolds = [
        mixer["rho_kg_m3"] * u * hydraulic_d / mixer["mu_pa_s"] for u in velocities
    ]
    peclet = [u * channel_w / d for u in velocities for d in mixer["diffusivity_m2_s"]]
    pressure = [
        12
        * mixer["mu_pa_s"]
        * channel_l
        * q
        / (channel_w * channel_h**3 * (1 - 0.63 * channel_h / channel_w))
        for q in flows
    ]
    return {
        "basis": "OFFLINE_ANALYTICAL_SCREEN_NOT_REFERENCE_EVIDENCE",
        "version": sheet["version"],
        "examined": {"challenge_count": len(challenges), "grant_count": 5},
        "allowance_totals": totals,
        "f02": {
            "solid_1d_resistance_k_w": solid_r,
            "lumped_heat_capacity_j_k": heat_c,
            "total_1d_resistance_k_w": [
                solid_r + 1 / (h * layers[-1]["area_m2"]) for h in thermal["h_w_m2_k"]
            ],
            "cannot_establish": "3D spreading, hotspot transients or burst feasibility",
        },
        "f06": {
            "minimum_perturbed_line_space_nm": feature,
            "minimum_remaining_si_nm": optical["si_thickness_nm"]
            - optical["etch_nm"][1]
            - optical["etch_offset_nm"][1],
            "cannot_establish": "coupling, reflection, FDTD memory or reference adequacy",
        },
        "f08": {
            "nominal_sharp_relief_mass_kg": mass,
            "plain_beam_compliance_mm_n": beam_compliance * 1000,
            "plain_beam_first_mode_hz": beam_f1,
            "cannot_establish": "ribbed CAD mass, modal/harmonic peaks or compliance",
        },
        "f13": {
            "duct_first_transverse_cutoff_hz": cutoff,
            "chamber_first_transverse_cutoff_hz": [
                1.84118 * acoustic["sound_speed_m_s"] / (2 * math.pi * r / 1000)
                for r in acoustic["chamber_radius_mm"]
            ],
            "cannot_establish": "3D chamber transmission loss or resolved resonances",
        },
        "f17": {
            "hydraulic_diameter_um": hydraulic_d * 1e6,
            "reynolds_by_flow": reynolds,
            "peclet_range": [min(peclet), max(peclet)],
            "smooth_channel_pressure_pa_by_flow": pressure,
            "smooth_mean_residence_s_by_flow": [area * channel_l / q for q in flows],
            "cannot_establish": "groove mixing, scalar diffusion error or groove residence",
        },
    }


def main() -> None:
    print(json.dumps(screen(json.loads(SHEET.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
