# Score proof: the owner's run (SCORE-PROOF-01)

This runs on the operator host only (the AX42), against the sealed tuning
set. It needs no new reference solve, spend or chain write. The new members
rebuild on free host CPU, and only aggregates are returned.

## Before

1. **The tuning work directory and quiz.** You need the tuning work
   directory `<W>` and its quiz `<Q>` from
   [HIDDEN_POOL_AND_TUNING_RUNBOOK.md](../../graphite/HIDDEN_POOL_AND_TUNING_RUNBOOK.md)
   section B.
2. **The decision results.** Copy the proof's development decision results
   from the PC's shared tuning inputs: `ev4-dev-proof-v1-results.json`, which
   the Test Engineer supplies, becomes `<DEV_RESULTS>` on the host. These are public development data:
   EV4's references and no sealed case.
3. **Main.** Update the repository on the host to main after this ticket's PR
   merges:

```bash
git -C ~/Carbon fetch origin && git -C ~/Carbon checkout --detach origin/main
```

## Run 1: rebuild the new members, then compare every rule (selection)

```bash
cd ~/Carbon && python -m scripts.dev.battery.score_proof_run --work <W> --quiz <Q> --dev-results <DEV_RESULTS> --out <W>/proof
```

- **The estimate.** It first prints its estimate: the registered members'
  rebuild CPU hours. Add `--estimate-only` to see it without running.
- **What it rebuilds.** The 11 registered Level 0 members: stage A's 5
  bundles, and minerH's and minerI's 6 submissions. They rebuild on host
  CPU and predict the sealed tuning set and the quiz.
- **Then it scores and compares.** It rescores, and compares every
  registered rule on the selection fold.
- **Read** `<W>/proof/selection.md` and pick a rule there. Nothing on that
  page is proof.

## Run 2: the proof for your pick (confirmation, sealed questions)

The confirmation runs on new, sealed decision questions, never the
development data that selection used. It is a pre-registered
group-sequential design (`proof-sequential-v1.json`: target ±0.15, an
interim look at 150 questions, O'Brien–Fleming spending). Follow
[SCORE_PROOF_CCX63_SHEET.md](SCORE_PROOF_CCX63_SHEET.md):
- the AX42 draws and keeps the sealed questions;
- one hourly CCX63 solves them under the startup-host custody procedure;
- the AX42 merges, rebuilds the members and runs the interim look with
  `--rule <PICK>`.

`<W>/proof/confirmation.md` opens with **PROVEN**, **FAIL**, **FUTILE** or
**CONTINUE** and names each failed screen. A gate that misses an unsafe
member reports FAIL with the cutoff range that would catch it; the cutoff
stays yours.

## Return

Send back `<W>/proof/selection.md` and `<W>/proof/confirmation.md`, and the
`.json` files if you want the detail. They are aggregates only: no case,
input, output or reference.

## What is not in this run

- **Levels 1 to 3** join through the level-aware ticket. The L1 round's
  bundles are pre-registered at submit time.
- **Level 4** waits for G5's acceptance.

Both are listed in `proof-members-v1.json` under `missing`.
