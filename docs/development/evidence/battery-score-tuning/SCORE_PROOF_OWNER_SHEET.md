# Score proof: the owner's run (SCORE-PROOF-01)

This runs on the operator host only (the AX42), against the sealed tuning
set. It needs no new solve, training, spend or chain write. It re-scores
stored predictions and writes aggregates only.

## Before

You need the tuning work directory `<W>` from
[HIDDEN_POOL_AND_TUNING_RUNBOOK.md](../../graphite/HIDDEN_POOL_AND_TUNING_RUNBOOK.md)
section B. Its `score` step has written `q3-regret.json`. You also need the
development decision results, `<DEV_RESULTS>`: the same
`ev4-dev-tuning-v1-results.json` the tuning curves used.

Update the repository on the host to main after this ticket's PR merges:

```bash
git -C ~/Carbon fetch origin && git -C ~/Carbon checkout --detach origin/main
```

## Run (one command)

```bash
cd ~/Carbon && python -m scripts.dev.battery.score_proof --work <W> --dev-results <DEV_RESULTS> --q3-regret <W>/q3-regret.json --out <W>/proof
```

It takes about 10–20 minutes of CPU and at most about 4 GB of memory. It
prints one line naming the output directory and the member count per
level.

## Return

Send back only `<W>/proof/proof.md`, plus `<W>/proof/proof.json` if you want
the detail. Both are aggregates:
- **per rule:** τ with its 95% interval, and Δτ against the rule in force
  (`G-FEAS/A-Q>@0.05`);
- **known-bad and adversarial members in the top half;**
- **top-1 regret;**
- **gate recall on the unsafe member;**
- **fold stability;**
- **adversarial divergence.**

Each appears per level and pooled. No case, input, output or reference is
in either file. Leave everything else in `<W>`.

## What it decides

Nothing by itself. The report shows whether each registered rule ranks
members by decision value and resists gaming, against the targets: no
known-bad member in the top half, every unsafe member gated, and no
adversarial divergence. Adopting a rule and choosing its cutoffs stay
yours. Levels 1 to 4 have no members yet; their gaps and the cheapest fills
are listed in `proof-members-v1.json` under `missing`.
