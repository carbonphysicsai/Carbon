# OWNER-F02-F08-EXAM-DRAW-01: F02 and F08 sealed exams are drawn from their approved near-limit laws

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session ("approve").
Implementation: **not yet implemented.** Data Collection is building the F02 and F08 reference families (`EXAM_BACKLOG_F02_F08_FAMILIES_SCOPE_20261020.md`).

## Decided

- **The exam population for each new sealed F02 and F08 batch** is the owner-approved TRAIN near-limit law, with fresh seeds. Every case is disjoint from TRAIN and from every published case.
  - **F02:** the S1 law, 70–100 W and 4–6 s (OWNER-F02-TRAIN40-V2-01).
  - **F08:** the N1r fit placement around 0.15 mm/N.
- **8 cases per batch,** the current exam sizes.
- **Served kinds mirror the current development exam:** F02 is one cold-context decision over its actions, and F08 is near-limit geometries.
- **Rotation follows OWNER-CADENCE-AND-ROTATION-02:**
  - one active version (`active_batches` 1);
  - a 90-day maximum (`every_blocks` 648,000);
  - weekly fresh draws come from the backlog, and 2 QA-passed versions are kept.
- **Every batch passes the exam batch QA** (`EXAM_BATCH_QA_SPEC_20261020.md`), with a straddle of at least a third per side and the registered U records, before going live.

## Implementation note (Validator, 2026-10-20)

- **The problem:** N1r's original rule placed cases nearest fixed predicted-compliance targets, so it ignored the seed, and a fresh seed would have redrawn the same geometries.
- **What the F08 sealed draw keeps:** N1r's pinned log-linear fit, its band (0.125–0.175 mm/N) and its safe/unsafe split.
- **What it changes:** each of the 8 cases is drawn uniformly, by seed, from the lattice candidates in one of 8 equal predicted-compliance strata (4 safe, 4 unsafe). That's `claude/exam-families` `1ff37e4f9`.
- **This is the same approved law, made seedable.** It adds no new range.
