## 2026-10-12 — OWNER-STARTUP-HOST-CUSTODY-03-EXT-02: the EXT-01 shard may be split across up to 4 RunPod pods, which may self-terminate with RunPod's injected pod key

**Authority.** The owner, 2026-10-12, directly in the Carbon Validator
session, as a custody (security) acceptance (AGENTS.md §13):

> Split the CUSTODY-03-EXT-01 shard across up to 4 RunPod pods, same terms,
> and I accept the pods self-terminating with RunPod's injected pod key,
> since no untrusted code runs on them.

**Amends** OWNER-STARTUP-HOST-CUSTODY-03-EXT-01, for its one shard only.

**1. Up to 4 pods, same terms.**
- The EXT-01 shard (fresh sealed confirmation questions) may be split into
  at most 4 sub-shards, one per RunPod Secure Cloud CPU pod.
- **Every CUSTODY-03 / EXT-01 term applies to each pod:**
  - the stock ubuntu image;
  - the hash-verified exported solve environment;
  - only `openssh-server` installed;
  - no network volume;
  - SSH only;
  - connection logging at solve start, midpoint and end;
  - shred, then terminate.
- **Each pod's host-key fingerprint is confirmed by the owner in the Carbon
  Validator session before any export to it.** The root-owned custody file
  names all of the pods' host keys, on the line
  `OWNER-STARTUP-HOST-CUSTODY-01 startup <ID> (accepted under
  OWNER-STARTUP-HOST-CUSTODY-03, extended by
  OWNER-STARTUP-HOST-CUSTODY-03-EXT-01 and -EXT-02)`.
- **All-or-nothing across the pods.** The shard merges on the AX42 only when
  every pod's sub-shard is pulled, verified and clean. A confirmation set is
  one registered set. So if any pod's connection log shows a connection
  other than the AX42's SSH session:
  - that pod's questions are treated as exposed and recorded as exposed;
  - **the whole shard is not used as confirmation**;
  - no subset of the shard is ever substituted for the registered set.

**2. Self-termination with RunPod's injected pod key.**
- **The mechanism.** A pod may terminate itself (never stop) using the API
  key RunPod injects into the pod's environment. The AX42 and the agents
  hold no RunPod key, and none is created for this.
- **The owner's basis.** No untrusted code runs on the pods: only Carbon's
  pinned truth code and the exported, hash-verified environment.
- **Conditions:**
  1. **Order: pull, shred, terminate.** A pod self-terminates only after
     the AX42 has pulled and verified its sub-shard's records over the
     pinned SSH, and after the pod has shredded its files. If it is never
     pulled, it shreds and self-terminates at the registered maximum
     lifetime set in the run sheet. Its questions are then lost, never used.
  2. **The termination call is outside the solve window.**
     - Its outbound connection to RunPod's API happens after the shred, when
       the pod holds no question.
     - It is not one of the connection-log checkpoints, and it does not
       invalidate the run.
     - Any connection **during** the solve window, other than the AX42's
       SSH session, still invalidates the run, as in CUSTODY-03.
  3. **The key stays in the pod.** It is never printed, logged, copied off
     the pod, or used for anything but the pod's own termination.
  4. **Termination is confirmed from outside.** After each pod reports
     termination, the owner confirms in the RunPod console that the pod is
     **Terminated** (not stopped). That confirmation goes into the run
     record. A pod that isn't Terminated is terminated by the owner at once.

**Accepted residual, stated.** The injected key is present in the pod's
environment during the solve. Its scope is RunPod's, and the owner accepts
it on the stated basis that no untrusted code runs on the pods.

**Not permitted here:**
- more than 4 pods;
- any shard other than EXT-01's;
- any bank, validator or mainnet material on a pod;
- a RunPod key on the AX42 or with any agent;
- agent access to a pod.

Spend runs under its own grant, via PR Head.
