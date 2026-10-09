# Canary miner plan (CANARY-01)

**Status:** SPECIFIED. This is a plan. Nothing here is built, rented or run.

**Authority.**
- The owner, 2026-10-08, relayed by the Test Lead: "I approve the canary
  miner(s)." (OWNER-CANARY-MINER-01).
- **Unattended commitments** depend on a second owner decision, relayed
  the same day: "approve testnet auto-confirm for test hotkeys"
  (SIGNER-AUTOCONFIRM-01). That flag is a separate ticket. It is not built,
  and it waits for the owner to confirm it in the building session (§3).

**Purpose.** A Carbon-owned miner drives the **real path** through the
Launchpad on every window, exactly as a mainnet miner would:
1. freeze, commit and submit to each live validator (valV2 now, valV3
   later);
2. check that a sealed verdict arrives within a registered deadline;
3. check that the weights publication then happens and treats the canary
   as excluded.

When a stage misses its deadline, the canary alerts through Ops 2
(healthchecks.io dead-man pings) and names the stage. It is a monitor, not
a competitor.

**Basis.** A5 (2026-10-08) proved the path once by hand: commitment at block
8178423, then a sealed SCORED verdict for `bsub-baf1508d…`. It also showed
why a canary is needed:
- the submission waited because slot 7572's batch had not been published,
  a validator-side stall that nothing alerted on;
- the validator answered `snapshot_unavailable` once while it synced;
- a person had to be present at the signer terminal for the commitment.

---

## 1. What the canary does, each cycle

1. **Read the door's public facts** (`GET /carbon/v1/battery/intake`):
   - network, genesis, netuid, challenge and receiver;
   - `snapshot.finalized_block`;
   - `submission_rule.current_window` and `rotation`.

   A door that doesn't answer is the stage `door`.
2. **Pick this cycle's recipe** from a registered list of variants (§2).
   Each one is a new strategy, so it is a new submission.
3. **Through the Launchpad's MCP door**, as an own-agent miner: launch (or
   resume), practise once on CPU, freeze, `carbon_commit`, then
   `carbon_submit`.
4. **Watch the outcome** with signed `battery_status` reads for its own id,
   through the Launchpad's readback. The state transitions are the stage
   clock: admitted → scoring → sealed verdict.
5. **After the verdict, read the chain:**
   - the validator's weights publication for that epoch happened;
   - the canary's UID got no weight (§5).
6. **Report.** One success ping per completed cycle. On a miss, a failure
   ping that names the stage, plus a journal line with the closed code.

**Stages the canary can see from the miner side:**

| Stage | How it is seen |
|---|---|
| `door` | the intake facts read answers |
| `window` | `current_window` advances on schedule |
| `commit` | the commitment reads back at finality |
| `admission` | `battery_status` shows the submission admitted |
| `scoring` | `battery_status` shows it in scoring |
| `verdict` | a sealed outcome arrives |
| `weights` | the publication is on chain, with the canary at zero |

**Stages only the validator host can see** (producer publish, dist push and
import, answer-key sync) stay with the Carbon Validator's existing Ops 2
checks (`ax42-tick`, `ax42-push`, `ax42-door`). Two new ones are proposed
for the Carbon Validator: `ax42-answer-key-import` and `ax42-rotation`.

The canary never reads hidden material, and never touches the AX42 or the
distribution host.

## 2. One submission per window, and same-recipe replay

- **The limit.** Rule v2 allows one scored submission per hotkey per
  360-block window (`exam.py` `per_hotkey`). The id is
  `bsub-`+`digest{hotkey, challenge, strategy, contract}`, so the same recipe
  resubmitted later is **the same submission**: it is never re-scored. There
  is no miner seed (the seed is Carbon's reconstruction randomness).
- **So each cycle's recipe differs.** The cheapest registered method is
  `knn`; its rebuild has no training loop. The variants step through:
  - `neighbours`: 1–64, default 5;
  - and/or `train_fraction`: 0.1–1.0, a seeded TRAIN subset.

  These are registered surfaces, so every variant is a real, rebuildable
  submission of the same method.
  - **Proposal:** a committed list of N variants (for example
    `neighbours` 2…33 × `train_fraction` {1.0, 0.95}), used in order.
  - The list is regenerated when the contract digest changes.
- **Cadence.**
  - **Proposal:** one cycle per producer rotation (1080 blocks, about 3.6 h).
    That is 3 tempos, which leaves a retry tempo, and stays far under the
    rehearsal's load ceiling (60 rebuilds a day across hotkeys).
  - D4 (one commitment per tempo) and D6 (a commitment must postdate the
    previous admission) both hold naturally: one commitment per cycle,
    posted just before its submission.
- **Cost.** One kNN CPU practice plus one CPU rebuild at the validator per
  cycle. That's measured in seconds of CPU on the miner side, with no model
  spend: the canary is an own-agent campaign driven by a script, with no
  LLM.

## 3. Unattended commitments

**The problem.** Every commitment needs a person at the signer's terminal
(OWNER-COMMITMENT-POSTER-01 D10: "an agent can never confirm").

**Owner decision, relayed 2026-10-08** ("approve testnet auto-confirm for
test hotkeys"): SIGNER-AUTOCONFIRM-01 adds an opt-in signer flag. It
auto-confirms a commitment only when all of these hold:
- it is a chain commitment of a Carbon strategy digest;
- the genesis is testnet 567's;
- the signer's hotkey is in the owner's allow-list file;
- the fee is within the ceiling;
- at most one per hotkey per tempo.

Every auto-confirm is printed and logged.

**Status.** Blocked. The auto-mode classifier refused the build in the
Launchpad Acceptance session as a security weakening. It waits for the owner
to confirm the decision, and the permission, in the building session. The
canary needs it before it can run unattended. Until then, the canary can run
attended: the owner confirms at the terminal, which is useful for proving
the stage checks.

**Risk** (for the decision record):
- The flag removes a human from **commitments only**, for allow-listed
  testnet hotkeys only.
- The larger exposure is the key itself. An unattended signer needs an
  unlocked hotkey on an always-on box. Anyone who takes that box can sign
  anything with that hotkey directly, flag or no flag.
- So the canary hotkey must be worth nothing beyond testnet registration:
  - its own coldkey, with test TAO only;
  - no stake;
  - never on a mainnet genesis.
- The genesis check refuses mainnet at startup and on every request.

## 4. Which hotkey

**Recommended:** a new, dedicated `carbon-canary` hotkey on **its own
coldkey**, which the owner creates, funds with test TAO and registers on 567.
- It isn't one of minerD–G, which belong to Graphite's confirmation lane,
  because one commitment per hotkey per tempo would collide.
- It isn't on the owner's coldkey either: a canary win on an owner-associated
  key makes the weights publication fail
  (`OWNER_ASSOCIATED_WINNER_WOULD_BURN`) rather than skip it.

## 5. Its scores must never win

**The hazard is real.** On testnet the canary may be the only miner whose
submission passes the gates.
- A gate-eligible first submission becomes the **first incumbent** with no
  comparison (`nominate`: "no incumbent").
- The winner takes the Challenge's weight share
  (`testnet_winner_publication`).
- A deliberately weak baseline still passes the gates, so being weak is
  not enough.

**Proposal: a registered canary list on the validator side** (the Carbon
Validator's domain).
- The validator reads an owner-recorded list of canary hotkeys.
- Their submissions are admitted, rebuilt and scored as usual, so the path
  is exercised, but they are never nominated or incumbent, never in
  standings, and never in weights.
- This mirrors how `graphite-dev:` identities are already kept out of
  incumbency and weights (`daemon.py`).
- The list is versioned, and every exclusion is logged.

**Plus, belt and braces:** the canary's recipes stay deliberately baseline
(kNN), so even a misconfigured validator would rarely promote one.

**What the canary checks:** at each weights publication after a canary
verdict, the canary's UID has weight 0. A non-zero weight is the stage
`weights` failing, an alert that also catches an exclusion regression.

## 6. Where it runs

| Option | Cost | Reaches the door | Always on | Notes |
|---|---|---|---|---|
| carbon-fresh (owner PC) | none | yes, via the existing tunnel | no | Misses windows while the PC sleeps; good for building and attended runs |
| Small always-on box (e.g. Hetzner CX23: 2 vCPU, 4 GB, 40 GB) | about EUR 4.49/month listed; read the price at order | needs its own tunnel key or a public door | yes | Must use `install_miner.sh --release`, which pulls images instead of building (4 GB RAM is too little to build them) |
| The AX42 | none | — | yes | **No:** the validator host holds hidden material, and a miner must not share it |

**Recommendation:**
1. Build and prove it on **carbon-fresh**, attended at first.
2. Move it to a small always-on box once:
   - SIGNER-AUTOCONFIRM-01 exists;
   - and either a public testnet door exists on a validator-only host
     (OWNER-AX42-DOOR-PRIVATE-01's next step), or the owner gives the box
     its own tunnel key.

Renting the box is an owner purchase (a grant line).

## 7. Deadlines and alerts

- **Deadlines are owner-set values (HUMAN_INPUT).** The plan proposes them
  from measurements and doesn't invent them. A5 measured:
  - commit to finality: about 60 s;
  - submit to 202: under 30 s;
  - 202 to verdict: from the validator's records, once slot 7572 was
    published.

  The canary's first attended runs measure each stage, and the owner then
  sets each deadline from the distribution.
- **Alerts** follow Ops 2's pattern:
  - one healthchecks.io check per canary (period: one cycle; grace: the
    owner-set deadline);
  - a success ping per completed cycle;
  - on a stage miss, a `/fail` ping whose body names the stage.

  That is one more check on a free plan of 20, which has 7 in use.

## 8. Slices

1. **CANARY-01 S1: the canary runner**
   (`scripts/dev/canary/` or `carbon/canary/`).
   - It drives the Launchpad's MCP door as an own-agent client, with the
     registered variant list.
   - It measures stages from the Launchpad readback and the intake facts.
   - It writes a journal, and pings as in §7.
   - Tests use the loopback intake and fixtures. Engineering evidence only.
   - **Built** in `scripts/dev/canary/`, with 320 registered kNN variants.
     The owner's steps are in [`CANARY_RUNBOOK.md`](./CANARY_RUNBOOK.md).
2. **CANARY-01 S2: the weights check.** It reads the validator's publication
   for the epoch after a verdict, and checks the canary's UID weight is zero.
3. **Carbon Validator (VALIDATOR domain): the registered canary list,**
   excluded from nomination, standings and weights, plus the two Ops 2
   checks in §1.
4. **SIGNER-AUTOCONFIRM-01** (§3), blocked as stated.
5. **Acceptance:** three attended cycles on carbon-fresh (stage timings
   recorded), then the owner sets the deadlines, then unattended on the box.

## 9. Owner decisions this plan needs

Answered 2026-10-08, recorded in OWNER-CANARY-MINER-01:
- "approve canary 2-4": items 2, 3 and 4, as recommended;
- "Approve all": item 6 (one cycle per rotation), plus item 1 again.
  Item 1's build is blocked by the auto-mode classifier, not by the owner.

Item 5, the deadlines, waits for measured runs.

1. **Unattended commitments:** confirm SIGNER-AUTOCONFIRM-01 in the building
   session, and grant that session the permission the classifier asked for.
2. **The hotkey:** a new `carbon-canary`, on its own coldkey (recommended).
3. **Excluding canary scores:** approve a registered canary list on the
   validator (recommended), as a new record, since it changes who can be
   incumbent.
4. **Where it runs:** carbon-fresh first; later an always-on box. That needs
   a purchase approval, and a tunnel key or a public door.
5. **Deadlines:** set from the first attended runs' measurements.
6. **Cadence:** one cycle per 1080-block rotation (proposed).
