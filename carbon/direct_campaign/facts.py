"""The owner-approved science facts for F08 (Ribbed Bracket) 1.4 and F02 (Burst
Thermal) 2.3's direct campaigns.

Owner approval of LAUNCHPAD_F08_F02_SCIENCE_FACTS_20261021 (relayed by Data
Collection, 2026-10-21), approved copy
sha256:34a4f31c8b9ad950593a3fa0cb9a533d3c57c2ad25c0e919acecff1eaffb1095, as
corrected to source after the Validator's check, corrected copy
sha256:e9d56c4bce390ab4bc2d7150d7951f09e8e05ac22ce50cbe96c7cceb1105f559 (the
Validator records the approval and checks each value against its cited
sources). Each value is copied unchanged from the corrected file's
per-Challenge section; its status there is the comment above it. A value the
file leaves `LEAVE_HUMAN_INPUT` is `HUMAN_INPUT` here.

Each value fills one `HUMAN_INPUT` field: a profile field (`contracts`), a
served document's field (`research`, `challenge_registry.direct`), or a clause.
A filled clause takes the field's approved label from `LABELS` in place of its
`human_input_*` label, and its content digest binds the value's text. The
Validator's fields (gates, components, rule, score, practice labels and
aggregation, error scale, measurement definitions, overlap rules, score
direction, learning-curve basis, reference policy and value bindings, stratum
applicability) are not here.
"""

from __future__ import annotations

from .spec import HUMAN_INPUT

#: The approval these values copy: the owner-approved file and its correction
#: to source, by record name and file digest.
APPROVAL = {
    "record": "LAUNCHPAD_F08_F02_SCIENCE_FACTS_20261021",
    "approved_sha256": (
        "34a4f31c8b9ad950593a3fa0cb9a533d3c57c2ad25c0e919acecff1eaffb1095"
    ),
    "corrected_sha256": (
        "e9d56c4bce390ab4bc2d7150d7951f09e8e05ac22ce50cbe96c7cceb1105f559"
    ),
}

#: (challenge id, version) -> field -> the approved value, or HUMAN_INPUT.
FACTS = {
    ("f08-ribbed-bracket", "1.4"): {
        # DRAFT_FROM_REGISTERED
        "task": "Predict the static tip compliance and, at each of three constant modal damping ratios (0.005, 0.01, 0.02), the largest tip dynamic compliance over 80-600 Hz and its frequency, for the registered clamped ribbed-plate bracket with a cable relief under a unit tip-pad force.",
        # DRAFT_FROM_REGISTERED
        "intended_use": "Public DEVELOPMENT construction and practice only; not a joint-damping, nonlinear, fatigue, strength, full-machine settling, hardware or customer-acceptance model.",
        # DRAFT_FROM_REGISTERED
        "interface_conventions": "millimetres, mm/N and Hz; one row per geometry; outputs are the static tip z-displacement per newton, then for each damping ratio the band-peak tip z-displacement magnitude per newton and its frequency (harmonic convention exp(+i omega t)); mass is analytic CAD mass, not a learned target",
        # DRAFT_FROM_REGISTERED
        "physical_scope": "Linear elastic, synthetic aluminium-like cantilever bracket (rectangular plate, two full-length ribs, through-plate cable relief), clamped at the root and loaded at a tip pad: static tip compliance and damped harmonic tip-response peaks over 80-600 Hz at three constant modal damping ratios. Not full-machine settling, fatigue, strength, joints or nonlinear dynamics.",
        # DRAFT_FROM_REGISTERED
        "governing_law": "3-D linear elastostatics and steady-state harmonic elastodynamics by modal superposition: isotropic synthetic material E = 70 000 MPa, nu = 0.33, rho = 2.7e-9 t/mm^3; CalculiX C3D10; a 48-mode mass-normalised eigen step, three steady-state-dynamics steps with constant modal damping (zeta 0.005, 0.01, 0.02) over 80-600 Hz, and a static step. Constant modal damping is not a joint law.",
        # DRAFT_FROM_REGISTERED
        "geometry_domain": "Six lattice inputs in mm: length 180-260 (step 5), width 60-100 (5), thickness 4-8 (0.5), rib height 8-16 (1), rib thickness 3-5 (0.5), relief length 20-60 (5). Ribs run full length at y = +-W/4; relief centred at (L/2, 0), 20 mm wide, 3 mm corner radius; root face x = 0 fully clamped; 1 N uniform +z traction on the 5 x 10 mm tip pad; tip observation at (L-2.5, 0, t). Valid only if W/4 - rib_t/2 > 10 mm and min((L - relief)/2, W/2 - 10) >= 6 mm.",
        # DRAFT_FROM_REGISTERED
        "governing_job": "Choose a light ribbed support with admissible tip motion across the service envelope: minimise the worst-band tip dynamic compliance subject to mass <= 0.45 kg, static tip compliance <= 0.03 mm/N and dynamic peak <= 0.15 mm/N over 80-600 Hz at every damping ratio (internal mock buyer).",
        # DRAFT_FROM_REGISTERED
        "time_semantics": "No time axis: output 1 is static; outputs 2-7 are frequency-domain summaries (for each damping ratio, the maximum tip receptance magnitude over the 80-600 Hz search band and its frequency, found on a grid no coarser than a tenth of each in-band half-power bandwidth and refined by golden section). STEADY in the authoring schema is correct for this interface.",
        # DRAFT_FROM_REGISTERED
        "operating_envelope": "The valid geometry lattice above; all three damping ratios (0.005, 0.01, 0.02) per geometry; frequency searched over 80-600 Hz (adversarial peak search, not a random state); unit 1 N z-force on the tip pad; 48-mode basis with a 900 Hz mode-cutoff band.",
        # DRAFT_FROM_REGISTERED
        "physical_support": "The reference is valid only for the synthetic isotropic linear-elastic material, a fully clamped root, constant modal damping, C3D10 meshes (Gmsh 4.15.2; h = 1.7 mm exam truth, h = 3 mm TRAIN) and the 48-mode truncation checked by its 12/24/48 ladder; the claim is agreement with the reference simulator, not with reality (credibility NOT_DEMONSTRATED).",
        # LEAVE_HUMAN_INPUT
        "physical_invariant": HUMAN_INPUT,
        # DRAFT_FROM_REGISTERED
        "sampling_law": "TRAIN v2 (287 rows): 255 of 256 geometries drawn uniformly on the valid lattice (seed 20261015, h = 3 mm; train-0016 failed) plus 32 near-limit lattice actions placed by a log-linear fit (16 safe / 16 unsafe at 0.15 mm/N). The exposed development bank (practice) is the RR-PACKS-07 ladder: 8 lattice neighbours of pilot-0000 placed around the 0.15 mm/N crossing, 4 safe and 4 unsafe, at h = 1.7 mm; not an independent population.",
        # REGISTERED_FACT
        "reference_method": "CalculiX ccx 2.23 (SPOOLES) with Gmsh 4.15.2 meshing (image ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05); exam ladder solved natively by ccx sha256 21edfdcb18568f42cdde46a06583247616121a2724f4cd68e10fe0239829645b at h = 3 / 2.25 / 1.7 mm (1.7 is the reference).",
        # REGISTERED_FACT
        "reference_quality": "Unqualified numerical DEVELOPMENT reference: f08_verify passed (MMS H1 2.06 / L2 3.13 and the closed-form axial rod; code verification only); reference uncertainty U = 3.9e-5 mm/N (worst dynamic) and 6.7e-7 mm/N (static), smallest ladder margin 0.00286 mm/N.",
        # DRAFT_FROM_REGISTERED
        "support_boundary": "All six inputs finite, within bounds and exactly on the lattice steps, with W/4 - rib_t/2 > 10 mm and min((L - relief)/2, W/2 - 10) >= 6 mm; anything else is refused, never repaired.",
        # DRAFT_FROM_REGISTERED
        "membership_decision": "A practice row is a member iff it is one of the exposed development bank's 8 registered ladder rows (each satisfies the validity rule above).",
        # DRAFT_FROM_REGISTERED
        "base_measure": "Counting measure on the 8 registered ladder rows.",
        # DRAFT_FROM_REGISTERED
        "probability_law": "A fixed, purposely placed set (PILOT_LATTICE_LADDER_AT_THE_LIMIT_NOT_INDEPENDENT), not a random draw; it carries no population-prevalence claim.",
        # REGISTERED_FACT
        "practice_reporting": "Practice reports aggregate public-practice errors on F08's registered scales: static 0.003 mm/N, each dynamic tip 0.015 mm/N, each peak frequency 10 Hz; aggregate the worst over quantity and case, with the mean recorded beside, labelled POINT_ESTIMATE_DIAGNOSTIC. No per-case values.",
        # REGISTERED_FACT
        "reference_fidelity": "F08 TRAIN is h = 3 mm; the exam truth is h = 1.7 mm; at the 0.15 mm/N limit, h3 reads about 0.07 % (about 1e-4 mm/N) lower (16 cases at both meshes: worst dynamic h3 - h1.7 = -0.000131 to -0.000090 mm/N). The practice bank's references are the h = 1.7 mm ladder solves.",
        # REGISTERED_FACT
        "known_limitation": "TRAIN at h = 3 mm (exam 1.7 mm); train-0016 failed (original 256 incomplete); the near-limit TRAIN stratum is placed, not random; the exam is a public, non-independent 8-case ladder; synthetic material and constant modal damping; accuracy_gate null, live_eligible false; not qualified; credibility NOT_DEMONSTRATED.",
        # DRAFT_FROM_REGISTERED
        "rights_profile": "Same rules as Motor and Cooling: the exam data and references are Carbon's own, solved with open solvers on synthetic, non-customer cases (public TRAIN and the exposed development bank are published for development use); miner recipes are private to Carbon. No customer or third-party data.",
        # DRAFT_FROM_REGISTERED
        "catalog_usage_text": "Catalog and graph recipes build from public TRAIN only; practice runs on the exposed 8-row ladder bank and reports aggregate errors on the registered scales, never per-case values.",
    },
    ("f02", "2.3"): {
        # DRAFT_FROM_REGISTERED
        "task": "Predict the maximum die-top temperature over a 120-second transient for one rectangular power burst (total power during the burst and its on-time, starting at 20 s on a 20 W base from a uniform 40 C start) in the registered three-layer die/TIM/copper stack with underside convective cooling.",
        # DRAFT_FROM_REGISTERED
        "intended_use": "Public DEVELOPMENT construction and practice only, in the single fixed cold context; not a model of other cooling, initial-state, source-split or waveform conditions, of temperature histories, of real silicon or package materials, or of hardware, throttling-control or customer-acceptance decisions.",
        # DRAFT_FROM_REGISTERED
        "interface_conventions": "watts, seconds and degrees Celsius; one row per schedule; peak_w is the total power during the burst (including the 20 W base), on_time_s the burst duration from t = 20 s; peak_top_c is the maximum die-top temperature over the 0-120 s window; fixed context: coolant 30 C, h 2500 W/m^2K, uniform 40 C at t = 0, 0.5 of the power on each patch, rectangular waveform; extra energy (peak_w - 20) * on_time_s is analytic, not learned",
        # DRAFT_FROM_REGISTERED
        "physical_scope": "Three-dimensional transient solid heat conduction in a fixed synthetic three-layer stack (die, TIM and copper surrogates), heated by two top-surface patches carrying a 20 W base plus one rectangular power burst and cooled by Robin convection on the whole underside; one fixed cold context. Not fluid flow, chip reliability, a controller or a hardware model.",
        # DRAFT_FROM_REGISTERED
        "governing_law": "rho c_p dT/dt = div(k grad T), constant isotropic properties per layer, perfect layer contact: copper k 390 W/mK, rho 8960 kg/m^3, c_p 385 J/kgK; TIM 5, 2500, 1000; die 130, 2330, 700 (synthetic, selected, not measured). Underside Robin h = 2500 W/m^2K to 30 C coolant; each top patch a uniform flux of its power share over 8 x 8 mm; all other faces insulated. Elmer HeatSolver, BDF2.",
        # REGISTERED_FACT
        "geometry_domain": "Centred stack, bottom to top: copper 30 x 30 x 2 mm, TIM 20 x 20 x 0.2 mm, die 20 x 20 x 0.5 mm (2.7 mm total); two 8 x 8 mm heated patches on the die top centred at x = -5 and +5 mm, y = 0; served split 0.5/0.5.",
        # DRAFT_FROM_REGISTERED
        "governing_job": "Choose a burst power and duration that maximises the extra energy above the 20 W base while the die-top maximum stays at or below 95 C over the 120 s window (internal mock buyer; 95 C is a buyer development limit, not a physical law).",
        # DRAFT_FROM_REGISTERED
        "time_semantics": "TRANSIENT event summarised to a scalar. Each row is one 120 s schedule: uniform 40 C at t = 0; 20 W total from t = 0; at t = 20 s total power steps to peak_w for on_time_s seconds, then back to 20 W until 120 s. peak_top_c is the largest die-top maximum over every solver step end in (0, 120] s (BDF2; 0.1 s steps, 0.02 s from 20 s to 10 s after the last event). No steady baseline enters peak_top_c, and the stack is not pre-equilibrated. In every registered case the peak occurs at the burst end.",
        # DRAFT_FROM_REGISTERED
        "operating_envelope": "The fixed cold context (coolant 30 C, h 2500 W/m^2K, initial 40 C, split 0.5, rectangular); inputs within the served ranges: TRAIN 70-150 W and 4-20 s (S1 70-100 W x 4-6 s, S2 80-150 W x 5-20 s); development bank 80-140 W and 5-20 s; sealed exam batches integer 70-100 W x 4.0-6.0 s in 0.1 s steps.",
        # LEAVE_HUMAN_INPUT
        "physical_support": HUMAN_INPUT,
        # LEAVE_HUMAN_INPUT
        "physical_invariant": HUMAN_INPUT,
        # DRAFT_FROM_REGISTERED
        "sampling_law": "TRAIN40-v2: 40 cold-context Elmer solves, S1 24 rows uniform on [70, 100] W x [4, 6] s (12 at or below 95 C, 12 above) and S2 16 rows uniform on [80, 150] W x [5, 20] s (all above), disjoint from the 8 bank actions. The exposed development bank (practice) is the 8 registered cold actions (80 W/5 s, 110/10, 140/5, 140/20, 84/85/86/87 W at 5 s): not an independent population.",
        # REGISTERED_FACT
        "reference_method": "Elmer 26.2.1 HeatSolver (locked source), hex808, BDF2, CG+ILU0 at 1e-12, one CPU, no network; primary rung plus mesh2 and dt0.5 convergence rungs.",
        # REGISTERED_FACT
        "reference_quality": "Unqualified numerical DEVELOPMENT reference: RR-04 ACCEPTED_FOR_DEVELOPMENT_BANK under F02-SCIENCE-VALUES-01 bands (B1 peak 0.5 C, B5 energy residual 1 %); code verification accepted by the owner (MMS, band [1.7, 2.3]); reference uncertainty U(peak_top_c) = 0.012 C (single-refinement bound); closest bank margin 0.21 C (about 17 U).",
        # DRAFT_FROM_REGISTERED
        "support_boundary": "Support is the served input box in the fixed cold context: peak_w 70-150 W and on_time_s 4-20 s (the union of the served TRAIN, bank and sealed ranges). Inputs are exactly {peak_w, on_time_s}; a TRAIN row with another context is refused by the loader. The reference runner itself does not check finiteness or the box.",
        # DRAFT_FROM_REGISTERED
        "membership_decision": "A practice row is a member iff it is one of the exposed development bank's 8 registered cold actions.",
        # DRAFT_FROM_REGISTERED
        "base_measure": "Counting measure on the 8 registered cold actions.",
        # DRAFT_FROM_REGISTERED
        "probability_law": "A fixed registered set (REGISTERED_EIGHT_ACTION_SET_NOT_INDEPENDENT), not a random draw; no population-prevalence claim.",
        # REGISTERED_FACT
        "practice_reporting": "Practice reports aggregate public-practice errors on F02's registered scale: each case |p - primary rung| / train_peak_std_c (6.701245845436587 C, TRAIN40-v2), aggregate max(mean, near-limit mean, worst). No per-case values.",
        # REGISTERED_FACT
        "reference_fidelity": "Each reference is the primary rung (1 mm in-plane cells, 6/2/4 z-cells, base step plan) with mesh2 (cells halved) and dt0.5 (steps halved) solved per case; a case is accepted only if B1-B5 pass at both rungs and the rungs agree on the 95 C side. Measured on the 8 bank actions: mesh2 shifts -0.0052 to -0.0114 C, dt0.5 at most 0.000201 C, no label flips.",
        # REGISTERED_FACT
        "known_limitation": "Synthetic constant-property materials; one cold context only (a cold-context slice, not a coolant/h/initial-state trust volume); bank actions not independent; no temperature-dependent properties, contact resistance, phase change, fluid or radiation; peak taken at discrete solver steps; 95 C is a buyer limit; cross-tool credibility NOT_DEMONSTRATED; not qualified.",
        # DRAFT_FROM_REGISTERED
        "rights_profile": "Same rules as Motor and Cooling: the exam data and references are Carbon's own, solved with open solvers on synthetic, non-customer cases (public TRAIN and the exposed development bank are published for development use); miner recipes are private to Carbon. No customer or third-party data.",
        # DRAFT_FROM_REGISTERED
        "catalog_usage_text": "Catalog and graph recipes build from public TRAIN40-v2 only; practice runs on the exposed 8-action bank and reports aggregate errors on the registered scale, never per-case values.",
    },  # Battery 2.2 (the Validator, 2026-10-22: Battery 2.1 plus the catalog
    # binding). No approval file covers it yet: every value is HUMAN_INPUT
    # until one does (Battery's own registered descriptions live in
    # `carbon.battery`; copying them here is that approval's to make).
    ("battery-fastcharge-ageing-development-v1", "2.2"): {
        "task": HUMAN_INPUT,
        "intended_use": HUMAN_INPUT,
        "interface_conventions": HUMAN_INPUT,
        "physical_scope": HUMAN_INPUT,
        "governing_law": HUMAN_INPUT,
        "geometry_domain": HUMAN_INPUT,
        "governing_job": HUMAN_INPUT,
        "time_semantics": HUMAN_INPUT,
        "operating_envelope": HUMAN_INPUT,
        "physical_support": HUMAN_INPUT,
        "physical_invariant": HUMAN_INPUT,
        "sampling_law": HUMAN_INPUT,
        "reference_method": HUMAN_INPUT,
        "reference_quality": HUMAN_INPUT,
        "support_boundary": HUMAN_INPUT,
        "membership_decision": HUMAN_INPUT,
        "base_measure": HUMAN_INPUT,
        "probability_law": HUMAN_INPUT,
        "practice_reporting": HUMAN_INPUT,
        "reference_fidelity": HUMAN_INPUT,
        "known_limitation": HUMAN_INPUT,
        "rights_profile": HUMAN_INPUT,
        "catalog_usage_text": HUMAN_INPUT,
    },
}

#: (challenge id, version) -> field -> the approved clause label, for each filled
#: clause. Rights is one text under Motor's two labels (the contracts' and the
#: research population's); F02's time coordinate is relabelled with its time
#: semantics (Validator, 2026-10-21: TimeMode STEADY is kept).
LABELS = {
    ("f08-ribbed-bracket", "1.4"): {
        "governing_law": "linear_elasticity_modal_harmonic_constant_damping",
        "geometry_domain": "clamped_ribbed_plate_with_relief_lattice_v1",
        "governing_job": "resonance_resistant_bracket_selection",
        "time_semantics": "static_and_frequency_domain_no_time_coordinate",
        "operating_envelope": "registered_lattice_three_damping_80_600_hz",
        "physical_support": "linear_clamped_synthetic_material_reference_support",
        "support_boundary": "lattice_bounds_and_rib_relief_ligament_rule",
        "membership_decision": "registered_ladder_row",
        "base_measure": "counting_measure_on_registered_bank",
        "probability_law": "fixed_placed_ladder_not_independent",
        "practice_reporting": "aggregate_errors_on_registered_scales",
        "reference_fidelity": "h1_7_reference_h3_train",
        "known_limitation": "h3_train_placed_ladder_synthetic_unqualified",
        "rights_profile": "public_synthetic",
        "rights_profile.research": "public_synthetic_cases",
    },
    ("f02", "2.3"): {
        "governing_law": "transient_conduction_robin_underside_patch_flux",
        "geometry_domain": "die_tim_copper_stack_two_patches_v1",
        "governing_job": "burst_schedule_under_peak_cap",
        "time_semantics": "transient_burst_summarised_as_window_maximum",
        "time_semantics.time_coordinate": "time_maximum_over_registered_window",
        "operating_envelope": "cold_context_served_input_ranges",
        "support_boundary": "served_input_box_cold_context",
        "membership_decision": "registered_cold_action",
        "base_measure": "counting_measure_on_registered_bank",
        "probability_law": "fixed_registered_actions_not_independent",
        "practice_reporting": "aggregate_errors_on_registered_scale",
        "reference_fidelity": "primary_rung_with_mesh2_dt_half_envelope",
        "known_limitation": "synthetic_single_context_unqualified",
        "rights_profile": "public_synthetic",
        "rights_profile.research": "public_synthetic_cases",
    },
    # Battery 2.2: none until its facts are approved.
    ("battery-fastcharge-ageing-development-v1", "2.2"): {},
}


def _replaced(text, old, new):
    assert old in text, old
    return text.replace(old, new)


def _f08_15():
    """F08 1.5's facts: 1.4's, with the exam-safety edits the Validator ruled
    (OWNER-PUBLISH-WHAT-IS-TESTED-01, 2026-10-24): the sampling law says the
    exam's cases are drawn privately by a different rule; the reference method
    names the practice ladder (the public development bank); and no mesh size
    of the reference appears anywhere. Older versions stay as served."""
    facts = dict(FACTS[("f08-ribbed-bracket", "1.4")])
    law = facts["sampling_law"]
    assert law.endswith("not an independent population.")
    facts["sampling_law"] = (
        law + " The exam's cases are drawn privately by a different rule; they are"
        " not these."
    )
    facts["reference_method"] = _replaced(
        facts["reference_method"],
        "exam ladder solved natively by ccx sha256 "
        "21edfdcb18568f42cdde46a06583247616121a2724f4cd68e10fe0239829645b at "
        "h = 3 / 2.25 / 1.7 mm (1.7 is the reference).",
        "practice ladder (the public development bank) solved natively by ccx "
        "sha256 21edfdcb18568f42cdde46a06583247616121a2724f4cd68e10fe0239829645b.",
    )
    facts["physical_support"] = _replaced(
        facts["physical_support"],
        "C3D10 meshes (Gmsh 4.15.2; h = 1.7 mm exam truth, h = 3 mm TRAIN) and",
        "C3D10 meshes (Gmsh 4.15.2; the reference is the converged solve, see "
        "the verification status) and",
    )
    facts["reference_fidelity"] = (
        "The reference is the converged solve; see the verification status. "
        "TRAIN is solved on a coarser mesh than the practice bank's references; "
        "at the 0.15 mm/N limit the coarser TRAIN reads about 0.07 % (about "
        "1e-4 mm/N) lower (16 cases at both meshes: worst dynamic difference "
        "-0.000131 to -0.000090 mm/N). The practice bank's references are the "
        "converged solves."
    )
    limitation = _replaced(
        facts["known_limitation"],
        "TRAIN at h = 3 mm (exam 1.7 mm);",
        "TRAIN on a coarser mesh than the references;",
    )
    # On 1.5 the exam is the private sealed batches; the public ladder is the
    # practice bank (Validator, 2026-10-24).
    facts["known_limitation"] = _replaced(
        limitation,
        "the exam is a public, non-independent 8-case ladder;",
        "the practice bank is a public, non-independent 8-case ladder; the "
        "exam's cases are private;",
    )
    return facts


def _f02_24():
    """F02 2.4's facts: 2.3's, without the reference's mesh sizes (the element
    type, an 8-node hexahedron, stays). Older versions stay as served."""
    facts = dict(FACTS[("f02", "2.3")])
    facts["reference_method"] = _replaced(
        facts["reference_method"],
        "primary rung plus mesh2 and dt0.5 convergence rungs.",
        "a primary solve with refined-mesh and refined-step convergence checks.",
    )
    facts["reference_fidelity"] = (
        "Each reference is a primary solve with a refined-mesh and a "
        "refined-step solve per case; a case is accepted only if B1-B5 pass at "
        "both and they agree on the 95 C side. Measured on the 8 bank actions: "
        "the refined mesh shifts -0.0052 to -0.0114 C, the refined step at most "
        "0.000201 C, no label flips."
    )
    return facts


FACTS[("f08-ribbed-bracket", "1.5")] = _f08_15()
LABELS[("f08-ribbed-bracket", "1.5")] = dict(LABELS[("f08-ribbed-bracket", "1.4")])
# 1.6 (pool grade) changes only the exam: the approved facts are 1.5's.
FACTS[("f08-ribbed-bracket", "1.6")] = dict(FACTS[("f08-ribbed-bracket", "1.5")])
LABELS[("f08-ribbed-bracket", "1.6")] = dict(LABELS[("f08-ribbed-bracket", "1.5")])
FACTS[("f02", "2.4")] = _f02_24()
LABELS[("f02", "2.4")] = dict(LABELS[("f02", "2.3")])
# 2.5 (pool grade) changes only the exam: the approved facts are 2.4's.
FACTS[("f02", "2.5")] = dict(FACTS[("f02", "2.4")])
LABELS[("f02", "2.5")] = dict(LABELS[("f02", "2.4")])


def value(spec, version, name):
    """The approved value of `name` at exactly `version`, or HUMAN_INPUT. A
    version uses the facts key it declares in the version registry (graph
    route v2: its predecessor's approved facts, named explicitly)."""
    from carbon.challenge_kit.version_registry import entry

    return FACTS[(spec.challenge_id, entry(spec.challenge_id, version).facts)][name]


def label(spec, version, name):
    """The approved clause label for `name`, or None while it is unset (a
    graph route v2 version: its predecessor's)."""
    from carbon.challenge_kit.version_registry import entry

    return LABELS[(spec.challenge_id, entry(spec.challenge_id, version).facts)].get(
        name
    )

FACTS[("f08-ribbed-bracket", "1.7")] = dict(FACTS[("f08-ribbed-bracket", "1.6")])
LABELS[("f08-ribbed-bracket", "1.7")] = dict(LABELS[("f08-ribbed-bracket", "1.6")])
