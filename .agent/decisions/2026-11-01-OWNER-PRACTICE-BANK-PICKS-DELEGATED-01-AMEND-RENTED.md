# Amendment to OWNER-PRACTICE-BANK-PICKS-DELEGATED-01: practice-bank solves may run on rented pods

Date: 2026-11-01 ~15:50 CST
Status: DECIDED by the Lead, under the same owner delegation ("you answer these optimally"; record 25f2d4b8505ce25358f992f7e9850ca6b90c3d43). The owner's later directions also apply: run quick wins in parallel on rented compute, and get the four versions done as soon as possible.

## Change
- Old condition: "Owned hosts only, $0 rented compute."
- New condition: the practice-bank solves may run on rented single-tenant pods, within the week's USD 250 (record e6c454b7) and a per-Challenge card cap of USD 30 (the practice cap already listed in the 1 Nov brief).

## Why this is safe
- The draw (seed, overdraw, candidate list, exclusion check) stays in custody, unchanged.
- Only the final N = 40 published practice inputs per Challenge go to the pods. They become public anyway, so this is the RENT-FREELY class (no hidden-exam material).
- Every other condition of the original record stands: N = 40, distance 0.10, inner half only, the probe-first stop rules, Q1a, and never entering scoring.

## Why change it
- The owned hosts (AX42, custody2, Hostkey, GPUYard) are the custody bottleneck for the four new versions, and rented pods cost about $1–3 per Challenge for these solves.
