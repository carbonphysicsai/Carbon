# OWNER-BATTERY-GATE-PLATING-V2-01: the Battery gate's plating truth moves to battery-plating-ref-v2

Date: 2026-10-19
Status: APPROVED by the owner in the Carbon Validator's session. Owner, verbatim: "more accurate plating labels now".
Implementation: **not yet implemented.** The new gate version is unbuilt as of `a3e0771df`, so EV5's mesh-20 plating truth is the only gate in code.

## Question

EV5 (frozen, #550) judges plating truth from the mesh-20 margin with EV4's band. Mesh-20 is optimistic near onset by about 1.3–2.6 mV (VALIDATOR-PLATING-REF-V2-01). The options were:
- A, a new gate version on the sealed v2 labels;
- B, keep EV5 and show v2 only as informational practice feedback (B5).

The Validator recommended A. The owner chose A now.

## Decided

- **A new Battery gate version, prospective.** EV5 and its results stay frozen as history and are never re-scored.
- **Plating truth per case comes from `carbon.battery.plating_v2`,** the pinned sealed reader, never a copy:
  - |m20| ≥ 15 mV: v2 makes no claim, so the mesh-20 label stands; the case is far from onset, where mesh-20's sign is reliable.
  - A v2 FEASIBLE or INFEASIBLE label: that label.
  - UNRESOLVED (`pending-m160-r1`, or `m160-d3-r1` UNRESOLVED): no plating truth. The case enters neither false acceptance nor near-optimism for plating, and it is never counted as plating-safe. It is counted and reported. Its temperature and CV truth are unchanged.
- **Coverage gap:** v2's sealed labels cover PDD and EV4 sources only, 772 rows. **No EV5 case has a mesh-160 re-solve,** so EV5-population cases inside the window are UNRESOLVED under the new gate until they're re-solved.
  - Mesh-160 re-solves for them are a separate, priced proposal (owner spend).
  - Until then the gate fails closed on those cases and never falls back to mesh-20.
- **Consumers require `rule ∈ V2_RULES`** and count by `source`, as for the bank.

## Not decided here

- The mesh-160 re-solve spend.
- Any threshold or band value. EV4's bands are unchanged; only the truth label changes.
