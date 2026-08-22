# Review These Preliminary Decisions — Frontier Leader Settlement

**Branch:** `design/symbolic-numeric-integration`  
**Status:** owner preliminary decisions after full frontier-settlement gauntlet.  
**Purpose:** Give tech/economic/protocol leads a v1 design to accept, modify, or reject rather than requiring a fresh mechanism design.

---

# Executive recommendation

> **Use equal logical Challenge slots and pay only scientifically verified frontier advances. Settle each Challenge in batches against a common promotion exam. Do not pay incumbency, do not redistribute no-event slots at Carbon's abstract policy layer, and do not let Bittensor normalization silently change the intended mechanism.**

Review model:

```text
F1 ACCEPT / MODIFY / REJECT
...
F16 ACCEPT / MODIFY / REJECT
```

---

# F1 — Frontier advance is the reward primitive

### Preliminary decision: ACCEPT

Miner reward is triggered by a verified new Challenge frontier, not participation or incumbent status.

Confidence: **Very high**.

---

# F2 — Equal base slot per reward-enabled Challenge

### Preliminary decision: ACCEPT

For `N` qualified LIVE reward-enabled Challenges, each gets logical base slot `1/N` for the settlement window.

Confidence: **Very high**.

---

# F3 — Freeze Challenge set per settlement window

### Preliminary decision: ACCEPT

Activation, retirement, suspension, or reward enablement changes apply prospectively at window boundaries.

Confidence: **Very high**.

---

# F4 — Every Challenge launches from a FrontierBaseline

### Preliminary decision: ACCEPT

The first miner must beat a registered qualified baseline. First admissible participation is not automatically a paid frontier advance.

Confidence: **Very high**.

---

# F5 — Stored scores from different draws cannot replace a leader

### Preliminary decision: ACCEPT

Final promotion compares incumbent and contenders on a common fresh hidden promotion exam under the same Challenge/Score Pack/reconstruction policy.

Confidence: **Very high**.

---

# F6 — Batch settlement, one paid event maximum

### Preliminary decision: ACCEPT

Settle contenders together after cutoff. At most one paid frontier event per Challenge per settlement window.

Confidence: **Very high**.

---

# F7 — Leader replacement is a scientific superiority state

### Preliminary decision: ACCEPT

Use `SUPERIOR / NOT_SUPERIOR / INDETERMINATE` or equivalent qualified semantics. Do not define leader replacement as raw `score_new > score_old`.

Confidence: **Very high**.

---

# F8 — Indeterminate top contenders do not receive arbitrary scientific winner reward

### Preliminary decision: ACCEPT FOR v1

Run registered repeat/extension policy. If still scientifically unresolved, no paid frontier event for that Challenge in the current window.

Confidence: **High**.

---

# F9 — Same miner may advance its own frontier with a new method

### Preliminary decision: ACCEPT

Frontier identity is method/strategy based rather than only hotkey based. Exact duplicates cannot generate an event.

Known limitation: unobservable strategic withholding/progress splitting cannot be perfectly detected. Mitigate with one payout/window, meaningful superiority, no carry-forward jackpot, and protocol costs/monitoring.

Confidence: **High**.

---

# F10 — No-event Challenge slot is WITHHOLD, not incumbent pay

### Preliminary decision: ACCEPT

No frontier event means no miner in that Challenge earns its slot for that period.

Confidence: **Very high**.

---

# F11 — No carry-forward jackpot in v1

### Preliminary decision: ACCEPT

Unused slots expire for base protocol settlement. Future sponsor/frontier bounties may have separate accumulation rules.

Confidence: **High**.

---

# F12 — Do not redistribute no-event slots at Carbon policy layer

### Preliminary decision: ACCEPT

With seven Challenges and two events, abstract settlement is `2 × 1/7 PAY + 5 × 1/7 WITHHOLD`, not `1/2 + 1/2`.

Confidence: **Very high**.

---

# F13 — Add explicit BittensorSettlementAdapter

### Preliminary decision: ACCEPT / STOP-SHIP FOR DEPLOYMENT

Current Bittensor normalization means zeroing inactive destinations does not automatically preserve withheld fractions. Chain behavior must be tested to implement `PAY / WITHHOLD` semantics faithfully.

Potential owner-associated sink behavior is not ratified because current `MinerBurned` affects broader subnet emissions.

Confidence: **Very high** that an adapter is required; exact implementation unresolved.

---

# F14 — Do not add miner participation dust merely to satisfy chain minimum weight count

### Preliminary decision: ACCEPT

`min_allowed_weights` is a deployment/hyperparameter/adapter constraint. It must not silently alter the frontier-only scientific reward doctrine.

Confidence: **Very high**.

---

# F15 — Scientific defect freezes frontier settlement

### Preliminary decision: ACCEPT

A material generator/truth/measurement/leakage/scoring defect suspends Challenge frontier settlement until repaired/requalified. Material new exam versions may start a new frontier lineage.

Confidence: **Very high**.

---

# F16 — Equal base reward is Challenge breadth policy, not compute-cost normalization

### Preliminary decision: ACCEPT

Keep equal base protocol opportunity. Expensive later partner/industrial Challenges may receive additive sponsor bounties under a separate visible mechanism.

Confidence: **High**.

---

# Consolidated table

| ID | Decision | Preliminary verdict | Confidence |
|---|---|---|---:|
| F1 | frontier advance reward primitive | ACCEPT | Very high |
| F2 | equal `1/N` Challenge slots | ACCEPT | Very high |
| F3 | freeze Challenge set per window | ACCEPT | Very high |
| F4 | launch baseline required | ACCEPT | Very high |
| F5 | common promotion exam | ACCEPT | Very high |
| F6 | batch settlement / one event max | ACCEPT | Very high |
| F7 | qualified superiority state | ACCEPT | Very high |
| F8 | unresolved tie -> no arbitrary payout | ACCEPT v1 | High |
| F9 | same miner can advance with new method | ACCEPT | High |
| F10 | no event -> WITHHOLD | ACCEPT | Very high |
| F11 | no carry-forward base jackpot | ACCEPT | High |
| F12 | no policy-layer redistribution | ACCEPT | Very high |
| F13 | explicit Bittensor adapter | ACCEPT / STOP-SHIP | Very high |
| F14 | no participation dust workaround | ACCEPT | Very high |
| F15 | defect freezes settlement | ACCEPT | Very high |
| F16 | equal base != cost normalization | ACCEPT | High |

---

# Remaining implementation questions, not architecture questions

1. settlement-window duration and alignment to Bittensor tempo / commit-reveal;
2. exact LeaderReplacementPolicy for each Challenge after rank-stability calibration;
3. exact FrontierBaseline for each Challenge;
4. exact duplicate/lineage policy;
5. exact Bittensor `WITHHOLD` implementation;
6. required `min_allowed_weights` setting / chain-valid sink topology if any;
7. testnet effect of miner withholding on `MinerBurned`, subnet emission share, validator bonds/dividends, and pruning;
8. emergency freeze timing relative to settlement cutoff.

---

# Owner conclusion

> **The full scientific incentive loop is now architecturally closed through Challenge-local frontier settlement. The final subnet deployment blocker is proving that the Bittensor adapter can faithfully transmit equal-slot `PAY / WITHHOLD` obligations without silently redistributing rewards or altering the scientific policy.**
