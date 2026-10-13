# OWNER-PLATING-REFERENCE-01, note 01 — the panel's "0 of 31 flipped" did not hold at scale

Date: 2026-10-13
Status: ADOPTED. Additive note to
`2026-10-13-OWNER-PLATING-REFERENCE-01.md`, whose bytes are unchanged, as are
those of its two errata.
Authority: PR Head, recording a measurement from Data Collection's D3 under
`VALIDATOR-PLATING-REF-V2-02`.
Why this note exists: **the owner's approval partly rested on that figure.** A
record whose basis has been measured and found not to generalise should say so
beside itself, not be left for a reader to discover from newer evidence.

## What the record relied on

The D2 panel reported **0 of 31** near-onset cases flipping their label when
re-solved. That was offered as evidence that the near-onset labels were stable
and the re-reference could proceed on the scale that was approved.

## What D3 measured

At 669 cases rather than 31, **5 labels flipped from FEASIBLE to INFEASIBLE**:

| | cases | FEASIBLE → INFEASIBLE |
| --- | --- | --- |
| PDD development set | 611 | **5** |
| EV4 | 58 | **0** |

The five are `D-0073` (c1 = 1.75; c2 = 0.2, 0.4, 0.6) and `D-0109`
(c1 = 1.25; c2 = 0.2, 0.4), **all `source: pdd`**.

So the panel's result was not wrong about its own 31 cases, and it did not hold
at scale. A flip rate of 0 in 31 is consistent with the measured 5 in 669 —
roughly 0.8% — which is exactly why 31 cases could not have detected it. The
panel was too small to establish what it was used to support, which is a
different fault from being mistaken.

## What this note does and does not do

- **It does not re-score anything.** The D4 mechanism is annotation only, and
  the affected evidence gets additive notes beside it rather than edits.
- **It does not withdraw the owner's approval or any figure.** D3 ran, the
  re-reference is in hand, and the cost was confirmed separately.
- **It records that one stated basis did not generalise**, so that the next
  decision resting on a small panel is sized against this.

## Count by `source`, never by the case-id prefix

All five flipped `case_id`s begin `ev4:` — `ev4:D-0073:c1=1.75,c2=0.2:0` and so
on — while their `source` field is `pdd`. On 2026-10-13 that artifact misled
three readers, the Carbon Validator among them, into recording the five as EV4
labels; the correction came from counting by `source`. Any later audit of these
counts should read the `source` field and ignore the prefix.

The transition is also measured against one specific pair of columns:
`labels.json`'s `old_label` against `labels-v2-r1.json`'s `label`, joined on
`case_id`. The other available pairs — `labels.json`'s `new_label`, which is the
superseded 0.6 mV draft, and `labels-v2-r1.json`'s `draft_label` — give
different numbers and are not this transition. The merge manager computed two of
those wrong pairings before arriving at the right one.
