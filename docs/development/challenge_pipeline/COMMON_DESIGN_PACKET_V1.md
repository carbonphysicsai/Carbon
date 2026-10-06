# Common Challenge design packet — documentation template v1

This is the F1 packet from the adopted
[`Eight_Challenge_Foundation_Plan.md`](../../../Design_Specs/Eight_Challenge_Foundation_Plan.md)
§3. Copy the ten numbered sections into a Challenge-specific packet; replace
prompts with source-linked facts. It is **not** a registered Challenge, new
authoring schema, stage protocol, scoring rule or launch permission. A value
without an owner decision or evidence is `OPEN` (owner, needed decision,
blocking behavior). A range alone is not a population. Keep public research
draws separate from protected EVAL/STRESS and sealed confirmation material.

The [Battery worked example](BATTERY_DESIGN_PACKET_WORKED_EXAMPLE.md) shows
how an existing DEVELOPMENT Challenge maps to these sections. Existing
[Cooling](../AI_ACCELERATOR_COOLING_DESIGN_PACKET.md) and
[Motor](../MOTOR_DECISION_DESIGN_PACKET.md) packets are narrower historical
contracts, not authority to copy their numbers into a new Challenge.

| Section | Existing owner to reuse or bind | Do not infer |
| --- | --- | --- |
| 1 | `carbon/authoring/goals.py`; `carbon/challenge_readiness/record.py` decision and claim fields | Customer demand or acceptance from an engineering hypothesis |
| 2 | `carbon/authoring/physical.py` physical system, initial/boundary/time contracts | Steady-state applicability to a transient task |
| 3 | `carbon/authoring/populations.py`, `sampling.py`, `evidence.py` separate P, Q and weighting roles | A deployment law from a bounded input box |
| 4 | `carbon/authoring/cases.py` canonical cases and disclosure projections | Protected identities in public research |
| 5 | `carbon/reference_runtime/` and a Challenge-specific solver adapter; readiness reference evidence | Qualification from a solver name or successful run |
| 6 | `carbon/authoring/physical.py` output contract and `carbon/authoring/evidence.py` measurement/evidence bindings | Approved gates from fixture metrics |
| 7 | `carbon/reconstruction/capability_registry.py` and `challenge_contracts.py` | Execution permissions from a planning label |
| 8 | `carbon/challenge_kit/standard.py` and Challenge-specific provisions | Official cases/seeds in a public kit |
| 9 | `carbon/challenge_readiness/admission.py`, `carbon/challenge_pipeline/`, `carbon/design_search/` where applicable | Admission, promotion or qualification from a green fixture |
| 10 | `carbon/challenge_readiness/records/` and `carbon/challenge_pipeline/readiness/` | LIVE status from an incomplete readiness row |

## 1. Engineering job

Name the decision maker, physical decision, objective and constraints, cost of
a wrong decision, and explicit exclusions. Separate a proposed user from
demonstrated customer demand. `OPEN`: objective or acceptance values, owner and
the behavior held closed.

## 2. Physical system

State geometry grammar, material definitions and provenance, causal inputs,
initial/boundary conditions, units and time/frequency horizon. Name every
coupling omitted by the first scope. `OPEN`: material laws, limits or
conditions without an approved source.

## 3. Population P, Q and w

Distinguish intended population `P`, proposal/sampling law `Q`, strata and
evidence weighting `w`; state support and exclusions for each. Name the unit
of independent observation before any uncertainty claim. `OPEN`: any
unapproved law or target population.

## 4. Case contract

Define valid/invalid geometries and conditions, canonical identity,
representation, and separate public versus protected fields. Do not encode
reversible protected identifiers in public artifacts. `OPEN`: unratified case
grammar or disclosure.

## 5. Reference policy

Bind solver/environment, material and geometry pins, numerical settings,
controls, refinement, uncertainty/witnesses, typed failures, attempts and
cost. Record a proposed solver as proposed until verified. `OPEN`: resource
approval, tolerances and reference adequacy.

## 6. Output and measurement contract

Specify observable shape, coordinates, units, transformations and
normalization. Separate measurement applicability/qualification from score
use. Mandatory scientific failures precede soft ranking. `OPEN`: unapproved
gates, thresholds or metric weights.

## 7. Construction contract

Enumerate actual Level 0 vocabulary, permitted training data/backends,
reconstruction and resource permissions, and artifact identity. Expansion is
versioned; a research tool is not an official evaluator. `OPEN`: missing
construction-owner grant.

## 8. Research kit

List public documentation, vocabulary, training runtime, own-seed generator
and reference solver, practice evaluation, compute, model and agent
provisions. Name gaps. Generated research data is construction input only if
the construction contract permits it. Protected cases, seeds and labels stay
operator-side. `OPEN`: unprovided public tooling or data rights.

## 9. Evidence plan

Register admission/attack and engineering-value studies, baselines and
controls, fresh independent confirmation, cost and training-budget studies,
missing-evidence policy, disclosure and revision procedure. Precommit before
reference access. `OPEN`: confirmation population, study thresholds, compute
and spend. No tuning on final sealed evidence.

## 10. Readiness and claim record

Link what exists, what ran, what failed and what remains unknown. Name science,
construction/compute, security and process reviewers and the next gate.
Report maturity separately from implementation and testing. `OPEN`: reserved
approvals; fail closed on launch and qualification.

## F0 reuse input for the five additional portfolio briefs

The following labels are from foundation-plan §4, **not** registered IDs.
This maps prior learning into next packets without opening a runtime lane.

| Brief | Reuse | New evidence or owner-bound gap | First packet after F1 |
| --- | --- | --- | --- |
| f02 burst-power thermal envelopes | Physical time/initial/boundary contracts, case/evidence projections, search freeze and cost-ledger patterns | Transient layered-solid reference, power waveform family and holdout law, materials/contact/convection, solver and compute approval; steady Cooling evidence does not answer this task | f02 scope and authority packet |
| f06 3D manufacturing-tolerant grating couplers | Generic authoring, reconstruction and readiness contracts; local-supermode code only as a regression witness | Full-wave 3D reference, ports/modes and fabrication law, GPU memory/cost feasibility; current photonic model is not a 3D grating reference | f06 packet after dependency review |
| f08 resonance-resistant automation structures | Generic physical/measurement and finite decision-study custody | Supports, damping, frequency/forcing population, harmonic reference and cheap-baseline adequacy | f08 packet |
| f13 compact industrial compressor silencers | Generic authoring/reference-custody pattern and analytic controls | Passive acoustic impedance/termination, Helmholtz verification and proof that transfer matrices are insufficient | f13 packet; park if no added value |
| f17 passive micromixers | Generic case, evidence and OpenFOAM ledger patterns | Flow provenance and charged flow solve, scalar conservation/positivity, outlet-sampling law, anti-smoothing controls | f17 packet |

`carbon/challenge_pipeline/families.json` remains the active queue.
`carbon/challenge_pipeline/protocol.json` remains `DEFINING`; Phase 1 step 2
is not completed by this packet. None of these entries supplies a scientific
population, runtime Challenge ID, spending grant or protected test case.
