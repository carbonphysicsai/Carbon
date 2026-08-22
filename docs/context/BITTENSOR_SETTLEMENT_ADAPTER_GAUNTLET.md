# Bittensor Settlement Adapter Gauntlet — Frontier-Only Challenge Rewards

**Status:** executed design simulation against current Bittensor/Yuma semantics; no production adapter ratified.  
**Branch:** `design/symbolic-numeric-integration`  
**Purpose:** Test whether Carbon's frontier-only, equal-Challenge-slot incentive doctrine can be transmitted faithfully through current Bittensor weight normalization and emission mechanics.

---

# 1. Carbon economic intent being tested

For a frozen ChallengeSetEpoch with `N` reward-enabled Challenges:

```text
logical slot per Challenge = 1 / N
```

A Challenge pays its slot only when that settlement window produces a scientifically verified `FrontierAdvanceEvent`.

Therefore, with seven Challenges and `k` verified frontier advances:

```text
k winners each receive logical 1/7
(7-k)/7 is WITHHELD
```

Unused slots are not redistributed to the active winning Challenges. The purpose is to preserve breadth and reward scientific progress rather than incumbency.

---

# 2. Current Bittensor facts that constrain the adapter

The current chain behavior relevant to this design is:

1. validators submit relative weight vectors; surviving rows are normalized;
2. normalized miner ranks become miner incentive;
3. zero-valued entries do not satisfy `min_allowed_weights`;
4. `max_weights_limit` caps individual normalized non-self weights;
5. miner incentive directed to subnet-owner-associated hotkeys is withheld rather than paid to miners;
6. the resulting `MinerBurned` fraction is used in **future cross-subnet emission allocation** through a factor proportional to `1 - MinerBurned`;
7. choosing recycle instead of burn does not avoid the `MinerBurned` adjustment;
8. current Bittensor supports at most two scoring mechanisms per subnet, not enough to map one mechanism per 4–7 Carbon Challenges.

These constraints mean Carbon cannot assume that `weight=0` for inactive Challenge slots preserves unused economic capacity.

---

# 3. Simulation A — naive zeroing fails the equal-slot doctrine

Suppose `N=7` and only two Challenges produce frontier events.

Carbon intends:

```text
winner_A = 1/7
winner_B = 1/7
withheld  = 5/7
```

If validators submit only the two winning miners with equal positive raw weights and omit all inactive slots, row normalization converts the vector into:

```text
winner_A = 1/2
winner_B = 1/2
```

Therefore naive zeroing **redistributes** the five inactive Challenge slots to the active winners.

### Result

**FAIL.**

A separate on-chain destination or accounting mechanism is required for unused logical slots.

---

# 4. Simulation B — owner-associated sink reproduces current-period slot arithmetic

An obvious adapter is to map unused logical slots to one or more subnet-owner-associated sink hotkeys.

For seven Challenges:

| New frontier events `k` | Each winner | Sink share | Total miner payout intended |
|---:|---:|---:|---:|
| 0 | — | 1.0000 | 0.0000 |
| 1 | 0.1429 | 0.8571 | 0.1429 |
| 2 | 0.1429 | 0.7143 | 0.2857 |
| 3 | 0.1429 | 0.5714 | 0.4286 |
| 4 | 0.1429 | 0.4286 | 0.5714 |
| 5 | 0.1429 | 0.2857 | 0.7143 |
| 6 | 0.1429 | 0.1429 | 0.8571 |
| 7 | 0.1429 | 0.0000 | 1.0000 |

If consensus validators use the same normalized vector and the sink share is directed to owner-associated hotkeys, the current-period **paid miner incentive** can in principle match Carbon's logical slots: the sink portion is withheld rather than paid to ordinary miners.

### Result

**LOCAL CURRENT-PERIOD ARITHMETIC PASS — but system-level FAIL.**

The reason is `MinerBurned`.

---

# 5. Simulation C — MinerBurned creates a future subnet-emission penalty

Current Bittensor cross-subnet allocation scales each subnet's demand share by:

```text
1 - MinerBurned
```

before cross-subnet renormalization.

Under the owner-sink implementation:

```text
MinerBurned = withheld logical Challenge share = (N-k)/N
```

For `N=7`, this means:

| `k` frontier events | `MinerBurned` | Multiplicative pre-normalization factor |
|---:|---:|---:|
| 0 | 1.0000 | 0.0000 |
| 1 | 0.8571 | 0.1429 |
| 2 | 0.7143 | 0.2857 |
| 3 | 0.5714 | 0.4286 |
| 4 | 0.4286 | 0.5714 |
| 5 | 0.2857 | 0.7143 |
| 6 | 0.1429 | 0.8571 |
| 7 | 0.0000 | 1.0000 |

In a simple 128-subnet equal-demand reference simulation, Carbon's resulting next cross-subnet share relative to an otherwise identical zero-burn subnet is approximately:

| `k` | Relative next-share |
|---:|---:|
| 0 | 0.000 |
| 1 | 0.144 |
| 2 | 0.287 |
| 3 | 0.430 |
| 4 | 0.573 |
| 5 | 0.716 |
| 6 | 0.858 |
| 7 | 1.000 |

The exact network-wide value depends on every subnet's demand and burn state, but the direction is structural.

### Monte Carlo frontier-rate example

Using the earlier illustrative seven-Challenge frontier rate of ~1.57 successful Challenge advances per settlement period:

```text
mean paid logical miner fraction ≈ 0.224
mean withheld / MinerBurned      ≈ 0.776
```

Under the equal-demand reference model, the next cross-subnet emission share is only about **22.6%** of an equivalent zero-burn subnet.

### Result

**FAIL as a production default.**

Using owner-associated sinks would implement Carbon's local withholding intent by imposing a potentially severe endogenous penalty on Carbon's future subnet emission share.

`RecycleOrBurn` does not solve this because current cross-subnet allocation uses the withheld `MinerBurned` proportion regardless of whether the tokens are recycled or burned.

---

# 6. Simulation D — zero-frontier period is especially pathological

Carbon explicitly permits a settlement period with:

```text
0 FrontierAdvanceEvents
```

Scientifically this is a normal result: no one advanced the frontier.

Strict owner-sink mapping would produce:

```text
MinerBurned = 1.0
```

which makes Carbon's burn-adjusted demand contribution zero for the next cross-subnet allocation step, subject to runtime-wide fallback semantics.

### Result

**STOP-SHIP for the owner-sink production design.**

A scientifically valid period with no progress must not mechanically starve the subnet merely because Carbon refuses to invent a winner.

---

# 7. Simulation E — `max_weights_limit` and sparse frontier vectors

Even before the `MinerBurned` problem, strict sink transmission has a weight-vector shape problem.

For `N=7`, one new winner requires:

```text
winner = 1/7 ≈ 0.143
sink   = 6/7 ≈ 0.857
```

A non-owner validator cannot generally place 0.857 on one ordinary destination if the subnet's `max_weights_limit` is materially lower.

The sink share can be split across multiple owner-associated sink UIDs. Required sink count is approximately:

```text
ceil(sink_share / max_weights_limit)
```

Illustrative counts:

### If `max_weights_limit = 0.30`

- zero frontier events: 4 sink UIDs;
- one event: 3 sink UIDs;
- two events: 3 sink UIDs.

### If `max_weights_limit = 0.20`

- zero events: 5 sink UIDs;
- one event: 5 sink UIDs;
- two events: 4 sink UIDs.

### If `max_weights_limit = 0.10`

- zero events: 10 sink UIDs;
- one event: 9 sink UIDs;
- two events: 8 sink UIDs.

Bittensor currently allows the subnet owner to raise the number of owner-immune hotkeys up to a bounded limit, but this would create operational complexity and still does not repair the `MinerBurned` economic penalty.

### Result

**Technically manageable in some configurations, strategically unattractive.**

---

# 8. Simulation F — `min_allowed_weights`

Carbon's frontier vectors are deliberately sparse. A period might contain only:

```text
1 winner + sink destinations
```

Zero weights do not count toward `min_allowed_weights`. The subnet owner can set `min_allowed_weights`, so Carbon should choose a value compatible with its sparse frontier settlement design rather than invent participation dust.

### Result

**PASS with configuration discipline.**

Constitutional rule retained:

> Chain vector-length requirements must not create fake scientific rewards.

---

# 9. Simulation G — stale weights / no-update is not withholding

Another candidate is simply not submitting new weights when no frontier advance occurs.

This fails because previously submitted weights can remain active until chain staleness rules remove them. Old frontier winners may continue receiving incentive despite no new frontier event.

### Result

**FAIL.**

Carbon needs an explicit settlement action every economic period, not silence interpreted as scientific withholding.

---

# 10. Simulation H — current leader as filler fails doctrine

Assigning unused slots to Challenge incumbents avoids burn and normalization problems.

But it converts:

```text
reward frontier advancement
```

into:

```text
pay historical incumbency
```

which is the mechanism Carbon intentionally rejected.

### Result

**FAIL by economic doctrine.**

---

# 11. Simulation I — proportional redistribution among frontier winners fails breadth

If only `k` Challenges advance and validator rows contain only those `k` winners, each receives approximately `1/k` of miner incentive.

This means a single advance during a seven-Challenge period receives 100% rather than 1/7.

This creates strong coupling between unrelated Challenges and rewards inactivity elsewhere.

### Result

**FAIL.**

---

# 12. Simulation J — two Bittensor mechanisms do not solve seven Challenge slots

Current Bittensor allows at most two scoring mechanisms per subnet. Carbon's intended Phase-0 portfolio is 4–7 simultaneous Challenges, originally seven PDEs.

One mechanism per Challenge is therefore not currently available, and each mechanism still runs its own normalized Yuma allocation.

### Result

**FAIL as a general solution.**

Multiple mechanisms may still be useful for future coarse economic separation, but they do not directly implement Carbon's seven fixed Challenge slots.

---

# 13. Candidate adapter K — non-owner protocol escrow / reserve destination

A theoretical workaround is to send unused Challenge slots to one or more **non-owner** protocol-controlled reserve UIDs so the chain counts the emission as ordinary miner incentive rather than `MinerBurned`.

This would preserve Carbon's cross-subnet demand share better than owner sinks, but it changes the trust and accounting model:

- the unused emission has not truly been withheld by the chain;
- somebody or something controls the reserve assets;
- custody, transfer, stake, tax/accounting, loss, compromise, and governance become material;
- redistributing the reserve later may accidentally implement carry-forward, which Carbon rejected for the base mechanism;
- if the reserve is made deliberately inaccessible, the proof of inaccessibility and registration lifecycle become their own security system.

### Result

**POSSIBLE RESEARCH PATH, NOT RATIFIED.**

A protocol escrow must not be adopted merely to hide a chain-accounting mismatch.

---

# 14. Candidate adapter L — explicit off-chain settlement layer

Another architecture is:

```text
Bittensor incentive → protocol settlement account
Carbon FrontierAdvanceEvents → deterministic payout ledger
ledger → actual miner payments
```

This can express exact `1/N` and exact withholding semantics, but it weakens the desirable property that Bittensor itself directly pays the scientific winner and introduces custody/settlement infrastructure.

### Result

**EXPRESSIVE BUT ARCHITECTURALLY COSTLY.**

Use only if no trust-minimized native adapter exists.

---

# 15. Yuma consensus simulation conclusion

If honest validators submit the **same valid weight vector**, Yuma's consensus/clipping does not fundamentally break Carbon's within-period relative winner allocation. The primary incompatibility is earlier/later in the chain:

```text
Carbon wants absolute logical capacity to remain unused
        ↓
Bittensor weight rows are relative and normalized
        ↓
owner sinks can represent unused capacity locally
        ↓
MinerBurned then affects future subnet-level emissions
```

Thus the unresolved problem is not ordinary Yuma rank consensus; it is faithful representation of **unused economic capacity**.

---

# 16. Settlement cadence constraint

Current Bittensor weight updates are rate-limited (default documented value 100 blocks). Carbon settlement periods must therefore be coordinated with:

- `weights_rate_limit`;
- subnet `tempo`;
- commit-reveal timing if enabled;
- ChallengeSetEpoch boundaries.

A frontier settlement period shorter than the chain's ability to accept fresh weight state is invalid architecture.

Recommended invariant:

> **One scientific settlement must map to one chain-valid weight state before the corresponding economic epoch settles.**

Exact cadence is deployment/configuration-specific.

---

# 17. Full-loop verdict

The scientific/economic Carbon loop itself survives:

```text
qualified Challenge
→ ScoreResult
→ common frontier promotion exam
→ FrontierAdvanceEvent
→ fixed 1/N logical Challenge slot
```

The unresolved seam is specifically:

```text
logical PAY / WITHHOLD instructions
        ↓
current Bittensor normalized weight + MinerBurned mechanics
```

### Final classification

- **Per-Challenge scientific frontier loop:** PASS.
- **Equal logical Challenge allocation:** PASS as Carbon accounting doctrine.
- **Naive zero-weight chain adapter:** FAIL.
- **Owner-burn-sink adapter:** FAIL for production because withholding feeds back into cross-subnet emission share.
- **No-update adapter:** FAIL.
- **Incumbent filler:** FAIL.
- **Redistribute-to-current-winners adapter:** FAIL.
- **Two-mechanism mapping:** FAIL for 4–7 Challenge generality.
- **Protocol reserve / escrow:** RESEARCH REQUIRED.

---

# 18. Required next experiment

Before final IM lock, run a localnet/testnet `BittensorSettlementAdapter` experiment that records actual chain outcomes for at least:

```text
7 Challenges / 0 frontier events
7 Challenges / 1 frontier event
7 Challenges / 2 frontier events
7 Challenges / 7 frontier events
```

and measures:

- submitted vs stored normalized weights;
- consensus miner incentive;
- owner-associated withheld incentive;
- `MinerBurned`;
- next-epoch subnet emission-share effect;
- max-weight/min-weight acceptance;
- stale-weight behavior;
- validator agreement under multiple validators;
- burn vs recycle mode;
- any candidate reserve/escrow design.

The production adapter must demonstrate that chain economics preserve Carbon's intended frontier doctrine without a hidden cross-subnet penalty or fictitious miner reward.

---

# 19. Final statement

> **Carbon's frontier incentive mechanism is coherent, but current Bittensor weight normalization does not provide a free notion of an unused Challenge slot. Owner-associated withholding reproduces the local payout arithmetic while feeding back into future subnet emissions through MinerBurned. The last IM problem is therefore a concrete settlement-adapter problem, not a scientific-scoring problem.**
