## 2026-10-07 — LAUNCHPAD-ACCEPT-02: the strategy commitment in the Launchpad and MCP

**Authority.**
- OWNER-COMMITMENT-POSTER-01 D1 to D10, and OWNER-COMMITMENT-D6-TIE-01.
- The ticket LAUNCHPAD-ACCEPT-02 (Launchpad Acceptance plan, step A1), and
  its delegated working decision: require a matching commitment before any
  submit through a rule-v2 validator.

Everything below is an engineering choice within that authority. No
scientific value, fee ceiling, pin, tempo or economic parameter is chosen,
and the validator, the intake and `commitment_record.json` are unchanged.

**Decisions.**

1. **Where the pre-submit read applies.** The Challenge's campaign declares it
   (`ChallengeCampaign.commitment` and `commitment_due`; battery today). It
   applies to the frozen candidate's first send through the Challenge's
   validator intake:
   - A validator deployment on this machine checks its own
     `require_commitment`, so the Launchpad does not gate it.
   - A submission the intake already holds is polled, not gated again. A
     resend after `commitment_required` or `commitment_stale` is the intake's
     to refuse (`intake.RECEIVED_AGAIN`), and the miner's next step is the
     refusal catalog's.
2. **Fail closed.** A read that fails refuses the submit
   `commitment_reader_unavailable`, with nothing signed or sent. A digest that
   cannot be worked out refuses `commitment_digest_unavailable`.
3. **A host that reads no chain gates nothing.** A `RunnerAdapter` built with a
   stubbed registration read (fixtures, the stdio journey test) has no
   commitment reader, as it has no signer probe today. Its submits are
   unchanged. This is not a security boundary: the validator still refuses
   every submission it requires a commitment for. A production host always
   reads the profile's chain.
4. **Two gates, one rule.** The door reads before it admits the submit, so the
   miner is told at once. The campaign's own submit
   (`battery.campaign._committed`) asks the same gate again just before the
   first send, which covers Graphite and the instant between the two reads.
5. **Graphite asks for its own commitment (D10).** In a campaign whose agent
   selects, the submit asks the signer itself. It goes on only after the miner
   has typed the digest's last 8 characters on the signer's terminal and the
   digest reads back at finality (L7). On a `commitment_stale` answer it asks
   once for a recommit. A miner's own submit never posts: it is refused
   `commitment_required` and the miner commits first.
6. **Closed codes.**
   - The signer's commit refusals reach the doors as their own enum values
     (`NOT_CONFIRMED`, `ALREADY_COMMITTED_THIS_TEMPO`, ...), as the
     uppercase transport codes already do.
   - The poster's codes are used as they are.
   - Each has its own step in the refusal catalog.
   - `commitment_reader_unavailable`'s step is widened to cover the
     Launchpad's own read. No code is renamed.
7. **The request field is `campaign`,** the table's field for every campaign
   operation, rather than the ticket's `campaign_id`.
8. **The extrinsic is named by the chain's id.** The pinned SDK's
   `ExtrinsicResult` carries no extrinsic hash. The read-back shows the digest,
   the block and the chain's extrinsic id `<block>-<index>` (`extrinsic_id`);
   no hash is computed.
9. **Where the records live.**
   - The poster's never-resend record is per hotkey, beside the runner
     database (`commitments/`), so every process of the principal shares it.
   - Each campaign keeps its last request (`commitment-request.json`).
   - A record left unsettled reads `RECONCILING` and is never resent.
10. **Testnet only (D5)** is held by the signer's pinned network
    (`WRONG_NETWORK`, `WRONG_NETUID`) and the SDK chain's genesis check. The
    Launchpad adds no network rule of its own.

**Security.** This touches hotkey authentication and chain writes. It needs
the owner's security review; the tests are engineering evidence, not an
audit. The acceptance is the plan's cells F10, F13 and A5.

**Maturity.** IMPLEMENTED and TESTED (CPU, a chain stand-in and the real
signer on a socket). Nothing here is LIVE.
