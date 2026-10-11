## 2026-10-11 — LA-F18-OBSERVE-VERDICT-READ: observe reads a queued verdict through a read-only signer kind

**Authority.** The Test Lead's ruling of 2026-10-11 on LA-F18
(`docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`):
build the proposed follow-up of
`2026-10-08-LAUNCHPAD-FINDINGS-F15-F18.md` decision 4, read-only, bounded,
on its own read-only signer request kind, never widening
`--auto-confirm-commitments`. It amends decision 4 there; that file is not
rewritten. It touches the miner's signer, so it waits for the owner's
security review before merge. No scientific value, threshold, gate, price or
budget changes.

**What status reads used before.** `remote_submission.submit_and_wait`
signs every `battery_status` poll through the signer's generic `sign` op
(`BittensorMessageSigner.sign`). That op is not a commitment and signs
unasked, but it sees only the `btauth/1` payload, so only the hash of the
body: it signs a `battery_submit` admission, or a Level 4 envelope part, just
the same. The kinds are not distinguishable at the signer, so a new kind was
added rather than `sign` reused.

**Decisions.**

1. **A new read-only signer kind, `status_read`.** The request carries the
   payload and the body it covers. The signer signs only when the payload
   passes every `sign` check (`refusal_for`: its hotkey, a fresh nonce, the
   receiver allow-list) for the MCP target only, the payload's body hash is
   the body's sha256, and the body is the canonical form of one Carbon
   request whose tool is `battery_status` and whose fields are exactly
   `{"submission_id": "bsub-<32 hex>"}`. Anything else is
   `NOT_A_STATUS_READ` or `MALFORMED_REQUEST`, signing nothing. It never
   reads the commitment policy, the commitment ledger, the terminal or the
   auto-confirm allow-list. An older signer answers it `MALFORMED_REQUEST`,
   and observe then reads nothing.
2. **Signed unasked on every network.** A status read changes nothing at
   the validator and spends nothing, and `sign` already signs the same read
   unasked on any network, so the narrower kind asks nothing either. It is
   not an auto-confirm: `--auto-confirm-commitments` still covers exactly
   the commitments it covered, and a commit sent through `status_read` is
   refused.
3. **Carbon's side.** `ExternalSigner.status_reader(body)` gives a
   `StatusReadSigner` bound to that body, whose only request is
   `status_read`; `BittensorMessageSigner.sign_status_read` and
   `remote_submission.read_status_once` use it. Submit's own polls are
   unchanged.
4. **Bounded.** Observe reads only the open epoch with a recorded submission
   (`intake-submission-epoch-N.json`) and no verdict; at most once per epoch
   per `READ_INTERVAL_S` = 60 s (an engineering bound, twice `POLL_S`), the
   time recorded in `intake-status-read-epoch-N.json` before the read is
   sent; one read at a time per process; only where submit itself would be
   admitted, so in a campaign where the miner selects, with nothing running
   or queued for it. A Level 4 candidate, never sent, is not read. The
   signer is reached only once a read is due.
5. **Stored as a replayed submit stores it.** One feedback builder
   (`battery.campaign.intake_feedback`) and one store (`record_verdict`,
   then `research_campaign.after_stored_verdict`), under the campaign's
   ownership lock and a control generation, settled as `_operate` settles.
   A refusal, an unreachable intake or signer, or an answer that is not a
   verdict changes nothing but the read's recorded time.
6. **The next step.** `NEXT_ACTIONS["evaluation_queued"]`,
   `intake_client.REFUSALS["evaluation_queued"]` and
   `FRESH_MINER_JOURNEY.md` step 10 no longer tell the miner to submit
   again.

**Tests.** `tests/cpu/test_observe_queued_verdict.py`;
`tests/cpu/test_launchpad_supervisor.py`'s LA-F18 next-step test, whose
expected text this changes.
