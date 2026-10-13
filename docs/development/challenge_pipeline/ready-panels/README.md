# Cooling and f02 registration handoffs

READY-TO-RUN-PANELS-01 uses #977's generator, not a second case identity policy.
No solver runs, spend, hidden/AX42 data or scientific adoption. Starting main
was 65ef88660; #977 (its generator) has since merged. The gap manifests were
refreshed against main on 2026-10-13 (Data Collection).

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
and rung pins, retained Set A/value/refinement returns and schedule snapshot (the cooling
readiness build is in `challenge_pipeline/cooling-readiness/`).
Do not substitute the historical full-plate 50 kPa/2.5 W/3 L/min constraints or
claim a uniform-only panel covers hotspots. Cost 0.45 CPU-h is a historical
reported planning context, not a current complete timing receipt.

**f02:** since this handoff was first written, the 16-action menu over the 24
contexts is registered for development (F02-MENU-V2-REGISTRATION, 2026-10-11,
with EQUAL-BUDGET-V2-F02-MENU; the nine-action V1 row stays as history). Its
registry pins the Elmer image, grids, refinement rule and bands
(`evidence/reference-packages-01/f02-menu-v2/`), and the producer stages
(`evidence-producer-stages.md`) solve it. Still missing: the f02-round2
question law (variant draw and context mass, HUMAN_INPUT), a public completed
AND scheduled tuple snapshot, and a pinned per-case timing receipt including
refinement. Measured so far: about 207 CPU-s per primary solve on a quiet
pinned host, about 336 CPU-s on the loaded operator PC. A known risk: 3 interior
calibration contexts were infeasible for every action, so the f02 value check
on the registered menu is pending before any bank is sized from it.

The shared value return remains per stratum: complete feasible answer,
>=5 distinct feasible and >=5 distinct infeasible within TWO accepted bands,
meaningful buyer-unit spread and changing answers. Boundary actions cannot be
chosen to guarantee passing results. Refine all decision contenders under the
registered rule, not only a favored model's winner. Cheap-baseline comparison
is required for TESTED, with the #994 material contract.

The missing inputs block numeric registration, not comparator/dossier tooling.
No repeated self-pings or fictional progress. Data Collection supplies the
tuple/index return; owner/science resolve only the still-unadopted values.
