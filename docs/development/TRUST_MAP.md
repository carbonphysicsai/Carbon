# DEVELOPMENT trust maps (PLT-05)

Run `python -m carbon.battery.trust_map --panel disclosed-panel.json --out maps`.
The offline tool writes one JSON and one SVG per model, named by a hash of the
model label. The JSON retains the full label and explicit input provenance.
The SVG shows median/p90 reference error and median top-model disagreement
for every battery output, in three SOC0 panels over c1 × ambient. JSON also
contains disagreement p90. c2 is pooled over the supplied public cases.

The file is an explicit projection, **not** an evaluation record. Its exact
top-level keys are:

```json
{
  "schema": "carbon.trust-map.disclosed-panel.v2",
  "disclosure": {
    "kind": "PUBLIC",
    "evidence": "public publication or recorded release location",
    "source_sha256": "64 lowercase hexadecimal characters"
  },
  "reference_image": "sha256:<64 lowercase hexadecimal characters>",
  "reference_verification": {
    "family": "battery-v3",
    "criteria_digest": "sha256:<registered criteria digest>",
    "image_digest": "sha256:<the same reference image>",
    "evidence": "operator source description; not application acceptance"
  },
  "cases": [],
  "models": {},
  "top_models": ["model-a", "model-b"]
}
```

Each case has exactly `id`, `inputs`, and `reference`. Battery inputs are c1,
c2, t_amb_c and soc0. Reference and prediction objects have exactly voltage_v
(121 values), temperature_c (121 values), plating_margin_v (one scalar), and
capacity_ah (four values). `models` maps each model name to an object keyed by
**every** case id, with these four output fields. At least two distinct models
are named in `top_models`; they must already be selected externally on public
evidence. Missing or additional cases are refused. `RELEASED` is the other
allowed disclosure kind, with an actual release record supplied as evidence.

Provenance is an operator assertion, not a cryptographic attestation. The input
must already have been cleared for disclosure; the CLI cannot determine if
someone copied hidden data into a falsely labelled file. Never point it at a
protected store or construct its projection from unretired exam cases. The
closed shape refuses extra metadata, and output contains only aggregates and
the allowed provenance, never case identifiers, inputs, predictions or seeds.

Native v2 requires the registered family/image/criteria acceptance link; a
caller-supplied PASS/Boolean record or unregistered re-pin is refused. The
separate owner link records bounded particle-diffusion/lumped-heat code
verification; the earlier MMS machine verdict keeps its original bytes and
`accepted_development_pass: false`. Neither record accepts DFN/plating use or
establishes physical adequacy, real-cell safety, current label resolution or a
measured product map. Operator disclosure/source descriptions remain assertions.

The [2026-10-13 Product audit](../../Business/research/customer-deliverable/EVIDENCE_HONESTY_2026-10-13.md)
records the `battery-plating-ref-v2` transition under OWNER-PLATING-REFERENCE-01.
Before required resolved mesh-160 evidence and current-use acceptance, no usable
near-onset label is established; **SOLVER_NOT_ACCEPTED / GAP** remains. An old
mesh-20 cell/image match cannot supply v2 accuracy, calibrated uncertainty,
feasible-pick evidence or TRUST permission. Reference refinement/failure/fallback
costs are required before a current speed or equal-budget value claim. Historical
map/EV4/EV5/score-proof values retain their original meaning: annotate, never
re-score. No new version default, label adapter or runtime capability is added.

Error is RMS across an output's coordinates for each case, in native units;
the cell reports its median and linearly interpolated p90. Disagreement is
the RMS of coordinate-wise population standard deviations among named top
models. No cross-output scalar or scientific weight is used. Display bands
include the upper endpoint in the final cell; interior edges start the next
cell. Near-limit outlines mean at least one observed reference case has
absolute plating margin ≤ 5 mV or peak temperature ≥ 55 C, using existing
DEVELOPMENT constants. They are observed-cell outlines, not an inferred
physical boundary. Gray means NO_DATA; absent evidence is never zero error.
Each row labels its color range; color ranges may differ between model files.

`carbon.trust_map.core.build_maps(panel, spec)` is Challenge-neutral. A spec
declares two axes, a band axis, marginalized inputs, output lengths/units and
closed near-limit predicates (`max` or `abs_min`, `le` or `ge`). Battery's
adapter derives its display grid and predicates from existing public domain
constants. All outputs are DEVELOPMENT descriptions, never qualification,
gates, rankings, rewards, or a scored-case selection channel. No runtime caller
uses the maps to alter scored P(x), Q(x), or w(x).
