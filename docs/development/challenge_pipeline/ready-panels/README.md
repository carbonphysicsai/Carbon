# Cooling and f02 registration handoffs

READY-TO-RUN-PANELS-01 uses #977's generator, not a second case identity policy.
No solver runs, spend, hidden/AX42 data or scientific adoption. Starting main
is 65ef88660; the live dependency is #977 at ff3ec0df9.

**Neither numeric panel is final today.** A source-confirmed expanded tuple is
ready for DC registration review only after its input return. Current public
authority does not contain enough accepted numeric inputs or completed AND
scheduled receipts to truthfully deduplicate all planned work. The two JSON
gap manifests are durable handoff checklists, not invented runnable cases.

## Smallest return, one bundle per Challenge

1. The generated ten-section packet draft plus a #977
   `carbon.onboarding.panel-seed.v1`: exact physical action designs, condition
   inputs and refinement-rung settings; solver/environment/material/observer/
   geometry-grammar pins; per-rung CPU estimate and its retained basis.
   Each pin is a `sha256:<64 hex>` artifact-manifest identity, not a mutable
   version/tag label. Keep solver versions and readable names inside that
   retained manifest.
   Include interfaces/maps/waveforms in the input identities. Readability labels
   alone are not physical pins. Scientific adoption/applicability receipts
   accompany the seed; hashing it does not approve it.
2. A `carbon.development.solve-inventory-snapshot.v1` with schema, challenge,
   scope PUBLIC_DEVELOPMENT, source_commit (40 hex), as_of_utc, namespace, rows,
   inventory_digest. Each row has identity, COMPLETED or SCHEDULED state,
   receipt and the full body: challenge, coordinates, inputs, rung_settings,
   pins. `seal_inventory(body)` computes its digest. List ALL eligible retained
   and scheduled solves in that public namespace, including an explicit empty
   snapshot if none exist. Completed means accepted usable reference work, not
   a failed job. Retain failures/costs separately. A source hash proves bytes,
   not that the producer included every possible solve.
3. Public scientific/value acceptance and operating-stage authority remain
   external DC/owner decisions, not new flags in this tool. Refresh the snapshot
   if new work is scheduled before registration. Cross-Challenge identities
   and changed map/observer/rung/material/environment pins cannot match.

```sh
python -m carbon.challenge_pipeline.onboarding.registration \
  --packet packet.json --packet-sha256 PACKET_BYTES_SHA256 \
  --seed panel-seed.json --seed-sha256 SEED_BYTES_SHA256 \
  --inventory public-solve-index.json --inventory-sha256 INVENTORY_BYTES_SHA256 \
  --output new-registration-handoff.json
```

The exact deduplicated tuples retain bodies, source receipts and each
design/condition/rung label. Completed, scheduled and prospective new cases are
separate. Unknown inventory is not zero reuse: remaining-work CPU and new-case
lists stay null. Prices and billed wall hours stay unknown; summed CPU estimates
do not authorize a rental or satisfy an all-in cap. No output overwrites a
prior report. Every completed envelope still says NOT_APPROVED and
dispatch_authority=false; Data Collection registers after acceptance.

## Current scientific input gaps

**Cooling:** freeze the selected buyer inlet/lid characterization and interface
maps/TIM; the current case-plane 85 C anchor is adopted, but final alternatives
are not. Supply accepted cell geometry/flow action coordinates, cell-only
hydraulic allocations/objective, source normalization, exact observer/package
and rung pins, retained Set A/value/refinement returns and schedule snapshot.
Do not substitute the historical full-plate 50 kPa/2.5 W/3 L/min constraints or
claim a uniform-only panel covers hotspots. Cost 0.45 CPU-h is a historical
reported planning context, not a current complete timing receipt.

**f02:** freeze the expanded action set and all 24 matched contexts; the
16-point seed is still a HUMAN_INPUT proposal in f02-round2.json. The legacy
nine-action menu cannot deliver five distinct feasible AND five distinct
infeasible actions in one condition. Supply accepted thermal/energy bands and
exact standard/refined spatial/time grids and observer pins, plus all retained
and scheduled tuple receipts. The 2–3 CPU-minute figure is owner-reported, not
a pinned per-case timing receipt; refinement cost is unmeasured. Do not turn
the old 50-launch feasibility plan into permission for a 384-solve bank.

The shared value return remains per stratum: complete feasible answer,
>=5 distinct feasible and >=5 distinct infeasible within TWO accepted bands,
meaningful buyer-unit spread and changing answers. Boundary actions cannot be
chosen to guarantee passing results. Refine all decision contenders under the
registered rule, not only a favored model's winner. Cheap-baseline comparison
is required for TESTED, with the #994 material contract.

The missing inputs block numeric registration, not comparator/dossier tooling.
No repeated self-pings or fictional progress. Data Collection supplies the
tuple/index return; owner/science resolve only the still-unadopted values.
