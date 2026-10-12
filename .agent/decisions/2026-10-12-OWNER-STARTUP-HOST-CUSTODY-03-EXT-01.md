## 2026-10-12 — OWNER-STARTUP-HOST-CUSTODY-03-EXT-01: a second SCORE-PROOF-01 shard, of fresh sealed confirmation questions, on RunPod under CUSTODY-03's terms

**Authority.** The owner, 2026-10-12, directly in the Carbon Validator
session, as a custody (security) acceptance (AGENTS.md §13):

> I extend CUSTODY-03 to a second SCORE-PROOF-01 shard: fresh sealed
> confirmation questions solved on RunPod, same custody terms.

**Extends** OWNER-STARTUP-HOST-CUSTODY-03. That record allowed one
SCORE-PROOF-01 shard of sealed testnet tuning questions on a RunPod Secure
Cloud CPU pod. This record allows **one more SCORE-PROOF-01 shard**, made of
**fresh sealed confirmation questions**.

**Same custody terms.** Every term of CUSTODY-03 and its same-day amendments
applies unchanged:
- **The pod:** stock `ubuntu:24.04` at the truth worker's base digest, with
  only `openssh-server` installed from Ubuntu's signed apt repository (its
  version goes into the run record).
- **The solve environment:** the truth image's `/opt/carbon-worker` and
  `/opt/uv-python`, exported from the AX42's pinned copy and verified by
  file-tree hash and by python, numpy and scipy versions on both sides
  before any sealed shard is pushed.
- **Transfers:** SSH only, over exposed TCP, with the pod's host-key
  fingerprint confirmed by the owner in the Carbon Validator session before
  any export. There is no network volume and no `rsync`.
- **Connection logging:** `ss -tnp` (or `/proc/net/tcp*`) at solve start,
  midpoint and end, with the web terminal closed. **Any connection other
  than the AX42's SSH session invalidates the run.** Its questions are
  treated as exposed and are recorded as exposed. **They are never used as
  confirmation**, and none of them is used to score.
- **What leaves the AX42:** only the shard. The merge on the AX42 is
  all-or-nothing, and every transfer is journaled.
- **Teardown:** shred, then **Terminate** (never stop). The exit check
  applies.
- **The custody file:** root-owned, naming the standing record as the r8
  code requires: `OWNER-STARTUP-HOST-CUSTODY-01 startup <ID> (accepted
  under OWNER-STARTUP-HOST-CUSTODY-03, extended by
  OWNER-STARTUP-HOST-CUSTODY-03-EXT-01)`, plus the pod's host key.
- **The residuals accepted in CUSTODY-03 are accepted again:**
  - the provider's host access to a container;
  - no VM boundary and no firewall of ours;
  - an unverifiable shred on copy-on-write disk;
  - deletion by RunPod's termination;
  - a solve that holds sealed questions with network access (pinned
    environment only).

**What "fresh sealed confirmation questions" means:**
- They are newly drawn for this shard on the AX42, journal-committed and
  sealed before any export.
- **They are not** EV5's sealed batch (journal sequence 14), not
  `graphite-confirmation-v1`, not this proof's first (tuning) shard, and not
  any other set already drawn or used. Those are never read, regenerated or
  reused for this shard.
- A confirmation set is used once. These questions confirm SCORE-PROOF-01's
  pick and are then spent.

**What a confirmation set on a pod adds.** A sealed set used for
confirmation is the strongest-held material in the proof. On a pod, the
provider's access and the unverifiable shred apply to it. The connection-log
invalidation is the control: an invalidated run's questions are never used
as confirmation. The owner accepted this as "same custody terms".

**Not permitted here:**
- anything CUSTODY-03 does not permit;
- a third shard;
- any bank, validator or mainnet material on a pod;
- a kept or stopped pod;
- agent access to the pod.

Spend runs under its own grant, via PR Head.
