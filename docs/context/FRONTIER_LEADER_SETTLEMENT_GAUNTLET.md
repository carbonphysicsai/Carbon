# Frontier Leader Settlement Gauntlet — Full Subnet Incentive Loop

**Branch:** `design/symbolic-numeric-integration`  
**Status:** executed design/economic gauntlet; no current P0 chain behavior changed.  
**Purpose:** Stress-test Carbon's intended subnet mechanism: several simultaneous qualified Challenges, equal base emissions opportunity per Challenge, and rewards only when a submission establishes a new scientifically verified Challenge frontier.

---

# 1. Executive conclusion

The clarified Carbon incentive mechanism is stronger than the earlier proportional-within-Challenge draft:

> **Carbon should reward verified frontier advances, not permanent incumbency and not proportional participation.**

The scientifically clean loop is:

```text
reward-enabled qualified Challenges
        ↓
equal logical Challenge slots
        ↓
submissions during settlement window
        ↓
independent screening / reconstruction
        ↓
frontier promotion exam
  incumbent + contenders
  same fresh hidden exam identity
        ↓
Score Pack / ScoreEngine
        ↓
LeaderReplacementPolicy
        ↓
verified frontier advance?
        ↓ yes
FrontierAdvanceEvent
        ↓
that Challenge's slot is payable for the period
```

The gauntlet found one major chain-adapter issue: **equal logical Challenge slots with unpaid inactive slots are not preserved automatically by ordinary normalized validator weights.** Current Bittensor weight rows and miner incentives are normalized. Therefore zeroing Challenges without a frontier event can redistribute their intended unused share to winners in other Challenges unless Carbon implements an explicit withholding/burn/recycle adapter. This must be solved on testnet; it must not be hidden inside the scientific score.

---

# 2. Intended economic primitive

Let the settlement window have `N` Challenges with exact state:

```text
LIVE
AND reward_enabled
AND scientific qualification current
```

Each receives the same **logical base slot**:

```text
slot_c = 1 / N
```

This is not based on Challenge score magnitude, popularity, compute cost, or number of submissions.

For Challenge `c`:

```text
frontier advance in period -> PAY(slot_c)
no frontier advance          -> WITHHOLD(slot_c)
```

The v1 recommendation is **no carry-forward**. A dry period does not create an accumulating jackpot.

Why:

- avoids strategic withholding while bounties grow;
- avoids a saturated Challenge building an arbitrarily large one-shot reward;
- keeps every period interpretable;
- preserves the statement "only a new winner gets that period's Challenge emissions."

Future sponsor-funded bounties may exist separately from the equal protocol base.

---

# 3. Gauntlet A — cross-Challenge comparability

### Case

Seven Challenges emit scores on different physical problems and different Score Packs.

### Bad mechanism

Pool all raw scores and pay highest scores globally.

### Result

**FAIL.** Raw Challenge scores are not common scientific units.

### Intended mechanism

Equal logical Challenge slots make cross-Challenge score comparability unnecessary:

```text
Burgers advance?  yes/no
Poisson advance?  yes/no
Darcy advance?    yes/no
...
```

Each Challenge uses its own qualified scientific ruler.

**PASS.**

---

# 4. Gauntlet B — permanent incumbent rent

### Case

A miner establishes a Challenge frontier and nobody improves it for six months.

### Bad mechanism

Continue paying the incumbent because it remains leader.

### Result

**FAIL.** Carbon would reward possession of old performance rather than discovery.

### Decision

The incumbent receives no new frontier reward merely for remaining incumbent.

> **Frontier state is persistent; frontier reward is event-based.**

---

# 5. Gauntlet C — first admissible miner wins by default

### Case

A new Challenge launches with no incumbent. The first barely admissible submission becomes leader and receives reward.

### Result

**FAIL without a launch baseline.**

### Decision

Every reward-enabled Challenge starts from a registered `FrontierBaseline`.

The baseline may be:

- protocol-owned benchmark method;
- qualified reference construction strategy;
- previous compatible frontier after requalification;
- another prospectively registered baseline.

The first miner reward requires beating that baseline under the LeaderReplacementPolicy.

---

# 6. Gauntlet D — different hidden draws create fake leader changes

### Case

Incumbent score was measured on draw A; challenger score is measured later on draw B.

### Failure

A draw-specific fluctuation can be mistaken for frontier improvement.

### Result

**FAIL if stored scalar scores are compared directly.**

### Decision: frontier promotion exam

A contender may be screened on ordinary fresh evaluation, but final leader replacement must use a common prospective promotion exam:

```text
incumbent method
challenger method(s)
        ↓
same Challenge version
same Score Pack
same fresh hidden settlement case bundle
same registered reconstruction-repeat policy
        ↓
comparable ScoreResults
```

This is the economic analogue of a head-to-head scientific experiment.

---

# 7. Gauntlet E — arrival-order / validator-latency gaming

### Case

Incumbent = 0.80. During one window:

```text
A = 0.81
B = 0.83
C = 0.82
```

If rewards settle immediately, arrival order can determine who gets paid or multiple miners can be paid for transient records.

### Result

**FAIL for immediate chronological settlement.**

### Decision

Use **batch frontier settlement**:

1. accept submissions until cutoff;
2. resolve required retries/infra states;
3. select eligible contenders;
4. run one common frontier promotion exam;
5. identify the strongest scientifically superior contender;
6. emit at most one payout event for that Challenge in that window.

Network latency is not scientific evidence.

---

# 8. Gauntlet F — floating-point micro-improvement

### Case

Incumbent = `0.8410`; challenger = `0.8414`; scientific uncertainty is far larger than the difference.

### Result

**FAIL for `new_score > old_score`.**

A new leader must satisfy the registered `LeaderReplacementPolicy`, which consumes Score Pack semantics and returns a state such as:

```text
SUPERIOR
NOT_SUPERIOR
INDETERMINATE
```

The exact criterion is Challenge-specific and may use:

- qualified minimum meaningful separation;
- repeat evidence;
- reconstruction-repeat evidence;
- equivalence/indeterminate bands;
- lower-bound comparison;
- another dossier-qualified rule.

> **A leader advance is an evidence state, not a floating-point comparison.**

Illustrative simulation: if an estimated challenger-minus-incumbent difference has standard deviation `0.01`, a truly equal challenger appears numerically better about 50% of the time. Requiring an illustrative `+0.02` superiority margin reduces that false crossing to about 2.3%. The value `0.02` is not proposed as a universal Carbon threshold; the example demonstrates why leader replacement must respect scientific resolution.

---

# 9. Gauntlet G — equivalent superior challengers

### Case

Two challengers are both superior to the incumbent but scientifically indistinguishable from each other.

### Failure

A deterministic hash/arrival tie-break pays one full scientific reward despite no scientific basis for preferring it.

### Decision

Do not manufacture a scientific winner from an unresolved equivalence.

Preferred v1 behavior:

- run the registered repeat/extension rule if available;
- if still `INDETERMINATE`, do not emit a frontier payout for that Challenge in the current window;
- preserve both contenders in the scientific record.

A future explicit co-winner policy may be reviewed, but is not required for v1.

---

# 10. Gauntlet H — same miner improves its own method

### Case

The current leader's miner develops a materially better strategy.

### Tension

If only a new hotkey may win, incumbents lose direct incentive to continue improving. If every same-miner micro-step earns a full slot, progress splitting becomes attractive.

### Decision

The scientific frontier is defined by **method/strategy identity**, not merely hotkey identity. A genuinely new method from the incumbent miner may establish a new frontier.

However, the gauntlet records a strategic limitation:

> **With a fixed reward per frontier event, an actor may benefit from withholding a larger latent improvement and releasing it in scientifically meaningful increments across periods.**

There is no reliable protocol test for an unobservable latent better method. v1 mitigations are:

- one payout maximum per Challenge per settlement window;
- scientifically meaningful LeaderReplacementPolicy, not epsilon improvements;
- no carry-forward jackpot;
- submission costs/collateral/deduplication in their own protocol layer;
- monitor repeated same-control frontier stepping empirically.

Do not pretend the mechanism can prove whether a miner withheld an unseen future method.

---

# 11. Gauntlet I — copy / duplicate / sybil frontier flipping

### Cases

- exact strategy resubmission;
- copied incumbent under a new hotkey;
- near-duplicate method benefiting from reconstruction noise;
- same controller rotating hotkeys.

### Decisions

1. exact strategy/artifact identity cannot create a new frontier event;
2. duplicate detection belongs before promotion settlement;
3. shared promotion exam + superiority criterion suppresses noise-only flips;
4. registration cost/collateral/identity policy remain separate sybil controls;
5. scientific reward cannot rely on hotkey novelty as evidence of method novelty.

---

# 12. Gauntlet J — reconstruction lottery

### Case

A stochastic training strategy produces one excellent artifact and many mediocre ones.

### Result

**FAIL if leader replacement uses the challenger's best reconstruction.**

### Decision

The promotion exam must use the Challenge's registered method-level reconstruction policy. If multiple independent reconstructions are required, incumbent and contender are assessed symmetrically.

The Leader record binds the method-level evidence, not a cherry-picked artifact.

---

# 13. Gauntlet K — no admissible contender

### Decision

No `FrontierAdvanceEvent` exists.

Do not reward:

- least-bad inadmissible miner;
- current incumbent merely for existing;
- failed-infrastructure submission;
- indeterminate contender.

The Challenge slot becomes `WITHHOLD` for that period at the abstract settlement layer.

---

# 14. Gauntlet L — only some of seven Challenges advance

### Intended semantics

Seven reward-enabled Challenges imply seven equal logical slots of `1/7`.

If only two Challenges have verified frontier events:

```text
Challenge A winner -> PAY(1/7)
Challenge B winner -> PAY(1/7)
other five          -> WITHHOLD(5/7 total)
```

Do **not** reinterpret this as `1/2 + 1/2` merely because only two miners are payable.

### Simulation

Using illustrative per-period frontier-event probabilities:

```text
[0.50, 0.40, 0.30, 0.20, 0.10, 0.05, 0.02]
```

there are only about `1.57` frontier events per seven-Challenge period on average. The intended equal-slot policy would therefore pay about `1.57 / 7 ≈ 22.4%` of the miner reward budget on average in this illustrative state.

If the surviving positive miner weights are simply normalized to one, the same periods instead distribute essentially the full available miner incentive whenever any event occurs. That materially changes the mechanism from "equal Challenge slots" into "split all emissions among whichever Challenges happened to advance."

**This is a stop-ship chain-adapter issue.**

---

# 15. Gauntlet M — current Bittensor normalization

Current Bittensor documentation states that validator surviving weight rows are normalized, and normalized miner ranks become miner incentive. Therefore Carbon cannot assume that placing zero weight on inactive Challenge winners preserves an unused Challenge fraction.

Relevant current docs:

- https://www.bittensor.com/docs/concepts/emissions
- https://www.bittensor.com/docs/internals/consensus

Current Bittensor also withholds miner incentive directed to subnet-owner-associated hotkeys, burning or recycling it according to subnet settings:

- https://www.bittensor.com/docs/guides/mining

However, `MinerBurned` also affects the subnet's future cross-subnet emission share under current runtime economics:

- https://www.bittensor.com/docs/concepts/emissions

### Decision

Define the scientific/economic settlement abstractly first:

```text
SettlementObligation = PAY(uid, slot_fraction) | WITHHOLD(slot_fraction)
```

Then require a separate `BittensorSettlementAdapter` to prove on testnet how those obligations map onto legal chain weights without:

- redistributing inactive Challenge slots to active winners;
- paying non-winners dust;
- accidentally changing Carbon's future subnet emission share beyond intended policy;
- violating `min_allowed_weights`, max-weight, commit-reveal, or rate-limit constraints.

No owner-hotkey sink implementation is ratified by this gauntlet.

---

# 16. Gauntlet N — minimum weight-count constraints

Current Bittensor can require a minimum number of nonzero weight destinations. Zero entries are dropped and do not satisfy the minimum.

Reference:

- https://www.bittensor.com/docs/hyperparameters/min-allowed-weights

### Risk

A scientific mechanism with only one or two payable frontier winners in a window may be incompatible with the chain's configured minimum weight count unless the adapter has approved non-paying sinks or the subnet hyperparameter is configured accordingly.

### Decision

`min_allowed_weights` is a deployment constraint on the Bittensor adapter, not a reason to add miner participation dust to Carbon's scientific reward policy.

---

# 17. Gauntlet O — challenge count changes mid-period

### Case

A fifth Challenge becomes qualified halfway through a four-Challenge settlement window.

### Failure

Immediate inclusion changes every existing Challenge's economic slot after miners have already acted.

### Decision

Freeze the reward-enabled Challenge set at settlement-window open.

Challenge activation, retirement, or reward suspension takes effect at the next window boundary.

```text
ChallengeSetEpoch {
  ids
  versions
  N
  slot_fraction = 1/N
}
```

---

# 18. Gauntlet P — Challenge scientific defect after a leader exists

### Case

Generator, measurement, or truth defect is discovered.

### Decision

Freeze reward settlement for that Challenge.

Do not continue comparing challengers against an invalid frontier. Repair via prospective scientific versioning/requalification. A new Challenge/exam version establishes a new compatible `FrontierBaseline` or explicitly requalifies the old frontier.

Historical payments remain historical economic events unless a separately ratified fraud/enforcement policy says otherwise; scientific evidence is never silently rewritten.

---

# 19. Gauntlet Q — Challenge version / Score Pack change

Material scientific changes terminate direct frontier comparability.

A new:

- target population;
- SamplingPlan;
- measurement;
- mandatory threshold;
- Score Pack;
- reconstruction policy;

may require a new frontier lineage.

A stored old score is not compared numerically with a score from the new exam.

---

# 20. Gauntlet R — cheap vs expensive Challenges

### Case

Equal slots exist but Challenge A costs miners 10x more compute than Challenge B.

### Result

Equal nominal reward does not guarantee equal expected miner effort.

### Decision

Keep equal **base protocol Challenge slots** because breadth is the deliberate design objective. Do not contaminate scientific score with compute-cost compensation.

For later expensive industrial or high-fidelity Challenges, additive sponsor/program bounties may supplement the equal base under a separately visible funding layer.

P0 should not activate seven weak Challenges simply to hit the target count. The reward set contains only qualified Challenges; start with fewer if necessary and grow toward the intended 4–7 breadth.

---

# 21. Gauntlet S — one miner advances several Challenges

### Decision

A miner may legitimately receive several Challenge slots in one period if it independently establishes several verified frontiers.

Breadth is Challenge-based, not identity-quota based.

Anti-concentration policy should not erase real multi-domain scientific progress.

---

# 22. Gauntlet T — score leakage and settlement sniping

### Risk

If incumbent/contender promotion scores are revealed continuously, miners can time submissions around known frontier gaps or copy promising strategies.

### Decision

Keep the rich promotion exam private until the appropriate settlement/disclosure boundary. Strategy submission identity, cutoff, and evaluation-information budget remain protocol-controlled.

Bittensor commit-reveal protects validator weight copying, but does not replace Carbon's scientific submission/evaluation secrecy.

---

# 23. Gauntlet U — validator disagreement

### Required property

Validators should agree on whether the same contender produced a `FrontierAdvanceEvent`.

### Decision

Promotion settlement should bind deterministic shared scientific identity where possible:

```text
ChallengeSetEpoch
Challenge version
Score Pack version
LeaderReplacementPolicy version
incumbent identity
contender identities
shared fresh exam seed commitment
registered reconstruction seeds
```

The result becomes a content-addressable `FrontierAdvanceReceipt` / event record.

Yuma consensus is the economic consensus layer; it should not be asked to resolve avoidable scientific nondeterminism.

---

# 24. Required objects after the gauntlet

## `FrontierRecord`

```text
challenge_identity
frontier_method_identity
frontier_owner/hotkey provenance
qualified ScoreResult / evidence refs
LeaderReplacementPolicy version
promotion exam identity
established_at
```

## `LeaderReplacementPolicy`

```text
eligible ScoreResult states
superiority semantics
repeat / extension semantics
reconstruction policy ref
stratum/non-regression semantics inherited from Score Pack
indeterminate handling
```

## `FrontierAdvanceEvent`

```text
challenge identity
prior FrontierRecord
new FrontierRecord
promotion exam identity
scientific superiority decision
event period
```

## `ChallengeSetEpoch`

```text
reward-enabled Challenge identities
N
slot_fraction = 1/N
window open/close
```

## `SettlementObligation`

```text
PAY(uid, slot_fraction)
WITHHOLD(slot_fraction)
```

## `BittensorSettlementAdapter`

Implementation-only adapter that maps settlement obligations to chain-valid weight behavior without redefining scientific/economic semantics.

---

# 25. Full intended loop after gauntlet

```text
QUALIFIED CHALLENGE SET
  4–7 desired; only qualified reward-enabled Challenges count
        ↓
ChallengeSetEpoch freezes N and equal slot 1/N
        ↓
miners submit construction strategies
        ↓
validator-controlled independent reconstruction
        ↓
protected qualified Challenge exam
        ↓
Score Pack
  eligibility → admissibility → rank evidence
        ↓
screen promotion candidates
        ↓
COMMON FRONTIER PROMOTION EXAM
  incumbent + contenders on same fresh evidence identity
        ↓
LeaderReplacementPolicy
        ↓
SUPERIOR?
  no / indeterminate → no event
  yes              → FrontierAdvanceEvent
        ↓
period settlement
  event Challenge   → PAY(1/N)
  no-event Challenge→ WITHHOLD(1/N)
        ↓
BittensorSettlementAdapter
        ↓
validator weights / Yuma consensus
```

---

# 26. Final conclusion

The frontier-event mechanism is coherent and unusually well aligned with Carbon's scientific purpose. It rewards **verified advances to the research frontier** while equal Challenge slots structurally preserve breadth.

The remaining blocker is not scientific architecture. It is the exact Bittensor settlement implementation required to preserve `PAY(1/N)` / `WITHHOLD(1/N)` semantics under normalized on-chain weights and current burn/recycle rules.

> **Do not weaken the scientific mechanism merely to fit a convenient weight vector. Build and test an explicit chain adapter.**
