# PDD development labels under battery-plating-ref-v2 — five known false-safe cases

Date: 2026-10-13
Status: **Annotation only. Nothing here is re-scored, and no pinned file or
digest is edited.** This is a new sibling file; `registry-v9.json` keeps its
bytes.
Authority: `VALIDATOR-PLATING-REF-V2-02` under `OWNER-PLATING-REFERENCE-01` D4.
Sealed labels: `docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json`,
sha256 `cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069`.

## The five false-safe labels

D3 re-solved the near-onset cases at mesh 160. Five PDD development labels were
**FEASIBLE and are INFEASIBLE under v2** — the one direction that matters most,
because a false FEASIBLE asserts safety the reference does not support:

| design | conditions | m20 → m160 |
| --- | --- | --- |
| `D-0073` | c1 = 1.75; c2 = 0.2, 0.4, 0.6 | 2.243 → **−0.016** |
| `D-0109` | c1 = 1.25; c2 = 0.2, 0.4 | 2.316 → **−0.335** |

Five cases across two designs: **`D-0073` ×3 and `D-0109` ×2.**

Both were labelled from mesh 20, which overstated the margin. **At mesh 160 the
margin is negative in both**, which is what makes the old labels false-safe.

**Extrapolation is measured for only one of the five.** The Richardson
extrapolation needs the 40/80/160 rungs, which exist only for D3's 67-case
subsample:

- **`D-0109` is not in the subsample at all**, so it has **no measured
  extrapolation**. Its mesh-160 margin of −0.335 is the measurement.
- **`D-0073` is in the subsample at three conditions** — extrapolated −1.193 at
  c1 = 1, c2 = 0.8; −0.322 at c1 = 1.75, c2 = 0.8; −0.453 at c1 = 1.75,
  c2 = 0.4. Of those, only **c1 = 1.75, c2 = 0.4 is one of the five false-safe
  cases**, with a measured extrapolation of **−0.453**.

So the claim that the truth is more negative than mesh 160 is **measured** for
one false-safe case and **inferred** for the other four, from the finding that
mesh 160's error was positive in all 67 subsample cases. That inference is
sound and it is not a measurement, and the distinction matters to anyone
auditing how far below zero these cases actually sit.

## These are PDD development cases, not EV4

**Count by the `source` field, never by the case-id prefix.** All five
`case_id`s begin `ev4:` — `ev4:D-0073:c1=1.75,c2=0.2:0` and so on — while their
`source` is `pdd`. That artifact caused these five to be recorded as EV4 labels
on 2026-10-13 by three separate readers, the Carbon Validator among them; the
correction came from counting by `source`.

**EV4 itself has zero known false-safe labels**, annotated at
`docs/development/evidence/ev4-2026-10-01/PLATING-REF-V2-ANNOTATION.md`.

## Consumer

`registry-v9.json` in this set is the **only in-repository consumer** of these
labels: a search of the whole repository for `D-0073` or `D-0109` returns it and
`plating-rereference-01/cases.json`, which is D3's own input and needs no note.
The PDD source records live outside the repository.

Any score-lab or score-proof development result resting on a FEASIBLE label for
those five cases is resting on a label v2 refutes. Nothing is re-scored; the
affected inputs are named so that a reader does not have to rediscover them.

## Scope

- **Development inputs only.** EV5's sealed batch is never read and keeps its
  general optimism note.
- **Annotation, not re-scoring**, per D4.
- The transition is measured as `labels.json`'s `old_label` against
  `labels-v2-r1.json`'s `label`, joined on `case_id` — not against
  `labels.json`'s `new_label` (the superseded 0.6 mV draft) or
  `labels-v2-r1.json`'s `draft_label`, which are different quantities.

## The wider finding this belongs to

The D2 panel reported **0 of 31** cases flipping. At 669 cases, 5 flipped — all
PDD, roughly 0.8%, a rate 31 cases could not have detected. That is recorded as
an additive note on the owner's record
(`.agent/decisions/2026-10-13-OWNER-PLATING-REFERENCE-01.note-01.md`), because
his approval partly rested on the panel's result.
