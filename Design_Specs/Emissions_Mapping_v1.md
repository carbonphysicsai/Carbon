# Carbon Emissions Mapping v1

**Status:** OWNER-RECOMMENDED v1 for tech/economic/protocol review.  
**Scope:** downstream mapping from a Challenge-bound scientific `ScoreResult` to validator weight signal.  
**Does not redefine:** scientific score, Challenge validity, product qualification, cross-Challenge scientific comparability, or Bittensor consensus semantics.

---

# 1. Core separation

```text
qualified Challenge
      ↓
Score Pack / ScoreEngine
      ↓
scientific ScoreResult
      ↓
EMISSIONS MAPPING
      ↓
validator weight signal
      ↓
Bittensor economic consensus
```

> **Economic mapping may allocate rewards from scientific evidence; it may not rewrite what that evidence means.**

---

# 2. Eligible result states

Only candidates with the exact scientific result state:

```text
VALID_RANKED
```

are eligible for positive scientific weight signal under the default path.

Distinct non-positive states remain distinct in the scientific record:

```text
REJECTED_INVALID
FAILED_INFRA
SCIENTIFIC_INADMISSIBLE
INDETERMINATE_EVIDENCE
```

`FAILED_INFRA` may trigger retry/operational policy rather than scientific penalty. The economic layer must not silently relabel it as scientific failure.

---

# 3. No-admissible-candidate state

If no candidate is `VALID_RANKED`, the scientific layer emits:

```text
NO_ADMISSIBLE_SCIENTIFIC_SIGNAL
```

It does **not** nominate the least-bad inadmissible candidate as a winner.

The chain/runtime owner must define the safe Bittensor behavior for this state (for example no new scientific signal, retry, or another protocol-safe fallback) without altering the underlying scientific result.

---

# 4. Initial P0 transform

For one Challenge and one validator evaluation set, let eligible scientific scores be:

```text
s_i >= 0
```

Owner-recommended initial mapping:

```text
w_i = s_i / sum_j s_j
```

for `VALID_RANKED` candidates when the denominator is positive.

All ineligible candidates receive zero scientific signal in this mapping.

### Why proportional first

- monotone;
- transparent;
- does not create new rank inversions;
- does not magnify tiny score differences aggressively;
- easy to audit;
- allows stronger concentration to be introduced later only if evidence supports it.

---

# 5. Concentration doctrine

> **Economic reward concentration should be no sharper than the scientific resolution the registered evaluation can defend.**

A high-temperature softmax, winner-take-all rule, or strong nonlinear exponent can transform scientifically modest or uncertain differences into economically dominant advantages.

The initial Carbon subnet should therefore avoid aggressive concentration until repeated evaluation/reconstruction data demonstrates stable scientific separation.

---

# 6. Pilot calibration

A controlled Burgers candidate set produced approximate scientific scores:

```text
truth      1.0000
noise2     0.9731
smooth     0.9596
atten90    0.8959
shift      0.7829
```

Representative reward concentration was:

```text
proportional:
  21.7 / 21.1 / 20.8 / 19.4 / 17.0 %

power-2:
  23.3 / 22.1 / 21.5 / 18.7 / 14.3 %

softmax(T=10):
  34.5 / 26.4 / 23.0 / 12.2 / 3.9 %
```

The softmax supplied substantially more economic separation than the scientific score itself.

### v1 decision

Use proportional mapping first. Treat any nonlinear sharpening as a separately versioned economic policy requiring evidence.

---

# 7. Future mild concentration

If P0 data later shows that proportional mapping creates insufficient selection pressure while rank is demonstrably stable, Carbon may test a bounded power family:

```text
w_i ∝ s_i^gamma
```

with `gamma > 1`.

`gamma` is an economic parameter, not a scientific constant. It must be:

- versioned;
- disclosed at the appropriate protocol level;
- evaluated for concentration and strategic effects;
- changed prospectively.

No default `gamma > 1` is ratified by this document.

---

# 8. Scientific indistinguishability

The Score Pack architecture permits Challenge-specific uncertainty/equivalence semantics.

If candidates are scientifically `INDETERMINATE_EVIDENCE` rather than `VALID_RANKED`, economic mapping should not manufacture a scientifically meaningful ordering between them.

If a future Challenge emits qualified equivalence tiers, the emissions policy should preserve those semantics rather than applying an arbitrary winner bonus within a tier.

---

# 9. Reconstruction variability

Where the scientific unit is a **construction method**, not one lucky artifact, ScoreResult should already incorporate the registered reconstruction-repeat policy before emissions mapping.

The emissions layer must not choose the best reconstruction post hoc.

---

# 10. Cross-Challenge allocation

Raw scientific scores are not automatically comparable across Challenges.

Therefore:

```text
within-Challenge candidate mapping
!=
cross-Challenge emissions allocation
```

Any later mechanism deciding how total subnet emissions are split between Burgers, CFD, multiphysics, or partner Challenges is a separate governance/economic system.

It must not assume that `0.9` on two different Score Packs is the same unit of scientific value.

---

# 11. Anti-gaming requirements

The mapping must be checked for:

- submission-frequency gaming;
- duplicate-strategy flooding;
- sybil/copy strategies;
- score clipping/floor exploitation;
- threshold-edge concentration;
- winner-bonus discontinuities;
- cross-round carry/decay effects;
- no-admissible rounds;
- very small eligible populations;
- one dominant candidate;
- many near-equivalent candidates.

Submission fees, identity policy, deduplication, decay, and Bittensor-specific weight mechanics remain separate protocol owners.

---

# 12. Versioning

A material emissions change requires a new economic mapping version, including:

- transform family;
- exponent/temperature;
- caps/floors;
- tie/equivalence treatment;
- round aggregation;
- decay/history semantics;
- challenge allocation semantics.

Historical `ScoreResult` remains unchanged.

---

# 13. v1 invariants

1. **Only qualified scientific results create default positive scientific weight signal.**
2. **No admissible candidate means no scientific winner.**
3. **Economic mapping never repairs or reinterprets scientific evidence.**
4. **Initial mapping is proportional within one Challenge.**
5. **Nonlinear concentration requires prospective evidence and versioning.**
6. **Economic concentration should not exceed defensible scientific resolution.**
7. **Cross-Challenge allocation is separate.**
8. **Scientific record survives unchanged beneath economic weights.**

---

# 14. Final v1 statement

> **Carbon should begin by transmitting scientific score differences to the market conservatively, then increase economic selection pressure only after the judge has demonstrated stable resolution under real miner adaptation.**
