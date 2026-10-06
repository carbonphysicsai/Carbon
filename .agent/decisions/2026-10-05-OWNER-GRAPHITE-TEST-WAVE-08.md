## 2026-10-05 — OWNER-GRAPHITE-TEST-WAVE-08: operational testing in a mainnet-mimicked environment; score tuning on a sealed tuning set

**Authority.** The owner, 2026-10-05, in the Test Lead session.

The owner questioned the practice-score proxy:
> I'm not sure how or why we were doing it a fake way before. Doesn't seem
> like that was useful for score tuning at all.

Approving the Test Lead's plan, the owner said:
> It's a go. You're the lead. It's time to start real testing and tune this
> engine. We keep testing and keep learning. Test the gates and the hidden
> conditions. This is OPERATIONAL TESTING. We need to be testing in a mainnet
> mimicked environment so we catch and fix and tune everything properly.

**Supplements** OWNER-GRAPHITE-TEST-WAVE-01 to -07 and
OWNER-VALIDATOR-MAINNET-PARITY-01.

**What changes.** Score-to-value evidence so far used the PRACTICE score: the
deciding rule's form evaluated on public cases the agent had already seen. That
showed whether the rule's form tracks value. It was not operational evidence,
and it could not tune weights. From now on the wave's scoring evidence comes
from the real scoring path in a mainnet-mimicked environment.

1. **Three hidden case sets per challenge, each with its own job.**

   | Set | Job | Seen by agents or miners? | Used by us |
   |---|---|---|---|
   | Rotating hidden pool | Operational scoring through the real validator, as on mainnet (VALIDATOR-13) | Never; outcomes only through the miner allow-list | Continuously, rotated |
   | **Tuning set (new)** | Scoring every panel member, and comparing candidate score weightings | Never | Repeatedly, for score development |
   | Confirmation set | One final check that the tuned score isn't overfit to the tuning set | Never | Once |

   **Battery's tuning set.** Role `graphite-tuning-v1`, 200 cases plus 4
   hidden duplicates, drawn from the Level 0 study sheet's population. It is
   sealed, and solved on the operator host's CPU. It must not overlap EV5,
   `graphite-confirmation-v1`, the rotating pool, TRAIN, PRACTICE or the
   practice decision set. Sealing it is an operator action.

2. **Retest Level 0 on the real path.**
   - Graphite Constructor runs (battery, grant GRAPHITE-GRANT-PHASE3-R3) submit
     through the real validator against the rotating hidden pool. Graphite's
     agent sees only the mainnet miner outcome allow-list.
   - The panel is scored on the tuning set: Graphite's constructions, EV4's
     100 recipes and the constructed controls.

3. **The tuning loop.**
   - Each candidate score weighting is registered BEFORE it is computed.
   - It is re-scored from stored per-case tuning-set predictions, with no
     retraining.
   - It is compared against decision value on the development decision data,
     which no optimiser sees: τ/ρ with a band, regret, false-feasible rate and
     divergences.
   - The survivors become development score variants (VALIDATOR-09). Graphite
     then optimises against each one, to check whether its winner decides well;
     the Attacker tests each one in Mode X; and the gates are tested on the
     hidden and tuning sets.
   - The winner is confirmed once on the confirmation set. The owner adopts it
     as a new rule version.

4. **Two kinds of weights.**
   - SCORE weights (how the score is assembled) are tuned under §3.
   - The score-to-CHAIN-weight mapping (OWNER-VALIDATOR-MAINNET-PARITY-01) is
     tested as the second stage, on the same data, for top-k selection value.

5. **Sequencing.**
   - Battery first, then motor once its scorer exists, then cooling once its
     construction families widen.
   - New Level 1–3 construction-freedom work is paused until the Level 0 tuning
     loop works. Battery Level 1, already built, waits too.
   - The gates and the hidden conditions are tested as part of this loop, never
     on public practice cases alone.

**Kept.** Every rule protecting what the test can believe stays: no agent
access to hidden, tuning or confirmation material; grader separation; one-shot
confirmation; candidates registered before they are computed.

**No execution** happens through this record itself. Sealing and host solves
are operator actions. Spend stays within existing grants.
