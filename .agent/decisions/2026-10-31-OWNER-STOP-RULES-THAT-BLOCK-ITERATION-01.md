# OWNER-STOP-RULES-THAT-BLOCK-ITERATION-01: stop adding rules that block iteration without protecting anything

Date: 2026-10-31 (CST)
Status: DIRECTIVE from the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "we HAVE to stop implementing rules that don't allow us to iterate. That is only hurting us and not protecting us. It's extremely frustrating how often this over protection is causing us issues!"

## Context

During the 30–31 October launch push, several guards each cost hours without stopping a real attack:
- GPU receipts voided by any image change;
- prepared receivers breaking when the box pulled a scripts-only commit (exact-revision pin);
- a dirty-tree refusal on hand-placed record files;
- the app's push block on teammate-triggered pushes.

## Decided

- A new or existing guard that blocks normal iteration must name the real harm it prevents: exam data or grading integrity, containment, keys, money, or disclosure (consistent with OWNER-MAX-MINER-FREEDOM and "max miner freedom, exam safe").
- Guards that protect none of those are removed, or turned into a warning or a log line.
- Where a guard protects something but costs a full rerun, prefer a cheap check of the real outcome (for example a sampled bit-identical spot check) over a hard rebuild.
- The Validator audits the current guards that cost the team time on 30–31 October and brings the owner one list: keep (with the harm named), soften (how), or remove.

## Bounds

- Exam-data custody, grading integrity, containment, keys and money protections stay.
- Each removal or softening still lands with tests, and the scoring meaning stays unchanged.
