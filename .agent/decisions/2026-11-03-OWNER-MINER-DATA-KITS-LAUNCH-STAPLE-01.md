# OWNER-MINER-DATA-KITS-LAUNCH-STAPLE-01: a "make your own practice data" kit per Challenge, as a staple of the launch version

Date: 2026-11-03 (CST, ~07:33)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words: "Nope make kits and give them how we did it. Doesn't make us liable. Have Launchpad get a subagent to do this for all challenges I want this to be a staple of the launch version. Miners generate data for improved practice"
Context: the Lead had suggested a build-it-yourself recipe for RB 2.0's internal-only solver image, plus a legal look. The owner answered with the words above.

## Decided
- **Every launch Challenge gets a miner data kit.** It gives "how we did it": the public reference setup (decks, mesher and solver build recipe, case runner, output parser), so miners can generate their own data for practice on their own compute.
- **Who builds them:** Launchpad, using a subagent, for all Challenges. The kits are a staple of the launch version (a miner-app entry point plus docs).
- **Ribbed Bracket:** the kit ships the build RECIPE for the 64-bit solver, not the internal-only built image. The owner's words settle the liability question for the kits.

## Limits (existing rules the kits must keep; the Validator checks each kit)
- **Never in a kit:**
  - sealed material: hidden cases, case banks, seeds, sealed packs, keys, custody paths;
  - the exact out-of-range extents (BT 3.0: kinds + rule only, owner 2 Nov; the same for every version whose region is unpublished);
  - anything that reconstructs the hidden exam.
- Kit results are stated plainly as possibly differing from Carbon's pinned reference, which stays the only grading truth.
- Carbon never rents, runs or bills miner compute. The kits run on the miner's own machine.

## Addendum (~07:35 CST, owner, Lead session)
Owner's words: "The kits also keep them from fitting data sets. I like that more." Then: "Give them the internal range. All the rules needed. What we're testing. And let them build."

Each kit (and its version's "How you're tested" page) gives:
1. **The internal range:** the version's signed training box (every input's range, the categorical choices, the constraints such as RB 2.0's B2 load position). The kit generates data anywhere inside it.
2. **All the rules needed:** the gates, the score formula, the minimums as published, the information budget and how it counts, the speed gate, the submission rules (lr, fitted constants within the budget, no trained weights), and the build and training rules.
3. **What we're testing:** the graded outputs and targets, that part of the hidden exam lies outside the training range, and the region KINDS plus the rule that sets them.

**Lead's reading, stated to the owner:** "internal range" = the training box. The exact out-of-range extents stay hidden, per his 2 Nov "Kinds + rule only". This addendum does not reverse that. If he meant the extents too, that is his explicit reversal to give.

"Let them build": no new restrictions on how miners build. The Lead's suggested "kit-data fit" strong check is NOT adopted; it was asked and not answered.

## Addendum 2 (~07:38 CST, owner, Lead session): kits REPLACE the shared practice bank
Owner's words: "You know what I want here. Ship the optimal version of it. I just want to ditch the same practice cases for everyone thing and transition to data kits. Reason through the best possible way to do this for the outcomes we want. You know them. Focus"

- **Design:** codex-queue/reports/DATA_KIT_PROGRAM_DESIGN_20261103.md (sha256 prefix a034e183062f1f5a). New versions ship kit + a ~8-case verify set + a local scorer + the submission mechanics check instead of a 40-case shared bank.
- **Live versions' practice:** unchanged until each retires. Nothing is rescored.
- **The "kit-data fit" strong-check shortcut:** PROPOSED, not adopted. It waits on the owner's words.

## Addendum 3 (~07:38 CST, owner, Lead session): the "kit-data fit" strong check is ADOPTED
Owner's words: "Add the fit check."

- **What it is:** before any new version opens, the shortcut panel is fitted on kit-scale data, including outside the training range, and confined to the information budget by the version's own counter. The panel: the engineer shortcut, CV-tuned GP/ridge/GBM/kNN, sparse physics regression, previous kings and graph-recipe fits.
- **The verdict:** if that fit beats every learned model on the hidden exam, the version does not open, and it goes to EXAM_MISS_PLAYBOOK (never rescored).
- **The fit data:** it must be disjoint from every sealed case.
- **Spend:** the first runs use data already solved (/usr/bin/bash). Any NEW solves for it come to the owner as a figure first, unless they fit inside an existing card.
