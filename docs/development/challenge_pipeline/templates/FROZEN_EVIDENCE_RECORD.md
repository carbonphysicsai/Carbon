# Frozen evidence record: <family id> <challenge name> v<version>

**Template, DRAFT until protocol lock.** Sources: Challenge Roadmap §02
Stage 3 and §03; `Design_Specs/Challenge_Admission.md` §2 and §5.
- The record covers one frozen run, and only this run feeds the leaderboard.
- A change after freeze makes a new challenge version and a new record.
  Earlier records keep their meaning.

## 1. What was pinned at freeze

| Pin | Identity |
| --- | --- |
| Suite version | |
| Harness code | commit |
| Scoring | digest |
| Sealed pool | root commitment (never the root) |
| Frozen study sheet (admission §2) | commit, made before the run |
| Construction permission level and capability manifest | |

## 2. Track A: construction, reconstruction and attack

For each of the suite's vectors, then each challenge-specific attack:
attempted coverage, outcome, and open findings.

| Vector | Attempted | Findings | Open at freeze |
| --- | --- | --- | --- |
| 1 Admission | | | |
| 2 Execution isolation | | | |
| 3 Protected-data separation | | | |
| 4 Resource enforcement | | | |
| 5 Clean reconstruction | | | |
| 6 Artifact integrity | | | |
| 7 Evidence integrity | | | |
| 8 Adaptive exposure | | | |

The technical owner grades the findings still open at freeze as critical,
high, medium or low. Those counts are the pipeline record's `attC`, `attH`,
`attM` and `attL`. A clean run does not prove resistance to unrestricted
agents.

## 3. Track B: score to engineering value

- **EV1, EV2, EV3 and baselines:** the pre-registration commit, the panel,
  and the results with uncertainty.
- **Rank agreement ρ** (`rho`): the Spearman correlation between score and
  reference-measured value, across candidate models on the sealed pool.
- **Independent scenarios and false-feasible events** (`n` and `k`). The
  bound is computed by `carbon.challenge_pipeline.roadmap.ff_upper`. It is
  never typed in.
- **Regret** (`regret`): the mean shortfall of chosen feasible designs, as a
  percentage of the best.

## 4. Execution provenance and cost

The run's ledger, the hardware, the wall time and the spend category. No
balances, credentials or private configuration are recorded.

## 5. Limits

Untested surfaces, reproducibility limits, and the reference credibility
level the claims stand on.

## Track sign-offs

Left blank by the drafter. Each owner signs their track with the decision or
review that made it:
- the technical owner signs Track A, gate `track_a`;
- the science owner signs Track B, gate `track_b`.
