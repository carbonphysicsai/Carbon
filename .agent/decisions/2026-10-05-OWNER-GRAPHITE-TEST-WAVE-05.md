## 2026-10-05 — OWNER-GRAPHITE-TEST-WAVE-05: motor scorer to Codex, a cooling Attacker grant, REF confirmation by best practice, and confirmation-set sizes

**Authority.** The owner, 2026-10-05, in the Test Lead session, answering the
Test Lead's four open items:

> codex builds scorer, approve, best practice, your best decision

The four answers map, in order, to the following decisions.

**Supplements** OWNER-GRAPHITE-TEST-WAVE-01 to -04.

1. **Codex builds motor's scorer.** The owner's answer: "codex builds scorer".
   - Codex builds the motor `ChallengeScoring` and the Interface v1 validator
     adapter for `electric-motor-magnetics`, as it did for cooling (#584,
     #586).
   - Until they merge, motor phase-4 Attacker runs stay blocked
     (`challenge_scoring_not_registered`).

2. **A phase-4 Attacker grant for cooling is approved.** The owner's answer:
   "approve".
   - The amounts are those proposed in #587: identical to
     GRAPHITE-GRANT-PHASE4.

     | Field | Value |
     |---|---|
     | Ceiling | USD 10.50 |
     | Cleanup allowance | USD 0.25 |
     | Worst case per run | USD 3.41 |
     | Permitted runs | 3, one at a time |
     | Maximum runtime | 15,600 s |

   - The grant is a new file. The runner must accept a grant only when it is
     the committed blob on main for the challenge named by `--challenge`.
   - A motor grant is proposed the same way once motor's scorer exists.

3. **REF confirmation follows best practice, which the owner delegated.** The
   owner's answer: "best practice". A live Graphite run may proceed without a
   separate owner confirmation of the REF when all of these hold, and the
   executor records them in the run's brief before launch:
   - the REF is a merge commit on `origin/main`, never a branch head;
   - it contains every PR the run's entry gate names;
   - the run's real-path no-spend check passes at that exact SHA. That means
     `phase4 prelive` for the Attacker, and `pods.real_path_check` with the
     dry run for the Constructor;
   - the installed checkout is clean at the REF, and setup has been redone
     after any reinstall, compute included;
   - the grant is the committed blob on main, within its permitted runs;
   - the host window is agreed with Data Collection.

   The executor sends the Test Lead the REF and the gate output before launch.
   Credentials are still entered by the owner. Anything that changes spend
   beyond an approved grant still needs the owner.

4. **Fresh confirmation-set sizes (Test Lead's decision, delegated).** The
   owner's answer: "your best decision". All sets are sealed on the operator
   host, used once for each challenge's final Track B evidence, and never
   touched by Graphite.

   | Challenge | Role | Size | Drawn from |
   |---|---|---|---|
   | Battery | `graphite-confirmation-v1` | 120 cases + 4 hidden duplicates | the Level 0 study sheet's population, as EV5 (OWNER-GRAPHITE-TEST-WAVE-01 §7) |
   | Cooling | `cooling-graphite-confirmation-v1` | 60 cases + 2 hidden duplicates | the chip-cold-plate DEVELOPMENT population law |
   | Motor | `motor-graphite-confirmation-v1` | 60 cases + 2 hidden duplicates | the motor DEVELOPMENT population law |

   For cooling and motor:
   - **Strata.** At least one third of the cases are drawn in each challenge's
     declared important or boundary region: motor current density
     ≥ 10 A/mm²; cooling's boundary-stress load and inlet range. The strata
     are reported separately.
   - **Why 60.** With 60 independent cases, zero events bound a rate at about
     4.9 % one-sided (95 %), the roadmap's `1 − 0.05^(1/n)`. Measured
     reference costs keep each set to roughly one counted campaign:
     - motor: about 0.8 core-hours per case on the operator host
       (calibration, 2 CPUs, p50 about 1,400 s);
     - cooling: about 0.5 allocated core-hours per case (the 48-case counted
       study).
   - **Overlap check.** No case may coincide with a TRAIN, PRACTICE,
     private-pool or study condition, nor any earlier batch.

   Sealing is an operator action through VALIDATOR-03's tooling. Solving a set
   on the operator host is scheduled by Data Collection like any campaign.

**No execution.** This record dispatches, provisions and spends nothing. The
grant file and the tooling ship in their own PRs.
