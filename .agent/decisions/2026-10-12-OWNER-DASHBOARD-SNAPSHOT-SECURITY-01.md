## 2026-10-12 — OWNER-DASHBOARD-SNAPSHOT-SECURITY-01: the dashboard's signed network snapshot may reuse the validator's feed key

**Authority.** The owner, 2026-10-12, directly in the PR Head session, in two
answers. This record exists because the acceptance was given in session and
had no repository trace: #1137 arrived as code with its review outstanding
rather than as a record to merge, and the Test Lead asked for the acceptance
to be written down rather than left in a transcript.

**What was asked, and what he answered.**

1. Asked whether the dashboard's network snapshot may be signed with the
   validator's existing feed key under a separate domain tag, rather than
   issuing a second key — the tradeoff being that one key would then attest
   two document types, so a feed-key compromise could forge snapshots too.
   He chose:

   > Approved — reuse the feed key

2. The Test Lead then held the merge, on the ground that a key-reuse approval
   covers one part of a security review and not the review. Asked whether his
   answer covered #1137's security review as a whole or only the key choice,
   with the alternatives being that it was key-only and the rest waited for a
   morning review, or that he wanted it walked through in full first. He
   chose:

   > It covers the review — merge it

**Accepted.** #1137 (DASHBOARD-02 S3, the signed network snapshot), merged at
`b1a775f96`, under the four properties below. This is a security acceptance of
that change (AGENTS.md §13). It is not a scientific, production or network
qualification of the dashboard or of anything the snapshot reports.

**The four properties the acceptance rests on.** These were verified by the
PR Head session and summarised to the owner before he answered; they are
review findings, not his assertions.

1. **Domain separation, tested both directions.** The signed bytes are
   `SNAPSHOT_DOMAIN` followed by the snapshot without its `signature` field,
   canonical as the feed's. The domain is never the feed's `FEED_DOMAIN`, so a
   snapshot signature never verifies as a feed and a feed signature never
   verifies as a snapshot. Covered by
   `tests/cpu/test_challenge_validator_network_snapshot.py::test_a_snapshot_signature_never_verifies_as_a_feed_and_back`.
   `SnapshotKey` signs under `SNAPSHOT_DOMAIN` only.
2. **Public chain data only, with an explicit exclusion list.** Per UID: uid,
   hotkey, incentive, emission, total stake and validator permit, plus the
   block number, hash and timestamp read at, and the network. Nothing else:
   no coldkey, axon address, commitment, submission, score, private or hidden
   state. Reads use the validator's existing public reads inside the chain
   boundary (`carbon.chain.metagraph_read`) at one finalized block,
   genesis-checked, with the hash re-read after the reads. No raw RPC and no
   new dependency.
3. **Never an evaluation input.** Scoring and weights code cannot import the
   module, enforced by
   `tests/invariants/test_network_snapshot_unreachable.py`. The dashboard
   cannot become an input to what it displays.
4. **The pinned key is unchanged.** The dashboard continues to pin the one
   feed key, so the acceptance adds no key distribution or trust step. The
   `sign` op and the feed path are unchanged.

**The residual the owner accepted.** One key attests two document types. A
compromise of the validator's feed key would allow forging both feeds and
snapshots; a separate snapshot key would contain that, at the cost of a second
pinned public key in the dashboard. He chose reuse with domain separation.

**Scope.** DEVELOPMENT only: no qualification, score, weight, reward, LIVE or
mainnet authority follows. `carbon/challenge_validator/network_snapshot.py`
states the same.

**Not decided here.** Whether a future signed document type may also reuse this
key — that is a fresh decision each time, not a precedent this record sets.
