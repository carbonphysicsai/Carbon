# Three-arm winnability harness — development proposal

`python -m carbon.design_search.winnability_pilot evaluate INPUT.json
--bootstrap-replicates 2000 --confidence 0.95 --seed SEED` replays a sealed
public held-out panel. `INPUT.json` is a **development** record, not a miner or
official scoring interface. The same input schema works for every Challenge
supported by `equal_budget`; a new Challenge first needs its own registered
budget and replay route. This command performs no fitting, prediction or solve.

The input contains an `equal_budget` sealed `panel`, its registered budget,
the method roles (plain L0 MLP, strongest applicable cheap method, registered
adaptive solver), explicit `P`, `Q` and `w` identities, a `PUBLIC_HELDOUT` role,
one learning outcome per job, and a digest for its complete workflow cost
record. It charges model fitting and cheap-map acquisition over each explicit
served-decision assumption, in addition to per-job screen and solver charges.
The registered solver evaluation, wall and core limits bind every arm. Every
candidate attempted by the underlying replay consumes a complete solve cost,
including an infeasible or failed attempt. Raw source, panel role, provenance,
rights, the declared strongest cheap comparator and adaptive policy must be
reviewed by their domain owners before a real run. A method label alone is not
proof that an arm is the strongest competitor.

The report gives per-stratum pointwise error, agreement, false-feasible,
missed-feasible, abstention, NONE and unresolved counts. It reuses
`equal_budget.compare` for verified value, regret, budget accounting and
cluster bootstrap. Its additional paired model-minus-cheap improvement uses
the same per-job replay and independent cluster bootstrap. Finite-bank MLP
regret is headroom relative to the solved bank only, never a global optimum.
An unresolved reference blocks advantage replay; it does not penalise the
model. With fewer than two independent clusters the interval is absent.
Learnability, advantage and headroom remain separate evidence questions with
**HUMAN_INPUT** useful-accuracy, gain and contestability limits. No PASS, PARK,
Challenge qualification or launch state is produced.

## Historical public EV4 battery row

Reproduce the aggregate row with:

```text
python -m carbon.design_search.winnability_pilot battery-ev4-retro \
  --res07 Business/research/value-metric-audit/results.json \
  --public-input-root <owner-supplied-public-ev4-proof-copy> \
  > docs/development/challenge_pipeline/challenge-factory/battery-winnability-retro.json
```

The command verifies the public reference SHA-256 and three plain MLP bundle
SHA-256s against committed RES-07's manifest. It extracts only aggregate
nominal, shifted, robust-SOC and robust-temperature results. Raw predictions,
case IDs, references and the local `codex-queue` path are not committed.
Historical gain unit `u` equals 120 seconds of CV-onset benefit, **not**
battery-v3 full-session charging time or money. The bilinear map uses D-only
cache; the fixed-order solver is an illustrative research comparator, not a
strong adaptive solver. Caps 1/3/5 count complete-action verification tokens;
model fitting, cache acquisition, inference, refinement and full solver
workflow costs are not matched. Therefore the battery row says
`INDETERMINATE_UNMATCHED_COMPLETE_COST` even where the MLP gain exceeds an
illustrative arm. It does not support a VALUE-BAR or winnability verdict.

The next real pilot needs independent rights-cleared public held-out buyer
questions, a settled full reference panel, plain L0 predictions, the strongest
applicable cheap baseline, a preregistered adaptive solver policy, complete
time/core/evaluation costs and owner-selected thresholds. EV5, hidden or sealed
material and AX42 evidence are outside this harness.
