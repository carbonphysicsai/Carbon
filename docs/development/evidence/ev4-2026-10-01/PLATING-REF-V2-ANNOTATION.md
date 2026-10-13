# EV4 under battery-plating-ref-v2 — eight labels become UNRESOLVED, none was false-safe

Date: 2026-10-13
Status: **Annotation only. Nothing in this evidence set is re-scored, and no
pinned file or digest is edited.** This is a new sibling file; `ev4-2026-10-01`
is EV4's frozen reference run, the public copy D3 pinned by `EV4_SHA`, and its
bytes are evidence.
Authority: `VALIDATOR-PLATING-REF-V2-02` under `OWNER-PLATING-REFERENCE-01` D4.
Sealed labels: `docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json`,
sha256 `cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069`.

## What changed for EV4

D3 re-solved the near-onset cases at mesh 160 and the band was re-derived to
1.0 mV with the window's upper edge at 4.5 mV. Of EV4's **58** re-solved cases:

| transition | count |
| --- | --- |
| FEASIBLE → FEASIBLE | 9 |
| FEASIBLE → **UNRESOLVED** | **8** |
| FEASIBLE → INFEASIBLE (false-safe) | **0** |
| UNRESOLVED → INFEASIBLE | 35 |
| UNRESOLVED → UNRESOLVED | 6 |

**No EV4 label was false-safe.** The five known false-safe labels in D3's run
are PDD development cases, annotated separately at
`docs/development/evidence/battery-score-tuning/PLATING-REF-V2-ANNOTATION.md`.

## The eight cases now UNRESOLVED

```
ev4:D-T14-S0.33:c1=1,c2=0.2:0
ev4:D-T14-S0.33:c1=1,c2=0.4:0
ev4:D-T14-S0.33:c1=1,c2=0.6:0
ev4:D-T24-S0.12:c1=0.75,c2=1:0
ev4:D-T5-S0.12:c1=0.75,c2=0.4:0
ev4:V-T19-S0.40:c1=1,c2=0.8:0
ev4:V-T9-S0.06:c1=1.5,c2=0.2:0
ev4:V-T9-S0.06:c1=1.5,c2=0.4:0
```

Five designs: `D-T14-S0.33`, `D-T24-S0.12`, `D-T5-S0.12`, `V-T19-S0.40`,
`V-T9-S0.06`.

A FEASIBLE label becoming UNRESOLVED means the margin sits inside the
re-derived band, so the reference no longer supports a feasibility claim either
way. It does **not** mean the case is infeasible.

## Consumers of these labels

Every result or measurement file in the repository that references these
designs. A reader of any of them should treat a feasibility claim resting on
the eight cases above as UNRESOLVED under v2:

- `docs/development/evidence/graphite-run5-q1/results.json`
- `docs/development/evidence/graphite-run5-q1-refined/results.json`
- `Business/research/verify-aware-score/results.json`
- `Business/research/value-metric-v2-stress/results.json`
- `Business/research/value-metric-v2-rev2-curves/results.json`
- `Business/research/value-metric-v2-rev2-curves/public-measurements.json`
- `Business/research/value-metric-audit/results.json`
- `Business/research/score-candidate-attacks/results.json`
- `Business/research/question-resolution-rate/results.json`
- `Business/research/plating-onset-sensitivity/results.json`
- `Business/research/battery-advantage-families/results.json`
- `Business/research/battery-advantage-families/measurements.json`

One annotation with a consumer list, rather than a note in each.

## Deliberately excluded, and why

- **The contracts** are task definitions, not label consumers.
- **`plating-convergence-02` and `plating-rereference-01`** are the reference
  studies themselves.
- **`battery-quiz-designs`** was checked and excluded. Of the eight cases only
  `V-T19-S0.40` at `c1=1,c2=0.8` appears in
  `grid-resolution-v1/grid-resolution.json`, and its `verdict_coarse` and
  `verdict_refined` are both **null** — it holds no feasibility label for these
  cases.
- **`battery-score-candidates-b1`** was checked and excluded: the word
  "feasible" appears in prose in its README, and no case id from the eight
  appears anywhere in the set.

## Count by `source`, never by the case-id prefix

**Every `case_id` in these files begins `ev4:`, PDD rows included.** The `source`
field is authoritative. On 2026-10-13 that artifact misled three readers,
including the Carbon Validator, into recording five PDD cases as EV4 labels.
Counting by prefix also turns the 19 pending EV4 cases into 103.

The transition above is measured against one specific pair of columns:
`labels.json`'s `old_label` against `labels-v2-r1.json`'s `label`, joined on
`case_id`. The other available pairs — `labels.json`'s `new_label` (the
superseded 0.6 mV draft) and `labels-v2-r1.json`'s `draft_label` — are different
quantities and give different numbers.

## Pending, not decided

Nineteen EV4 cases fall in the newly opened [3.5, 4.5) mV window and are
`pending-m160-r1:UNRESOLVED` — undecided rather than unfavourable. Solving them
later is a recorded relabel under the same rules.
