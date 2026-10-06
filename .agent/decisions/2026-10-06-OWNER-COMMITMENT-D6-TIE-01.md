## 2026-10-06 — OWNER-COMMITMENT-D6-TIE-01: a same-block tie under D6 goes to the earlier transaction

**Authority.** The owner, 2026-10-06, directly in the Test Engineer session.
The owner was answering the open question that #715 (Carbon Validator)
raised under OWNER-COMMITMENT-POSTER-01 D6:

> earlier transaction in the block wins

**The gap.** D6 says that when two hotkeys commit the same digest, the
earliest commitment block has priority. It does not settle two commitments
of the same digest in the same block. #715 refused both hotkeys (fail
closed). That would let a copier block the original miner by landing the
copied digest in the same block.

**Ruling.**
- **Within one block**, the commitment whose extrinsic comes first in the
  block's order has priority. A later extrinsic of the same digest is
  `commitment_contested`, exactly as a commitment from a later block is.
- **Across blocks**, D6 is unchanged: the earlier block has priority.
- **Fail closed:** when the validator cannot establish both extrinsics'
  positions in the block, it still refuses both.

**Scope.** This amends D6 only. It changes nothing in the miner's poster or
signer (#717), and it changes no scientific value, score, gate, threshold or
economic parameter. The Carbon Validator implements it in #715.

**Maturity.** SPECIFIED. #715 implements and tests it. Nothing here is LIVE.
