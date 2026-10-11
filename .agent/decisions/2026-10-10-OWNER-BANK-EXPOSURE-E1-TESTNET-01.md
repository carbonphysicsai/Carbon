## 2026-10-10 — OWNER-BANK-EXPOSURE-E1-TESTNET-01: testnet battery releases scores fast: E = 1, a 360-block rotation, a 24-hour bank

**Authority.** The owner, 2026-10-10.
- Relayed by the Test Lead, approving item 9 of `WEIGHTS_POLICY_VALV2.md`:
  > Yes, release scores faster for testing.

  and, on the window length:
  > yes we need to be able to score quickly in testing.
- **Directly in the Carbon Validator session**, after the Validator corrected
  item 9's estimate: at E = 2 a window releases only once all 98 of its cases
  are drawn a second time from the ~2,000-case bank, about 105 windows
  (~16 days), not ~7.2 hours. Asked which exposure valV2 should run, the
  owner chose **"E = 1, new rule"**, whose description read:
  > Register testnet rule v2-bank-e1 (a new version; E=2 records stay as
  > they are). Release ≈ 1,080 blocks (~3.6 h) after a window is drawn, plus
  > ~30 min of reveal/publish/feed timers. Each window consumes 98 fresh
  > solved cases (~650/day plus finals, double E=2), so the producer's solve
  > rate must keep up or windows stop (fail closed). Mainnet's E stays a
  > separate decision.
- **Asked next** which rotation the E = 1 rule should use, after the
  Validator corrected that release waits for a window's 3 active rotations,
  the owner chose **"360 blocks"**, whose description read:
  > One tempo (~72 min) per rotation. A score publishes ~1,080 blocks
  > (~3.6 h) after its window opens. ~3,900 solved cases/day, ~99 CPU-h/day
  > of refill (~26% of the AX42); a full 2,000-case bank covers ~12 h, so
  > the refill timer runs continuously.
- **Relayed by the Test Lead afterwards:** the owner agreed the bank reserve
  covers at least 24 hours of draws, kept there by the refill timer.

**Decided (testnet only, DEVELOPMENT):**
- **Rule `v2-bank-e1-r360`.** It is `v2-bank` with:
  - **E = 1:** each case serves exactly one window;
  - **rotation 360 blocks:** with v2's 3 active rotations, a window's scores
    publish about 1,080 blocks (~3.6 h) after it opens, plus the producer
    tick, push and feed-build timers;
  - **B = 4,000 live cases:** two windows of 98 cases a rotation, 20
    rotations a day, is 3,920 cases;
  - **refill by the operator's timer, never inside a tick** (`top_up: False`).

  It is a new rule version. `v2`, `v2-bank` and `v2-bank-e2` history is
  unchanged (invariant 10), and a deployment moves to the rule by naming it,
  as a new deployment.
- **Release** follows OWNER-AUTO-PUBLISH-RETIRED-01. The producer's tick
  reveals each ended window and publishes its retired cases, signed, into
  the training pool. A case drawn by a live window is never published, and
  a published case is never drawn again by any producer on that bank.
- **Fail closed:**
  - A short bank leaves the slot unfilled (`bank_short`) and never reuses a
    case.
  - Each tick reports `BANK_LOW` when fewer than half of B are live.

**Not decided here:**
- mainnet's E, rotation and bank size;
- the rule-v3 composition (`v3-bank-e1-r360`), which follows VALIDATOR-26;
- a per-Challenge derivation of E and rotation from solve cost and an
  owner-set refill budget, whose budget values are the owner's;
- security acceptance. Publishing hidden cases is security-sensitive and
  goes to the owner's review.
