## 2026-10-07 — OWNER-AUTO-PUBLISH-RETIRED-01: retired bank cases publish automatically to each Challenge's public training pool

**Authority.** The owner, 2026-10-07:
- "auto-publish retired", relayed by the Test Lead;
- confirmed directly in the Carbon Validator session. Asked whether retired
  cases should publish automatically, and where, they chose "Yes, via
  answers host (Recommended)".

It amends OWNER-BANK-ARCHITECTURE-01's release clause and the scope of
OWNER-ANSWER-KEY-INTAKE-EXPOSURE-01. It realizes the training-pool release
path that OWNER-VALIDATOR-MAINNET-PARITY-01 and OWNER-BATTERY-3B-AND-EXPOSURE-01
name (`CARBON_COMMIT_TO_TRAINING_POOL`).

**What publishes, automatically, per Challenge:**
1. **Only retired cases.** A bank case publishes only after it retired at E,
   from the pool, a quiz stratum or the canary.
   - A case still within its E budget can never be published
     (`bank_case_not_retired`).
   - Tuning, confirmation, study and EV material live in their own custodies
     and are never banked (`bank_name_not_bankable`), so they never publish.
2. **Reveal first.** A case publishes only after every window that drew it
   has ended and its selection is journaled (`window_revealed`), so the
   window's commitment can be checked first (`bank_window_not_revealed`).
3. **Integrity.** Each publication is a training file signed with Carbon's
   producer key. Each case carries its inputs, reference, tranche and Merkle
   proof, and the file its tranche commitments. Anyone can check it came
   from the sealed bank (`training_pool.verify`).
4. **Graphite.** The attack knowledge store and Graphite never receive an
   unretired case. They see only what the public training pool serves.

**Where:** the distribution host (`answers.carbonphysics.ai`), read-only and
public:
- `GET /carbon/v1/training/<challenge>`;
- `GET /carbon/v1/training/<challenge>/<file>`.

The producer pushes `training/<challenge>/` beside the packages, over the
existing write-only push. Every request is logged. The host verifies every
file before listing or serving it, and serves nothing else on this path.

**Unchanged:**
- hidden batches, quizzes and canaries stay sealed while live;
- answer-key packages still go only to permit holders;
- no qualification, LIVE, reward or production claim.
