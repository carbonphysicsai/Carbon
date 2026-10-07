# Motor quiz power on the public stand-in (registry-v1, commit ed095dd7)

This is public data only: 180 TRAIN and PRACTICE references, and study V2's 8 × 6 grid. There was no new solve and no hidden material. Results are in `result-v1.json`.

**Setup.**
- **Known-bad** (by behaviour): boundary optimist, localized sign error, infeasible edge-seeker.
- **Known-good:** oracle plus 9 noisy oracles. These are a stand-in construction, because motor has only two real models.

## Q2 (near-limit cases)

- **The near band is rare.** Only **33 of 180** public cases (18 %) lie within the recommended 10 % band of a limit, and 25 of them are infeasible.
- **Per batch** (a batch is half the pool): n = 12 gives **AUC 0.84 mean / 0.70 p05**. n = 24 is not reachable, because a half-pool batch holds about 16 near cases.
- **Pooled over batches** (the cross-rotation proxy, drawn from the whole near set): **0.84 / 0.70 at n 12, 0.84 / 0.72 at n 24, 0.85 / 0.78 at n 32.** Power saturates near 0.85 mean. The localized-sign-error control acts only in the torque band, while most near-limit infeasible cases are ripple-limited. **No size reaches battery's 0.9 bar on this pool.**

## Q3 (decision tasks)

**No power on the stand-in** (AUC 0.50 at every k).
- None of V2's 8 designs sits near a limit, so the known-bad controls decide exactly like the oracle.
- Random-geometry Q3 scenarios will rarely be near-limit. Q3 needs **near-limit-targeted** candidate geometries, which need screening solves first: a cost the owner must weigh.

## Producer wall time on the AX42

16 threads; GetDP at 2 CPUs, so 8 concurrent; median 1,366 s per case.

| Option per batch | Solves | Wall time |
|---|---|---|
| A: Q2 n = 24 (pool of about 133 at the 18 % near share) + Q3 k = 2 | 229 | **about 10.9 h** |
| B: Q2 n = 12 (pool of about 67), pooled over W = 4 batches, + Q3 k = 2 | 163 | **about 7.7 h** |
| C: B without Q3, until near-limit-targeted scenarios exist | 67 | **about 3.2 h** |

## Cross-rotation pooling (registered option)

**The rule.** A hotkey's verdict pools its quiz outcomes over its last **W** batches (HUMAN_INPUT, recommended 4), for the same construction identity only. A new submission starts a new pool.

**Costs.**
- **Freshness.** The verdict reflects up to W rotations. A changed construction is not pooled with its predecessor.
- **Exposure.** It reveals nothing new per batch (aggregates only). But a leaked quiz case would affect up to W verdicts, so the case-level secrecy that hidden batches already require now matters across W rotations.

## Reading

- Motor's quiz is weaker than battery's on public data.
- Q2 tops out around 0.85 mean AUC.
- Q3 needs a targeted scenario generator before it can test anything.
- The near band itself is HUMAN_INPUT (10 % recommended). A refinement-repeatability study should replace it with a measured band.
