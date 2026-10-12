## 2026-10-12 — OWNER-SCORE-PROOF-CONFIRM-02-GRANT: USD 25 for the sealed confirmation run on RunPod

**Authority.** The owner, 2026-10-12, typed directly in the PR Head session:

> Approve SCORE-PROOF-CONFIRM-02 grant, USD 25, RunPod, sealed confirmation
> questions

**The grant.**
- **Cap: USD 25**, all in. A ceiling, not a target.
- **Platform:** RunPod, for the SCORE-PROOF-01 confirmation shard.
- **What it is for:** the second SCORE-PROOF-01 shard, carrying fresh sealed
  confirmation questions, against the owner's pick
  `G-FEAS+ENV/A-Q@0.01` (`OWNER-SCORE-PROOF-PICK-01`) with the rule in force
  `G-FEAS/A-Q>@0.05` as the registered contrast.

**Custody is separate, and this grant does not supply it.** Sealed
confirmation questions on a rented container is a security acceptance, not a
spending one. When this grant was approved, no custody record covered it:
`OWNER-STARTUP-HOST-CUSTODY-03` is scoped to "today's score proof" of
2026-10-11 with sealed *tuning* questions, and `-04` covers the daily
championship batches. The owner was asked separately and accepted custody for
the confirmation run **on CUSTODY-03's terms**:

> Yes — same terms as CUSTODY-03

Those terms, as -03 and its amendment record them: stock `ubuntu:24.04` at the
truth worker's base digest plus `/opt/carbon-worker` and `/opt/uv-python`
exported from the AX42's pinned truth image and hash-verified; the pinned SSH
host key confirmed per pod; established connections logged with `ss -tnp` at
solve start, midpoint and end, with any connection other than the operator's
own SSH session invalidating the run and treating the questions as exposed;
shred then Terminate; the AX42 remaining producer of record.

The Carbon Validator session is recording that acceptance as
`OWNER-STARTUP-HOST-CUSTODY-03-EXT-01`, which the owner also gave directly in
that session. **No sealed confirmation material goes to a pod until that
record is merged**, independently of this grant.

**Not authorized by this.**
- No second pod, no repeat run, and no overrun past USD 25. An overrun needs
  its own owner acceptance, as the first score-proof pod's did
  (`OWNER-SCORE-PROOF-RUNPOD-OVERRUN-01`).
- Nothing scientific. A confirmation verdict is not adoption: per
  `OWNER-SCORE-PROOF-PICK-01`, adoption into any deployment's scoring needs
  its own owner record, and only if the verdict is PROVEN.

**The hard stop still applies.** `OWNER-SCORE-PROOF-RUNPOD-OVERRUN-01`
recorded that a pod under a capped grant needs a termination that does not
depend on the owner being at the PC. That lesson applies to this run; the
operator sheet should name the stop before the pod is created.

**Spend figures.** The pod's hours and charge go in the operator's private
ledger. The public repository holds caps and rates, never spend totals.

**Maturity.** DEVELOPMENT spending authority only.
